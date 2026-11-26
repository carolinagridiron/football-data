import unittest
from archive_collector import sweep

class PriorityTests(unittest.TestCase):
    def test_pending_before_partial_and_retry(self):
        def game(i):
            return {'game': {'gameID':str(i),'startDate':'2026-09-01','away':{'names':{'short':'NC','seo':'nc-at'}},'home':{'names':{'short':'Other','seo':'other'}}}}
        config={'nc_school_slugs':['nc-at']}
        def scoreboard(url):
            return {'games':[game(i) for i in (1,2,3,4)]} if '/fbs/' in url else {'games':[]}
        def detail(url):
            i=url.rsplit('/',1)[-1]
            return {'contests':[{'id':i,'teams':[],'location':{},'linescores':[]}]}
        existing={'games':{},'details':{},'detail_tracking':{
            '1':{'status':'PARTIAL','attempts':1},
            '2':{'status':'RETRY','attempts':1},
            '3':{'status':'PENDING','attempts':0}}}
        _,report=sweep(2026,config,1,fetch=scoreboard,detail_fetch=detail,existing=existing,detail_limit=2)
        self.assertEqual(report['detail_requests_by_prior_status'],{'PENDING':2,'RETRY':0,'PARTIAL':0})
        self.assertEqual(report['eligible_before_batch'],{'PENDING':2,'RETRY':1,'PARTIAL':1})
    def test_retry_before_partial_when_no_pending(self):
        def game(i):
            return {'game': {'gameID':str(i),'startDate':'2026-09-01','away':{'names':{'short':'NC','seo':'nc-at'}},'home':{'names':{'short':'Other','seo':'other'}}}}
        config={'nc_school_slugs':['nc-at']}
        def scoreboard(url):return {'games':[game(i) for i in (1,2)]} if '/fbs/' in url else {'games':[]}
        def detail(url):return {'contests':[{'id':url.rsplit('/',1)[-1],'teams':[],'location':{},'linescores':[]}]}
        existing={'detail_tracking':{'1':{'status':'PARTIAL','attempts':1},'2':{'status':'RETRY','attempts':1}}}
        _,r=sweep(2026,config,1,fetch=scoreboard,detail_fetch=detail,existing=existing,detail_limit=1)
        self.assertEqual(r['detail_requests_by_prior_status']['RETRY'],1)
if __name__=='__main__':unittest.main()
