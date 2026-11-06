"""Fictional support captures and send boundaries; no real email or screen."""
import base64
from concurrent.futures import ThreadPoolExecutor
import io
import json
import threading
import zipfile

import pytest
from PIL import Image, PngImagePlugin

from cvstudio_diagnostics import redact_support_text
from cvstudio_support import SupportReports, SupportReportError
from test_job_leads_email import email


def setup(sender='reporter@example.test'):
    messages=[];clock=[1000]
    delivery={'connected':True,'can_send':True,'account':{'email':sender}}
    destination=['support@example.test']
    runtime={'version':'v-test','runtime_mode':'source','platform':{'system':'Fictional OS','python':'3.12','private_path':'/home/private-user/doc'},
             'memory':{'total_bytes':1000,'available_bytes':500,'candidate':'not-for-diagnostics'},
             'dependencies':{'node':True,'antiword_health':{'trusted':True,'available':True,'path':'/home/private-user/tools'}},
             'connections':{'jobadder':{'connected':True,'email':'private@example.test','access_token':'private-token'}},
             'candidate_data':'not-for-diagnostics','root':'/home/private-user/app'}
    def send(payload):messages.append(payload);return {'ok':True,'state':'accepted'},200
    service=SupportReports(recipient=lambda:destination[0],version=lambda:'v-test',runtime=lambda:runtime,
        redact=lambda text:redact_support_text(text,()),outlook_info=lambda:delivery,send_email=send,clock=lambda:clock[0])
    return service,messages,clock,delivery,destination


def prepare(service,**extra):
    return service.prepare({'description':'A fictional button does not respond.','title':'Button problem','module':'Job Leads','doctor':'Fictional diagnostics',**extra})


def ticket(preview):return {key:preview[key] for key in ('report_id','preview_token')}


def test_prepare_collects_redacted_doctor_and_allowlisted_runtime_without_sending():
    service,messages,_,_,_=setup()
    key='sk-ant-api03-'+'FAKEVALUE'*10
    preview=prepare(service,doctor='api_key="'+key+'"\nEmail: private@example.test\n/home/private-user/cv.docx',
        recent_issues=[{'module':'Job Leads','code':'JOBADDER_CONTACT_UNCONFIRMED','http_status':201,'result_reason':'missing_contact_id','candidate_data':'not-for-diagnostics'}])
    assert not messages
    assert key not in preview['doctor'] and 'private@example.test' not in preview['doctor'] and '/home/private-user/' not in preview['doctor']
    raw=json.dumps(preview['runtime'])
    assert 'private-token' not in raw and 'candidate_data' not in raw and '/home/' not in raw and 'private@example.test' not in raw
    assert 'JOBADDER_CONTACT_UNCONFIRMED' in preview['doctor']
    assert 'not-for-diagnostics' not in preview['doctor']
    assert preview['delivery']['recipient']=='support@example.test'


def test_screenshot_is_normalized_and_its_metadata_is_not_exported():
    service,messages,_,_,_=setup()
    image=Image.new('RGB',(20,10),'blue');raw=io.BytesIO();metadata=PngImagePlugin.PngInfo();metadata.add_text('private','fictional-private-metadata');image.save(raw,format='PNG',pnginfo=metadata)
    preview=prepare(service,screenshot='data:image/png;base64,'+base64.b64encode(raw.getvalue()).decode())
    content,_=service.download(ticket(preview))
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        assert set(archive.namelist())=={'report.txt','doctor-report.txt','runtime.json','screenshot.jpg'}
        assert b'fictional-private-metadata' not in archive.read('screenshot.jpg')
        screenshot=Image.open(io.BytesIO(archive.read('screenshot.jpg')))
        assert screenshot.format=='JPEG' and screenshot.size==(20,10)
    assert not messages


@pytest.mark.parametrize('screenshot',['data:image/svg+xml;base64,PHN2Zz4=','https://example.test/image.png','data:image/png;base64,bm90LWFuLWltYWdl',{'type':'image/png'}])
def test_bad_screenshots_are_rejected_without_sending(screenshot):
    service,messages,_,_,_=setup()
    with pytest.raises(SupportReportError):prepare(service,screenshot=screenshot)
    assert not messages


