"""Real JobAdder client contract: a 201 Location need not contain JSON."""
import copy,json
from urllib.parse import urlsplit

import pytest
from cvstudio_clients import ExternalResponse,JobAdderClient
from test_job_leads_jobadder import setup,call,BASE


def real_client_service(location='',body=None,status=201):
    service,_,vault,account=setup();requests=[]
    class Transport:
        def request(self,kind,url,**kwargs):
            requests.append((url,kwargs));path=urlsplit(url).path
            if kwargs.get('method')=='POST':
                return ExternalResponse(status,{'Location':location} if location else {},b'' if body is None else json.dumps(body).encode(),url)
            value={'companyId':12,'name':'Example Company'} if path.endswith('/companies/12') else {'items':[],'totalCount':0}
            return ExternalResponse(200,{},json.dumps(value).encode(),url)
    client=JobAdderClient(lambda:'https://api.jobadder.com/v2',lambda force:'fictional-token',transport=Transport())
    service.client=lambda:client
    return service,requests,vault


@pytest.mark.parametrize('location',['https://api.jobadder.com/v2/contacts/45','/v2/contacts/45','contacts/45','https://au3.jobadder.com/contacts/45'])
def test_location_only_created_response_is_confirmed_once(location):
    service,requests,vault=real_client_service(location)
    proof=call(service,'review')['review_token'];result=call(service,'create',review_token=proof,confirmed=True)
    assert result['state']=='created' and result['contact_id']==45 and result['result_reason']=='created_location'
    assert call(service,'create',review_token=proof,confirmed=True)['contact_id']==45
    posts=[kw for _,kw in requests if kw['method']=='POST']
    assert len(posts)==1 and posts[0]['safe_to_retry'] is False and posts[0]['retries']==0
    assert next(iter(vault['operations'].values()))['http_status']==201


@pytest.mark.parametrize('location',['https://attacker.invalid/contacts/45','http://api.jobadder.com/v2/contacts/45','https://api.jobadder.com/v2/candidates/45','/v2/contacts/45?token=fictional','//attacker.invalid/contacts/45','/v2/contacts/0'])
def test_foreign_or_wrong_resource_location_does_not_claim_creation(location):
    service,requests,_=real_client_service(location)
    proof=call(service,'review')['review_token'];result=call(service,'create',review_token=proof,confirmed=True)
    assert result['state']=='unconfirmed' and not result.get('contact_id')
    call(service,'create',review_token=proof,confirmed=True)
    assert len([kw for _,kw in requests if kw['method']=='POST'])==1


def test_conflicting_ids_and_non_created_status_stay_unconfirmed():
    for location,body,status in [('/v2/contacts/46',{'contactId':45},201),('/v2/contacts/45',{},202)]:
        service,requests,_=real_client_service(location,body,status)
        proof=call(service,'review')['review_token'];result=call(service,'create',review_token=proof,confirmed=True)
        assert result['state']=='unconfirmed' and result['http_status']==status
