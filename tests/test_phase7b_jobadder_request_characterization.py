"""Characterization tests for the low-level JobAdder request layer.

Locks the behaviour of the helpers extracted into ``cvstudio_jobadder_request``:
the pure ``_ja_normalize_api_base`` URL guard and the JSON convenience wrappers
(which reach the network only through the injected client callable). These are a
verbatim move from the legacy web shell, so every assertion below equally
describes the pre-extraction ``app.py`` behaviour.
"""

import unittest

import cvstudio_jobadder_request as jr


class NormalizeApiBaseTests(unittest.TestCase):
    def test_empty_falls_back_to_documented_endpoint(self):
        self.assertEqual(jr._ja_normalize_api_base(""), "https://api.jobadder.com/v2")
        self.assertEqual(jr._ja_normalize_api_base(None), "https://api.jobadder.com/v2")

    def test_keeps_tenant_specific_jobadder_https_host(self):
        self.assertEqual(
            jr._ja_normalize_api_base("  https://api.au3.jobadder.com/v2/  "),
            "https://api.au3.jobadder.com/v2",
        )
        self.assertEqual(
            jr._ja_normalize_api_base("https://foo.jobadder.com/v2/x"),
            "https://foo.jobadder.com/v2/x",
        )

    def test_appends_v2_when_path_missing(self):
        self.assertEqual(jr._ja_normalize_api_base("https://api.jobadder.com"), "https://api.jobadder.com/v2")

    def test_lowercases_host(self):
        self.assertEqual(jr._ja_normalize_api_base("https://JOBADDER.COM"), "https://jobadder.com/v2")

    def test_rejects_non_https_and_non_jobadder_and_lookalike_hosts(self):
        self.assertEqual(jr._ja_normalize_api_base("http://evil.com/v2"), "https://api.jobadder.com/v2")
        self.assertEqual(jr._ja_normalize_api_base("https://evil.com/v2"), "https://api.jobadder.com/v2")
        # a lookalike suffix must not be treated as a JobAdder host
        self.assertEqual(jr._ja_normalize_api_base("https://api.jobadder.com.evil.com/v2"), "https://api.jobadder.com/v2")


class JsonWrapperTests(unittest.TestCase):
    def setUp(self):
        self._saved = jr._request_json
        self.calls = []
        jr.bind_jobadder_request_client(self._record)

    def tearDown(self):
        jr._request_json = self._saved

    def _record(self, *a, **k):
        self.calls.append((a, k))
        return {"ok": True}

    def test_get_json_shape(self):
        out = jr._ja_get_json("candidates/1", timeout=9)
        self.assertEqual(out, {"ok": True})
        (args, kw) = self.calls[-1]
        self.assertEqual(args, ("candidates/1",))
        self.assertEqual(kw["method"], "GET")
        self.assertEqual(kw["timeout"], 9)
        self.assertTrue(kw["raw_fallback"])
        self.assertEqual(kw["headers"], {"Accept": "application/json"})

    def test_post_json_is_non_retrying_with_body(self):
        jr._ja_post_json("candidates/1/activities", {"a": 1}, timeout=5)
        (_args, kw) = self.calls[-1]
        self.assertEqual(kw["method"], "POST")
        self.assertEqual(kw["timeout"], 5)
        self.assertIs(kw["safe_to_retry"], False)
        self.assertEqual(kw["retries"], 0)
        self.assertEqual(kw["body"], b'{"a": 1}')
        self.assertEqual(kw["headers"]["Content-Type"], "application/json")

    def test_put_json_defaults_to_20s(self):
        jr._ja_put_json("candidates/1", {"b": 2})
        (_args, kw) = self.calls[-1]
        self.assertEqual(kw["method"], "PUT")
        self.assertEqual(kw["timeout"], 20)
        self.assertIs(kw["safe_to_retry"], False)


if __name__ == "__main__":
    unittest.main()
