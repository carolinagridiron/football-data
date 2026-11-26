import unittest
from archive_collector import parse_detail,merge,sweep
class ArchiveTests(unittest.TestCase):
 def test_detail(self):
  p={'contests':[{'id':'123','linescores':[{'period':'1','visit':'7','home':'3'}],'location':{'venue':'Stadium','city':'Town'},'teams':[{'isHome':True,'teamId':'1','seoname':'home'},{'isHome':False,'teamId':'2','seoname':'away'}]}]}
  x=parse_detail(p,'123');self.assertEqual(x['period_scores'][0]['away'],'7');self.assertEqual(x['venue']['stadium'],'Stadium')
 def test_preserve_conflict(self):
  x,c=merge({'venue':{'stadium':'Original'}},{'id':'123','venue':{'stadium':'Changed'}})
  self.assertEqual(x['venue']['stadium'],'Original');self.assertEqual(len(c),1)
 def test_failed_week_prevents_change(self):
  old={'games':{'x':{'id':'x'}}}; result,report=sweep(2026,{'nc_school_slugs':['barton']},1,fetch=lambda u: (_ for _ in ()).throw(RuntimeError('offline')),existing=old,detail_limit=0)
  self.assertEqual(result,old);self.assertTrue(report['blocked'])
if __name__=='__main__':unittest.main()
