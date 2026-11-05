"""Employer and availability evidence: fictional pages, never live providers."""
from datetime import datetime, timezone
import json
from unittest import mock
import pytest
from cvstudio_lead_evidence import parse_jobstreet,parse_extracted_jobstreet,JobstreetVerifier,fetch_jobstreet

URL='https://sg.jobstreet.com/job/95258471'
POST={'@type':'JobPosting','url':URL,'title':'Software Engineer','hiringOrganization':{'name':'Elitez'},'description':'<p>Build software and maintain systems.</p>','validThrough':'2099-01-01','jobLocation':{'address':{'addressLocality':'Penang Island','addressCountry':'Malaysia'}}}

def html(post=POST,notice=''):
    return '<main><h1>Software Engineer</h1>'+notice+'</main><script type="application/ld+json">'+json.dumps(post)+'</script>'

def test_employer_comes_from_posting_not_location_or_search_title():
    verifier=JobstreetVerifier({},fetch=lambda url:html())
    rows,w=verifier.results([{'url':URL,'title':'Software Engineer | Penang Island | JobStreet','snippet':'Full time developers, RM 6000'}])
    from cvstudio_lead_enrich import _lead_provider_results_to_leads
    out,_=_lead_provider_results_to_leads(rows,['Malaysia'],['JobStreet'],['Software Engineer'],'Software Engineer')
    assert out['companies'][0]['company']=='Elitez'
    assert out['companies'][0]['region']=='Penang Island, Malaysia'
    assert not w

@pytest.mark.parametrize('notice',['<h2>This job is no longer advertised</h2>','<p>This job has expired</p>','<div role="alert">This job is no longer available</div>'])
def test_expired_notice_overrides_retained_description(notice):
    assert parse_jobstreet(html(notice=notice),URL)['state']=='expired'

def test_expired_structured_deadline_is_not_guessed_from_post_age():
    assert parse_jobstreet(html({**POST,'validThrough':'2020-01-01'}),URL)['state']=='expired'
    assert parse_jobstreet(html({**POST,'datePosted':'2020-01-01','validThrough':'2099-01-01'}),URL)['state']=='active'

def test_failed_layout_or_identity_is_not_an_active_ad():
    assert parse_jobstreet('<h1>Just a moment</h1>',URL)['state']=='unverified'
    assert parse_jobstreet(html({**POST,'url':'https://sg.jobstreet.com/job/94790829'}),URL)['state']=='unverified'

def test_expired_unknown_ads_are_dropped_and_cached():
    fetch=mock.Mock(return_value=html(notice='<h2>This job has expired</h2>'))
    verifier=JobstreetVerifier({},fetch=fetch)
    rows,w=verifier.results([{'url':URL},{'url':URL}]);assert not rows and '2' in w
    verifier.leads({'companies':[{'job_url':URL}]});assert fetch.call_count==1

def test_tavily_extract_is_batched_once_and_corrects_explicit_header():
    raw='# Software Engineer\n\nElitez\n\n[View all jobs](https://sg.jobstreet.com/)\n\nPosted 3d ago\n\nQuick apply\n'+('Build systems. '*30)
    extract=mock.Mock(return_value={'results':[{'url':URL,'raw_content':raw}]})
    verifier=JobstreetVerifier({'provider':'tavily','api_key':'fictional'},fetch=lambda url:'',extract=extract)
    rows,_=verifier.results([{'url':URL}]);assert rows[0]['company_name']=='Elitez'
    verifier.results([{'url':URL}]);assert extract.call_count==1
    assert parse_extracted_jobstreet(raw+'\nThis job has expired',URL)['state']=='expired'

def test_unknown_jobstreet_never_survives_final_ai_cleanup():
    verifier=JobstreetVerifier({},fetch=lambda url:'')
    data,w=verifier.leads({'companies':[{'job_url':URL,'company':'Penang Island'}]})
    assert not data['companies']


