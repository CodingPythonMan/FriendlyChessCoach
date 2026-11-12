import os, shutil, threading
from flask import Flask, jsonify, request, render_template
import chess, chess.engine

app = Flask(__name__)
ENGINE = os.getenv("STOCKFISH_PATH") or shutil.which("stockfish") or "/usr/games/stockfish"
lock = threading.Lock()

def board_from(data):
    try:
        b = chess.Board(data.get("fen") or chess.STARTING_FEN)
    except (ValueError, TypeError) as exc:
        raise ValueError("FEN 형식 오류: " + str(exc))
    if not b.is_valid():
        raise ValueError("체스 규칙상 성립하지 않는 FEN입니다.")
    return b

def state(b):
    result = b.outcome(claim_draw=False)
    if b.is_checkmate(): status = "체크메이트! " + ("흑" if b.turn else "백") + " 승리"
    elif result: status = "게임 종료: 무승부"
    elif b.is_check(): status = "체크! " + ("백" if b.turn else "흑") + " 차례"
    else: status = ("백" if b.turn else "흑") + " 차례"
    return dict(fen=b.fen(),legal=[m.uci() for m in b.legal_moves],status=status,game_over=bool(result))

def explain(b,m):
    p=b.piece_at(m.from_square)
    reasons=[]
    if b.is_castling(m): reasons.append("캐슬링으로 왕을 안전하게 옮깁니다.")
    if b.is_capture(m): reasons.append("상대 기물을 잡습니다.")
    if m.promotion: reasons.append("폰을 승격합니다.")
    if p and p.piece_type in (chess.BISHOP,chess.KNIGHT) and chess.square_rank(m.from_square) in (0,7): reasons.append("기물을 전개해 활동성을 높입니다.")
    if chess.square_file(m.to_square) in (3,4) and chess.square_rank(m.to_square) in (3,4): reasons.append("중앙을 차지하거나 압박합니다.")
    copy=b.copy();copy.push(m)
    if copy.is_checkmate(): reasons.insert(0,"이 수로 체크메이트입니다!")
    elif copy.is_check(): reasons.append("상대 왕에게 체크를 겁니다.")
    return " ".join(reasons) or "엔진이 좋은 후속 수순을 찾았습니다. 아래 예상 수순을 살펴보세요."

@app.get("/")
def home(): return render_template("index.html")

@app.post("/api/position")
def position():
    try: return jsonify(state(board_from(request.get_json(force=True))))
    except (ValueError,TypeError) as e: return jsonify(error=str(e)),400

@app.post("/api/move")
def move():
    try:
        data=request.get_json(force=True);b=board_from(data)
        m=chess.Move.from_uci(data.get("move",""))
        if m not in b.legal_moves: raise ValueError("합법적인 수가 아닙니다.")
        san=b.san(m);b.push(m)
        return jsonify(**state(b),san=san)
    except (ValueError,TypeError) as e: return jsonify(error=str(e)),400

@app.post("/api/analyze")
def analyze():
    try:
        data=request.get_json(force=True);b=board_from(data)
        if b.is_game_over(): return jsonify(**state(b),lines=[],explanation="게임이 종료되었습니다.")
        depth=max(6,min(20,int(data.get("depth",12))))
        with lock:
            with chess.engine.SimpleEngine.popen_uci(ENGINE,timeout=40) as engine:
                infos=engine.analyse(b,chess.engine.Limit(depth=depth,time=3),multipv=min(3,b.legal_moves.count()))
        lines=[]
        for info in infos:
            pv=info.get("pv",[])
            if not pv: continue
            score=info["score"].white()
            tmp=b.copy();sans=[]
            for m in pv[:8]:
                sans.append(tmp.san(m));tmp.push(m)
            lines.append(dict(move=pv[0].uci(),san=b.san(pv[0]),score_cp=score.score(mate_score=100000),mate=score.mate(),pv=sans,explanation=explain(b,pv[0])))
        if not lines: return jsonify(error="엔진 분석 결과가 없습니다."),503
        cp=lines[0]["score_cp"]
        balance="백 우세" if cp>60 else "흑 우세" if cp< -60 else "대체로 균형"
        return jsonify(**state(b),lines=lines,depth=depth,score_text=balance,explanation="추천: "+lines[0]["san"]+". "+lines[0]["explanation"])
    except (ValueError,TypeError) as e: return jsonify(error=str(e)),400
    except Exception as e: return jsonify(error="Stockfish 실행에 실패했습니다: "+str(e)),503

if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.getenv("PORT",5000)))
