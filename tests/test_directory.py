import unittest
from pathlib import Path
from team_directory.lookup import load_lookup,resolve_name
ROOT=Path(__file__).resolve().parents[1]
class TestDirectory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lookup=load_lookup(ROOT/'team_directory/ncaa_teams.csv',ROOT/'team_directory/editorial_names.csv')
    def test_nc_state(self):self.assertEqual(resolve_name('NC State',self.lookup),'north-carolina-st')
    def test_winston(self):self.assertEqual(resolve_name('Winston-Salem State',self.lookup),'winston-salem')
    def test_west_alabama(self):self.assertEqual(resolve_name('West Alabama',self.lookup),'west-ala')
    def test_ambiguous_miami(self):self.assertTrue(resolve_name('Miami',self.lookup).startswith('unresolved:'))
    def test_ncaa_slug(self):self.assertEqual(resolve_name('unc-pembroke',self.lookup),'unc-pembroke')
    def test_unknown(self):self.assertTrue(resolve_name('unknown university',self.lookup).startswith('unresolved:'))
if __name__=='__main__':unittest.main()
