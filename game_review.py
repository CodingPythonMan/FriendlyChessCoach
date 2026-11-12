"""Bounded PGN import and stateless, resumable Stockfish review batches."""
import hashlib
import io
import chess
import chess.pgn
import chess.engine
from coaching import move_notes, coach_line, priorities
from openings import key, names, guide
from review_explanations import compare_moves

MAX_PLIES=512

class QuietBuilder(chess.pgn.GameBuilder):
    def handle_error(self,error):
        self.game.errors.append(error)


def parse_game(text):
    if not isinstance(text,str) or not text.strip():
        raise ValueError('체스닷컴에서 복사한 PGN을 붙여넣어 주세요.')
    text=text.strip().lstrip('\ufeff').strip()
    if len(text.encode('utf-8'))>150000:
        raise ValueError('PGN이 너무 커요. 한 게임, 150KB 이하로 가져와 주세요.')
    stream=io.StringIO(text)
    try:
        game=chess.pgn.read_game(stream,Visitor=QuietBuilder)
        if game is None or game.errors:
            raise ValueError('PGN 수순을 읽지 못했어요. 합법적인 수인지, 전체 게임을 복사했는지 확인해 주세요.')
        if game.headers.get('Variant','Standard') not in ('Standard','Chess','Normal'):
            raise ValueError('지금은 일반 체스 PGN만 지원해요. 체스960 등 변형 체스는 지원하지 않아요.')
        board=game.board()
        if board.chess960 or not board.is_valid():
            raise ValueError('PGN의 시작 포지션이 올바른 일반 체스 포지션이 아니에요.')
        moves=[];opening=None;start=board.fen();states=[position_state(board)]
        for move in game.mainline_moves():
            if len(moves)>=MAX_PLIES:raise ValueError('한 게임에 최대 512반수(양쪽 합계)를 가져올 수 있어요.')
            if board.is_game_over() or move not in board.legal_moves:
                raise ValueError('게임 종료 뒤의 수나 합법적이지 않은 수가 들어 있어요.')
            before=board.fen();san=board.san(move);number=board.fullmove_number;color='white' if board.turn else 'black'
            board.push(move);states.append(position_state(board))
            moves.append(dict(move=move.uci(),san=san,fen=before,after=board.fen(),number=number,color=color))
            if len(moves)<=24 and key(board) in names():
                row=names()[key(board)];opening=dict(name=row['name'],eco=row['eco'],ply=len(moves))
        if not moves:raise ValueError('이동 기록이 없어요. [Event ...] 태그와 1. e4 같은 수순을 함께 복사해 주세요.')
        if chess.pgn.read_game(stream,Visitor=QuietBuilder) is not None:
            raise ValueError('게임이 여러 개 들어 있어요. 한 번에 한 게임만 가져와 주세요.')
    except (ValueError,TypeError,IndexError) as exc:
        if isinstance(exc,ValueError):raise
        raise ValueError('PGN 형식이 올바르지 않아요.') from exc
    return dict(id=hashlib.sha256(text.encode()).hexdigest(),pgn=text,headers=dict(game.headers),
                start_fen=start,fen=board.fen(),initial=states[0],positions=states,moves=moves,total=len(moves),opening=opening,
                note='본선 수순만 가져왔어요. 주석·변화수는 리뷰하지 않으며, 기보의 결과와 판의 체크메이트 여부는 다를 수 있어요.')


def classify(best_score,played_score,is_best=False,mate=False):
    loss=max(0,best_score-played_score)
    if mate:return '체크메이트!',0,0
    if is_best:return '엔진 첫 후보',0,0
    if loss<50:return '무난한 수',0,loss
    if loss<100:return '아쉬운 수',1,loss
    if loss<200:return '실수',2,loss
    return '큰 실수',3,loss


