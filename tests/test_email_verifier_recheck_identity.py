"""Review regressions: synthetic SMTP responses only, no live mailboxes."""
import time
from unittest import mock

import pytest

from cvstudio_email_verifier import EmailVerifier, SMTPProbe, VerifierError
from test_email_verifier import SMTPFixture, engine


@pytest.mark.parametrize('suffix', ['', '.', '. AS(201806281)', '. [EXAMPLE]', ' [EXAMPLE]'])
@pytest.mark.parametrize('control', [False, True])
def test_microsoft_punctuated_rejection_retains_recipient_and_control_evidence(suffix, control):
    rejected=(550, ('5.4.1 Recipient address rejected: Access denied'+suffix).encode())
    fixture=SMTPFixture((250,b'OK') if control else rejected, rejected)
    dns=engine().dns
    dns.hosts.return_value=('mx',['tenant.mail.protection.outlook.com'])
    with mock.patch('cvstudio_email_verifier._DeadlineSMTP',return_value=fixture):
        result=EmailVerifier(dns,SMTPProbe()).check({'email':'person@example.test','mode':'deep'})
    assert result['status']==('accepted' if control else 'invalid')
    assert fixture.closed


def test_control_recipient_is_retained_after_the_delayed_recheck():
    seen={};clock=[2000000000];controls=[]
    class GreylistFixture(SMTPFixture):
        def rcpt(self,address):
            self.calls.append(('rcpt',address))
            if address=='person@example.test': return 250,b'2.1.5 Recipient OK'
            controls.append(address)
            first=seen.setdefault(address,clock[0])
            return (451,b'4.7.1 Deferred') if clock[0]-first<120 else (550,b'5.1.1 User unknown')
    service=EmailVerifier(engine().dns,SMTPProbe())
    with mock.patch('cvstudio_email_verifier.time.time',side_effect=lambda:clock[0]), mock.patch('cvstudio_email_verifier._DeadlineSMTP',side_effect=lambda *args:GreylistFixture((250,b'OK'))):
        first=service.check({'email':'person@example.test','mode':'deep'})
        assert first['status']=='unknown' and first['retryable']
        clock[0]+=120
        second=service.check({'email':'person@example.test','mode':'deep','recheck_token':first['recheck_token']})
    assert second['status']=='accepted'
    assert controls[0]==controls[1]
    assert first['recheck_token']==second['recheck_token']
    assert 'person' not in first['recheck_token'] and 'example.test' not in first['recheck_token']


def test_all_connections_in_one_check_share_one_control_identity():
    service=engine(verdict='unknown')
    service.dns.hosts.return_value=('mx',['one.example.test','two.example.test'])
    service.dns.addresses.return_value=['8.8.8.8','2001:4860:4860::8888']
    result=service.check({'email':'person@example.test','mode':'deep'})
    ids={call.kwargs['control_id'] for call in service.probe.check.call_args_list}
    assert len(ids)==1 and len(next(iter(ids)))==32
    assert result['attempts']==4


@pytest.mark.parametrize('token', [None,False,[],{},'', 'v1.bad','x'*1024])
def test_malformed_recheck_identity_is_rejected_before_dns(token):
    service=engine()
    with pytest.raises(VerifierError): service.check({'email':'person@example.test','recheck_token':token})
    service.dns.hosts.assert_not_called()
    service.probe.check.assert_not_called()


def test_recheck_identity_is_bound_to_canonical_address_process_and_expiry():
    service=engine()
    with mock.patch('cvstudio_email_verifier.time.time',return_value=2000000000):
        first=service.check({'email':'Name@EXAMPLE.test'})
        token=first['recheck_token']
        assert service.check({'email':'Name@example.test','mode':'deep','recheck_token':token})['recheck_token']==token
        for email in ['Other@example.test','name@example.test','Name@other.test']:
            service.dns.hosts.reset_mock()
            with pytest.raises(VerifierError): service.check({'email':email,'recheck_token':token})
            service.dns.hosts.assert_not_called()
        service.dns.hosts.reset_mock()
        for bad in [token[:-1]+('0' if token[-1]!='0' else '1'),token.replace('v1.','v2.',1)]:
            with pytest.raises(VerifierError): service.check({'email':'Name@example.test','recheck_token':bad})
        service.dns.hosts.assert_not_called()
        other=engine()
        with pytest.raises(VerifierError): other.check({'email':'Name@example.test','recheck_token':token})
        other.dns.hosts.assert_not_called()
        with pytest.raises(VerifierError): service.check({'email':'Name@example.test','mode':'quick','recheck_token':token})
    with mock.patch('cvstudio_email_verifier.time.time',return_value=2000000000+14401):
        with pytest.raises(VerifierError): service.check({'email':'Name@example.test','recheck_token':token})
    service.dns.hosts.assert_not_called()


def test_quick_and_unsupported_checks_do_not_issue_probe_context():
    service=engine()
    assert 'recheck_token' not in service.check({'email':'person@example.test','mode':'quick'})
    assert 'recheck_token' not in service.check({'email':'"quoted local"@example.test'})
    service.probe.check.assert_not_called()


@pytest.mark.parametrize('bad', ['', 'a'*31, 'a'*33, 'x'*32, ['a'*32]])
def test_control_identity_cannot_add_an_arbitrary_recipient(bad):
    with mock.patch('cvstudio_email_verifier._DeadlineSMTP') as socket:
        with pytest.raises(VerifierError): SMTPProbe().check('mx.example.test','8.8.8.8','person@example.test',1,control_id=bad)
    socket.assert_not_called()


@pytest.mark.parametrize('host,code,reply', [
    ('mx.example.test',550,b'5.4.1 Recipient address rejected: Access denied.'),
    ('tenant.mail.protection.outlook.com.attacker.test',550,b'5.4.1 Recipient address rejected: Access denied.'),
    ('tenant.mail.protection.outlook.com',450,b'5.4.1 Recipient address rejected: Access denied.'),
    ('tenant.mail.protection.outlook.com',550,b'5.4.1 Recipient address rejected: Access deniedSomething'),
    ('tenant.mail.protection.outlook.com',550,b'5.4.1 Recipient address rejected: Access denied..'),
])
def test_punctuation_support_cannot_relax_provider_code_or_word_boundaries(host,code,reply):
    fixture=SMTPFixture((code,reply))
    with mock.patch('cvstudio_email_verifier._DeadlineSMTP',return_value=fixture):
        assert SMTPProbe().check(host,'8.8.8.8','person@example.test',time.monotonic()+5)[0]=='unknown'
