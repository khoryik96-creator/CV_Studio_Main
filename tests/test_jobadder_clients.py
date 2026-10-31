"""Signed JobAdder clients: read-only JobAdder access, per-user choices.

All companies, statuses, users, accounts and links are fictional; no network
is used.
"""
import copy
import hashlib
import io
import json
import urllib.error
from unittest import mock

import pytest

from cvstudio_jobadder_clients import (JobAdderClientsService, JobAdderClientsError, linkedin_link,
                                       MAX_FOLLOWED, MAX_ACCOUNTS, MAX_CONNECTIONS)

ACCOUNT_A = "a" * 64          # browser namespace of one JobAdder sign-in
ACCOUNT_B = "b" * 64          # namespace of a later sign-in
API = "https://api.jobadder.com/v2"
USER = {"userId": 7, "accountName": "Example Recruitment", "firstName": "Sample", "email": "sample.user@example.test"}
STATUSES = {"items": [{"statusId": 1, "name": "Prospect", "active": True},
                      {"statusId": 2, "name": "Signed Client", "active": True},
                      {"statusId": 3, "name": "Former Client", "active": False}]}


def company(company_id, status_id=2, name="Example Client", linkedin=None):
    row = {"companyId": company_id, "name": name, "status": {"statusId": status_id, "name": "Signed Client"},
           "owner": {"firstName": "Sample", "lastName": "Owner"}}
    if linkedin is not None:
        row["social"] = {"linkedin": linkedin}
    return row


def identity(user_id=7, account="Example Recruitment", api=API):
    return hashlib.sha256("|".join(["cvstudio-jobadder-clients-v1", api.lower(), account.casefold(), str(user_id)]).encode()).hexdigest()


class Client:
    def __init__(self):
        self.calls, self.replies = [], {"users/current": copy.deepcopy(USER)}

    def request_json(self, path, **kwargs):
        self.calls.append((path, copy.deepcopy(kwargs)))
        reply = self.replies.get(path)
        if isinstance(reply, Exception):
            raise reply
        if reply is None:
            raise AssertionError("unexpected JobAdder read: " + path)
        return 200, copy.deepcopy(reply)

    def paths(self):
        return [path for path, _ in self.calls]


def setup(account=ACCOUNT_A, connected=True):
    vault, client, state = {}, Client(), {"account": account, "connected": connected, "api": API}
    def save(data):
        vault.clear(); vault.update(json.loads(json.dumps(data)))
    service = JobAdderClientsService(client=lambda: client,
        account=lambda: {"connected": state["connected"], "account_cache_namespace": state["account"], "api_url": state["api"]},
        load=lambda: copy.deepcopy(vault), save=save, web_base=lambda: "https://app.jobadder.com", clock=lambda: 1000.0)
    return service, client, vault, state


def token():
    return "fictional-token"


def run(service, body, account=ACCOUNT_A):
    return service.perform({"account": account, **body}, token)


def signed(service, client, account=ACCOUNT_A):
    client.replies["companies/lists/status"] = STATUSES
    return run(service, {"action": "set_statuses", "status_ids": [2]}, account=account)


@pytest.mark.parametrize("value,expected", [
    ("https://www.linkedin.com/company/866656/", ("https://www.linkedin.com/company/866656/", "866656")),
    ("http://linkedin.com/company/example-client", ("https://www.linkedin.com/company/example-client/", "")),
    ("https://sg.linkedin.com/company/example-client/jobs/", ("https://www.linkedin.com/company/example-client/", "")),
    ("https://www.linkedin.com/jobs/search/?f_C=12345&geoId=1", ("", "12345")),
    ("https://www.linkedin.com/jobs/search-results/?f_C=777", ("", "777")),
    ("https://www.linkedin.com/jobs/search/?f_C=1%2C2", ("", "")),
    ("https://www.linkedin.com/jobs/search/?f_C=1&f_C=2", ("", "")),
    ("https://www.linkedin.com/in/sample-person/", ("", "")),
    ("https://evil.test/company/866656/", ("", "")),
    ("https://user@www.linkedin.com/company/866656/", ("", "")),
    ("https://www.linkedin.com:8443/company/866656/", ("", "")),
    ("https://www.linkedin.com:abc/company/866656/", ("", "")),
    ("https://www.linkedin.com:99999/company/866656/", ("", "")),
    ("https://[::1/company/1/", ("", "")),
    ("javascript:alert(1)", ("", "")),
    ("", ("", "")),
])
def test_linkedin_link_accepts_only_company_pages_and_single_company_job_searches(value, expected):
    assert linkedin_link(value) == expected


