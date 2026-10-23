"""Public page extraction, request bounds and redirect restrictions; no network."""
import json
from unittest import mock

import pytest
import requests

from cvstudio_job_ads import PublicLinkedInJobs, parse_public_job, MAX_HTML_BYTES, _without_credentials
from cvstudio_job_leads import JobLeadsError

URL = 'https://www.linkedin.com/jobs/view/1234567890'
POSTING = {'@type':'JobPosting', 'identifier':{'@type':'PropertyValue','value':'1234567890'},
           'datePosted':'2026-10-02T23:30:00-04:00',
           'title':'Senior Finance Consultant', 'hiringOrganization':{'name':'Example Company'},
           'jobLocation':{'address':{'addressLocality':'Kuala Lumpur','addressCountry':{'name':'Malaysia'}}},
           'description':'<p>Build partnerships.</p><ul><li>Manage reporting.</li></ul>'}


def html(posting=POSTING, canonical=URL):
    return ('<html><head><link rel="canonical" href="'+canonical+'"><script type="application/ld+json">'+json.dumps(posting).replace('<','\\u003c')+'</script></head><body><h1>Unrelated search header</h1><aside>Recommended company</aside></body></html>').encode()


class Reply:
    def __init__(self, body=None, status=200, headers=None):
        self.body = html() if body is None else body
        self.status_code = status
        self.headers = {'Content-Type':'text/html; charset=utf-8', **(headers or {})}
        self.closed = False
    def __enter__(self): return self
    def __exit__(self, *args): self.closed=True
    def iter_content(self, chunk_size):
        for offset in range(0,len(self.body),chunk_size): yield self.body[offset:offset+chunk_size]


def test_structured_job_fields_are_grounded_and_contacts_are_never_filled():
    value = parse_public_job(html(),URL)
    assert value['company']=='Example Company' and value['role']=='Senior Finance Consultant'
    assert value['location']=='Kuala Lumpur, Malaysia'
    assert value['description']=='Build partnerships.\nManage reporting.'
    assert value['date_posted']=='2026-10-02'
    assert set(value)=={'url','company','role','location','date_posted','description','description_rich','description_truncated'}
    assert value['description_rich'][1]['tag'] == 'ul'


def test_public_metadata_can_retain_matching_richer_visible_description():
    posting = {**POSTING, 'description':'Build partnerships. Manage reporting.'}
    body = html(posting).replace(b'</body>', b'<div class="description__text"><p><strong>Build partnerships.</strong></p><ol><li>Manage reporting.</li></ol></div></body>')
    value = parse_public_job(body, URL)
    assert value['description'] == posting['description']
    assert value['description_rich'][0]['children'][0]['tag'] == 'strong'
    assert value['description_rich'][1]['tag'] == 'ol'
    mismatch = parse_public_job(body.replace(b'<strong>Build partnerships.</strong>', b'<strong>Different duties.</strong>'), URL)
    assert not any(node.get('tag') == 'ol' for node in mismatch['description_rich'])
    assert mismatch['description'] == value['description']
    oversized = body.replace(b'class="description__text"', b'class="description__text" data-layout="'+b'x'*80000+b'"')
    assert parse_public_job(oversized, URL)['description'] == value['description'], 'oversized optional DOM markup cannot break otherwise valid metadata'


@pytest.mark.parametrize('value,expected', [
    ('2026-10-02','2026-10-02'), ('2026-10-02T00:15:00+08:00','2026-10-02'),
    ('2026-10-02T23:30:00-04:00','2026-10-02'), ('2026-10-02T12:30:00.123Z','2026-10-02'),
    ('2024-02-29','2024-02-29'), ('2026-02-29',''), ('2026-02-30',''),
    ('2026-10-02T25:00:00Z',''), ('2 weeks ago',''), ('20261002',''),
    (None,''), (1234,''), (['2026-10-02'],''), ('','')])
def test_posting_date_preserves_source_calendar_without_guessing(value,expected):
    assert parse_public_job(html({**POSTING,'datePosted':value}),URL)['date_posted']==expected


def test_graph_and_recommendations_choose_only_the_requested_job():
    result=parse_public_job(html({'@graph':[{**POSTING,'identifier':{'value':'999'},'title':'Wrong role'},POSTING]}),URL)
    assert result['role']==POSTING['title']


@pytest.mark.parametrize('posting,canonical', [
    ({**POSTING,'identifier':{'value':'999'}},URL),
    (POSTING,'https://www.linkedin.com/jobs/view/999'),
    ({**POSTING,'url':'https://www.linkedin.com/jobs/view/999'},URL),
    ({'@graph':[POSTING,{**POSTING,'title':'Conflicting role'}]},URL),
    ({**POSTING,'hiringOrganization':[]},URL),
    ({**POSTING,'title':None},URL),
])
def test_mismatched_or_ambiguous_metadata_is_not_guessed(posting,canonical):
    with pytest.raises(JobLeadsError):parse_public_job(html(posting,canonical),URL)


def test_canonical_topcard_fallback_excludes_search_and_recommendations():
    body=f'<link rel="canonical" href="{URL}"><h1>Wrong search heading</h1><section class="top-card-layout"><h1 class="top-card-layout__title">Correct Role</h1><a class="topcard__org-name-link">Correct Company</a><span class="topcard__flavor--bullet">Penang</span><time itemprop="datePosted" datetime="2026-10-02"></time></section><div class="description__text">Correct description</div>'
    value=parse_public_job(body.encode(),URL)
    assert (value['role'],value['company'],value['location'])==('Correct Role','Correct Company','Penang')
    assert value['date_posted']=='2026-10-02'
    assert parse_public_job(body.replace('datetime="2026-10-02"','datetime="2 weeks ago"').encode(),URL)['date_posted']==''
    with pytest.raises(JobLeadsError):parse_public_job(body.replace('rel="canonical"','rel="alternate"').encode(),URL)


