"""App-independent AI cost estimates, guardrails and billing reconciliation.

Standard Anthropic Messages, DeepSeek Messages and OpenAI Responses calls
return usage counters but do not return invoice-authoritative per-call cost.
This module therefore keeps the established local estimate separate from an
optional, explicitly authoritative billing record. Missing authority is always
represented by ``None`` plus a status; it is never converted to a zero bill.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, localcontext
import json
import os
import re
from typing import Any, Mapping


AI_COST_GUARDRAIL_ENV = "CVSTUDIO_AI_MAX_ESTIMATED_REQUEST_USD"
AI_COST_GUARDRAIL_MAX_USD = Decimal("10000")
AI_COST_BILLING_MAX_AMOUNT = Decimal("1000000000000")
AI_COST_BILLING_MAX_DECIMAL_PLACES = 18
AI_COST_BILLING_MAX_SIGNIFICANT_DIGITS = 30
AI_COST_MAX_RECONCILIATION_RECORDS = 100
AI_COST_MAX_OUTPUT_TOKENS = 1_000_000_000_000
AI_COST_MAX_TOKEN_COUNT = 1_000_000_000_000

_PROVIDER_BILLING_FIELD = "_cvstudio_provider_billing"
_PROVIDER_BILLING_ERROR_FIELD = "_cvstudio_provider_billing_error"
_USAGE_ERROR_FIELD = "_cvstudio_usage_error"
_USAGE_MISSING_FIELD = "_cvstudio_usage_missing"

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


def _billing_error_marker(
    error: BaseException | None = None,
    *,
    provider_response_received: bool = False,
) -> dict[str, Any]:
    details = (
        dict(getattr(error, "details", {}) or {})
        if error is not None
        else {}
    )
    billing_status = str(
        details.get("provider_billing_status") or "invalid"
    ).strip().lower()
    if billing_status not in {
        "delayed",
        "invalid",
        "partial",
        "pending",
        "unavailable",
    }:
        billing_status = "invalid"
    reconciliation = str(
        details.get("reconciliation_status") or "reconciliation_failed"
    ).strip().lower()
    if reconciliation not in {
        "provider_billing_delayed",
        "provider_billing_partial",
        "provider_billing_pending",
        "provider_billing_unavailable",
        "reconciliation_failed",
    }:
        reconciliation = "reconciliation_failed"
    invalid = billing_status == "invalid"
    missing = billing_status in {
        "delayed",
        "partial",
        "pending",
        "unavailable",
    }
    return {
        "provider_billing_status": billing_status,
        "reconciliation_status": reconciliation,
        "billing_data_missing": missing,
        "billing_data_invalid": invalid,
        "provider_response_received": bool(provider_response_received),
    }


def _sanitize_billing_error_marker(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    marker = _billing_error_marker()
    marker["provider_billing_status"] = str(
        value.get("provider_billing_status") or marker["provider_billing_status"]
    ).strip().lower()
    marker["reconciliation_status"] = str(
        value.get("reconciliation_status") or marker["reconciliation_status"]
    ).strip().lower()
    marker["provider_response_received"] = (
        value.get("provider_response_received") is True
    )
    return _billing_error_marker(
        AICostReconciliationError("", details=marker),
        provider_response_received=marker["provider_response_received"],
    )


def _usage_counter_is_invalid(value: Any, maximum: int) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return True
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return True
    return bool(
        not parsed.is_finite()
        or parsed < 0
        or parsed != parsed.to_integral_value()
        or parsed > maximum
    )


def _usage_error_marker(usage: Mapping[str, Any]) -> str:
    for key in (
        "input_tokens",
        "prompt_tokens",
        "output_tokens",
        "completion_tokens",
        "prompt_cache_hit_tokens",
        "cache_read_input_tokens",
        "prompt_cache_miss_tokens",
        "cache_creation_input_tokens",
    ):
        if key in usage and _usage_counter_is_invalid(
            usage.get(key),
            AI_COST_MAX_TOKEN_COUNT,
        ):
            return "invalid_provider_usage_counter"
    if "api_calls" in usage and _usage_counter_is_invalid(
        usage.get("api_calls"),
        AI_COST_MAX_RECONCILIATION_RECORDS,
    ):
        return "invalid_provider_api_call_count"
    details = usage.get("input_tokens_details")
    if isinstance(details, Mapping) and _usage_counter_is_invalid(
        details.get("cached_tokens"),
        AI_COST_MAX_TOKEN_COUNT,
    ):
        return "invalid_provider_usage_counter"
    return ""


def _safe_model_identifier(value: Any) -> str:
    model = str(value or "").strip()
    lowered = model.lower()
    if (
        not model
        or len(model) > 160
        or re.search(
            r"(?i)(?:sk-[a-z0-9]|api[_-]?key|access[_-]?token|"
            r"client[_-]?secret|password|authorization|"
            r"bearer(?:[._:/-]|$))",
            lowered,
        )
        is not None
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]*", model) is None
    ):
        return "[redacted-or-invalid-model]" if model else ""
    return model


def _safe_external_provider_identifier(value: Any) -> str:
    provider = str(value or "").strip().lower()
    if (
        not provider
        or len(provider) > 80
        or re.search(
            r"(?:sk-[a-z0-9]|api[_-]?key|access[_-]?token|"
            r"client[_-]?secret|password|authorization|"
            r"bearer(?:[._-]|$))",
            provider,
        )
        is not None
        or re.fullmatch(r"[a-z0-9][a-z0-9._-]*", provider) is None
    ):
        return "unknown"
    return provider


def _safe_billing_reason(value: Any) -> str:
    reason = str(
        value or "Provider-authoritative billing was not returned."
    ).strip()
    reason = re.sub(
        r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+",
        r"\1[redacted]",
        reason,
    )
    reason = re.sub(
        r"(?i)(api[_-]?key|access_token|client_secret|password)"
        r"(\s*[:=]\s*)[^\s,;}]+",
        r"\1\2[redacted]",
        reason,
    )
    reason = re.sub(r"(?i)\bsk-[A-Za-z0-9._-]+", "[redacted]", reason)
    return reason[:500]


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
    existing_usage_missing = raw.pop(_USAGE_MISSING_FIELD, None) is True
    existing_usage_error = str(raw.pop(_USAGE_ERROR_FIELD, "") or "")
    current_usage_error = _usage_error_marker(raw)
    usage_error = (
        current_usage_error
        or (
            existing_usage_error
            if existing_usage_error in {
            "inconsistent_provider_usage_counters",
            "invalid_provider_api_call_count",
            "invalid_provider_usage_counter",
            }
            else ""
        )
    )
    billing_candidate = raw.pop(_PROVIDER_BILLING_FIELD, None)
    billing_error = _sanitize_billing_error_marker(
        raw.pop(_PROVIDER_BILLING_ERROR_FIELD, None)
    )
    input_counter_supplied = any(
        key in raw and raw.get(key) is not None
        for key in (
            "input_tokens",
            "prompt_tokens",
            "prompt_cache_hit_tokens",
            "cache_read_input_tokens",
            "prompt_cache_miss_tokens",
            "cache_creation_input_tokens",
        )
    )
    output_counter_supplied = any(
        key in raw and raw.get(key) is not None
        for key in ("output_tokens", "completion_tokens")
    )
    input_details = raw.get("input_tokens_details")
    if (
        isinstance(input_details, Mapping)
        and input_details.get("cached_tokens") is not None
    ):
        input_counter_supplied = True
    token_counters_complete = (
        input_counter_supplied and output_counter_supplied
    )
    if billing_candidate is not None and billing_error is None:
        try:
            if isinstance(billing_candidate, list):
                if (
                    not billing_candidate
                    or len(billing_candidate)
                    > AI_COST_MAX_RECONCILIATION_RECORDS
                ):
                    raise AICostReconciliationError(
                        "Provider billing record collection is empty or too large"
                    )
                normalized_billing = [
                    normalize_provider_billing(item)
                    for item in billing_candidate
                ]
            else:
                normalized_billing = normalize_provider_billing(
                    billing_candidate
                )
        except AICostReconciliationError as exc:
            normalized_billing = None
            billing_error = _billing_error_marker(exc)
        if normalized_billing is not None:
            raw[_PROVIDER_BILLING_FIELD] = normalized_billing
    if billing_error is not None:
        raw[_PROVIDER_BILLING_ERROR_FIELD] = billing_error
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
    if (
        not usage_error
        and input_tokens
        and cache_hit + cache_miss > input_tokens
    ):
        usage_error = "inconsistent_provider_usage_counters"
    if usage_error:
        raw[_USAGE_ERROR_FIELD] = usage_error
    elif existing_usage_missing or (
        raw["api_calls"] > 0 and not token_counters_complete
    ):
        raw[_USAGE_MISSING_FIELD] = True
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
    billing_records: list[dict[str, Any]] = []
    billing_errors: list[dict[str, Any]] = []
    usage_errors: list[str] = []
    usage_missing = False
    for usage in usages:
        normalized = normalize_usage(usage)
        usage_error = str(normalized.get(_USAGE_ERROR_FIELD) or "")
        if usage_error:
            usage_errors.append(usage_error)
        if normalized.get(_USAGE_MISSING_FIELD) is True:
            usage_missing = True
        for key in tuple(total):
            total[key] += usage_int(normalized, key)
        billing_error = _sanitize_billing_error_marker(
            normalized.get(_PROVIDER_BILLING_ERROR_FIELD)
        )
        if billing_error is not None:
            billing_errors.append(billing_error)
        billing = normalized.get(_PROVIDER_BILLING_FIELD)
        if isinstance(billing, Mapping):
            billing_records.append(dict(billing))
        elif isinstance(billing, list):
            billing_records.extend(dict(item) for item in billing)
    if len(billing_records) > AI_COST_MAX_RECONCILIATION_RECORDS:
        billing_errors.append(_billing_error_marker())
    recorded_calls = total["api_calls"]
    if billing_records and recorded_calls:
        if len(billing_records) < recorded_calls:
            billing_errors.append(
                _billing_error_marker(
                    AICostReconciliationError(
                        "Provider billing covers only part of the paid calls",
                        details={
                            "provider_billing_status": "partial",
                            "reconciliation_status": "provider_billing_partial",
                        },
                    ),
                    provider_response_received=True,
                )
            )
        elif len(billing_records) > recorded_calls:
            billing_errors.append(
                _billing_error_marker(
                    AICostReconciliationError(
                        "Provider billing record count exceeds paid-call count"
                    ),
                    provider_response_received=True,
                )
            )
    if billing_errors:
        # Never reconcile only the valid subset of a partial/malformed
        # collection. Prefer the most failure-visible status and discard all
        # untrusted record content.
        priority = {
            "invalid": 5,
            "partial": 4,
            "delayed": 3,
            "pending": 2,
            "unavailable": 1,
        }
        selected = max(
            billing_errors,
            key=lambda item: priority.get(
                str(item.get("provider_billing_status") or ""),
                0,
            ),
        )
        total[_PROVIDER_BILLING_ERROR_FIELD] = dict(selected)
    elif len(billing_records) == 1:
        total[_PROVIDER_BILLING_FIELD] = billing_records[0]
    elif billing_records:
        total[_PROVIDER_BILLING_FIELD] = billing_records
    if usage_errors:
        total[_USAGE_ERROR_FIELD] = (
            "invalid_provider_usage_counter"
            if any(item.startswith("invalid_provider") for item in usage_errors)
            else "inconsistent_provider_usage_counters"
        )
    elif usage_missing:
        total[_USAGE_MISSING_FIELD] = True
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
        raw_value = str(value).strip()
        if not raw_value or len(raw_value) > 128:
            raise ValueError("bounded decimal required")
        parsed = Decimal(raw_value)
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
    if parsed != 0:
        normalized = parsed.normalize()
        significant_digits = len(normalized.as_tuple().digits)
        decimal_places = max(0, -normalized.as_tuple().exponent)
        if (
            significant_digits > AI_COST_BILLING_MAX_SIGNIFICANT_DIGITS
            or decimal_places > AI_COST_BILLING_MAX_DECIMAL_PLACES
        ):
            raise AICostReconciliationError(
                "{} precision exceeds the reconciliation limit".format(
                    field
                )
            )
    return parsed


def _explicit_billing_provider(value: Any) -> str:
    provider = str(value or "").strip().lower()
    aliases = {
        "anthropic": "anthropic",
        "claude": "anthropic",
        "deepseek": "deepseek",
        "gpt": "openai",
        "openai": "openai",
    }
    if provider not in aliases:
        raise AICostReconciliationError(
            "Provider billing provider is invalid"
        )
    return aliases[provider]


def normalize_provider_billing(
    billing: Mapping[str, Any] | None,
    *,
    expected_provider: Any = None,
) -> dict[str, Any] | None:
    """Validate an explicitly authoritative, non-secret provider cost record."""
    if billing is None:
        return None
    if not isinstance(billing, Mapping):
        raise AICostReconciliationError(
            "Provider billing data must be an object"
        )
    observed_status = str(billing.get("status") or "").strip().lower()
    status_details = {
        "pending": {
            "provider_billing_status": "pending",
            "reconciliation_status": "provider_billing_pending",
        },
        "delayed": {
            "provider_billing_status": "delayed",
            "reconciliation_status": "provider_billing_delayed",
        },
        "partial": {
            "provider_billing_status": "partial",
            "reconciliation_status": "provider_billing_partial",
        },
        "unavailable": {
            "provider_billing_status": "unavailable",
            "reconciliation_status": "provider_billing_unavailable",
        },
    }.get(observed_status)
    if status_details is not None:
        raise AICostReconciliationError(
            "Provider billing data is not final and authoritative",
            details=status_details,
        )
    if billing.get("authoritative") is not True:
        raise AICostReconciliationError(
            "Provider billing data was not explicitly marked authoritative",
            details=status_details,
        )
    source = str(billing.get("source") or "").strip().lower()
    if source not in _AUTHORITATIVE_BILLING_SOURCES:
        raise AICostReconciliationError(
            "Provider billing source is not an approved authority"
        )
    currency = str(billing.get("currency") or "").strip().upper()
    if re.fullmatch(r"[A-Z]{3}", currency) is None:
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
    expected = (
        _explicit_billing_provider(expected_provider)
        if str(expected_provider or "").strip()
        else ""
    )
    supplied_provider = ""
    if str(billing.get("provider") or "").strip():
        supplied_provider = _explicit_billing_provider(
            billing.get("provider")
        )
    if expected and supplied_provider and expected != supplied_provider:
        raise AICostReconciliationError(
            "Provider billing provider does not match the inference provider"
        )
    normalized = {
        "authoritative": True,
        "source": source,
        "scope": "request",
        "currency": currency,
        "amount": format(amount, "f"),
    }
    resolved_provider = expected or supplied_provider
    if resolved_provider:
        normalized["provider"] = resolved_provider
    return normalized


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
    expected_provider = normalize_provider(None, provider)
    return normalize_provider_billing(
        candidate,
        expected_provider=expected_provider,
    )


def extract_provider_billing_result(
    provider: Any,
    response: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return sanitized billing or a failure-visible status without raw data."""
    try:
        return {
            "billing": extract_provider_billing(provider, response),
            "error": None,
        }
    except AICostReconciliationError as exc:
        return {
            "billing": None,
            "error": _billing_error_marker(
                exc,
                provider_response_received=True,
            ),
        }


