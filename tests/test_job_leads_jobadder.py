"""Fictional company-contact creation. No live API, credentials or records."""
import copy
import hashlib
import json
from unittest import mock
from urllib.error import HTTPError
import pytest
from cvstudio_jobadder_write import JobAdderContactService, JobAdderContactError

SOURCE={"name":"Example Person","email":"person@example.test","position":"HR","profile_url":"https://www.linkedin.com/in/example-person"}
SCOPE='a'*64
KEY='b'*64
BASE={"account":SCOPE,"contact_key":KEY,"company_id":12,"first_name":"Example","last_name":"Person","position":"HR"}

class Client:
    def __init__(self):
        self.calls=[];self.matches=[];self.total=None;self.fail=None;self.company=12;self.before_post=None
        self.users=[{'userId':7,'firstName':'Example','lastName':'Owner'}, {'userId':8,'firstName':'Example','lastName':'Recruiter'}]
    def request_json(self,path,**kw):
        self.calls.append((path,copy.deepcopy(kw)))
        if kw.get('method')=='POST':
            if self.before_post:self.before_post()
            if self.fail:raise self.fail
            return 201,{"contactId":45}
        if path=='contacts':return 200,{"items":copy.deepcopy(self.matches),"totalCount":self.total if self.total is not None else len(self.matches)}
        if path=='companies':return 200,{"items":[{"companyId":12,"name":"Example Company"}],"totalCount":1}
        if path=='companies/12':return 200,{"companyId":self.company,"name":"Example Company"}
        if path=='users':return 200,{'items':copy.deepcopy(self.users),'totalCount':len(self.users)}
        raise AssertionError('Unexpected remote path')

def setup():
    client=Client();vault={};account={"connected":True,"account_cache_namespace":SCOPE}
    def save(value):vault.clear();vault.update(copy.deepcopy(value))
    def contact(key):
        if key!=KEY:raise JobAdderContactError('Choose the saved contact')
        return copy.deepcopy(SOURCE)
    service=JobAdderContactService(client=lambda:client,account=lambda:account,contact=contact,load=lambda:copy.deepcopy(vault),save=save,clock=lambda:1000)
    return service,client,vault,account

def call(service,action,**changes):return service.perform({**BASE,"action":action,**changes},'fictional-token')
def review(service):return call(service,'review')['review_token']
def post_count(client):return sum(kw.get('method')=='POST' for _,kw in client.calls)

def test_only_reviewed_existing_company_contact_is_posted_once():
    service,client,vault,account=setup()
    assert service.perform({'action':'companies','query':'Example'},'fictional-token')['companies']==[{"id":12,"name":"Example Company"}]
    proof=review(service);assert post_count(client)==0
    def before():assert next(iter(vault['operations'].values()))['state']=='pending'
    client.before_post=before
    result=call(service,'create',review_token=proof,confirmed=True)
    assert result['state']=='created' and result['contact_id']==45
    path,kwargs=next((path,kw) for path,kw in client.calls if kw.get('method')=='POST')
    assert path=='contacts' and kwargs['retries']==0 and kwargs['safe_to_retry'] is False and kwargs['refresh_on_401'] is False
    assert json.loads(kwargs['body'])=={'firstName':'Example','lastName':'Person','email':'person@example.test','position':'HR','companyId':12,'social':{'linkedin':SOURCE['profile_url']}}
    assert 'X-Allow-Duplicates' not in kwargs['headers']
    for action in ['create','review','check']:assert call(service,action,review_token=proof,confirmed=True)['state']=='created'
    assert post_count(client)==1 and SOURCE['email'] not in json.dumps(vault)

@pytest.mark.parametrize('change',[{'confirmed':False},{'review_token':'wrong'},{'position':'Different'},{'first_name':'Other'},{'company_id':13},{'account':'c'*64}])
def test_stale_changed_or_unconfirmed_review_never_writes(change):
    service,client,vault,account=setup();proof=review(service)
    with pytest.raises(JobAdderContactError):call(service,'create',**{'review_token':proof,'confirmed':True,**change})
    assert post_count(client)==0