def test_scripts_html_and_long_descriptions_are_bounded_plain_text():
    value=parse_public_job(html({**POSTING,'title':'<b>Finance</b> <script>ignore()</script>', 'description':'<p>'+'中'*21000+'</p><script>evil()</script>'}),URL)
    assert value['role']=='Finance' and value['description_truncated']
    assert value['description']=='中'*20000
    with pytest.raises(JobLeadsError):parse_public_job(b' '*(MAX_HTML_BYTES+1),URL)
    with pytest.raises(JobLeadsError):parse_public_job(b'<main>Unknown layout</main>',URL)
    with pytest.raises(JobLeadsError):parse_public_job(html()+b'<iframe src="captcha"></iframe>',URL)


def test_redirect_is_same_job_only_and_no_credentials_or_tracking_forwarded():
    redirect=Reply(status=301,headers={'Location':'https://my.linkedin.com/jobs/view/senior-finance-at-example-1234567890?trk=discard'})
    final=Reply()
    get=mock.Mock(side_effect=[redirect,final])
    result=PublicLinkedInJobs(get=get).read(URL+'?trackingId=discard')
    assert result['role']==POSTING['title'] and get.call_count==2
    assert get.call_args_list[0].args[0]==URL
    assert get.call_args_list[1].args[0]=='https://my.linkedin.com/jobs/view/senior-finance-at-example-1234567890'
    for call in get.call_args_list:
        assert call.kwargs['allow_redirects'] is False and call.kwargs['stream'] is True
        assert set(call.kwargs['headers'])=={'Accept'} and call.kwargs['auth'] is _without_credentials
    assert redirect.closed and final.closed


@pytest.mark.parametrize('target', ['https://attacker.invalid/jobs/view/1234567890', 'http://www.linkedin.com/jobs/view/1234567890','https://user@www.linkedin.com/jobs/view/1234567890','https://www.linkedin.com:444/jobs/view/1234567890','https://www.linkedin.com/jobs/view/999','https://www.linkedin.com/login','https://www.linkedin.com/jobs/search/?currentJobId=1234567890'])
def test_unsafe_or_login_redirects_stop_before_following(target):
    get=mock.Mock(return_value=Reply(status=302,headers={'Location':target}))
    with pytest.raises(JobLeadsError):PublicLinkedInJobs(get=get).read(URL)
    assert get.call_count==1


@pytest.mark.parametrize('reply', [Reply(status=403),Reply(status=429),Reply(headers={'Content-Type':'application/octet-stream'}),Reply(headers={'Content-Length':str(MAX_HTML_BYTES+1)}),Reply(body=b' '*(MAX_HTML_BYTES+1))])
def test_access_checks_bad_types_and_size_fail_without_retry(reply):
    get=mock.Mock(return_value=reply)
    with pytest.raises(JobLeadsError):PublicLinkedInJobs(get=get).read(URL)
    assert get.call_count==1 and reply.closed


def test_public_rate_limit_is_distinct_and_never_retried_or_disguised():
    reply = Reply(status=429)
    get = mock.Mock(return_value=reply)
    with pytest.raises(JobLeadsError) as error: PublicLinkedInJobs(get=get).read(URL)
    assert error.value.code == 'JOB_AD_RATE_LIMITED' and error.value.status == 429
    assert 'limiting' in str(error.value) and 'Chrome' in str(error.value)
    assert get.call_count == 1 and reply.closed


def test_time_redirect_and_concurrency_limits_release_after_failure():
    redirect=Reply(status=302,headers={'Location':URL})
    get=mock.Mock(return_value=redirect)
    with pytest.raises(JobLeadsError):PublicLinkedInJobs(get=get).read(URL)
    assert get.call_count==4
    get=mock.Mock(return_value=Reply())
    service=PublicLinkedInJobs(get=get,clock=mock.Mock(side_effect=[0,21]))
    with pytest.raises(JobLeadsError):service.read(URL)
    get.assert_not_called()
    service=PublicLinkedInJobs(get=get)
    assert service.slots.acquire(False) and service.slots.acquire(False)
    with pytest.raises(JobLeadsError) as failure:service.read(URL)
    assert failure.value.code=='JOB_AD_BUSY'
    service.slots.release();service.slots.release()
    assert service.read(URL)['role']==POSTING['title']


def test_invalid_urls_and_network_errors_never_expose_raw_details():
    get=mock.Mock(side_effect=requests.ConnectionError('synthetic-private-key and private/path'))
    service=PublicLinkedInJobs(get=get)
    with pytest.raises(JobLeadsError):service.read('http://127.0.0.1/private')
    get.assert_not_called()
    with pytest.raises(JobLeadsError) as failure:service.read(URL)
    assert 'synthetic-private-key' not in str(failure.value) and 'private/path' not in str(failure.value)


def test_public_auth_callback_disables_netrc_and_removes_auth_and_cookies():
    with mock.patch('requests.sessions.get_netrc_auth',side_effect=AssertionError('Must not read credentials')):
        with requests.Session() as session:
            request=session.prepare_request(requests.Request('GET',URL,auth=_without_credentials,headers={'Authorization':'synthetic-secret','Cookie':'synthetic-cookie'}))
    assert 'Authorization' not in request.headers and 'Cookie' not in request.headers
