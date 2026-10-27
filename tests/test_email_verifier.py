"""Synthetic addresses and protocol fixtures only; no live recipient checks."""
import hashlib
import json
import os
from pathlib import Path
import smtplib
import socket
import socketserver
import ssl
import sys
import threading
import time
from types import SimpleNamespace
from unittest import mock

import pytest

from cvstudio_email_verifier import (EmailVerifier, MailDNS, SMTPProbe, VerifierError,
                                    CheckUnavailable, _DeadlineSMTP, address_parts, public_ip)


@pytest.mark.parametrize('address,expected', [
    ('person@example.test','ok'), ('Name+tag@EXAMPLE.TEST','ok'),
    ('a@bücher.test','ok'), ('a..b@example.test','invalid'),
    ('.a@example.test','invalid'), ('a.@example.test','invalid'),
    ('a@@example.test','invalid'), ('a@example','invalid'),
    ('a@127.0.0.1','invalid'), ('a@bad_domain.test','invalid'),
    ('a\r\nRCPT TO:x@example.test','invalid'), ('a b@example.test','invalid'),
    ('é@example.test','unsupported'), ('"first last"@example.test','unsupported'),
    ('"first,last"@example.test','unsupported'), ('a@[8.8.8.8]','unsupported'),
    ('a'*65+'@example.test','invalid'), ('\ud800@example.test','invalid'),
])
def test_syntax_is_conservative_without_rewriting_local_identity(address,expected):
    assert address_parts(address)[2] == expected
    assert address_parts('Name+tag@EXAMPLE.TEST')[0] == 'Name+tag@example.test'
    assert address_parts('a@bücher.test')[0] == 'a@xn--bcher-kva.test'


@pytest.mark.parametrize('ip', ['127.0.0.1','10.0.0.1','192.168.1.1','169.254.169.254','::1','fc00::1','fe80::1','::ffff:127.0.0.1','224.0.0.1','0.0.0.0','not an IP'])
def test_private_special_and_multicast_targets_never_probed(ip):
    assert not public_ip(ip)
    with mock.patch('cvstudio_email_verifier._DeadlineSMTP') as smtp:
        with pytest.raises(CheckUnavailable):
            SMTPProbe().check('mx.example.test',ip,'person@example.test',time.monotonic()+1)
        smtp.assert_not_called()


def engine(state='mx',addresses=None,verdict='accepted'):
    dns = mock.Mock()
    dns.hosts.return_value=(state, [] if state in {'no_domain','no_mail'} else ['mx.example.test'])
    dns.addresses.return_value=addresses if addresses is not None else ['8.8.8.8']
    probe=mock.Mock()
    probe.check.return_value=(verdict,'Synthetic protocol evidence')
    return EmailVerifier(dns,probe)


@pytest.mark.parametrize('state', ['no_domain','no_mail'])
def test_definite_domain_failures_are_invalid_without_smtp(state):
    service=engine(state)
    assert service.check({'email':'person@example.test'})['status']=='invalid'
    service.probe.check.assert_not_called()


def test_quick_mode_and_flags_do_not_claim_mailbox_validity():
    service=engine()
    result=service.check({'email':'info@mailinator.com','mode':'quick'})
    assert result['status']=='domain_ok' and result['mailbox']=='not_checked'
    assert result['flags']==['Role address','Known disposable domain']
    service.probe.check.assert_not_called()
    result=service.check({'email':'Name@gmial.com','mode':'quick'})
    assert result['suggestion']=='Name@gmail.com' and result['normalized']=='Name@gmial.com'


def test_no_mx_has_implicit_fallback_and_missing_mx_target_is_not_definite_invalid():
    assert engine('implicit').check({'email':'person@example.test'})['status']=='accepted'
    assert engine('implicit',[]).check({'email':'person@example.test'})['status']=='invalid'
    assert engine('mx',[]).check({'email':'person@example.test'})['status']=='unknown'


@pytest.mark.parametrize('mode', ['quick','full'])
@pytest.mark.parametrize('failed_first', [False,True])
def test_one_mx_lookup_failure_does_not_discard_a_usable_server(mode,failed_first):
    service=engine()
    service.dns.hosts.return_value=('mx',['primary.example.test','backup.example.test'])
    failure=CheckUnavailable('The domain\'s DNS could not be read. This does not mean the address is invalid.')
    answers=[failure,['8.8.8.8']] if failed_first else [['8.8.8.8'],failure]
    service.dns.addresses.side_effect=answers
    result=service.check({'email':'person@example.test','mode':mode})
    assert result['status']==('domain_ok' if mode=='quick' else 'accepted')
    assert result['domain']=='mx'
    if mode=='quick': service.probe.check.assert_not_called()
    else:
        host='backup.example.test' if failed_first else 'primary.example.test'
        assert service.probe.check.call_args.args[:3]==(host,'8.8.8.8','person@example.test')


