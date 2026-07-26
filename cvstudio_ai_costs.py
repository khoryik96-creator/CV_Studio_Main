"""App-independent AI cost estimates, guardrails and billing reconciliation.

Standard Anthropic Messages, DeepSeek Messages and OpenAI Responses calls
return usage counters but do not return invoice-authoritative per-call cost.
This module therefore keeps the established local estimate separate from an
optional, explicitly authoritative billing record. Missing authority is always
represented by ``None`` plus a status; it is never converted to a zero bill.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import json
import os
from typing import Any, Mapping


AI_COST_GUARDRAIL_ENV = "CVSTUDIO_AI_MAX_ESTIMATED_REQUEST_USD"
AI_COST_GUARDRAIL_MAX_USD = Decimal("10000")
AI_COST_BILLING_MAX_AMOUNT = Decimal("1000000000000")
AI_COST_MAX_RECONCILIATION_RECORDS = 100

MODEL_PRICING_USD_PER_MILLION = {
    "claude-sonnet-5": (2.00, 10.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-opus-4-8": (5.00, 25.00),
    "claude-opus-4-7": (5.00, 25.00),
    "claude-opus-4-6": (5.00, 25.00),
    "claude-sonnet-4-5": (3.00, 15.00),
    "claude-opus-4-5": (5.00, 25.00),
    "claude-haiku-4-5-20251001": (1.00, 5.00),
    "deepseek-v4-flash": (0.14, 0.28),
    "deepseek-v4-pro": (0.435, 0.87),
    "gpt-5.5": (5.00, 30.00),
    "gpt-5.5-pro": (30.00, 180.00),
    "gpt-5.4": (2.50, 15.00),
    "gpt-5.4-mini": (0.75, 4.50),
    "gpt-5.4-nano": (0.20, 1.25),
    "gpt-5.4-pro": (30.00, 180.00),
}

_PROVIDER_FALLBACK_MODEL = {
    "anthropic": "claude-sonnet-4-6",
    "deepseek": "deepseek-v4-flash",
    "openai": "gpt-5.5",
}

_PROVIDER_MODEL_PREFIXES = {
    "anthropic": ("claude-",),
    "deepseek": ("deepseek",),
    "openai": ("gpt-", "o1", "o3", "o4"),
}

_AUTHORITATIVE_BILLING_SOURCES = frozenset(
    {
        "provider_cost_report",
        "provider_invoice",
        "provider_response",
    }
)


class AICostError(ValueError):
    """Base class for failure-visible local AI cost-control errors."""

    code = "AI_COST_ERROR"

    def __init__(self, message: str, *, details: Mapping[str, Any] | None = None):
        super().__init__(str(message))
        self.details = dict(details or {})


class AICostGuardrailError(AICostError):
    """Raised before transport when a configured cost guardrail rejects a call."""

    code = "AI_COST_GUARDRAIL_BLOCKED"


class AICostGuardrailConfigurationError(AICostGuardrailError):
    """Raised before transport when the configured guardrail is invalid."""

    code = "AI_COST_GUARDRAIL_CONFIG_INVALID"


class AICostReconciliationError(AICostError):
    """Raised when purported authoritative billing data is unsafe to use."""

    code = "AI_COST_RECONCILIATION_FAILED"


def usage_int(usage: Mapping[str, Any] | None, *keys: str) -> int:
    """Return the first positive, otherwise last valid zero, usage counter."""
    fallback = 0
    source = usage if isinstance(usage, Mapping) else {}
    for key in keys:
        try:
            value = source.get(key)
            if value is None or isinstance(value, bool):
                continue
            parsed = max(0, int(value or 0))
            if parsed:
                return parsed
            fallback = parsed
        except (TypeError, ValueError, OverflowError):
            continue
    return fallback


def normalize_usage(
    usage: Mapping[str, Any] | None,
    api_calls: int | None = None,
) -> dict[str, Any]:
    """Return the established canonical shape without discarding native fields."""
    raw = dict(usage or {}) if isinstance(usage, Mapping) else {}
    input_tokens = usage_int(raw, "input_tokens", "prompt_tokens")
    output_tokens = usage_int(raw, "output_tokens", "completion_tokens")
    cache_hit = usage_int(
        raw,
        "prompt_cache_hit_tokens",
        "cache_read_input_tokens",
    )
    cache_miss = usage_int(
        raw,
        "prompt_cache_miss_tokens",
        "cache_creation_input_tokens",
    )

    input_details = raw.get("input_tokens_details")
    if not cache_hit and isinstance(input_details, Mapping):
        cache_hit = usage_int(input_details, "cached_tokens")
    if not input_tokens and (cache_hit or cache_miss):
        input_tokens = cache_hit + cache_miss

    raw["input_tokens"] = input_tokens
    raw["output_tokens"] = output_tokens
    raw["prompt_cache_hit_tokens"] = cache_hit
    raw["prompt_cache_miss_tokens"] = cache_miss
    raw["api_calls"] = (
        max(0, int(api_calls or 0))
        if api_calls is not None
        else usage_int(raw, "api_calls")
    )
    return raw


def merge_usage(*usages: Mapping[str, Any] | None) -> dict[str, Any]:
    """Merge canonical counters and retain normalized authoritative billing."""
    total: dict[str, Any] = {
        "input_tokens": 0,
        "output_tokens": 0,
        "prompt_cache_hit_tokens": 0,
        "prompt_cache_miss_tokens": 0,
        "api_calls": 0,
    }
    billing_records = []
    for usage in usages:
        normalized = normalize_usage(usage)
        for key in tuple(total):
            total[key] += usage_int(normalized, key)
        billing = normalized.get("_cvstudio_provider_billing")
        if isinstance(billing, Mapping):
            billing_records.append(dict(billing))
        elif isinstance(billing, list):
            billing_records.extend(
                dict(item) for item in billing if isinstance(item, Mapping)
            )
    if len(billing_records) == 1:
        total["_cvstudio_provider_billing"] = billing_records[0]
    elif billing_records:
        total["_cvstudio_provider_billing"] = billing_records
    return total


def normalize_provider(model: Any, provider: Any = None) -> str:
    """Resolve the established provider aliases and model-prefix fallback."""
    value = str(provider or "").strip().lower()
    if value in ("claude", "anthropic"):
        return "anthropic"
    if value in ("gpt", "openai"):
        return "openai"
    if value == "deepseek":
        return "deepseek"
    model_key = str(model or "").strip().lower()
    if model_key.startswith(_PROVIDER_MODEL_PREFIXES["deepseek"]):
        return "deepseek"
    if model_key.startswith(_PROVIDER_MODEL_PREFIXES["openai"]):
        return "openai"
    return "anthropic"


def pricing_for_model(
    model: Any,
    provider: Any = None,
) -> tuple[tuple[float, float], bool, str]:
    """Return established estimate rates, recognition and resolved model key."""
    key = str(model or "").strip().lower()
    if key in MODEL_PRICING_USD_PER_MILLION:
        return MODEL_PRICING_USD_PER_MILLION[key], True, key
    resolved = normalize_provider(model, provider)
    fallback = _PROVIDER_FALLBACK_MODEL[resolved]
    return MODEL_PRICING_USD_PER_MILLION[fallback], False, fallback


def _finite_nonnegative_decimal(value: Any, field: str) -> Decimal:
    if isinstance(value, bool):
        raise AICostReconciliationError(
            "{} must be a finite non-negative number".format(field)
        )
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise AICostReconciliationError(
            "{} must be a finite non-negative number".format(field)
        )
    if (
        not parsed.is_finite()
        or parsed < 0
        or parsed > AI_COST_BILLING_MAX_AMOUNT
    ):
        raise AICostReconciliationError(
            "{} must be a finite non-negative number no greater than {}".format(
                field,
                AI_COST_BILLING_MAX_AMOUNT,
            )
        )
    return parsed


def normalize_provider_billing(
    billing: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Validate an explicitly authoritative, non-secret provider cost record."""
    if billing is None:
        return None
    if not isinstance(billing, Mapping):
        raise AICostReconciliationError(
            "Provider billing data must be an object"
        )
    if billing.get("authoritative") is not True:
        raise AICostReconciliationError(
            "Provider billing data was not explicitly marked authoritative"
        )
    source = str(billing.get("source") or "").strip().lower()
    if source not in _AUTHORITATIVE_BILLING_SOURCES:
        raise AICostReconciliationError(
            "Provider billing source is not an approved authority"
        )
    currency = str(billing.get("currency") or "USD").strip().upper()
    if not currency or len(currency) > 12:
        raise AICostReconciliationError("Provider billing currency is invalid")
    amount = _finite_nonnegative_decimal(
        billing.get("amount"),
        "Provider billing amount",
    )
    scope = str(billing.get("scope") or "").strip().lower()
    if scope != "request":
        raise AICostReconciliationError(
            "Provider billing scope must explicitly identify one request"
        )
    return {
        "authoritative": True,
        "source": source,
        "scope": "request",
        "currency": currency,
        "amount": float(amount),
    }


