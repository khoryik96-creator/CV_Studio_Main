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
