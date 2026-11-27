import unittest,datetime as dt,json,tempfile
from pathlib import Path
from season_policy import resolve,SeasonNotReady
from season_runtime import collection_plan
from run_v3 import execute

CFG=json.loads((Path(__file__).resolve().parents[1]/'config_v3.json').read_text())
class IntegratedTests(unittest.TestCase):
 def test_january_postseason(self):
  self.assertEqual(resolve(dt.date(2027,1,2),CFG)[0],2026)
 def test_june_operating_year(self):
  self.assertEqual(collection_plan(dt.date(2027,6,30),CFG)['mode'],'offseason')
 def test_unverified_july_rollover(self):
  with self.assertRaises(SeasonNotReady):collection_plan(dt.date(2027,7,1),CFG)
 def test_2026_game_window(self):
  self.assertEqual(collection_plan(dt.date(2026,11,21),CFG)['weeks'],[11,12,13])
 def test_offseason_no_fetch(self):
  def fail(url):raise AssertionError('Unexpected API request')
  plan,data=execute(dt.date(2027,6,15),CFG,fetch=fail)
  self.assertIsNone(data)
 def test_no_production_write(self):
  self.assertFalse((Path(__file__).resolve().parents[1]/'build/v3-preview/nc-scores.json').exists())
if __name__=='__main__':unittest.main()
