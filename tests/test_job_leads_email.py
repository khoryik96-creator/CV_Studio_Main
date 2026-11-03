"""Offline sending checks: explicit consent, reviewed sender, durable non-replay."""
from concurrent.futures import ThreadPoolExecutor
import sqlite3
import time
from unittest.mock import Mock

import pytest

from cvstudio_msgraph import OutlookService


@pytest.fixture
def email(tmp_path):
    data = dict(confirmed=True, request_id='job-email:'+'a'*32, sender='owner@example.com',
                to='client@example.com', subject='Hiring', html='<p>Hello</p>')
    graph = Mock()
    graph.request_json.return_value = {}
    def create():
        service = OutlookService(jsonify=lambda value:value, request_json=lambda:data,
            token_response=Mock(), graph_client_factory=lambda **kwargs:graph,
            receipt_path=lambda:str(tmp_path/'receipt.json'), machine_hash=lambda:'fictional-machine',
            signing_key=lambda:b'fictional-key')
        service._store = dict(access_token='fictional-token', expires_at=int(time.time())+3600,
            scope=service._SEND_SCOPE, account=dict(email='owner@example.com'))
        return service
    return data, graph, create


def test_send_requires_confirmation_permission_and_reviewed_sender(email):
    data, graph, create = email
    service=create()
    data['confirmed']=False
    assert service.send_job_leads_email()[1]==400
    data['confirmed']=True;data['sender']='different@example.com'
    assert service.send_job_leads_email()[1]==409
    data['sender']='owner@example.com';service._store['scope']=service._SCOPE
    assert service.send_job_leads_email()[1]==403
    graph.request_json.assert_not_called()


def test_send_uses_pinned_token_no_retries_and_reuses_durable_success(email):
    data, graph, create = email
    assert create().send_job_leads_email()=={'ok':True,'state':'accepted'}
    call=graph.request_json.call_args
    assert call.args==('me/sendMail',)
    assert call.kwargs['access_token']=='fictional-token'
    assert call.kwargs['safe_to_retry'] is False and call.kwargs['retries']==0
    assert call.kwargs['body']['saveToSentItems'] is True
    assert call.kwargs['body']['message']['toRecipients']==[{'emailAddress':{'address':'client@example.com'}}]
    assert create().send_job_leads_email()['reused'] is True
    assert graph.request_json.call_count==1
    data['subject']='Different message'
    assert create().send_job_leads_email()[1]==409
    assert graph.request_json.call_count==1


def test_unknown_send_result_is_never_replayed_even_after_restart(email):
    data, graph, create = email
    graph.request_json.side_effect=TimeoutError('fictional timeout')
    assert create().send_job_leads_email()[0]['state']=='unconfirmed'
    graph.request_json.side_effect=None
    assert create().send_job_leads_email()[1]==409
    assert graph.request_json.call_count==1


def test_concurrent_requests_send_only_once(email):
    data, graph, create = email
    services=[create() for _ in range(4)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda service:service.send_job_leads_email(),services))
    assert graph.request_json.call_count==1


def test_storage_failure_blocks_network(email, monkeypatch):
    data, graph, create = email
    service=create()
    monkeypatch.setattr(sqlite3,'connect',Mock(side_effect=sqlite3.OperationalError('fictional failure')))
    assert service.send_job_leads_email()[1]==503
    graph.request_json.assert_not_called()


def test_send_scope_is_optional_and_survives_protected_storage(email):
    data, graph, create=email
    service=create()
    assert 'Mail.Send' not in service._SCOPE.split()
    assert service._record_for_storage(service._store)['scope']==service._SEND_SCOPE
    service._save_store()
    assert service._load_store()['scope']==service._SEND_SCOPE
    assert service.public_info()['can_send'] is True


@pytest.mark.parametrize('bad', ['','job-email:bad',None])
def test_invalid_send_ids_do_not_reach_outlook(email,bad):
    data,graph,create=email;data['request_id']=bad
    assert create().send_job_leads_email()[1]==400
    graph.request_json.assert_not_called()


