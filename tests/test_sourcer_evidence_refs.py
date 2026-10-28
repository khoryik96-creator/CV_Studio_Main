import copy
import re
from unittest import mock
import pytest
import cvstudio_linkedin_sourcer as sourcer
from test_sourcer_assessment_output import module

PROFILES=[{'id':'p0','name':'Example One','url':'https://www.linkedin.com/in/example-one',
           'text':'SAP FI/CO — finance transformation. Hands-on configuration and project delivery.'},
          {'id':'p1','name':'Example Two','url':'https://www.linkedin.com/in/example-two',
           'text':'Manufacturing finance. SAP controlling experience.'}]

def setup(change=None):
    requests=[]
    def provider(model,brief,task,schema,data):
        requests.append(copy.deepcopy((schema,data)))
        row={'id':'p0','score':85,'evidence_refs':[data['profiles'][0]['passages'][0]['id']], 'unknowns':[]}
        if change: change(row,data)
        return ({'content':[{'type':'tool_use','name':'return_profile_review','input':{'candidates':[row]}}]},
                {'usage':{'input_tokens':21,'output_tokens':9,'api_calls':1},'cost':0.001,'model':model,'provider':'deepseek'})
    call=mock.Mock(side_effect=provider)
    engine=sourcer.LinkedInSourcerService(key_available=lambda:True,provider_call=call)
    run=engine.handle({'action':'start','brief':'SAP finance specialists','mode':'standard','max_pages':3,'max_calls':10,'confirm_paid':True})['run']['id']
    return engine,run,call,requests

def review(engine,run,profiles=PROFILES):
    return engine.handle({'action':'review','run_id':run,'stage':'screen','page':1,'profiles':profiles})

def test_provider_selects_source_ids_and_app_attaches_original_words():
    engine,run,call,requests=setup();result=review(engine,run)
    assert result['candidates'][0]['evidence']==[PROFILES[0]['text']]
    assert result['candidates'][0]['name']==PROFILES[0]['name']
    assert result['candidates'][0]['url']==PROFILES[0]['url']
    assert 'evidence_refs' not in result['candidates'][0]
    fields=requests[0][0]['properties']['candidates']['items']['properties']
    assert 'evidence_refs' in fields and 'evidence' not in fields
    assert fields['evidence_refs']['minItems']==1 and fields['evidence_refs']['maxItems']==4
    assert requests[0][0]['properties']['candidates']['maxItems']==5
    assert result['run']['calls']==1 and result['run']['tokens']==30
    call.assert_called_once()

def test_passages_cover_bounded_source_in_order_and_have_fresh_namespaced_ids():
    source=('Observed “SAP FI/CO”\u00a0delivery — Unicode and line breaks.\n'*400)[:14000]
    engine,run,call,requests=setup();review(engine,run,[{**PROFILES[0],'text':source}]);review(engine,run,[{**PROFILES[0],'text':source}])
    groups=[request[1]['profiles'][0]['passages'] for request in requests]
    for passages in groups:
        assert 1<=len(passages)<=112
        assert ''.join(''.join(p['text'].split()) for p in passages)==''.join(source.strip().split())
        assert all(0<len(p['text'])<=250 and p['text'] in source for p in passages)
        assert all(re.fullmatch(r'p0:[a-f0-9]{16}:e\d{1,3}',p['id']) for p in passages)
    assert not set(p['id'] for p in groups[0]) & set(p['id'] for p in groups[1])
    assert all('text' not in request[1]['profiles'][0] for request in requests),'source is not duplicated beside passages'
    assert call.call_count==2

