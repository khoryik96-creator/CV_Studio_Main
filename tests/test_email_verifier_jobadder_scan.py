"""Read-only JobAdder client-contact listing for the Email Verifier scan.

``GET /jobadder/client_contacts`` returns one bounded page of client contacts
(id, name, company, primary email, no-longer-with-company flag) so the browser
can check each email and list the invalid ones with a link to the contact. It
never writes to JobAdder and never echoes JobAdder's raw error body. The
transport and token refresh are replaced with in-memory fakes; no network call,
OAuth exchange or credential write happens. All names are synthetic.
"""

import io
import os
from pathlib import Path
import tempfile
import unittest
import urllib.error

from cvstudio_jobadder_read import JobAdderReadService, _client_contact_summary

ROOT = Path(__file__).resolve().parents[1]


class _FakeClient:
    def __init__(self, payload=None, error=None):
        self.payload = {"items": []} if payload is None else payload
        self.error = error
        self.calls = []

    def request_json(self, endpoint, **kwargs):
        self.calls.append((endpoint, kwargs))
        if self.error is not None:
            raise self.error
        return 200, self.payload

    def request_raw(self, *args, **kwargs):  # pragma: no cover - must never be used
        raise AssertionError("the contact scan must not issue raw requests")


def _contact(contact_id, first="Alex", last="Tan", email="alex@contoso.example", company="Contoso", **extra):
    item = {
        "contactId": contact_id, "firstName": first, "lastName": last, "email": email,
        "phone": "+60 3 0000 0000", "mobile": "+60 12 000 0000", "position": "HR Manager",
        "company": {"companyId": 77, "name": company}, "status": {"statusId": 1, "name": "Active"},
        "owner": {"userId": 9, "firstName": "Owner"},
    }
    item.update(extra)
    return item


def _service(client, *, token="fake-token", args=None):
    args = dict(args or {})
    return JobAdderReadService(
        jsonify=lambda payload: payload,
        query_arg=lambda name, default="": args.get(name, default),
        refresh_token=lambda force=False: token,
        client=lambda: client,
        public_info=lambda: {},
        creds_store=lambda: {},
        ja_api=lambda path: path,
    )


def _http_error(code, body=b'{"secret":"raw jobadder detail"}'):
    return urllib.error.HTTPError("https://api.jobadder.example/v2/contacts", code, "error", {}, io.BytesIO(body))


class ClientContactSummaryTests(unittest.TestCase):
    def test_only_the_fields_the_dashboard_needs_leave_the_process(self):
        summary = _client_contact_summary(_contact(41, inactive=True))
        self.assertEqual(summary, {
            "contact_id": 41, "name": "Alex Tan", "company": "Contoso",
            "email": "alex@contoso.example", "inactive": True,
        })

    def test_unusable_records_are_dropped(self):
        for item in (None, "x", {}, {"contactId": "41"}, {"contactId": 0}, {"contactId": -3}, {"contactId": True}, {"contactId": 4.0}):
            with self.subTest(item=item):
                self.assertIsNone(_client_contact_summary(item))

    def test_text_is_collapsed_bounded_and_typed(self):
        summary = _client_contact_summary({
            "contactId": 5, "firstName": "  Mary \n Ann ", "lastName": None, "email": ["not", "text"],
            "company": {"name": "N" * 500}, "status": "not-a-dict", "inactive": "yes",
        })
        self.assertEqual(summary["name"], "Mary Ann")
        self.assertEqual(summary["email"], "")
        self.assertEqual(len(summary["company"]), 200)
        self.assertNotIn("status", summary)
        self.assertIs(summary["inactive"], False)