def test_expired_review_and_changed_account_never_writes():
    service,client,vault,account=setup();proof=review(service);service.clock=lambda:2000
    with pytest.raises(JobAdderContactError):call(service,'create',review_token=proof,confirmed=True)
    service.clock=lambda:1000;account['account_cache_namespace']='c'*64
    with pytest.raises(JobAdderContactError):call(service,'review')
    assert post_count(client)==0

def test_duplicate_email_under_another_company_is_not_overridden():
    service,client,vault,account=setup();client.matches=[{'contactId':77,'email':SOURCE['email'].upper(),'company':{'companyId':90,'name':'Other Company'}}]
    result=call(service,'review');assert result['state']=='exists' and result['matches'][0]['contact_id']==77
    assert post_count(client)==0

def test_racing_duplicate_after_review_is_caught_before_post():
    service,client,vault,account=setup();proof=review(service)
    client.matches=[{'contactId':77,'email':SOURCE['email'],'company':{'companyId':12,'name':'Example Company'}}]
    assert call(service,'create',review_token=proof,confirmed=True)['state']=='exists'
    assert post_count(client)==0

def test_ambiguous_write_survives_restart_and_only_reads_until_confirmed():
    service,client,vault,account=setup();proof=review(service);client.fail=TimeoutError('private upstream details')
    result=call(service,'create',review_token=proof,confirmed=True);assert result['state']=='unconfirmed' and 'private' not in str(result)
    restarted=JobAdderContactService(client=lambda:client,account=lambda:account,contact=lambda key:SOURCE,load=lambda:copy.deepcopy(vault),save=service.save)
    client.fail=None
    for action in ['review','create','check']:assert call(restarted,action,confirmed=True)['state']=='unconfirmed'
    assert post_count(client)==1
    client.matches=[{'contactId':45,'email':SOURCE['email'],'company':{'companyId':12,'name':'Example Company'}}]
    assert call(restarted,'check')['state']=='created' and post_count(client)==1


def test_changing_company_cannot_bypass_uncertain_or_completed_email_write():
    service,client,vault,account=setup();proof=review(service);client.fail=TimeoutError()
    assert call(service,'create',review_token=proof,confirmed=True)['state']=='unconfirmed'
    client.fail=None
    original=client.request_json
    client.request_json=lambda path,**kwargs: (200,{'companyId':13,'name':'Other Company'}) if path=='companies/13' else original(path,**kwargs)
    for action in ['review','create','check']:
        assert call(service,action,company_id=13,confirmed=True)['state']=='unconfirmed'
    assert post_count(client)==1
    client.matches=[{'contactId':45,'email':SOURCE['email'],'company':{'companyId':12,'name':'Example Company'}}]
    assert call(service,'check',company_id=13)['state']=='created','recovery uses the company of the original POST'
    assert call(service,'review',company_id=13)['state']=='created'
    assert post_count(client)==1

def test_storage_failure_before_post_and_corruption_fail_closed():
    service,client,vault,account=setup();proof=review(service)
    service.save=mock.Mock(side_effect=OSError('private path'))
    with pytest.raises(JobAdderContactError):call(service,'create',review_token=proof,confirmed=True)
    assert post_count(client)==0
    service.load=lambda:{'version':99,'operations':{}}
    with pytest.raises(JobAdderContactError):call(service,'review')
    assert post_count(client)==0

@pytest.mark.parametrize('total,matches',[(1,[]),(0,[{}]),(1,[{'contactId':4}])])
def test_incomplete_duplicate_reads_never_allow_post(total,matches):
    service,client,vault,account=setup();client.total=total;client.matches=matches
    with pytest.raises(JobAdderContactError):call(service,'review')
    assert post_count(client)==0

