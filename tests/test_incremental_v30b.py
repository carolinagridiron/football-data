import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from incremental_v30b import execute
from season_policy import SeasonNotReady

class SeasonAwareTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.config={'schema_version':2,'operating_year':{'start_month':7,'start_day':1},'seasons':{
            '2026':{'verified':True,'week_anchor_date':'2026-11-21','week_anchor_number':12,
                    'max_week':22,'nc_school_slugs':['duke']},
            '2027':{'verified':False,'week_anchor_date':None,'week_anchor_number':None,
                    'max_week':None,'nc_school_slugs':['duke']}}}
        (self.root/'config.json').write_text(json.dumps(self.config))
        self.engine=Mock(side_effect=lambda feed,archive,day,**kw:(archive,{'conflicts':[],'detail_errors':[]}))
        self.publisher=Mock(return_value={'held':[],'new_files':0})
    def invoke(self, date, feedseason, write=False):
        (self.root/'feed.json').write_text(json.dumps({'season':feedseason,'games':[]}))
        return execute(self.root/'feed.json',self.root/'config.json',self.root/'archive',
                       self.root/'details',dt.date.fromisoformat(date),write,
                       engine=self.engine,publisher=self.publisher)
    def test_january_2027_is_2026(self):
        self.invoke('2027-01-12',2026)
        self.assertEqual(self.engine.call_args.args[1]['season'],2026)
    def test_june_30_still_2026(self):
        self.invoke('2027-06-30',2026)
    def test_july_1_unverified_blocks(self):
        with self.assertRaises(SeasonNotReady): self.invoke('2027-07-01',2027,True)
        self.assertFalse((self.root/'archive').exists())
    def test_mismatched_feed_blocks(self):
        with self.assertRaises(SeasonNotReady): self.invoke('2026-11-26',2027,True)
    def test_read_only_does_not_write(self):
        self.invoke('2026-11-26',2026)
        self.assertFalse((self.root/'archive').exists())
        self.publisher.assert_called_once()
    def test_verified_2027_creates_separate_archive(self):
        self.config['seasons']['2027'].update(verified=True,week_anchor_date='2027-11-20',week_anchor_number=12,max_week=22)
        (self.root/'config.json').write_text(json.dumps(self.config))
        self.invoke('2027-09-01',2027,True)
        self.assertTrue((self.root/'archive/2027/archive.json').exists())
        self.assertFalse((self.root/'archive/2026').exists())
    def test_conflict_blocks_all_writes(self):
        self.engine=Mock(side_effect=lambda feed,archive,day,**kw:(archive,{'conflicts':[{'id':'1'}],'detail_errors':[]}))
        with self.assertRaises(RuntimeError): self.invoke('2026-11-26',2026,True)
        self.assertFalse((self.root/'archive').exists())

if __name__=='__main__':unittest.main()