def test_every_action_needs_a_connected_account():
    service, client, _vault, _state = setup(connected=False)
    for action in ["overview", "statuses", "companies", "follow"]:
        with pytest.raises(JobAdderClientsError) as error:
            run(service, {"action": action})
        assert error.value.status == 401
    assert client.calls == []


@pytest.mark.parametrize("action", [None, ["overview"], {"a": 1}, 7, "delete"])
def test_unsupported_actions_are_input_errors(action):
    service, client, _vault, _state = setup()
    with pytest.raises(JobAdderClientsError) as error:
        run(service, {"action": action})
    assert error.value.status == 400 and client.calls == []


def test_choices_follow_the_jobadder_user_across_sign_ins():
    service, client, vault, state = setup()
    signed(service, client)
    client.replies["companies/11"] = company(11, linkedin="https://www.linkedin.com/company/866656/")
    run(service, {"action": "follow", "company_id": 11})
    assert client.paths().count("users/current") == 1, "the user is read once per sign-in"
    # Signing out and in again to the same user gives a new connection scope;
    # the choices come back after one user read.
    state["account"] = ACCOUNT_B
    overview = run(service, {"action": "overview"}, account=ACCOUNT_B)
    assert overview["account"] == ACCOUNT_B and overview["signed"] == [2] and [row["company_id"] for row in overview["followed"]] == [11]
    assert client.paths().count("users/current") == 2
    run(service, {"action": "overview"}, account=ACCOUNT_B)
    assert client.paths().count("users/current") == 2, "a known sign-in needs no further user read"
    assert set(vault["accounts"]) == {identity()} and vault["connections"] == {ACCOUNT_A: identity(), ACCOUNT_B: identity()}
    # The vault keeps only a one-way key, never the user or account name.
    text = json.dumps(vault)
    assert "Example Recruitment" not in text and "sample.user" not in text and '"7"' not in text


@pytest.mark.parametrize("user", [{"userId": 8, "accountName": "Example Recruitment"}, {"userId": 7, "accountName": "Other Agency"}])
def test_another_user_or_account_never_sees_the_choices(user):
    service, client, _vault, state = setup()
    signed(service, client)
    client.replies["companies/11"] = company(11)
    run(service, {"action": "follow", "company_id": 11})
    state["account"] = ACCOUNT_B
    client.replies["users/current"] = user
    assert run(service, {"action": "overview"}, account=ACCOUNT_B) == {"account": ACCOUNT_B, "signed": [], "followed": []}


def test_another_jobadder_region_never_sees_the_choices():
    service, client, _vault, state = setup()
    signed(service, client)
    state.update(account=ACCOUNT_B, api="https://api.au.jobadder.example/v2")
    assert run(service, {"action": "overview"}, account=ACCOUNT_B)["signed"] == []


@pytest.mark.parametrize("reply", [{"userId": 0}, {"userId": "7"}, {"userId": True}, {}, []])
def test_an_unconfirmed_user_stops_every_action(reply):
    service, client, vault, _state = setup()
    client.replies["users/current"] = reply
    with pytest.raises(JobAdderClientsError) as error:
        run(service, {"action": "overview"})
    assert error.value.status == 502 and not vault


def test_a_stale_page_cannot_change_the_new_sign_in():
    service, client, _vault, state = setup()
    signed(service, client)
    client.replies["companies/11"] = company(11)
    run(service, {"action": "follow", "company_id": 11})
    state["account"] = ACCOUNT_B
    for action in ["set_statuses", "follow", "unfollow", "set_linkedin", "pulled"]:
        with pytest.raises(JobAdderClientsError) as error:
            run(service, {"action": action, "company_id": 11, "status_ids": [2], "link": ""}, account=ACCOUNT_A)
        assert error.value.status == 409