@pytest.mark.parametrize('company',[True,999,None])
def test_wrong_company_response_never_becomes_a_review(company):
    service,client,vault,account=setup();client.company=company
    with pytest.raises(JobAdderContactError):call(service,'review')
    assert post_count(client)==0

def test_401_write_is_not_refreshed_or_replayed_and_requires_new_review():
    service,client,vault,account=setup();proof=review(service);client.fail=HTTPError('https://example.test',401,'denied',{},None)
    assert call(service,'create',review_token=proof,confirmed=True)['state']=='rejected'
    with pytest.raises(JobAdderContactError):call(service,'create',review_token=proof,confirmed=True)
    assert post_count(client)==1

def test_source_email_is_authoritative_and_scan_country_is_not_sent():
    service,client,vault,account=setup();proof=review(service)
    call(service,'create',review_token=proof,confirmed=True,email='other@example.test',country='Malaysia',candidateId=9)
    payload=json.loads(next(kw['body'] for _,kw in client.calls if kw.get('method')=='POST'))
    assert payload['email']==SOURCE['email'] and 'country' not in payload and 'candidateId' not in payload


def test_reviewed_owner_and_recruiters_are_posted_and_remembered_securely():
    service,client,vault,account=setup()
    fields={'owner_user_id':7,'recruiter_user_ids':[8,7],'remember_assignments':True}
    proof=call(service,'review',**fields)['review_token']
    result=call(service,'create',review_token=proof,confirmed=True,**fields)
    assert result['state']=='created'
    payload=json.loads(next(kw['body'] for _,kw in client.calls if kw.get('method')=='POST'))
    assert payload['ownerUserId']==7 and payload['recruiterUserId']==[7,8]
    options=service.perform({'action':'companies','query':'Example','include_assignments':True},'fictional-token')
    assert options['assignments']['available'] is True
    assert options['assignments']['defaults']=={'owner_user_id':7,'recruiter_user_ids':[7,8]}
    assert options['assignments']['users']==[{'id':7,'name':'Example Owner'},{'id':8,'name':'Example Recruiter'}]
    assert 'firstName' not in json.dumps(vault) and 'Example Owner' not in json.dumps(vault)
    account['account_cache_namespace']='c'*64
    other=service.perform({'action':'companies','query':'Example','include_assignments':True},'fictional-token')
    assert other['assignments']['defaults'] is None,'defaults cannot cross a connection change'


@pytest.mark.parametrize('patch',[{'owner_user_id':8},{'recruiter_user_ids':[8]}, {'recruiter_user_ids':[]}])
def test_assignment_changes_require_a_new_review(patch):
    service,client,vault,account=setup()
    fields={'owner_user_id':7,'recruiter_user_ids':[7,8]}
    proof=call(service,'review',**fields)['review_token']
    with pytest.raises(JobAdderContactError):call(service,'create',review_token=proof,confirmed=True,**{**fields,**patch})
    assert post_count(client)==0


@pytest.mark.parametrize('fields',[
    {'owner_user_id':True},{'owner_user_id':-1},{'owner_user_id':'7'}, {'owner_user_id':999},
    {'recruiter_user_ids':'all'},{'recruiter_user_ids':[True]}, {'recruiter_user_ids':[8,8]},
    {'recruiter_user_ids':[999]},{'recruiter_user_ids':list(range(1,1002))}, {'remember_assignments':'yes'},
])
def test_invalid_or_unknown_assignments_never_create(fields):
    service,client,vault,account=setup()
    with pytest.raises(JobAdderContactError):call(service,'review',**fields)
    assert post_count(client)==0


def test_inactive_assignments_cannot_survive_review_or_become_defaults():
    service,client,vault,account=setup()
    fields={'owner_user_id':7,'recruiter_user_ids':[8],'remember_assignments':True}
    proof=call(service,'review',**fields)['review_token']
    assert 'assignment_defaults' not in vault,'review alone does not change saved defaults'
    client.users[0]['inactive']=True
    with pytest.raises(JobAdderContactError):call(service,'create',review_token=proof,confirmed=True,**fields)
    vault['assignment_defaults']={'account':SCOPE,'owner_user_id':7,'recruiter_user_ids':[8]}
    options=service.perform({'action':'companies','query':'Example','include_assignments':True},'fictional-token')
    assert options['assignments']['defaults'] is None and options['assignments']['stale'] is True
    assert post_count(client)==0


