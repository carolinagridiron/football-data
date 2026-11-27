import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from v3_pipeline import pipeline
from season_policy import SeasonNotReady

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.config=self.root/'config.json'
        self.feed=self.root/'feed.json'
        self.arc=self.root/'archive'
        self.details=self.root/'details'
        self.config.write_text(json.dumps({'schema_version':2,'operating_year':{'start_month':7,'start_day':1},'seasons':{
            '2026':{'verified':True,'week_anchor_date':'2026-11-21','week_anchor_number':12,'max_week':22,'nc_school_slugs':['duke']},
            '2027':{'verified':False,'week_anchor_date':None,'week_anchor_number':None,'max_week':None,'nc_school_slugs':['duke']}}}))
        self.sample={'games':[{'game':{'gameID':'12345','startDate':'11/26/2026','gameState':'final',
          'away':{'names':{'short':'Duke','seo':'duke'},'score':'7'},'home':{'names':{'short':'Other','seo':'other'},'score':'3'}}}]}
    def call(self,day,write=False,engine=None):
        with patch('v3_pipeline.detail_execute') as details:
            if engine is None: details.return_value={'ok':True}
            else: details.side_effect=engine
            result=pipeline(dt.date.fromisoformat(day),self.config,self.feed,self.arc,self.details,write,
                fetch=lambda url:self.sample)
            return result,details
    def test_offseason_preserves_feed(self):
        self.feed.write_text('PRESERVE')
        result,details=self.call('2027-06-15',True)
        self.assertFalse(result['feed_published'])
        self.assertEqual(self.feed.read_text(),'PRESERVE')
        details.assert_not_called()
    def test_unverified_rollover_blocks_writes(self):
        self.feed.write_text('PRESERVE')
        with self.assertRaises(SeasonNotReady):self.call('2027-09-01',True)
        self.assertEqual(self.feed.read_text(),'PRESERVE')
    def test_january_is_2026(self):
        result,_=self.call('2027-01-02',False)
        self.assertEqual(result['plan']['season'],2026)
    def test_live_score_saved_even_if_detail_fails(self):
        result,_=self.call('2026-11-26',True,engine=RuntimeError('details unavailable'))
        self.assertTrue(result['feed_published'])
        self.assertFalse(result['details_published'])
        self.assertIn('details unavailable',result['detail_warning'])
        self.assertEqual(json.loads(self.feed.read_text())['season'],2026)
    def test_dry_run_writes_nothing(self):
        result,details=self.call('2026-11-26',False)
        self.assertFalse(self.feed.exists())
        details.assert_not_called()
    def test_verified_new_season_isolated(self):
        data=json.loads(self.config.read_text())
        data['seasons']['2027'].update(verified=True,week_anchor_date='2027-11-20',week_anchor_number=12,max_week=22)
        self.config.write_text(json.dumps(data))
        result,_=self.call('2027-11-25',False)
        self.assertEqual(result['plan']['season'],2027)

if __name__=='__main__':unittest.main()
