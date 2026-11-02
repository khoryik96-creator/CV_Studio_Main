import copy
import json
from io import BytesIO
from types import SimpleNamespace
import pytest
from unittest import mock
from openpyxl import load_workbook
from cvstudio_people import (SourcerCandidates,PeopleError,hr_people,filter_candidates,
    filter_people,workbook,CANDIDATE_FIELDS,employment_label)
from cvstudio_job_leads import JobLeadsStore,JobLeadsError
from test_job_leads_hr import AD,SEARCH


@pytest.fixture
def archive():
    data={}
    def save(value):
        data.clear();data.update(copy.deepcopy(value))
    store=SourcerCandidates(load=lambda:copy.deepcopy(data),save=save)
    return store,data


def candidate(**patch):
    return dict(name='Example Person',url='https://www.linkedin.com/in/example',title='SAP Consultant',
        location='Malaysia',score=87,evidence=['SAP Consultant'],unknowns=['Years not shown'],**patch)


def test_candidate_archive_persists_search_and_notes(archive):
    store,data=archive;run=SimpleNamespace(id='a'*32,brief='SAP consultant in Malaysia')
    store.remember(run,[candidate()], 'screen');row=store.list()[0]
    saved=store.note(row['key'],row['revision'],'=literal note')
    store.remember(run,[candidate()], 'detail');row=store.list()[0]
    assert row['notes']=='=literal note' and row['read']=='Profile detail'
    assert row['revision']==saved['revision']+1
    store.remember(run,[candidate()], 'screen')
    assert store.list()[0]['read']=='Profile detail'
    run.id='b'*32;store.remember(run,[candidate()], 'screen')
    assert len(store.list())==2
    assert len(filter_candidates(store.list(),'SAP',run.id))==1
    assert len(SourcerCandidates(load=lambda:copy.deepcopy(data),save=lambda _:None).list())==2
    with pytest.raises(PeopleError,match='changed'):store.note(row['key'],1,'stale')


def test_archive_failures_preserve_existing_data(archive):
    store,data=archive;run=SimpleNamespace(id='a'*32,brief='SAP')
    store.remember(run,[candidate()], 'screen');old=copy.deepcopy(data)
    store.MAX_ROWS=1;run.id='b'*32
    with pytest.raises(PeopleError,match='full'):store.remember(run,[candidate()],'detail')
    assert data==old
    run.brief='bad\x00brief'
    with pytest.raises(PeopleError,match='unsupported'):store.remember(run,[candidate()],'screen')
    assert data==old
    broken=SourcerCandidates(load=lambda:{'version':7},save=lambda _:pytest.fail('must not overwrite corruption'))
    with pytest.raises(PeopleError,match='read securely'):broken.remember(run,[candidate()],'screen')


def test_exports_are_literal_and_filter_matches(archive):
    store,_=archive;run=SimpleNamespace(id='a'*32,brief='=SUM(1)')
    store.remember(run,[candidate()],'screen');row=store.list()[0]
    store.note(row['key'],row['revision'],'@literal')
    rows=filter_candidates(store.list(),'@literal')
    book=load_workbook(BytesIO(workbook(rows,CANDIDATE_FIELDS,'Candidates')))
    sheet=book.active
    assert sheet.freeze_panes=='B2' and sheet.max_row==2
    assert all(cell.data_type!='f' for row in sheet for cell in row)
    assert sheet['I2'].value=='@literal'
    sanitized=load_workbook(BytesIO(workbook([{'notes':'text\x01with\nline'}],{'notes':'Notes'},'Candidates'))).active
    assert sanitized['A2'].value=='textwith\nline'


