"""No-network Apollo boundaries; all accounts, addresses and keys fictional."""
import copy
import io
import json
from unittest import mock
import pytest
from cvstudio_apollo import ApolloService, ApolloBrokerClient, ApolloError, broker_origin

ORIGIN = 'https://cvstudio-apollo.example.workers.dev'
PERSON = {'name':'Sample Person','title':'HR','location':'Malaysia','matched':'HR','url':'https://www.linkedin.com/in/sample-person'}
ROW = {'id':'1'*32,'revision':2,'company':'Example Company','hr':{'company_id':'123','company_url':'https://www.linkedin.com/company/example/','people':[PERSON]}}


class Broker:
    origin = ORIGIN
    def __init__(self): self.calls=[]; self.result={'state':'found','email':'person@example.test','email_status':'verified'}
    def post(self, action, body):
        self.calls.append((action,copy.deepcopy(body)))
        if action=='start': return {'flow_id':'a'*64,'authorization_url':'https://app.apollo.io/#/oauth/authorize?state='+'a'*64}
        if action=='poll': return {'state':'connected','connection_id':'a'*64,'name':'Example User'}
        if action in {'reveal','lookup-status'}:
            if isinstance(self.result,Exception): raise self.result
            return copy.deepcopy(self.result)
        return {}


def fixture():
    vault={}; broker=Broker()
    def save(data): vault.clear();vault.update(copy.deepcopy(data))
    service=ApolloService(client=broker,load=lambda:copy.deepcopy(vault),save=save,clock=lambda:1000)
    return service,broker,vault


def connect(service): service.perform('connect'); service.perform('poll')


def test_login_hides_credentials_and_account_replacement_is_explicit():
    service,broker,vault=fixture()
    assert not service.status()['connected']
    result=service.perform('connect')
    assert 'secret' not in json.dumps(result) and 'authorization_url' in result
    assert len(vault['flow']['secret'])==64
    assert set(broker.calls[0][1])=={'proof_hash'}
    service.perform('connect');assert len(broker.calls)==1,'continue does not create a second flow'
    service.perform('poll'); assert service.status()['name']=='Example User'
    assert vault['secret'] not in json.dumps(service.status())
    with pytest.raises(ApolloError): service.perform('connect')
    service.perform('disconnect');assert not vault and not service.status()['connected']


def test_confirmation_and_saved_profile_gates_precede_any_paid_transport():
    service,broker,vault=fixture();connect(service);before=len(broker.calls)
    for row,url,confirmed in [(ROW,PERSON['url'],False),(ROW,'https://www.linkedin.com/in/other',True),({**ROW,'deleted':True},PERSON['url'],True),({**ROW,'hr':None},PERSON['url'],True)]:
        with pytest.raises(ApolloError): service.perform('reveal',row=row,url=url,confirmed=confirmed)
    assert len(broker.calls)==before and not vault['emails']


def test_reveal_is_persisted_once_and_keeps_provider_status_separate():
    service,broker,vault=fixture();connect(service)
    seen=[];original=broker.post
    def check(action,body):
        if action=='reveal':
            assert next(iter(vault['emails'].values()))['state']=='pending'
            seen.append(body['operation_id'])
        return original(action,body)
    broker.post=check
    result=service.perform('reveal',row=ROW,url=PERSON['url'],confirmed=True)['result']
    assert result['email']=='person@example.test' and result['email_status']=='verified'
    assert 'operation_id' not in result
    service.perform('reveal',row=ROW,url=PERSON['url'],confirmed=True)
    assert len(seen)==1
    assert service.perform('emails',row=ROW)['emails'][PERSON['url']]==result
    changed=copy.deepcopy(ROW);changed['hr']['company_id']='456'
    assert service.perform('emails',row=changed)['emails']=={}
    service.perform('disconnect');connect(service)
    assert service.perform('emails',row=ROW)['emails']=={},'a new account never sees the previous account emails'


