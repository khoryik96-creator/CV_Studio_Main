"""Fictional, read-only name checks. No credentials, paid calls or real records."""
import copy
import json
from unittest import mock

import pytest

from cvstudio_jobadder_write import JobAdderContactMatcher, JobAdderContactError
from test_job_leads_jobadder import setup, call, SOURCE, SCOPE, KEY, post_count


def contact(identity=31, first='Marina', last='Quinn', company='Example Bank (MY)'):
    return {'contactId':identity,'firstName':first,'lastName':last,'company':{'companyId':12,'name':company},
            'email':'already-saved@example.test','position':'Talent Manager'}


def matcher(rows=None, source=None):
    account={'connected':True,'account_cache_namespace':SCOPE}
    saved=source or {'name':'Marina Q.','company':'Example Bank'}
    calls=[]
    class Client:
        def request_json(self,path,**kwargs):
            calls.append((path,kwargs))
            if callable(rows):return rows(path,kwargs)
            return 200,{'items':copy.deepcopy(rows or []),'totalCount':len(rows or [])}
    service=JobAdderContactMatcher(client=Client,account=lambda:account,source=lambda body:copy.deepcopy(saved))
    return service,account,calls


def find(service,**extra):
    return service.find({'action':'find_contacts','account':SCOPE,'contact_key':KEY,**extra},'fictional-token')


def test_initial_surname_matches_a_full_name_and_never_returns_or_unlocks_email():
    service,_,calls=matcher([contact()])
    result=find(service)
    assert result['state']=='matches' and result['matches'][0]['reason']=='Name and initial'
    assert result['matches'][0]['company_matches']
    assert [c[1]['params']['Name'] for c in calls]==['marina']
    assert all(path=='contacts' and kw.get('method','GET')=='GET' for path,kw in calls)
    assert 'already-saved@example.test' not in json.dumps(result)


@pytest.mark.parametrize('name,first,last,expected',[
    ('MARÍNA QUINN','Quinn','Marina',True),
    ('Marina Q.','Marina','Quinn',True),
    ('M. Quinn','Marina','Quinn',True),
    ('Marina Quinn','Marina','Quinns',True),
    ('Marina Quinn','Marina','Queen',False),
    ('Marina Quinn','Marina','Smith',False),
    ('Marina Quinn','Melissa','Quinn',False),
])
def test_name_variations_remain_suggestions_and_not_arbitrary_shared_tokens(name,first,last,expected):
    service,_,_=matcher([contact(first=first,last=last)],{'name':name,'company':'Example Bank'})
    assert bool(find(service)['matches']) is expected


def test_company_agreement_ranks_results_without_hiding_other_company_names():
    service,_,_=matcher([contact(32,company='Other Organisation'),contact(31)])
    result=find(service)
    assert [r['contact_id'] for r in result['matches']]==[31,32]
    assert not result['matches'][1]['company_matches']
    assert len({r['contact_id'] for r in result['matches']})==2


def test_queries_come_only_from_saved_source_and_are_bounded():
    service,_,calls=matcher([],{'name':'Marina Quinn','company':'Example Bank'})
    assert find(service,name='Untrusted Different Name')['state']=='no_matches'
    assert [kw['params'] for _,kw in calls]==[{'Name':'marina','Limit':100},{'Name':'quinn','Limit':100}]


def test_partial_or_malformed_rows_never_become_a_clean_no_match():
    for response in [{'items':[],'totalCount':300},{'items':[{}],'totalCount':1}]:
        service,_,_=matcher(lambda *_:(200,response))
        result=find(service)
        assert result['state']=='incomplete' and result['partial']


@pytest.mark.parametrize('data',[{}, {'items':None,'totalCount':0},{'items':[],'totalCount':True},{'items':[contact()],'totalCount':0}])
def test_bad_search_envelopes_fail_without_suggesting_a_paid_lookup(data):
    service,_,_=matcher(lambda *_:(200,data))
    with pytest.raises(JobAdderContactError):find(service)


def test_initials_only_do_not_query_all_contacts():
    service,_,calls=matcher(source={'name':'M. Q.','company':'Example Bank'})
    assert find(service)['state']=='incomplete' and not calls


def test_account_changes_before_or_during_reads_discard_results():
    service,account,calls=matcher([contact()])
    with pytest.raises(JobAdderContactError):find(service,account='c'*64)
    assert not calls
    def during(*_):
        account['account_cache_namespace']='c'*64
        return 200,{'items':[contact()],'totalCount':1}
    service,account,_=matcher(during)
    with pytest.raises(JobAdderContactError):find(service)


def test_name_matches_cannot_confirm_a_previous_write_or_create_a_contact():
    service,client,vault,account=setup()
    client.matches=[{'contactId':45,'email':SOURCE['email'],'company':{'companyId':12,'name':'Example Company'}}]
    result=call(service,'review')
    assert result['contact_id']==45 and post_count(client)==0
    links=service.contact_links([{'contact_key':KEY,'email':SOURCE['email']}])
    assert links['links']==[{'contact_key':KEY,'state':'exists','contact_id':45}]
    assert SOURCE['email'] not in json.dumps(vault)


def test_multiple_email_matches_are_not_silently_linked_to_the_first_person():
    service,client,vault,_=setup()
    client.matches=[{'contactId':identity,'email':SOURCE['email'],'company':{'companyId':12,'name':'Example Company'}} for identity in (45,46)]
    result=call(service,'review')
    assert len(result['matches'])==2 and not result.get('contact_id')
    assert service.contact_links([{'contact_key':KEY,'email':SOURCE['email']}])['links']==[]
    assert post_count(client)==0


def test_route_uses_saved_hr_evidence_and_regional_contact_links():
    import app
    source={'name':'Marina Q.','url':'https://www.linkedin.com/in/fictional-marina'}
    row={'company':'Example Bank','hr':{'people':[source]}}
    service,_,_=matcher([contact()])
    service.source=app._jobadder_contact_match_source
    browser=app.app.test_client();browser.get('/')
    with mock.patch.object(app._JOB_LEADS,'hr_record',return_value=row),mock.patch.object(app,'_JOB_LEADS_JA_MATCHES',service),mock.patch.object(app,'_ja_refresh_access_token',return_value='fictional-token'),mock.patch.object(app,'_jobadder_web_base',return_value='https://au3.jobadder.com'):
        response=browser.post('/jobadder/contact_actions',json={'action':'find_contacts','account':SCOPE,'id':'a'*32,'revision':1,'url':source['url']},headers={'X-CV-Studio-Request':'1'})
    assert response.status_code==200
    assert response.json['matches'][0]['url']=='https://au3.jobadder.com/contacts/31'
    assert 'no-store' in response.headers['Cache-Control']
    with mock.patch.object(app._JOB_LEADS,'hr_record',return_value=row):
        with pytest.raises(JobAdderContactError):app._jobadder_contact_match_source({'url':'https://www.linkedin.com/in/not-saved'})


def test_large_result_sets_are_bounded_and_never_report_a_complete_negative():
    service,_,calls=matcher([contact(identity=i) for i in range(1,201)])
    result=find(service)
    assert result['partial'] and len(result['matches'])==10
    assert len(calls)==1 and calls[0][1]['params']['Limit']==100


def test_disconnected_or_uncredentialed_checks_do_not_read_saved_people_or_jobadder():
    service,account,calls=matcher([contact()])
    account['connected']=False
    with pytest.raises(JobAdderContactError):find(service)
    account['connected']=True
    with pytest.raises(JobAdderContactError):service.find({'account':SCOPE},'')
    assert not calls