def test_hr_projection_excludes_trash_and_deduplicates(tmp_path):
    store=JobLeadsStore(tmp_path/'leads.sqlite3')
    row=store.save(AD)['record'];row=store.save_hr(row['id'],row['revision'],SEARCH)['record']
    duplicate={**copy.deepcopy(row),'id':'b'*32,'url':'https://www.linkedin.com/jobs/view/12345'}
    trash={**copy.deepcopy(row),'id':'c'*32,'deleted':True}
    people=hr_people([row,duplicate,trash])
    assert len(people)==1 and people[0]['ads']==2
    assert people[0]['id']==row['id'] and people[0]['revision']==row['revision']
    assert len(filter_people(people,'Example',people[0]['company_id']))==1
    assert not filter_people(people,'missing')
    result=hr_people([row,duplicate],lambda r,p:{'state':'found','email':'person@example.test'} if r['id']==duplicate['id'] else None)[0]
    assert result['email_id']==duplicate['id'] and result['email_result']['state']=='found'


def test_date_update_is_atomic_and_preserves_scan_metadata(tmp_path):
    store=JobLeadsStore(tmp_path/'leads.sqlite3');row=store.save(AD)['record']
    row=store.save_hr(row['id'],row['revision'],SEARCH)['record'];hr=copy.deepcopy(row['hr']);url=hr['people'][0]['url']
    data=store.save_hr(row['id'],row['revision'],None,person_url=url,dates={'joined':'2026-10','left':'','current':True})['record']
    assert employment_label(data['hr']['people'][0])=='Oct 2026 to Present'
    assert data['hr']['people'][0]['employment_status']=='observed'
    assert data['hr']['scanned_at']==hr['scanned_at'] and data['hr']['complete']==hr['complete']
    with pytest.raises(JobLeadsError):store.save_hr(row['id'],row['revision'],None,person_url=url,dates={'joined':'2020','left':'2024','current':False})
    with pytest.raises(JobLeadsError):store.save_hr(data['id'],data['revision'],None,person_url=url,dates={'joined':'2026-13','left':'','current':True})
    assert store.hr_record(data['id'],data['revision'])['hr']==data['hr']


@pytest.mark.parametrize('dates,label',[
    ({'joined':'2026-10','left':'','current':True},'Oct 2026 to Present'),
    ({'joined':'2020-06','left':'2024-03','current':False},'Jun 2020 to Mar 2024'),
    ({'joined':'2020'},'2020'), ({'joined':''},'Not checked'),
    ({'joined':'','employment_status':'not_shown'},'Not confirmed')])
def test_date_labels(dates,label):
    assert employment_label(dates)==label


def test_guarded_dashboards_exports_and_new_vault(archive,tmp_path):
    from isolated_app import load_app
    app=load_app()
    from test_apollo_contacts import setup
    store,_=archive;store.remember(SimpleNamespace(id='a'*32,brief='SAP Malaysia'),[candidate()],'screen')
    service,broker,*_=setup();before=len(broker.calls)
    existing=service.rows()[0]
    full={**existing,'url':'https://www.linkedin.com/jobs/view/12345','hr':{**existing['hr'],'country':'Malaysia','scanned_at':'2026-10-29T00:00:00Z'}}
    service.rows=lambda:[full]
    client=app.app.test_client();client.get('/');headers={'X-CV-Studio-Request':'1'}
    from cvstudio_linkedin_sourcer import LinkedInSourcerService
    sourcer=LinkedInSourcerService(key_available=lambda:False,provider_call=lambda *_:pytest.fail('No provider call'),candidates=store)
    with mock.patch.object(app,'_LINKEDIN_SOURCER',sourcer),mock.patch.object(app,'_SOURCER_CANDIDATES',store),mock.patch.object(app,'_APOLLO',service):
        assert client.post('/linkedin-sourcer',json={'action':'candidates'},headers={'Origin':'https://other.test'}).status_code==403
        response=client.post('/linkedin-sourcer',json={'action':'candidates'},headers=headers)
        assert response.status_code==200 and len(response.json['candidates'])==1
        assert client.post('/linkedin-sourcer',json={'action':'export_candidates'},headers=headers).data[:2]==b'PK'
        response=client.post('/apollo',json={'action':'hr_people'},headers=headers)
        assert response.status_code==200 and len(response.json['people'])==1
        assert 'no-store' in response.headers['Cache-Control']
        assert client.post('/apollo',json={'action':'export_people'},headers=headers).data[:2]==b'PK'
    assert len(broker.calls)==before
    paths=(str(tmp_path/'candidates.dpapi'),str(tmp_path/'candidates.enc'))
    with mock.patch.object(app,'_cv_secure_paths',return_value=paths):
        app._cv_secure_save('sourcer_candidates',{'version':1,'rows':{}})
        assert app._cv_secure_load('sourcer_candidates')['version']==1
        from pathlib import Path
        existing=next(p for p in map(Path,paths) if p.exists());assert b'"rows"' not in existing.read_bytes()
        existing.write_bytes(b'corrupt archive')
        with pytest.raises(ValueError):app._cv_secure_load('sourcer_candidates')


