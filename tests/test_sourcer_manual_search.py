"""Manual search authority and independent AI-review criteria; fictional only."""
from unittest import mock
import pytest
from cvstudio_linkedin_sourcer import LinkedInSourcerService, SourcerError

QUERY='Oracle AND (Ansible OR Terraform)'
PROMPT='Look for current Malaysia location and explicit local work eligibility; do not guess.'

def provider(model, brief, task, schema, data):
    value={'query':'Different generated keywords','country':'Singapore','requirements':['Oracle','Automation']}
    if task=='profile_review':
        profile=data['profiles'][0]
        value={'candidates':[{'id':profile['id'],'score':80,'evidence_refs':[profile['passages'][0]['id']],'unknowns':['Work eligibility not stated']} ]}
    return {'content':[{'type':'tool_use','name':'return_'+task,'input':value}]},{'usage':{'input_tokens':10,'output_tokens':20},'cost':0.001}

def setup(**changes):
    transport=mock.Mock(side_effect=provider)
    service=LinkedInSourcerService(key_available=lambda:True,provider_call=transport)
    body={'action':'start','brief':'','boolean_query':QUERY,'country_mode':'specific','country':'Malaysia','mode':'standard','max_pages':1,'max_calls':5,'confirm_paid':True,**changes}
    run=service.handle(body)['run']['id']
    return service,transport,run

def plan(service,run):return service.handle({'action':'plan','run_id':run})

def test_boolean_only_keeps_exact_search_and_native_country_without_paid_planning():
    service,transport,run=setup()
    result=plan(service,run)
    assert result['plan']['query']==QUERY and result['plan']['country']=='Malaysia'
    assert result['run']['calls']==0 and result['run']['tokens']==0
    transport.assert_not_called()

@pytest.mark.parametrize('country_mode,country',[('specific','Malaysia'),('any','')])
def test_both_uses_own_boolean_and_complete_review_prompt(country_mode,country):
    service,transport,run=setup(brief=PROMPT,country_mode=country_mode,country=country)
    result=plan(service,run);assert result['plan']['query']==QUERY and result['plan']['country']==country
    transport.assert_not_called()
    reply=service.handle({'action':'review','run_id':run,'stage':'screen','page':1,'profiles':[{'id':'p0','name':'Example','url':'https://www.linkedin.com/in/example','text':'Oracle database and Ansible automation. Kuala Lumpur, Malaysia.'}]})
    assert reply['candidates'] and transport.call_count==1
    args=transport.call_args.args
    assert args[1]==PROMPT and args[2]=='profile_review'
    assert args[4]['search_context']['boolean_query']==QUERY
    assert args[4]['search_context']['country_mode']==country_mode
    assert 'do not infer' in args[4]['instruction'].lower()

def test_both_can_infer_country_from_prompt_without_rewriting_boolean():
    service,transport,run=setup(brief=PROMPT,country_mode='auto',country='')
    result=plan(service,run)
    assert result['plan']['query']==QUERY and result['plan']['country']=='Singapore'
    assert result['run']['calls']==1 and transport.call_count==1
    assert 'query' not in transport.call_args.args[3]['properties'],'country inference never asks AI to rewrite a manual Boolean'
    assert transport.call_args.args[4]['boolean_query']==QUERY

@pytest.mark.parametrize('country_mode,country,expected',[('specific','Malaysia','Malaysia'),('any','','')])
def test_prompt_only_uses_explicit_country_authority(country_mode,country,expected):
    service,transport,run=setup(brief='Oracle automation profiles in Singapore',boolean_query='',country_mode=country_mode,country=country)
    result=plan(service,run)
    assert result['plan']['query']=='Different generated keywords' and result['plan']['country']==expected
    assert transport.call_count==1

@pytest.mark.parametrize('query',['Oracle AND','(Oracle OR Ansible','Oracle OR )Ansible(','Oracle "unfinished','A AND B AND C AND D AND E','A OR B OR C OR D NOT intern','x\x00y','x'*1001])
def test_invalid_or_overbudget_manual_boolean_fails_before_provider(query):
    transport=mock.Mock()
    service=LinkedInSourcerService(key_available=lambda:True,provider_call=transport)
    with pytest.raises(SourcerError):service.handle({'action':'start','brief':'Check automation experience','boolean_query':query,'mode':'standard','max_pages':1,'max_calls':5,'confirm_paid':True})
    transport.assert_not_called();assert service.run is None

@pytest.mark.parametrize('query',['Oracle AND (Ansible OR Terraform)','"Oracle OR SQL" NOT intern','(Oracle OR DBA) AND (Ansible OR Chef)','Oracle database'])
def test_valid_manual_boolean_is_never_shortened_or_rephrased(query):
    service,transport,run=setup(boolean_query=query)
    assert plan(service,run)['plan']['query']==query
    transport.assert_not_called()

@pytest.mark.parametrize('changes',[{'confirm_paid':False},{'boolean_query':None},{'country_mode':'specific','country':''},{'country_mode':'guess'},{'country':'x\ny'},{'country':None},{'use_open_search':True},{'mode':'recruiter'}])
def test_invalid_settings_never_charge(changes):
    with pytest.raises(SourcerError):setup(**changes)

def test_recruiter_boolean_without_native_country_works_unchanged():
    query='Oracle AND Database AND (Ansible OR Chef OR Puppet) NOT intern'
    service,transport,run=setup(mode='recruiter',country_mode='any',country='',boolean_query=query)
    assert plan(service,run)['plan']['query']==query
    transport.assert_not_called()

def test_boolean_only_auto_country_needs_no_inference_and_still_requires_a_key():
    service,transport,run=setup(country_mode='auto',country='')
    assert plan(service,run)['plan']['country']==''
    transport.assert_not_called()
    service=LinkedInSourcerService(key_available=lambda:False,provider_call=transport)
    with pytest.raises(SourcerError,match='key'):service.handle({'action':'start','brief':'','boolean_query':QUERY,'mode':'standard','max_pages':1,'max_calls':5,'confirm_paid':True})


def test_explicit_country_does_not_hide_ai_geography_mixed_into_keywords():
    service,transport,run=setup(brief='Oracle profiles',boolean_query='',country_mode='any',country='')
    def mixed(*args):
        return {'content':[{'type':'tool_use','name':'return_search_plan','input':{'query':'Oracle AND Singapore','country':'Singapore','requirements':['Oracle']}}]},{'usage':{'input_tokens':10,'output_tokens':20},'cost':0.001}
    transport.side_effect=mixed
    with pytest.raises(SourcerError,match='country into the keywords') as error:plan(service,run)
    assert transport.call_count==1 and service.run.calls==1
    assert error.value.accounting['usage']['output_tokens']==20
