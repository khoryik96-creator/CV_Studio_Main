import io
import json
import unittest
import urllib.error

from cvstudio_clients import (
    ExternalServiceError,
    ExternalServiceHTTPError,
    ExternalServiceTransport,
    JobAdderClient,
    bounded_timeout,
    redact_external_headers,
    redact_external_text,
)


class _FakeResponse:
    def __init__(self, payload=b"", *, status=200, headers=None):
        if isinstance(payload, (dict, list)):
            payload = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        elif isinstance(payload, str):
            payload = payload.encode("utf-8")
        self._payload = bytes(payload)
        self.status = int(status)
        self.headers = dict(headers or {})
        self.url = ""

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


def _http_error(status, payload, headers=None):
    if isinstance(payload, (dict, list)):
        payload = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    elif isinstance(payload, str):
        payload = payload.encode("utf-8")
    return urllib.error.HTTPError(
        "https://api.jobadder.com/v2/fixture",
        int(status),
        "fixture failure",
        dict(headers or {}),
        io.BytesIO(payload),
    )


class Phase3ClientFoundationTests(unittest.TestCase):
    def test_timeout_and_redaction_are_bounded_and_recursive_safe(self):
        self.assertEqual(bounded_timeout("invalid", default=20, minimum=2, maximum=60), 20)
        self.assertEqual(bounded_timeout(0, default=20, minimum=2, maximum=60), 2)
        self.assertEqual(bounded_timeout(999, default=20, minimum=2, maximum=60), 60)
        text = redact_external_text(
            "Authorization: Bearer <fixture-credential> "
            "?access_token=<fixture-credential>&safe=1 "
            '"client_secret":"<fixture-credential>"'
        )
        self.assertNotIn("<fixture-credential>", text)
        self.assertIn("Bearer [redacted]", text)
        self.assertIn("access_token=[redacted]", text)
        self.assertIn('"client_secret":"[redacted]"', text)
        self.assertEqual(
            redact_external_headers(
                {"Authorization": "Bearer <fixture-credential>", "Content-Type": "application/json"}
            ),
            {"Authorization": "[redacted]", "Content-Type": "application/json"},
        )

    def test_transport_retries_safe_get_once_and_redacts_final_error(self):
        errors = [
            _http_error(503, {"access_token": "<fixture-credential>", "message": "temporary"}, {"Retry-After": "1"}),
            _http_error(503, {"access_token": "<fixture-credential>", "message": "temporary"}),
        ]
        calls = []
        sleeps = []

        def opener(request_object, **kwargs):
            calls.append((request_object, kwargs))
            raise errors[len(calls) - 1]

        transport = ExternalServiceTransport(opener=opener, sleeper=sleeps.append)
        with self.assertRaises(ExternalServiceHTTPError) as caught:
            transport.request(
                "jobadder",
                "https://api.jobadder.com/v2/fixture",
                allowed_hosts=("jobadder.com",),
                timeout=999,
                timeout_maximum=60,
                retries=1,
            )
        for error in errors:
            error.close()
        self.assertEqual(len(calls), 2)
        self.assertEqual([item[1]["timeout"] for item in calls], [60, 60])
        self.assertEqual(sleeps, [1.0])
        structured = caught.exception.structured()
        self.assertEqual(structured["code"], "JOBADDER_REQUEST_FAILED")
        self.assertEqual(structured["status"], 503)
        self.assertTrue(structured["retryable"])
        self.assertEqual(structured["action"], "retry")
        body = caught.exception.read().decode("utf-8")
        self.assertNotIn("<fixture-credential>", body)
        self.assertIn("[redacted]", body)

    def test_transport_does_not_replay_unsafe_post_or_allow_foreign_host(self):
        error = _http_error(503, {"message": "ambiguous write failure"})
        calls = []

        def opener(request_object, **kwargs):
            calls.append((request_object, kwargs))
            raise error

        transport = ExternalServiceTransport(opener=opener, sleeper=lambda _delay: None)
        with self.assertRaises(ExternalServiceHTTPError) as caught:
            transport.request(
                "jobadder",
                "https://api.jobadder.com/v2/fixture",
                method="POST",
                body=b"{}",
                allowed_hosts=("jobadder.com",),
                safe_to_retry=False,
                retries=2,
            )
        error.close()
        caught.exception.close()
        self.assertEqual(len(calls), 1)

        with self.assertRaises(ExternalServiceError) as blocked:
            transport.request(
                "jobadder",
                "https://example.invalid/v2/fixture",
                allowed_hosts=("jobadder.com",),
            )
        self.assertEqual(blocked.exception.service_code, "JOBADDER_REQUEST_FAILED")
        self.assertEqual(len(calls), 1)

    def test_jobadder_client_refreshes_one_401_and_marks_repeated_rejection(self):
        token_calls = []
        reconnects = []
        requests_seen = []
        first_error = _http_error(401, {"message": "expired"})

        def token_provider(force):
            token_calls.append(bool(force))
            return "<fixture-credential-b>" if force else "<fixture-credential-a>"

        def opener(request_object, **kwargs):
            requests_seen.append((request_object, kwargs))
            if len(requests_seen) == 1:
                raise first_error
            return _FakeResponse({"items": [{"fixture": True}]}, headers={"Content-Type": "application/json"})

        client = JobAdderClient(
            lambda: "https://api.jobadder.com/v2",
            token_provider,
            reconnect_handler=lambda: reconnects.append(True),
            transport=ExternalServiceTransport(opener=opener, sleeper=lambda _delay: None),
        )
        status, payload = client.request_json("candidates", timeout=14)
        first_error.close()
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"items": [{"fixture": True}]})
        self.assertEqual(token_calls, [False, True])
        self.assertEqual(reconnects, [])
        self.assertEqual(
            [item[0].get_header("Authorization") for item in requests_seen],
            ["Bearer <fixture-credential-a>", "Bearer <fixture-credential-b>"],
        )

        repeated_errors = [
            _http_error(401, {"message": "expired"}),
            _http_error(401, {"message": "still expired"}),
        ]
        reconnects.clear()
        retry_calls = []

        def rejecting_opener(request_object, **kwargs):
            retry_calls.append((request_object, kwargs))
            raise repeated_errors[len(retry_calls) - 1]

        client.transport = ExternalServiceTransport(opener=rejecting_opener, sleeper=lambda _delay: None)
        with self.assertRaises(ExternalServiceHTTPError) as caught:
            client.request_raw("candidates")
        for error in repeated_errors:
            error.close()
        caught.exception.close()
        self.assertEqual(len(retry_calls), 2)
        self.assertEqual(reconnects, [True])

    def test_jobadder_offset_paginator_preserves_caps_and_no_progress_diagnostics(self):
        payloads = [
            {"items": [{"fixture": "a"}, {"fixture": "b"}], "totalCount": 4},
            {"items": [{"fixture": "a"}, {"fixture": "b"}], "totalCount": 4},
        ]
        seen_params = []

        def fetch_page(params):
            seen_params.append(list(params))
            return payloads[len(seen_params) - 1]

        client = JobAdderClient(
            lambda: "https://api.jobadder.com/v2",
            lambda _force: "<fixture-credential>",
            transport=ExternalServiceTransport(sleeper=lambda _delay: None),
        )
        items, state = client.paginate_offset(
            "candidates",
            params={"Keywords": "fixture"},
            max_items=4,
            page_size=2,
            parse_page=lambda payload: (payload["items"], payload["totalCount"]),
            item_key=lambda item: item["fixture"],
            fetch_page=fetch_page,
        )
        self.assertEqual(items, payloads[0]["items"])
        self.assertEqual(state["pages"], 2)
        self.assertTrue(state["incomplete"])
        self.assertIn("repeated_page", state["codes"])
        self.assertEqual(
            [[pair for pair in params if pair[0] in ("Offset", "Limit")] for params in seen_params],
            [[("Offset", 0), ("Limit", 2)], [("Offset", 2), ("Limit", 2)]],
        )


if __name__ == "__main__":
    unittest.main()
