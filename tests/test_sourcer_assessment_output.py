"""Synthetic assessment contracts; never use a live key or provider."""
import copy
from pathlib import Path
import os
import sys
from unittest import mock

import pytest
import cvstudio_linkedin_sourcer as sourcer

PROFILE = {'id':'p0','name':'Example Candidate',
           'url':'https://www.linkedin.com/in/example-candidate',
           'text':'Finance Manager. SAP finance experience. Manufacturing.'}
ROW = {'id':'p0','score':80,'evidence':['SAP finance experience'],
       'unknowns':['Availability not stated']}


def response(value):
    return ({'content':[{'type':'tool_use','name':'return_profile_review','input':value}]},
            {'usage':{'input_tokens':31,'output_tokens':17,'api_calls':1},
             'provider':'deepseek','model':'deepseek-v4-flash','cost':0.001})


def service(value):
    call=mock.Mock(return_value=response(value))
    engine=sourcer.LinkedInSourcerService(key_available=lambda:True,provider_call=call)
    run=engine.handle({'action':'start','brief':'Finance managers with SAP',
                      'mode':'standard','max_pages':10,'max_calls':35,
                      'confirm_paid':True})['run']['id']
    return engine,run,call


def test_schema_declares_the_limits_that_the_validator_enforces():
    fields=sourcer.REVIEW_SCHEMA['properties']['candidates']['items']['properties']
    assert fields['score']['minimum']==0 and fields['score']['maximum']==100
    assert fields['evidence']['minItems']==1 and fields['evidence']['maxItems']==4
    assert fields['unknowns']['maxItems']==6
    for name in ['evidence','unknowns']:
        assert fields[name]['items']['minLength']==1
        assert fields[name]['items']['maxLength']==250


@pytest.mark.parametrize('stage,limit',[('screen',5),('detail',1)])
def test_per_call_schema_matches_candidate_limit_without_mutating_shared_schema(stage,limit):
    before=copy.deepcopy(sourcer.REVIEW_SCHEMA)
    engine,run,call=service({'candidates':[ROW]})
    result=engine.handle({'action':'review','run_id':run,'stage':stage,'page':1,'profiles':[PROFILE]})
    assert result['candidates'][0]['score']==80
    schema=call.call_args.args[3]
    assert schema['properties']['candidates']['maxItems']==limit
    assert 'leave it out of candidates' in call.call_args.args[4]['instruction']
    assert sourcer.REVIEW_SCHEMA==before


@pytest.mark.parametrize('patch',[
    {'evidence':[]}, {'evidence':['SAP']*5}, {'unknowns':None},
    {'unknowns':['Not stated']*7}, {'evidence':['x'*251]},
    {'unknowns':['x'*251]}, {'evidence':[' ']},
    {'score':True}, {'score':101}, {'evidence':['Invented qualification']},
    {'id':'p99'},
])
def test_bad_paid_output_has_specific_guidance_and_is_never_replayed(patch):
    engine,run,call=service({'candidates':[{**ROW,**patch}]})
    with pytest.raises(sourcer.SourcerError) as caught:
        engine.handle({'action':'review','run_id':run,'stage':'detail','page':1,'profiles':[PROFILE]})
    error=caught.value
    assert getattr(error,'code',None)=='AI_PROVIDER_RESPONSE_INVALID'
    assert getattr(error,'action',None)=='review_sourcer_results'
    assert error.accounting['paid_ai_failure'] is True
    assert error.accounting['usage']['api_calls']==1
    assert engine.run.calls==1 and engine.run.tokens==48
    call.assert_called_once()


def test_complete_boundary_output_and_empty_unknowns_remain_valid():
    evidence='A'*250
    profile={**PROFILE,'text':evidence}
    row={**ROW,'score':100,'evidence':[evidence]*4,'unknowns':['Unknown']*6}
    assert sourcer.validate_reviews({'candidates':[row]},[profile],5)[0]['score']==100
    assert sourcer.validate_reviews({'candidates':[{**ROW,'unknowns':[]}]},[PROFILE],5)
    assert sourcer.validate_reviews({'candidates':[]},[PROFILE],5)==[]


@pytest.fixture
def module(tmp_path):
    if 'app' not in sys.modules:
        os.environ.update(LOCALAPPDATA=str(tmp_path),APPDATA=str(tmp_path),
            CVSTUDIO_STATE_DIR=str(tmp_path/'state'),CVSTUDIO_DB_PATH=str(tmp_path/'db.sqlite3'),
            CVSTUDIO_JOB_STATE_PATH=str(tmp_path/'jobs.json'),SALARY_COMPARISON_DATA_DIR=str(tmp_path/'salary'))
        from owner_build_tools.build_protected import write_test_receipt
        write_test_receipt(Path(__file__).resolve().parents[1],
                           environment={'HOME':str(tmp_path),'LOCALAPPDATA':str(tmp_path)})
    import app
    return app


def test_response_validation_error_does_not_suggest_replacing_a_working_key(module,monkeypatch):
    engine,run,call=service({'candidates':[{**ROW,'unknowns':None}]})
    monkeypatch.setattr(module,'_LINKEDIN_SOURCER',engine)
    client=module.app.test_client()
    client.set_cookie(module._AI_SPEND_SESSION_COOKIE,module._AI_SPEND_SESSION_TOKEN)
    result=client.post('/linkedin-sourcer',json={'action':'review','run_id':run,
        'stage':'detail','page':1,'profiles':[PROFILE]},headers={
            'X-CV-Studio-Request':'1','X-CV-Studio-Request-ID':'synthetic-assessment-request'})
    assert result.status_code==400
    assert result.json['code']=='AI_PROVIDER_RESPONSE_INVALID'
    assert result.json['action']=='review_sourcer_results'
    assert result.json['retryable'] is False
    assert result.json['request_id']=='synthetic-assessment-request'
    assert result.json['usage']['api_calls']==1
    call.assert_called_once()


def test_actual_authentication_guidance_is_unchanged(module,monkeypatch):
    engine,run,call=service({'candidates':[ROW]})
    call.side_effect=sourcer.SourcerError('DeepSeek API key is invalid')
    monkeypatch.setattr(module,'_LINKEDIN_SOURCER',engine)
    client=module.app.test_client()
    client.set_cookie(module._AI_SPEND_SESSION_COOKIE,module._AI_SPEND_SESSION_TOKEN)
    result=client.post('/linkedin-sourcer',json={'action':'review','run_id':run,
        'stage':'detail','page':1,'profiles':[PROFILE]},headers={'X-CV-Studio-Request':'1'})
    assert result.json['code']=='AI_PROVIDER_AUTH_REQUIRED'
    assert result.json['action']=='open_ai_settings'
    call.assert_called_once()