@pytest.mark.parametrize('v4,v6,expected', [
    (['8.8.8.8','8.8.4.4'], ['2001:4860:4860::8888'], ['8.8.8.8','2001:4860:4860::8888']),
    (['8.8.8.8','8.8.4.4'], ['2001:4860:4860::8888','2001:4860:4860::8844'], ['8.8.8.8','2001:4860:4860::8888']),
    (['8.8.8.8'], ['2001:4860:4860::8888'], ['8.8.8.8','2001:4860:4860::8888']),
    (['8.8.8.8','8.8.4.4'], [], ['8.8.8.8','8.8.4.4']),
    ([], ['2001:4860:4860::8888','2001:4860:4860::8844'], ['2001:4860:4860::8888','2001:4860:4860::8844']),
    (['8.8.8.8','8.8.8.8','8.8.4.4'], ['2001:4860:4860::8888'], ['8.8.8.8','2001:4860:4860::8888']),
    (['8.8.8.8'], ['::ffff:8.8.4.4','2001:4860:4860::8888'], ['8.8.8.8','2001:4860:4860::8888']),
])
def test_bounded_mail_addresses_keep_both_advertised_families(v4,v6,expected):
    resolver=MailDNS()
    resolver.query=mock.Mock(side_effect=lambda host,kind,deadline:[SimpleNamespace(address=ip) for ip in (v4 if kind=='A' else v6)])
    assert resolver.addresses('mx.example.test',time.monotonic()+5)==expected
    assert resolver.query.call_count==2


def test_full_mailbox_check_falls_back_to_ipv6_after_ipv4_timeout():
    resolver=MailDNS()
    resolver.hosts=mock.Mock(return_value=('mx',['mx.example.test']))
    resolver.query=mock.Mock(side_effect=lambda host,kind,deadline:[SimpleNamespace(address=ip) for ip in (['8.8.8.8','8.8.4.4'] if kind=='A' else ['2001:4860:4860::8888'])])
    attempted=[]
    def probe(host,ip,address,deadline):
        attempted.append((host,ip,address,deadline))
        return ('unknown','Connection timed out') if ':' not in ip else ('accepted','Synthetic recipient-specific SMTP evidence')
    service=EmailVerifier(resolver,mock.Mock())
    service.probe.check.side_effect=probe
    result=service.check({'email':'person@example.test'})
    assert result['status']=='accepted'
    assert [call[1] for call in attempted]==['8.8.8.8','2001:4860:4860::8888']
    assert attempted[0][3]==attempted[1][3], 'fallback retains the single overall deadline'
    assert service.probe.check.call_count==2


@pytest.mark.parametrize('bad', ['10.0.0.1','::1','fc00::1','::ffff:127.0.0.1','ff02::1'])
def test_address_family_selection_cannot_hide_restricted_answers(bad):
    resolver=MailDNS()
    resolver.query=mock.Mock(side_effect=lambda host,kind,deadline:[SimpleNamespace(address=ip) for ip in (['8.8.8.8','8.8.4.4'] if kind=='A' else ['2001:4860:4860::8888',bad])])
    with pytest.raises(CheckUnavailable): resolver.addresses('mx.example.test',time.monotonic()+5)


def test_all_failed_mx_lookups_stay_unknown_and_release_domain_slots():
    service=engine()
    service.dns.hosts.return_value=('mx',['primary.example.test','backup.example.test'])
    service.dns.addresses.side_effect=CheckUnavailable('DNS temporarily unavailable')
    for _ in range(3):
        result=service.check({'email':'person@example.test'})
        assert result['status']=='unknown' and result['reason']=='DNS temporarily unavailable'
        assert result['mailbox']=='not_checked'
    assert service.dns.addresses.call_count==6
    service.probe.check.assert_not_called()


def test_restricted_mx_is_skipped_without_weakening_the_public_address_guard():
    resolver=MailDNS()
    resolver.hosts=mock.Mock(return_value=('mx',['restricted.example.test','public.example.test']))
    def records(host,kind,deadline):
        return [SimpleNamespace(address='10.0.0.1' if host=='restricted.example.test' else '8.8.8.8')] if kind=='A' else []
    resolver.query=mock.Mock(side_effect=records)
    probe=mock.Mock();probe.check.return_value=('accepted','Synthetic protocol evidence')
    result=EmailVerifier(resolver,probe).check({'email':'person@example.test'})
    assert result['status']=='accepted'
    assert probe.check.call_args.args[:3]==('public.example.test','8.8.8.8','person@example.test')
    assert probe.check.call_count==1


