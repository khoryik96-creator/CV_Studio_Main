"""Spider (AI Crawler) candidate data-shaping helpers.

Behaviour-preserving extraction of the pure candidate-record shaping logic from
the legacy web shell (Phase 7B): numeric coercion, salary and notice-period
snapshots, JobAdder custom-field lookup, candidate-card projection, record
identity keys, and the summary/detail deep-merge that fills missing list-result
fields from the full candidate representation.

Pure functions of their inputs - no Flask, no globals, no network, no JobAdder
or provider access. Depends only on the stateless field helpers already
extracted into ``cvstudio_spider_boolean``. This module never imports ``app``.
"""

import re
from datetime import date, datetime

from cvstudio_spider_boolean import _spider_flatten, _spider_normalized_record_label


def _spider_number(value):
    try:
        number = float(value)
        return number if number == number else None
    except Exception:
        try:
            cleaned = re.sub(r"[^0-9.\-]", "", str(value or ""))
            return float(cleaned) if cleaned else None
        except Exception:
            return None


def _spider_salary_snapshot(salary, is_range=False):
    if not isinstance(salary, dict):
        return None
    currency = str(salary.get("currency") or salary.get("currencyCode") or "").strip().upper()
    rate_per = str(salary.get("ratePer") or salary.get("period") or "").strip()
    low = _spider_number(salary.get("rateLow") if is_range else salary.get("rate"))
    high = _spider_number(salary.get("rateHigh")) if is_range else low
    if low is None and is_range:
        low = _spider_number(salary.get("rate") or salary.get("amount") or salary.get("value"))
    if high is None:
        high = low
    if low is None and high is None:
        return None
    values = [x for x in (low, high) if x is not None]
    lo = min(values) if values else None
    hi = max(values) if values else None
    def fmt(n):
        if n is None:
            return ""
        rounded = round(n)
        return "{:,.0f}".format(rounded) if abs(n - rounded) < 0.005 else "{:,.2f}".format(n).rstrip("0").rstrip(".")
    display_value = fmt(lo)
    if hi is not None and lo is not None and abs(hi - lo) > 0.005:
        display_value += " to " + fmt(hi)
    display = ((currency + " ") if currency else "") + display_value
    if rate_per:
        display += " / " + rate_per
    factor = {"hour": 173.333, "day": 21.666, "week": 4.333, "month": 1.0, "year": 1.0 / 12.0}.get(rate_per.lower(), 1.0)
    representative = lo if lo is not None else hi
    monthly = representative * factor if representative is not None else None
    return {"display": display.strip(), "sort": monthly, "currency": currency, "ratePer": rate_per}


def _spider_custom_field_value(candidate, aliases):
    aliases = [re.sub(r"[^a-z0-9]", "", str(x or "").lower()) for x in aliases]
    custom = candidate.get("custom") if isinstance(candidate, dict) else None
    if not isinstance(custom, list):
        return None
    for item in custom:
        if not isinstance(item, dict):
            continue
        name = re.sub(r"[^a-z0-9]", "", str(item.get("name") or item.get("label") or "").lower())
        if any(alias and (alias == name or alias in name) for alias in aliases):
            return item.get("value")
    return None


def _spider_notice_snapshot(candidate):
    availability = candidate.get("availability") if isinstance(candidate, dict) else None
    if isinstance(availability, dict):
        if availability.get("immediate") is True:
            return {"display": "Immediate", "sort": 0}
        relative = availability.get("relative")
        if isinstance(relative, dict):
            period = _spider_number(relative.get("period"))
            unit = str(relative.get("unit") or "").strip()
            if period is not None and unit:
                n = int(period) if float(period).is_integer() else period
                label = unit.rstrip("s") + ("" if float(period) == 1 else "s")
                unit_low = unit.lower()
                day_factor = 1 if unit_low.startswith("day") else 7 if unit_low.startswith("week") else 30 if unit_low.startswith("month") else 365 if unit_low.startswith("year") else 30
                days = float(period) * day_factor
                return {"display": "{} {}".format(n, label), "sort": days}
        date_value = str(availability.get("date") or "").strip()
        if date_value:
            try:
                dt = datetime.fromisoformat(date_value[:10]).date()
                days = max(0, (dt - date.today()).days)
            except Exception:
                days = None
            return {"display": date_value[:10], "sort": days}
    raw = _spider_custom_field_value(candidate, ["notice period", "notice", "availability", "available from"])
    if raw not in (None, "", [], {}):
        text = re.sub(r"\s+", " ", " ".join(_spider_flatten(raw))).strip()
        if re.search(r"\b(immediate|immediately|asap|available now)\b", text, re.I):
            return {"display": "Immediate", "sort": 0}
        m = re.search(r"(\d+(?:\.\d+)?)\s*(day|week|month)s?", text, re.I)
        if m:
            number = float(m.group(1))
            unit = m.group(2).lower()
            days = number * ({"day": 1, "week": 7, "month": 30}[unit])
            return {"display": text[:120], "sort": days}
        return {"display": text[:120], "sort": None}
    return None


