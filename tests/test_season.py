import datetime as dt
import json
import pathlib
import sys
import unittest
from unittest.mock import patch
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from season_policy import football_season, resolve, SeasonNotReady
from collector_v30a import collect
CFG=json.loads((ROOT/'config_v3.json').read_text())
class SeasonTests(unittest.TestCase):
    def test_june_july(self):
        self.assertEqual(football_season(dt.date(2027,6,30)),2026)
        self.assertEqual(football_season(dt.date(2027,7,1)),2027)
    def test_january_postseason(self):
        self.assertEqual(resolve(dt.date(2027,1,9),CFG)[0],2026)
    def test_unverified_blocks(self):
        with self.assertRaises(SeasonNotReady):resolve(dt.date(2027,7,1),CFG)
    def test_offseason_preserves_feed(self):
        with self.assertRaises(SeasonNotReady):collect(CFG,dt.date(2027,6,30),fetch=lambda url:self.fail('should not fetch'))
    def test_2026_endpoint(self):
        urls=[]
        def fetch(url):
            urls.append(url)
            return {'games':[]}
        r=collect(CFG,dt.date(2026,11,26),fetch=fetch)
        self.assertEqual(r['season'],2026)
        self.assertEqual(len(urls),12)
        self.assertTrue(all('/2026/' in url for url in urls))
    def test_legacy_compatibility(self):
        legacy=json.loads((ROOT.parent/'config.json').read_text()) if (ROOT.parent/'config.json').exists() else {'week_anchor_date':'2026-11-21','week_anchor_number':12,'max_week':22,'nc_school_slugs':['duke']}
        self.assertEqual(resolve(dt.date(2027,1,3),legacy)[0],2026)
        with self.assertRaises(SeasonNotReady):resolve(dt.date(2027,8,1),legacy)
if __name__=='__main__':unittest.main()
