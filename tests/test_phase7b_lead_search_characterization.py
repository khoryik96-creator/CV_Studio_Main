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


def _llm_stub_deps():
    """The three LLM-path injected deps, inert for config/collect tests."""
    def _unused_call_llm(*a, **k):  # pragma: no cover - not exercised here
        raise AssertionError("call_llm should not be reached in this test")

    def _unused_cwow(*a, **k):  # pragma: no cover - not exercised here
        raise AssertionError("call_with_optional_web should not be reached")

    return dict(
        call_llm=_unused_call_llm,
        provider_info=lambda: {},
        call_with_optional_web=_unused_cwow,
    )


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


class OrchestratorConfigTests(unittest.TestCase):
    def _orch(self, secret_store=None, **calls):
        defaults = dict(
            secret_store=lambda: (secret_store or {}),
            search_provider_config=lambda raw: orch.search_provider_config(raw),
            search_tavily=lambda *a, **k: [],
            search_serpapi=lambda *a, **k: [],
            search_provider_queries=lambda *a, **k: [],
            **_llm_stub_deps(),
        )
        defaults.update(calls)
        orch = ls.LeadSearchOrchestrator(**defaults)
        return orch

    def test_disabled_when_no_provider(self):
        orch = self._orch()
        cfg = orch.search_provider_config({"provider": "none"})
        self.assertEqual(cfg, {"provider": "none", "api_key": "", "enabled": False})

    def test_unknown_provider_coerced_to_none(self):
        orch = self._orch()
        self.assertEqual(orch.search_provider_config({"provider": "bing"})["provider"], "none")

    def test_inline_key_enables_provider(self):
        orch = self._orch()
        cfg = orch.search_provider_config({"provider": "tavily", "api_key": "inline-key"})
        self.assertEqual(cfg, {"provider": "tavily", "api_key": "inline-key", "enabled": True})

    def test_backend_secure_falls_back_to_secret_store(self):
        orch = self._orch(secret_store={"search_serpapi": "stored-key"})
        cfg = orch.search_provider_config({"provider": "serpapi", "api_key": "__BACKEND_SECURE__"})
        self.assertEqual(cfg["api_key"], "stored-key")
        self.assertTrue(cfg["enabled"])

    def test_secret_store_read_is_late_bound(self):
        # Reassigning what the injected callable returns must be picked up.
        store = {"search_tavily": "k1"}
        orch = ls.LeadSearchOrchestrator(
            secret_store=lambda: store,
            search_provider_config=lambda raw: orch.search_provider_config(raw),
            search_tavily=lambda *a, **k: [],
            search_serpapi=lambda *a, **k: [],
            search_provider_queries=lambda *a, **k: [],
            **_llm_stub_deps(),
        )
        self.assertEqual(orch.search_provider_config({"provider": "tavily", "key": ""})["api_key"], "k1")
        store["search_tavily"] = "k2"
        self.assertEqual(orch.search_provider_config({"provider": "tavily", "key": ""})["api_key"], "k2")


class OrchestratorCollectTests(unittest.TestCase):
    def _orch(self, **overrides):
        defaults = dict(
            secret_store=lambda: {},
            search_provider_config=lambda raw: {"provider": "tavily", "api_key": "k", "enabled": True},
            search_tavily=lambda *a, **k: [],
            search_serpapi=lambda *a, **k: [],
            search_provider_queries=lambda *a, **k: ["q1", "q2"],
            **_llm_stub_deps(),
        )
        defaults.update(overrides)
        return ls.LeadSearchOrchestrator(**defaults)

    def test_disabled_config_short_circuits(self):
        orch = self._orch(search_provider_config=lambda raw: {"provider": "none", "enabled": False})
        self.assertEqual(orch.collect_search_provider_results({}, [], [], []), ([], []))

    def test_dedupes_by_url_then_title(self):
        batches = iter([
            [{"url": "https://a.example/1", "title": "A"}, {"url": "https://a.example/1/", "title": "dupe"}],
            [{"url": "", "title": "A"}],  # title "a" already seen via first item's url? no -> new key "a"
        ])
        orch = self._orch(search_tavily=lambda *a, **k: next(batches))
        results, warnings = orch.collect_search_provider_results({}, [], [], [])
        urls = [r.get("url") for r in results]
        # Trailing-slash duplicate collapsed; distinct title-only item kept.
        self.assertEqual(urls, ["https://a.example/1", ""])
        self.assertEqual(warnings, [])

    def test_provider_exception_is_captured_as_warning(self):
        def boom(*a, **k):
            raise RuntimeError("tavily down")
        orch = self._orch(search_tavily=boom)
        results, warnings = orch.collect_search_provider_results({}, [], [], [])
        self.assertEqual(results, [])
        self.assertEqual(len(warnings), 2)  # one per query
        self.assertIn("tavily query failed: tavily down", warnings[0])

    def test_serpapi_provider_dispatch(self):
        called = {}
        def serp(*a, **k):
            called["hit"] = True
            return [{"url": "https://s.example", "title": "S"}]
        orch = self._orch(
            search_provider_config=lambda raw: {"provider": "serpapi", "api_key": "k", "enabled": True},
            search_serpapi=serp,
            search_provider_queries=lambda *a, **k: ["q1"],
        )
        results, _ = orch.collect_search_provider_results({}, [], [], [])
        self.assertTrue(called.get("hit"))
        self.assertEqual(results[0]["url"], "https://s.example")


