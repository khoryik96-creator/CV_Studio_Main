"""Tests for AI-provider transient handling and failure reporting.

Create Profile failed with a bare "AI provider request failed / Retry the action".
Two things were wrong. Chargeable AI POSTs were never retried at all, so a single
rate-limit answer ended the run; and the message named neither the provider nor what it
answered, so a rate limit, an outage and an oversized request all read identically.
"""

import json
import os
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent))
import tempfile
import unittest

from cvstudio_clients import (
    AIProviderClient,
    ExternalResponse,
    ExternalServiceError,
    ExternalServiceHTTPError,
)

_MODULE_TEMPORARY = tempfile.TemporaryDirectory(prefix="cvstudio-ai-retry-")
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


class _FakeTransport:
    """Raise the queued statuses in order, then answer successfully."""

    def __init__(self, statuses, retry_after="1"):
        self.statuses = list(statuses)
        self.retry_after = retry_after
        self.calls = 0

    def request(self, service, url, **kwargs):
        self.calls += 1
        if self.statuses:
            raise ExternalServiceHTTPError(
                "ai_provider",
                url,
                self.statuses.pop(0),
                "upstream rejected",
                {"Retry-After": self.retry_after},
                b'{"error": {"message": "rate limit"}}',
            )
        return ExternalResponse(
            200, {}, json.dumps({"content": [{"text": "ok"}]}).encode("utf-8"), url
        )


class ProviderRejectionRetryTests(unittest.TestCase):
    def _client(self, statuses, retry_after="1"):
        transport = _FakeTransport(statuses, retry_after)
        delays = []
        client = AIProviderClient(
            transport=transport, sleeper=lambda delay: delays.append(delay)
        )
        return client, transport, delays

    def test_rate_limit_is_retried_until_it_succeeds(self):
        for statuses, expected_calls in (([429], 2), ([429, 429], 3), ([529], 2)):
            with self.subTest(statuses=statuses):
                client, transport, _delays = self._client(statuses)
                result = client.request("anthropic", "<fixture-credential>", {"model": "m"})
                self.assertEqual(result["content"][0]["text"], "ok")
                self.assertEqual(transport.calls, expected_calls)

    def test_retry_is_bounded_and_the_failure_still_surfaces(self):
        client, transport, _delays = self._client([429, 429, 429, 429])
        with self.assertRaises(ExternalServiceHTTPError) as caught:
            client.request("anthropic", "<fixture-credential>", {"model": "m"})
        self.assertEqual(caught.exception.code, 429)
        self.assertEqual(transport.calls, 3)

    def test_retry_after_is_honoured_and_clamped(self):
        client, _transport, delays = self._client([429], retry_after="9")
        client.request("anthropic", "<fixture-credential>", {"model": "m"})
        self.assertEqual(delays, [9.0])

        client, _transport, delays = self._client([429], retry_after="9999")
        client.request("anthropic", "<fixture-credential>", {"model": "m"})
        self.assertEqual(delays, [30.0])

        client, _transport, delays = self._client([429], retry_after="")
        client.request("anthropic", "<fixture-credential>", {"model": "m"})
        self.assertEqual(delays, [1.0])

    def test_an_ambiguous_or_fatal_status_is_never_retried(self):
        # A 500 or 503 may have been answered after the model already ran, and an auth
        # failure will not fix itself. Re-sending a chargeable call on a maybe is worse
        # than surfacing the failure.
        for status in (500, 502, 503, 504, 400, 401, 402, 422):
            with self.subTest(status=status):
                client, transport, delays = self._client([status])
                with self.assertRaises(ExternalServiceHTTPError):
                    client.request("anthropic", "<fixture-credential>", {"model": "m"})
                self.assertEqual(transport.calls, 1)
                self.assertEqual(delays, [])


class FailureReportTests(unittest.TestCase):
    def test_message_names_the_provider_and_what_it_answered(self):
        for status, provider, expected in (
            (429, "anthropic", "Anthropic returned 429 - rate limit reached"),
            (529, "anthropic", "Anthropic returned 529 - provider overloaded"),
            (503, "deepseek", "DeepSeek returned 503 - provider temporarily unavailable"),
            (504, "openai", "OpenAI returned 504 - provider timed out"),
        ):
            with self.subTest(status=status):
                message, reported = app._llm_failure_report(
                    ExternalServiceError(
                        "ai_provider", "AI provider request failed", status=status
                    ),
                    provider,
                )
                self.assertEqual(reported, status)
                self.assertIn(expected, message)

    def test_an_ordinary_error_is_left_alone(self):
        message, status = app._llm_failure_report(ValueError("Invalid JSON body"), "anthropic")
        self.assertEqual(message, "Invalid JSON body")
        self.assertEqual(status, 0)

    def test_detail_is_not_duplicated_when_already_present(self):
        error = ExternalServiceError(
            "ai_provider", "Anthropic returned 429 - rate limit reached", status=429
        )
        message, _status = app._llm_failure_report(error, "anthropic")
        self.assertEqual(message.count("returned 429"), 1)

    def test_paid_ai_routes_report_through_the_helper(self):
        import inspect

        for handler in (app.parse_cv, app.blind_cv, app.generate_ai):
            with self.subTest(handler=handler.__name__):
                self.assertIn(
                    "_llm_failure_report(e", inspect.getsource(handler)
                )


if __name__ == "__main__":
    unittest.main()