def test_statuses_are_read_and_the_choice_is_checked_against_jobadder():
    service, client, vault, _state = setup()
    client.replies["companies/lists/status"] = STATUSES
    result = run(service, {"action": "statuses"})
    assert [row["name"] for row in result["statuses"]] == ["Prospect", "Signed Client", "Former Client"]
    assert result["statuses"][2]["active"] is False and result["signed"] == []
    with pytest.raises(JobAdderClientsError) as error:
        run(service, {"action": "set_statuses", "status_ids": [2, 9]})
    assert error.value.status == 409 and not vault["accounts"]
    assert run(service, {"action": "set_statuses", "status_ids": [3, 2]})["signed"] == [2, 3]
    assert vault["accounts"][identity()]["statuses"] == [2, 3]
    for bad in [[2, 2], ["2"], [True], list(range(1, 60)), None]:
        with pytest.raises(JobAdderClientsError):
            run(service, {"action": "set_statuses", "status_ids": bad})


def test_a_status_removed_from_jobadder_can_be_dropped():
    service, client, vault, _state = setup()
    client.replies["companies/lists/status"] = {"items": STATUSES["items"] + [{"statusId": 9, "name": "Old Signed", "active": True}]}
    run(service, {"action": "set_statuses", "status_ids": [2, 9]})
    client.replies["companies/lists/status"] = STATUSES
    assert run(service, {"action": "statuses"})["signed"] == [2, 9], "the saved choice is shown as it is"
    assert run(service, {"action": "set_statuses", "status_ids": [2]})["signed"] == [2]
    assert vault["accounts"][identity()]["statuses"] == [2]


def test_incomplete_status_list_is_an_error():
    service, client, _vault, _state = setup()
    for reply in [{"items": [{"statusId": 1}]}, {"items": [{"statusId": 1, "name": "A"}, {"statusId": 1, "name": "B"}]}, {"nothing": []}]:
        client.replies["companies/lists/status"] = reply
        with pytest.raises(JobAdderClientsError) as error:
            run(service, {"action": "statuses"})
        assert error.value.status == 502


def test_company_list_needs_a_status_choice_and_uses_the_chosen_status_filter():
    service, client, _vault, _state = setup()
    with pytest.raises(JobAdderClientsError) as error:
        run(service, {"action": "companies"})
    assert error.value.code == "JOBADDER_CLIENTS_SETUP"
    signed(service, client)
    client.replies["companies"] = {"items": [company(11), company(12, status_id=1, name="Not Signed"), company(13, name="Second Client")], "totalCount": 120}
    result = run(service, {"action": "companies", "query": " Example ", "offset": 50})
    path, kwargs = client.calls[-1]
    assert path == "companies" and kwargs["params"] == {"StatusId": [2], "Offset": 50, "Limit": 50, "Name": "Example"}
    for _path, call in client.calls:
        assert set(call) == {"token", "timeout", "fallback", "params"}, "read-only: no method, body or write retry"
    # A company whose status is not chosen is never labelled signed, even if
    # JobAdder ignored the filter.
    assert [row["name"] for row in result["companies"]] == ["Example Client", "Second Client"]
    assert result["companies"][0] == {"company_id": 11, "name": "Example Client", "status": "Signed Client", "owner": "Sample Owner",
                                      "followed": False, "jobadder_url": "https://app.jobadder.com/companies/11"}
    assert result["next_offset"] == 53 and result["total"] == 120
    client.replies["companies"] = {"items": [company(14)], "totalCount": 51}
    assert run(service, {"action": "companies", "offset": 50})["next_offset"] is None
    for bad in [{"offset": -1}, {"offset": "0"}, {"offset": 100001}, {"query": "x" * 201}, {"query": "a\nb"}]:
        with pytest.raises(JobAdderClientsError):
            run(service, {"action": "companies", **bad})
    for reply in [{"items": None}, {"totalCount": 3}, [], {"items": [company(1)] * 51}]:
        client.replies["companies"] = reply
        with pytest.raises(JobAdderClientsError) as error:
            run(service, {"action": "companies"})
        assert error.value.status == 502


