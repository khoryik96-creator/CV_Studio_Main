"""Explicit folder lifecycle and atomic moves; disposable synthetic stores only."""
import json
import sqlite3
from unittest import mock

import pytest

from cvstudio_job_leads import APPLICATION_ID, JobLeadsError, JobLeadsStore, clean_record

AD = {'url':'https://www.linkedin.com/jobs/view/1234567890', 'company':'Example', 'role':'Analyst'}


def test_empty_folder_survives_restart_and_backup(tmp_path):
    store = JobLeadsStore(tmp_path/'leads.sqlite3')
    store.create_folder(' Finance ')
    store.create_folder('Finance')
    assert JobLeadsStore(store.path).snapshot() == {'records':[], 'folders':['Finance']}
    backup = store.backup()
    assert backup['version'] == 2 and backup['folders'] == ['Finance']
    other = JobLeadsStore(tmp_path/'other.sqlite3')
    other.restore(backup)
    assert other.snapshot() == store.snapshot()


def test_select_saved_ads_then_move_preserves_all_other_data(tmp_path):
    store = JobLeadsStore(tmp_path/'leads.sqlite3')
    first = store.save({**AD,'notes':'Keep notes','contact':'Sample contact'})['record']
    second = store.save({**AD,'url':'https://www.linkedin.com/jobs/view/2'})['record']
    store.create_folder('Shortlist')
    store.move_to_folder([first,second], 'Shortlist')
    moved = {row['id']:row for row in JobLeadsStore(store.path).list()}
    assert moved[first['id']]['folder'] == moved[second['id']]['folder'] == 'Shortlist'
    assert moved[first['id']]['notes'] == first['notes']
    assert moved[first['id']]['contact'] == first['contact']
    assert moved[first['id']]['created_at'] == first['created_at']
    assert moved[first['id']]['revision'] == first['revision']+1
    store.move_to_folder([moved[first['id']]], '')
    assert next(row for row in store.list() if row['id']==first['id'])['folder'] == ''


def test_delete_folder_unfiles_active_and_trashed_ads_without_deleting_them(tmp_path):
    store = JobLeadsStore(tmp_path/'leads.sqlite3')
    first = store.save({**AD,'folder':'Finance'})['record']
    second = store.save({**AD,'url':'https://www.linkedin.com/jobs/view/2','folder':'Finance'})['record']
    store.set_deleted([second], True)
    before = store.list()
    store.delete_folder('Finance', before)
    after = store.list()
    assert len(after) == 2 and all(row['folder']=='' for row in after)
    assert sum(row['deleted'] for row in after) == 1
    assert store.snapshot()['folders'] == []
    assert {row['id']:row['created_at'] for row in before} == {row['id']:row['created_at'] for row in after}
    with pytest.raises(JobLeadsError): store.save(first)
    store.create_folder('Empty')
    store.delete_folder('Empty', [])
    assert store.snapshot()['folders'] == []


def test_stale_moves_or_folder_delete_fail_atomically(tmp_path):
    store = JobLeadsStore(tmp_path/'leads.sqlite3')
    a = store.save({**AD,'folder':'Old'})['record']
    b = store.save({**AD,'url':'https://www.linkedin.com/jobs/view/2','folder':'Old'})['record']
    store.create_folder('New')
    store.save({**b,'notes':'Newer edit'})
    before = store.snapshot()
    for action in [lambda:store.move_to_folder([a,b],'New'), lambda:store.delete_folder('Old',[a,b])]:
        with pytest.raises(JobLeadsError) as error: action()
        assert error.value.status == 409 and store.snapshot() == before
    with pytest.raises(JobLeadsError): store.move_to_folder([a], 'Missing')
    store.set_deleted([a], True)
    trashed = next(row for row in store.list() if row['id']==a['id'])
    with pytest.raises(JobLeadsError): store.move_to_folder([trashed], 'New')
    assert next(row for row in store.list() if row['id']==a['id'])['deleted']


@pytest.mark.parametrize('name', ['', '*','!trash','x'*81,'line\nbreak',None])
def test_invalid_folder_creation_never_initializes_store(tmp_path, name):
    store = JobLeadsStore(tmp_path/'leads.sqlite3')
    with pytest.raises(JobLeadsError): store.create_folder(name)
    assert not store.path.exists()


def legacy_store(path):
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE leads (id TEXT PRIMARY KEY, url TEXT NOT NULL UNIQUE, payload TEXT NOT NULL, revision INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)')
        data = clean_record({**AD,'folder':'Legacy'})
        db.execute('INSERT INTO leads VALUES (?,?,?,?,?,?)',('a'*32,data['url'],json.dumps(data),7,'2026-10-01T00:00:00Z','2026-10-02T00:00:00Z'))
        db.execute('PRAGMA user_version=1')
        db.execute('PRAGMA application_id='+str(APPLICATION_ID))


def test_v1_migration_has_verified_backup_and_preserves_exact_leads(tmp_path):
    path = tmp_path/'leads.sqlite3'
    legacy_store(path)
    with sqlite3.connect(path) as db: before = db.execute('SELECT * FROM leads').fetchall()
    store = JobLeadsStore(path)
    assert store.snapshot()['folders'] == ['Legacy']
    assert JobLeadsStore(path).snapshot() == store.snapshot()
    with sqlite3.connect(path) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 2
        assert db.execute('SELECT * FROM leads').fetchall() == before
    backups = list((tmp_path/'job_leads_backups').glob('before-v2-*.sqlite3'))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert db.execute('PRAGMA user_version').fetchone()[0] == 1
        assert db.execute('SELECT * FROM leads').fetchall() == before


def test_migration_failure_keeps_v1_and_can_retry(tmp_path):
    path = tmp_path/'leads.sqlite3'
    legacy_store(path)
    store = JobLeadsStore(path)
    with mock.patch.object(store, '_record', side_effect=JobLeadsError('Controlled invalid row')):
        with pytest.raises(JobLeadsError): store.snapshot()
    with sqlite3.connect(path) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 1
        assert not db.execute("SELECT name FROM sqlite_master WHERE name='folders'").fetchall()
    assert store.snapshot()['folders'] == ['Legacy']


def test_folder_capacity_and_bad_import_roll_back(tmp_path):
    store = JobLeadsStore(tmp_path/'leads.sqlite3')
    store.create_folder('Keep')
    before = store.snapshot()
    with mock.patch('cvstudio_job_leads.MAX_FOLDERS',1):
        with pytest.raises(JobLeadsError): store.create_folder('Overflow')
        with pytest.raises(JobLeadsError): store.save({**AD,'folder':'Overflow'})
    assert store.snapshot() == before
    with pytest.raises(JobLeadsError): store.restore({'format':'cvstudio-job-leads','version':2,'folders':['Good','!trash'],'records':[AD]})
    assert store.snapshot() == before
    assert store.restore({'format':'cvstudio-job-leads','version':1,'records':[{**AD,'folder':'Legacy'}]}) == {'added':1,'skipped':0}
    assert store.snapshot()['folders'] == ['Keep','Legacy']
