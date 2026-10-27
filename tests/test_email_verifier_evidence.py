"""Controlled SMTP evidence, never real mailboxes or network destinations."""
import time
from unittest import mock

import pytest

from cvstudio_email_verifier import CheckUnavailable, EmailVerifier, ProbeResult, SMTPProbe, VerifierError
from test_email_verifier import SMTPFixture, engine, module


@pytest.mark.parametrize('host,reply,expected', [
    ('tenant.mail.protection.outlook.com', b'5.4.1 Recipient address rejected: Access denied [EXAMPLE]', 'invalid'),
    ('mail.protection.outlook.com.attacker.test', b'5.4.1 Recipient address rejected: Access denied', 'unknown'),
    ('mx.example.test', b'5.4.1 Recipient address rejected: Access denied', 'unknown'),
    ('tenant.mail.protection.outlook.com', b'5.4.1 Access denied', 'unknown'),
    ('tenant.mail.protection.outlook.com', b'5.7.1 Recipient address rejected: Access denied', 'unknown'),
])
def test_provider_rejections_require_exact_mx_suffix_code_and_recipient_message(host, reply, expected):
    fixture = SMTPFixture((550, reply))
    with mock.patch('cvstudio_email_verifier._DeadlineSMTP', return_value=fixture):
        result = SMTPProbe().check(host, '8.8.8.8', 'person@example.test', time.monotonic()+5)
    assert result[0] == expected
    assert fixture.closed


def test_microsoft_rejected_control_supports_the_accepted_target():
    fixture = SMTPFixture((250, b'OK'), (550, b'5.4.1 Recipient address rejected: Access denied'))
    with mock.patch('cvstudio_email_verifier._DeadlineSMTP', return_value=fixture):
        result = SMTPProbe().check('tenant.mail.protection.outlook.com', '8.8.8.8', 'person@example.test', time.monotonic()+5)
    assert result[0] == 'accepted'


@pytest.mark.parametrize('status,mailbox,catch_all,assessment', [
    ('accepted', 'accepted', 'not_detected', 'lower_risk'),
    ('catch_all', 'accepted', 'detected', 'caution'),
    ('unknown', 'unconfirmed', 'inconclusive', 'unconfirmed'),
    ('invalid', 'rejected', 'not_checked', 'avoid'),
])
def test_assessment_keeps_mailbox_acceptance_separate_from_domain_policy(status, mailbox, catch_all, assessment):
    result = engine(verdict=status).check({'email':'person@example.test'})
    assert result['status'] == status  # legacy status is preserved
    assert result['mailbox_evidence'] == mailbox
    assert result['catch_all'] == catch_all
    assert result['assessment']['level'] == assessment
    assert result['attempts'] == 1
    assert result['evidence'] and result['checked_at']
    assert 'score' not in result and 'confidence_percent' not in result


def test_quick_check_cannot_gain_mailbox_evidence_or_disposable_invalidate_a_mailbox():
    result = engine().check({'email':'info@mailinator.com', 'mode':'quick'})
    assert result['assessment']['level'] == 'unconfirmed'
    assert result['mailbox_evidence'] == result['catch_all'] == 'not_checked'
    assert result['attempts'] == 0
    result = engine().check({'email':'info@mailinator.com'})
    assert result['status'] == 'accepted' and result['assessment']['level'] == 'caution'


def test_deeper_check_compares_servers_and_reports_conflicting_recipient_evidence():
    service = engine()
    service.dns.hosts.return_value = ('mx', ['one.example.test','two.example.test'])
    service.dns.addresses.return_value = ['8.8.8.8','2001:4860:4860::8888']
    service.probe.check.side_effect = [('invalid','Explicit rejection'), ('accepted','Specific acceptance')]
    result = service.check({'email':'person@example.test', 'mode':'deep'})
    assert result['status'] == 'unknown' and result['outcome'] == 'conflicting_servers'
    assert result['assessment']['level'] == 'unconfirmed'
    assert result['mailbox_evidence'] == 'conflicting'
    assert result['attempts'] == 2
    assert [call.args[0] for call in service.probe.check.call_args_list] == ['one.example.test','two.example.test']


def test_deep_check_has_four_session_limit_and_one_shared_deadline():
    service = engine(verdict='unknown')
    service.dns.hosts.return_value = ('mx', ['one.example.test','two.example.test'])
    service.dns.addresses.return_value = ['8.8.8.8','2001:4860:4860::8888']
    result = service.check({'email':'person@example.test', 'mode':'deep'})
    assert result['status'] == 'unknown' and result['attempts'] == 4
    calls = service.probe.check.call_args_list
    assert len({call.args[3] for call in calls}) == 1
    assert calls[0].args[3] <= time.monotonic()+25


def test_deep_connection_failure_keeps_dual_stack_recovery_before_another_blocked_route():
    service=engine()
    service.dns.hosts.return_value=('mx',['one.example.test','two.example.test'])
    service.dns.addresses.return_value=['8.8.8.8','2001:4860:4860::8888']
    service.probe.check.side_effect=lambda host,ip,*args: ProbeResult('unknown','Network blocked',outcome='connection',retryable=True) if ':' not in ip else ProbeResult('accepted','Specific acceptance',outcome='recipient_supported',target='accepted')
    result=service.check({'email':'person@example.test','mode':'deep'})
    assert result['status']=='accepted' and result['attempts']==4
    assert [(call.args[0],call.args[1]) for call in service.probe.check.call_args_list][:2]==[('one.example.test','8.8.8.8'),('one.example.test','2001:4860:4860::8888')]