def test_dns_failure_and_unsupported_syntax_are_unknown_and_release_slots():
    service=engine()
    service.dns.hosts.side_effect=CheckUnavailable('DNS temporarily unavailable')
    for _ in range(4):
        assert service.check({'email':'person@example.test'})['status']=='unknown'
    for email in ['"first last"@example.test','é@example.test']:
        assert service.check({'email':email})['status']=='unknown'
    assert service.dns.hosts.call_count==4


def test_busy_and_invalid_payloads_fail_before_network():
    service=engine()
    for payload in [None,[],{'email':False},{'email':'a'*321},{'email':'a@example.test','mode':[]},{'email':'a@example.test','mode':'secret'}]:
        with pytest.raises(VerifierError): service.check(payload)
    service.dns.hosts.assert_not_called()
    service._domains.add('example.test')
    for _ in range(3):
        with pytest.raises(VerifierError) as error: service.check({'email':'a@example.test'})
        assert error.value.status==429
    service._domains.clear()
    assert service.check({'email':'a@example.test'})['status']=='accepted'


def test_resolver_uses_mx_order_null_mx_and_public_pinned_addresses():
    resolver=MailDNS()
    with mock.patch.object(resolver,'query',side_effect=[[SimpleNamespace(preference=0,exchange='.')]]):
        assert resolver.hosts('example.test',0)==('no_mail',[])
    with mock.patch.object(resolver,'query',return_value=[]):
        assert resolver.hosts('example.test',0)==('implicit',['example.test'])
    answer=[SimpleNamespace(preference=20,exchange='backup.example.test.'),SimpleNamespace(preference=0,exchange='mx.example.test.')]
    with mock.patch.object(resolver,'query',return_value=answer):
        assert resolver.hosts('example.test',0)==('mx',['mx.example.test','backup.example.test'])
    with mock.patch.object(resolver,'query',side_effect=[[SimpleNamespace(address='8.8.8.8')],[SimpleNamespace(address='::1')]]):
        with pytest.raises(CheckUnavailable): resolver.addresses('mx.example.test',0)


def test_dns_timeouts_missing_dependency_and_noanswer_are_distinct():
    import dns.exception
    import dns.resolver
    resolver=MailDNS()
    for failure,expected in [(dns.resolver.NXDOMAIN(),None),(dns.resolver.NoAnswer(),[])]:
        with mock.patch.object(resolver.resolver,'resolve',side_effect=failure) as query:
            assert resolver.query('example.test','MX',time.monotonic()+5)==expected
            assert query.call_args.kwargs['search'] is False
    with mock.patch.object(resolver.resolver,'resolve',side_effect=dns.exception.Timeout()):
        with pytest.raises(CheckUnavailable): resolver.query('example.test','MX',time.monotonic()+5)
    resolver.resolver=None
    with pytest.raises(CheckUnavailable): resolver.query('example.test','MX',time.monotonic()+5)


class SMTPFixture:
    def __init__(self,recipient,random=(550,b'5.1.1 User unknown'),mail=(250,b'OK'),tls=False):
        self.recipient,self.random,self.mail_result,self.tls=recipient,random,mail,tls
        self.calls=[]; self.sock=mock.Mock(); self.closed=False
    def connect(self,host,port): self.calls.append(('connect',host,port)); return 220,b'Welcome'
    def ehlo(self): return 250,b'OK'
    def helo(self): return 250,b'OK'
    def has_extn(self,name): return self.tls
    def starttls(self,*,context): self.calls.append(('tls',self._host)); return 220,b'OK'
    def mail(self,address): self.calls.append(('mail',address)); return self.mail_result
    def rcpt(self,address):
        self.calls.append(('rcpt',address))
        if isinstance(self.recipient,Exception): raise self.recipient
        return self.recipient if len([row for row in self.calls if row[0]=='rcpt'])==1 else self.random
    def rset(self): self.calls.append(('rset',)); return 250,b'OK'
    def close(self): self.closed=True


