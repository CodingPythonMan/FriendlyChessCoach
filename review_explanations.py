"""Move comparisons backed by legal engine lines and explicit board facts."""
import chess
from coaching import NAMES, VALUES, move_notes

def line_data(board,pv):
    current=board.copy();steps=[]
    for move in pv[:10]:
        if move not in current.legal_moves:break
        san=current.san(move);piece=current.piece_at(move.from_square)
        captured=chess.PAWN if current.is_en_passant(move) else current.piece_type_at(move.to_square) if current.is_capture(move) else None
        steps.append(dict(move=move.uci(),san=san,number=current.fullmove_number,color='white' if current.turn else 'black',
                          text=f'{current.fullmove_number}{"." if current.turn else "..."} {san}',
                          reason=move_notes(current,move)['reasons'][0],capture=NAMES.get(captured),check=current.gives_check(move)))
        current.push(move)
    return steps

def blocking_fact(board,move):
    piece=board.piece_at(move.from_square)
    if piece.piece_type==chess.PAWN:return None
    after=board.copy();after.push(move)
    behind=move.to_square+(-8 if piece.color else 8)
    if 0<=behind<64:
        pawn=after.piece_at(behind)
        if pawn and pawn.color==piece.color and pawn.piece_type==chess.PAWN:
            return f'{chess.square_name(move.to_square)}의 {NAMES[piece.piece_type]}가 내 {chess.square_name(behind)} 폰의 전진 칸을 막아요. 이 기물이 비키기 전에는 그 폰을 한 칸 전진시킬 수 없어요.'

def pawn_fork_plan(board,move):
    """A geometric plan, explicitly conditional, never a forced material win."""
    after=board.copy();after.push(move);enemy=after.turn;plans=[]
    for square in after.pieces(chess.PAWN,enemy):
        current=after.copy();current.turn=enemy;path=[]
        for _ in range(2):
            dest=square+(8 if enemy else -8)
            if not 0<=dest<64:break
            push=chess.Move(square,dest)
            if push not in current.legal_moves or current.is_capture(push):break
            path.append(current.san(push));current.push(push)
            targets=[s for s in current.attacks(dest) if current.piece_at(s) and current.color_at(s)!=enemy and current.piece_type_at(s) not in (chess.PAWN,chess.KING)]
            if len(targets)>=2:
                names='·'.join(f'{chess.square_name(s)} {NAMES[current.piece_type_at(s)]}' for s in sorted(targets))
                side='백' if enemy else '흑'
                plans.append((sum(VALUES[current.piece_type_at(s)] for s in targets),f'{side}이 기회를 얻어 {" → ".join(path)}로 폰을 밀면 {names}에 동시에 공격이 걸리는 모양이 생겨요. 강제 수순이나 기물 손실이 확정됐다는 뜻은 아니며, 그 전에 피하거나 막을 수 있어요.'))
            square=dest;current.turn=enemy
    return max(plans,key=lambda item:item[0])[1] if plans else None

def compare_moves(board,move,best,played_pv,best_pv,grade,loss):
    actual=line_data(board,played_pv);alternative=line_data(board,best_pv)
    actual_san=board.san(move);best_san=board.san(best);facts=[]
    blocked=blocking_fact(board,move);alt_blocked=blocking_fact(board,best)
    if blocked and blocked!=alt_blocked:
        facts.append(blocked)
        if not alt_blocked:facts.append(f'{best_san}는 그 전진 칸을 비워 두므로 폰 전진을 선택지로 남겨요. 폰을 실제로 밀어도 안전한지는 아래 수순과 함께 확인해요.')
    fork=pawn_fork_plan(board,move);alt_fork=pawn_fork_plan(board,best)
    if fork and fork!=alt_fork:
        facts.append(fork)
        if not alt_fork:facts.append(f'{best_san} 뒤에는 같은 두 기물이 그 폰에게 동시에 공격받는 배치가 되지 않아요.')
    if len(actual)>1:
        facts.append(f'실제 수 뒤 엔진이 고른 상대 응수는 {actual[1]["text"]}예요. {actual[1]["reason"]}')
    if len(actual)>2:
        facts.append(f'그 응수에 대한 내 후속 후보는 {actual[2]["text"]}예요. {actual[2]["reason"]}')
    for title,steps in [('실제 수 수순',actual),('대안 수순',alternative)]:
        captures=[f'{x["text"]}에서 {x["capture"]} 잡기' for x in steps if x['capture']]
        if captures:facts.append(f'{title}에서 확인할 교환: '+', '.join(captures[:4])+'. 한 번 잡는 장면만 보고 이득으로 판단하지 말고 되잡기까지 비교해요.')
    if not blocked and not fork:
        facts.extend(move_notes(board,best)['reasons'][:2])
    if move==best:
        verdict=f'더 살펴보니 {actual_san}가 이번 탐색의 첫 후보예요. 이전의 짧은 탐색 판정과 다를 수 있어요.'
    elif loss<100:
        verdict=f'{best_san}를 더 높게 평가하지만, 이번 비교에서 {actual_san}와 차이는 약 {loss/100:.2f}폰이에요. 반드시 {best_san}만 둬야 하는 장면으로 단정하지 않아요.'
    else:
        verdict=f'{actual_san}보다 {best_san}의 평가가 약 {loss/100:.2f}폰 높아요. 두 수 뒤 상대의 최선 응수까지 비교한 추정 차이예요.' if loss<9000 else f'{actual_san}와 {best_san} 사이에 메이트 수순 차이가 관찰됐어요. 아래 수순을 확인해 주세요.'
    return dict(version=1,verdict=verdict,facts=facts,played=actual,alternative=alternative,
                lesson='한 수를 고를 때는 도착 칸의 장점뿐 아니라, 막히는 내 폰과 상대의 폰 전진·동시 공격도 함께 확인해 봐요.',
                caveat='엔진 수순은 양쪽이 이 후보들을 골랐을 때의 예시예요. 각 설명은 실제 배치에서 확인한 사실이며, 평가 차이 전체의 원인을 증명하는 것은 아니에요. 짧은 탐색 결과는 깊이에 따라 달라질 수 있어요.')