def test_paid_success_survives_archive_failure_and_metadata_stays_observed():
    from cvstudio_linkedin_sourcer import LinkedInSourcerService
    archive=SimpleNamespace(remember=mock.Mock(side_effect=PeopleError('Dashboard unavailable')))
    def provider(*_):
        return {'content':[{'type':'tool_use','name':'return_profile_review','input':{'candidates':[{'id':'p0','score':80,'evidence':['SAP Consultant'],'unknowns':[]}]}}]}, {'usage':{'input_tokens':10,'output_tokens':20}}
    service=LinkedInSourcerService(key_available=lambda:True,provider_call=provider,candidates=archive)
    run=service.start({'brief':'SAP Malaysia','mode':'standard','max_pages':1,'max_calls':2,'confirm_paid':True})['run']
    result=service.handle({'action':'review','run_id':run['id'],'stage':'screen','page':1,'profiles':[{'id':'p0','name':'Example','url':'https://www.linkedin.com/in/example','text':'SAP Consultant\nMalaysia','title':'SAP Consultant','location':'Invented'}]})
    assert result['dashboard_warning']=='Dashboard unavailable'
    assert result['usage']['input_tokens']==10 and result['candidates'][0]['title']=='SAP Consultant'
    assert 'location' not in result['candidates'][0]
    assert result['run']['calls']==1


@pytest.mark.parametrize('status,joined',[
    ('not_checked',''),('not_shown',''),('observed','2022-07')])
def test_employment_evidence_status_survives_reopen_and_backup(tmp_path,status,joined):
    store=JobLeadsStore(tmp_path/'leads.sqlite3');row=store.save(AD)['record']
    search=copy.deepcopy(SEARCH);search['people'][0].update(joined=joined,employment_status=status)
    saved=store.save_hr(row['id'],row['revision'],search)['record']
    reopened=JobLeadsStore(tmp_path/'leads.sqlite3').list()[0]
    assert reopened['hr']==saved['hr']
    restored=JobLeadsStore(tmp_path/'restored.sqlite3');restored.restore(store.backup())
    assert restored.list()[0]['hr']==saved['hr']


@pytest.mark.parametrize('status,joined',[
    ('observed',''),('not_checked','2022-07'),('not_shown','2022-07'),
    ('bogus',''),(None,''),([],''),({},''),(True,'')])
def test_bad_employment_status_cannot_overwrite_saved_people(tmp_path,status,joined):
    store=JobLeadsStore(tmp_path/'leads.sqlite3');row=store.save(AD)['record']
    row=store.save_hr(row['id'],row['revision'],SEARCH)['record']
    search=copy.deepcopy(SEARCH);search['people'][0].update(joined=joined,employment_status=status)
    with pytest.raises(JobLeadsError):store.save_hr(row['id'],row['revision'],search)
    assert store.list()[0]==row


