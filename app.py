import os, shutil, threading
from flask import Flask, jsonify, request, render_template
import chess, chess.engine
from werkzeug.exceptions import BadRequest
from coaching import coach_line, priorities, move_notes
from openings import guide
from game_review import parse_game, review_batch

app = Flask(__name__)
ENGINE = os.getenv("STOCKFISH_PATH") or shutil.which("stockfish") or "/usr/games/stockfish"
lock = threading.Lock()

@app.errorhandler(BadRequest)
def invalid_json(exc):
    return jsonify(error="올바른 JSON 요청을 보내 주세요."), 400

def board_from(data):
    if not isinstance(data, dict):
        raise ValueError("JSON 객체로 요청해 주세요.")
    fen = data.get("fen")
    if fen is not None and not isinstance(fen, str):
        raise ValueError("FEN은 문자열이어야 합니다.")
    try:
        b = chess.Board(fen or chess.STARTING_FEN)
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
        uci=data.get("move", "")
        if not isinstance(uci, str): raise ValueError("수는 UCI 문자열이어야 합니다.")
        m=chess.Move.from_uci(uci)
        if m not in b.legal_moves: raise ValueError("합법적인 수가 아닙니다.")
        san=b.san(m);b.push(m)
        return jsonify(**state(b),san=san)
    except (ValueError,TypeError) as e: return jsonify(error=str(e)),400

@app.post("/api/analyze")
def analyze():
    try:
        data=request.get_json(force=True);b=board_from(data)
        side=data.get("player_color", "white")
        if side not in ("white", "black"): raise ValueError("내 편은 white 또는 black으로 선택해 주세요.")
        player=side == "white"
        goals, material=priorities(b, player)
        opening=guide(b,player,data)
        enabled=data.get("repertoire",True)
        if not isinstance(enabled,bool):raise ValueError("오프닝 안내 설정은 true 또는 false여야 합니다.")
        book_move=opening.pop("candidate") if enabled else None
        opening["candidate"]=None
        context=dict(player_color=side, my_turn=b.turn == player, priorities=goals, material_text=material,opening=opening)
        if b.is_game_over(): return jsonify(**state(b),**context,lines=[],explanation="게임이 종료되었습니다.")
        depth=max(6,min(20,int(data.get("depth",12))))
        with lock:
            with chess.engine.SimpleEngine.popen_uci(ENGINE,timeout=40) as engine:
                engine.configure({"Threads": 1, "Hash": 32})
                infos=engine.analyse(b,chess.engine.Limit(depth=depth,time=3),multipv=min(3,b.legal_moves.count()))
                if book_move and infos:
                    candidate=chess.Move.from_uci(book_move)
                    book_info=next((i for i in infos if i.get("pv") and i["pv"][0]==candidate),None)
                    if book_info is None:
                        book_info=engine.analyse(b,chess.engine.Limit(time=0.5),root_moves=[candidate])
                    best_score=infos[0]["score"].pov(b.turn).score(mate_score=100000)
                    candidate_score=book_info["score"].pov(b.turn).score(mate_score=100000)
                    gap=max(0,best_score-candidate_score)
                    opening["candidate"]=dict(move=book_move,san=b.san(candidate),allowed=gap<=80,
                        comparison=("짧은 엔진 비교에서 큰 차이가 없어요. 학습 후보로 살펴봐요." if gap<=80 else "엔진 평가 차이가 커서 정석을 고집하기보다 아래 엔진 추천을 우선 살펴봐요."))
        lines=[]
        for info in infos:
            pv=info.get("pv",[])
            if not pv: continue
            score=info["score"].white()
            tmp=b.copy();sans=[]
            for m in pv[:8]:
                sans.append(tmp.san(m));tmp.push(m)
            lines.append(dict(move=pv[0].uci(),san=b.san(pv[0]),score_cp=score.score(mate_score=100000),mate=score.mate(),pv=sans,player_score_cp=info["score"].pov(player).score(mate_score=100000),player_mate=info["score"].pov(player).mate(),actual_depth=info.get("depth"),coach=coach_line(b,pv,player),explanation=" ".join(move_notes(b,pv[0])["reasons"])))
        if not lines: return jsonify(error="엔진 분석 결과가 없습니다."),503
        cp=lines[0]["player_score_cp"]
        balance="내가 유리" if cp>60 else "상대가 유리" if cp< -60 else "대체로 균형"
        return jsonify(**state(b),**context,lines=lines,depth=depth,score_text=balance,explanation=lines[0]["coach"]["intro"])
    except (ValueError,TypeError) as e: return jsonify(error=str(e)),400
    except BadRequest:
        raise
    except Exception as e: return jsonify(error="Stockfish 실행에 실패했습니다: "+str(e)),503

@app.post("/api/pgn")
def import_pgn():
    try:
        data=request.get_json(force=True)
        if not isinstance(data,dict):raise ValueError("JSON 객체로 요청해 주세요.")
        return jsonify(parse_game(data.get('pgn')))
    except (ValueError,TypeError) as exc:return jsonify(error=str(exc)),400


@app.post("/api/review")
def game_review():
    try:
        data=request.get_json(force=True)
        if not isinstance(data,dict):raise ValueError("JSON 객체로 요청해 주세요.")
        game=parse_game(data.get('pgn'))
        start=data.get('start',0)
        if not isinstance(start,int) or isinstance(start,bool) or not 0<=start<game['total']:
            raise ValueError("리뷰 시작 위치가 올바르지 않아요.")
        with lock:
            with chess.engine.SimpleEngine.popen_uci(ENGINE,timeout=40) as engine:
                engine.configure({"Threads":1,"Hash":32})
                return jsonify(review_batch(engine,game,start,4))
    except (ValueError,TypeError) as exc:return jsonify(error=str(exc)),400
    except BadRequest:raise
    except Exception:return jsonify(error="게임 리뷰 중 엔진 응답을 받지 못했어요. 완료된 부분부터 다시 이어갈 수 있어요."),503


if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.getenv("PORT",5000)))
