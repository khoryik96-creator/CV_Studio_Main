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