def test_default_assignments_are_omitted_but_explicit_empty_recruiters_are_sent():
    service,client,vault,account=setup()
    proof=call(service,'review',owner_user_id=None,recruiter_user_ids=[])['review_token']
    call(service,'create',review_token=proof,confirmed=True,owner_user_id=None,recruiter_user_ids=[])
    payload=json.loads(next(kw['body'] for _,kw in client.calls if kw.get('method')=='POST'))
    assert 'ownerUserId' not in payload and payload['recruiterUserId']==[]


def test_assignment_directory_failure_preserves_legacy_create_and_preferences():
    service,client,vault,account=setup()
    original=client.request_json
    def request(path,**kwargs):
        if path=='users':raise HTTPError('https://example.test',403,'denied',{},None)
        return original(path,**kwargs)
    client.request_json=request
    options=service.perform({'action':'companies','query':'Example','include_assignments':True},'fictional-token')
    assert options['assignments']['available'] is False
    proof=review(service);assert call(service,'create',review_token=proof,confirmed=True)['state']=='created'
    assert post_count(client)==1


def test_unconfirmed_assignment_write_recovers_original_defaults_without_replay():
    service,client,vault,account=setup()
    fields={'owner_user_id':7,'recruiter_user_ids':[8],'remember_assignments':True}
    proof=call(service,'review',**fields)['review_token'];client.fail=TimeoutError()
    assert call(service,'create',review_token=proof,confirmed=True,**fields)['state']=='unconfirmed'
    assert 'assignment_defaults' not in vault
    client.matches=[{'contactId':45,'email':SOURCE['email'],'company':{'companyId':12,'name':'Example Company'}}]
    assert call(service,'check',owner_user_id=999,recruiter_user_ids=[])['state']=='created'
    assert vault['assignment_defaults']=={'account':SCOPE,'owner_user_id':7,'recruiter_user_ids':[8]}
    assert 'assignments' not in next(iter(vault['operations'].values()))
    assert post_count(client)==1


def test_no_remember_preserves_prior_defaults_and_legacy_company_search_does_not_read_users():
    service,client,vault,account=setup()
    defaults={'account':SCOPE,'owner_user_id':7,'recruiter_user_ids':[8]}
    vault.update(version=1,operations={},assignment_defaults=copy.deepcopy(defaults))
    proof=call(service,'review',owner_user_id=8,recruiter_user_ids=[],remember_assignments=False)['review_token']
    call(service,'create',review_token=proof,confirmed=True,owner_user_id=8,recruiter_user_ids=[],remember_assignments=False)
    assert vault['assignment_defaults']==defaults
    before=len(client.calls);service.perform({'action':'companies','query':'Example'},'fictional-token')
    assert not any(path=='users' for path,_ in client.calls[before:])


@pytest.mark.parametrize('data',[
    {'items':[],'totalCount':2}, {'items':[],'totalCount':'0'}, {'items':[],'totalCount':1001},
    {'items':[{'userId':True}],'totalCount':1},
    {'items':[{'userId':7},{'userId':7}],'totalCount':2},
    {'items':[{'userId':7,'inactive':'false'}],'totalCount':1},
])
def test_malformed_user_directory_cannot_authorize_assignments(data):
    service,client,vault,account=setup();original=client.request_json
    client.request_json=lambda path,**kwargs:(200,data) if path=='users' else original(path,**kwargs)
    result=service.perform({'action':'companies','query':'Example','include_assignments':True},'fictional-token')
    assert result['assignments']['available'] is False
    with pytest.raises(JobAdderContactError):call(service,'review',owner_user_id=7)
    assert post_count(client)==0


