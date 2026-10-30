"""Isolated fictional Job Leads regression server; no real credentials or calls."""
import runpy,copy,sys,os
from pathlib import Path
from unittest import mock
import flask
root=Path(__file__).resolve().parents[2]
os.environ['CVSTUDIO_PEOPLE_FIXTURE_PORT']='5097'
with mock.patch.object(flask.Flask,'run'):
    seed=runpy.run_path(str(root/'tests/browser/people_dashboard_server.py'))
app=seed['app'];store=app._JOB_LEADS
search=copy.deepcopy(seed['search']);search['people']=[]
for i in range(1,4):
    search['people'].append(dict(name='Fictional Queue Person '+str(i),url='https://www.linkedin.com/in/fictional-queue-'+str(i),title='HR Partner',location='Malaysia',matched='HR',joined='',left='',current=None,employment_status='not_checked'))
row=store.save({**seed['AD'],'url':'https://www.linkedin.com/jobs/view/888888','company':'Example Company'})['record']
row=store.save_hr(row['id'],row['revision'],search)['record']
contacts=seed['contacts']
for i,(company,country,status) in enumerate([('123','Malaysia','verified'),('456','Singapore','catch_all')],1):
    source=copy.deepcopy(row);source['company']='Fictional Company '+str(i);source['hr']['company_id']=company;source['hr']['country']=country
    person={**search['people'][0],'name':'Fictional Contact '+str(i),'url':'https://www.linkedin.com/in/fictional-contact-'+str(i)}
    contacts.remember([(source,person,{'state':'found','email':'fictional'+str(i)+'@example.test','email_status':status})])
from cvstudio_jobadder_write import JobAdderContactService
from test_job_leads_jobadder import Client,SCOPE
client=Client();history={}
def before_post():
    client.fail=TimeoutError('Fictional lost response') if sum(kw.get('method')=='POST' for _,kw in client.calls)==1 else None
client.before_post=before_post
def save(value):history.clear();history.update(copy.deepcopy(value))
app._JOB_LEADS_JA=JobAdderContactService(client=lambda:client,account=lambda:{'connected':True,'account_cache_namespace':SCOPE},contact=contacts.get,load=lambda:copy.deepcopy(history),save=save)
app._ja_refresh_access_token=lambda force=False:'fictional-token'
class LocalReadClient:
    def request_json(self,path,**kwargs):
        assert kwargs.get('method','GET')=='GET','Unexpected provider write in fictional preview'
        return 200,{'items':[],'totalCount':0}
    def request_raw(self,*args,**kwargs):raise AssertionError('No external transport in fictional preview')
app._JOBADDER_CLIENT=LocalReadClient()

class Verifier:
    def check(self,*args,**kwargs):return {'status':'catch_all','reason':'Fictional local test result.','mailbox_evidence':'accepted','catch_all':'detected','assessment':{'label':'Use caution'},'attempts':2}
app._EMAIL_VERIFIER=Verifier()
@app.app.route('/__job_leads525_fixture__')
def job_leads525_fixture_marker():return {'fictional_job_leads_fixture':True}
@app.app.after_request
def fictional_banner(response):
    if flask.request.path=='/' and response.mimetype=='text/html':
        response.direct_passthrough=False
        response.set_data(response.get_data().replace(b'<div class="app">',b'<div style="padding:8px;text-align:center;background:#fff2cc;color:#4a3800">Fictional preview - real accounts and data are untouched.</div><div class="app">',1))
    return response
app.app.run(host='127.0.0.1',port=5097,debug=False,use_reloader=False)
