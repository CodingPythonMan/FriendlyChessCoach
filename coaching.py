"""Position-grounded Korean coaching, with conditional plans from legal engine PVs."""
import chess

NAMES = {chess.PAWN: '폰', chess.KNIGHT: '나이트', chess.BISHOP: '비숍',
         chess.ROOK: '룩', chess.QUEEN: '퀸', chess.KING: '왕'}
VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
CENTER = {chess.D4, chess.E4, chess.D5, chess.E5}


def label(color, player):
    return '나' if color == player else '상대'


def move_notes(board, move):
    """Describe observable effects, never invent the engine's tactical intent."""
    piece = board.piece_at(move.from_square)
    name = NAMES[piece.piece_type]
    src, dst = map(chess.square_name, (move.from_square, move.to_square))
    after = board.copy()
    after.push(move)
    reasons = []
    motif = 'activity'
    if after.is_checkmate():
        reasons.append('이 수를 두면 상대 왕이 체크를 피할 곳이 없어요. 체크메이트예요!')
        motif = 'mate'
    elif board.is_check():
        reasons.append('현재 수를 두는 쪽의 왕이 체크를 받고 있어요. 이 수로 우선 급한 불부터 끌 수 있어요.')
        motif = 'defense'
    if board.is_castling(move):
        reasons.append('왕을 가장자리로 옮기고 룩을 중앙 쪽으로 꺼내는 캐슬링이에요.')
        motif = 'castle'
    if board.is_capture(move):
        captured = chess.PAWN if board.is_en_passant(move) else board.piece_type_at(move.to_square)
        reasons.append(f'{dst}의 상대 {NAMES[captured]}을 잡아요.' if not board.is_en_passant(move)
                       else '앙파상으로 방금 두 칸 전진한 상대 폰을 잡아요.')
        if motif == 'activity': motif = 'capture'
    if move.promotion:
        reasons.append(f'끝줄에 도착한 폰을 {NAMES[move.promotion]}으로 승격해요.')
        if motif != 'mate': motif = 'promotion'
    home = 0 if piece.color else 7
    if piece.piece_type in (chess.KNIGHT, chess.BISHOP) and chess.square_rank(move.from_square) == home:
        reasons.append(f'{src}에서 대기하던 {name}를 {dst}로 전개해요. 아직 움직이지 않은 기물도 경기에 참여시키는 수예요.')
        if motif == 'activity': motif = 'develop'
    attacks = set(after.attacks(move.to_square))
    central = sorted(attacks & CENTER)
    if central:
        squares = '·'.join(chess.square_name(s) for s in central)
        reasons.append(f'이동한 {name}가 중앙 {squares} 칸을 공격해요. 상대가 그 칸을 편하게 쓰기 어려워져요.')
        if motif == 'activity': motif = 'center'
    elif move.to_square in CENTER:
        reasons.append(f'{dst} 중앙 칸에 기물을 놓아 공간을 챙겨요.')
        if motif == 'activity': motif = 'center'
    if after.is_check() and not after.is_checkmate():
        reasons.append('상대 왕에게 체크를 걸어요. 상대는 다른 일보다 체크를 해소하는 게 먼저예요.')
        if motif == 'activity': motif = 'check'
    targets = [s for s in attacks if after.piece_at(s) and after.piece_at(s).color != piece.color
               and after.piece_type_at(s) != chess.KING]
    targets.sort(key=lambda s: VALUES.get(after.piece_type_at(s), 0), reverse=True)
    if targets:
        text = ', '.join(f'{chess.square_name(s)} {NAMES[after.piece_type_at(s)]}' for s in targets[:2])
        reasons.append(f'이동한 {name}가 상대 {text}을 공격해요. 다만 상대도 피하거나 지킬 수 있으니 “공짜 기물 발견!”은 아직 이르답니다.')
    if not reasons:
        reasons.append(f'{name}를 {src}에서 {dst}로 옮겨요. 이 수의 장점은 뒤에 이어지는 예상 수순과 함께 살펴봐요.')
    analogy = {
        'mate': '상대 왕의 마지막 비상구까지 닫혔어요. 오늘의 명탐정은 바로 이 기물이네요!',
        'defense': '집에 경보가 울리면 인테리어보다 불부터 꺼야겠죠? 왕의 안전을 먼저 챙겨요.',
        'castle': '왕은 안전한 숙소로, 룩은 일터로! 두 기물이 한 번에 제자리를 찾아가는 이사예요.',
        'capture': '기물을 챙기는 장면이에요. 다만 상대도 되잡을 수 있으니, 체스판 계산서는 끝까지 확인해 봐요.',
        'promotion': '폰이 긴 여정을 마치고 승진했어요. 이제 새 명함을 꺼낼 차례네요!',
        'develop': '벤치에 있던 기물도 출근할 시간이에요. 혼자 뛰던 동료에게 든든한 지원군을 보내는 셈이죠.',
        'center': '중앙은 체스판의 환승역 같아요. 길목을 챙겨두면 다음 목적지로 갈 선택지가 늘어나죠.',
        'check': '상대 왕에게 “잠깐, 이것부터 답해주세요!” 하고 질문을 던지는 수예요.',
        'activity': '기물의 자리를 바꿔 다음 일을 준비해요. 다음 장면은 아래 수순에서 같이 확인해 봐요.',
    }[motif]
    return dict(instruction=f'{name} {src} → {dst}', reasons=reasons, analogy=analogy)