def extract_provider_billing(
    provider: Any,
    response: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Extract only the explicit normalized authority envelope.

    Current standard provider inference responses do not contain this envelope.
    It is intentionally strict so ordinary usage or balance fields can never be
    mistaken for authoritative per-call cost.
    """
    if not isinstance(response, Mapping):
        return None
    candidate = response.get("_cvstudio_provider_billing")
    if candidate is None:
        candidate = response.get("provider_billing")
    if candidate is None:
        return None
    normalized = normalize_provider_billing(candidate)
    if normalized is not None:
        normalized["provider"] = normalize_provider(None, provider)
    return normalized


def _reconciliation_fields(
    estimate_usd: float,
    billing: Mapping[str, Any] | list[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    if billing is None:
        return {
            "provider_billing_status": "unavailable",
            "provider_authoritative_cost_usd": None,
            "provider_billing_currency": None,
            "provider_billing_source": None,
            "reconciliation_status": "provider_billing_unavailable",
            "reconciliation_difference_usd": None,
            "reconciliation_difference_percent": None,
            "billing_data_missing": True,
        }

    candidates = billing if isinstance(billing, list) else [billing]
    if len(candidates) > AI_COST_MAX_RECONCILIATION_RECORDS:
        raise AICostReconciliationError(
            "Provider billing record count exceeds the reconciliation limit"
        )
    normalized = [normalize_provider_billing(item) for item in candidates]
    normalized = [item for item in normalized if item is not None]
    if not normalized:
        raise AICostReconciliationError(
            "Provider billing authority was present but empty"
        )
    currencies = {item["currency"] for item in normalized}
    sources = {item["source"] for item in normalized}
    if len(currencies) != 1:
        raise AICostReconciliationError(
            "Provider billing records use multiple currencies"
        )
    currency = next(iter(currencies))
    if currency != "USD":
        return {
            "provider_billing_status": "authoritative_non_usd",
            "provider_authoritative_cost_usd": None,
            "provider_billing_currency": currency,
            "provider_billing_source": ",".join(sorted(sources)),
            "reconciliation_status": "currency_conversion_unavailable",
            "reconciliation_difference_usd": None,
            "reconciliation_difference_percent": None,
            "billing_data_missing": False,
        }

    authoritative_decimal = sum(
        Decimal(str(item["amount"])) for item in normalized
    )
    if authoritative_decimal > AI_COST_BILLING_MAX_AMOUNT:
        raise AICostReconciliationError(
            "Provider billing total exceeds the reconciliation limit"
        )
    authoritative_usd = float(authoritative_decimal)
    difference = authoritative_usd - float(estimate_usd)
    difference_percent = (
        difference / float(estimate_usd) * 100.0
        if float(estimate_usd) > 0
        else None
    )
    return {
        "provider_billing_status": "authoritative",
        "provider_authoritative_cost_usd": authoritative_usd,
        "provider_billing_currency": "USD",
        "provider_billing_source": ",".join(sorted(sources)),
        "reconciliation_status": "reconciled",
        "reconciliation_difference_usd": difference,
        "reconciliation_difference_percent": difference_percent,
        "billing_data_missing": False,
    }


def cost_details(
    model: Any,
    usage: Mapping[str, Any] | None,
    provider: Any = None,
    *,
    provider_billing: Mapping[str, Any] | list[Mapping[str, Any]] | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Return legacy estimate fields plus explicit authority reconciliation."""
    normalized = normalize_usage(usage)
    input_tokens = usage_int(normalized, "input_tokens")
    output_tokens = usage_int(normalized, "output_tokens")
    hit = usage_int(normalized, "prompt_cache_hit_tokens")
    miss = usage_int(normalized, "prompt_cache_miss_tokens")
    api_calls = usage_int(normalized, "api_calls")
    resolved_provider = normalize_provider(model, provider)
    model_key = str(model or "").strip().lower()

    if provider_billing is None:
        embedded = normalized.get("_cvstudio_provider_billing")
        if isinstance(embedded, Mapping) or isinstance(embedded, list):
            provider_billing = embedded

    if resolved_provider == "deepseek":
        if model_key == "deepseek-v4-pro":
            hit_rate, miss_rate, output_rate = 0.003625, 0.435, 0.87
            pricing_key, known = "deepseek-v4-pro", True
        elif model_key in (
            "deepseek-v4-flash",
            "deepseek-chat",
            "deepseek-reasoner",
        ):
            hit_rate, miss_rate, output_rate = 0.0028, 0.14, 0.28
            pricing_key, known = (
                "deepseek-v4-flash",
                model_key == "deepseek-v4-flash",
            )
        else:
            hit_rate, miss_rate, output_rate = 0.0028, 0.14, 0.28
            pricing_key, known = "deepseek-v4-flash", False
        residual_input = 0
        billed_miss = miss
        if hit or miss:
            if not input_tokens:
                input_tokens = hit + miss
            residual_input = max(0, input_tokens - hit - miss)
            billed_miss = miss + residual_input
            estimate_usd = (
                hit / 1e6 * hit_rate
                + billed_miss / 1e6 * miss_rate
                + output_tokens / 1e6 * output_rate
            )
            method = (
                "deepseek_returned_cache_hit_miss_tokens"
                if not residual_input
                else "deepseek_cache_split_plus_unclassified_input_as_miss"
            )
        else:
            residual_input = input_tokens
            billed_miss = input_tokens
            estimate_usd = (
                input_tokens / 1e6 * miss_rate
                + output_tokens / 1e6 * output_rate
            )
            method = "deepseek_input_priced_as_cache_miss_no_split_returned"
        details = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "prompt_cache_hit_tokens": hit,
            "prompt_cache_miss_tokens": miss,
            "unclassified_input_tokens": residual_input,
            "billed_cache_miss_tokens": billed_miss,
            "api_calls": api_calls,
            "usd": estimate_usd,
            "model": model,
            "provider": "deepseek",
            "pricing_model_key": pricing_key,
            "pricing_known": known,
            "cost_method": method,
            "rates_per_million_usd": {
                "cache_hit_input": hit_rate,
                "cache_miss_input": miss_rate,
                "output": output_rate,
            },
            "note": (
                "DeepSeek cost uses returned cache-hit/cache-miss counters when "
                "available; otherwise all input is conservatively priced as "
                "cache miss. Separate search/enrichment-provider fees are excluded."
            ),
        }
    else:
        (input_rate, output_rate), known, pricing_key = pricing_for_model(
            model,
            resolved_provider,
        )
        estimate_usd = (
            input_tokens / 1e6 * input_rate
            + output_tokens / 1e6 * output_rate
        )
        details = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "prompt_cache_hit_tokens": hit,
            "prompt_cache_miss_tokens": miss,
            "api_calls": api_calls,
            "usd": estimate_usd,
            "model": model,
            "provider": resolved_provider,
            "pricing_model_key": pricing_key,
            "pricing_known": known,
            "cost_method": "standard_input_output_tokens",
            "rates_per_million_usd": {
                "input": input_rate,
                "output": output_rate,
            },
            "note": (
                "Estimated API token cost only; separate third-party search/"
                "enrichment fees are excluded unless explicitly reported."
            ),
        }

    details.update(
        {
            "estimated_cost_usd": float(estimate_usd),
            "cost_value_type": "local_estimate",
            "cost_authority": "local_rate_table",
            "usage_authority": (
                "provider_response" if api_calls > 0 else "not_returned"
            ),
        }
    )
    details.update(_reconciliation_fields(float(estimate_usd), provider_billing))
    try:
        config = guardrail_configuration(environ)
        details["guardrail_enabled"] = config["enabled"]
        details["guardrail_limit_usd"] = config["limit_usd"]
        details["guardrail_status"] = (
            "configured" if config["enabled"] else "disabled"
        )
    except AICostGuardrailConfigurationError:
        # Reconciliation reporting must not hide the original guardrail error.
        details["guardrail_enabled"] = False
        details["guardrail_limit_usd"] = None
        details["guardrail_status"] = "configuration_invalid"
    return details