@pytest.mark.parametrize('recipient,random,expected',[
    ((250,b'2.1.5 OK'),(550,b'5.1.1 User unknown'),'accepted'),
    ((250,b'OK'),(250,b'OK'),'catch_all'),
    ((250,b'OK'),(451,b'4.7.1 Greylisted'),'unknown'),
    ((252,b'Cannot verify'),(550,b'5.1.1 User unknown'),'unknown'),
    ((550,b'5.1.1 User unknown'),(550,b'5.1.1 User unknown'),'invalid'),
    ((550,b'5.7.1 Blocked IP'),(550,b'5.1.1 User unknown'),'unknown'),
    ((550,b'Mailbox unavailable'),(550,b'5.1.1 User unknown'),'unknown'),
    ((452,b'4.2.2 Full'),(550,b'5.1.1 User unknown'),'unknown'),
    (TimeoutError(),(550,b'5.1.1 User unknown'),'unknown'),
])
def test_smtp_verdicts_are_recipient_specific_never_policy_guessing(recipient,random,expected):
    fixture=SMTPFixture(recipient,random)
    with mock.patch('cvstudio_email_verifier._DeadlineSMTP',return_value=fixture):
        verdict,_=SMTPProbe().check('mx.example.test','8.8.8.8','person@example.test',time.monotonic()+5)
    assert verdict==expected and fixture.closed
    assert fixture.calls[0]==('connect','8.8.8.8',25)
    assert all(row[1]=='' for row in fixture.calls if row[0]=='mail')
    assert not any(row[0] in {'data','auth','vrfy','expn'} for row in fixture.calls)
    randoms=[row[1] for row in fixture.calls if row[0]=='rcpt' and row[1]!='person@example.test']
    if randoms: assert randoms[0].startswith('cvstudio-') and randoms[0].endswith('@example.test')


def test_tls_uses_mx_identity_and_sender_rejection_is_unknown():
    for tls,mail in [(True,(250,b'OK')),(False,(550,b'5.7.1 Null sender blocked'))]:
        fixture=SMTPFixture((250,b'OK'),mail=mail,tls=tls)
        with mock.patch('cvstudio_email_verifier._DeadlineSMTP',return_value=fixture):
            result=SMTPProbe().check('mx.example.test','8.8.8.8','person@example.test',time.monotonic()+5)
        if tls: assert ('tls','mx.example.test') in fixture.calls
        else: assert result[0]=='unknown' and not any(row[0]=='rcpt' for row in fixture.calls)


@pytest.mark.parametrize('stage,error,word',[
    ('connect',TimeoutError(),'connection timed out'),
    ('connect',ConnectionRefusedError(),'connection was refused'),
    ('rcpt',TimeoutError(),'mailbox response timed out'),
    ('starttls',ssl.SSLCertVerificationError(),'secure connection'),
])
def test_probe_failures_remain_unconfirmed_with_specific_safe_evidence(stage,error,word):
    fixture=SMTPFixture((250,b'OK'),tls=stage=='starttls')
    setattr(fixture,stage,mock.Mock(side_effect=error))
    with mock.patch('cvstudio_email_verifier._DeadlineSMTP',return_value=fixture):
        verdict,reason=SMTPProbe().check('mx.example.test','8.8.8.8','person@example.test',time.monotonic()+5)
    assert verdict=='unknown' and fixture.closed
    assert word in reason.lower()
    assert 'person@example.test' not in reason
    if stage=='connect': assert not any(row[0]=='rcpt' for row in fixture.calls)


def test_timeout_keeps_passed_format_and_mail_records_without_invalid_verdict():
    service=engine(verdict='unknown')
    result=service.check({'email':'person@example.test'})
    assert (result['syntax'],result['domain'],result['mailbox'],result['status'])==('ok','mx','unknown','unknown')


def test_reply_reader_bounds_slow_drips_line_size_and_multiline_replies():
    for response in [b'250-'+b'x'*4097, b'250-OK\r\n'*17]:
        client=_DeadlineSMTP(time.monotonic()+5)
        client.sock=mock.Mock(); client.sock.recv.side_effect=[bytes([byte]) for byte in response]
        with pytest.raises(smtplib.SMTPException): client.getreply()
    client=_DeadlineSMTP(time.monotonic()-1); client.sock=mock.Mock()
    with pytest.raises(TimeoutError): client.getreply()
    client.sock.recv.assert_not_called()


