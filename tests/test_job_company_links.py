"""Company-page evidence survives local storage, edits and public ad parsing."""
import pytest
from cvstudio_job_leads import JobLeadsStore,JobLeadsError,company_url
from cvstudio_job_ads import parse_public_job
from test_job_ads import POSTING,URL,html

PAGE='https://www.linkedin.com/company/example/'
RECORD={'url':URL,'company':'Example Company','role':'Finance Manager','company_url':PAGE,'notes':'Keep my notes'}

@pytest.mark.parametrize('value',[PAGE,PAGE+'?trk=jobs','https://sg.linkedin.com/company/example/about/'])
def test_company_pages_normalize_to_the_employer_root(value):
    assert company_url(value)==PAGE

@pytest.mark.parametrize('value',['https://example.invalid/company/example/','javascript:alert(1)','https://www.linkedin.com.evil.invalid/company/example/','https://www.linkedin.com/search/results/companies/?keywords=example','https://www.linkedin.com@evil.invalid/company/example/'])
def test_unsafe_non_company_links_are_never_persisted(tmp_path,value):
    assert not company_url(value)
    store=JobLeadsStore(tmp_path/'leads.sqlite3')
    with pytest.raises(JobLeadsError):store.save({**RECORD,'company_url':value})
    assert store.list()==[]

def test_link_survives_reopen_backup_restore_and_same_employer_edit(tmp_path):
    store=JobLeadsStore(tmp_path/'leads.sqlite3');saved=store.save(RECORD)['record']
    edited=store.save({'id':saved['id'],'revision':saved['revision'],'url':URL,'company':'Example Company','role':'Updated role','notes':'Updated notes'})['record']
    assert edited['company_url']==PAGE and edited['notes']=='Updated notes'
    assert JobLeadsStore(store.path).list()[0]['company_url']==PAGE
    restored=JobLeadsStore(tmp_path/'restored.sqlite3');restored.restore(store.backup())
    assert restored.list()[0]['company_url']==PAGE
    changed=store.save({'id':edited['id'],'revision':edited['revision'],'url':URL,'company':'Different Employer','role':'Updated role'})['record']
    assert not changed.get('company_url'),'an employer edit must not retain the previous employer link'


def test_public_reader_uses_linkedin_organization_url_and_ignores_external_website():
    post={**POSTING,'hiringOrganization':{'name':'Example Company','sameAs':PAGE+'?trk=jobs','url':'https://example.invalid'}}
    assert parse_public_job(html(post),URL)['company_url']==PAGE
    post['hiringOrganization']={'name':'Example Company','url':'https://example.invalid'}
    assert not parse_public_job(html(post),URL).get('company_url')


def test_public_reader_matches_header_employer_and_ignores_recommended_company():
    markup=b'<div class="top-card-layout"><a class="topcard__org-name-link" href="/company/example/?trk=jobs">Example Company</a></div><aside><a href="https://www.linkedin.com/company/unrelated/">Example Company</a></aside>'
    assert parse_public_job(html().replace(b'</body>',markup+b'</body>'),URL)['company_url']==PAGE
    conflicting={**POSTING,'hiringOrganization':{'name':'Example Company','sameAs':'https://www.linkedin.com/company/conflicting/'}}
    assert not parse_public_job(html(conflicting).replace(b'</body>',markup+b'</body>'),URL).get('company_url')