def test_temporary_reply_and_mailbox_full_are_distinct_and_never_missing():
    for reply, outcome, retryable in [((451,b'4.7.1 Try later'),'temporary',True), ((552,b'5.2.2 Mailbox full'),'mailbox_full',False)]:
        fixture = SMTPFixture(reply)
        with mock.patch('cvstudio_email_verifier._DeadlineSMTP',return_value=fixture):
            service = EmailVerifier(engine().dns, SMTPProbe())
            result = service.check({'email':'person@example.test'})
        assert result['status'] == 'unknown' and result['outcome'] == outcome
        assert result['retryable'] is retryable
        assert result['retry_after_seconds'] == (120 if retryable else 0)
        assert 'person@example.test' not in str(result['evidence'])


def test_deep_invalid_input_still_fails_before_dns():
    service = engine()
    for value in [False,[], 'unlimited']:
        with pytest.raises(VerifierError): service.check({'email':'person@example.test','mode':value})
    service.dns.hosts.assert_not_called()


@pytest.mark.parametrize('first,second,expected', [
    ('accepted','unknown','accepted'), ('unknown','accepted','accepted'),
    ('accepted','catch_all','catch_all'), ('catch_all','accepted','catch_all'),
    ('invalid','unknown','invalid'), ('unknown','invalid','invalid'),
])
def test_deep_inconclusive_connections_cannot_overwrite_decisive_evidence(first, second, expected):
    service = engine()
    service.dns.hosts.return_value = ('mx', ['one.example.test','two.example.test'])
    service.probe.check.side_effect = [ProbeResult(status, 'Synthetic '+status, outcome=status, retryable=status=='unknown') for status in (first,second)]
    result = service.check({'email':'person@example.test','mode':'deep'})
    assert result['status'] == expected and result['outcome'] == expected
    assert not result['retryable']


def test_accepted_target_with_failed_control_remains_unconfirmed_but_keeps_acceptance_evidence():
    fixture = SMTPFixture((250,b'OK'), (451,b'4.7.1 Temporary failure'))
    with mock.patch('cvstudio_email_verifier._DeadlineSMTP',return_value=fixture):
        result = EmailVerifier(engine().dns,SMTPProbe()).check({'email':'person@example.test'})
    assert result['status'] == 'unknown' and result['mailbox_evidence'] == 'accepted'
    assert result['catch_all'] == 'inconclusive' and result['retryable']


def test_full_mode_cannot_ignore_accepted_recipient_evidence_on_an_earlier_connection():
    service=engine()
    service.dns.addresses.return_value=['8.8.8.8','8.8.4.4']
    service.probe.check.side_effect=[ProbeResult('unknown','Control deferred',target='accepted',retryable=True),ProbeResult('invalid','Recipient rejected',target='rejected')]
    result=service.check({'email':'person@example.test'})
    assert result['status']=='unknown' and result['mailbox_evidence']=='conflicting'


def test_a_temporary_connection_cannot_make_a_later_policy_block_automatically_retryable():
    service=engine()
    service.dns.addresses.return_value=['8.8.8.8','8.8.4.4']
    service.probe.check.side_effect=[ProbeResult('unknown','Connection failed',outcome='connection',retryable=True),ProbeResult('unknown','Policy blocked',outcome='policy',retryable=False)]
    result=service.check({'email':'person@example.test'})
    assert not result['retryable'] and result['retry_after_seconds']==0
    assert result['outcome']=='policy' and result['reason']=='Policy blocked'


def test_temporary_dns_failure_is_recheckable_but_restricted_destinations_are_not():
    service = engine()
    for message, retryable in [("The domain's DNS could not be read. This does not mean the address is invalid.",True), ('The mail server resolves to a restricted network address. It was not contacted.',False)]:
        service.dns.hosts.side_effect = CheckUnavailable(message)
        result = service.check({'email':'person@example.test','mode':'deep'})
        assert result['status'] == 'unknown' and result['retryable'] is retryable
        assert not service._domains and result['attempts'] == 0


@pytest.mark.parametrize('reply', [
    (550,b'5.7.1 Policy block. See 5.1.1 documentation'),
    (450,b'5.1.1 Misleading temporary reply'),
    (550,b'Read more about 5.1.1'),
    (550,b'5.4.1 Recipient address rejected: Access deniedSomething'),
])
def test_embedded_or_malformed_codes_cannot_create_missing_mailbox_evidence(reply):
    fixture = SMTPFixture(reply)
    with mock.patch('cvstudio_email_verifier._DeadlineSMTP',return_value=fixture):
        assert SMTPProbe().check('tenant.mail.protection.outlook.com','8.8.8.8','person@example.test',time.monotonic()+5)[0]=='unknown'


def test_route_accepts_deep_mode_without_routes_paid_calls_or_persistent_results(module):
    app = module
    with mock.patch.object(app,'_EMAIL_VERIFIER',engine()) as service:
        response=app.app.test_client().post('/email-verifier',json={'email':'person@example.test','mode':'deep'},headers={'X-CV-Studio-Request':'1'})
    assert response.status_code==200 and response.json['result']['assessment']['level']=='lower_risk'
    assert response.json['result']['mode']=='deep' and service.probe.check.call_count==1
    assert 'no-store' in response.headers['Cache-Control']