def test_refreshed_older_ad_dates_survive_duplicate_projection_and_excel(tmp_path):
    store=JobLeadsStore(tmp_path/'leads.sqlite3')
    with mock.patch('cvstudio_job_leads._now',return_value='2026-10-01T00:00:00Z'):
        old=store.save(AD)['record'];old=store.save_hr(old['id'],old['revision'],SEARCH)['record']
    with mock.patch('cvstudio_job_leads._now',return_value='2026-10-02T00:00:00Z'):
        newer=store.save({**AD,'url':'https://www.linkedin.com/jobs/view/123456'})['record']
        newer=store.save_hr(newer['id'],newer['revision'],SEARCH)['record']
    person=old['hr']['people'][0]
    old=store.save_hr(old['id'],old['revision'],None,person_url=person['url'],dates={'joined':'2022-07','left':'','current':True})['record']
    assert old['hr']['scanned_at']=='2026-10-01T00:00:00Z'
    projected=hr_people(JobLeadsStore(tmp_path/'leads.sqlite3').list())[0]
    assert projected['ads']==2 and projected['id']==newer['id']
    assert projected['employment']=='Jul 2022 to Present'
    assert projected['employment_id']==old['id'] and projected['employment_revision']==old['revision']
    sheet=load_workbook(BytesIO(workbook([projected],{'employment':'Employment'},'People'))).active
    assert sheet['A2'].value=='Jul 2022 to Present'
    newer=store.save_hr(newer['id'],newer['revision'],None,person_url=person['url'],dates={'joined':'2024-03','left':'2026-08','current':False})['record']
    latest=hr_people(store.list())[0]
    assert latest['employment']=='Mar 2024 to Aug 2026' and latest['employment_id']==newer['id']
    restored=JobLeadsStore(tmp_path/'restored.sqlite3');restored.restore(store.backup())
    assert hr_people(restored.list())[0]['employment']==latest['employment']


@pytest.mark.parametrize('stamp',[None,'','not a date','2026-10-29T00:00:00',[],True])
def test_bad_employment_observation_time_is_atomic(tmp_path,stamp):
    store=JobLeadsStore(tmp_path/'leads.sqlite3');row=store.save(AD)['record']
    search=copy.deepcopy(SEARCH);search['people'][0].update(joined='2022-07',employment_checked_at=stamp)
    with pytest.raises(JobLeadsError):store.save_hr(row['id'],row['revision'],search)
    assert store.list()[0]==row


def test_candidate_sort_order_and_filters_match_the_dashboard():
    rows=[{'name':'Bee','location':'','score':70,'read':'Search card','saved_at':'2026-10-03T00:00:00+00:00','run_id':'r','title':'','url':'','evidence':[],'unknowns':[],'notes':'','brief':''},
          {'name':'alpha','location':'Kuala Lumpur','score':90,'read':'Profile detail','saved_at':'2026-10-01T00:00:00+00:00','run_id':'r','title':'','url':'','evidence':[],'unknowns':[],'notes':'','brief':''},
          {'name':'Cee','location':'Singapore','score':70,'read':'Profile detail','saved_at':'2026-10-02T00:00:00+00:00','run_id':'r','title':'','url':'','evidence':[],'unknowns':[],'notes':'','brief':''}]
    names=lambda **view:[row['name'] for row in filter_candidates(rows,**view)]
    assert names()==['Bee','Cee','alpha'], 'default is newest assessed first, as before'
    assert names(sort='saved_at',order='asc')==['alpha','Cee','Bee']
    assert names(sort='score',order='desc')==['alpha','Bee','Cee'], 'equal scores keep archive order'
    assert names(sort='score',order='asc')==['Bee','Cee','alpha']
    assert names(sort='name',order='asc')==['alpha','Bee','Cee'], 'name order ignores letter case'
    assert names(sort='name',order='desc')==['Cee','Bee','alpha']
    assert names(sort='location',order='asc')==['alpha','Cee','Bee'] and names(sort='location',order='desc')==['Cee','alpha','Bee'], 'blank locations always last'
    assert names(min_score=80)==['alpha'] and names(read='Search card')==['Bee'] and names(min_score=71,read='Search card')==[]
    for bad in [dict(min_score=101),dict(min_score='80'),dict(min_score=True),dict(read='Other'),dict(sort='email'),dict(order='up')]:
        with pytest.raises(PeopleError):filter_candidates(rows,**bad)