class ClientContactsHandlerTests(unittest.TestCase):
    def test_one_page_is_fetched_with_offset_and_limit(self):
        client = _FakeClient({"items": [_contact(1), _contact(2, email="")], "totalCount": 250})
        body = _service(client, args={"offset": "100", "limit": "100"}).client_contacts()
        self.assertEqual(len(client.calls), 1)
        endpoint, kwargs = client.calls[0]
        self.assertEqual(endpoint, "contacts")
        self.assertEqual(kwargs["params"], [("Offset", 100), ("Limit", 100)])
        self.assertEqual(kwargs["token"], "fake-token")
        # A plain read: no method override, body or write retry.
        self.assertNotIn("method", kwargs)
        self.assertNotIn("body", kwargs)
        self.assertEqual([c["contact_id"] for c in body["contacts"]], [1, 2])
        self.assertEqual(body["next_offset"], 102)
        self.assertEqual(body["total"], 250)
        self.assertNotIn("phone", body["contacts"][0])
        self.assertNotIn("status", body["contacts"][0])
        # No stand-in list: a page that is not JSON must not pass as an empty one.
        self.assertEqual(kwargs["fallback"], {})

    def test_the_last_page_has_no_next_offset(self):
        client = _FakeClient({"items": [_contact(1), _contact(2)], "totalCount": 202})
        body = _service(client, args={"offset": "200"}).client_contacts()
        self.assertIsNone(body["next_offset"])
        empty = _service(_FakeClient({"items": [], "totalCount": 202}), args={"offset": "202"}).client_contacts()
        self.assertIsNone(empty["next_offset"])

    def test_without_a_total_a_full_page_means_more(self):
        full = _FakeClient({"items": [_contact(i) for i in range(1, 11)]})
        self.assertEqual(_service(full, args={"limit": "10"}).client_contacts()["next_offset"], 10)
        short = _FakeClient({"items": [_contact(i) for i in range(1, 4)]})
        self.assertIsNone(_service(short, args={"limit": "10"}).client_contacts()["next_offset"])

    def test_bad_offset_or_limit_is_refused_before_any_request(self):
        for args in ({"offset": "-1"}, {"offset": "abc"}, {"offset": "1000001"}, {"limit": "0"}, {"limit": "101"}, {"limit": "1.5"}):
            with self.subTest(args=args):
                client = _FakeClient()
                body, status = _service(client, args=args).client_contacts()
                self.assertEqual(status, 400)
                self.assertIn("error", body)
                self.assertEqual(client.calls, [])

    def test_without_a_jobadder_connection_nothing_is_requested(self):
        client = _FakeClient()
        body, status = _service(client, token="").client_contacts()
        self.assertEqual(status, 401)
        self.assertIn("Connect JobAdder", body["error"])
        self.assertEqual(client.calls, [])

        def broken_refresh(force=False):
            raise RuntimeError("token endpoint unavailable")

        service = _service(client)
        service._refresh_token = broken_refresh
        body, status = service.client_contacts()
        # A refresh that cannot reach JobAdder is temporary, not "disconnected".
        self.assertEqual(status, 503)
        self.assertNotIn("Connect JobAdder", body["error"])
        self.assertNotIn("token endpoint unavailable", body["error"])
        self.assertEqual(client.calls, [])

    def test_jobadder_errors_never_echo_the_raw_response(self):
        cases = ((401, 401), (403, 403), (429, 429), (500, 502), (404, 502))
        for upstream, expected in cases:
            with self.subTest(upstream=upstream):
                body, status = _service(_FakeClient(error=_http_error(upstream))).client_contacts()
                self.assertEqual(status, expected)
                self.assertNotIn("raw jobadder detail", str(body))
        body, status = _service(_FakeClient(error=PermissionError("Not authenticated"))).client_contacts()
        self.assertEqual(status, 401)
        body, status = _service(_FakeClient(error=OSError("socket detail 10.0.0.1"))).client_contacts()
        self.assertEqual(status, 502)
        self.assertNotIn("10.0.0.1", str(body))

    def test_an_unexpected_payload_is_an_error_not_an_empty_list(self):
        # {} is what the client returns for a 200 page that is not JSON (an HTML
        # maintenance page, say): it must stop the scan, not end it as complete.
        for payload in ([], {"items": "x"}, "text", {}, {"totalCount": 300}, {"items": None}):
            with self.subTest(payload=payload):
                body, status = _service(_FakeClient(payload)).client_contacts()
                self.assertEqual(status, 502)

    def test_a_bad_total_is_ignored(self):
        for total in (-5, "250", True, None):
            with self.subTest(total=total):
                body = _service(_FakeClient({"items": [_contact(1)], "totalCount": total}), args={"limit": "1"}).client_contacts()
                self.assertIsNone(body["total"])
                self.assertEqual(body["next_offset"], 1)


