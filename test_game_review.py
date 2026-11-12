import unittest
from unittest.mock import MagicMock
import chess,chess.engine
from game_review import parse_game,review_move,review_batch,classify,snapshot
from app import app

class GameReviewTests(unittest.TestCase):
 def test_import_comments_variations_and_positions(self):
  g=parse_game('[White "Me"]\n[Black "Them"]\n\n1. e4 {hello} c6 (1... e5) 2. d4 d5 *')
  self.assertEqual(g['total'],4);self.assertEqual(g['moves'][1]['san'],'c6')
  self.assertEqual(len(g['positions']),5);self.assertEqual(g['positions'][-1]['fen'],g['fen'])
  self.assertEqual(g['opening']['eco'][:1],'B');self.assertIn('Caro-Kann',g['opening']['name'])
 def test_bom_import_has_stable_id_for_resuming(self):
  g=parse_game('\ufeff  \n1. e4 e5 * ');self.assertEqual(parse_game(g['pgn'])['id'],g['id'])
 def test_invalid_and_multiple_games_rejected(self):
  for pgn in ['',None,[], 'hello', '1. e4 e5 2. e5', '1. f3 e5 2. g4 Qh4# 3. a3', '1. e4 *\n\n[Event "two"]\n\n1. d4 *', '[Variant "Atomic"]\n\n1. e4 *']:
   with self.subTest(pgn=pgn):
    self.assertEqual(app.test_client().post('/api/pgn',json={'pgn':pgn}).status_code,400)
 def test_custom_fen_black_to_move(self):
  pgn='[SetUp "1"]\n[FEN "7k/8/8/8/8/8/8/K7 b - - 0 23"]\n\n23... Kg8 *'
  # Insufficient material is already terminal and cannot have a further move.
  with self.assertRaises(ValueError):parse_game(pgn)
  pgn='[SetUp "1"]\n[FEN "7k/7p/8/8/8/8/8/K7 b - - 0 23"]\n\n23... Kg8 *'
  g=parse_game(pgn);self.assertEqual(g['moves'][0]['color'],'black');self.assertEqual(g['moves'][0]['number'],23)
 def test_root_move_comparison_black_perspective(self):
  b=chess.Board();b.push_san('e4');move=b.parse_san('f6');best=b.parse_san('e5')
  engine=MagicMock();engine.analyse.side_effect=[{'pv':[best],'score':chess.engine.PovScore(chess.engine.Cp(0),False),'depth':9}, {'pv':[move],'score':chess.engine.PovScore(chess.engine.Cp(-250),False)}]*2
  row=review_move(engine,b,move,1)
  self.assertEqual(row['grade'],'큰 실수');self.assertEqual(row['loss_cp'],250)
  self.assertEqual(row['analysis']['black']['lines'][0]['player_score_cp'],0)
  self.assertEqual(row['analysis']['white']['fen'],b.fen())
  self.assertEqual(engine.analyse.call_args.kwargs['root_moves'],[move])
 def test_delivered_mate_and_terminal_cached_position(self):
  g=parse_game('1. f3 e5 2. g4 Qh4# 0-1');b=chess.Board(g['moves'][-1]['fen']);m=b.parse_san('Qh4#')
  engine=MagicMock();engine.analyse.return_value={'pv':[m],'score':chess.engine.PovScore(chess.engine.Mate(1),False),'depth':8}
  result=review_batch(engine,g,3,4)
  self.assertTrue(result['done']);self.assertEqual(result['rows'][0]['grade'],'체크메이트!')
  self.assertEqual(engine.analyse.call_count,1)
  self.assertEqual(result['final_analysis']['white']['lines'],[])
  self.assertTrue(result['final_analysis']['black']['game_over'])
 def test_batch_bounds_and_classification_thresholds(self):
  c=app.test_client()
  for start in [-1,True,99,'0']:
   self.assertEqual(c.post('/api/review',json={'pgn':'1. e4 *','start':start}).status_code,400)
  self.assertEqual(classify(0,-49)[1],0);self.assertEqual(classify(0,-50)[1],1)
  self.assertEqual(classify(0,-100)[1],2);self.assertEqual(classify(0,-200)[1],3)

if __name__=='__main__':unittest.main()
