import contextlib
import io
import inspect
import json
import os
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent))
from frontend_sources import frontend_source
import tempfile
import unittest
import urllib.error
from unittest import mock


_MODULE_TEMPORARY = tempfile.TemporaryDirectory(prefix="cvstudio-phase5b-characterization-")
_ORIGINAL_DATABASE_OVERRIDE = os.environ.get("CVSTUDIO_DB_PATH")
os.environ["CVSTUDIO_DB_PATH"] = str(
    Path(_MODULE_TEMPORARY.name) / "state" / "cv_studio.sqlite3"
)
from owner_build_tools.build_protected import write_test_receipt
from cvstudio_ai_costs import (
    AI_COST_GUARDRAIL_ENV,
    AICostGuardrailError,
)

write_test_receipt(Path(__file__).resolve().parents[1])
try:
    import app
    from cvstudio_clients import AIProviderClient
finally:
    if _ORIGINAL_DATABASE_OVERRIDE is None:
        os.environ.pop("CVSTUDIO_DB_PATH", None)
    else:
        os.environ["CVSTUDIO_DB_PATH"] = _ORIGINAL_DATABASE_OVERRIDE


_PAID_BROWSER_ROUTE_CONTRACTS = {
    "/test": ({"POST"}, "test_key"),
    "/parse": ({"POST"}, "parse_cv"),
    "/generate-ai": ({"POST"}, "generate_ai"),
    "/blind": ({"POST"}, "blind_cv"),
    "/jobadder/onenote_log_screening": ({"POST"}, "jobadder_onenote_log_screening"),
    "/lead-finder/search": ({"POST"}, "lead_finder_search"),
    "/lead-finder/find-people": ({"POST"}, "lead_finder_find_people"),
    "/lead-finder/find-emails": ({"POST"}, "lead_finder_find_emails"),
    "/salary-comparison/api/rules/preview": ({"POST"}, "salary_comparison.rules_preview_api"),
}

_LEGACY_COST_FIELDS = {
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "prompt_cache_hit_tokens",
    "prompt_cache_miss_tokens",
    "api_calls",
    "usd",
    "model",
    "provider",
    "pricing_model_key",
    "pricing_known",
    "cost_method",
    "rates_per_million_usd",
    "note",
}

_LEGACY_AI_SUCCESS_FIELDS = {
    "/test": {"ok", "usage", "model", "provider", "cost", "cost_details"},
    "/parse": {"ok", "data", "usage", "model", "provider", "cost", "cost_details"},
    "/generate-ai": {"ok", "content", "usage", "model", "provider", "cost", "cost_details"},
    "/blind": {"ok", "data", "usage", "model", "provider", "cost", "cost_details"},
}


class _FailingPaidTransport:
    def __init__(self):
        self.calls = []

    def request(self, service, url, **kwargs):
        self.calls.append((service, url, kwargs))
        raise TimeoutError("fixture ambiguous paid timeout")


