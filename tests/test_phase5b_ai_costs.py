import unittest
from decimal import Decimal

from cvstudio_ai_costs import (
    AI_COST_GUARDRAIL_ENV,
    AICostGuardrailConfigurationError,
    AICostGuardrailError,
    AICostReconciliationError,
    cost_details,
    enforce_request_guardrail,
    estimate_request_ceiling,
    extract_provider_billing_result,
    merge_usage,
    normalize_provider_billing,
    normalize_usage,
    paid_failure_reconciliation,
    unavailable_external_billing,
)


class Phase5BAICostFoundationTests(unittest.TestCase):
    def test_usage_normalization_preserves_native_and_openai_cache_fields(self):
        usage = normalize_usage(
            {
                "input_tokens": 20,
                "output_tokens": 4,
                "input_tokens_details": {"cached_tokens": 7},
                "native_marker": "fixture",
            },
            api_calls=1,
        )
        self.assertEqual(usage["input_tokens"], 20)
        self.assertEqual(usage["output_tokens"], 4)
        self.assertEqual(usage["prompt_cache_hit_tokens"], 7)
        self.assertEqual(usage["prompt_cache_miss_tokens"], 0)
        self.assertEqual(usage["api_calls"], 1)
        self.assertEqual(usage["native_marker"], "fixture")

        merged = merge_usage(
            usage,
            {
                "prompt_tokens": 3,
                "completion_tokens": 2,
                "cache_read_input_tokens": 1,
                "cache_creation_input_tokens": 2,
                "api_calls": 1,
            },
        )
        self.assertEqual(
            {key: merged[key] for key in (
                "input_tokens",
                "output_tokens",
                "prompt_cache_hit_tokens",
                "prompt_cache_miss_tokens",
                "api_calls",
            )},
            {
                "input_tokens": 23,
                "output_tokens": 6,
                "prompt_cache_hit_tokens": 8,
                "prompt_cache_miss_tokens": 2,
                "api_calls": 2,
            },
        )

    def test_malformed_usage_counters_do_not_become_valid_zero_estimates(self):
        for usage in (
            {"input_tokens": -1, "output_tokens": 2, "api_calls": 1},
            {"input_tokens": 1.5, "output_tokens": 2, "api_calls": 1},
            {"input_tokens": True, "output_tokens": 2, "api_calls": 1},
            {
                "input_tokens": 10,
                "output_tokens": 2,
                "api_calls": 1,
                "prompt_cache_hit_tokens": 8,
                "prompt_cache_miss_tokens": 8,
            },
        ):
            with self.subTest(usage=usage):
                details = cost_details(
                    "deepseek-v4-flash",
                    usage,
                    "deepseek",
                    environ={},
                )
                self.assertIsNone(details["estimated_cost_usd"])
                self.assertEqual(
                    details["cost_value_type"],
                    "local_estimate_unavailable",
                )
                self.assertEqual(
                    details["usage_authority"],
                    "provider_response_invalid",
                )
                self.assertEqual(details["estimate_status"], "usage_invalid")
                self.assertEqual(
                    details["reconciliation_status"],
                    "provider_billing_unavailable",
                )

    def test_missing_provider_billing_is_explicit_and_never_zero_authority(self):
        details = cost_details(
            "claude-sonnet-4-6",
            {"input_tokens": 100, "output_tokens": 10, "api_calls": 1},
            "anthropic",
            environ={},
        )
        self.assertGreater(details["usd"], 0)
        self.assertEqual(details["estimated_cost_usd"], details["usd"])
        self.assertEqual(details["cost_value_type"], "local_estimate")
        self.assertEqual(details["cost_authority"], "local_rate_table")
        self.assertEqual(details["usage_authority"], "provider_response")
        self.assertEqual(details["provider_billing_status"], "unavailable")
        self.assertIsNone(details["provider_authoritative_cost_usd"])
        self.assertEqual(
            details["reconciliation_status"],
            "provider_billing_unavailable",
        )
        self.assertIsNone(details["reconciliation_difference_usd"])
        self.assertTrue(details["billing_data_missing"])

    def test_authoritative_usd_billing_reconciles_without_replacing_estimate(self):
        estimate_only = cost_details(
            "deepseek-v4-flash",
            {
                "input_tokens": 1000,
                "output_tokens": 100,
                "api_calls": 1,
            },
            "deepseek",
            environ={},
        )
        billing = {
            "authoritative": True,
            "source": "provider_cost_report",
            "scope": "request",
            "currency": "USD",
            "amount": "0.0042",
        }
        reconciled = cost_details(
            "deepseek-v4-flash",
            {
                "input_tokens": 1000,
                "output_tokens": 100,
                "api_calls": 1,
            },
            "deepseek",
            provider_billing=billing,
            environ={},
        )
        self.assertEqual(reconciled["usd"], estimate_only["usd"])
        self.assertEqual(reconciled["estimated_cost_usd"], estimate_only["usd"])
        self.assertEqual(reconciled["provider_billing_status"], "authoritative")
        self.assertEqual(reconciled["provider_authoritative_cost_usd"], 0.0042)
        self.assertEqual(reconciled["reconciliation_status"], "reconciled")
        self.assertAlmostEqual(
            reconciled["reconciliation_difference_usd"],
            0.0042 - estimate_only["usd"],
        )
        self.assertFalse(reconciled["billing_data_missing"])

    def test_non_usd_authority_remains_visible_without_fake_conversion(self):
        details = cost_details(
            "gpt-5.4-mini",
            {"input_tokens": 10, "output_tokens": 2, "api_calls": 1},
            "openai",
            provider_billing={
                "authoritative": True,
                "source": "provider_invoice",
                "scope": "request",
                "currency": "EUR",
                "amount": "0.01",
            },
            environ={},
        )
        self.assertEqual(
            details["provider_billing_status"],
            "authoritative_non_usd",
        )
        self.assertIsNone(details["provider_authoritative_cost_usd"])
        self.assertEqual(details["provider_authoritative_cost"], 0.01)
        self.assertEqual(
            details["provider_authoritative_cost_currency"],
            "EUR",
        )
        self.assertEqual(
            details["reconciliation_status"],
            "currency_conversion_unavailable",
        )
        self.assertFalse(details["billing_data_missing"])

    def test_invalid_billing_authority_fails_visibly(self):
        invalid_records = [
            {
                "source": "provider_invoice",
                "scope": "request",
                "currency": "USD",
                "amount": "1",
            },
            {
                "authoritative": True,
                "source": "client_estimate",
                "scope": "request",
                "currency": "USD",
                "amount": "1",
            },
            {
                "authoritative": True,
                "source": "provider_invoice",
                "scope": "request",
                "currency": "USD",
                "amount": "-1",
            },
            {
                "authoritative": True,
                "source": "provider_invoice",
                "currency": "USD",
                "amount": "1",
            },
            {
                "authoritative": True,
                "source": "provider_invoice",
                "scope": "request",
                "amount": "1",
            },
            {
                "authoritative": True,
                "status": "partial",
                "source": "provider_invoice",
                "scope": "request",
                "currency": "USD",
                "amount": "1",
            },
            {
                "authoritative": True,
                "source": "provider_invoice",
                "scope": "request",
                "currency": "USD",
                "amount": "1e100",
            },
        ]
        for record in invalid_records:
            with self.subTest(record=record):
                with self.assertRaises(AICostReconciliationError):
                    normalize_provider_billing(record)

    def test_billing_provider_currency_and_partial_records_fail_visibly(self):
        with self.assertRaises(AICostReconciliationError):
            cost_details(
                "claude-sonnet-4-6",
                {"input_tokens": 10, "output_tokens": 2, "api_calls": 1},
                "anthropic",
                provider_billing={
                    "authoritative": True,
                    "source": "provider_invoice",
                    "scope": "request",
                    "provider": "openai",
                    "currency": "USD",
                    "amount": "0.01",
                },
                environ={},
            )
        for currency in ("US", "US12", "U$D", "TOO-LONG"):
            with self.subTest(currency=currency):
                with self.assertRaises(AICostReconciliationError):
                    normalize_provider_billing(
                        {
                            "authoritative": True,
                            "source": "provider_invoice",
                            "scope": "request",
                            "currency": currency,
                            "amount": "0.01",
                        }
                    )

        merged = merge_usage(
            {
                "api_calls": 1,
                "_cvstudio_provider_billing": [
                    {
                        "authoritative": True,
                        "source": "provider_invoice",
                        "scope": "request",
                        "currency": "USD",
                        "amount": "0.01",
                        "account_token": "<must-not-survive>",
                    },
                    "malformed-record",
                ],
            }
        )
        self.assertNotIn("<must-not-survive>", repr(merged))
        self.assertNotIn("_cvstudio_provider_billing", merged)
        self.assertIn("_cvstudio_provider_billing_error", merged)
        details = cost_details(
            "claude-sonnet-4-6",
            merged,
            "anthropic",
            environ={},
        )
        self.assertEqual(details["provider_billing_status"], "invalid")
        self.assertEqual(details["reconciliation_status"], "reconciliation_failed")
        self.assertTrue(details["billing_data_invalid"])
        self.assertFalse(details["billing_data_missing"])

        pending = extract_provider_billing_result(
            "openai",
            {
                "provider_billing": {
                    "authoritative": False,
                    "status": "delayed",
                    "source": "provider_cost_report",
                    "scope": "request",
                    "currency": "USD",
                }
            },
        )
        self.assertIsNone(pending["billing"])
        self.assertEqual(
            pending["error"]["provider_billing_status"],
            "pending",
        )
        self.assertEqual(
            pending["error"]["reconciliation_status"],
            "provider_billing_pending",
        )
        self.assertTrue(pending["error"]["billing_data_missing"])
        self.assertFalse(pending["error"]["billing_data_invalid"])

    def test_no_call_and_missing_usage_have_distinct_reconciliation_states(self):
        no_call = cost_details(
            "claude-sonnet-4-6",
            {},
            "anthropic",
            environ={},
        )
        self.assertEqual(no_call["provider_billing_status"], "not_applicable")
        self.assertEqual(no_call["reconciliation_status"], "not_called")
        self.assertFalse(no_call["billing_data_missing"])

        billing_without_usage = cost_details(
            "claude-sonnet-4-6",
            {},
            "anthropic",
            provider_billing={
                "authoritative": True,
                "source": "provider_invoice",
                "scope": "request",
                "currency": "USD",
                "amount": "0",
            },
            environ={},
        )
        self.assertEqual(
            billing_without_usage["provider_authoritative_cost_usd"],
            0.0,
        )
        self.assertEqual(
            billing_without_usage["reconciliation_status"],
            "estimate_usage_unavailable",
        )
        self.assertIsNone(
            billing_without_usage["reconciliation_difference_usd"]
        )

    def test_guardrail_is_disabled_by_default_and_blocks_before_transport(self):
        payload = {
            "model": "claude-sonnet-4-6",
            "max_tokens": 1000,
            "messages": [{"role": "user", "content": "fixture"}],
        }
        disabled = enforce_request_guardrail("anthropic", payload, environ={})
        self.assertEqual(
            disabled,
            {
                "enabled": False,
                "status": "disabled",
                "limit_usd": None,
                "source": AI_COST_GUARDRAIL_ENV,
            },
        )
        estimate = estimate_request_ceiling("anthropic", payload)
        self.assertGreater(estimate["estimated_request_ceiling_usd"], 0)
        allowed = enforce_request_guardrail(
            "anthropic",
            payload,
            environ={
                AI_COST_GUARDRAIL_ENV: str(
                    estimate["estimated_request_ceiling_usd"] + 0.01
                )
            },
        )
        self.assertEqual(allowed["status"], "allowed")

        with self.assertRaises(AICostGuardrailError) as blocked:
            enforce_request_guardrail(
                "anthropic",
                payload,
                environ={AI_COST_GUARDRAIL_ENV: "0.000001"},
            )
        self.assertEqual(blocked.exception.details["status"], "blocked")
        self.assertNotIn("fixture", str(blocked.exception))

        for output_value in ("invalid", -1, 10 ** 1000):
            with self.subTest(output_value=str(output_value)[:20]):
                with self.assertRaises(AICostGuardrailError):
                    enforce_request_guardrail(
                        "openai",
                        {
                            "model": "gpt-5.5-pro",
                            "max_tokens": output_value,
                        },
                        environ={AI_COST_GUARDRAIL_ENV: "10000"},
                    )

    def test_guardrail_rejects_zero_boolean_and_fractional_output_ceilings(self):
        for output_value in (0, False, True, 1.1, 4096.5, "4096"):
            with self.subTest(output_value=repr(output_value)):
                with self.assertRaises(AICostGuardrailError):
                    enforce_request_guardrail(
                        "anthropic",
                        {
                            "model": "claude-sonnet-4-6",
                            "max_tokens": output_value,
                        },
                        environ={AI_COST_GUARDRAIL_ENV: "10000"},
                    )

        defaulted = estimate_request_ceiling(
            "anthropic",
            {"model": "claude-sonnet-4-6"},
        )
        self.assertEqual(defaulted["max_output_tokens"], 4096)

    def test_guardrail_compares_exact_decimal_values_before_transport(self):
        payload = {
            "model": "deepseek-v4-flash",
            "max_tokens": 10,
            "messages": [{"role": "user", "content": "fixture"}],
        }
        estimate = estimate_request_ceiling("deepseek", payload)
        exact = Decimal(estimate["estimated_request_ceiling_usd_text"])
        slightly_lower = exact - Decimal("1e-30")
        self.assertEqual(float(exact), float(slightly_lower))
        with self.assertRaises(AICostGuardrailError):
            enforce_request_guardrail(
                "deepseek",
                payload,
                environ={AI_COST_GUARDRAIL_ENV: str(slightly_lower)},
            )

    def test_invalid_guardrail_configuration_fails_before_estimation(self):
        for value in ("not-a-number", "nan", "0", "-1", "10001"):
            with self.subTest(value=value):
                with self.assertRaises(AICostGuardrailConfigurationError):
                    enforce_request_guardrail(
                        "deepseek",
                        {"model": "deepseek-v4-flash", "max_tokens": 10},
                        environ={AI_COST_GUARDRAIL_ENV: value},
                    )

    def test_unknown_model_uses_provider_rate_ceiling_for_guardrail(self):
        estimate = estimate_request_ceiling(
            "openai",
            {"model": "gpt-future", "max_tokens": 100},
        )
        self.assertFalse(estimate["pricing_known"])
        self.assertEqual(
            estimate["pricing_model_key"],
            "provider_known_rate_ceiling",
        )
        self.assertEqual(
            estimate["rates_per_million_usd"],
            {"input": 30.0, "output": 180.0},
        )

    def test_external_billing_and_ambiguous_failures_do_not_invent_zero(self):
        external = unavailable_external_billing(
            "apollo",
            observed_operations=2,
            reason="Fixture provider returned no billing amount.",
        )
        self.assertEqual(external["provider"], "apollo")
        self.assertEqual(external["observed_operations"], 2)
        self.assertIsNone(external["provider_authoritative_cost"])
        self.assertTrue(external["billing_data_missing"])

        ambiguous = paid_failure_reconciliation(
            TimeoutError("fixture timeout"),
            provider="anthropic",
            model="claude-sonnet-4-6",
            usage={},
        )
        self.assertEqual(
            ambiguous["paid_call_status"],
            "ambiguous_no_provider_usage_returned",
        )
        self.assertEqual(
            ambiguous["billing_reconciliation"]["reconciliation_status"],
            "ambiguous_provider_charge",
        )
        self.assertIsNone(
            ambiguous["billing_reconciliation"][
                "provider_authoritative_cost_usd"
            ]
        )

        not_called = paid_failure_reconciliation(
            RuntimeError("fixture local validation"),
            provider="anthropic",
            model="claude-sonnet-4-6",
            usage={},
            attempted=False,
        )
        self.assertEqual(not_called["paid_call_status"], "not_called")
        self.assertEqual(
            not_called["billing_reconciliation"]["provider_billing_status"],
            "not_applicable",
        )
        self.assertFalse(
            not_called["billing_reconciliation"]["billing_data_missing"]
        )


if __name__ == "__main__":
    unittest.main()