def test_extract_cannot_revive_a_publicly_expired_ad_in_the_same_batch():
    expired='https://sg.jobstreet.com/job/94790829'
    extract=mock.Mock(return_value={'results':[{'url':expired,'raw_content':html({**POST,'url':expired})}]})
    verifier=JobstreetVerifier({'provider':'tavily','api_key':'fictional'},
        fetch=lambda url:html({**POST,'url':expired},'<h2>This job has expired</h2>') if url==expired else '',extract=extract)
    rows,_=verifier.results([{'url':expired},{'url':URL}])
    assert rows==[]
    assert verifier.cache['94790829']['state']=='expired'


def test_reported_second_ad_is_excluded_when_deadline_has_passed():
    url='https://sg.jobstreet.com/job/94790829'
    verifier=JobstreetVerifier({},fetch=lambda _:html({**POST,'url':url,'validThrough':'2020-01-01'}))
    rows,_=verifier.results([{'url':url}])
    assert rows==[]


def test_direct_transport_is_bounded_and_never_follows_redirects():
    response=mock.Mock(status_code=302,url=URL,headers={'Content-Type':'text/html'})
    with mock.patch('cvstudio_lead_evidence.requests.get',return_value=response) as get:
        assert fetch_jobstreet(URL)==''
    assert get.call_args.kwargs['allow_redirects'] is False
    assert callable(get.call_args.kwargs['auth'])
    response.close.assert_called_once()
    with mock.patch('cvstudio_lead_evidence.requests.get') as get:
        assert fetch_jobstreet('https://evil.invalid/job/95258471')==''
        get.assert_not_called()


def test_direct_transport_rejects_oversize_content_and_closes_response():
    from cvstudio_lead_evidence import MAX_BYTES
    response=mock.Mock(status_code=200,url=URL,headers={'Content-Type':'text/html'})
    response.iter_content.return_value=[b'x'*(MAX_BYTES+1)]
    with mock.patch('cvstudio_lead_evidence.requests.get',return_value=response):assert fetch_jobstreet(URL)==''
    response.close.assert_called_once()


def test_company_entities_and_country_objects_are_decoded():
    data=parse_jobstreet(html({**POST,'hiringOrganization':{'name':'Elitez&#x20;'},'jobLocation':{'address':{'addressLocality':'Penang Island','addressCountry':{'name':'Malaysia'}}}}),URL)
    assert data['company_name']=='Elitez'
    assert data['location']=='Penang Island, Malaysia'


def test_structured_employer_without_post_identity_or_matching_header_is_not_trusted():
    post={k:v for k,v in POST.items() if k!='url'}
    assert parse_jobstreet(html(post),URL)['state']=='unverified'
    assert parse_jobstreet(html({**post,'identifier':{'value':'95258471'}}),URL)['state']=='active'


@pytest.mark.parametrize('alias,detail',[
    ('https://my.jobstreet.com/jobs?jobId=95258471&type=standard','https://my.jobstreet.com/job/95258471'),
    ('https://www.jobstreet.com.ph/jobs?job_id=95258471','https://www.jobstreet.com.ph/job/95258471'),
])
def test_supported_individual_ad_aliases_are_verified_at_the_detail_url(alias,detail):
    fetch=mock.Mock(return_value=html({**POST,'url':detail}))
    verifier=JobstreetVerifier({},fetch=fetch)
    rows,_=verifier.results([{'url':alias}])
    fetch.assert_called_once_with(detail)
    assert rows[0]['company_name']=='Elitez'


@pytest.mark.parametrize('url',[
    'https://my.jobstreet.com/login?jobId=95258471',
    'https://my.jobstreet.com/jobs?jobId=95258471&jobId=94790829',
    'https://my.jobstreet.com/jobs?jobId=not-a-number',
])
def test_non_ad_or_ambiguous_jobstreet_aliases_do_not_authorize_reads(url):
    fetch=mock.Mock();verifier=JobstreetVerifier({},fetch=fetch)
    rows,_=verifier.results([{'url':url}]);assert not rows;fetch.assert_not_called()
