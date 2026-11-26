import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from publish_game_details import publish, compact

class TestPublisher(unittest.TestCase):
    def setUp(self):
        self.game={'id':'123','division':'d2','date':'11/21/2026','status':'final',
                   'away':{'name':'UNC Pembroke','ncaa_slug':'unc-pembroke'},
                   'home':{'name':'Central State','ncaa_slug':'central-st-oh'}}
        self.detail={'id':'123','period_scores':[{'period':'1','away':'7','home':'3'}],
                     'venue':{'stadium':'Stadium','city':'Pembroke','state':'NC'},
                     'ncaa_away':{'name':'UNC Pembroke'},'ncaa_home':{'name':'Central State'}}
        self.archive={'season':2026,'games':{'123':self.game},'details':{'123':self.detail}}
    def test_period_orientation(self):
        p=compact(self.game,self.detail)
        self.assertEqual(p['period_scores'][0]['away'],'7')
    def test_dry_run_no_files(self):
        with tempfile.TemporaryDirectory() as d:
            result=publish(self.archive,Path(d)/'2026',False)
            self.assertEqual(result['new_files'],1)
            self.assertFalse((Path(d)/'2026').exists())
    def test_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)
            publish(self.archive,target,True)
            r=publish(self.archive,target,True)
            self.assertEqual(r['unchanged_files'],1)
            self.assertEqual(r['changed_files_held'],0)
    def test_conflict_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)
            publish(self.archive,target,True)
            original=(target/'123.json').read_bytes()
            self.archive['details']['123']['venue']['stadium']='Other'
            r=publish(self.archive,target,True)
            self.assertEqual(r['changed_files_held'],1)
            self.assertEqual((target/'123.json').read_bytes(),original)

if __name__ == '__main__': unittest.main()
