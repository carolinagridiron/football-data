import unittest
from archive_collector import detail_state, sweep

class DetailTrackingTests(unittest.TestCase):
    def test_classification(self):
        self.assertEqual(detail_state({'venue':{},'period_scores':[]}), 'NO_DATA')
        self.assertEqual(detail_state({'venue':{'city':'Raleigh'},'period_scores':[]}), 'PARTIAL')
        self.assertEqual(detail_state({'venue':{'stadium':'Stadium'},'period_scores':[{'period':'1'}]}), 'COMPLETE')

    def test_no_data_does_not_repeat(self):
        config={'nc_school_slugs':['barton']}
        item={'game':{'gameID':'1','away':{'names':{'seo':'barton'}},'home':{'names':{'seo':'other'}},'gameState':'F'}}
        fetch=lambda url:{'games':[item]}
        calls=[]
        def detail(url):
            calls.append(url)
            return {'contests':[{'id':'1','teams':[],'linescores':[],'location':None}]}
        first, report=sweep(2026,config,1,fetch=fetch,detail_fetch=detail,detail_limit=15)
        self.assertEqual(report['detail_status_counts']['NO_DATA'],1)
        second, report=sweep(2026,config,1,fetch=fetch,detail_fetch=detail,existing=first,detail_limit=15)
        self.assertEqual(len(calls),1)
        self.assertEqual(report['detail_requests'],0)
        self.assertEqual(report['details_pending'],0)

    def test_migration_does_not_repeat_complete(self):
        config={'nc_school_slugs':['barton']}
        item={'game':{'gameID':'1','away':{'names':{'seo':'barton'}},'home':{'names':{'seo':'other'}}}}
        existing={'games':{'1':{'id':'1'}},'details':{'1':{'venue':{'stadium':'X'},'period_scores':[{'period':'1'}]}}}
        result,report=sweep(2026,config,1,fetch=lambda u:{'games':[item]},detail_fetch=lambda u: (_ for _ in ()).throw(AssertionError('unexpected fetch')),existing=existing,detail_limit=15)
        self.assertEqual(result['detail_tracking']['1']['status'],'COMPLETE')
        self.assertEqual(report['detail_requests'],0)

if __name__=='__main__': unittest.main()