def test_candidate_export_uses_the_same_sort_and_filters():
    from isolated_app import load_app
    app = load_app()
    rows=[{'name':'Low','score':40,'read':'Search card'},{'name':'High','score':95,'read':'Profile detail'},{'name':'Mid','score':75,'read':'Profile detail'}]
    seen={}
    def capture(found,fields,title):
        seen['names']=[row['name'] for row in found];return b'xlsx'
    with mock.patch.object(app._SOURCER_CANDIDATES,'list',return_value=[{**row,'run_id':'r','location':'','title':'','url':'','evidence':[],'unknowns':[],'notes':'','brief':'','saved_at':'2026-10-01T00:00:00+00:00'} for row in rows]),\
            mock.patch.object(app,'_people_workbook',side_effect=capture):
        browser=app.app.test_client();browser.get('/');headers={'X-CV-Studio-Request':'1'}
        response=browser.post('/linkedin-sourcer',json={'action':'export_candidates','min_score':50,'sort':'score','order':'asc'},headers=headers)
        assert response.status_code==200 and seen['names']==['Mid','High']
        assert browser.post('/linkedin-sourcer',json={'action':'export_candidates','sort':'email'},headers=headers).status_code==400


# The same names, in the same expected order, are checked in
# tests/test_people_candidate_sort_frontend.js so screen and Excel agree.
PARITY_NAMES=['Zara Lim','\u00c9milie Tan','Candidate 10','Candidate 9','adam Ong','  Bee Ng','\u00c5ngstr\u00f6m Lee','   ','\u00c9va Kumar','Eve Tan','Ezra Lim']
PARITY_ASC=['adam Ong','\u00c5ngstr\u00f6m Lee','  Bee Ng','Candidate 9','Candidate 10','\u00c9milie Tan','\u00c9va Kumar','Eve Tan','Ezra Lim','Zara Lim','   ']
PARITY_DESC=['Zara Lim','Ezra Lim','Eve Tan','\u00c9va Kumar','\u00c9milie Tan','Candidate 10','Candidate 9','  Bee Ng','\u00c5ngstr\u00f6m Lee','adam Ong','   ']


def test_candidate_name_order_matches_the_dashboard_rules():
    rows=[{'name':name,'score':50,'read':'Search card','saved_at':'2026-10-01T00:00:00+00:00','run_id':'r','location':'','title':'','url':'','evidence':[],'unknowns':[],'notes':'','brief':''} for name in PARITY_NAMES]
    assert [row['name'] for row in filter_candidates(rows,sort='name',order='asc')]==PARITY_ASC
    assert [row['name'] for row in filter_candidates(rows,sort='name',order='desc')]==PARITY_DESC
    assert [row['name'] for row in filter_candidates([{**rows[0],'score':None},{**rows[1],'score':True}],sort='score')]==['Zara Lim','\u00c9milie Tan'], 'non-numbers are blank, never an error'