def test_preview_proof_and_expiry_cannot_be_bypassed():
    service,messages,clock,_,_=setup();first=prepare(service);second=prepare(service)
    with pytest.raises(SupportReportError):service.send({**ticket(first),'preview_token':second['preview_token'],'confirmed':True})
    with pytest.raises(SupportReportError):service.send({**ticket(first),'confirmed':False})
    clock[0]+=901
    with pytest.raises(SupportReportError):service.send({**ticket(first),'confirmed':True})
    assert not messages


def test_sending_uses_exact_reviewed_packet_and_server_inbox_only_once():
    service,messages,_,_,_=setup();preview=prepare(service)
    result,status=service.send({**ticket(preview),'confirmed':True,'to':'attacker@example.test','description':'Unreviewed replacement'})
    assert status==200 and result['state']=='accepted'
    assert messages[0]['to']==['support@example.test']
    assert messages[0]['sender']=='reporter@example.test'
    assert 'Unreviewed replacement' not in messages[0]['html']
    assert len(messages[0]['attachments'])==2
    assert service.send({**ticket(preview),'confirmed':True})[0]['reused']
    assert len(messages)==1
    assert service.report_status(ticket(preview))['state']=='accepted'


def test_sender_inbox_or_scope_change_prevents_send_until_reviewed_again():
    for kind in ('sender','recipient','scope'):
        service,messages,_,delivery,destination=setup();preview=prepare(service)
        if kind=='sender':delivery['account']['email']='different@example.test'
        elif kind=='recipient':destination[0]='different-support@example.test'
        else:delivery['can_send']=False
        result,status=service.send({**ticket(preview),'confirmed':True})
        assert status in (403,409) and result['retry_safe']
        assert not messages


def test_ambiguous_delivery_or_exception_is_never_replayed():
    for throw in (False,True):
        service,messages,_,_,_=setup();preview=prepare(service)
        def unknown(payload):
            messages.append(payload)
            if throw:raise TimeoutError('fictional')
            return {'state':'unconfirmed','error':'Fictional timeout'},502
        service.send_email=unknown
        assert service.send({**ticket(preview),'confirmed':True})[0]['state']=='unconfirmed'
        assert service.send({**ticket(preview),'confirmed':True})[1]==409
        assert len(messages)==1
        assert service.report_status(ticket(preview))['state']=='unconfirmed'


def test_concurrent_send_and_status_do_not_repeat_email():
    service,messages,_,_,_=setup();preview=prepare(service);entered=threading.Event();release=threading.Event()
    def send(payload):messages.append(payload);entered.set();assert release.wait(5);return {'ok':True,'state':'accepted'},200
    service.send_email=send
    with ThreadPoolExecutor(2) as pool:
        first=pool.submit(service.send,{**ticket(preview),'confirmed':True});assert entered.wait(5)
        assert service.report_status(ticket(preview))['state']=='sending'
        assert service.send({**ticket(preview),'confirmed':True})[1]==409
        release.set();assert first.result()[0]['state']=='accepted'
    assert len(messages)==1


def test_report_storage_is_bounded_and_discard_releases_it():
    service,messages,_,_,_=setup();previews=[prepare(service) for _ in range(service.MAX_REPORTS)]
    with pytest.raises(SupportReportError):prepare(service)
    service.discard(ticket(previews[0]));prepare(service)
    assert len(service.reports)==service.MAX_REPORTS and not messages
    assert previews[1]['preview_token'] not in json.dumps([{key:value for key,value in record.items() if key not in {'files'}} for record in service.reports.values()])


def test_outlook_shared_durable_ledger_and_no_retry_are_used(email):
    _,graph,create=email;outlook=create();service,messages,_,_,_=setup(sender='owner@example.com')
    service.outlook_info=outlook.public_info
    def send(data):
        messages.append(data)
        result=outlook.send_email_message(data)
        return (result if isinstance(result,tuple) else (result,200))
    service.send_email=send
    preview=prepare(service)
    assert service.send({**ticket(preview),'confirmed':True})[0]['state']=='accepted'
    assert graph.request_json.call_count==1
    call=graph.request_json.call_args
    assert call.args==('me/sendMail',) and call.kwargs['safe_to_retry'] is False and call.kwargs['retries']==0
    assert call.kwargs['body']['message']['toRecipients']==[{'emailAddress':{'address':'support@example.test'}}]
    # Even a new Outlook service instance cannot replay this prepared request.
    assert create().send_email_message(messages[0])=={'ok':True,'state':'accepted','reused':True}
    assert graph.request_json.call_count==1
