from __future__ import annotations

import math
import re
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


def _normalize_contribution_rule(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise RuleValidationError(f"{field_name} must be a JSON object.")
    contribution = dict(value)
    for key in ("employee_rate", "employer_rate"):
        rate = _finite_number(contribution.get(key, 0), f"{field_name}.{key}")
        if not 0 <= rate <= 1:
            raise RuleValidationError(f"{field_name}.{key} must be between 0 and 1.")
        contribution[key] = rate

    cap = contribution.get("annual_cap")
    if cap not in (None, ""):
        cap = _finite_number(cap, f"{field_name}.annual_cap")
        if cap < 0:
            raise RuleValidationError(f"{field_name}.annual_cap cannot be negative.")
        contribution["annual_cap"] = cap
    else:
        contribution["annual_cap"] = None

    contribution["include_bonus"] = _strict_bool(
        contribution.get("include_bonus"), f"{field_name}.include_bonus", True
    )
    contribution["employee_contribution_tax_deductible"] = _strict_bool(
        contribution.get("employee_contribution_tax_deductible"),
        f"{field_name}.employee_contribution_tax_deductible",
        False,
    )
    scheme = str(contribution.get("scheme") or "Statutory contribution").strip()
    if len(scheme) > 200:
        raise RuleValidationError("Contribution scheme name is too long.")
    contribution["scheme"] = scheme or "Statutory contribution"
    return contribution


def _normalize_contribution_profiles(values: Any) -> list[dict[str, Any]]:
    if values in (None, ""):
        return []
    if not isinstance(values, (list, tuple)) or len(values) > 20:
        raise RuleValidationError("contribution_profiles must be a list of at most 20 profiles.")
    profiles: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(values):
        if not isinstance(raw, Mapping):
            raise RuleValidationError(f"Contribution profile {index + 1} must be a JSON object.")
        profile_id = _clean_text(raw.get("id"), f"Contribution profile {index + 1} id", max_length=80)
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", profile_id):
            raise RuleValidationError(f"Contribution profile {index + 1} id is invalid.")
        if profile_id in seen:
            raise RuleValidationError(f"Duplicate contribution profile id: {profile_id}.")
        seen.add(profile_id)
        label = _clean_text(raw.get("label"), f"Contribution profile {index + 1} label", max_length=160)
        normalized = dict(raw)
        normalized["id"] = profile_id
        normalized["label"] = label
        normalized.update(_normalize_contribution_rule(raw, f"contribution_profiles[{index}]"))

        periods_raw = raw.get("periods")
        if periods_raw not in (None, ""):
            if not isinstance(periods_raw, (list, tuple)) or not periods_raw or len(periods_raw) > 12:
                raise RuleValidationError(f"Contribution profile {label} periods must be a non-empty list.")
            periods: list[dict[str, Any]] = []
            expected_start = 1
            for period_index, period_raw in enumerate(periods_raw):
                if not isinstance(period_raw, Mapping):
                    raise RuleValidationError(f"Contribution profile {label} period {period_index + 1} is invalid.")
                try:
                    start_month = int(period_raw.get("start_month"))
                    end_month = int(period_raw.get("end_month"))
                except (TypeError, ValueError) as exc:
                    raise RuleValidationError(f"Contribution profile {label} period months must be whole numbers.") from exc
                if start_month != expected_start or not start_month <= end_month <= 12:
                    raise RuleValidationError(f"Contribution profile {label} periods must cover months 1 to 12 without gaps.")
                period = _normalize_contribution_rule(
                    {**normalized, **dict(period_raw)},
                    f"contribution_profiles[{index}].periods[{period_index}]",
                )
                period["start_month"] = start_month
                period["end_month"] = end_month
                periods.append(period)
                expected_start = end_month + 1
            if expected_start != 13:
                raise RuleValidationError(f"Contribution profile {label} periods must end at month 12.")
            normalized["periods"] = periods
        profiles.append(normalized)
    return profiles


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

    contribution = _normalize_contribution_rule(rule["contribution_rule"], "contribution_rule")
    contribution_profiles = _normalize_contribution_profiles(rule.get("contribution_profiles"))
    default_profile = str(rule.get("default_contribution_profile") or "").strip()
    if contribution_profiles:
        profile_ids = {profile["id"] for profile in contribution_profiles}
        if not default_profile:
            default_profile = contribution_profiles[0]["id"]
        if default_profile not in profile_ids:
            raise RuleValidationError("default_contribution_profile does not match a contribution profile.")
    elif default_profile:
        raise RuleValidationError("default_contribution_profile requires contribution_profiles.")

    normalized = dict(rule)
    normalized["country"] = country
    normalized["residency"] = residency
    normalized["currency"] = currency
    normalized["tax_year"] = tax_year
    normalized["tax_brackets"] = normalized_brackets
    normalized["contribution_rule"] = contribution
    normalized["contribution_profiles"] = contribution_profiles
    if default_profile:
        normalized["default_contribution_profile"] = default_profile
    else:
        normalized.pop("default_contribution_profile", None)
    normalized["personal_reliefs_allowed"] = _strict_bool(
        rule.get("personal_reliefs_allowed"), "personal_reliefs_allowed", True
    )
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
