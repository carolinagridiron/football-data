import csv
import unittest
from pathlib import Path
from audit import compare, read_exceptions, slug
ROOT=Path(__file__).resolve().parents[1]

def game(gid, date, away, home, a, h, status='final'):
    return {'id':gid,'division':'d2','date':date,'away':{'name':away,'ncaa_slug':away,'score':a},'home':{'name':home,'ncaa_slug':home,'score':h},'status':status}

def row(date,away,home,a,h,status='Final'):
    return {'date':date,'division':'Division II','visitor':away,'home':home,'visitor_score':str(a) if a is not None else '', 'home_score':str(h) if h is not None else '', 'status':status}

class Stabilization(unittest.TestCase):
    def test_external_names(self):
        for a,b in [('Bluefield','Bluefield Univ.'),('Monroe','Monroe'),('VU-Lynchburg','Virginia-Lynchburg')]:
            self.assertEqual(slug(a),slug(b))
        self.assertNotEqual(slug('Bluefield'),slug('Bluefield State'))
    def test_external_games(self):
        r=[row('2026-09-12','Bluefield','Barton',21,36),row('2026-09-19','Bluefield','Greensboro',28,7),row('2026-09-26','Monroe','UNC Pembroke',6,24)]
        g=[game('6605324','09/12/2026','Bluefield Univ.','Barton',21,36),game('6605930','09/19/2026','Bluefield Univ.','Greensboro',28,7),game('6605675','09/26/2026','Monroe','UNC Pembroke',6,24)]
        result, extra=compare(r,g,set())
        self.assertEqual([x['finding'] for x in result],['MATCH']*3)
        self.assertEqual([x['external_opponent'] for x in result],['yes']*3)
    def test_approved_exception(self):
        ex=read_exceptions(ROOT/'audit/editorial_exceptions.csv')
        r=[row('2026-10-10','Mars Hill','Emory and Henry',9,17)]
        g=[game('6605011','10/10/2026','Mars Hill','Emory and Henry',6,17)]
        result,_=compare(r,g,set(),ex)
        self.assertEqual(result[0]['finding'],'ACCEPTED_EXCEPTION')
        r[0]['visitor_score']='8'
        result,_=compare(r,g,set(),ex)
        self.assertEqual(result[0]['finding'],'SCORE_DISCREPANCY')
    def test_scheduled_and_manual(self):
        r=[row('2026-12-05','Wake Forest','Miami',None,None,'Scheduled'),row('2026-12-05','Louisburg College','DuPage',None,None,'Scheduled')]
        r[1]['division']='JUCO'
        result,_=compare(r,[],set())
        self.assertEqual([x['finding'] for x in result],['SCHEDULED_NOT_IN_NCAA','MANUAL_ONLY'])
    def test_ambiguous_not_guessed(self):
        r=[row('2026-09-12','Bluefield','Barton',21,36)]
        g=[game('1','09/12/2026','Bluefield Univ.','Barton',21,36),game('2','09/12/2026','Bluefield Univ.','Barton',21,36)]
        result,_=compare(r,g,set())
        self.assertEqual(result[0]['finding'],'AMBIGUOUS')
    def test_exception_requires_id_and_exact_scores(self):
        ex=read_exceptions(ROOT/'audit/editorial_exceptions.csv')
        r=[row('2026-10-10','Mars Hill','Emory and Henry',9,17)]
        g=[game('different-id','10/10/2026','Mars Hill','Emory and Henry',6,17)]
        result,_=compare(r,g,set(),ex)
        self.assertEqual(result[0]['finding'],'SCORE_DISCREPANCY')
if __name__=='__main__': unittest.main()