def test_job_leads_draft_pins_reviewed_sender_without_send_permission(email):
    data,graph,create=email
    service=create();service._store['scope']=service._SCOPE
    data['sender']='other@example.com'
    assert service.create_draft()[1]==409
    graph.request_json.assert_not_called()
    data['sender']='owner@example.com'
    graph.request_json.return_value={'id':'fictional-draft','webLink':'https://outlook.office.com/mail/draft/fictional'}
    assert service.create_draft()['isDraft'] is True
    assert graph.request_json.call_args.args==('me/messages',)
    assert graph.request_json.call_args.kwargs['access_token']=='fictional-token'
    assert graph.request_json.call_args.kwargs['safe_to_retry'] is False


def test_sending_permission_is_requested_only_when_selected(email):
    data,graph,create=email
    service=create()
    data.clear();data.update(client_id='12345678-1234-1234-1234-123456789abc')
    graph.token_request.return_value={'device_code':'fictional-code'}
    service.device_start()
    assert 'Mail.Send' not in graph.token_request.call_args.args[0]['scope'].split()
    data['enable_send']=True
    service.device_start()
    assert 'Mail.Send' in graph.token_request.call_args.args[0]['scope'].split()


@pytest.mark.parametrize('replace_account', [False, True])
@pytest.mark.parametrize('refresh_fails', [False, True])
def test_late_refresh_cannot_restore_or_corrupt_a_new_connection(email, replace_account, refresh_fails):
    data,graph,create=email;service=create()
    service._store.update(refresh_token='old-refresh',client_id='old-client',expires_at=1)
    replacement=dict(access_token='new-account-token',refresh_token='new-refresh',client_id='new-client',
                     scope=service._SEND_SCOPE,account={'email':'new@example.com'},expires_at=int(time.time())+3600)
    def exchange(*args,**kwargs):
        service.disconnect()
        if replace_account:
            with service._store_lock:
                service._store.update(replacement)
        if refresh_fails:raise TimeoutError('fictional old refresh failure')
        return {'access_token':'refreshed-old-account-token'}
    service._token_response=exchange
    data['sender']='new@example.com' if replace_account else 'owner@example.com'
    result=service.send_job_leads_email()
    assert result[1]==401 and result[0]['retry_safe'] is True
    assert service._store==(replacement if replace_account else {})
    graph.request_json.assert_not_called()


def test_late_account_lookup_cannot_replace_the_reviewed_identity(email):
    data,graph,create=email;service=create()
    def profile(*args,**kwargs):
        service.disconnect()
        service._store.update(access_token='new-token',account={'email':'new@example.com'})
        return {'mail':'old@example.com'}
    graph.request_json.side_effect=profile
    with pytest.raises(PermissionError):service.refresh_account()
    assert service._store['account']['email']=='new@example.com'
    assert graph.request_json.call_args.kwargs['access_token']=='fictional-token'


def test_cancelled_device_login_cannot_restore_disconnected_account(email):
    data,graph,create=email;service=create()
    data.clear();data['login_session_id']='fictional-session'
    service._device_store['fictional-session']=dict(device_code='fictional-code',expires_at=time.time()+60,
        client_id='fictional-client',connection_generation=service._connection_generation)
    def exchange(*args,**kwargs):
        service.disconnect()
        return {'access_token':'late-login-token'}
    service._token_response=exchange
    assert service.device_poll()[1]==409
    assert service._store=={}


def test_preflight_send_failures_are_explicitly_safe_to_retry(email,monkeypatch):
    data,graph,create=email;service=create()
    data['sender']='different@example.com'
    assert service.send_job_leads_email()[0]['retry_safe'] is True
    data['sender']='owner@example.com'
    monkeypatch.setattr(sqlite3,'connect',Mock(side_effect=sqlite3.OperationalError('fictional')))
    assert service.send_job_leads_email()[0]['retry_safe'] is True
    graph.request_json.assert_not_called()