class ClientContactsRouteTests(unittest.TestCase):
    """Through the real Flask route, with isolated state and a fake transport."""

    @classmethod
    def setUpClass(cls):
        cls._temporary = tempfile.TemporaryDirectory(prefix="cvstudio-ja-contact-scan-")
        state = Path(cls._temporary.name)
        cls._saved = {key: os.environ.get(key) for key in (
            "HOME", "LOCALAPPDATA", "APPDATA", "CVSTUDIO_STATE_DIR", "CVSTUDIO_DB_PATH", "CVSTUDIO_JOB_STATE_PATH",
            "SALARY_COMPARISON_DATA_DIR")}
        import sys
        if "app" not in sys.modules:
            # The receipt is read from HOME on Linux and macOS and LOCALAPPDATA on
            # Windows: point both at this temporary state, never the owner's.
            os.environ.update(
                HOME=str(state), LOCALAPPDATA=str(state), APPDATA=str(state), CVSTUDIO_STATE_DIR=str(state / "state"),
                CVSTUDIO_DB_PATH=str(state / "main.sqlite3"), CVSTUDIO_JOB_STATE_PATH=str(state / "jobs.json"),
                SALARY_COMPARISON_DATA_DIR=str(state / "salary"),
            )
            from owner_build_tools.build_protected import write_test_receipt
            write_test_receipt(ROOT, environment={"HOME": str(state), "LOCALAPPDATA": str(state)})
        import app
        cls.app = app

    @classmethod
    def tearDownClass(cls):
        for key, value in cls._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        cls._temporary.cleanup()

    def setUp(self):
        self._orig_refresh = self.app._ja_refresh_access_token
        self._orig_client = self.app._JOBADDER_CLIENT
        self.client_double = _FakeClient({"items": [_contact(7, email="sam@fabrikam.example", company="Fabrikam")], "totalCount": 1})
        self.app._ja_refresh_access_token = lambda force=False: "fake-token"
        self.app._JOBADDER_CLIENT = self.client_double
        self.http = self.app.app.test_client()

    def tearDown(self):
        self.app._ja_refresh_access_token = self._orig_refresh
        self.app._JOBADDER_CLIENT = self._orig_client

    def test_the_route_returns_one_page(self):
        response = self.http.get("/jobadder/client_contacts?offset=0&limit=50", headers={"X-CV-Studio-Request": "1"})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["contacts"][0]["email"], "sam@fabrikam.example")
        self.assertIsNone(data["next_offset"])
        self.assertEqual(self.client_double.calls[0][1]["params"], [("Offset", 0), ("Limit", 50)])

    def test_the_route_is_get_only(self):
        rules = [rule for rule in self.app.app.url_map.iter_rules() if rule.rule == "/jobadder/client_contacts"]
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0].methods - {"HEAD", "OPTIONS"}, {"GET"})
        self.assertEqual(rules[0].endpoint, "jobadder_client_contacts")
        response = self.http.post("/jobadder/client_contacts", json={}, headers={"X-CV-Studio-Request": "1"})
        self.assertEqual(response.status_code, 405)
        self.assertEqual(self.client_double.calls, [])

    def test_unauthenticated_route_returns_401(self):
        self.app._ja_refresh_access_token = lambda force=False: None
        response = self.http.get("/jobadder/client_contacts", headers={"X-CV-Studio-Request": "1"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.client_double.calls, [])


if __name__ == "__main__":
    unittest.main()
