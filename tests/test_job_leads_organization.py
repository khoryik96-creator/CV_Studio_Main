"""Recoverable local organization and passive rich content; synthetic only."""
import json
import sqlite3
from unittest import mock

import pytest

from cvstudio_job_leads import JobLeadsError, JobLeadsStore, clean_record, format_description, rich_text

RECORD = {'url':'https://www.linkedin.com/jobs/view/1234567890', 'company':'Example Company', 'role':'Finance Manager'}
HTML = '<h2>Responsibilities</h2><p>Build <strong>partnerships</strong>.</p><ul><li>Manage reporting.</li><li><em>Support teams.</em></li></ul>'
PLAIN = 'Responsibilities\nBuild partnerships.\nManage reporting.\nSupport teams.'


def test_source_formatting_retains_headings_bold_and_bullets_without_active_content():
    source = HTML + '<script>steal()</script><button>Show more</button><img src="https://attacker.invalid/pixel" onerror="steal()">'
    nodes = format_description(PLAIN, source)
    assert [node['tag'] for node in nodes] == ['h3','p','ul']
    assert nodes[1]['children'][1] == {'tag':'strong','children':[{'text':'partnerships'}]}
    assert nodes[2]['children'][0]['tag'] == 'li'
    assert 'steal' not in json.dumps(nodes) and 'attacker' not in json.dumps(nodes)
    assert format_description('Manual correction', HTML) == []


@pytest.mark.parametrize('nodes', [
    [{'tag':'script','children':[]}], [{'tag':'p','children':[], 'onclick':'bad()'}],
    [{'text':'x','src':'https://attacker.invalid'}], [{'text':'x'*20001}],
    [{'tag':'p','children':[]}]*4001, {'text':'wrong shape'}, None,
])
def test_rich_payloads_are_bounded_and_reject_attributes_or_active_tags(nodes):
    with pytest.raises(JobLeadsError): clean_record({**RECORD,'description_rich':nodes})


def test_nested_rich_limit_and_literal_text_are_safe():
    node = {'text':'literal <img src=x onerror=bad()> & value'}
    assert rich_text(format_description(node['text'], '<p>literal &lt;img src=x onerror=bad()&gt; &amp; value</p>')) == node['text']
    for _ in range(18): node = {'tag':'p','children':[node]}
    with pytest.raises(JobLeadsError): clean_record({**RECORD,'description_rich':[node]})
    assert format_description('x', '<div>'*30+'x'+'</div>'*30) == []


def test_linkedin_layout_wrappers_do_not_create_nested_paragraphs():
    source = '<div><div><h2>Responsibilities</h2><p>Build <span><b>partnerships</b></span>.</p></div><div><ul><li>Manage reporting.</li><li><em>Support teams.</em></li></ul></div></div>'
    nodes = format_description(PLAIN, source)
    assert nodes == format_description(PLAIN, HTML)
    assert rich_text(nodes).replace(' ', '') == PLAIN.replace(' ', '').replace('\n', '')
    # A nested span cannot close a surrounding paragraph or swallow the next.
    assert format_description('First bold end. Second.', '<div><p>First <span><b>bold</b></span> end.</p><p>Second.</p></div>') == [
        {'tag':'p','children':[{'text':'First '},{'tag':'strong','children':[{'text':'bold'}]},{'text':' end.'}]},
        {'tag':'p','children':[{'text':'Second.'}]},
    ]


def test_folders_rich_content_and_original_creation_survive_backup_restore(tmp_path):
    store = JobLeadsStore(tmp_path/'leads.sqlite3')
    with mock.patch('cvstudio_job_leads._now', return_value='2026-10-02T12:30:00Z'):
        row = store.save({**RECORD,'folder':'Finance','description':PLAIN,'description_rich':format_description(PLAIN,HTML)})['record']
    updated = store.save({**row,'folder':'Priority Finance'})['record']
    assert updated['created_at'] == '2026-10-02T12:30:00Z'
    assert updated['folder'] == 'Priority Finance' and updated['description_rich'][2]['tag'] == 'ul'
    other = JobLeadsStore(tmp_path/'other.sqlite3')
    other.restore(store.backup())
    assert other.list()[0]['created_at'] == row['created_at']
    assert other.list()[0]['description_rich'] == row['description_rich']
    with sqlite3.connect(store.path) as db: assert db.execute('PRAGMA user_version').fetchone()[0] == 2


def test_trash_restore_are_durable_revision_checked_and_never_overwritten_by_backup(tmp_path):
    store = JobLeadsStore(tmp_path/'leads.sqlite3')
    row = store.save({**RECORD,'folder':'Finance'})['record']
    old_backup = store.backup()
    assert store.set_deleted([row], True) == {'changed':1}
    trashed = JobLeadsStore(store.path).list()[0]
    assert trashed['deleted'] and trashed['revision'] == row['revision']+1
    assert trashed['folder'] == 'Finance' and trashed['created_at'] == row['created_at']
    assert store.restore(old_backup) == {'added':0,'skipped':1}
    assert store.list()[0]['deleted']
    assert store.save(RECORD)['duplicate']
    with pytest.raises(JobLeadsError): store.save({**trashed, 'deleted':False})
    with pytest.raises(JobLeadsError): store.set_deleted([row], False)
    assert store.set_deleted([trashed], False) == {'changed':1}
    assert not store.list()[0]['deleted']
    assert store.list()[0]['created_at'] == row['created_at']


def test_clear_is_atomic_when_any_selected_revision_is_stale(tmp_path):
    store = JobLeadsStore(tmp_path/'leads.sqlite3')
    first = store.save(RECORD)['record']
    second = store.save({**RECORD,'url':'https://www.linkedin.com/jobs/view/2'})['record']
    store.save({**second,'notes':'Changed in another tab'})
    with pytest.raises(JobLeadsError) as error: store.set_deleted([first,second], True)
    assert error.value.status == 409 and all(not row['deleted'] for row in store.list())
    assert next(row for row in store.list() if row['id']==first['id'])['revision'] == first['revision']


@pytest.mark.parametrize('patch', [{'folder':'*'}, {'folder':'!trash'}, {'folder':'a\nb'}, {'folder':'x'*81}, {'deleted':'true'}])
def test_invalid_organization_metadata_does_not_write(tmp_path, patch):
    store = JobLeadsStore(tmp_path/'leads.sqlite3')
    with pytest.raises(JobLeadsError): store.save({**RECORD, **patch})
    assert not store.path.exists()


def test_invalid_backup_created_date_is_atomic_and_legacy_backup_still_loads(tmp_path):
    store = JobLeadsStore(tmp_path/'leads.sqlite3')
    backup = {'format':'cvstudio-job-leads','version':1,'records':[RECORD,{**RECORD,'created_at':'yesterday'}]}
    with pytest.raises(JobLeadsError): store.restore(backup)
    assert not store.path.exists()
    backup['records'] = [RECORD]
    store.restore(backup)
    assert store.list()[0]['folder']=='' and not store.list()[0]['deleted']
    assert store.list()[0]['description_rich']==[]


@pytest.mark.parametrize('selection', [[], None, [{'id':'bad','revision':1}], [{'id':'a'*32,'revision':True}], [{'id':'a'*32,'revision':1}]*2])
def test_invalid_clear_selection_fails_before_write(tmp_path, selection):
    store = JobLeadsStore(tmp_path/'leads.sqlite3')
    with pytest.raises(JobLeadsError): store.set_deleted(selection,True)
    assert not store.path.exists()