def test_follow_reads_the_company_and_keeps_its_linkedin_page():
    service, client, vault, _state = setup()
    signed(service, client)
    client.replies["companies/11"] = company(11, linkedin="https://www.linkedin.com/company/866656/")
    result = run(service, {"action": "follow", "company_id": 11})
    assert result["followed"] == [{"company_id": 11, "name": "Example Client", "linkedin_url": "https://www.linkedin.com/company/866656/",
                                   "linkedin_id": "866656", "followed_at": result["followed"][0]["followed_at"], "pulled_at": "",
                                   "jobadder_url": "https://app.jobadder.com/companies/11"}]
    client.replies["companies"] = {"items": [company(11)], "totalCount": 1}
    assert run(service, {"action": "companies"})["companies"][0]["followed"] is True
    # A company that is no longer signed cannot be followed.
    client.replies["companies/12"] = company(12, status_id=1)
    with pytest.raises(JobAdderClientsError) as error:
        run(service, {"action": "follow", "company_id": 12})
    assert error.value.status == 409 and "12" not in vault["accounts"][identity()]["followed"]
    client.replies["companies/13"] = company(99)
    with pytest.raises(JobAdderClientsError) as error:
        run(service, {"action": "follow", "company_id": 13})
    assert error.value.status == 502
    # A malformed LinkedIn link in JobAdder is ignored, not a server failure.
    client.replies["companies/14"] = company(14, linkedin="https://www.linkedin.com:abc/company/x/")
    assert next(row for row in run(service, {"action": "follow", "company_id": 14})["followed"] if row["company_id"] == 14)["linkedin_url"] == ""
    for bad in [0, -1, "11", True, None]:
        with pytest.raises(JobAdderClientsError):
            run(service, {"action": "follow", "company_id": bad})


def test_pasted_links_unfollow_and_pull_times():
    service, client, vault, _state = setup()
    signed(service, client)
    client.replies["companies/11"] = company(11)
    assert run(service, {"action": "follow", "company_id": 11})["followed"][0]["linkedin_url"] == ""
    def followed():
        return run(service, {"action": "overview"})["followed"][0]
    run(service, {"action": "set_linkedin", "company_id": 11, "link": "https://www.linkedin.com/company/example-client/about/"})
    assert (followed()["linkedin_url"], followed()["linkedin_id"]) == ("https://www.linkedin.com/company/example-client/", "")
    run(service, {"action": "set_linkedin", "company_id": 11, "link": "https://www.linkedin.com/jobs/search/?f_C=4242"})
    assert (followed()["linkedin_url"], followed()["linkedin_id"]) == ("https://www.linkedin.com/company/example-client/", "4242")
    for bad in ["https://evil.test/company/1/", "https://www.linkedin.com:99999/company/x/"]:
        with pytest.raises(JobAdderClientsError) as error:
            run(service, {"action": "set_linkedin", "company_id": 11, "link": bad})
        assert error.value.status == 400
    # Re-following when JobAdder still has no link keeps the pasted one.
    run(service, {"action": "follow", "company_id": 11})
    assert followed()["linkedin_id"] == "4242"
    run(service, {"action": "pulled", "company_id": 11})
    assert followed()["pulled_at"].endswith("+00:00")
    run(service, {"action": "set_linkedin", "company_id": 11, "link": ""})
    assert (followed()["linkedin_url"], followed()["linkedin_id"]) == ("", "")
    with pytest.raises(JobAdderClientsError) as error:
        run(service, {"action": "set_linkedin", "company_id": 12, "link": ""})
    assert error.value.status == 404
    assert run(service, {"action": "unfollow", "company_id": 11})["followed"] == []
    assert vault["accounts"][identity()]["followed"] == {}
    calls = len(client.calls)
    for action in ["overview", "unfollow", "pulled", "set_linkedin"]:
        try:
            run(service, {"action": action, "company_id": 11, "link": ""})
        except JobAdderClientsError:
            pass
    assert len(client.calls) == calls, "local actions never contact JobAdder"


