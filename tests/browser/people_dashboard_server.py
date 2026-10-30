"""Optional native fixture: run in a separate terminal, then people_dashboards.js.
Isolates every data/credential path before importing the app. Fictional Apollo
transport only; never run this inside or against the owner installation.
"""
import os,sys,tempfile,copy,json
from unittest import mock
from pathlib import Path
root=Path(__file__).resolve().parents[2];state=Path(tempfile.mkdtemp(prefix='people521-native-'))
sys.path.insert(0,str(root));sys.path.insert(0,str(root/'tests'))
fixture_port=int(os.environ.get('CVSTUDIO_PEOPLE_FIXTURE_PORT','5096'))
os.environ.update(LOCALAPPDATA=str(state),APPDATA=str(state),CVSTUDIO_STATE_DIR=str(state/'state'),CVSTUDIO_DB_PATH=str(state/'db.sqlite3'),CVSTUDIO_JOB_STATE_PATH=str(state/'jobs.json'),SALARY_COMPARISON_DATA_DIR=str(state/'salary'),CVSTUDIO_OWNER_BUILD_SMOKE='1',CVSTUDIO_OWNER_BUILD_SMOKE_PORT=str(fixture_port))
from owner_build_tools.build_protected import write_test_receipt
write_test_receipt(root,environment={'HOME':str(state),'LOCALAPPDATA':str(state)})
import app
from cvstudio_apollo import ApolloService,ApolloContacts
from test_apollo import Broker
from test_job_leads_hr import AD, SEARCH
search=copy.deepcopy(SEARCH)
search['people'][0].update(joined='2022-07',left='',current=True)
search['people'].append({**search['people'][0],'name':'Fictional Former Person','url':'https://www.linkedin.com/in/fictional-former','joined':'2020-06','left':'2024-03','current':False})
with mock.patch('cvstudio_job_leads._now',return_value='2026-10-01T00:00:00Z'):
    row=app._JOB_LEADS.save(AD)['record'];row=app._JOB_LEADS.save_hr(row['id'],row['revision'],search)['record']
with mock.patch('cvstudio_job_leads._now',return_value='2026-10-02T00:00:00Z'):
    duplicate=app._JOB_LEADS.save({**AD,'url':'https://www.linkedin.com/jobs/view/123456'})['record']
    newer=copy.deepcopy(search);newer['people'][0].update(joined='',left='',current=None)
    duplicate=app._JOB_LEADS.save_hr(duplicate['id'],duplicate['revision'],newer)['record']
vault={}
def save(data):vault.clear();vault.update(copy.deepcopy(data))
contacts=ApolloContacts(load=lambda:app._cv_secure_load('apollo_contacts'),save=lambda d:app._cv_secure_save('apollo_contacts',d))
app._APOLLO=ApolloService(client=Broker(),load=lambda:copy.deepcopy(vault),save=save,contacts=contacts,rows=lambda:app._JOB_LEADS.list())
app._APOLLO.perform('connect');app._APOLLO.perform('poll');app._APOLLO.perform('reveal',row=row,url=row['hr']['people'][0]['url'],confirmed=True)
from types import SimpleNamespace
run=SimpleNamespace(id='c'*32,brief='SAP consultants in Malaysia')
app._SOURCER_CANDIDATES.remember(run,[dict(name='Example Person '+str(i).zfill(2),url='https://www.linkedin.com/in/example-'+str(i),title='SAP Finance Consultant',location='Malaysia',score=90-i%20,evidence=['SAP Finance Consultant','Malaysia'],unknowns=['Years of experience not shown']) for i in range(45)],'screen')
@app.app.route('/__people_dashboard_fixture__')
def fixture_marker():
    return {'fictional_people_fixture':True,'employment_source':row['id'],'latest_source':duplicate['id']}
app.app.run(host='127.0.0.1',port=fixture_port,debug=False,use_reloader=False)