@pytest.mark.parametrize('expected',['accepted','catch_all','invalid'])
def test_real_smtp_parser_on_isolated_loopback_never_sends_message_data(expected):
    commands=[]
    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            self.connection.settimeout(3)
            self.wfile.write(b'220 Fixture SMTP\r\n')
            while True:
                raw=self.rfile.readline(1024)
                if not raw: break
                command=raw.decode('ascii').strip(); commands.append(command)
                if command.lower().startswith('ehlo '): response=b'250-Fixture\r\n250 SIZE 1024\r\n'
                elif command.lower().startswith('rcpt to:'):
                    missing=expected=='invalid' or ('cvstudio-' in command and expected!='catch_all')
                    response=b'550 5.1.1 User unknown\r\n' if missing else b'250 2.1.5 Recipient OK\r\n'
                else: response=b'250 OK\r\n'
                self.wfile.write(response)
    with socketserver.TCPServer(('127.0.0.1',0),Handler) as server:
        thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        connect=socket.create_connection
        def local_transport(destination,timeout,*args,**kwargs):
            assert destination==('8.8.8.8',25)
            return connect(server.server_address,timeout,*args,**kwargs)
        try:
            with mock.patch('smtplib.socket.create_connection',side_effect=local_transport):
                verdict,_=SMTPProbe().check('mx.example.test','8.8.8.8','person@example.test',time.monotonic()+5)
            assert verdict==expected
        finally:
            server.shutdown(); thread.join(timeout=3)
    assert all(command.split()[0].lower() in {'ehlo','mail','rcpt','rset'} for command in commands)
    assert any(command.lower()=='mail from:<>' for command in commands)


def test_global_probe_concurrency_is_bounded_without_waiting_or_leaking_slots():
    service=engine(); entered=threading.Event(); release=threading.Event()
    def held(*args):
        entered.set(); release.wait(3); return 'unknown','Synthetic wait'
    service.probe.check.side_effect=held
    thread=threading.Thread(target=lambda:service.check({'email':'a@example.test'}))
    thread.start(); assert entered.wait(1)
    try:
        with pytest.raises(VerifierError) as error: service.check({'email':'b@example.test'})
        assert error.value.status==429
        service._slots.acquire()
        try:
            with pytest.raises(VerifierError) as error: service.check({'email':'c@other.test'})
            assert error.value.status==429
        finally: service._slots.release()
    finally:
        release.set(); thread.join(timeout=3)
    assert not thread.is_alive()
    assert service.check({'email':'a@example.test'})['status']=='unknown'


@pytest.fixture
def module(tmp_path):
    if 'app' not in sys.modules:
        os.environ.update(LOCALAPPDATA=str(tmp_path),APPDATA=str(tmp_path),CVSTUDIO_STATE_DIR=str(tmp_path/'state'),CVSTUDIO_DB_PATH=str(tmp_path/'main.sqlite3'),CVSTUDIO_JOB_STATE_PATH=str(tmp_path/'jobs.json'),SALARY_COMPARISON_DATA_DIR=str(tmp_path/'salary'))
        from owner_build_tools.build_protected import write_test_receipt
        write_test_receipt(Path(__file__).resolve().parents[1],environment={'HOME':str(tmp_path),'LOCALAPPDATA':str(tmp_path)})
    import app
    return app


def test_new_route_preserves_all_previous_120_routes_exactly(module):
    from cvstudio_architecture import _route_contract
    previous=tuple(row for row in _route_contract(module.app) if row['endpoint']!='email_verifier')
    assert len(previous)==120
    assert hashlib.sha256(json.dumps(previous,ensure_ascii=True,sort_keys=True,separators=(',',':')).encode()).hexdigest()=='ee8d33baeb48b961a2f50723faacbeb7fed86b55454b3518ab4a07bcd1e90033'


def test_local_post_only_no_store_structured_errors_and_no_paid_calls(module):
    client=module.app.test_client(); headers={'X-CV-Studio-Request':'1'}
    with mock.patch.object(module,'_EMAIL_VERIFIER',engine()) as service, mock.patch.object(module._AI_PROVIDER_CLIENT,'request') as paid:
        assert client.get('/email-verifier').status_code==405
        blocked=client.post('/email-verifier',json={'email':'person@example.test'},headers={**headers,'Origin':'https://untrusted.invalid','Sec-Fetch-Site':'cross-site'})
        assert blocked.status_code==403
        assert not service.dns.hosts.called
        oversized=client.post('/email-verifier',data='x'*2049,headers=headers,content_type='application/json')
        assert oversized.status_code==413 and oversized.json['request_id']
        assert not service.dns.hosts.called
        streamed=client.post('/email-verifier',data=b'x'*3000,headers=headers,content_type='application/json',environ_overrides={'CONTENT_LENGTH':'','wsgi.input_terminated':True})
        assert streamed.status_code==413 and not service.dns.hosts.called
        response=client.post('/email-verifier',json={'email':'person@example.test','mode':'quick'},headers=headers)
        assert response.status_code==200 and response.json['result']['status']=='domain_ok'
        assert 'no-store' in response.headers['Cache-Control']
        error=client.post('/email-verifier',json=[],headers=headers)
        assert error.status_code==400 and error.json['request_id']
        assert 'person@example.test' not in str(error.json)
        paid.assert_not_called()
