import sys,unittest,datetime as dt,tempfile,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from incremental_details import run,publish_changed

class IncrementalTests(unittest.TestCase):
 def setUp(self):
  self.g={'id':'123','date':'11/26/2026','division':'fbs','status':'pre','away':{'name':'A','ncaa_slug':'a','score':None},'home':{'name':'B','ncaa_slug':'b','score':None}}
  self.feed={'season':2026,'games':[self.g]}
  self.archive={'season':2026,'games':{},'details':{},'detail_tracking':{}}
  self.detail={'contests':[{'id':'123','location':{'venue':'Test Field','city':'X','stateUsps':'NC'},'teams':[{'isHome':True,'seoname':'b'},{'isHome':False,'seoname':'a'}],'linescores':[{'period':'1','home':'7','visit':'0'}]}]}
 def test_new_game_details(self):
  result,report=run(self.feed,self.archive,dt.date(2026,11,26),fetch=lambda u:self.detail)
  self.assertEqual(report['new_games'],1);self.assertEqual(report['detail_requests'],1)
  self.assertEqual(result['details']['123']['venue']['stadium'],'Test Field')
 def test_final_score_conflict_preserved(self):
  old=dict(self.g,status='final',away={**self.g['away'],'score':10},home={**self.g['home'],'score':7})
  incoming=dict(old,away={**old['away'],'score':11})
  result,report=run({'season':2026,'games':[incoming]}, {'season':2026,'games':{'123':old},'details':{},'detail_tracking':{'123':{'status':'NO_DATA','attempts':2}}},dt.date(2026,11,26))
  self.assertEqual(result['games']['123']['away']['score'],10)
  self.assertEqual(report['conflicts'][0]['type'],'final_score_change')
 def test_outside_window_skipped(self):
  result,report=run(self.feed,self.archive,dt.date(2026,12,10))
  self.assertEqual(report['detail_requests'],0)
 def test_wrong_season_rejected(self):
  with self.assertRaises(ValueError):run({'season':2027,'games':[]},self.archive,dt.date(2027,1,1))
 def test_publisher_preflight_no_writes(self):
  archive={'season':2026,'games':{'123':self.g},'details':{'123':{'id':'123','venue':{'stadium':'X'},'period_scores':[]}}}
  with tempfile.TemporaryDirectory() as d:
   report=publish_changed(archive,Path(d),False)
   self.assertEqual(report['new_files'],1)
   self.assertFalse((Path(d)/'2026'/'123.json').exists())
if __name__=='__main__':unittest.main()