def test_candidate_folders_shortlist_and_trash(archive):
    store,data=archive;run=SimpleNamespace(id='a'*32,brief='SAP FICO in Malaysia')
    store.remember(run,[candidate(),{**candidate(),'name':'Second Person','url':'https://www.linkedin.com/in/second'}],'screen')
    now=lambda name:next(row for row in store.list() if row['name']==name)
    pick=lambda *names:[{'key':now(name)['key'],'revision':now(name)['revision']} for name in names]
    first=now('Example Person')
    assert (first['folder'],first['shortlisted'],first['deleted'])==('',False,False)
    assert store.create_folder(' Controlling ')=={'folder':'Controlling'} and store.folders()==['Controlling']
    store.create_folder('Controlling');assert data['folders']==['Controlling'],'creating it again keeps one folder'
    for bad in ['','   ','x'*81,'a\nb','*','!trash',None]:
        with pytest.raises(PeopleError):store.create_folder(bad)
    stale=pick('Example Person')
    assert store.move(pick('Example Person'),'Controlling')=={'changed':1} and now('Example Person')['folder']=='Controlling'
    with pytest.raises(PeopleError,match='changed in another window'):store.move(stale,'')
    with pytest.raises(PeopleError,match='no longer exists'):store.move(pick('Second Person'),'Missing')
    for bad in [[],None,[{'key':'x','revision':1}],[{'key':first['key'],'revision':'1'}],pick('Second Person')*2]:
        with pytest.raises(PeopleError):store.move(bad,'Controlling')
    starred=store.shortlist(first['key'],now('Example Person')['revision'],True)
    assert starred['shortlisted'] is True and starred['revision']==now('Example Person')['revision']
    with pytest.raises(PeopleError):store.shortlist(first['key'],starred['revision'],'yes')
    assert store.trash(pick('Example Person'),True)=={'changed':1}
    row=now('Example Person')
    assert row['deleted'] is True and row['deleted_at'] and row['folder']=='Controlling' and row['shortlisted'] is True,'Trash keeps the folder and shortlist'
    with pytest.raises(PeopleError,match='Restore candidates from Trash'):store.move(pick('Example Person'),'')
    with pytest.raises(PeopleError,match='Restore this candidate'):store.shortlist(row['key'],row['revision'],False)
    with pytest.raises(PeopleError):store.trash(pick('Example Person'),'yes')
    rows=store.list()
    names=lambda **view:sorted(row['name'] for row in filter_candidates(rows,**view))
    assert names()==['Second Person'] and names(folder='!trash')==['Example Person'],'Trash shows only when chosen'
    assert names(folder='Controlling')==[] and names(folder='')==['Second Person']
    store.trash(pick('Example Person'),False);rows=store.list()
    assert now('Example Person')['deleted'] is False and now('Example Person')['deleted_at']==''
    assert names(folder='Controlling')==['Example Person'] and names(shortlisted=True)==['Example Person']
    assert names(folder='*',shortlisted=True)==['Example Person'] and names(folder='',shortlisted=True)==[]
    for bad in [dict(folder='a\nb'),dict(folder=None),dict(shortlisted='yes')]:
        with pytest.raises(PeopleError):filter_candidates(rows,**bad)
    # A note or a new assessment keeps the folders and the organisation.
    store.note(first['key'],now('Example Person')['revision'],'Strong in CO-PA')
    store.remember(run,[candidate()],'detail')
    row=now('Example Person')
    assert (row['folder'],row['shortlisted'],row['deleted'],row['notes'],row['read'])==('Controlling',True,False,'Strong in CO-PA','Profile detail')
    assert data['folders']==['Controlling']
    # Deleting a folder needs every candidate in it, and leaves them Unfiled.
    with pytest.raises(PeopleError,match='changed in another window'):store.delete_folder('Controlling',[])
    assert store.delete_folder('Controlling',pick('Example Person'))=={'changed':1}
    assert store.folders()==[] and now('Example Person')['folder']=='' and now('Example Person')['shortlisted'] is True
    with pytest.raises(PeopleError,match='changed in another window'):store.delete_folder('Controlling',[])
    store.create_folder('Empty');assert store.delete_folder('Empty',[])=={'changed':0},'an empty folder deletes without a selection'


