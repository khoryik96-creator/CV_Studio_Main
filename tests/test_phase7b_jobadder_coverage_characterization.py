"""Phase 7B-5a JobAdder coverage net (characterization, no extraction).

This module locks the observable behaviour of the JobAdder route surface
*before* any of it is moved out of the legacy web shell.  It is deliberately
hermetic: the JobAdder OAuth token refresh and the already-extracted
``JobAdderClient`` transport are replaced with in-memory fakes, so no real
OAuth exchange, network call or credential write happens.  Later extraction
slices (read proxies, token lifecycle, candidate writes) can lean on these
assertions to prove they preserved behaviour.

Scope of this net:
  * the exact JobAdder route contract (URLs, methods, endpoints, guards);
  * the read-only proxy routes (api_info / search_candidate / lists /
    get_candidate) authenticated and unauthenticated behaviour;
  * that every unsafe write route rejects an unauthenticated request with 401
    before touching the transport, leaving the critical-write counter balanced.
"""

import os
from pathlib import Path
import tempfile
import unittest

_MODULE_TEMPORARY = tempfile.TemporaryDirectory(
    prefix="cvstudio-phase7b-jobadder-"
)
_ORIGINAL_DATABASE_OVERRIDE = os.environ.get("CVSTUDIO_DB_PATH")
os.environ["CVSTUDIO_DB_PATH"] = str(
    Path(_MODULE_TEMPORARY.name) / "state" / "cv_studio.sqlite3"
)
from owner_build_tools.build_protected import write_test_receipt

write_test_receipt(Path(__file__).resolve().parents[1])
try:
    import app
finally:
    if _ORIGINAL_DATABASE_OVERRIDE is None:
        os.environ.pop("CVSTUDIO_DB_PATH", None)
    else:
        os.environ["CVSTUDIO_DB_PATH"] = _ORIGINAL_DATABASE_OVERRIDE


# Routes whose behaviour this net exercises directly (exact endpoint + methods).
_CHARACTERIZED_ROUTES = {
    "/jobadder/api_info": ({"GET"}, "jobadder_api_info"),
    "/jobadder/search_candidate": ({"GET"}, "jobadder_search_candidate"),
    "/jobadder/lists": ({"GET"}, "jobadder_lists"),
    "/jobadder/get_candidate": ({"GET"}, "jobadder_get_candidate"),
    "/jobadder/debug_endpoints": ({"GET"}, "jobadder_debug_endpoints"),
    "/jobadder/create_candidate": ({"POST"}, "jobadder_create_candidate"),
    "/jobadder/update_candidate": ({"POST"}, "jobadder_update_candidate"),
    "/jobadder/upload_cv": ({"POST"}, "jobadder_upload_cv"),
    "/jobadder/upload_original_cv": ({"POST"}, "jobadder_upload_original_cv"),
}

_WRITE_ROUTES = (
    "/jobadder/create_candidate",
    "/jobadder/update_candidate",
    "/jobadder/upload_cv",
    "/jobadder/upload_original_cv",
)


class _FakeJobAdderClient:
    """Records transport calls and returns canned responses; never networks."""

    def __init__(self):
        self.json_calls = []
        self.raw_calls = []
        self.json_response = (200, {"items": [], "fake": True})

    def request_json(self, endpoint, **kwargs):
        self.json_calls.append((endpoint, kwargs))
        return self.json_response

    def request_raw(self, url, **kwargs):
        self.raw_calls.append((url, kwargs))

        class _Resp:
            status = 200

        return _Resp()