def guardrail_configuration(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Return the bounded call-time guardrail configuration."""
    source = os.environ if environ is None else environ
    raw = str(source.get(AI_COST_GUARDRAIL_ENV) or "").strip()
    if not raw:
        return {
            "enabled": False,
            "limit_usd": None,
            "source": AI_COST_GUARDRAIL_ENV,
        }
    try:
        limit = Decimal(raw)
    except InvalidOperation:
        raise AICostGuardrailConfigurationError(
            "AI cost guardrail configuration {} must be a finite number "
            "greater than 0 and no more than {}".format(
                AI_COST_GUARDRAIL_ENV,
                AI_COST_GUARDRAIL_MAX_USD,
            )
        )
    if not limit.is_finite() or limit <= 0 or limit > AI_COST_GUARDRAIL_MAX_USD:
        raise AICostGuardrailConfigurationError(
            "AI cost guardrail configuration {} must be a finite number "
            "greater than 0 and no more than {}".format(
                AI_COST_GUARDRAIL_ENV,
                AI_COST_GUARDRAIL_MAX_USD,
            )
        )
    return {
        "enabled": True,
        "limit_usd": float(limit),
        "source": AI_COST_GUARDRAIL_ENV,
    }


def _guardrail_pricing(
    model: Any,
    provider: Any,
) -> tuple[float, float, str, bool]:
    resolved = normalize_provider(model, provider)
    (input_rate, output_rate), known, pricing_key = pricing_for_model(
        model,
        resolved,
    )
    if known:
        return input_rate, output_rate, pricing_key, True

    candidates = [
        (key, rates)
        for key, rates in MODEL_PRICING_USD_PER_MILLION.items()
        if key.startswith(_PROVIDER_MODEL_PREFIXES[resolved])
    ]
    if candidates:
        input_rate = max(rates[0] for _key, rates in candidates)
        output_rate = max(rates[1] for _key, rates in candidates)
        pricing_key = "provider_known_rate_ceiling"
    return input_rate, output_rate, pricing_key, False


def estimate_request_ceiling(
    provider: Any,
    payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Estimate a conservative per-request ceiling without exposing payload data."""
    clean = dict(payload or {}) if isinstance(payload, Mapping) else {}
    model = clean.get("model") or ""
    resolved = normalize_provider(model, provider)
    serialized = json.dumps(
        clean,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8", errors="replace")
    # One token per UTF-8 byte is intentionally conservative for preflight.
    estimated_input_tokens = max(1, len(serialized))
    output_value = clean.get("max_tokens")
    if output_value is None:
        output_value = clean.get("max_output_tokens")
    try:
        max_output_tokens = int(output_value or 4096)
    except (TypeError, ValueError, OverflowError):
        raise AICostGuardrailError(
            "AI cost guardrail blocked the request before provider transport: "
            "the requested output-token ceiling is invalid.",
            details={
                "enabled": True,
                "status": "blocked",
                "provider": resolved,
                "model": str(model)[:160],
                "reason": "invalid_output_token_ceiling",
            },
        )
    if max_output_tokens < 0:
        raise AICostGuardrailError(
            "AI cost guardrail blocked the request before provider transport: "
            "the requested output-token ceiling is negative.",
            details={
                "enabled": True,
                "status": "blocked",
                "provider": resolved,
                "model": str(model)[:160],
                "reason": "negative_output_token_ceiling",
            },
        )
    input_rate, output_rate, pricing_key, pricing_known = _guardrail_pricing(
        model,
        resolved,
    )
    estimate_decimal = (
        Decimal(estimated_input_tokens) / Decimal(1_000_000)
        * Decimal(str(input_rate))
        + Decimal(max_output_tokens) / Decimal(1_000_000)
        * Decimal(str(output_rate))
    )
    try:
        estimate_usd = float(estimate_decimal)
    except (OverflowError, ValueError):
        estimate_usd = float("inf")
    return {
        "provider": resolved,
        "model": str(model)[:160],
        "estimated_input_token_ceiling": estimated_input_tokens,
        "max_output_tokens": max_output_tokens,
        "estimated_request_ceiling_usd": estimate_usd,
        "pricing_model_key": pricing_key,
        "pricing_known": pricing_known,
        "rates_per_million_usd": {
            "input": input_rate,
            "output": output_rate,
        },
        "method": "utf8_byte_input_ceiling_plus_requested_output_ceiling",
    }


def enforce_request_guardrail(
    provider: Any,
    payload: Mapping[str, Any] | None,
    *,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Reject a request before transport when its estimate exceeds the limit."""
    config = guardrail_configuration(environ)
    if not config["enabled"]:
        return {
            "enabled": False,
            "status": "disabled",
            "limit_usd": None,
            "source": config["source"],
        }
    estimate = estimate_request_ceiling(provider, payload)
    estimate.update(
        {
            "enabled": True,
            "status": "allowed",
            "limit_usd": config["limit_usd"],
            "source": config["source"],
        }
    )
    if (
        float(estimate["estimated_request_ceiling_usd"])
        > float(config["limit_usd"])
    ):
        estimate["status"] = "blocked"
        raise AICostGuardrailError(
            (
                "AI cost guardrail blocked the request before provider transport: "
                "estimated ceiling ${:.6f} exceeds configured limit ${:.6f} "
                "for {}."
            ).format(
                float(estimate["estimated_request_ceiling_usd"]),
                float(config["limit_usd"]),
                estimate["provider"],
            ),
            details=estimate,
        )
    return estimate


def unavailable_external_billing(
    provider: Any,
    *,
    observed_operations: int | None = None,
    reason: str = "",
) -> dict[str, Any]:
    """Describe third-party billing absence without fabricating a zero cost."""
    operations = None
    if observed_operations is not None:
        try:
            operations = max(0, int(observed_operations))
        except (TypeError, ValueError, OverflowError):
            operations = None
    return {
        "provider": (
            str(provider or "unknown").strip().lower()[:80] or "unknown"
        ),
        "provider_billing_status": "unavailable",
        "provider_authoritative_cost": None,
        "provider_billing_currency": None,
        "reconciliation_status": "provider_billing_unavailable",
        "observed_operations": operations,
        "billing_data_missing": True,
        "reason": str(reason or "Provider-authoritative billing was not returned.")[
            :500
        ],
    }


def paid_failure_reconciliation(
    error: BaseException,
    *,
    provider: Any,
    model: Any,
    usage: Mapping[str, Any] | None = None,
    attempted: bool | None = None,
) -> dict[str, Any]:
    """Return additive failure status without changing legacy error fields."""
    normalized = normalize_usage(usage)
    calls = usage_int(normalized, "api_calls")
    if attempted is False:
        call_status = "not_called"
        reconciliation = "not_called"
    elif isinstance(error, AICostGuardrailError) or (
        "ai cost guardrail" in str(error or "").lower()
    ):
        call_status = "blocked_before_provider_transport"
        reconciliation = "not_called"
    elif isinstance(error, AICostReconciliationError):
        call_status = "provider_response_received"
        reconciliation = "reconciliation_failed"
    elif getattr(error, "code", None) is not None or getattr(
        error,
        "status",
        None,
    ) is not None:
        call_status = "provider_error_response_received"
        reconciliation = "provider_billing_unavailable"
    elif calls > 0:
        call_status = "provider_response_received"
        reconciliation = "provider_billing_unavailable"
    else:
        call_status = "ambiguous_no_provider_usage_returned"
        reconciliation = "ambiguous_provider_charge"
    return {
        "paid_call_status": call_status,
        "billing_reconciliation": {
            "provider": normalize_provider(model, provider),
            "model": str(model or "")[:160],
            "usage_authority": (
                "provider_response" if calls > 0 else "not_returned"
            ),
            "provider_billing_status": "unavailable",
            "provider_authoritative_cost_usd": None,
            "reconciliation_status": reconciliation,
            "billing_data_missing": True,
        },
    }


__all__ = [
    "AI_COST_GUARDRAIL_ENV",
    "AICostError",
    "AICostGuardrailConfigurationError",
    "AICostGuardrailError",
    "AICostReconciliationError",
    "MODEL_PRICING_USD_PER_MILLION",
    "cost_details",
    "enforce_request_guardrail",
    "estimate_request_ceiling",
    "extract_provider_billing",
    "guardrail_configuration",
    "merge_usage",
    "normalize_provider",
    "normalize_provider_billing",
    "normalize_usage",
    "paid_failure_reconciliation",
    "pricing_for_model",
    "unavailable_external_billing",
    "usage_int",
]