@pytest.mark.parametrize('kind',['unknown','cross-profile','stale','mixed','empty','none','too-many','not-text','unknown-profile'])
def test_bad_references_fail_without_paid_replay_or_content_in_error(kind):
    def change(row,data):
        if kind=='unknown':row['evidence_refs']=['p0:'+'0'*16+':e999']
        if kind=='cross-profile':row['evidence_refs']=[data['profiles'][1]['passages'][0]['id']]
        if kind=='stale':row['evidence_refs']=[row['evidence_refs'][0].replace(':e0',':e999')]
        if kind=='mixed':row['evidence']=['Invented qualification']
        if kind=='empty':row['evidence_refs']=[]
        if kind=='none':row['evidence_refs']=None
        if kind=='too-many':row['evidence_refs']*=5
        if kind=='not-text':row['evidence_refs']=[{}]
        if kind=='unknown-profile':row['id']='p99'
    engine,run,call,_=setup(change)
    with pytest.raises(sourcer.SourcerResponseError) as caught:review(engine,run)
    assert caught.value.code=='AI_PROVIDER_RESPONSE_INVALID'
    assert caught.value.accounting['paid_ai_failure'] is True
    assert caught.value.accounting['usage']['api_calls']==1
    assert not any(profile['text'] in str(caught.value) for profile in PROFILES)
    assert engine.run.calls==1
    call.assert_called_once()

def test_legacy_exact_quotes_remain_strict_and_do_not_mutate_input():
    value={'candidates':[{'id':'p0','score':80,'evidence':['SAP FI/CO'],'unknowns':[]}]}
    original=copy.deepcopy(value)
    assert sourcer.validate_reviews(value,PROFILES,5)[0]['evidence']==['SAP FI/CO']
    assert value==original
    with pytest.raises(sourcer.SourcerResponseError):
        sourcer.validate_reviews({'candidates':[{**value['candidates'][0],'evidence':['Invented qualification']}]},PROFILES,5)


def test_a_real_previous_request_reference_cannot_be_reused():
    saved=[]
    def change(row,data):
        if saved: row['evidence_refs']=[saved[0]]
        else: saved.append(row['evidence_refs'][0])
    engine,run,call,_=setup(change);review(engine,run)
    with pytest.raises(sourcer.SourcerResponseError):review(engine,run)
    assert call.call_count==2 and engine.run.calls==2 and engine.run.tokens==60


def test_resolved_passages_still_pass_the_original_source_grounding_check():
    observed,refs=sourcer.review_passages(PROFILES);ref=observed[0]['passages'][0]['id']
    refs['p0'][ref]='Invented qualification'
    raw={'candidates':[{'id':'p0','score':80,'evidence_refs':[ref],'unknowns':[]}]}
    original=copy.deepcopy(raw)
    with pytest.raises(sourcer.SourcerResponseError):sourcer.resolve_review_evidence(raw,PROFILES,5,refs)
    assert raw==original


@pytest.mark.parametrize('source',['x'*14000,'word '*2800,'a\n'*7000])
def test_long_unbroken_or_dense_text_is_not_dropped_or_unbounded(source):
    profiles=sourcer.clean_profiles([{**PROFILES[0],'text':source}])
    observed,_=sourcer.review_passages(profiles);passages=observed[0]['passages']
    assert len(passages)<=112 and all(0<len(p['text'])<=250 for p in passages)
    assert ''.join(''.join(p['text'].split()) for p in passages)==''.join(source.strip().split())


def test_actual_route_resolves_references_without_changing_response_or_spending_fields(module,monkeypatch):
    engine,run,call,_=setup();monkeypatch.setattr(module,'_LINKEDIN_SOURCER',engine)
    client=module.app.test_client();client.set_cookie(module._AI_SPEND_SESSION_COOKIE,module._AI_SPEND_SESSION_TOKEN)
    result=client.post('/linkedin-sourcer',json={'action':'review','run_id':run,'stage':'detail','page':1,'profiles':PROFILES},headers={'X-CV-Studio-Request':'1'})
    assert result.status_code==200 and result.json['candidates'][0]['evidence']==[PROFILES[0]['text']]
    assert result.json['usage']['api_calls']==1 and result.json['cost']==0.001
    assert 'evidence_refs' not in result.json['candidates'][0]
    call.assert_called_once()
