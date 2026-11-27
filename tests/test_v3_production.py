import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from v3_score_stage import stage
from collector import normalize as legacy_normalize
from collector_v30a import normalize as v3_normalize

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / 'config_v3.json').read_text())

class ProductionCompatibility(unittest.TestCase):
    def test_normalization_matches_legacy(self):
        item = {'game': {'gameID': 123, 'startDate': '11/28/2026', 'startTime': '3:30 PM', 'startTimeEpoch': '1795897800', 'gameState': 'final', 'currentPeriod': '4', 'contestClock': '', 'finalMessage': '', 'network': '', 'away': {'names': {'short': 'Duke', 'seo': 'duke'}, 'score': '25'}, 'home': {'names': {'short': 'Wake Forest', 'seo': 'wake-forest'}, 'score': '36'}}}
        self.assertEqual(legacy_normalize(item, 'fbs'), v3_normalize(item, 'fbs'))

    def test_active_feed_schema_and_diagnostics(self):
        item = {'game': {'gameID': 123, 'startDate': '11/28/2026', 'startTime': '3:30 PM', 'startTimeEpoch': '1795897800', 'gameState': 'final', 'away': {'names': {'short': 'Duke', 'seo': 'duke'}, 'score': '25'}, 'home': {'names': {'short': 'Wake Forest', 'seo': 'wake-forest'}, 'score': '36'}}}
        def fetch(url): return {'games': [item] if '/fbs/' in url else []}
        with tempfile.TemporaryDirectory() as d:
            feed, diag = Path(d)/'feed.json', Path(d)/'diagnostics.json'
            result = stage(dt.date(2026,11,28), CONFIG, feed, diag, fetch=fetch, write=True)
            self.assertEqual(result['mode'], 'collect')
            doc = json.loads(feed.read_text())
            self.assertEqual(doc['schema_version'], 1)
            self.assertEqual(doc['season'], 2026)
            self.assertEqual(doc['game_count'], 1)
            self.assertTrue({'id','date','away','home','status','period','clock','division'} <= set(doc['games'][0]))
            self.assertEqual(json.loads(diag.read_text())['games_collected'], 1)

    def test_offseason_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            feed, diag = Path(d)/'feed.json', Path(d)/'diagnostics.json'
            feed.write_text('ORIGINAL'); diag.write_text('ORIGINAL')
            result = stage(dt.date(2027,6,15), CONFIG, feed, diag, write=True)
            self.assertEqual(result['mode'], 'skip')
            self.assertEqual(feed.read_text(), 'ORIGINAL')
            self.assertEqual(diag.read_text(), 'ORIGINAL')

    def test_unverified_2027_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            feed, diag = Path(d)/'feed.json', Path(d)/'diagnostics.json'
            feed.write_text('ORIGINAL'); diag.write_text('ORIGINAL')
            result = stage(dt.date(2027,8,15), CONFIG, feed, diag, write=True)
            self.assertEqual(result['mode'], 'skip')
            self.assertEqual(feed.read_text(), 'ORIGINAL')

    def test_partial_api_failure_preserves_files(self):
        def fetch(url): raise RuntimeError('API down')
        with tempfile.TemporaryDirectory() as d:
            feed, diag = Path(d)/'feed.json', Path(d)/'diagnostics.json'
            feed.write_text('ORIGINAL'); diag.write_text('ORIGINAL')
            with self.assertRaises(RuntimeError):
                stage(dt.date(2026,11,28), CONFIG, feed, diag, fetch=fetch, write=True)
            self.assertEqual(feed.read_text(), 'ORIGINAL')
            self.assertEqual(diag.read_text(), 'ORIGINAL')

if __name__ == '__main__': unittest.main()
