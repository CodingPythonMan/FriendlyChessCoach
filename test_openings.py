import unittest
from unittest.mock import patch,MagicMock
import chess,chess.engine
from openings import guide,play_sans,repertoire
from app import app

class OpeningTests(unittest.TestCase):
 def guide(self,text,player):
  board,positions=play_sans(text)
  return guide(board,player,{'start_fen':chess.STARTING_FEN,'moves':[m.uci() for b,m in positions]})
 def test_named_openings_and_branches(self):
  for line in ['e4 c6','e4 c6 d4 d5 e5','e4 c6 d4 d5 exd5 cxd5','e4 c6 d4 d5 Nc3']:
   self.assertIn('카로칸',self.guide(line,False)['name'])
  self.assertIn('잉글리시',self.guide('c4 e5 Nc3',True)['name'])
 def test_transposition_and_history(self):
  a=self.guide('c4 Nf6 Nc3 e5',True);b=self.guide('c4 e5 Nc3 Nf6',True)
  self.assertEqual(a['name'],b['name']);self.assertEqual(a['exact'],b['exact'])
  b,p=play_sans('c4 a6 h3')
  result=guide(b,True,{'start_fen':chess.STARTING_FEN,'moves':[m.uci() for _,m in p]})
  self.assertFalse(result['exact']);self.assertIn('잉글리시',result['name'])
  self.assertIsNone(guide(b,True,{})['eco'])
 def test_double_fianchetto_and_central_reply(self):
  result=self.guide('c4 g6 Nc3 Bg7 g3 b6 Bg2 Bb7',True)
  self.assertTrue(result['double_fianchetto']);self.assertEqual(result['candidate'],'e2e4')
  result=self.guide('g3 d5 Bg2 e5 b3 Nc6 Bb2',False)
  self.assertTrue(result['double_fianchetto']);self.assertEqual(result['candidate'],'g8f6')
 def test_every_book_move_legal_and_no_forced_caro_against_d4(self):
  for color in [True,False]:
   for fen,uci in repertoire(color).items():
    self.assertIn(chess.Move.from_uci(uci),chess.Board(fen+' 0 1').legal_moves)
  self.assertEqual(self.guide('d4',False)['candidate'],'d7d5')
 def test_mismatching_or_illegal_history_rejected(self):
  c=app.test_client()
  for moves in [['e2e5'],['e2e4']]:
   r=c.post('/api/analyze',json={'start_fen':chess.STARTING_FEN,'moves':moves})
   self.assertEqual(r.status_code,400)
 def test_book_candidate_is_separately_checked_and_unsafe_one_disabled(self):
  engine=MagicMock();engine.__enter__.return_value=engine
  best={'pv':[chess.Move.from_uci('e2e4')],'score':chess.engine.PovScore(chess.engine.Cp(20),True),'depth':8}
  candidate={'pv':[chess.Move.from_uci('c2c4')],'score':chess.engine.PovScore(chess.engine.Cp(-200),True)}
  engine.analyse.side_effect=[[best],candidate]
  with patch('app.chess.engine.SimpleEngine.popen_uci',return_value=engine):
   r=app.test_client().post('/api/analyze',json={})
  self.assertEqual(r.status_code,200);self.assertFalse(r.json['opening']['candidate']['allowed'])
  self.assertEqual(r.json['lines'][0]['move'],'e2e4')
  self.assertIn('root_moves',engine.analyse.call_args.kwargs)

if __name__=='__main__':unittest.main()