@pytest.mark.parametrize('send_permission',[False,True])
def test_device_login_completes_with_expected_scope_and_sender(email,send_permission):
    data,graph,create=email;service=create()
    data.clear();data.update(client_id='12345678-1234-1234-1234-123456789abc',enable_send=send_permission)
    graph.token_request.return_value={'device_code':'fictional-code'}
    session=service.device_start()
    data.clear();data['login_session_id']=session['login_session_id']
    service._token_response=lambda *args,**kwargs:dict(access_token='new-account-token',expires_in=3600)
    graph.request_json.return_value={'mail':'connected@example.com','id':'fictional-id'}
    result=service.device_poll()
    assert result['connected'] is True
    assert result['account']['email']=='connected@example.com'
    assert result['can_send'] is send_permission
    assert service._connection_generation==1
    assert service._load_store()['scope']==(service._SEND_SCOPE if send_permission else service._SCOPE)


def test_draft_preflight_failures_allow_retry_without_graph_call(email):
    data,graph,create=email;service=create()
    data['sender']='other@example.com'
    result=service.create_draft();assert result[1]==409 and result[0]['retry_safe'] is True
    data['sender']='owner@example.com';service._store.clear()
    result=service.create_draft();assert result[1]==401 and result[0]['retry_safe'] is True
    graph.request_json.assert_not_called()


def test_disconnect_during_login_profile_lookup_is_not_reported_as_connected(email):
    data,graph,create=email;service=create()
    data.clear();data.update(client_id='12345678-1234-1234-1234-123456789abc')
    graph.token_request.return_value={'device_code':'fictional-code'}
    session=service.device_start();data.clear();data['login_session_id']=session['login_session_id']
    service._token_response=lambda *args,**kwargs:dict(access_token='new-token',expires_in=3600)
    def profile(*args,**kwargs):
        service.disconnect()
        return {'mail':'connected@example.com'}
    graph.request_json.side_effect=profile
    assert service.device_poll()[1]==409
    assert service._store=={}


def test_multiple_recipients_cc_bcc_and_attachments_reach_send_and_draft(email):
    data,graph,create=email;service=create()
    data.update(composer_version=2,to='first@example.com; second@example.com',cc=['cc@example.com'],
        bcc='private@example.com',html='<p>Hello <strong>team</strong></p>',
        attachments=[{'name':'brief.txt','contentBytes':'SGVsbG8='}])
    graph.request_json.return_value={'id':'draft-id','webLink':'https://outlook.office.com/mail/draft/test'}
    assert service.create_draft()['isDraft'] is True
    message=graph.request_json.call_args.kwargs['body']
    assert len(message['toRecipients'])==2
    assert message['ccRecipients'][0]['emailAddress']['address']=='cc@example.com'
    assert message['bccRecipients'][0]['emailAddress']['address']=='private@example.com'
    assert message['attachments'][0]['contentBytes']=='SGVsbG8='
    assert '<strong>team</strong>' in message['body']['content']
    assert service.send_job_leads_email()['state']=='accepted'
    assert graph.request_json.call_args.kwargs['body']['message']==message
    data['cc']=['changed@example.com']
    assert service.send_job_leads_email()[1]==409,'CC is part of send identity'
    data['cc']=['cc@example.com'];data['attachments'][0]['contentBytes']='V29ybGQ='
    assert service.send_job_leads_email()[1]==409,'attachment bytes are part of send identity'


@pytest.mark.parametrize('patch',[
    {'to':'bad address'},{'cc':'a@example.com,broken'},{'bcc':['hidden@example.com\r\nBcc: bad@example.com']},
    {'to':[]},{'cc':['x@example.com']*101},{'attachments':[{'name':'../secret','contentBytes':'AA=='}]},
    {'attachments':[{'name':'ok','contentBytes':'not base64'}]},
    {'attachments':[{'name':'ok','contentBytes':'AA=='}]*11},
    {'attachments':[{'name':'big','contentBytes':'A'*3500000}]},
    {'html':'<script>only script</script>'}])
def test_composer_rejects_invalid_recipients_content_and_files_without_network(email,patch):
    data,graph,create=email;service=create();data.update(composer_version=2,**patch)
    assert service.create_draft()[1] in {400,413}
    assert service.send_job_leads_email()[1] in {400,413}
    graph.request_json.assert_not_called()