class Phase7BJobAdderCoverageTests(unittest.TestCase):
    def setUp(self):
        self._orig_refresh = app._ja_refresh_access_token
        self._orig_client = app._JOBADDER_CLIENT
        self._orig_creds = app._ja_creds_store

        self.token = "fake-access-token"
        app._ja_refresh_access_token = lambda force=False: self.token
        self.client_double = _FakeJobAdderClient()
        app._JOBADDER_CLIENT = self.client_double
        app._ja_creds_store = {}
        self.http = app.app.test_client()

    def tearDown(self):
        app._ja_refresh_access_token = self._orig_refresh
        app._JOBADDER_CLIENT = self._orig_client
        app._ja_creds_store = self._orig_creds

    @staticmethod
    def _headers(request_id):
        return {
            "X-CV-Studio-Request": "1",
            "X-CV-Studio-Request-ID": request_id,
        }

    def _unauthenticate(self):
        app._ja_refresh_access_token = lambda force=False: None

    def test_jobadder_route_contract_is_exact(self):
        rules = list(app.app.url_map.iter_rules())
        self.assertEqual(len(rules), 116)
        by_rule = {rule.rule: rule for rule in rules}
        jobadder_rules = [r for r in rules if r.rule.startswith("/jobadder")]
        self.assertEqual(len(jobadder_rules), 26)
        for rule in jobadder_rules:
            self.assertTrue(rule.endpoint)
            self.assertTrue((rule.methods & {"GET", "POST"}) <= {"GET", "POST"})
        for path, (methods, endpoint) in _CHARACTERIZED_ROUTES.items():
            self.assertIn(path, by_rule)
            self.assertEqual(by_rule[path].methods & {"GET", "POST"}, methods)
            self.assertEqual(by_rule[path].endpoint, endpoint)
        self.assertEqual(
            [item.__name__ for item in app.app.before_request_funcs.get(None, [])],
            [
                "_assign_cvstudio_request_id",
                "_reject_declared_oversize_request",
                "_reject_non_local_host_header",
                "_require_ai_spend_browser_session",
                "_reject_cross_site_unsafe_request",
            ],
        )

    def test_read_proxies_require_authentication(self):
        self._unauthenticate()
        h = self._headers("phase7b-ja-read-401")
        self.assertEqual(
            self.http.get("/jobadder/search_candidate?email=a@b.com", headers=h).status_code,
            401,
        )
        self.assertEqual(
            self.http.get("/jobadder/lists?name=worktype", headers=h).status_code, 401
        )
        # get_candidate/debug_endpoints fold the missing token into a 400
        # "need token and id" contract rather than a bare 401.
        self.assertEqual(
            self.http.get("/jobadder/get_candidate?candidate_id=5", headers=h).status_code,
            400,
        )
        self.assertEqual(
            self.http.get("/jobadder/debug_endpoints?candidate_id=5", headers=h).status_code,
            400,
        )
        self.assertEqual(self.client_double.json_calls, [])
        self.assertEqual(self.client_double.raw_calls, [])

    def test_search_candidate_passes_quoted_email_and_returns_payload(self):
        self.client_double.json_response = (200, {"items": [{"candidateId": 7}]})
        response = self.http.get(
            "/jobadder/search_candidate?email=a%2Bb@example.com",
            headers=self._headers("phase7b-ja-search"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"items": [{"candidateId": 7}]})
        self.assertEqual(len(self.client_double.json_calls), 1)
        endpoint, kwargs = self.client_double.json_calls[0]
        self.assertTrue(endpoint.startswith("candidates?email="))
        self.assertIn("%2B", endpoint)  # '+' stays percent-encoded in the query
        self.assertEqual(kwargs.get("token"), self.token)

    def test_lists_maps_worktype_and_rejects_invalid_name(self):
        self.client_double.json_response = (200, {"items": ["a"]})
        ok = self.http.get(
            "/jobadder/lists?name=worktype", headers=self._headers("phase7b-ja-lists")
        )
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(self.client_double.json_calls[0][0], "worktypes")

        invalid = self.http.get(
            "/jobadder/lists?name=bad name!",
            headers=self._headers("phase7b-ja-lists-bad"),
        )
        self.assertEqual(invalid.status_code, 400)

    def test_get_candidate_returns_payload_and_requires_id(self):
        self.client_double.json_response = (200, {"candidateId": 9})
        ok = self.http.get(
            "/jobadder/get_candidate?candidate_id=9",
            headers=self._headers("phase7b-ja-get"),
        )
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.get_json(), {"candidateId": 9})
        self.assertEqual(self.client_double.json_calls[0][0], "candidates/9")

        missing = self.http.get(
            "/jobadder/get_candidate", headers=self._headers("phase7b-ja-get-missing")
        )
        self.assertEqual(missing.status_code, 400)

    def test_api_info_returns_public_info_shape_when_disconnected(self):
        response = self.http.get(
            "/jobadder/api_info", headers=self._headers("phase7b-ja-info")
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(
            set(payload),
            {
                "api_url",
                "connected",
                "expires_at",
                "client_id",
                "needs_reconnect",
                "client_secret_configured",
                "account_cache_namespace",
                "storage",
            },
        )
        self.assertFalse(payload["connected"])

    def test_write_routes_reject_unauthenticated_without_touching_transport(self):
        self._unauthenticate()
        for path in _WRITE_ROUTES:
            response = self.http.post(
                path,
                json={"firstName": "Should", "lastName": "NotWrite"},
                headers=self._headers("phase7b-ja-write-401"),
            )
            self.assertEqual(response.status_code, 401, path)
        # No transport call happened, and the critical-write guard is balanced.
        self.assertEqual(self.client_double.json_calls, [])
        self.assertEqual(self.client_double.raw_calls, [])
        self.assertEqual(app._ja_critical_writes_active, 0)


if __name__ == "__main__":
    unittest.main()
