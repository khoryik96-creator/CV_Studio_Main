"""Local session, stale evidence and guarded Apollo routing, without a provider."""
import hashlib
import json
from unittest import mock


def test_apollo_adds_only_its_declared_route_to_the_exact_previous_contract():
    import app
    from cvstudio_architecture import _route_contract
    previous=tuple(row for row in _route_contract(app.app) if row['endpoint']!='apollo_connection')
    assert len(previous)==121
    assert hashlib.sha256(json.dumps(previous,ensure_ascii=True,sort_keys=True,separators=(',',':')).encode()).hexdigest()=='6b0b7dfd41ab2b85fa4685de18efdf1aad477fa91a39cbf0b8a8794eb923b221'


def test_apollo_routes_reject_unpaired_cross_site_and_stale_requests(tmp_path):
    # The suite launcher isolates the entire application's receipt and state.
    import app
    from cvstudio_job_leads import JobLeadsStore
    from test_job_leads_hr import AD, SEARCH
    store=JobLeadsStore(tmp_path/'leads.sqlite3')
    row=store.save(AD)['record'];row=store.save_hr(row['id'],row['revision'],SEARCH)['record']
    unpaired=app.app.test_client()
    assert unpaired.post('/apollo',json={'action':'connect'},headers={'X-CV-Studio-Request':'1'}).status_code==403
    client=app.app.test_client();client.get('/')
    with mock.patch.object(app,'_JOB_LEADS',store), mock.patch.object(app,'_APOLLO') as service:
        assert client.post('/apollo',json={'action':'connect'},headers={'Origin':'https://other.test'}).status_code==403
        headers={'X-CV-Studio-Request':'1'}
        assert client.post('/apollo',json={'action':'reveal','id':row['id'],'revision':row['revision']-1},headers=headers).status_code==409
        assert client.post('/apollo',data='x'*4097,headers={**headers,'Content-Type':'application/json'}).status_code==413
        service.perform.assert_not_called()
        service.perform.return_value={'result':{'state':'not_found'}}
        data={'action':'reveal','id':row['id'],'revision':row['revision'],'url':SEARCH['people'][0]['url'],'confirmed':True}
        response=client.post('/apollo',json=data,headers=headers)
        assert response.status_code==200 and 'no-store' in response.headers['Cache-Control']
        assert service.perform.call_args.kwargs['row']==row
        assert store.list()==[row], 'email actions cannot change ad notes or saved HR evidence'
        service.status.return_value={'connected':False,'available':False}
        assert client.get('/apollo').json['available'] is False