class Phase5BAICostCharacterizationTests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()

    @staticmethod
    def _headers(request_id):
        return {
            "X-CV-Studio-Request": "1",
            "X-CV-Studio-Request-ID": request_id,
        }

    def _post_paid(self, path, payload, request_id):
        with mock.patch.object(app, "_ai_spend_session_allowed", return_value=True):
            return self.client.post(
                path,
                json=payload,
                headers=self._headers(request_id),
            )

    def test_onenote_activity_creator_email_reaches_single_official_write(self):
        captured = []

        def post_json(path, payload, timeout=30):
            captured.append((path, payload, timeout))
            return 201, {
                "activityId": 91,
                "createdBy": {"email": "recruiter@example.com"},
            }

        with mock.patch.object(app, "_ja_refresh_access_token", return_value="fixture-token"), mock.patch.object(
            app, "_ja_post_json", side_effect=post_json
        ), mock.patch.object(
            app, "_ja_salary_ai_extract", return_value=({}, {})
        ), mock.patch.object(
            app,
            "_ja_update_candidate_salary_notice",
            return_value={"ok": True, "salary_canonical": {}},
        ):
            response = self._post_paid(
                "/jobadder/onenote_log_screening",
                {
                    "candidate_id": "123",
                    "email": "candidate@example.com",
                    "created_by_email": "recruiter@example.com",
                    "fields": {"presentability_rating": "4"},
                    "note_text": "Presentability: 4/4",
                    "salary_ai": {"enabled": False},
                },
                "phase5b-onenote-created-by",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0][0], "candidates/123/activities")
        self.assertEqual(
            captured[0][1]["createdBy"],
            {"email": "recruiter@example.com"},
        )
        self.assertEqual(
            response.get_json()["creator_attribution_reported"],
            {"email": "recruiter@example.com"},
        )

    def test_onenote_invalid_creator_email_stops_before_jobadder_write(self):
        with mock.patch.object(app, "_ja_refresh_access_token", return_value="fixture-token"), mock.patch.object(
            app, "_ja_post_json"
        ) as post_json:
            response = self._post_paid(
                "/jobadder/onenote_log_screening",
                {
                    "candidate_id": "123",
                    "created_by_email": "not an email",
                    "fields": {"presentability_rating": "4"},
                    "note_text": "Presentability: 4/4",
                },
                "phase5b-onenote-invalid-created-by",
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["field"], "created_by_email")
        post_json.assert_not_called()

    def test_onenote_rejected_creator_email_is_not_retried_without_attribution(self):
        rejected = urllib.error.HTTPError(
            "https://api.jobadder.com/v2/candidates/123/activities",
            422,
            "Unprocessable Entity",
            {},
            io.BytesIO(b'{"message":"createdBy is not supported"}'),
        )
        with mock.patch.object(app, "_ja_refresh_access_token", return_value="fixture-token"), mock.patch.object(
            app, "_ja_post_json", side_effect=rejected
        ) as post_json, mock.patch.object(
            app, "_ja_salary_ai_extract", return_value=({}, {})
        ), mock.patch.object(
            app, "_ja_spa_browser_bridge", return_value={"script": "manual-only"}
        ):
            response = self._post_paid(
                "/jobadder/onenote_log_screening",
                {
                    "candidate_id": "123",
                    "created_by_email": "recruiter@example.com",
                    "fields": {"presentability_rating": "4"},
                    "note_text": "Presentability: 4/4",
                    "salary_ai": {"enabled": False},
                },
                "phase5b-onenote-rejected-created-by",
            )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(post_json.call_count, 1)
        payload = response.get_json()
        self.assertEqual(
            payload["creator_attribution_requested"],
            {"email": "recruiter@example.com"},
        )
        self.assertIn("did not retry without it", payload["next_step"])

    def test_paid_route_helper_confirmation_and_global_guard_inventory(self):
        rules = {rule.rule: rule for rule in app.app.url_map.iter_rules()}
        self.assertEqual(len(rules), 116)
        self.assertEqual(app._AI_SPEND_EXACT_PATHS, frozenset(_PAID_BROWSER_ROUTE_CONTRACTS))
        for path, (methods, endpoint) in _PAID_BROWSER_ROUTE_CONTRACTS.items():
            self.assertEqual(rules[path].methods & {"GET", "POST"}, methods)
            self.assertEqual(rules[path].endpoint, endpoint)

        self.assertEqual(rules["/owner/integration/run"].endpoint, "owner_integration_run")
        self.assertEqual(
            rules["/lead-finder/test-search-provider"].endpoint,
            "lead_finder_test_search_provider",
        )
        self.assertNotIn("/owner/integration/run", app._AI_SPEND_EXACT_PATHS)
        self.assertNotIn("/lead-finder/test-search-provider", app._AI_SPEND_EXACT_PATHS)
        self.assertIn(
            'confirmation != "RUN ONE PAID DEEPSEEK PROBE"',
            inspect.getsource(app._owner_integration_deepseek_probe),
        )
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

    def test_normalized_usage_and_legacy_estimate_fields_are_characterized(self):
        deepseek_usage = app._normalize_llm_usage(
            {
                "prompt_tokens": 120,
                "completion_tokens": 30,
                "prompt_cache_hit_tokens": 80,
                "prompt_cache_miss_tokens": 40,
                "provider_native_counter": 7,
            },
            api_calls=1,
        )
        self.assertEqual(
            {
                key: deepseek_usage[key]
                for key in (
                    "input_tokens",
                    "output_tokens",
                    "prompt_cache_hit_tokens",
                    "prompt_cache_miss_tokens",
                    "api_calls",
                    "provider_native_counter",
                )
            },
            {
                "input_tokens": 120,
                "output_tokens": 30,
                "prompt_cache_hit_tokens": 80,
                "prompt_cache_miss_tokens": 40,
                "api_calls": 1,
                "provider_native_counter": 7,
            },
        )

        deepseek = app._llm_cost_details(
            "deepseek-v4-flash", deepseek_usage, "deepseek"
        )
        self.assertTrue(
            _LEGACY_COST_FIELDS
            | {"unclassified_input_tokens", "billed_cache_miss_tokens"}
            <= set(deepseek)
        )
        self.assertEqual(deepseek["cost_method"], "deepseek_returned_cache_hit_miss_tokens")
        self.assertAlmostEqual(
            deepseek["usd"],
            80 / 1e6 * 0.0028 + 40 / 1e6 * 0.14 + 30 / 1e6 * 0.28,
        )

        conservative = app._llm_cost_details(
            "deepseek-v4-flash",
            {"input_tokens": 120, "output_tokens": 30, "api_calls": 1},
            "deepseek",
        )
        self.assertEqual(
            conservative["cost_method"],
            "deepseek_input_priced_as_cache_miss_no_split_returned",
        )
        self.assertEqual(conservative["billed_cache_miss_tokens"], 120)

        standard = app._llm_cost_details(
            "claude-sonnet-4-6",
            {"input_tokens": 100, "output_tokens": 20, "api_calls": 1},
            "anthropic",
        )
        self.assertTrue(_LEGACY_COST_FIELDS <= set(standard))
        self.assertEqual(standard["cost_method"], "standard_input_output_tokens")
        self.assertAlmostEqual(standard["usd"], 100 / 1e6 * 3 + 20 / 1e6 * 15)

    def test_provider_translation_preserves_established_usage_shape(self):
        translated = app._openai_response_to_anthropic_shape(
            {
                "output_text": "fixture",
                "usage": {
                    "input_tokens": 11,
                    "output_tokens": 4,
                    "input_tokens_details": {"cached_tokens": 3},
                },
            }
        )
        self.assertEqual(translated["content"], [{"type": "text", "text": "fixture"}])
        self.assertEqual(translated["usage"]["input_tokens"], 11)
        self.assertEqual(translated["usage"]["output_tokens"], 4)

        merged = app._merge_llm_usage(
            {"input_tokens": 3, "output_tokens": 2, "api_calls": 1},
            {
                "prompt_tokens": 4,
                "completion_tokens": 1,
                "cache_read_input_tokens": 2,
                "cache_creation_input_tokens": 2,
                "api_calls": 1,
            },
        )
        self.assertEqual(
            merged,
            {
                "input_tokens": 7,
                "output_tokens": 3,
                "prompt_cache_hit_tokens": 2,
                "prompt_cache_miss_tokens": 2,
                "api_calls": 2,
            },
        )

    def test_existing_ai_success_response_fields_are_preserved(self):
        usage = {
            "input_tokens": 10,
            "output_tokens": 4,
            "prompt_cache_hit_tokens": 0,
            "prompt_cache_miss_tokens": 0,
            "api_calls": 1,
        }

        with mock.patch.object(
            app, "_resolve_request_api_key", return_value="sk-ant-fixture"
        ), mock.patch.object(
            app,
            "call_llm",
            return_value={
                "content": [{"type": "text", "text": "OK"}],
                "usage": usage,
            },
        ):
            response = self._post_paid(
                "/test",
                {"provider": "anthropic"},
                "phase5b-test-success",
            )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(_LEGACY_AI_SUCCESS_FIELDS["/test"] <= set(payload))
        self.assertEqual(
            payload["cost_details"]["cost_value_type"],
            "local_estimate",
        )
        self.assertEqual(
            payload["cost_details"]["provider_billing_status"],
            "unavailable",
        )
        self.assertIsNone(
            payload["cost_details"]["provider_authoritative_cost_usd"]
        )

        parsed_data = {
            "candidate": {},
            "work_experiences": [],
            "education": [],
            "certifications": [],
            "skills": [],
        }
        with mock.patch.object(
            app, "_resolve_request_api_key", return_value="<fixture-credential>"
        ), mock.patch.object(
            app,
            "call_llm",
            return_value={
                "content": [{"type": "text", "text": json.dumps(parsed_data)}],
                "usage": usage,
            },
        ):
            response = self._post_paid(
                "/parse",
                {"cv_text": "Fixture CV", "provider": "anthropic"},
                "phase5b-parse-success",
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(_LEGACY_AI_SUCCESS_FIELDS["/parse"] <= set(response.get_json()))

        with mock.patch.object(
            app, "_resolve_request_api_key", return_value="<fixture-credential>"
        ), mock.patch.object(
            app,
            "call_llm",
            return_value={
                "content": [{"type": "text", "text": "fixture content"}],
                "usage": usage,
            },
        ):
            response = self._post_paid(
                "/generate-ai",
                {"prompt": "fixture prompt", "provider": "anthropic"},
                "phase5b-generate-success",
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            _LEGACY_AI_SUCCESS_FIELDS["/generate-ai"] <= set(response.get_json())
        )

        blinded_data = dict(parsed_data, candidate={"name": "[Candidate]"})
        with mock.patch.object(
            app, "_resolve_request_api_key", return_value="<fixture-credential>"
        ), mock.patch.object(
            app,
            "call_llm",
            return_value={
                "content": [{"type": "text", "text": json.dumps(blinded_data)}],
                "usage": usage,
            },
        ), mock.patch.object(
            app, "_blind_postprocess_company_mentions", side_effect=lambda value, _source: value
        ):
            response = self._post_paid(
                "/blind",
                {"cv_data": parsed_data, "provider": "anthropic"},
                "phase5b-blind-success",
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(_LEGACY_AI_SUCCESS_FIELDS["/blind"] <= set(response.get_json()))

    def test_blind_candidate_gender_neutralization_is_explicit_and_opt_in(self):
        parsed_data = {
            "candidate": {"name": "Fixture Candidate"},
            "work_experiences": [
                {
                    "company": "Fixture Company",
                    "roles": [
                        {
                            "title": "Engineer",
                            "bullets": [
                                "She supported her manager while he led the client meeting."
                            ],
                        }
                    ],
                }
            ],
        }
        prompts = []

        def fake_llm(_provider, _api_key, payload):
            prompts.append(payload["system"])
            return {
                "content": [{"type": "text", "text": json.dumps(parsed_data)}],
                "usage": {},
            }

        with mock.patch.object(
            app, "_resolve_request_api_key", return_value="<fixture-credential>"
        ), mock.patch.object(app, "call_llm", side_effect=fake_llm), mock.patch.object(
            app,
            "_blind_postprocess_company_mentions",
            side_effect=lambda value, _source: value,
        ):
            disabled = self._post_paid(
                "/blind",
                {
                    "cv_data": parsed_data,
                    "provider": "anthropic",
                    "neutralize_candidate_gender": False,
                },
                "blind-gender-neutral-disabled",
            )
            enabled = self._post_paid(
                "/blind",
                {
                    "cv_data": parsed_data,
                    "provider": "anthropic",
                    "neutralize_candidate_gender": True,
                },
                "blind-gender-neutral-enabled",
            )

        self.assertEqual(disabled.status_code, 200)
        self.assertEqual(enabled.status_code, 200)
        self.assertEqual(prompts[0], app.BLIND_SYSTEM_PROMPT)
        self.assertNotIn("CANDIDATE GENDER NEUTRALIZATION", prompts[0])
        self.assertIn("CANDIDATE GENDER NEUTRALIZATION", prompts[1])
        self.assertIn('"the candidate will"', prompts[1])
        self.assertIn('"the candidate\'s"', prompts[1])
        self.assertIn("Never leave or introduce they, them, their", prompts[1])
        self.assertIn("managers, colleagues, clients", prompts[1])

    def test_existing_failure_and_salary_processing_fields_are_preserved(self):
        with mock.patch.object(
            app, "_resolve_request_api_key", return_value="<fixture-credential>"
        ), mock.patch.object(
            app, "call_llm", side_effect=TimeoutError("fixture timeout")
        ):
            with contextlib.redirect_stderr(io.StringIO()):
                response = self._post_paid(
                    "/parse",
                    {"cv_text": "Fixture CV", "provider": "anthropic"},
                    "phase5b-parse-failure",
                )
        payload = response.get_json()
        self.assertEqual(response.status_code, 500)
        self.assertTrue(
            {
                "error",
                "paid_ai_failure",
                "usage",
                "model",
                "provider",
                "cost",
                "cost_details",
            }
            <= set(payload)
        )
        self.assertFalse(payload["paid_ai_failure"])
        self.assertEqual(
            payload["paid_call_status"],
            "ambiguous_no_provider_usage_returned",
        )
        self.assertEqual(
            payload["billing_reconciliation"]["reconciliation_status"],
            "ambiguous_provider_charge",
        )
        self.assertIsNone(
            payload["billing_reconciliation"][
                "provider_authoritative_cost_usd"
            ]
        )

        fields = {
            "current_salary_breakdown": "MYR 10,000 monthly",
            "expected_salary": "MYR 12,000 monthly",
        }
        successful_usage = {
            "input_tokens": 50,
            "output_tokens": 10,
            "api_calls": 1,
        }
        with mock.patch.object(
            app, "_ja_salary_ai_cache_get", return_value={}
        ), mock.patch.object(
            app, "_ja_salary_ai_cache_put"
        ), mock.patch.object(
            app,
            "call_llm",
            return_value={
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "current": {
                                    "currency": "MYR",
                                    "baseMonthly": 10000,
                                    "guaranteedSalaryMonths": 12,
                                    "fixedMonthlyAllowance": 0,
                                    "otherFixedMonthlyCash": 0,
                                    "includedEmployerEpf": 0,
                                    "excludedComponents": [],
                                    "evidence": [],
                                    "confidence": "high",
                                },
                                "expected": {
                                    "currency": "MYR",
                                    "explicitAmount": 12000,
                                    "explicitMin": None,
                                    "explicitMax": None,
                                    "sameAsCurrent": False,
                                    "percent": None,
                                    "percentMin": None,
                                    "percentMax": None,
                                    "open": False,
                                    "confidence": "high",
                                },
                            }
                        ),
                    }
                ],
                "usage": successful_usage,
            },
        ):
            components, processing = app._ja_salary_ai_extract(
                fields,
                {
                    "enabled": True,
                    "api_key": "<fixture-credential>",
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-6",
                },
            )
        self.assertIsInstance(components, dict)
        self.assertTrue(
            {
                "fieldExtraction",
                "salaryCalculation",
                "aiAttempted",
                "aiUsed",
                "aiApiCalled",
                "cacheHit",
                "provider",
                "model",
                "inputTokens",
                "outputTokens",
                "totalTokens",
                "apiCalls",
                "promptCacheHitTokens",
                "promptCacheMissTokens",
                "costUsd",
                "pricingKnown",
                "pricingModelKey",
                "costMethod",
                "costReason",
            }
            <= set(processing)
        )
        self.assertEqual(
            processing["costValueType"],
            "local_estimate",
        )
        self.assertEqual(
            processing["providerBillingStatus"],
            "unavailable",
        )
        self.assertIsNone(processing["providerAuthoritativeCostUsd"])
        self.assertEqual(
            processing["reconciliationStatus"],
            "provider_billing_unavailable",
        )

    def test_paid_transport_is_single_attempt_after_ambiguous_timeout(self):
        transport = _FailingPaidTransport()
        client = AIProviderClient(transport=transport)
        with self.assertRaisesRegex(TimeoutError, "ambiguous paid timeout"):
            client.request(
                "anthropic",
                "<fixture-credential>",
                {
                    "model": "claude-sonnet-4-6",
                    "max_tokens": 10,
                    "messages": [{"role": "user", "content": "fixture"}],
                },
                timeout=45,
            )
        self.assertEqual(len(transport.calls), 1)
        _service, _url, kwargs = transport.calls[0]
        self.assertFalse(kwargs["safe_to_retry"])
        self.assertEqual(kwargs["retries"], 0)
        self.assertEqual(kwargs["timeout"], 45)

    def test_central_guardrail_blocks_app_transport_and_authority_reconciles(self):
        request_payload = {
            "model": "claude-sonnet-4-6",
            "max_tokens": 100,
            "messages": [{"role": "user", "content": "fixture"}],
        }
        with mock.patch.dict(
            os.environ,
            {AI_COST_GUARDRAIL_ENV: "0.000001"},
        ), mock.patch.object(app._AI_PROVIDER_CLIENT, "request") as requested:
            with self.assertRaises(AICostGuardrailError):
                app.call_llm(
                    "anthropic",
                    "<fixture-credential>",
                    request_payload,
                )
        requested.assert_not_called()

        provider_response = {
            "content": [{"type": "text", "text": "fixture"}],
            "usage": {"input_tokens": 10, "output_tokens": 2},
            "provider_billing": {
                "authoritative": True,
                "source": "provider_response",
                "scope": "request",
                "currency": "USD",
                "amount": "0.004",
            },
        }
        with mock.patch.dict(
            os.environ,
            {},
            clear=False,
        ), mock.patch.object(
            app._AI_PROVIDER_CLIENT,
            "request",
            return_value=provider_response,
        ):
            os.environ.pop(AI_COST_GUARDRAIL_ENV, None)
            result = app.call_llm(
                "anthropic",
                "<fixture-credential>",
                request_payload,
            )
        details = app._llm_cost_details(
            "claude-sonnet-4-6",
            result["usage"],
            "anthropic",
        )
        self.assertEqual(details["cost_value_type"], "local_estimate")
        self.assertEqual(details["provider_billing_status"], "authoritative")
        self.assertEqual(details["provider_authoritative_cost_usd"], 0.004)
        self.assertEqual(details["reconciliation_status"], "reconciled")
        self.assertNotEqual(
            details["estimated_cost_usd"],
            details["provider_authoritative_cost_usd"],
        )

    def test_malformed_billing_does_not_discard_a_successful_paid_response(self):
        provider_response = {
            "content": [{"type": "text", "text": "fixture"}],
            "usage": {"input_tokens": 10, "output_tokens": 2},
            "provider_billing": {
                "authoritative": True,
                "source": "provider_response",
                "scope": "request",
                "currency": "USD",
                "amount": "malformed",
                "account_token": "<must-not-survive>",
            },
        }
        with mock.patch.dict(
            os.environ,
            {},
            clear=False,
        ), mock.patch.object(
            app._AI_PROVIDER_CLIENT,
            "request",
            return_value=provider_response,
        ):
            os.environ.pop(AI_COST_GUARDRAIL_ENV, None)
            result = app.call_llm(
                "anthropic",
                "<fixture-credential>",
                {
                    "model": "claude-sonnet-4-6",
                    "max_tokens": 100,
                    "messages": [{"role": "user", "content": "fixture"}],
                },
            )

        self.assertEqual(result["content"][0]["text"], "fixture")
        self.assertEqual(result["usage"]["api_calls"], 1)
        self.assertNotIn("provider_billing", result)
        self.assertNotIn("<must-not-survive>", repr(result))
        details = app._llm_cost_details(
            "claude-sonnet-4-6",
            result["usage"],
            "anthropic",
        )
        self.assertEqual(details["provider_billing_status"], "invalid")
        self.assertEqual(
            details["reconciliation_status"],
            "reconciliation_failed",
        )
        self.assertTrue(details["billing_data_invalid"])
        self.assertFalse(details["billing_data_missing"])

    def test_successful_response_without_usage_is_not_a_zero_estimate(self):
        provider_response = {
            "content": [{"type": "text", "text": "fixture"}],
        }
        with mock.patch.dict(
            os.environ,
            {},
            clear=False,
        ), mock.patch.object(
            app._AI_PROVIDER_CLIENT,
            "request",
            return_value=provider_response,
        ):
            os.environ.pop(AI_COST_GUARDRAIL_ENV, None)
            result = app.call_llm(
                "anthropic",
                "<fixture-credential>",
                {
                    "model": "claude-sonnet-4-6",
                    "max_tokens": 100,
                    "messages": [{"role": "user", "content": "fixture"}],
                },
            )

        details = app._llm_cost_details(
            "claude-sonnet-4-6",
            result["usage"],
            "anthropic",
        )
        self.assertEqual(result["usage"]["api_calls"], 1)
        self.assertEqual(details["usd"], 0)
        self.assertIsNone(details["estimated_cost_usd"])
        self.assertEqual(details["usage_validation_status"], "missing")
        self.assertEqual(details["estimate_status"], "usage_unavailable")
        self.assertEqual(
            details["provider_billing_status"],
            "unavailable",
        )

    def test_external_search_failure_is_not_mislabeled_as_an_ai_call(self):
        search_config = {
            "enabled": True,
            "provider": "tavily",
            "api_key": "<fixture-credential>",
        }
        external_error = app.urllib.error.HTTPError(
            "https://example.invalid/search",
            503,
            "fixture search-provider failure",
            {},
            io.BytesIO(b'{"error":{"message":"fixture"}}'),
        )
        with mock.patch.object(
            app,
            "_lead_finder_lock_allowed",
            return_value=True,
        ), mock.patch.object(
            app,
            "_resolve_request_api_key",
            return_value="sk-ant-fixture",
        ), mock.patch.object(
            app,
            "_lead_search_provider_config",
            return_value=search_config,
        ), mock.patch.object(
            app,
            "_lead_collect_search_provider_results",
            side_effect=external_error,
        ), mock.patch.object(
            app._AI_PROVIDER_CLIENT,
            "request",
        ) as ai_request:
            response = self._post_paid(
                "/lead-finder/search",
                {
                    "cv_text": "Fixture CV",
                    "regions": ["Malaysia"],
                    "job_sources": ["Company career pages"],
                    "search_provider": {"provider": "tavily"},
                },
                "phase5b-external-before-ai",
            )
        external_error.close()
        ai_request.assert_not_called()
        payload = response.get_json()
        self.assertEqual(payload["paid_call_status"], "not_called")
        self.assertEqual(
            payload["billing_reconciliation"]["provider_billing_status"],
            "not_applicable",
        )
        self.assertEqual(
            payload["billing_reconciliation"]["reconciliation_status"],
            "not_called",
        )
        self.assertEqual(
            payload["billing_reconciliation"]["provider_billing_status"],
            "not_applicable",
        )
        self.assertFalse(
            payload["billing_reconciliation"]["billing_data_missing"]
        )
        self.assertFalse(
            payload["billing_reconciliation"]["billing_data_missing"]
        )

    def test_apollo_failure_before_ai_is_not_mislabeled_as_an_ai_call(self):
        person = {
            "id": "person-1",
            "name": "Fixture Person",
            "company": "Example",
            "email": "",
        }
        local_error = app.urllib.error.HTTPError(
            "https://example.invalid/cache",
            503,
            "fixture pre-Apollo failure",
            {},
            io.BytesIO(b'{"error":{"message":"fixture"}}'),
        )
        with mock.patch.object(
            app,
            "_lead_finder_lock_allowed",
            return_value=True,
        ), mock.patch.object(
            app,
            "_lead_contact_cache_find",
            side_effect=local_error,
        ), mock.patch.object(
            app,
            "_lead_apollo_enrich_person",
        ) as apollo_request, mock.patch.object(
            app, "_lead_call_with_optional_web"
        ) as ai_request:
            response = self._post_paid(
                "/lead-finder/find-emails",
                {
                    "people": [person],
                    "selected_person_ids": ["person-1"],
                    "enrichment_provider": {
                        "provider": "apollo",
                        "api_key": "<fixture-credential>",
                    },
                },
                "phase5b-apollo-before-ai",
            )
        local_error.close()
        apollo_request.assert_not_called()
        ai_request.assert_not_called()
        payload = response.get_json()
        self.assertEqual(payload["paid_call_status"], "not_called")
        self.assertEqual(
            payload["billing_reconciliation"]["reconciliation_status"],
            "not_called",
        )
        self.assertFalse(
            payload["billing_reconciliation"]["billing_data_missing"]
        )
        self.assertNotIn("external_billing", payload)

    def test_deepseek_history_cutoff_and_non_secret_storage_boundary_are_explicit(self):
        # Frontend JS now lives in vendor/cvstudio/*.js modules; search the
        # combined source (index.html + modules) so moved code is found.
        frontend = frontend_source()
        self.assertIn(
            "Created before v24.6.215; historical cost is preserved but "
            "token/call/cache details cannot be reconstructed.",
            frontend,
        )
        self.assertIn("Estimated AI API token cost only", frontend)
        self.assertIn(
            "missing provider billing remains explicitly unreconciled",
            frontend,
        )
        self.assertIn(
            "Tavily, SerpAPI, Apollo or other third-party credits/fees",
            frontend,
        )
        source = Path(app.__file__).read_text(encoding="utf-8-sig")
        for secret_slot in (
            "main_anthropic",
            "main_deepseek",
            "main_openai",
            "lead_anthropic",
            "lead_deepseek",
            "lead_openai",
            "search_tavily",
            "search_serpapi",
            "enrichment_apollo",
        ):
            self.assertIn(secret_slot, source)

    def test_guardrail_route_failure_owner_probe_and_external_billing_are_visible(self):
        with mock.patch.dict(
            os.environ,
            {AI_COST_GUARDRAIL_ENV: "0.000001"},
        ), mock.patch.object(
            app,
            "_resolve_request_api_key",
            return_value="sk-ant-fixture",
        ), mock.patch.object(
            app._AI_PROVIDER_CLIENT,
            "request",
        ) as requested:
            response = self._post_paid(
                "/test",
                {"provider": "anthropic"},
                "phase5b-guardrail-block",
            )
        requested.assert_not_called()
        payload = response.get_json()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["code"], "AI_COST_GUARDRAIL_BLOCKED")
        self.assertEqual(
            payload["paid_call_status"],
            "blocked_before_provider_transport",
        )
        self.assertEqual(
            payload["billing_reconciliation"]["reconciliation_status"],
            "not_called",
        )

        with mock.patch.dict(
            app._ai_secret_store,
            {"main_deepseek": "<fixture-credential>"},
            clear=False,
        ), mock.patch.object(
            app,
            "_call_deepseek",
            return_value={
                "content": [{"type": "text", "text": "OK"}],
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 10,
                    "prompt_cache_hit_tokens": 20,
                    "prompt_cache_miss_tokens": 80,
                },
            },
        ):
            result = app._owner_integration_deepseek_probe(
                "RUN ONE PAID DEEPSEEK PROBE"
            )
        self.assertTrue(result["ok"])
        self.assertGreater(result["metadata"]["cost_usd"], 0)
        self.assertEqual(
            result["metadata"]["cost_details"]["cost_value_type"],
            "local_estimate",
        )
        self.assertIsNone(
            result["metadata"]["cost_details"][
                "provider_authoritative_cost_usd"
            ]
        )

        with mock.patch.object(
            app,
            "_lead_search_provider_config",
            return_value={
                "enabled": True,
                "provider": "tavily",
                "api_key": "<fixture-credential>",
            },
        ), mock.patch.object(
            app,
            "_lead_search_tavily",
            return_value=[{"title": "Fixture", "url": "https://example.invalid"}],
        ):
            response = self.client.post(
                "/lead-finder/test-search-provider",
                json={},
                headers=self._headers("phase5b-search-provider-billing"),
            )
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(
            payload["external_billing"]["provider"],
            "tavily",
        )
        self.assertIsNone(
            payload["external_billing"]["provider_authoritative_cost"]
        )
        self.assertTrue(payload["external_billing"]["billing_data_missing"])

        person = {
            "id": "person-1",
            "name": "Fixture Person",
            "company": "Example",
            "email": "",
        }
        with mock.patch.object(
            app,
            "_lead_finder_lock_allowed",
            return_value=True,
        ), mock.patch.object(
            app,
            "_lead_contact_cache_find",
            return_value=None,
        ), mock.patch.object(
            app,
            "_lead_contact_cache_store",
        ), mock.patch.object(
            app,
            "_lead_apollo_enrich_person",
            return_value={
                "email": "fixture@example.com",
                "email_confidence": "high",
                "email_source": "Apollo",
                "verification_status": "Verified",
            },
        ):
            response = self._post_paid(
                "/lead-finder/find-emails",
                {
                    "people": [person],
                    "selected_person_ids": ["person-1"],
                    "enrichment_provider": {
                        "provider": "apollo",
                        "api_key": "<fixture-credential>",
                    },
                },
                "phase5b-apollo-billing",
            )
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["cost"], 0)
        self.assertEqual(payload["external_billing"]["provider"], "apollo")
        self.assertEqual(
            payload["external_billing"]["observed_operations"],
            1,
        )
        self.assertIsNone(
            payload["external_billing"]["provider_authoritative_cost"]
        )


def tearDownModule():
    _MODULE_TEMPORARY.cleanup()


if __name__ == "__main__":
    unittest.main()
