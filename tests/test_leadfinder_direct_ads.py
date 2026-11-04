"""Reject search/listing links throughout Lead Finder; fictional results, no network."""
import copy
import pytest
from cvstudio_lead_enrich import (
    _lead_is_direct_job_url, _lead_keep_only_direct_job_leads,
    _lead_provider_results_to_leads, _lead_cleanup_urls_by_selected_sources,
)

SEARCH = 'https://www.google.com/search?q=%22Nov%202026%22%20%22Software%20Engineer%20%28with%20Salaries%29%22%20site%3Amy.jobstreet.com'
AD = 'https://my.jobstreet.com/job/87401944'


def row(url=AD, **changes):
    return {'company':'Fictional Systems', 'matched_role':'Software Engineer',
            'job_portal':'JobStreet', 'country':'Malaysia', 'region':'Malaysia',
            'job_url':url, 'source_url':url, **changes}


@pytest.mark.parametrize('url', [SEARCH, 'https://my.jobstreet.com/software-engineer-jobs',
    'https://www.linkedin.com/jobs/search/?keywords=software',
    'https://www.google.com/search?q=jobid=123', 'https://www.bing.com/jobs/view/123'])
def test_search_and_listing_pages_never_count_as_ads_even_with_structured_flag(url):
    out, _ = _lead_keep_only_direct_job_leads({'companies':[row(url, job_url_quality='structured_google_job')]})
    assert not out['companies']
    assert not _lead_is_direct_job_url(url)


def test_real_ad_survives_and_indirect_source_only_row_does_not():
    out, _ = _lead_keep_only_direct_job_leads({'companies':[
        row(), row('', source_url=SEARCH, job_url_quality='needs_verification'), row(AD+'?tracking=1')
    ]})
    assert len(out['companies']) == 2
    assert all(_lead_is_direct_job_url(c['job_url']) for c in out['companies'])


def test_provider_listing_results_do_not_fill_the_real_ad_cap():
    indirect = {'title':'Software Engineer (with Salaries) - Nov 2026 | JobStreet',
                'url':'https://my.jobstreet.com/software-engineer-jobs',
                'snippet':'Fictional Systems Software Engineer jobs in Malaysia'}
    results = [copy.deepcopy(indirect) for _ in range(8)] + [{
        'title':'Software Engineer - Fictional Systems - JobStreet', 'url':AD,
        'snippet':'Software Engineer at Fictional Systems in Malaysia', 'location':'Malaysia'}]
    out, _ = _lead_provider_results_to_leads(results, ['Malaysia'], ['JobStreet'], ['Software Engineer'], 'Software Engineer', max_n=1)
    assert [c['job_url'] for c in out['companies']] == [AD]


def test_source_cleanup_cannot_leave_generated_google_link_as_a_lead():
    out, _ = _lead_cleanup_urls_by_selected_sources({'companies':[
        row(), row('https://www.linkedin.com/jobs/view/1234567890', job_portal='LinkedIn Jobs')
    ]}, ['JobStreet'])
    assert [c['job_url'] for c in out['companies']] == [AD]


def test_queries_target_individual_linkedin_and_jobstreet_postings():
    from cvstudio_lead_enrich import _lead_search_provider_queries
    queries = _lead_search_provider_queries(['JobStreet','LinkedIn Jobs'], ['Software Engineer'], ['Malaysia'])
    assert len(queries) == 2
    assert 'site:jobstreet.com/job/' in queries[0]
    assert 'site:linkedin.com/jobs/view/' in queries[1]


def test_month_misread_as_employer_does_not_turn_listing_into_google_lead():
    out, _ = _lead_keep_only_direct_job_leads({'companies':[
        row('https://my.jobstreet.com/software-engineer-jobs', company='Nov 2026',
            matched_role='Software Engineer (with Salaries)', job_url_quality='needs_verification')
    ]})
    assert out['companies'] == []


SOURCES = ['JobStreet', 'LinkedIn Jobs', 'Monster/Foundit', 'Indeed', 'Hiredly', 'Other public job portals']


def test_queries_cover_every_selected_source_before_extra_titles_or_regions():
    from cvstudio_lead_enrich import _lead_search_provider_queries
    queries = _lead_search_provider_queries(SOURCES, ['Software Engineer','Backend Engineer','Developer','Programmer'], ['Malaysia','Singapore'], max_queries=6)
    assert len(queries) == 6
    for query, hint in zip(queries, ['jobstreet.com/job/', 'linkedin.com/jobs/view/', 'foundit.my', 'indeed.com', 'hiredly.com', 'jobs']):
        assert hint in query
        assert '"Software Engineer" Malaysia' in query


def test_quick_search_reserves_a_query_for_each_selected_source_even_after_result_threshold():
    from cvstudio_lead_enrich import _lead_search_provider_queries
    from cvstudio_lead_search import LeadSearchOrchestrator
    calls=[]
    def search(key,query,**kwargs):
        calls.append(query)
        return [{'url':f'https://fictional.example/{hash(query)}/{i}', 'title':'Fictional role'} for i in range(5)]
    orch = LeadSearchOrchestrator(
        secret_store=lambda:{}, search_provider_config=lambda raw:{'enabled':True,'provider':'tavily','api_key':'fictional'},
        search_tavily=search, search_serpapi=lambda *a,**k:[], search_provider_queries=_lead_search_provider_queries,
        call_llm=lambda *a,**k:None, provider_info=lambda:{}, call_with_optional_web=lambda *a,**k:None)
    results,warnings=orch.collect_search_provider_results({},SOURCES,['Software Engineer','Backend Engineer'],['Malaysia'],depth='light')
    assert len(calls) == 6  # minimum coverage, not the old five-query cutoff
    assert any('hiredly.com' in query for query in calls)
    assert len(results) == 30
    assert not warnings