def test_full_select_all_payload_fits_the_bounded_route_without_extra_post():
    import app
    service,client,vault,account=setup()
    identities=list(range(2147482000,2147483000))
    client.users=[{'userId':identity,'firstName':'Example','lastName':str(identity)} for identity in identities]
    browser=app.app.test_client();browser.get('/')
    data={**BASE,'action':'review','owner_user_id':identities[0],'recruiter_user_ids':identities,'position':'Role '*100}
    headers={'X-CV-Studio-Request':'1'}
    with mock.patch.object(app,'_JOB_LEADS_JA',service),mock.patch.object(app,'_ja_refresh_access_token',return_value='fictional-token'):
        raw=json.dumps(data).encode();assert 8192<len(raw)<16384
        result=browser.post('/jobadder/contact_actions',data=raw,content_type='application/json',headers=headers)
        assert result.status_code==200 and result.json['state']=='review'
        assert post_count(client)==0
        too_large=browser.post('/jobadder/contact_actions',data=b' '*16385,content_type='application/json',headers=headers)
        assert too_large.status_code==413 and post_count(client)==0

def test_new_route_is_the_only_change_to_all_122_previous_routes():
    import app
    from cvstudio_architecture import _route_contract
    old=tuple(row for row in _route_contract(app.app) if row['endpoint']!='jobadder_contact_actions')
    assert len(old)==122 and hashlib.sha256(json.dumps(old,ensure_ascii=True,sort_keys=True,separators=(',',':')).encode()).hexdigest()=='4cb6b3f8e64b3421c9b9fae819c7fe64e6b05d98db193bb1eb42f8da07aaf600'

def test_route_requires_browser_pairing_and_tracks_account_transition(tmp_path):
    import app
    service,client,vault,account=setup()
    browser=app.app.test_client();headers={'X-CV-Studio-Request':'1'}
    with mock.patch.object(app,'_JOB_LEADS_JA',service),mock.patch.object(app,'_ja_refresh_access_token',return_value='fictional-token'):
        assert browser.post('/jobadder/contact_actions',json={'action':'companies','query':'Example'},headers=headers).status_code==403
        browser.get('/')
        assert browser.post('/jobadder/contact_actions',json={'action':'companies','query':'Example'},headers={'Origin':'https://other.test'}).status_code==403
        response=browser.post('/jobadder/contact_actions',json={'action':'companies','query':'Example'},headers=headers)
        assert response.status_code==200 and 'no-store' in response.headers['Cache-Control']
        proof=browser.post('/jobadder/contact_actions',json={**BASE,'action':'review'},headers=headers).json['review_token']
        def during_post():
            assert app._ja_begin_account_transition()=='write'
        client.before_post=during_post
        response=browser.post('/jobadder/contact_actions',json={**BASE,'action':'create','review_token':proof,'confirmed':True},headers=headers)
        assert response.json['state']=='created'
        assert response.json['contact_url'].endswith('/contacts/45')


@pytest.mark.parametrize('state,identity,expected', [
    ('created',45,True),('exists',45,True),('unconfirmed',45,False),
    ('review',45,False),('created',True,False),('created',None,False),('created',-1,False),
])
def test_contact_links_use_the_connected_jobadder_region_and_confirmed_id(state, identity, expected):
    import app
    browser=app.app.test_client();browser.get('/')
    service=mock.Mock()
    service.perform.return_value={'state':state,'contact_id':identity}
    with mock.patch.object(app,'_JOB_LEADS_JA',service),mock.patch.object(app,'_ja_refresh_access_token',return_value='fictional-token'),mock.patch.object(app,'_jobadder_web_base',return_value='https://au3.jobadder.com'):
        response=browser.post('/jobadder/contact_actions',json={'action':'check'},headers={'X-CV-Studio-Request':'1'})
    assert response.status_code==200
    assert ('contact_url' in response.json) is expected
    if expected:assert response.json['contact_url']=='https://au3.jobadder.com/contacts/45'