def _spider_card_fields(candidate):
    candidate = candidate if isinstance(candidate, dict) else {}
    employment = candidate.get("employment") if isinstance(candidate.get("employment"), dict) else {}
    current = employment.get("current") if isinstance(employment.get("current"), dict) else {}
    ideal = employment.get("ideal") if isinstance(employment.get("ideal"), dict) else {}
    current_salary = _spider_salary_snapshot(current.get("salary"), False)
    expected_salary = _spider_salary_snapshot(ideal.get("salary"), True)
    if not expected_salary:
        for other in ideal.get("other") or []:
            if isinstance(other, dict):
                expected_salary = _spider_salary_snapshot(other.get("salary"), True)
                if expected_salary:
                    break
    return {
        "currentSalary": current_salary,
        "expectedSalary": expected_salary,
        "notice": _spider_notice_snapshot(candidate),
    }


def _spider_custom_record_key(item):
    if not isinstance(item, dict):
        return ""
    for key in ("fieldId", "fieldID", "customFieldId", "customFieldID", "id"):
        value = item.get(key)
        if value not in (None, ""):
            return "id:" + str(value).strip().casefold()
    label = _spider_normalized_record_label(item)
    return "label:" + label if label else ""


def _spider_work_record_key(item):
    if not isinstance(item, dict):
        return ""
    for key in ("id", "workTypeId", "workTypeID", "typeId", "typeID"):
        value = item.get(key)
        if value not in (None, ""):
            return "id:" + str(value).strip().casefold()
    work_type = item.get("workType")
    if isinstance(work_type, dict):
        for key in ("id", "value", "name", "label"):
            value = work_type.get(key)
            if value not in (None, ""):
                return "work:" + re.sub(r"[^a-z0-9]+", "", str(value).casefold())
    elif work_type not in (None, ""):
        return "work:" + re.sub(r"[^a-z0-9]+", "", str(work_type).casefold())
    for key in ("type", "name", "label"):
        value = item.get(key)
        if value not in (None, ""):
            return "work:" + re.sub(r"[^a-z0-9]+", "", str(value).casefold())
    return ""


def _spider_merge_record_lists(primary, secondary, key_func):
    left = list(primary) if isinstance(primary, list) else []
    right = list(secondary) if isinstance(secondary, list) else []
    merged = [dict(item) if isinstance(item, dict) else item for item in left]
    positions = {}
    for index, item in enumerate(merged):
        key = key_func(item)
        if key and key not in positions:
            positions[key] = index
    for item in right:
        if not isinstance(item, dict):
            if item not in merged:
                merged.append(item)
            continue
        key = key_func(item)
        if key and key in positions and isinstance(merged[positions[key]], dict):
            merged[positions[key]] = _spider_merge_missing_json(merged[positions[key]], item, 1)
        else:
            if key:
                positions[key] = len(merged)
            merged.append(dict(item))
    return merged


def _spider_merge_missing_json(primary, secondary, depth=0):
    """Deep-fill missing JobAdder list fields from full candidate detail.

    Existing list-result values stay authoritative.  Dictionaries recurse, while
    ordinary lists append missing values.  Candidate custom fields and expected-
    salary work-type lists receive identity-aware merging in the wrapper below.
    """
    if depth > 10:
        return primary
    if isinstance(primary, dict) and isinstance(secondary, dict):
        merged = dict(primary)
        for key, value in secondary.items():
            if key not in merged or merged.get(key) in (None, "", [], {}):
                merged[key] = value
            elif isinstance(merged.get(key), dict) and isinstance(value, dict):
                merged[key] = _spider_merge_missing_json(merged.get(key), value, depth + 1)
            elif isinstance(merged.get(key), list) and isinstance(value, list):
                # Generic list fill is conservative.  Identity-aware business
                # lists are merged below so a detail salary/notice cannot vanish.
                out = list(merged.get(key) or [])
                for candidate in value:
                    if candidate not in out:
                        out.append(candidate)
                merged[key] = out
        return merged
    if isinstance(primary, list) and isinstance(secondary, list):
        out = list(primary)
        for value in secondary:
            if value not in out:
                out.append(value)
        return out
    if primary in (None, "", [], {}):
        return secondary
    return primary


def _spider_merge_candidate_summary_and_detail(summary, detail):
    if not isinstance(summary, dict):
        summary = {"value": summary}
    if not isinstance(detail, dict):
        return dict(summary)
    merged = _spider_merge_missing_json(summary, detail)

    custom = _spider_merge_record_lists(summary.get("custom"), detail.get("custom"), _spider_custom_record_key)
    if custom:
        merged["custom"] = custom

    summary_employment = summary.get("employment") if isinstance(summary.get("employment"), dict) else {}
    detail_employment = detail.get("employment") if isinstance(detail.get("employment"), dict) else {}
    merged_employment = merged.get("employment") if isinstance(merged.get("employment"), dict) else {}
    summary_ideal = summary_employment.get("ideal") if isinstance(summary_employment.get("ideal"), dict) else {}
    detail_ideal = detail_employment.get("ideal") if isinstance(detail_employment.get("ideal"), dict) else {}
    merged_ideal = merged_employment.get("ideal") if isinstance(merged_employment.get("ideal"), dict) else {}
    ideal_other = _spider_merge_record_lists(summary_ideal.get("other"), detail_ideal.get("other"), _spider_work_record_key)
    if ideal_other:
        merged_ideal = dict(merged_ideal)
        merged_ideal["other"] = ideal_other
        merged_employment = dict(merged_employment)
        merged_employment["ideal"] = merged_ideal
        merged["employment"] = merged_employment

    # Retain a private scoring copy only.  Response construction removes it.
    merged["_spiderDetail"] = detail
    return merged