def test_quick_search_source_coverage_stays_bounded_at_twelve_queries():
    from cvstudio_lead_enrich import _lead_search_provider_queries
    from cvstudio_lead_search import LeadSearchOrchestrator
    calls=[]
    orch = LeadSearchOrchestrator(
        secret_store=lambda:{}, search_provider_config=lambda raw:{'enabled':True,'provider':'tavily','api_key':'fictional'},
        search_tavily=lambda key,q,**kw:calls.append(q) or [], search_serpapi=lambda *a,**k:[], search_provider_queries=_lead_search_provider_queries,
        call_llm=lambda *a,**k:None, provider_info=lambda:{}, call_with_optional_web=lambda *a,**k:None)
    orch.collect_search_provider_results({},SOURCES+['Glassdoor','JobsDB','MyCareersFuture','Kalibrr','Company career pages'],['Software Engineer'],['Malaysia'],depth='light')
    assert len(calls) == 11
    assert any('kalibrr' in q for q in calls)
    calls.clear()
    orch.collect_search_provider_results({},['portal'+str(i) for i in range(100)],['Software Engineer'],['Malaysia'],depth='light')
    assert len(calls) <= 12


def test_lead_cap_is_balanced_across_qualifying_sources_after_location_filters():
    results = [{'title':'Software Engineer - Fictional Systems - JobStreet','url':f'https://my.jobstreet.com/job/{87401944+i}', 'location':'Malaysia','snippet':'Software Engineer Malaysia'} for i in range(8)]
    other_urls = ['https://www.linkedin.com/jobs/view/1234567890', 'https://www.foundit.my/job/software-engineer-123',
                  'https://my.indeed.com/viewjob?jk=123', 'https://my.hiredly.com/jobs/software-engineer-123',
                  'https://fictional-board.example/jobs/software-engineer-123']
    results += [{'title':'Software Engineer - Fictional Systems','url':url,'location':'Malaysia','snippet':'Software Engineer Malaysia'} for url in other_urls]
    results.insert(0,{'title':'Software Engineer - Fictional Systems','url':'https://my.jobstreet.com/job/9999','location':'Germany','snippet':'Software Engineer Germany'})
    out,_=_lead_provider_results_to_leads(results,['Malaysia'],SOURCES,['Software Engineer'],'Software Engineer',max_n=6)
    assert len(out['companies']) == 6
    assert set(other_urls) <= {c['job_url'] for c in out['companies']}
    assert [c['count'] for c in out['summary']['job_source_counts']] == [1]*6


@pytest.mark.parametrize("depth", ["light", "standard", "deep"])
def test_large_source_coverage_is_bounded_to_three_concurrent_searches(depth):
    import threading
    from cvstudio_lead_enrich import _lead_search_provider_queries
    from cvstudio_lead_search import LeadSearchOrchestrator
    ready=threading.Event(); lock=threading.Lock(); active=0; maximum=0
    def search(*args,**kwargs):
        nonlocal active,maximum
        with lock:
            active+=1; maximum=max(maximum,active)
            if active==3:ready.set()
        try:
            assert ready.wait(5), 'Coverage should run concurrently'
            return []
        finally:
            with lock:active-=1
    orch=LeadSearchOrchestrator(secret_store=lambda:{},search_provider_config=lambda raw:{'enabled':True,'provider':'tavily','api_key':'fictional'},search_tavily=search,search_serpapi=search,search_provider_queries=_lead_search_provider_queries,call_llm=lambda *a,**k:None,provider_info=lambda:{},call_with_optional_web=lambda *a,**k:None)
    _,warnings=orch.collect_search_provider_results({},SOURCES,['Software Engineer'],['Malaysia'],depth=depth)
    assert not warnings
    assert maximum==3


def test_source_counts_do_not_double_count_other_portals_and_company_careers():
    out,_=_lead_provider_results_to_leads([{'title':'Software Engineer - Fictional Systems', 'url':'https://fictional.example/careers/software-engineer', 'snippet':'Software Engineer Malaysia','location':'Malaysia'}], ['Malaysia'], ['Company career pages','Other public job portals'], ['Software Engineer'], 'Software Engineer')
    assert len(out['companies']) == 1
    assert sum(row['count'] for row in out['summary']['job_source_counts']) == 1


@pytest.mark.parametrize('url', [
    'https://www.google.com/about/careers/applications/jobs/results/123456789-software-engineer/',
    'https://google.com/about/careers/applications/jobs/results/123456789',
    'https://careers.google.com/jobs/results/123456789-software-engineer/',
])
def test_google_careers_individual_posts_survive_search_engine_filter(url):
    assert _lead_is_direct_job_url(url)
    out,_=_lead_keep_only_direct_job_leads({'companies':[row(url, company='Google',job_portal='Company Careers')]})
    assert [c['job_url'] for c in out['companies']] == [url]


@pytest.mark.parametrize('url', [
    'https://www.google.com/about/careers/applications/jobs/results/?q=engineer',
    'https://careers.google.com/jobs/results/?q=engineer',
    'https://www.google.com/search?q=jobs&jobid=123456789',
    'https://www.google.com/jobs/view/123456789',
    'https://www.google.com/about/careers/applications/jobs/results/not-an-id/',
])
def test_google_career_listings_and_search_pages_are_not_individual_ads(url):
    assert not _lead_is_direct_job_url(url)
