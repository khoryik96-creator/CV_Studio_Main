"""Job Leads persistence and guarded-route tests; no live browser/provider calls."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from unittest import mock

import pytest

from cvstudio_job_leads import JobLeadsStore, JobLeadsError, clean_record, job_url


RECORD = {"url":"https://www.linkedin.com/jobs/view/1234567890?trackingId=discard",
          "company":"Example Company", "role":"Finance Manager", "contact":"Sample Contact",
          "notes":"Discuss hiring needs", "status":"to_contact", "follow_up":"2026-10-19"}


@pytest.fixture
def store(tmp_path):
    return JobLeadsStore(tmp_path / "job_leads.sqlite3")


@pytest.mark.parametrize("url", ["https://www.linkedin.com/jobs/view/1234567890", "https://www.linkedin.com/jobs/view/finance-manager-1234567890/?trk=x", "https://my.linkedin.com/jobs/view/1234567890", "https://www.linkedin.com/jobs/search/?currentJobId=1234567890", "https://www.linkedin.com/jobs/collections/recommended/?currentJobId=1234567890"])
def test_job_identity_removes_tracking_and_search_aliases(url):
    assert job_url(url) == "https://www.linkedin.com/jobs/view/1234567890"


@pytest.mark.parametrize('suffix', ['?currentJobId=1234567890', '/?keywords=finance&currentJobId=1234567890&eBP=discard'])
def test_modern_job_search_selected_ad_identity(suffix):
    assert job_url('https://www.linkedin.com/jobs/search-results'+suffix) == 'https://www.linkedin.com/jobs/view/1234567890'


@pytest.mark.parametrize('query', ['', '?keywords=finance', '?currentJobId=1&currentJobId=2'])
def test_modern_search_requires_one_selected_job(query):
    assert not job_url('https://www.linkedin.com/jobs/search-results/'+query)


@pytest.mark.parametrize("url", ["javascript:alert(1)", "http://www.linkedin.com/jobs/view/123", "https://www.linkedin.com.attacker.invalid/jobs/view/123", "https://user@www.linkedin.com/jobs/view/123", "https://www.linkedin.com:444/jobs/view/123", "https://www.linkedin.com/in/person", "https://www.linkedin.com/jobs/search/?currentJobId=1&currentJobId=2", "https://www.linkedin.com/jobs/view/no-id", "https://www.linkedin.com/jobs/search/"])
def test_invalid_urls_are_not_saved(url, store):
    assert not job_url(url)
    with pytest.raises(JobLeadsError):
        store.save({**RECORD, "url":url})
    assert store.list() == []


def test_persists_reopens_duplicate_keeps_notes_and_filters_unknown_fields(store):
    saved = store.save({**RECORD, "api_key":"synthetic-secret"})["record"]
    duplicate = JobLeadsStore(store.path).save({**RECORD, "notes":"Would overwrite"})
    assert duplicate["duplicate"] and duplicate["record"] == saved
    assert JobLeadsStore(store.path).list() == [saved]
    assert "api_key" not in saved and "synthetic-secret" not in store.path.read_bytes().decode("latin1")


def test_posted_date_and_description_survive_save_reopen_backup_restore(store,tmp_path):
    content='Responsibilities\nBuild partnerships.\nManage regional reporting.'
    saved=store.save({**RECORD,'date_posted':'2026-10-02','description':content,'description_truncated':True})['record']
    assert JobLeadsStore(store.path).list()==[saved]
    other=JobLeadsStore(tmp_path/'restored.sqlite3')
    other.restore(store.backup())
    record=other.list()[0]
    assert record['date_posted']=='2026-10-02' and record['description']==content and record['description_truncated'] is True


def test_legacy_rows_without_new_fields_keep_defaults_in_current_schema(store):
    saved=store.save(RECORD)['record']
    raw={key:value for key,value in saved.items() if key not in {'date_posted','description_truncated'}}
    with sqlite3.connect(store.path) as connection:
        connection.execute('UPDATE leads SET payload=? WHERE id=?',(json.dumps(raw),saved['id']))
    result=JobLeadsStore(store.path).list()[0]
    assert result['date_posted']=='' and result['description_truncated'] is False
    with sqlite3.connect(store.path) as connection:
        assert connection.execute('PRAGMA user_version').fetchone()[0]==2


@pytest.mark.parametrize('patch',[{'date_posted':'2026-02-30'},{'date_posted':'2 weeks ago'},{'date_posted':'20261002'},{'date_posted':None},{'description_truncated':'false'},{'description_truncated':1}])
def test_invalid_posted_dates_and_excerpt_markers_reject_before_writing(store,patch):
    with pytest.raises(JobLeadsError):store.save({**RECORD,**patch})
    assert not store.path.exists()


def test_revision_conflict_preserves_latest_edit(store):
    original = store.save(RECORD)["record"]
    changed = store.save({**original, "notes":"Changed in another window"})["record"]
    with pytest.raises(JobLeadsError) as error:
        store.save({**original, "notes":"Stale edit"})
    assert error.value.status == 409 and store.list() == [changed]


def test_concurrent_saves_share_one_identity_without_lost_edits(store):
    with ThreadPoolExecutor(max_workers=5) as pool:
        replies = list(pool.map(lambda _:JobLeadsStore(store.path).save(RECORD), range(5)))
    assert sum(not row["duplicate"] for row in replies) == 1
    assert len(store.list()) == 1
    first = store.list()[0]
    def update(note):
        try:
            return JobLeadsStore(store.path).save({**first, "notes":note})
        except JobLeadsError as error:
            return error.status
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(update, ["First update", "Other update"]))
    assert sum(isinstance(value, dict) for value in results) == 1 and 409 in results


def test_backup_restore_insert_only_and_invalid_batch_is_atomic(store, tmp_path):
    original = store.save(RECORD)["record"]
    backup = store.backup()
    other = JobLeadsStore(tmp_path / "other.sqlite3")
    assert other.restore(backup) == {"added":1, "skipped":0}
    assert other.list()[0]["contact"] == RECORD["contact"]
    backup["records"][0]["notes"] = "Old backup notes"
    assert store.restore(backup) == {"added":0, "skipped":1}
    assert store.list() == [original]
    with pytest.raises(JobLeadsError):
        store.restore({**backup, "records":[{**RECORD,"url":"https://www.linkedin.com/jobs/view/2"}, {**RECORD,"follow_up":"2026-02-30"}]})
    assert store.list() == [original]


def test_capacity_failure_rolls_back_single_and_restore_writes(store):
    original = store.save(RECORD)["record"]
    with mock.patch("cvstudio_job_leads.MAX_RECORDS", 1):
        with pytest.raises(JobLeadsError):
            store.save({**RECORD, "url":"https://www.linkedin.com/jobs/view/2"})
        with pytest.raises(JobLeadsError):
            store.restore({"format":"cvstudio-job-leads", "version":1,"records":[{**RECORD, "url":"https://www.linkedin.com/jobs/view/2"}]})
    assert store.list() == [original]


def test_first_schema_change_has_verified_backup_and_failure_does_not_migrate(store):
    with mock.patch.object(store, "_verify", side_effect=JobLeadsError("Controlled backup failure",503)):
        with pytest.raises(JobLeadsError): store.list()
    with sqlite3.connect(store.path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 0
        assert connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == []
    assert store.list() == []
    backups = list((store.path.parent / "job_leads_backups").glob("*.sqlite3"))
    assert backups
    for path in backups:
        with sqlite3.connect(path) as connection:
            assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_unknown_schema_or_corruption_is_not_overwritten(store):
    with sqlite3.connect(store.path) as connection:
        connection.execute("CREATE TABLE existing(value TEXT)")
        connection.execute("INSERT INTO existing VALUES ('keep')")
    with pytest.raises(JobLeadsError): store.list()
    with sqlite3.connect(store.path) as connection:
        assert connection.execute("SELECT value FROM existing").fetchone()[0] == "keep"
    store.path.write_bytes(b"corrupt synthetic contents")
    with pytest.raises(JobLeadsError) as error: store.list()
    assert error.value.status == 503
    assert "synthetic" not in str(error.value) and str(store.path) not in str(error.value)
    assert store.path.read_bytes() == b"corrupt synthetic contents"


@pytest.mark.parametrize("patch", [{"follow_up":"2026-02-30"}, {"follow_up":"20261019"}, {"status":"unknown"}, {"contact":False}, {"notes":"x"*10001}, {"role":""}, {"company":[]}, {"notes":"bad\x00value"}])
def test_invalid_fields_fail_before_write(patch, store):
    with pytest.raises(JobLeadsError): store.save({**RECORD, **patch})
    assert not store.path.exists()


@pytest.fixture
def module(tmp_path):
    if "app" not in sys.modules:
        os.environ.update(LOCALAPPDATA=str(tmp_path), APPDATA=str(tmp_path), CVSTUDIO_STATE_DIR=str(tmp_path/"state"), CVSTUDIO_DB_PATH=str(tmp_path/"main.sqlite3"), CVSTUDIO_JOB_STATE_PATH=str(tmp_path/"jobs.json"), SALARY_COMPARISON_DATA_DIR=str(tmp_path/"salary"))
        from owner_build_tools.build_protected import write_test_receipt
        write_test_receipt(Path(__file__).resolve().parents[1], environment={"HOME":str(tmp_path),"LOCALAPPDATA":str(tmp_path)})
    import app
    with mock.patch.object(app, "_JOB_LEADS", JobLeadsStore(tmp_path/"leads.sqlite3")):
        yield app


def test_existing_119_routes_and_five_guards_remain_exact(module):
    from cvstudio_architecture import _route_contract
    previous = tuple(row for row in _route_contract(module.app) if row["endpoint"] not in {"job_leads", "email_verifier"})
    assert len(previous) == 119
    assert hashlib.sha256(json.dumps(previous,ensure_ascii=True,sort_keys=True,separators=(',',':')).encode()).hexdigest() == "da29d6476a2dc929fc3b4f06faae8bdffc7ce69261f58901b90de46d0b857e31"
    assert [fn.__name__ for fn in module.app.before_request_funcs[None]] == ["_assign_cvstudio_request_id","_reject_declared_oversize_request","_reject_non_local_host_header","_require_ai_spend_browser_session","_reject_cross_site_unsafe_request"]


def test_route_crud_backup_needs_no_ai_and_errors_have_request_id(module):
    client = module.app.test_client()
    headers = {"X-CV-Studio-Request":"1"}
    with mock.patch.object(module._AI_PROVIDER_CLIENT, "request") as provider:
        reply = client.post('/job-leads',json={"action":"save","record":{**RECORD,"company":"示例 Company"}},headers=headers)
        assert reply.status_code == 200 and reply.json['ok']
        assert client.get('/job-leads').json['records'] == [reply.json['record']]
        backup = client.get('/job-leads?action=backup')
        assert 'attachment' in backup.headers['Content-Disposition'] and 'no-store' in backup.headers['Cache-Control']
        assert '示例'.encode('utf-8') in backup.data and b'\\u793a' not in backup.data
        assert client.post('/job-leads',json={"action":"restore","backup":backup.json},headers=headers).json['skipped'] == 1
        bad = client.post('/job-leads',json={"action":"save","record":{}},headers=headers)
        assert bad.status_code == 400 and bad.json['request_id'] and bad.json['code'] == 'JOB_LEADS_INVALID'
        provider.assert_not_called()


def test_route_cross_site_and_oversized_requests_blocked(module):
    client = module.app.test_client()
    for headers in [{"Origin":"https://attacker.invalid"}, {"Origin":"chrome-extension://"+'a'*32}]:
        assert client.post('/job-leads',json={"action":"save","record":RECORD},headers=headers).status_code == 403
    large = client.post('/job-leads',data=b' '*(12*1024*1024+1),content_type='application/json',headers={"X-CV-Studio-Request":"1"})
    assert large.status_code == 413
    assert not module._JOB_LEADS.path.exists()


def test_hr_results_route_keeps_guards_no_paid_call_and_revision_contract(module):
    from test_job_leads_hr import SEARCH
    client = module.app.test_client()
    headers = {'X-CV-Studio-Request':'1'}
    row = client.post('/job-leads',json={'action':'save','record':{**RECORD,'company':'Example Company'}},headers=headers).json['record']
    body = {'action':'save_hr','id':row['id'],'revision':row['revision'],'search':SEARCH}
    with mock.patch.object(module._AI_PROVIDER_CLIENT,'request') as provider:
        assert client.post('/job-leads',json=body,headers={'Origin':'https://attacker.invalid'}).status_code == 403
        saved = client.post('/job-leads',json=body,headers=headers)
        assert saved.status_code == 200 and saved.json['record']['hr']['country'] == 'Malaysia'
        assert 'no-store' in saved.headers['Cache-Control']
        conflict = client.post('/job-leads',json=body,headers=headers)
        assert conflict.status_code == 409 and conflict.json['request_id']
        assert client.get('/job-leads').json['records'][0]['notes'] == RECORD['notes']
        provider.assert_not_called()


def test_route_storage_failure_visible_without_private_path(module):
    module._JOB_LEADS.path.write_bytes(b'corrupt')
    reply = module.app.test_client().get('/job-leads')
    assert reply.status_code == 503 and reply.json['request_id']
    assert reply.json['code'] == 'JOB_LEADS_CORRUPT' and reply.json['retryable'] is False
    assert reply.json['action'] == 'restore_job_leads_backup'
    assert str(module._JOB_LEADS.path) not in reply.text


def test_public_lookup_uses_no_ai_credentials_or_durable_write(module):
    result={'url':RECORD['url'].split('?')[0],'company':'Example Company','role':'Finance Manager','location':'Penang','description':'Public description'}
    with mock.patch.object(module._PUBLIC_JOB_ADS,'read',return_value=result) as read, mock.patch.object(module._AI_PROVIDER_CLIENT,'request') as provider:
        reply=module.app.test_client().post('/job-leads',json={'action':'lookup','url':result['url']},headers={'X-CV-Studio-Request':'1'})
    assert reply.status_code==200 and reply.json['record']==result
    read.assert_called_once_with(result['url']);provider.assert_not_called()
    assert not module._JOB_LEADS.path.exists()


def test_rich_format_and_trash_routes_preserve_guards_and_use_no_ai(module):
    client = module.app.test_client()
    headers = {'X-CV-Studio-Request':'1'}
    with mock.patch.object(module._AI_PROVIDER_CLIENT,'request') as provider:
        result = client.post('/job-leads',json={'action':'format_content','description':'Build partnerships.','description_html':'<p>Build <b>partnerships.</b></p><script>bad()</script>'},headers=headers)
        assert result.status_code == 200 and result.json['description_rich'][0]['tag']=='p'
        assert not module._JOB_LEADS.path.exists()
        row = client.post('/job-leads',json={'action':'save','record':RECORD},headers=headers).json['record']
        assert client.post('/job-leads',json={'action':'trash','records':[row]},headers={'Origin':'https://attacker.invalid'}).status_code == 403
        reply = client.post('/job-leads',json={'action':'trash','records':[row]},headers=headers)
        assert reply.status_code == 200 and reply.json['changed'] == 1
        row = client.get('/job-leads').json['records'][0]
        assert row['deleted']
        assert client.post('/job-leads',json={'action':'untrash','records':[row]},headers=headers).status_code == 200
        provider.assert_not_called()


def test_folder_routes_preserve_guards_data_and_insert_only_backups(module):
    client = module.app.test_client()
    headers = {'X-CV-Studio-Request':'1'}
    with mock.patch.object(module._AI_PROVIDER_CLIENT,'request') as provider:
        assert client.post('/job-leads',json={'action':'create_folder','folder':'Finance'},headers={'Origin':'https://attacker.invalid'}).status_code == 403
        assert client.post('/job-leads',json={'action':'create_folder','folder':'Finance'},headers=headers).status_code == 200
        assert client.get('/job-leads').json['folders'] == ['Finance']
        row = client.post('/job-leads',json={'action':'save','record':RECORD},headers=headers).json['record']
        assert client.post('/job-leads',json={'action':'move_folder','folder':'Finance','records':[row]},headers=headers).status_code == 200
        snapshot = client.get('/job-leads').json
        assert snapshot['records'][0]['folder'] == 'Finance'
        stale = client.post('/job-leads',json={'action':'delete_folder','folder':'Finance','records':[row]},headers=headers)
        assert stale.status_code == 409 and stale.json['request_id']
        assert client.post('/job-leads',json={'action':'delete_folder','folder':'Finance','records':snapshot['records']},headers=headers).status_code == 200
        data = client.get('/job-leads').json
        assert data['folders'] == [] and len(data['records']) == 1 and data['records'][0]['notes'] == row['notes']
        assert not data['records'][0]['deleted'] and data['records'][0]['folder'] == ''
        provider.assert_not_called()
