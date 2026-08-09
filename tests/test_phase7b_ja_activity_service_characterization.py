"""Characterization tests for JaActivityDiagnosticService.

The read-only OAuth GET probe and the single controlled OAuth POST probe were
moved verbatim out of the ``app.py`` shell into ``cvstudio_ja_activity`` with
their JobAdder dependencies injected. These tests drive both probes through a
fake client - previously impossible, since the shell versions reached straight
for ``_JOBADDER_CLIENT`` and the credential store - and lock every branch:
success, HTTP error, network error, and the not-authenticated guard.
"""

import io
import urllib.error
import unittest

from cvstudio_ja_activity import JaActivityDiagnosticService
from cvstudio_clients import ExternalServiceError


class _FakeResponse:
    def __init__(self, body=b"", status=200, headers=None):
        self.body = body
        self.status = status
        self.headers = headers or {}


def _http_error(code=422, body=b'{"error":"bad"}', headers=None):
    return urllib.error.HTTPError(
        url="https://api.test/v2/candidates/1/activities",
        code=code,
        msg="Unprocessable Entity",
        hdrs=headers or {"X-Trace": "abc", "Set-Cookie": "s=1"},
        fp=io.BytesIO(body),
    )


def _make_service(request_raw, *, get_token="tok-get", post_token="tok-post"):
    calls = {}

    def _record(*a, **k):
        calls["args"] = a
        calls["kwargs"] = k
        return request_raw(*a, **k)

    svc = JaActivityDiagnosticService(
        access_token_provider=lambda: get_token,
        refresh_access_token=lambda force=False: post_token,
        api_url=lambda path: "https://api.test/v2/" + path,
        request_raw=_record,
    )
    return svc, calls


class GetProbeTests(unittest.TestCase):
    def test_success_parses_json_and_redacts_headers(self):
        resp = _FakeResponse(b'{"items":[{"activityId":5}]}', 200,
                             {"Content-Type": "application/json", "Set-Cookie": "x=1"})
        svc, calls = _make_service(lambda *a, **k: resp)
        out = svc.get("candidates/1/activities")
        self.assertTrue(out["ok"])
        self.assertEqual(out["method"], "GET")
        self.assertEqual(out["status"], 200)
        self.assertEqual(out["url"], "https://api.test/v2/candidates/1/activities")
        self.assertEqual(out["response_json"], {"items": [{"activityId": 5}]})
        self.assertEqual(out["response_headers"], {"Content-Type": "application/json"})
        # GET uses the plain access token, not the refresh token
        self.assertEqual(calls["kwargs"]["token"], "tok-get")
        self.assertEqual(calls["kwargs"]["method"], "GET")

    def test_http_error_branch(self):
        def _raise(*a, **k):
            raise _http_error(code=404, body=b"not found")
        svc, _ = _make_service(_raise)
        out = svc.get("candidates/1/activities")
        self.assertFalse(out["ok"])
        self.assertEqual(out["status"], 404)
        self.assertEqual(out["response_body"], "not found")
        self.assertNotIn("Set-Cookie", out["response_headers"])
        self.assertEqual(out["response_headers"].get("X-Trace"), "abc")

    def test_network_error_branch(self):
        def _raise(*a, **k):
            raise urllib.error.URLError("connection refused")
        svc, _ = _make_service(_raise)
        out = svc.get("candidates/1/activities")
        self.assertFalse(out["ok"])
        self.assertIsNone(out["status"])
        self.assertIn("network_error", out)

    def test_external_service_error_branch(self):
        def _raise(*a, **k):
            raise ExternalServiceError("jobadder", "upstream boom", detail="safe detail")
        svc, _ = _make_service(_raise)
        out = svc.get("candidates/1/activities")
        self.assertFalse(out["ok"])
        self.assertIsNone(out["status"])
        self.assertEqual(out["network_error"], "safe detail")

    def test_not_authenticated_raises(self):
        svc, _ = _make_service(lambda *a, **k: _FakeResponse(), get_token="")
        with self.assertRaises(PermissionError):
            svc.get("candidates/1/activities")


class PostProbeTests(unittest.TestCase):
    def test_success_includes_request_payload_and_uses_refresh_token(self):
        resp = _FakeResponse(b'{"activityId":9}', 201, {"Location": "/v2/activities/9"})
        svc, calls = _make_service(lambda *a, **k: resp)
        out = svc.post("candidates/1/activities", {"actionName": "Screening"}, timeout=30)
        self.assertTrue(out["ok"])
        self.assertEqual(out["method"], "POST")
        self.assertEqual(out["status"], 201)
        self.assertEqual(out["request_payload"], {"actionName": "Screening"})
        self.assertEqual(out["response_json"], {"activityId": 9})
        # POST uses the refreshed token and never retries
        self.assertEqual(calls["kwargs"]["token"], "tok-post")
        self.assertEqual(calls["kwargs"]["method"], "POST")
        self.assertEqual(calls["kwargs"]["safe_to_retry"], False)
        self.assertEqual(calls["kwargs"]["retries"], 0)

    def test_http_error_branch_keeps_payload(self):
        def _raise(*a, **k):
            raise _http_error(code=500, body=b'{"m":"server"}')
        svc, _ = _make_service(_raise)
        out = svc.post("candidates/1/activities", {"a": 1})
        self.assertFalse(out["ok"])
        self.assertEqual(out["status"], 500)
        self.assertEqual(out["request_payload"], {"a": 1})
        self.assertEqual(out["response_json"], {"m": "server"})
        self.assertNotIn("Set-Cookie", out["response_headers"])

    def test_network_error_branch(self):
        def _raise(*a, **k):
            raise ExternalServiceError("jobadder", "boom", detail="redacted")
        svc, _ = _make_service(_raise)
        out = svc.post("candidates/1/activities", {"a": 1})
        self.assertFalse(out["ok"])
        self.assertIsNone(out["status"])
        self.assertEqual(out["network_error"], "redacted")

    def test_not_authenticated_raises(self):
        svc, _ = _make_service(lambda *a, **k: _FakeResponse(), post_token="")
        with self.assertRaises(PermissionError):
            svc.post("candidates/1/activities", {"a": 1})


if __name__ == "__main__":
    unittest.main()