def test_re_follow_keeps_a_pasted_company_number_for_the_same_named_page():
    service, client, _vault, _state = setup()
    signed(service, client)
    named = "https://www.linkedin.com/company/example-client/"
    client.replies["companies/11"] = company(11, linkedin=named)
    run(service, {"action": "follow", "company_id": 11})
    run(service, {"action": "set_linkedin", "company_id": 11, "link": "https://www.linkedin.com/jobs/search/?f_C=4242"})
    row = run(service, {"action": "follow", "company_id": 11})["followed"][0]
    assert (row["linkedin_url"], row["linkedin_id"]) == (named, "4242"), "a second Follow keeps the number LinkedIn needs"
    # JobAdder later records a different page: the old number may belong to the
    # old page, so it is dropped.
    client.replies["companies/11"] = company(11, linkedin="https://www.linkedin.com/company/example-client-asia/")
    row = run(service, {"action": "follow", "company_id": 11})["followed"][0]
    assert (row["linkedin_url"], row["linkedin_id"]) == ("https://www.linkedin.com/company/example-client-asia/", "")
    # A numbered page in JobAdder wins over anything pasted.
    run(service, {"action": "set_linkedin", "company_id": 11, "link": "https://www.linkedin.com/jobs/search/?f_C=5555"})
    client.replies["companies/11"] = company(11, linkedin="https://www.linkedin.com/company/909090/")
    row = run(service, {"action": "follow", "company_id": 11})["followed"][0]
    assert (row["linkedin_url"], row["linkedin_id"]) == ("https://www.linkedin.com/company/909090/", "909090")


def test_follow_limit_and_eviction_of_users_and_sign_ins():
    service, client, vault, state = setup()
    signed(service, client)
    vault["accounts"][identity()]["followed"] = {str(n): {"name": "Client %d" % n, "linkedin_url": "", "linkedin_id": "",
        "followed_at": "2026-10-30T00:00:00+00:00", "pulled_at": ""} for n in range(1, MAX_FOLLOWED + 1)}
    client.replies["companies/999"] = company(999)
    with pytest.raises(JobAdderClientsError) as error:
        run(service, {"action": "follow", "company_id": 999})
    assert error.value.code == "JOBADDER_CLIENTS_LIMIT"
    for index in range(MAX_ACCOUNTS + 2):
        scope = "%064x" % (index + 1)
        state["account"] = scope
        client.replies["users/current"] = {"userId": 100 + index, "accountName": "Example Recruitment"}
        service.clock = lambda index=index: 2000.0 + index
        client.replies["companies/lists/status"] = STATUSES
        run(service, {"action": "set_statuses", "status_ids": [2]}, account=scope)
    assert len(vault["accounts"]) == MAX_ACCOUNTS and identity(100 + MAX_ACCOUNTS + 1) in vault["accounts"]
    for index in range(MAX_CONNECTIONS + 5):
        scope = "%064x" % (10_000 + index)
        state["account"] = scope
        run(service, {"action": "overview"}, account=scope)
    assert len(vault["connections"]) == MAX_CONNECTIONS and "%064x" % (10_000 + MAX_CONNECTIONS + 4) in vault["connections"]


@pytest.mark.parametrize("mutate", [
    lambda data: data.update(version=2),
    lambda data: data["accounts"].update({"not-hex": {}}),
    lambda data: data["accounts"][identity()].update(statuses=["2"]),
    lambda data: data["accounts"][identity()]["followed"].update({"11": {"name": "", "linkedin_url": "", "linkedin_id": "", "followed_at": "x", "pulled_at": ""}}),
    lambda data: data["accounts"][identity()]["followed"].update({"11": {"name": "A", "linkedin_url": "https://evil.test/", "linkedin_id": "", "followed_at": "2026-10-30T00:00:00+00:00", "pulled_at": ""}}),
    lambda data: data["accounts"][identity()]["followed"].update({"11": {"name": "A", "linkedin_url": "", "linkedin_id": 5, "followed_at": "2026-10-30T00:00:00+00:00", "pulled_at": ""}}),
    lambda data: data["connections"].update({ACCOUNT_A: "not-a-key"}),
    lambda data: data.update(connections=[]),
])
def test_unreadable_saved_choices_fail_without_being_overwritten(mutate):
    service, client, vault, _state = setup()
    signed(service, client)
    mutate(vault)
    before = copy.deepcopy(vault)
    with pytest.raises(JobAdderClientsError) as error:
        run(service, {"action": "overview"})
    assert error.value.status == 503 and vault == before


