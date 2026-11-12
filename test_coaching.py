import unittest
from unittest.mock import patch, MagicMock
import chess
import chess.engine
from app import app
from coaching import coach_line, move_notes


def pv_from(board, sans):
    tmp=board.copy(); result=[]
    for san in sans:
        move=tmp.parse_san(san);result.append(move);tmp.push(move)
    return result


class CoachTests(unittest.TestCase):
    def test_black_waiting_for_white_gets_conditional_black_reply(self):
        b=chess.Board();pv=pv_from(b,['e4','c5','Nf3','d6','d4','cxd4'])
        c=coach_line(b,pv,chess.BLACK)
        self.assertEqual([s['actor'] for s in c['steps']],['상대','나','상대','나','상대','나'])
        self.assertIn('상대가 e4',c['headline']);self.assertIn('나는 c5',c['headline'])
        self.assertIn('c7 → c5',c['intro'])
        self.assertTrue(any('Nf3' in text and 'd6' in text for text in c['continuation']))
        for step in c['steps']:
            self.assertIn(chess.Move.from_uci(step['move']),chess.Board(step['fen']).legal_moves)

    def test_white_development_uses_actual_squares(self):
        b=chess.Board();pv=pv_from(b,['Nf3','d5','d4','Nf6'])
        c=coach_line(b,pv,chess.WHITE)
        self.assertIn('g1 → f3',c['headline']);self.assertIn('출근',c['analogy'])
        self.assertTrue(any('d4' in text and 'e5' in text for text in c['reasons']))

    def test_opponent_mate_does_not_invent_my_reply(self):
        b=chess.Board();pv=pv_from(b,['f3','e5','g4'])
        for m in pv:b.push(m)
        c=coach_line(b,pv_from(b,['Qh4#']),chess.WHITE)
        self.assertIn('게임이 끝',c['headline']);self.assertEqual(len(c['steps']),1)
        self.assertEqual(c['continuation'],[])

    def test_special_moves_have_grounded_explanations(self):
        b=chess.Board('r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1')
        self.assertIn('캐슬링',' '.join(move_notes(b,b.parse_san('O-O'))['reasons']))
        b=chess.Board('7k/P7/8/8/8/8/8/7K w - - 0 1')
        self.assertIn('나이트',' '.join(move_notes(b,b.parse_san('a8=N'))['reasons']))
        b=chess.Board()
        for san in ['e4','a6','e5','d5']:b.push_san(san)
        self.assertIn('앙파상',' '.join(move_notes(b,b.parse_san('exd6'))['reasons']))

    def test_api_side_perspective_and_engine_results(self):
        b=chess.Board();pv=pv_from(b,['e4','c5','Nf3','d6'])
        info={'pv':pv,'score':chess.engine.PovScore(chess.engine.Cp(120),chess.WHITE),'depth':9}
        engine=MagicMock();engine.__enter__.return_value=engine;engine.analyse.return_value=[info]
        with patch('app.chess.engine.SimpleEngine.popen_uci',return_value=engine):
            white=app.test_client().post('/api/analyze',json={'player_color':'white'}).get_json()
            black=app.test_client().post('/api/analyze',json={'player_color':'black'}).get_json()
        self.assertTrue(white['my_turn']);self.assertFalse(black['my_turn'])
        self.assertEqual(white['score_text'],'내가 유리');self.assertEqual(black['score_text'],'상대가 유리')
        self.assertEqual(black['lines'][0]['player_score_cp'],-120)
        self.assertEqual(black['lines'][0]['score_cp'],120)
        self.assertEqual(black['lines'][0]['actual_depth'],9)
        self.assertIn('나는 c5',black['lines'][0]['coach']['headline'])

    def test_invalid_input_and_terminal_positions(self):
        c=app.test_client()
        for side in ['blue',None,3]:
            self.assertEqual(c.post('/api/analyze',json={'player_color':side}).status_code,400)
        for route in ['position','move','analyze']:
            for body in ['null','[]','{']:
                r=c.post('/api/'+route,data=body,content_type='application/json')
                self.assertEqual(r.status_code,400);self.assertTrue(r.is_json)
        r=c.post('/api/analyze',json={'fen':'7k/6Q1/6K1/8/8/8/8/8 b - - 0 1','player_color':'black'})
        self.assertTrue(r.json['game_over']);self.assertEqual(r.json['lines'],[])
        self.assertTrue(r.json['my_turn'])


if __name__ == '__main__': unittest.main()