def review_move(engine,board,move,index,thorough=False):
    mover=board.turn;san=board.san(move);played_pv=[move]
    best_info=engine.analyse(board,chess.engine.Limit(time=2) if thorough else chess.engine.Limit(time=0.25,depth=12))
    pv=best_info.get('pv',[])
    if not pv:raise RuntimeError('엔진의 추천 수를 받지 못했어요.')
    best=pv[0];best_score=best_info['score'].pov(mover)
    after=board.copy();after.push(move)
    terminal=after.outcome(claim_draw=False)
    if terminal:
        played_score=chess.engine.Cp(0) if terminal.winner is None else -chess.engine.Mate(0) if terminal.winner==mover else chess.engine.Mate(0)
    elif move==best:
        played_score=best_score;played_pv=pv
    else:
        played_info=engine.analyse(board,chess.engine.Limit(time=2) if thorough else chess.engine.Limit(time=0.25,depth=12),root_moves=[move])
        played_score=played_info['score'].pov(mover);played_pv=played_info.get('pv',[move])
    # Mate scores are bounded for ranking; separate mate fields preserve their meaning in the UI.
    before_cp=best_score.score(mate_score=10000);after_cp=played_score.score(mate_score=10000)
    grade,severity,loss=classify(before_cp,after_cp,move==best,after.is_checkmate())
    if severity>=2 and not thorough:
        return review_move(engine,board,move,index,thorough=True)
    if best_score.mate() is not None and best_score.mate()>0 and played_score.mate() is None and move!=best:
        grade='메이트 수순 이탈 추정';severity=max(severity,2)
    temp=board.copy();pv_san=[]
    for candidate in pv[:6]:
        pv_san.append(temp.san(candidate));temp.push(candidate)
    notes=move_notes(board,best)
    exposed=[]
    for square,piece in after.piece_map().items():
        if piece.color==mover and piece.piece_type not in (chess.PAWN,chess.KING) and after.is_attacked_by(not mover,square) and not after.is_attacked_by(mover,square):
            exposed.append(chess.square_name(square))
    if move==best:explanation='엔진의 첫 번째 후보와 같은 수예요. 이 장면은 잘 챙기셨어요!'
    elif severity==0:explanation='짧은 탐색에서는 최우선 후보와 차이가 크지 않아요. 다른 계획도 가능한 장면이에요.'
    else:explanation=f'{san}보다 {board.san(best)}를 먼저 살펴볼 장면이에요. '+notes['reasons'][0]
    if terminal and terminal.winner is None:
        explanation='이 수로 규칙상 무승부가 됐어요. 무승부를 만들려던 상황이었는지도 함께 살펴봐요.'
    return dict(ply=index+1,color='white' if mover else 'black',number=board.fullmove_number,
                move=move.uci(),san=san,fen=board.fen(),after=after.fen(),grade=grade,severity=severity,
                loss_cp=loss,before_cp=before_cp,after_cp=after_cp,
                before_mate=best_score.mate(),after_mate=played_score.mate(),
                best_move=best.uci(),best_san=board.san(best),pv=pv_san,
                comparison=compare_moves(board,move,best,played_pv,pv,grade,loss) if thorough else None,
                explanation=explanation,analysis=snapshot(board,best_info),best_reasons=notes['reasons'],best_capture=board.is_capture(best),
                best_check=board.gives_check(best),exposed=exposed,depth=best_info.get('depth'))


def review_batch(engine,game,start,count):
    board=chess.Board(game['start_fen'])
    for row in game['moves'][:start]:board.push_uci(row['move'])
    rows=[]
    for index in range(start,min(start+count,game['total'])):
        move=chess.Move.from_uci(game['moves'][index]['move'])
        rows.append(review_move(engine,board,move,index));board.push(move)
    next_index=start+len(rows)
    result=dict(game_id=game['id'],rows=rows,next=next_index,total=game['total'],done=next_index==game['total'])
    if result['done']:
        info=None if board.is_game_over() else engine.analyse(board,chess.engine.Limit(time=0.25,depth=12))
        result['final_analysis']=snapshot(board,info)
    return result


def position_state(board):
    result=board.outcome(claim_draw=False)
    turn='백' if board.turn else '흑'
    if board.is_checkmate():status='체크메이트! '+('흑' if board.turn else '백')+' 승리'
    elif result:status='게임 종료: 무승부'
    else:status=('체크! ' if board.is_check() else '')+turn+' 차례'
    return dict(fen=board.fen(),legal=[m.uci() for m in board.legal_moves],status=status,game_over=bool(result))


def snapshot(board,info):
    """Precompute both viewpoints so browsing and changing sides require no new engine calls."""
    result={};pv=info.get('pv',[]) if info else []
    for color,side in [(chess.WHITE,'white'),(chess.BLACK,'black')]:
        goals,material=priorities(board,color)
        opening=guide(board,color,{'start_fen':board.root().fen(),'moves':[m.uci() for m in board.move_stack]})
        opening['candidate']=None
        lines=[]
        if pv:
            tmp=board.copy();sans=[]
            for move in pv[:8]:sans.append(tmp.san(move));tmp.push(move)
            score=info['score']
            lines=[dict(move=pv[0].uci(),san=board.san(pv[0]),score_cp=score.white().score(mate_score=100000),mate=score.white().mate(),
                        player_score_cp=score.pov(color).score(mate_score=100000),player_mate=score.pov(color).mate(),
                        pv=sans,actual_depth=info.get('depth'),coach=coach_line(board,pv,color))]
        cp=lines[0]['player_score_cp'] if lines else 0
        result[side]=dict(**position_state(board),player_color=side,my_turn=board.turn==color,priorities=goals,material_text=material,
                          opening=opening,lines=lines,depth=info.get('depth') if info else None,
                          score_text='내가 유리' if cp>60 else '상대가 유리' if cp < -60 else '대체로 균형',
                          explanation='게임이 종료됐어요.' if not lines else lines[0]['coach']['intro'])
    return result
