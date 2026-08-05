"""Characterization tests for the Lead Finder search-provider HTTP primitives.

Locks the behaviour of the certifi-aware SSL context and the Tavily / SerpAPI
result normalisers extracted into ``cvstudio_lead_search`` (Phase 7B). These are
a verbatim move, so the assertions equally describe the legacy web-shell
behaviour. The network boundary (``_lead_fetch_json_url``) is stubbed so no
socket is opened and no credentials are used.
"""

import unittest
from unittest import mock

import cvstudio_lead_search as ls


class SslContextTests(unittest.TestCase):
    def test_returns_context_when_certifi_present(self):
        sentinel = object()
        with mock.patch.object(ls, "certifi") as fake_certifi, mock.patch.object(
            ls.ssl, "create_default_context", return_value=sentinel
        ) as create:
            fake_certifi.where.return_value = "/fake/cacert.pem"
            self.assertIs(ls._lead_ssl_context(), sentinel)
        create.assert_called_once_with(cafile="/fake/cacert.pem")

    def test_returns_none_when_certifi_absent(self):
        with mock.patch.object(ls, "certifi", None):
            self.assertIsNone(ls._lead_ssl_context())

    def test_returns_none_when_context_creation_raises(self):
        with mock.patch.object(ls, "certifi") as fake_certifi, mock.patch.object(
            ls.ssl, "create_default_context", side_effect=Exception("boom")
        ):
            fake_certifi.where.return_value = "/fake/cacert.pem"
            self.assertIsNone(ls._lead_ssl_context())


class TavilyNormaliserTests(unittest.TestCase):
    def test_maps_results_to_lead_shape(self):
        raw = {
            "results": [
                {
                    "title": "  Data Engineer  ",
                    "url": " https://acme.example/jobs/1 ",
                    "content": "Build pipelines",
                    "published_date": "2026-08-01",
                },
                "not-a-dict",
            ]
        }
        with mock.patch.object(ls, "_lead_fetch_json_url", return_value=raw) as fetch:
            out = ls._lead_search_tavily("key", "data engineer", max_results=6, timeout=16)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["title"], "Data Engineer")
        self.assertEqual(out[0]["url"], "https://acme.example/jobs/1")
        self.assertEqual(out[0]["snippet"], "Build pipelines")
        self.assertEqual(out[0]["provider"], "tavily")
        self.assertEqual(out[0]["query"], "data engineer")
        # Bearer auth header and clamped max_results.
        _, kwargs = fetch.call_args
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer key")
        self.assertEqual(kwargs["data"]["max_results"], 6)

    def test_snippet_falls_back_to_snippet_key(self):
        raw = {"results": [{"title": "T", "url": "u", "snippet": "from-snippet"}]}
        with mock.patch.object(ls, "_lead_fetch_json_url", return_value=raw):
            out = ls._lead_search_tavily("key", "q")
        self.assertEqual(out[0]["snippet"], "from-snippet")

    def test_max_results_is_clamped_to_ten(self):
        with mock.patch.object(ls, "_lead_fetch_json_url", return_value={"results": []}) as fetch:
            ls._lead_search_tavily("key", "q", max_results=999)
        self.assertEqual(fetch.call_args.kwargs["data"]["max_results"], 10)


class SerpapiNormaliserTests(unittest.TestCase):
    def test_structured_google_jobs_result_preferred(self):
        jobs = {
            "jobs_results": [
                {
                    "title": "Backend Engineer",
                    "company_name": "Acme",
                    "location": "Remote",
                    "description": "Go and Postgres",
                    "detected_extensions": {"posted_at": "2 days ago"},
                    "apply_options": [
                        {"title": "Acme Careers", "link": "https://acme.example/careers/backend"},
                    ],
                }
            ]
        }
        with mock.patch.object(ls, "_lead_fetch_json_url", return_value=jobs), mock.patch.object(
            ls, "_lead_is_direct_job_url", return_value=True
        ):
            out = ls._lead_search_serpapi("key", "backend engineer")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["provider"], "serpapi_google_jobs")
        self.assertEqual(out[0]["company_name"], "Acme")
        self.assertEqual(out[0]["url"], "https://acme.example/careers/backend")
        self.assertEqual(out[0]["published_date"], "2 days ago")
        self.assertTrue(out[0]["structured_job_result"])

    def test_google_apply_links_are_skipped(self):
        jobs = {
            "jobs_results": [
                {
                    "title": "Role",
                    "company_name": "Acme",
                    "apply_options": [
                        {"title": "Google", "link": "https://www.google.com/search?q=role"},
                    ],
                    "related_links": [{"link": "https://acme.example/role"}],
                }
            ]
        }
        with mock.patch.object(ls, "_lead_fetch_json_url", return_value=jobs), mock.patch.object(
            ls, "_lead_is_direct_job_url", return_value=False
        ):
            out = ls._lead_search_serpapi("key", "role")
        # google.com apply link skipped => falls back to related_links url.
        self.assertEqual(out[0]["url"], "https://acme.example/role")

    def test_falls_back_to_organic_when_no_jobs_results(self):
        organic = {"organic_results": [{"title": "Org", "link": "https://x.example", "snippet": "s", "date": "2026-08-01"}]}
        # First call (google_jobs) returns empty jobs; second (organic) returns hits.
        with mock.patch.object(ls, "_lead_fetch_json_url", side_effect=[{"jobs_results": []}, organic]):
            out = ls._lead_search_serpapi("key", "q")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["provider"], "serpapi")
        self.assertEqual(out[0]["url"], "https://x.example")

    def test_jobs_exception_falls_through_to_organic(self):
        organic = {"organic_results": [{"title": "Org", "link": "https://x.example"}]}
        with mock.patch.object(ls, "_lead_fetch_json_url", side_effect=[RuntimeError("jobs boom"), organic]):
            out = ls._lead_search_serpapi("key", "q")
        self.assertEqual(out[0]["provider"], "serpapi")


class FetchJsonUrlTests(unittest.TestCase):
    def test_cert_error_is_reraised_with_actionable_message(self):
        err = ls.urllib.error.URLError("CERTIFICATE_VERIFY_FAILED: unable to get local issuer")
        with mock.patch.object(ls.urllib.request, "urlopen", side_effect=err), mock.patch.object(
            ls, "_lead_ssl_context", return_value=None
        ):
            with self.assertRaises(ls.urllib.error.URLError) as ctx:
                ls._lead_fetch_json_url("https://api.example/x")
        self.assertIn("certifi", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