def test_save_failure_is_reported():
    service, client, _vault, _state = setup()
    client.replies["companies/lists/status"] = STATUSES
    service.save = mock.Mock(side_effect=OSError("disk full"))
    with pytest.raises(JobAdderClientsError) as error:
        run(service, {"action": "set_statuses", "status_ids": [2]})
    assert error.value.status == 503 and "disk" not in str(error.value)


@pytest.mark.parametrize("failure,status", [
    (urllib.error.HTTPError("u", 401, "x", {}, io.BytesIO(b"secret body")), 403),
    (urllib.error.HTTPError("u", 403, "x", {}, io.BytesIO(b"secret body")), 403),
    (urllib.error.HTTPError("u", 404, "x", {}, io.BytesIO(b"secret body")), 404),
    (urllib.error.HTTPError("u", 429, "x", {}, io.BytesIO(b"secret body")), 429),
    (urllib.error.HTTPError("u", 500, "x", {}, io.BytesIO(b"secret body")), 502),
    (TimeoutError("profile content"), 502),
])
def test_jobadder_errors_are_fixed_messages(failure, status):
    service, client, _vault, _state = setup()
    client.replies["companies/lists/status"] = failure
    with pytest.raises(JobAdderClientsError) as error:
        run(service, {"action": "statuses"})
    assert error.value.status == status and "secret" not in str(error.value) and "profile" not in str(error.value)


def test_sign_in_refresh_failure_and_missing_token():
    service, client, _vault, state = setup()
    def broken():
        raise OSError("offline")
    with pytest.raises(JobAdderClientsError) as error:
        service.perform({"action": "overview"}, broken)
    assert error.value.status == 503, "a new sign-in needs one user read"
    with pytest.raises(JobAdderClientsError) as error:
        service.perform({"action": "statuses"}, lambda: None)
    assert error.value.status == 401
    run(service, {"action": "overview"})
    calls = len(client.calls)
    # Once this sign-in's user is known, the follow list needs no JobAdder.
    assert service.perform({"action": "overview"}, broken)["followed"] == []
    assert len(client.calls) == calls


def test_route_is_post_only_bounded_and_local():
    from isolated_app import load_app
    app = load_app()
    assert app._cv_secure_service_name("jobadder_clients") == "jobadder_clients"
    service, client, _vault, _state = setup()
    browser = app.app.test_client()
    headers = {"X-CV-Studio-Request": "1"}
    with mock.patch.object(app, "_JOBADDER_CLIENTS", service), mock.patch.object(app, "_ja_refresh_access_token", return_value="fictional-token"):
        assert browser.post("/jobadder/clients", json={"action": "overview"}).status_code == 403
        assert browser.get("/jobadder/clients").status_code == 405
        response = browser.post("/jobadder/clients", json={"action": "overview"}, headers=headers)
        assert response.status_code == 200 and response.headers["Cache-Control"].startswith("no-store")
        assert response.get_json() == {"ok": True, "account": ACCOUNT_A, "signed": [], "followed": []}
        assert browser.post("/jobadder/clients", data="x" * 9000, content_type="application/json", headers=headers).status_code == 413
        assert browser.post("/jobadder/clients", data="{", content_type="application/json", headers=headers).status_code == 400
        assert browser.post("/jobadder/clients", json={"action": ["overview"]}, headers=headers).status_code == 400
        client.replies["companies/lists/status"] = urllib.error.HTTPError("u", 500, "x", {}, io.BytesIO(b"secret body"))
        failed = browser.post("/jobadder/clients", json={"action": "statuses"}, headers=headers)
        assert failed.status_code == 502 and failed.get_json()["retryable"] is True and "secret" not in failed.get_data(as_text=True)
