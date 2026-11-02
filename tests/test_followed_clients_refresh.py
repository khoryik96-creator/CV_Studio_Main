"""Refresh fictional company metadata without creating/removing any follow."""
import copy

import pytest

from test_jobadder_clients import setup, signed, company, run, ACCOUNT_B
from cvstudio_jobadder_clients import JobAdderClientsError


def followed(link=None):
    service, client, vault, state = setup()
    signed(service, client)
    client.replies['companies/11'] = company(11, linkedin=link)
    row = run(service, {'action': 'follow', 'company_id': 11})['followed'][0]
    return service, client, vault, state, row


def refresh(service, row):
    return run(service, {'action': 'refresh_linkedin', 'company_id': row['company_id'],
                         'expected_url': row['linkedin_url'], 'expected_id': row['linkedin_id']})


def test_refresh_imports_link_added_after_follow_and_preserves_history():
    service, client, _vault, _state, row = followed()
    row = run(service, {'action': 'pulled', 'company_id': 11})['followed'][0]
    client.replies['companies/11'] = company(11, name='Example Updated [MY]', linkedin='http://linkedin.com/company/example-client/')
    updated = refresh(service, row)['followed'][0]
    assert updated['name'] == 'Example Updated [MY]'
    assert updated['linkedin_url'] == 'https://www.linkedin.com/company/example-client/'
    assert updated['linkedin_id'] == ''
    assert updated['followed_at'] == row['followed_at'] and updated['pulled_at'] == row['pulled_at']
    assert all(kwargs.get('method', 'GET') == 'GET' for _, kwargs in client.calls)


@pytest.mark.parametrize('new_link,expected_url,expected_id', [
    (None, 'https://www.linkedin.com/company/first/', '42'),
    ('https://www.linkedin.com/company/first/', 'https://www.linkedin.com/company/first/', '42'),
    ('https://www.linkedin.com/company/second/', 'https://www.linkedin.com/company/second/', ''),
    ('https://www.linkedin.com/company/99/', 'https://www.linkedin.com/company/99/', '99'),
])
def test_refresh_preserves_manual_number_only_for_same_or_missing_registered_page(new_link, expected_url, expected_id):
    service, client, _vault, _state, _row = followed('https://www.linkedin.com/company/first/')
    row = run(service, {'action': 'set_linkedin', 'company_id': 11, 'link': 'https://www.linkedin.com/jobs/search/?f_C=42'})['followed'][0]
    client.replies['companies/11'] = company(11, linkedin=new_link)
    updated = refresh(service, row)['followed'][0]
    assert (updated['linkedin_url'], updated['linkedin_id']) == (expected_url, expected_id)


def test_refresh_never_resurrects_unfollowed_client_or_overwrites_new_manual_link():
    service, client, vault, _state, row = followed()
    run(service, {'action': 'set_linkedin', 'company_id': 11, 'link': 'https://www.linkedin.com/company/new/'})
    baseline, calls = copy.deepcopy(vault), len(client.calls)
    with pytest.raises(JobAdderClientsError) as error:
        refresh(service, row)
    assert error.value.status == 409 and vault == baseline and len(client.calls) == calls
    run(service, {'action': 'unfollow', 'company_id': 11})
    baseline = copy.deepcopy(vault)
    with pytest.raises(JobAdderClientsError) as error:
        refresh(service, row)
    assert error.value.status == 404 and vault == baseline and len(client.calls) == calls


@pytest.mark.parametrize('bad', [company(12), {}, company(11, linkedin='https://attacker.invalid/company/example/')])
def test_bad_response_keeps_saved_follow_and_link(bad):
    service, client, vault, _state, row = followed('https://www.linkedin.com/company/42/')
    client.replies['companies/11'] = bad
    baseline = copy.deepcopy(vault)
    with pytest.raises(JobAdderClientsError):
        refresh(service, row)
    assert vault == baseline


def test_account_swap_during_refresh_cannot_save_response():
    service, client, vault, state, row = followed()
    baseline, request = copy.deepcopy(vault), client.request_json
    def swap(path, **kwargs):
        result = request(path, **kwargs)
        state['account'] = ACCOUNT_B
        return result
    client.request_json = swap
    with pytest.raises(JobAdderClientsError) as error:
        refresh(service, row)
    assert error.value.status == 409 and vault == baseline