def test_saved_candidates_with_unreadable_organisation_fail_closed(archive):
    store,data=archive;run=SimpleNamespace(id='a'*32,brief='SAP')
    store.remember(run,[candidate()],'screen')
    key=next(iter(data['rows']))
    legacy=copy.deepcopy(data);legacy.pop('folders')
    for name in ['folder','shortlisted','deleted','deleted_at']:
        legacy['rows'][key].pop(name)
    assert SourcerCandidates(load=lambda:copy.deepcopy(legacy),save=lambda _:None).list()[0]['name']=='Example Person','dashboards saved before folders still read'
    for patch in [dict(folders='Controlling'),dict(folders=['A','A']),dict(folders=['']),dict(folders=['a\nb']),dict(folders=[' padded']),dict(folders=['x']*201)]:
        broken={**copy.deepcopy(data),**patch}
        with pytest.raises(PeopleError,match='read securely'):
            SourcerCandidates(load=lambda broken=broken:copy.deepcopy(broken),save=lambda _:pytest.fail('must not overwrite')).list()
    for field,value in [('folder','a\nb'),('folder',' padded'),('folder','*'),('shortlisted','yes'),('deleted',1),('deleted_at',5),('folder',None)]:
        broken=copy.deepcopy(data);broken['rows'][key][field]=value
        with pytest.raises(PeopleError,match='read securely'):
            SourcerCandidates(load=lambda broken=broken:copy.deepcopy(broken),save=lambda _:pytest.fail('must not overwrite')).list()


def test_candidate_organising_actions_and_export_through_the_route():
    from isolated_app import load_app
    app=load_app();data={}
    def save(value):
        data.clear();data.update(copy.deepcopy(value))
    store=SourcerCandidates(load=lambda:copy.deepcopy(data),save=save)
    run=SimpleNamespace(id='c'*32,brief='SAP FICO in Malaysia')
    store.remember(run,[candidate(),{**candidate(),'name':'Second Person','url':'https://www.linkedin.com/in/second'}],'screen')
    seen={}
    def capture(found,fields,title):
        seen.update(names=[row['name'] for row in found],columns=list(fields.values()),rows=found);return b'xlsx'
    with mock.patch.object(app._LINKEDIN_SOURCER,'candidates',store),mock.patch.object(app,'_SOURCER_CANDIDATES',store),\
            mock.patch.object(app,'_people_workbook',side_effect=capture):
        browser=app.app.test_client();browser.get('/');headers={'X-CV-Studio-Request':'1'}
        post=lambda **body:browser.post('/linkedin-sourcer',json=body,headers=headers)
        assert post(action='candidate_folder_create',name='Finance').get_json()=={'folder':'Finance'}
        listed=post(action='candidates').get_json()
        assert listed['folders']==['Finance'] and len(listed['candidates'])==2
        first=next(row for row in listed['candidates'] if row['name']=='Example Person')
        moved=post(action='candidate_move',items=[{'key':first['key'],'revision':first['revision']}],folder='Finance')
        assert moved.status_code==200 and moved.get_json()=={'changed':1}
        stale=post(action='candidate_move',items=[{'key':first['key'],'revision':first['revision']}],folder='')
        assert stale.status_code==400 and 'changed in another window' in stale.get_json()['error']
        current=lambda:next(row for row in post(action='candidates').get_json()['candidates'] if row['name']=='Example Person')
        starred=post(action='candidate_shortlist',key=first['key'],revision=current()['revision'],shortlisted=True).get_json()['candidate']
        assert starred['shortlisted'] is True
        response=post(action='export_candidates',folder='Finance',shortlisted=True)
        assert response.status_code==200 and seen['names']==['Example Person']
        assert seen['columns'][-3:]==['Folder','Shortlisted','In Trash'] and (seen['rows'][0]['folder'],seen['rows'][0]['shortlisted'],seen['rows'][0]['deleted'])==('Finance','Yes','')
        assert post(action='candidate_trash',items=[{'key':first['key'],'revision':current()['revision']}],deleted=True).get_json()=={'changed':1}
        post(action='export_candidates');assert seen['names']==['Second Person'],'the default export leaves Trash out'
        post(action='export_candidates',folder='!trash');assert seen['names']==['Example Person'] and seen['rows'][0]['deleted']=='Yes'
        assert post(action='export_candidates',folder='a\nb').status_code==400
        assert post(action='candidate_folder_delete',name='Finance',items=[{'key':first['key'],'revision':current()['revision']}]).get_json()=={'changed':1}
        assert post(action='candidates').get_json()['folders']==[]


