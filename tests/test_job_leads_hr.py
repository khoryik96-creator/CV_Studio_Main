"""Company-associated professional search results use the existing local store."""
import copy
import pytest
from cvstudio_job_leads import JobLeadsStore, JobLeadsError


AD = {'url':'https://www.linkedin.com/jobs/view/123', 'company':'Example Company',
      'role':'Engineer', 'notes':'Keep my notes', 'folder':'Priority'}
SEARCH = {'company':'Example Company', 'company_url':'https://www.linkedin.com/company/example/',
          'company_id':'12345', 'country':'Malaysia', 'keywords':'HR, CHRO, talent acquisition',
          'source_url':'https://www.linkedin.com/search/results/people/?currentCompany=%5B%2212345%22%5D&geoUrn=%5B%22106808692%22%5D',
          'complete':True, 'people':[{'name':'Sample Person','title':'HR Business Partner',
          'location':'Malaysia','url':'https://www.linkedin.com/in/sample-person', 'matched':'HR'}]}


def test_verified_linkedin_name_is_separate_from_saved_ad_label(tmp_path):
    store = JobLeadsStore(tmp_path/'leads.sqlite3')
    old = store.save({**AD, 'company':'ABC'})['record']
    saved = store.save_hr(old['id'], old['revision'], {**SEARCH, 'company':'ABC', 'company_name':'ABC Corporate Business Solutions'})['record']
    assert saved['company'] == 'ABC'
    assert saved['notes'] == AD['notes']
    assert saved['hr']['company_name'] == 'ABC Corporate Business Solutions'
    restored = JobLeadsStore(tmp_path/'restored.sqlite3')
    restored.restore(store.backup())
    assert restored.list()[0]['hr'] == saved['hr']


@pytest.mark.parametrize('name', ['', ' ', 'x'*201, None, 'Example\nCompany'])
def test_invalid_verified_company_name_keeps_previous_records(tmp_path, name):
    store = JobLeadsStore(tmp_path/'leads.sqlite3')
    old = store.save(AD)['record']
    with pytest.raises(JobLeadsError):
        store.save_hr(old['id'], old['revision'], {**SEARCH, 'company_name':name})
    assert store.list() == [old]


def test_hr_roundtrip_preserves_ad_and_survives_edits_trash_folders_backup(tmp_path):
    store = JobLeadsStore(tmp_path/'leads.sqlite3')
    old = store.save(AD)['record']
    saved = store.save_hr(old['id'], old['revision'], SEARCH)['record']
    assert saved['hr']['people'][0]['name'] == 'Sample Person'
    assert saved['hr']['scanned_at']
    assert saved['created_at'] == old['created_at']
    assert saved['notes'] == old['notes']
    assert store.list()[0] == saved
    edited = store.save({**saved, 'notes':'New notes', 'hr':{}})['record']
    assert edited['hr'] == saved['hr'], 'ordinary form saves cannot erase newer HR results'
    store.create_folder('HR')
    store.move_to_folder([{'id':edited['id'],'revision':edited['revision']}], 'HR')
    moved = store.list()[0]
    store.set_deleted([{'id':moved['id'],'revision':moved['revision']}], True)
    restored = JobLeadsStore(tmp_path/'restored.sqlite3')
    restored.restore(store.backup())
    assert restored.list()[0]['hr'] == saved['hr']
    assert restored.list()[0]['deleted'] is True


def test_company_edit_invalidates_results_and_late_scan_cannot_overwrite(tmp_path):
    store = JobLeadsStore(tmp_path/'leads.sqlite3')
    old = store.save(AD)['record']
    saved = store.save_hr(old['id'], old['revision'], SEARCH)['record']
    edited = store.save({**saved,'company':'Different Company'})['record']
    assert not edited.get('hr')
    with pytest.raises(JobLeadsError) as conflict:
        store.save_hr(old['id'], old['revision'], SEARCH)
    assert conflict.value.status == 409
    with pytest.raises(JobLeadsError):
        store.save_hr(edited['id'], edited['revision'], SEARCH)
    assert store.list()[0] == edited


@pytest.mark.parametrize('patch', [
    {'company_id':'999'}, {'company':'Different Company'},
    {'company_url':'https://attacker.invalid/company/example/'},
    {'source_url':'https://www.linkedin.com/search/results/people/?currentCompany=%5B%2212345%22,%22999%22%5D'},
    {'country':'Malaysia','source_url':'https://www.linkedin.com/search/results/people/?currentCompany=%5B%2212345%22%5D'},
    {'country':'','source_url':SEARCH['source_url']},
    {'people':[{'name':'X','title':'HR','location':'Malaysia','url':'javascript:alert(1)','matched':'HR'}]},
    {'people':SEARCH['people']*101}, {'complete':'yes'}, {'keywords':'x'*601},
])
def test_invalid_hr_is_atomic(tmp_path, patch):
    store = JobLeadsStore(tmp_path/'leads.sqlite3')
    old = store.save(AD)['record']
    with pytest.raises(JobLeadsError):
        store.save_hr(old['id'], old['revision'], {**copy.deepcopy(SEARCH), **patch})
    assert store.list() == [old]


