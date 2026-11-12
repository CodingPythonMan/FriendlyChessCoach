"""Named positions (Lichess CC0 subset) and a small, explicit learning repertoire."""
import json
import re
from pathlib import Path
from functools import lru_cache
import chess


def key(board):
    return ' '.join(board.fen(en_passant='legal').split()[:4])


def play_sans(text):
    board=chess.Board(); positions=[]
    for san in text.split():
        if re.match(r'^\d+\.',san): continue
        move=board.parse_san(san);positions.append((board.copy(),move));board.push(move)
    return board,positions


@lru_cache(maxsize=1)
def names():
    result={}
    for row in json.loads(Path(__file__).with_name('data').joinpath('openings.json').read_text()):
        board,_=play_sans(row['pgn']);result[key(board)]=row
    return result


LINES={
    chess.WHITE:[
        'c4 e5 Nc3 Nf6 g3 d5 cxd5 Nxd5 Bg2',
        'c4 c5 Nc3 Nc6 g3 g6 Bg2 Bg7',
        'c4 Nf6 Nc3 g6 g3 Bg7 Bg2 O-O',
        'c4 e6 Nc3 d5 d4 Nf6 Nf3',
        'c4 c6 Nc3 d5 d4 Nf6',
        'c4 g6 Nc3 Bg7 g3 b6 Bg2 Bb7 e4 d6 Nge2 Nf6 O-O',
        'c4 b6 Nc3 Bb7 e4 e6 d4',
        'c4 g6 Nc3 Bg7 g3 d6 Bg2 Nf6 Nf3 O-O O-O',
    ],
    chess.BLACK:[
        'e4 c6 d4 d5 e5 Bf5',
        'e4 c6 d4 d5 exd5 cxd5 Bd3 Nc6',
        'e4 c6 d4 d5 Nc3 dxe4 Nxe4 Bf5',
        'e4 c6 d4 d5 Nd2 dxe4 Nxe4 Bf5',
        'e4 c6 Nc3 d5 Nf3 Bg4',
        'e4 c6 g3 d5 Bg2 dxe4 Bxe4 Nf6',
        'g3 d5 Bg2 e5 b3 Nc6 Bb2 Nf6',
        'b3 d5 Bb2 Nf6 g3 e5 Bg2 Nc6',
        'd4 d5 c4 e6 Nc3 Nf6',
        'd4 d5 Nf3 Nf6 Bf4 e6',
        'Nf3 d5 g3 Nf6 Bg2 e6',
    ]
}


@lru_cache(maxsize=2)
def repertoire(player):
    book={}
    for text in LINES[player]:
        _,positions=play_sans(text)
        for board,move in positions:
            if board.turn==player:book.setdefault(key(board),move.uci())
    return book


def guide(board,player,data):
    root=data.get('start_fen')
    moves=data.get('moves',[])
    if not isinstance(moves,list) or len(moves)>512 or any(not isinstance(m,str) for m in moves):
        raise ValueError('기보는 UCI 수의 목록으로 보내 주세요 (최대 512수).')
    if moves and root is None:raise ValueError('기보를 보내려면 시작 FEN도 필요해요.')
    positions=[board]
    if root is not None:
        if not isinstance(root,str):raise ValueError('시작 FEN은 문자열이어야 합니다.')
        tmp=chess.Board(root)
        if not tmp.is_valid():raise ValueError('시작 FEN이 올바르지 않아요.')
        positions=[tmp.copy()]
        for text in moves:
            move=chess.Move.from_uci(text)
            if move not in tmp.legal_moves:raise ValueError('기보에 합법적이지 않은 수가 있어요.')
            tmp.push(move);positions.append(tmp.copy())
        if tmp.fen()!=board.fen():raise ValueError('기보의 마지막 포지션과 현재 FEN이 달라요.')
    matched=next((b for b in reversed(positions) if key(b) in names()),None)
    record=names().get(key(matched)) if matched else None
    exact=bool(record and key(matched)==key(board))
    opening_name=(record['name'].replace('English Opening','잉글리시').replace('Caro-Kann Defense','카로칸 디펜스') if record else '등록된 이름을 아직 확인하지 못했어요')
    early=board.fullmove_number<=12 and not board.is_game_over()
    book_move=repertoire(player).get(key(board)) if early and board.turn==player and not board.is_check() else None
    if book_move and chess.Move.from_uci(book_move) not in board.legal_moves:book_move=None
    opponent=not player
    bishop_squares=(chess.B2,chess.G2) if opponent else (chess.B7,chess.G7)
    double=all(board.piece_at(s)==chess.Piece(chess.BISHOP,opponent) for s in bishop_squares)
    central_home=(chess.D2,chess.E2) if opponent else (chess.D7,chess.E7)
    untouched=all(board.piece_at(s)==chess.Piece(chess.PAWN,opponent) for s in central_home)
    if not early:
        plan=['정석 안내보다 현재 판의 전술과 기물 활동이 중요한 구간이에요. 아래 엔진 추천을 우선 살펴봐요.']
    elif double:
        plan=['상대 비숍 두 개가 긴 대각선에 자리 잡았어요. 더블 피앙케토 배치예요. 이름이 낯설어도 비상사태는 아니랍니다!',
              '중앙 폰을 지킬 기물부터 전개하고, 안전할 때 d4·e4(흑은 …d5·…e5)로 공간을 챙겨요. 비숍이 겨누는 대각선도 확인하세요.',
              '중앙 폰은 성벽이자 문이에요. 공간은 확보하되 무작정 더 밀거나, 준비 없이 중앙을 열어 상대 비숍의 고속도로를 만들어주지는 말아요.']
    elif player:
        plan=['내 기본 레퍼토리는 잉글리시(1.c4)예요. Nc3와 g3·Bg2로 전개하고, 상대 중앙에 맞춰 d4 또는 e4를 준비해요.',
              '상대가 …e5라면 d5 칸과 …d5 돌파, …c5라면 대칭 중앙의 d4 돌파를 살펴봐요. …d5가 나오면 교환하거나 d4로 다른 폰 구조에 합류할 수도 있어요.']
    else:
        plan=['1.e4에는 …c6와 …d5로 카로칸을 준비해요. e5 전진형은 …Bf5, exd5 교환형은 …cxd5, Nc3/Nd2 뒤 교환은 …dxe4와 …Bf5가 기본 분기예요.',
              '상대가 1.d4·1.g3·1.b3로 시작하면 카로칸 수순을 억지로 복사하지 않아요. …d5로 중앙을 잡고 기물을 전개하는 별도 배치를 준비해요.']
    if early and untouched:
        plan.append('상대 중앙 폰이 아직 출발 칸에 있어요. 새 오프닝으로 갈아타기보다 안전하게 중앙을 잡을 기회인지 먼저 살펴봐요. 단, 느린 수라고 해서 나쁜 수는 아니에요.')
    return dict(name=opening_name,eco=record['eco'] if record else None,exact=exact,
                label='현재 포지션의 오프닝' if exact else '마지막으로 확인된 오프닝',
                plan=plan,double_fianchetto=double,candidate=book_move,
                repertoire='잉글리시' if player else '카로칸 + 유연한 중앙 배치',
                note='이름은 수순이 바뀌어 같은 포지션이 되어도 인식해요. 수록 범위 밖에서는 마지막 확인 이름만 표시해요. FEN만 가져오면 과거 수순은 알 수 없어요.',
                source='https://github.com/lichess-org/chess-openings')