def test_reads_and_writes_measure_the_same_bytes_near_the_limit(archive):
    # The secure loader adds '_storage', which is never saved, so a dashboard
    # written just under the limit must read back.
    store,data=archive;run=SimpleNamespace(id='a'*32,brief='SAP')
    store.remember(run,[candidate()],'screen')
    loaded=SourcerCandidates(load=lambda:{**copy.deepcopy(data),'_storage':'machine_bound_file'},save=lambda value:(data.clear(),data.update(copy.deepcopy(value))))
    loaded.MAX_BYTES=len(json.dumps(data).encode())
    assert loaded.list()[0]['name']=='Example Person','a dashboard exactly at the limit reads'
    row=loaded.list()[0]
    with pytest.raises(PeopleError,match='full'):loaded.note(row['key'],row['revision'],'x'*5)
    assert loaded.list()[0]['notes']=='','a write over the limit is refused and the dashboard still reads'


def test_organised_dashboards_are_version_two_so_older_builds_refuse_them(archive):
    store,data=archive;run=SimpleNamespace(id='a'*32,brief='SAP')
    store.remember(run,[candidate()],'screen')
    assert data['version']==1,'a dashboard nobody organised stays readable by older builds'
    store.create_folder('Finance');assert data['version']==2
    store.delete_folder('Finance',[]);assert data['version']==1
    row=store.list()[0];store.shortlist(row['key'],row['revision'],True);assert data['version']==2
    for version in (0,3,'2',True):
        broken={**copy.deepcopy(data),'version':version}
        with pytest.raises(PeopleError,match='read securely'):
            SourcerCandidates(load=lambda broken=broken:copy.deepcopy(broken),save=lambda _:pytest.fail('must not overwrite')).list()


def test_built_in_names_one_read_and_a_stable_folder_order(archive):
    store,data=archive;run=SimpleNamespace(id='a'*32,brief='SAP')
    store.remember(run,[candidate()],'screen')
    for name in ['Unfiled','trash',' TRASH ','All folders']:
        with pytest.raises(PeopleError,match='built in'):store.create_folder(name)
    for name in ['finance','Finance','FINANCE','Team 01','Team 1','Café','Cafe']:
        store.create_folder(name)
    assert store.folders()==['Cafe','Café','FINANCE','Finance','finance','Team 01','Team 1'],'equal sort keys fall back to the name itself'
    loads=[]
    counted=SourcerCandidates(load=lambda:(loads.append(1),copy.deepcopy(data))[1],save=lambda _:None)
    snapshot=counted.snapshot()
    assert len(loads)==1 and snapshot['folders']==store.folders() and [row['key'] for row in snapshot['candidates']]==[row['key'] for row in store.list()]


def test_non_text_filters_and_actions_are_input_errors():
    for bad in [dict(folder=[]),dict(folder={}),dict(read=[]),dict(sort={}),dict(order=['asc']),dict(folder=None)]:
        with pytest.raises(PeopleError):filter_candidates([],**bad)
    from isolated_app import load_app
    app=load_app();browser=app.app.test_client();browser.get('/');headers={'X-CV-Studio-Request':'1'}
    for body in [{'action':'export_candidates','folder':[]},{'action':'export_candidates','read':{}},{'action':['candidates']},{'action':{'x':1}}]:
        response=browser.post('/linkedin-sourcer',json=body,headers=headers)
        assert response.status_code==400,body