def test_hr_deduplicates_and_trash_rejects_scan(tmp_path):
    store = JobLeadsStore(tmp_path/'leads.sqlite3')
    old = store.save(AD)['record']
    saved = store.save_hr(old['id'],old['revision'],{**SEARCH,'people':SEARCH['people']*2})['record']
    assert len(saved['hr']['people']) == 1
    store.set_deleted([{'id':saved['id'],'revision':saved['revision']}],True)
    trashed = store.list()[0]
    with pytest.raises(JobLeadsError):
        store.save_hr(trashed['id'],trashed['revision'],SEARCH)
    assert store.list() == [trashed]


def test_hr_capacity_failure_rolls_back_and_does_not_migrate(tmp_path, monkeypatch):
    import sqlite3
    import cvstudio_job_leads
    store = JobLeadsStore(tmp_path/'leads.sqlite3')
    old = store.save(AD)['record']
    monkeypatch.setattr(cvstudio_job_leads,'MAX_BYTES',1)
    with pytest.raises(JobLeadsError):
        store.save_hr(old['id'],old['revision'],SEARCH)
    assert store.list() == [old]
    with sqlite3.connect(store.path) as connection:
        assert connection.execute('PRAGMA user_version').fetchone()[0] == 2


@pytest.mark.parametrize('joined', ['2020-06', '2023', ''])
def test_joining_dates_survive_storage_and_backup_without_inventing_precision(tmp_path, joined):
    store = JobLeadsStore(tmp_path/'leads.sqlite3')
    old = store.save(AD)['record']
    search = copy.deepcopy(SEARCH)
    search['people'][0]['joined'] = joined
    saved = store.save_hr(old['id'], old['revision'], search)['record']
    assert saved['hr']['people'][0]['joined'] == joined
    restored = JobLeadsStore(tmp_path/'restored.sqlite3')
    restored.restore(store.backup())
    assert restored.list()[0]['hr'] == saved['hr']


@pytest.mark.parametrize('joined', ['2024-13', '2024-00', 'June 2024', '2024-02-01', 2024, '<b>2024</b>'])
def test_invalid_joining_dates_cannot_rewrite_saved_evidence(tmp_path, joined):
    store = JobLeadsStore(tmp_path/'leads.sqlite3')
    old = store.save(AD)['record']
    search = copy.deepcopy(SEARCH)
    search['people'][0]['joined'] = joined
    with pytest.raises(JobLeadsError):
        store.save_hr(old['id'], old['revision'], search)
    assert store.list() == [old]


@pytest.mark.parametrize('dates', [
    {'joined':'2026-10','left':'','current':True},
    {'joined':'2020-06','left':'2024-03','current':False},
    {'joined':'2020','left':'2024','current':False},
    {'joined':'','left':'','current':None},
])
def test_employment_ranges_roundtrip_without_schema_migration(tmp_path, dates):
    import sqlite3
    store = JobLeadsStore(tmp_path/'leads.sqlite3')
    old = store.save(AD)['record']
    search = copy.deepcopy(SEARCH)
    search['people'][0].update(dates)
    saved = store.save_hr(old['id'], old['revision'], search)['record']
    assert all(saved['hr']['people'][0][key] == value for key, value in dates.items())
    restored = JobLeadsStore(tmp_path/'restored.sqlite3')
    restored.restore(store.backup())
    assert restored.list()[0]['hr'] == saved['hr']
    with sqlite3.connect(store.path) as connection:
        assert connection.execute('PRAGMA user_version').fetchone()[0] == 2


@pytest.mark.parametrize('dates', [
    {'joined':'2024-01','left':'2023-12','current':False},
    {'joined':'2024','left':'2023','current':False},
    {'joined':'2024','left':'2025','current':True},
    {'joined':'','left':'','current':True},
    {'joined':'2024','left':'','current':False},
    {'joined':'2024','left':'','current':'true'},
    {'joined':'2024','left':'2024-01-01','current':False},
    {'joined':'2024','left':'2025','current':None},
    {'joined':'2024','current':True},
    {'joined':'2024','left':''},
])
def test_invalid_employment_ranges_are_atomic(tmp_path, dates):
    store = JobLeadsStore(tmp_path/'leads.sqlite3')
    old = store.save(AD)['record']
    search = copy.deepcopy(SEARCH)
    search['people'][0].update(dates)
    with pytest.raises(JobLeadsError):
        store.save_hr(old['id'], old['revision'], search)
    assert store.list() == [old]