def test_rich_html_is_sanitized_and_cross_field_duplicates_deliver_once():
    from cvstudio_msgraph import _email_message
    result=_email_message(dict(to=['one@example.com','ONE@example.com'],cc='one@example.com;two@example.com',bcc='two@example.com;three@example.com',subject='Hello',
        html='<p onclick="bad()">Hello <b>bold</b><script>bad()</script><img src="https://tracker.invalid"><a href="javascript:bad()">text</a><a href="https://example.com">link</a></p>'))
    html=result['body']['content']
    assert 'onclick' not in html and 'script' not in html and '<img' not in html and 'javascript:' not in html
    assert '<b>bold</b>' in html and 'href="https://example.com"' in html
    assert [len(result[k]) for k in ['toRecipients','ccRecipients','bccRecipients']]==[1,1,1]


def test_templates_persist_update_delete_and_reject_stale_writes(email):
    data,graph,create=email;service=create()
    data.clear();data.update(name='Introduction',subject='Hiring',html='<p>Hello <b>team</b><script>bad()</script></p>',to='never-saved@example.com',attachments=[{'name':'not-saved'}])
    result=service.email_templates('save');assert result['ok'] is True
    identity=result['id'];template=result['templates'][0]
    assert '<b>team</b>' in template['html'] and 'script' not in template['html']
    assert 'to' not in template and 'attachments' not in template
    assert create().email_templates()['templates']==[template]
    data.update(id=identity,revision=1,subject='Updated')
    assert service.email_templates('save')['templates'][0]['revision']==2
    assert service.email_templates('delete')[1]==409
    data['revision']=2
    assert service.email_templates('delete')['templates']==[]
    assert create().email_templates()['templates']==[]
    graph.request_json.assert_not_called()


def test_draft_fingerprint_covers_cc_bcc_and_attachment_content(email):
    data,graph,create=email;service=create()
    data.update(composer_version=2,cc='cc@example.com')
    graph.request_json.return_value={'id':'draft-id','webLink':'https://outlook.office.com/mail/draft/test'}
    assert service.create_draft()['ok'] is True
    data['bcc']='private@example.com'
    assert service.create_draft()[1]==409
    assert graph.request_json.call_count==1


def test_signature_banner_persists_in_template_and_is_embedded_for_outlook(email):
    import base64,io
    from PIL import Image
    from cvstudio_msgraph import _email_message
    buffer=io.BytesIO();Image.new('RGB',(688,171),'#e6b54f').save(buffer,format='PNG')
    encoded=base64.b64encode(buffer.getvalue()).decode()
    signature='<p>Best regards,</p><p><b><i>Guok</i></b><br><a href="mailto:guok@example.com" style="color:rgb(0, 91, 180);font-size:10pt">guok@example.com</a></p><img width="688" src="data:image/png;base64,'+encoded+'">'
    data,graph,create=email;service=create()
    data.clear();data.update(name='Client introduction',subject='Hiring',html=signature)
    template=service.email_templates('save')['templates'][0]
    assert 'data:image/png;base64,'+encoded in template['html']
    assert 'rgb(0, 91, 180)' in template['html'] and '<i>Guok</i>' in template['html']
    reopened=create().email_templates()['templates'][0]
    message=_email_message(dict(to='client@example.com',subject=reopened['subject'],html=reopened['html']))
    attachment=message['attachments'][0]
    assert attachment['isInline'] is True
    assert attachment['contentBytes']==encoded
    assert 'src="cid:'+attachment['contentId']+'"' in message['body']['content']
    assert 'data:image' not in message['body']['content']
    graph.request_json.assert_not_called()


@pytest.mark.parametrize('source',['data:image/svg+xml;base64,PHN2Zz4=','data:image/png;base64,SGVsbG8='])
def test_invalid_or_active_inline_images_never_reach_outlook(email,source):
    data,graph,create=email;service=create();data.update(composer_version=2,html='<p>Hello</p><img src="'+source+'">')
    assert service.send_job_leads_email()[1]==400
    assert service.create_draft()[1]==400
    graph.request_json.assert_not_called()