def priorities(board, player):
    """Separate general position observations from engine-backed continuations."""
    items = []
    if board.turn == player and board.is_check():
        items.append('왕이 체크 상태예요. 멋진 장기 계획도 좋지만, 우선 왕부터 구해주세요!')
    home = 0 if player else 7
    undeveloped = [s for s, p in board.piece_map().items() if p.color == player
                   and p.piece_type in (chess.KNIGHT, chess.BISHOP) and chess.square_rank(s) == home]
    if undeveloped:
        text = ', '.join(f'{chess.square_name(s)} {NAMES[board.piece_type_at(s)]}' for s in sorted(undeveloped))
        items.append(f'홈 줄에 남은 기물: {text}. 전술적으로 안전하다면 이 기물들도 슬슬 출근시킬 후보로 생각해 봐요.')
    if board.has_kingside_castling_rights(player) or board.has_queenside_castling_rights(player):
        items.append('캐슬링 권리가 남아 있어요. 왕의 이삿날도 생각해 봐요. 다만 길과 체크 여부에 따라 지금 당장은 못 할 수도 있어요.')
    if not items:
        items.append('양쪽의 체크·잡기·공격받는 기물을 차례로 살펴봐요. 숨은 분실물(?)이 없는지 확인하는 시간이에요.')
    material = sum(VALUES.get(p.piece_type, 0) * (1 if p.color == player else -1)
                   for p in board.piece_map().values())
    text = '기물 점수는 같아요.' if material == 0 else f'기물 점수로는 {"내가" if material > 0 else "상대가"} {abs(material)}점 많아요.'
    return items[:3], text + ' (폰 1·나이트/비숍 3·룩 5·퀸 9, 위치 평가는 별도)'


def coach_line(board, pv, player):
    steps = []
    current = board.copy()
    for move in pv[:6]:
        if move not in current.legal_moves:
            break
        notes = move_notes(current, move)
        steps.append(dict(actor=label(current.turn, player), color='white' if current.turn else 'black',
                          move=move.uci(), san=current.san(move), fen=current.fen(),
                          instruction=notes['instruction'], reason=notes['reasons'][0]))
        current.push(move)
    mine = board.turn == player
    focus_index = 0 if mine else 1
    if len(steps) > focus_index:
        focus_board = chess.Board(steps[focus_index]['fen'])
        focus_move = chess.Move.from_uci(steps[focus_index]['move'])
        notes = move_notes(focus_board, focus_move)
        if mine:
            headline = f"지금은 {steps[0]['instruction']}"
            intro = f"내 차례네요! 엔진과 함께 고른 첫 번째 후보는 {steps[0]['san']}입니다."
        else:
            headline = f"상대가 {steps[0]['san']}를 두면, 나는 {steps[1]['san']}"
            intro = f"지금은 상대 차례예요. 우리도 다음 장면을 준비해 볼까요? {steps[0]['instruction']}를 예상하고, 그때 {steps[1]['instruction']}로 대응하는 수순이에요. 상대가 다르게 두면 새로 작전 회의를 열어봐요."
    else:
        notes = dict(reasons=['이 예상 수순에서는 상대의 수로 게임이 끝나서 내 응수는 없어요.'], analogy='다음 작전보다 게임이 끝나는지부터 살펴볼 장면이에요.')
        headline = '상대의 수로 게임이 끝나는 수순이에요'
        intro = '지금 수를 둘 쪽의 예상 수순을 보여드릴게요. 내 차례로 바꾸어 계산하면 다른 판이 되니까요.'
    continuation = []
    for index, step in enumerate(steps):
        if index > focus_index and step['actor'] == '나':
            previous = steps[index - 1]
            continuation.append(f"상대가 {previous['san']} ({previous['instruction']})로 답하면, {step['san']} ({step['instruction']})로 이어가 봐요. {step['reason']}")
    return dict(headline=headline, intro=intro, reasons=notes['reasons'], analogy=notes['analogy'],
                continuation=continuation[:2], steps=steps,
                watch=(f"상대의 예상 응수는 {steps[1]['san']} ({steps[1]['instruction']})이에요. {steps[1]['reason']}"
                       if mine and len(steps) > 1 else
                       '상대의 실제 수를 먼저 입력해 주세요. 그다음 우리 기물들이 어디로 가면 좋을지 다시 살펴봐요.'),
                conditional='양쪽이 이 수들을 골랐을 때의 예시예요. 상대에게 대본을 건넬 순 없으니, 실제 수가 다르면 계획도 새로 짜봐요.')
