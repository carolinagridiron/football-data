import unittest
from national_postseason import build_outputs,postseason_candidate,merge_preserving_finals


def game(gid,date,status='scheduled',score=None):
    return {'id':str(gid),'date':date,'status':status,'_season':2026,'away':{'ncaa_slug':'a','score':score},'home':{'ncaa_slug':'b','score':score}}

class Tests(unittest.TestCase):
    def test_window(self):
        self.assertTrue(postseason_candidate(game(1,'2026-12-19')))
        self.assertTrue(postseason_candidate(game(1,'2027-01-10')))
        self.assertFalse(postseason_candidate(game(1,'2026-11-28')))
    def test_merge(self):
        original=game(1,'2026-12-19','final',10)
        with self.assertRaises(ValueError):merge_preserving_finals({'1':original},{'1':game(1,'2026-12-19','final',11)})
    def test_output(self):
        national,bowl=build_outputs(2026,{}, {'1':game(1,'2026-12-19'),'2':game(2,'2026-10-01')})
        self.assertEqual(national['game_count'],2)
        self.assertEqual(bowl['game_count'],1)
    def test_season_guard(self):
        with self.assertRaises(ValueError):build_outputs(2026,{'season':2025,'games':[]},{})
if __name__=='__main__':unittest.main()

class DateFormats(unittest.TestCase):
    def test_ncaa_us_date(self):
        self.assertTrue(postseason_candidate(game(3,'12/19/2026')))
        self.assertTrue(postseason_candidate(game(4,'01/09/2027')))
