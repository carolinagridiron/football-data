import unittest
from pathlib import Path
from audit import compare, game_pair, side_identity, read_exceptions
from collector import normalize

ROOT=Path(__file__).resolve().parents[1]

def game(gid, date, visitor, visitor_slug, home, home_slug, vs, hs, division):
    item={'game':{'gameID':gid,'startDate':date,'gameState':'final',
        'away':{'names':{'short':visitor,'seo':visitor_slug},'score':str(vs)},
        'home':{'names':{'short':home,'seo':home_slug},'score':str(hs)}}}
    return normalize(item,division)

def row(date, visitor, home, vs, hs, division):
    return {'date':date,'division':division,'visitor':visitor,'home':home,
            'visitor_score':str(vs),'home_score':str(hs),'status':'Final'}

class IdentityRegression(unittest.TestCase):
    def test_real_bluefield_slug(self):
        g=game('6605324','09/12/2026','Bluefield Univ.','bluefield-col','Barton','barton',21,36,'d2')
        r=row('2026-09-12','Bluefield','Barton',21,36,'Division II')
        self.assertEqual(compare([r],[g],set())[0][0]['finding'],'MATCH')
    def test_real_bluefield_d3(self):
        g=game('6605930','09/19/2026','Bluefield Univ.','bluefield-col','Greensboro','greensboro',28,7,'d3')
        r=row('2026-09-19','Bluefield','Greensboro',28,7,'Division III')
        self.assertEqual(compare([r],[g],set())[0][0]['finding'],'MATCH')
    def test_real_monroe_empty_slug(self):
        g=game('6605675','09/26/2026','Monroe','','UNC Pembroke','unc-pembroke',6,24,'d2')
        r=row('2026-09-26','Monroe','UNC Pembroke',6,24,'Division II')
        self.assertEqual(side_identity(g['away']),'external:monroe-university')
        self.assertEqual(compare([r],[g],set())[0][0]['finding'],'MATCH')
    def test_nonmatching_external_not_guessed(self):
        g=game('x','09/26/2026','Unknown College','','Barton','barton',6,24,'d2')
        r=row('2026-09-26','Monroe','Barton',6,24,'Division II')
        self.assertEqual(compare([r],[g],set())[0][0]['finding'],'UNMATCHED')
    def test_header_only_2027_exceptions(self):
        self.assertEqual(read_exceptions(ROOT/'audit/editorial_exceptions_2027.csv'),{})

if __name__=='__main__': unittest.main()