def _reconciliation_fields(
    estimate_usd: float,
    billing: Mapping[str, Any] | list[Any] | None,
    *,
    expected_provider: Any = None,
    provider_called: bool = False,
    usage_available: bool = False,
    billing_error: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    common = {
        "provider_authoritative_cost_usd": None,
        "provider_authoritative_cost_usd_text": None,
        "provider_authoritative_cost": None,
        "provider_authoritative_cost_text": None,
        "provider_authoritative_cost_currency": None,
        "provider_billing_currency": None,
        "provider_billing_source": None,
        "reconciliation_difference_usd": None,
        "reconciliation_difference_percent": None,
        "billing_data_invalid": False,
    }
    sanitized_error = _sanitize_billing_error_marker(billing_error)
    if sanitized_error is not None:
        return dict(
            common,
            provider_billing_status=sanitized_error[
                "provider_billing_status"
            ],
            reconciliation_status=sanitized_error[
                "reconciliation_status"
            ],
            billing_data_missing=sanitized_error["billing_data_missing"],
            billing_data_invalid=sanitized_error["billing_data_invalid"],
        )
    if billing is None:
        if not provider_called:
            return dict(
                common,
                provider_billing_status="not_applicable",
                reconciliation_status="not_called",
                billing_data_missing=False,
            )
        return dict(
            common,
            provider_billing_status="unavailable",
            reconciliation_status="provider_billing_unavailable",
            billing_data_missing=True,
        )

    candidates = billing if isinstance(billing, list) else [billing]
    if len(candidates) > AI_COST_MAX_RECONCILIATION_RECORDS:
        raise AICostReconciliationError(
            "Provider billing record count exceeds the reconciliation limit"
        )
    normalized = [
        normalize_provider_billing(
            item,
            expected_provider=expected_provider,
        )
        for item in candidates
    ]
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
    with localcontext() as decimal_context:
        decimal_context.prec = 50
        authoritative_decimal = sum(
            Decimal(str(item["amount"])) for item in normalized
        )
    if authoritative_decimal > AI_COST_BILLING_MAX_AMOUNT:
        raise AICostReconciliationError(
            "Provider billing total exceeds the reconciliation limit"
        )
    authoritative_native = float(authoritative_decimal)
    authoritative_text = format(authoritative_decimal, "f")
    if currency != "USD":
        return dict(
            common,
            provider_billing_status="authoritative_non_usd",
            provider_authoritative_cost=authoritative_native,
            provider_authoritative_cost_text=authoritative_text,
            provider_authoritative_cost_currency=currency,
            provider_billing_currency=currency,
            provider_billing_source=",".join(sorted(sources)),
            reconciliation_status="currency_conversion_unavailable",
            billing_data_missing=False,
        )
    if not usage_available:
        return dict(
            common,
            provider_billing_status="authoritative",
            provider_authoritative_cost_usd=authoritative_native,
            provider_authoritative_cost_usd_text=authoritative_text,
            provider_authoritative_cost=authoritative_native,
            provider_authoritative_cost_text=authoritative_text,
            provider_authoritative_cost_currency="USD",
            provider_billing_currency="USD",
            provider_billing_source=",".join(sorted(sources)),
            reconciliation_status="estimate_usage_unavailable",
            billing_data_missing=False,
        )
    with localcontext() as decimal_context:
        decimal_context.prec = 50
        estimate_decimal = Decimal(str(estimate_usd))
        difference_decimal = authoritative_decimal - estimate_decimal
        difference_percent_decimal = (
            difference_decimal / estimate_decimal * Decimal(100)
            if estimate_decimal > 0
            else None
        )
    return dict(
        common,
        provider_billing_status="authoritative",
        provider_authoritative_cost_usd=authoritative_native,
        provider_authoritative_cost_usd_text=authoritative_text,
        provider_authoritative_cost=authoritative_native,
        provider_authoritative_cost_text=authoritative_text,
        provider_authoritative_cost_currency="USD",
        provider_billing_currency="USD",
        provider_billing_source=",".join(sorted(sources)),
        reconciliation_status="reconciled",
        reconciliation_difference_usd=float(difference_decimal),
        reconciliation_difference_percent=(
            float(difference_percent_decimal)
            if difference_percent_decimal is not None
            else None
        ),
        billing_data_missing=False,
    )


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
    billing_error = _sanitize_billing_error_marker(
        normalized.get(_PROVIDER_BILLING_ERROR_FIELD)
    )
    usage_error = str(normalized.get(_USAGE_ERROR_FIELD) or "")
    usage_missing = normalized.get(_USAGE_MISSING_FIELD) is True

    explicit_provider_billing = provider_billing is not None
    if provider_billing is None:
        embedded = normalized.get(_PROVIDER_BILLING_FIELD)
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

    usage_counters_present = bool(
        api_calls
        or input_tokens
        or output_tokens
        or hit
        or miss
    )
    usage_available = (
        usage_counters_present and not usage_error and not usage_missing
    )
    provider_called = bool(
        usage_counters_present
        or usage_error
        or usage_missing
        or provider_billing is not None
        or (
            billing_error is not None
            and billing_error.get("provider_response_received") is True
        )
    )
    details.update(
        {
            "estimated_cost_usd": (
                None
                if usage_error or usage_missing
                else float(estimate_usd)
            ),
            "cost_value_type": (
                "local_estimate_unavailable"
                if usage_error or usage_missing
                else "local_estimate"
            ),
            "cost_authority": "local_rate_table",
            "usage_authority": (
                "provider_response_invalid"
                if usage_error
                else (
                    "provider_response_missing"
                    if usage_missing
                    else (
                        "provider_response"
                        if usage_available
                        else "not_returned"
                    )
                )
            ),
            "usage_validation_status": (
                "invalid"
                if usage_error
                else (
                    "missing"
                    if usage_missing
                    else (
                        "valid"
                        if usage_counters_present
                        else "not_applicable"
                    )
                )
            ),
            "usage_validation_reason": (
                usage_error
                or (
                    "provider_usage_counters_unavailable"
                    if usage_missing
                    else None
                )
            ),
            "estimate_status": (
                "usage_invalid"
                if usage_error
                else (
                    "usage_unavailable"
                    if usage_missing
                    else (
                        "available"
                        if usage_available
                        else (
                            "usage_unavailable"
                            if provider_called
                            else "not_applicable"
                        )
                    )
                )
            ),
        }
    )
    try:
        reconciliation_fields = _reconciliation_fields(
            float(estimate_usd),
            provider_billing,
            expected_provider=resolved_provider,
            provider_called=provider_called,
            usage_available=usage_available,
            billing_error=billing_error,
        )
    except AICostReconciliationError as exc:
        if explicit_provider_billing:
            raise
        reconciliation_fields = _reconciliation_fields(
            float(estimate_usd),
            None,
            expected_provider=resolved_provider,
            provider_called=provider_called,
            usage_available=usage_available,
            billing_error=_billing_error_marker(
                exc,
                provider_response_received=True,
            ),
        )
    details.update(reconciliation_fields)
    try:
        config = guardrail_configuration(environ)
        details["guardrail_enabled"] = config["enabled"]
        details["guardrail_limit_usd"] = config["limit_usd"]
        details["guardrail_limit_usd_text"] = config.get("limit_usd_text")
        details["guardrail_status"] = (
            "configured" if config["enabled"] else "disabled"
        )
    except AICostGuardrailConfigurationError:
        # Reconciliation reporting must not hide the original guardrail error.
        details["guardrail_enabled"] = False
        details["guardrail_limit_usd"] = None
        details["guardrail_limit_usd_text"] = None
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
        if len(raw) > 128:
            raise InvalidOperation
        limit = Decimal(raw)
    except InvalidOperation:
        raise AICostGuardrailConfigurationError(
            "AI cost guardrail configuration {} must be a finite number "
            "greater than 0 and no more than {}".format(
                AI_COST_GUARDRAIL_ENV,
                AI_COST_GUARDRAIL_MAX_USD,
            )
        )
    normalized_limit = limit.normalize() if limit else limit
    limit_float = float(limit) if limit.is_finite() else 0.0
    if (
        not limit.is_finite()
        or limit <= 0
        or limit > AI_COST_GUARDRAIL_MAX_USD
        or not limit_float > 0
        or len(normalized_limit.as_tuple().digits)
        > AI_COST_BILLING_MAX_SIGNIFICANT_DIGITS
        or max(0, -normalized_limit.as_tuple().exponent)
        > AI_COST_BILLING_MAX_DECIMAL_PLACES
    ):
        raise AICostGuardrailConfigurationError(
            "AI cost guardrail configuration {} must be a finite number "
            "greater than 0 and no more than {}".format(
                AI_COST_GUARDRAIL_ENV,
                AI_COST_GUARDRAIL_MAX_USD,
            )
        )
    return {
        "enabled": True,
        "limit_usd": limit_float,
        "limit_usd_text": format(limit, "f"),
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
    safe_model = _safe_model_identifier(model)
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
    if output_value is None:
        max_output_tokens = 4096
    elif isinstance(output_value, bool) or not isinstance(output_value, int):
        raise AICostGuardrailError(
            "AI cost guardrail blocked the request before provider transport: "
            "the requested output-token ceiling is invalid.",
            details={
                "enabled": True,
                "status": "blocked",
                "provider": resolved,
                "model": safe_model,
                "reason": "invalid_output_token_ceiling",
            },
        )
    else:
        max_output_tokens = output_value
    if max_output_tokens <= 0:
        raise AICostGuardrailError(
            "AI cost guardrail blocked the request before provider transport: "
            "the requested output-token ceiling must be greater than zero.",
            details={
                "enabled": True,
                "status": "blocked",
                "provider": resolved,
                "model": safe_model,
                "reason": "nonpositive_output_token_ceiling",
            },
        )
    if max_output_tokens > AI_COST_MAX_OUTPUT_TOKENS:
        raise AICostGuardrailError(
            "AI cost guardrail blocked the request before provider transport: "
            "the requested output-token ceiling exceeds the validation limit.",
            details={
                "enabled": True,
                "status": "blocked",
                "provider": resolved,
                "model": safe_model,
                "reason": "output_token_ceiling_too_large",
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
    estimate_usd = float(estimate_decimal)
    return {
        "provider": resolved,
        "model": safe_model,
        "estimated_input_token_ceiling": estimated_input_tokens,
        "max_output_tokens": max_output_tokens,
        "estimated_request_ceiling_usd": estimate_usd,
        "estimated_request_ceiling_usd_text": str(estimate_decimal),
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
    if Decimal(estimate["estimated_request_ceiling_usd_text"]) > Decimal(
        config["limit_usd_text"]
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
            if isinstance(observed_operations, bool):
                raise ValueError("integer required")
            parsed_operations = Decimal(str(observed_operations))
            if (
                not parsed_operations.is_finite()
                or parsed_operations < 0
                or parsed_operations != parsed_operations.to_integral_value()
                or parsed_operations > AI_COST_MAX_TOKEN_COUNT
            ):
                raise ValueError("bounded non-negative integer required")
            operations = int(parsed_operations)
        except (InvalidOperation, TypeError, ValueError, OverflowError):
            operations = None
    return {
        "provider": _safe_external_provider_identifier(provider),
        "provider_billing_status": "unavailable",
        "provider_authoritative_cost": None,
        "provider_billing_currency": None,
        "reconciliation_status": "provider_billing_unavailable",
        "observed_operations": operations,
        "billing_data_missing": True,
        "reason": _safe_billing_reason(reason),
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
    usage_error = str(normalized.get(_USAGE_ERROR_FIELD) or "")
    usage_missing = normalized.get(_USAGE_MISSING_FIELD) is True
    usage_evidence = bool(
        calls
        or usage_int(normalized, "input_tokens")
        or usage_int(normalized, "output_tokens")
        or usage_int(normalized, "prompt_cache_hit_tokens")
        or usage_int(normalized, "prompt_cache_miss_tokens")
        or usage_error
        or usage_missing
    )
    billing_error = _sanitize_billing_error_marker(
        normalized.get(_PROVIDER_BILLING_ERROR_FIELD)
    )
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
    elif usage_evidence or (
        billing_error is not None
        and billing_error.get("provider_response_received") is True
    ):
        call_status = "provider_response_received"
        reconciliation = "provider_billing_unavailable"
    elif getattr(error, "code", None) is not None or getattr(
        error,
        "status",
        None,
    ) is not None:
        call_status = "provider_error_response_received"
        reconciliation = "provider_billing_unavailable"
    else:
        call_status = "ambiguous_no_provider_usage_returned"
        reconciliation = "ambiguous_provider_charge"
    if billing_error is not None and call_status != "not_called":
        reconciliation = billing_error["reconciliation_status"]
    not_called = reconciliation == "not_called"
    invalid = (
        billing_error is not None
        and billing_error.get("billing_data_invalid") is True
    ) or isinstance(error, AICostReconciliationError)
    billing_status = (
        "not_applicable"
        if not_called
        else (
            billing_error["provider_billing_status"]
            if billing_error is not None
            else ("invalid" if invalid else "unavailable")
        )
    )
    return {
        "paid_call_status": call_status,
        "billing_reconciliation": {
            "provider": normalize_provider(model, provider),
            "model": _safe_model_identifier(model),
            "usage_authority": (
                "provider_response_invalid"
                if usage_error
                else (
                    "provider_response_missing"
                    if usage_missing
                    else (
                        "provider_response"
                        if usage_evidence
                        else "not_returned"
                    )
                )
            ),
            "provider_billing_status": billing_status,
            "provider_authoritative_cost_usd": None,
            "reconciliation_status": reconciliation,
            "billing_data_missing": (
                False
                if not_called or invalid
                else (
                    billing_error["billing_data_missing"]
                    if billing_error is not None
                    else True
                )
            ),
            "billing_data_invalid": invalid,
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
    "extract_provider_billing_result",
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
