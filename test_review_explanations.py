import unittest
import chess
from review_explanations import blocking_fact,pawn_fork_plan,compare_moves,line_data
from app import app

class ExplanationTests(unittest.TestCase):
 def position(self):
  b=chess.Board()
  for san in 'c4 e5 g3 d5 cxd5 Qxd5 Nf3 Bg4 Nc3 Qc6 Bg2 Bxf3 Bxf3 Qb6 O-O Bb4 Nd5 Qd6 Qa4+ c6 Nxb4 Ne7 Qb3 O-O'.split():b.push_san(san)
  return b
 def test_robo_knight_comparison_has_concrete_not_forced_facts(self):
  b=self.position();nd3=b.parse_san('Nd3');nc2=b.parse_san('Nc2')
  self.assertIn('d2',blocking_fact(b,nd3));self.assertIsNone(blocking_fact(b,nc2))
  fork=pawn_fork_plan(b,nd3)
  self.assertIn('b3 퀸',fork);self.assertIn('d3 나이트',fork);self.assertIn('확정됐다는 뜻은 아니',fork)
  self.assertIsNone(pawn_fork_plan(b,nc2))
  actual=[nd3];tmp=b.copy();tmp.push(nd3);actual.append(tmp.parse_san('c5'));tmp.push(actual[-1]);actual.append(tmp.parse_san('Ne1'))
  other=[nc2];tmp=b.copy();tmp.push(nc2);other.append(tmp.parse_san('c5'))
  result=compare_moves(b,nd3,nc2,actual,other,'무난한 수',29)
  self.assertIn('단정하지',result['verdict']);self.assertEqual(result['played'][1]['text'],'13... c5')
  self.assertEqual(b.fullmove_number,13);self.assertEqual(b.peek().uci(),'e8g8')
 def test_line_data_stops_at_illegal_move(self):
  b=chess.Board();self.assertEqual(len(line_data(b,[b.parse_san('e4'),chess.Move.from_uci('e2e3')])),1)
 def test_detail_endpoint_rejects_bad_indices_before_engine(self):
  for index in [True,-1,1,'0',None]:
   self.assertEqual(app.test_client().post('/api/review/detail',json={'pgn':'1. e4 *','index':index}).status_code,400)

if __name__=='__main__':unittest.main()
