"""Explicit manual recovery of fictional uncertain writes; no external services."""
import copy,json
import pytest
from test_job_leads_jobadder import setup,call,review,post_count,SOURCE,JobAdderContactError


def uncertain():
    service,client,vault,account=setup();proof=review(service);client.fail=TimeoutError('private response')
    assert call(service,'create',review_token=proof,confirmed=True)['state']=='unconfirmed'
    client.fail=None
    return service,client,vault,account,proof


def test_confirmed_resolution_preserves_old_attempt_and_requires_a_new_review_and_create():
    service,client,vault,account,old_proof=uncertain()
    token=call(service,'check')['recovery_token'];old=copy.deepcopy(next(iter(vault['operations'].values())))
    result=call(service,'resolve_not_created',recovery_token=token,confirmed_not_created=True)
    assert token not in json.dumps(vault),'only a hashed challenge is retained'
    assert result['state']=='not_started' and post_count(client)==1
    entry=next(iter(vault['operations'].values()));assert entry['attempts'][0]['payload']==old['payload'] and entry['attempts'][0]['state']=='unconfirmed'
    with pytest.raises(JobAdderContactError):call(service,'create',confirmed=True,review_token=old_proof)
    proof=review(service)
    assert len(next(iter(vault['operations'].values()))['attempts'])==1
    assert call(service,'create',confirmed=True,review_token=proof)['state']=='created'
    assert post_count(client)==2 and SOURCE['email'] not in json.dumps(vault)


@pytest.mark.parametrize('patch',[{}, {'confirmed_not_created':False}, {'confirmed_not_created':True,'recovery_token':'wrong'}])
def test_resolution_cannot_bypass_confirmation_or_challenge(patch):
    service,client,vault,account,_=uncertain();token=call(service,'check')['recovery_token'];before=copy.deepcopy(vault)
    with pytest.raises(JobAdderContactError):call(service,'resolve_not_created',**{'recovery_token':token,**patch})
    assert vault==before and post_count(client)==1


def test_expired_replaced_or_cross_account_challenges_cannot_clear_an_attempt():
    service,client,vault,account,_=uncertain();token=call(service,'check')['recovery_token']
    fresh=call(service,'check')['recovery_token']
    with pytest.raises(JobAdderContactError):call(service,'resolve_not_created',recovery_token=token,confirmed_not_created=True)
    service.clock=lambda:2000
    with pytest.raises(JobAdderContactError):call(service,'resolve_not_created',recovery_token=fresh,confirmed_not_created=True)
    service.clock=lambda:1000;account['account_cache_namespace']='c'*64
    with pytest.raises(JobAdderContactError):call(service,'resolve_not_created',recovery_token=fresh,confirmed_not_created=True)
    assert post_count(client)==1


@pytest.mark.parametrize('company',[12,90])
def test_newly_visible_contacts_prevent_manual_reset(company):
    service,client,vault,account,_=uncertain();token=call(service,'check')['recovery_token']
    client.matches=[{'contactId':45,'email':SOURCE['email'],'company':{'companyId':company,'name':'Example Company'}}]
    if company==12:assert call(service,'resolve_not_created',recovery_token=token,confirmed_not_created=True)['state']=='created'
    else:
        with pytest.raises(JobAdderContactError):call(service,'resolve_not_created',recovery_token=token,confirmed_not_created=True)
    assert 'attempts' not in next(iter(vault['operations'].values())) and post_count(client)==1


def test_old_challenge_cannot_resolve_the_next_uncertain_attempt():
    service,client,vault,account,_=uncertain();token=call(service,'check')['recovery_token']
    call(service,'resolve_not_created',recovery_token=token,confirmed_not_created=True)
    proof=review(service);client.fail=TimeoutError();call(service,'create',confirmed=True,review_token=proof);client.fail=None
    with pytest.raises(JobAdderContactError):call(service,'resolve_not_created',recovery_token=token,confirmed_not_created=True)
    assert post_count(client)==2 and len(next(iter(vault['operations'].values()))['attempts'])==1


def test_manual_resolution_history_is_bounded_without_discarding_older_attempts():
    service,client,vault,account,_=uncertain()
    for index in range(5):
        token=call(service,'check')['recovery_token'];call(service,'resolve_not_created',recovery_token=token,confirmed_not_created=True)
        proof=review(service);client.fail=TimeoutError();call(service,'create',confirmed=True,review_token=proof);client.fail=None
    before=copy.deepcopy(vault);token=call(service,'check')['recovery_token']
    with pytest.raises(JobAdderContactError,match='limit'):call(service,'resolve_not_created',recovery_token=token,confirmed_not_created=True)
    assert len(next(iter(vault['operations'].values()))['attempts'])==5 and post_count(client)==6