def test_ambiguous_request_survives_restart_and_only_checks_the_same_operation():
    service,broker,vault=fixture();connect(service)
    broker.result=TimeoutError('private upstream content must not leak')
    result=service.perform('reveal',row=ROW,url=PERSON['url'],confirmed=True)
    assert result['result']['state']=='unconfirmed' and 'private' not in json.dumps(result)
    operation=next(iter(vault['emails'].values()))['operation_id']
    restarted=ApolloService(client=broker,load=lambda:copy.deepcopy(vault),save=lambda d:(vault.clear(),vault.update(copy.deepcopy(d))))
    broker.result={'state':'found','email':'person@example.test','email_status':'catch_all'}
    assert restarted.perform('reveal',row=ROW,url=PERSON['url'])['result']['email_status']=='catch_all'
    assert [x[0] for x in broker.calls].count('reveal')==1
    assert broker.calls[-1]==('lookup-status',{'connection_id':vault['connection'],'secret':vault['secret'],'operation_id':operation})


def test_storage_failure_stops_before_spend_and_concurrency_is_visible():
    service,broker,vault=fixture();connect(service);before=len(broker.calls)
    service.save=mock.Mock(side_effect=OSError('private path'))
    with pytest.raises(ApolloError,match='saved securely'): service.perform('reveal',row=ROW,url=PERSON['url'],confirmed=True)
    assert len(broker.calls)==before
    service.lock.acquire()
    try:
        with pytest.raises(ApolloError) as error: service.perform('disconnect')
        assert error.value.code=='APOLLO_BUSY'
    finally: service.lock.release()


@pytest.mark.parametrize('result',[{'state':'found','email':'bad\n@example.test'},{'state':'found','email':'person@example.test','email_status':'<script>'},{'state':'unexpected'},[]])
def test_malformed_provider_data_never_becomes_a_verified_email(result):
    service,broker,vault=fixture();connect(service);broker.result=result
    assert service.perform('reveal',row=ROW,url=PERSON['url'],confirmed=True)['result']['state']=='unconfirmed'


def test_changed_broker_does_not_receive_old_connection_credential():
    service,broker,vault=fixture();connect(service);before=len(broker.calls)
    broker.origin='https://other.example.workers.dev'
    assert not service.status()['connected']
    with pytest.raises(ApolloError): service.perform('emails',row=ROW)
    assert len(broker.calls)==before


def test_disconnect_failure_never_claims_a_local_credential_was_removed():
    service,broker,vault=fixture();connect(service)
    service.save=mock.Mock(side_effect=OSError('fictional storage failure'))
    with pytest.raises(ApolloError) as exc: service.perform('disconnect')
    assert exc.value.code=='APOLLO_STORAGE' and vault['connection']


def test_expired_or_cancelled_login_cannot_restore_a_connection():
    service,broker,vault=fixture();service.perform('connect')
    service.clock=lambda:2000
    with pytest.raises(ApolloError):service.perform('poll')
    service.perform('disconnect')
    with pytest.raises(ApolloError):service.perform('poll')
    assert not service.status()['connected']


@pytest.mark.parametrize('value',['http://localhost:5000','https://127.0.0.1','https://a.b.workers.dev@evil.test','https://a.b.workers.dev/path','https://a.b.workers.dev:443','https://a.b.workers.dev?key=x'])
def test_service_address_is_not_an_arbitrary_network_target(value):
    with pytest.raises(ApolloError): broker_origin(value)


def test_transport_does_not_retry_or_follow_redirects_and_hides_errors():
    opener=mock.Mock(side_effect=TimeoutError('key and profile content'))
    with pytest.raises(ApolloError) as exc: ApolloBrokerClient(ORIGIN,opener).post('reveal',{})
    assert opener.call_count==1 and 'profile' not in str(exc.value)
    response=io.BytesIO(b'{}');response.__enter__=lambda:response
    class Reply(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self,*args): self.close()
    client=ApolloBrokerClient(ORIGIN,lambda *args,**kwargs:Reply(b'x'*131073))
    with pytest.raises(ApolloError): client.post('poll',{})
    from cvstudio_apollo import _NoRedirect
    with pytest.raises(ApolloError): _NoRedirect().redirect_request(None,None,302,'',{},'https://other.test')
