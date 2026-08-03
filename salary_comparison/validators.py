from __future__ import annotations

import math
from typing import Any, Mapping
from urllib.parse import urlparse


class RuleValidationError(ValueError):
    pass


def _finite_number(value: Any, field_name: str) -> float:
    try:
        number = float(value)
    except Exception as exc:
        raise RuleValidationError(f"{field_name} must be numeric.") from exc
    if not math.isfinite(number):
        raise RuleValidationError(f"{field_name} must be finite.")
    if abs(number) > 1_000_000_000_000_000:
        raise RuleValidationError(f"{field_name} is outside the supported range.")
    return number


def _strict_bool(value: Any, field_name: str, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    text = str(value).strip().casefold()
    if text in {"true", "yes", "1", "on"}:
        return True
    if text in {"false", "no", "0", "off", ""}:
        return False
    raise RuleValidationError(f"{field_name} must be true or false.")


def _clean_text(value: Any, field_name: str, *, max_length: int) -> str:
    text = str(value or "").strip()
    if not text:
        raise RuleValidationError(f"{field_name} is required.")
    if len(text) > max_length:
        raise RuleValidationError(f"{field_name} is too long.")
    return text


def _normalize_urls(values: Any) -> list[str]:
    if values in (None, ""):
        return []
    if not isinstance(values, (list, tuple)):
        raise RuleValidationError("source_urls must be a list.")
    if len(values) > 10:
        raise RuleValidationError("Too many source URLs.")
    result: list[str] = []
    for raw in values:
        url = str(raw or "").strip()
        if not url:
            continue
        if len(url) > 2048:
            raise RuleValidationError("A source URL is too long.")
        parsed = urlparse(url)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            raise RuleValidationError("Source URLs must be valid http:// or https:// URLs.")
        if parsed.username or parsed.password:
            raise RuleValidationError("Source URLs cannot contain embedded credentials.")
        if url not in result:
            result.append(url)
    return result


def _normalize_notes(values: Any) -> list[str]:
    if values in (None, ""):
        return []
    if not isinstance(values, (list, tuple)):
        raise RuleValidationError("notes must be a list.")
    if len(values) > 50:
        raise RuleValidationError("Too many rule notes.")
    notes: list[str] = []
    for raw in values:
        text = str(raw or "").strip()
        if not text:
            continue
        if len(text) > 2000:
            raise RuleValidationError("A rule note is too long.")
        notes.append(text)
    return notes


def validate_rule(rule: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(rule, Mapping):
        raise RuleValidationError("Rule must be a JSON object.")

    required = ("country", "tax_year", "residency", "currency", "tax_brackets", "contribution_rule")
    missing = [key for key in required if rule.get(key) in (None, "", [])]
    if missing:
        raise RuleValidationError(f"Missing required rule fields: {', '.join(missing)}")

    country = _clean_text(rule["country"], "Country", max_length=120)
    residency = _clean_text(rule["residency"], "Residency", max_length=80)
    currency = str(rule["currency"]).strip().upper()
    if len(currency) != 3 or not currency.isalpha():
        raise RuleValidationError("Currency must be a three-letter code.")

    try:
        tax_year = int(rule["tax_year"])
    except (TypeError, ValueError) as exc:
        raise RuleValidationError("Tax year must be a whole number.") from exc
    if not 1900 <= tax_year <= 2200:
        raise RuleValidationError("Tax year is outside the supported range.")

    brackets_raw = rule["tax_brackets"]
    if not isinstance(brackets_raw, (list, tuple)):
        raise RuleValidationError("tax_brackets must be a list.")
    brackets = list(brackets_raw)
    if not brackets:
        raise RuleValidationError("At least one tax bracket is required.")
    if len(brackets) > 100:
        raise RuleValidationError("Too many tax brackets.")

    previous_upper = None
    open_ended_seen = False
    normalized_brackets: list[dict[str, Any]] = []
    for index, bracket in enumerate(brackets):
        if not isinstance(bracket, Mapping):
            raise RuleValidationError(f"Invalid tax bracket {index + 1}.")
        if open_ended_seen:
            raise RuleValidationError("An open-ended tax bracket must be the final bracket.")

        lower = _finite_number(bracket.get("lower"), f"Tax bracket {index + 1} lower bound")
        upper_raw = bracket.get("upper")
        upper = None if upper_raw in (None, "") else _finite_number(
            upper_raw, f"Tax bracket {index + 1} upper bound"
        )
        rate = _finite_number(bracket.get("rate"), f"Tax bracket {index + 1} rate")

        if lower < 0:
            raise RuleValidationError(f"Tax bracket {index + 1} has a negative lower bound.")
        if index == 0 and abs(lower) > 1e-9:
            raise RuleValidationError("The first tax bracket must start at zero.")
        if previous_upper is not None and abs(lower - previous_upper) > 1e-6:
            raise RuleValidationError(f"Tax brackets are not contiguous at bracket {index + 1}.")
        if upper is not None and upper <= lower:
            raise RuleValidationError(f"Tax bracket {index + 1} has an invalid upper bound.")
        if not 0 <= rate <= 1:
            raise RuleValidationError(f"Tax bracket {index + 1} has an invalid rate.")

        normalized_brackets.append({"lower": lower, "upper": upper, "rate": rate})
        previous_upper = upper
        open_ended_seen = upper is None

    if not open_ended_seen:
        raise RuleValidationError("The final tax bracket must be open-ended.")

    contribution_raw = rule["contribution_rule"]
    if not isinstance(contribution_raw, Mapping):
        raise RuleValidationError("contribution_rule must be a JSON object.")
    contribution = dict(contribution_raw)
    for key in ("employee_rate", "employer_rate"):
        value = _finite_number(contribution.get(key, 0), key)
        if not 0 <= value <= 1:
            raise RuleValidationError(f"{key} must be between 0 and 1.")
        contribution[key] = value

    cap = contribution.get("annual_cap")
    if cap not in (None, ""):
        cap = _finite_number(cap, "annual_cap")
        if cap < 0:
            raise RuleValidationError("annual_cap cannot be negative.")
        contribution["annual_cap"] = cap
    else:
        contribution["annual_cap"] = None

    contribution["include_bonus"] = _strict_bool(
        contribution.get("include_bonus"), "include_bonus", True
    )
    contribution["employee_contribution_tax_deductible"] = _strict_bool(
        contribution.get("employee_contribution_tax_deductible"),
        "employee_contribution_tax_deductible",
        False,
    )
    scheme = str(contribution.get("scheme") or "Statutory contribution").strip()
    if len(scheme) > 200:
        raise RuleValidationError("Contribution scheme name is too long.")
    contribution["scheme"] = scheme or "Statutory contribution"

    normalized = dict(rule)
    normalized["country"] = country
    normalized["residency"] = residency
    normalized["currency"] = currency
    normalized["tax_year"] = tax_year
    normalized["tax_brackets"] = normalized_brackets
    normalized["contribution_rule"] = contribution
    normalized["verified"] = _strict_bool(rule.get("verified"), "verified", False)
    normalized["tax_brackets_verified"] = _strict_bool(
        rule.get("tax_brackets_verified"),
        "tax_brackets_verified",
        normalized["verified"],
    )
    normalized["contribution_rule_verified"] = _strict_bool(
        rule.get("contribution_rule_verified"),
        "contribution_rule_verified",
        normalized["verified"],
    )
    title = rule.get("tax_schedule_title")
    normalized["tax_schedule_title"] = None if title in (None, "") else str(title).strip()[:500]
    normalized["source_urls"] = _normalize_urls(rule.get("source_urls"))
    normalized["notes"] = _normalize_notes(rule.get("notes"))
    if rule.get("last_updated") not in (None, ""):
        normalized["last_updated"] = str(rule.get("last_updated")).strip()[:100]
    return normalized