class OrchestratorCallWithOptionalWebTests(unittest.TestCase):
    def _orch(self, call_llm, provider_info=None):
        return ls.LeadSearchOrchestrator(
            secret_store=lambda: {},
            search_provider_config=lambda raw: {},
            search_tavily=lambda *a, **k: [],
            search_serpapi=lambda *a, **k: [],
            search_provider_queries=lambda *a, **k: [],
            call_llm=call_llm,
            provider_info=lambda: (provider_info or {"anthropic": {"supports_web_search": True}}),
            call_with_optional_web=lambda *a, **k: None,
        )

    def test_happy_path_returns_data_and_no_warning(self):
        orch = self._orch(lambda provider, key, payload: {"content": [{"type": "text", "text": "ok"}]})
        data, warning = orch.call_with_optional_web("k", {"model": "m", "messages": []}, provider="anthropic")
        self.assertEqual(data["content"][0]["text"], "ok")
        self.assertEqual(warning, "")

    def test_provider_without_web_search_and_tools_degrades_upfront(self):
        calls = []
        def fake(provider, key, payload):
            calls.append(payload)
            return {"content": [{"type": "text", "text": "no-web"}]}
        orch = self._orch(fake, provider_info={"deepseek": {"supports_web_search": False}})
        data, warning = orch.call_with_optional_web(
            "k", {"model": "m", "messages": [], "tools": [{"type": "web_search"}]}, provider="deepseek"
        )
        # tools stripped for the no-web fallback call.
        self.assertNotIn("tools", calls[0])
        self.assertTrue(warning)  # actionable message surfaced

    def test_timeout_with_graceful_json_returns_fake_response(self):
        def boom(*a, **k):
            raise TimeoutError("slow")
        orch = self._orch(boom)
        graceful = {"summary": {}, "companies": [], "people": []}
        data, warning = orch.call_with_optional_web("k", {"messages": []}, graceful_json=graceful)
        # _lead_fake_anthropic_response wraps graceful JSON as a content block.
        self.assertIn("content", data)
        self.assertTrue(warning)

    def test_timeout_without_graceful_raises(self):
        def boom(*a, **k):
            raise TimeoutError("slow")
        orch = self._orch(boom)
        with self.assertRaises(TimeoutError):
            orch.call_with_optional_web("k", {"messages": []}, graceful_json=None)


class OrchestratorExtractAndQuickTests(unittest.TestCase):
    def _orch(self, **overrides):
        d = dict(
            secret_store=lambda: {},
            search_provider_config=lambda raw: {"provider": "tavily", "api_key": "k", "enabled": True},
            search_tavily=lambda *a, **k: [],
            search_serpapi=lambda *a, **k: [],
            search_provider_queries=lambda *a, **k: [],
            call_llm=lambda *a, **k: {"content": [{"type": "text", "text": "{}"}], "usage": {}},
            provider_info=lambda: {},
            call_with_optional_web=lambda *a, **k: ({"content": [{"type": "text", "text": "{}"}]}, ""),
        )
        d.update(overrides)
        return ls.LeadSearchOrchestrator(**d)

    def test_extract_empty_provider_results_short_circuits(self):
        orch = self._orch()
        out = orch.extract_from_search_provider_results(
            "k", "m", {}, [], ["MY"], [], [], "", "", "", "", company_n=5
        )
        self.assertEqual(out, ({"summary": {}, "companies": [], "people": []}, "", {}))

    def test_extract_calls_llm_and_annotates_summary(self):
        seen = {}
        def fake_llm(provider, key, payload):
            seen["provider"] = provider
            return {"content": [{"type": "text", "text": '{"companies":[],"people":[]}'}], "usage": {"input_tokens": 1}}
        orch = self._orch(call_llm=fake_llm)
        parsed, warning, usage = orch.extract_from_search_provider_results(
            "k", "m", {"provider": "tavily"}, [{"title": "T", "url": "u"}], ["MY"],
            ["src"], ["angle"], "role", "ind", "ctx", "cv", company_n=5, llm_provider="anthropic",
        )
        self.assertEqual(seen["provider"], "anthropic")
        self.assertEqual(parsed["summary"]["search_provider_used"], "tavily")
        self.assertEqual(parsed["summary"]["search_provider_results_seen"], 1)
        self.assertEqual(usage, {"input_tokens": 1})

    def test_quick_delegates_to_call_with_optional_web(self):
        captured = {}
        def fake_cwow(api_key, payload, warning_prefix="", graceful_json=None, provider="anthropic"):
            captured["tools"] = payload.get("tools")
            captured["skip"] = payload.get("_skip_no_web_fallback")
            return {"content": [{"type": "text", "text": '{"companies":[],"people":[]}'}]}, ""
        orch = self._orch(call_with_optional_web=fake_cwow)
        parsed, warning, usage = orch.quick_job_search(
            "k", "m", ["MY"], ["src"], ["angle"], "role", "ind", "ctx", "cv", company_n=3,
        )
        # quick always requests the web-search tool and skips the no-web fallback.
        self.assertTrue(captured["tools"])
        self.assertTrue(captured["skip"])
        self.assertEqual(parsed["people"], [])


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
