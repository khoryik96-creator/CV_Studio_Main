"""Salary currency/amount parsing and formatting helpers for CV Studio.

Behaviour-preserving extraction from the app shell: currency detection, salary
amount tokenisation/parsing, component classification, display formatting, and
LLM usage/cost provenance helpers. Pure functions of their inputs -- no Flask,
no globals, no network. Depends only on the stdlib and the already-extracted
recruiter-typo normaliser.
"""

import re
from decimal import Decimal, ROUND_HALF_UP

from cvstudio_ja_typos import _ja_salary_normalize_recruiter_typos


_JA_CURRENCY_OPTIONS = {
    "BND": "Brunei Dollar (BND)",
    "KHR": "Cambodian Riel (KHR)",
    "IDR": "Indonesian Rupiah (IDR)",
    "LAK": "Lao Kip (LAK)",
    "MYR": "Malaysian Ringgit (MYR)",
    "MMK": "Myanmar Kyat (MMK)",
    "PHP": "Philippine Peso (PHP)",
    "SGD": "Singapore Dollar (SGD)",
    "THB": "Thai Baht (THB)",
    "VND": "Vietnamese Đồng (VND)",
    "CNY": "Chinese Yuan Renminbi (CNY)",
    "HKD": "Hong Kong Dollar (HKD)",
    "AUD": "Australian Dollar (AUD)",
    "EUR": "Euro (EUR) - Used in the European Union",
    "USD": "United States Dollar (USD)",
    "INR": "Indian Rupee (INR)",
}


_JA_CURRENCY_ALIAS_PATTERNS = [
    ("MYR", [r"(?<![a-z])myr(?![a-z])", r"(?<![a-z])rm(?![a-z])", r"malaysian\s+ringgit", r"\bringgit\b"]),
    ("SGD", [r"(?<![a-z])sgd(?![a-z])", r"(?<![a-z])s\$", r"singapore\s+dollars?", r"sing\s*dollars?"]),
    ("USD", [r"(?<![a-z])usd(?![a-z])", r"(?<![a-z])us\$", r"u\.?s\.?\s*dollars?", r"united\s+states\s+dollars?"]),
    ("AUD", [r"(?<![a-z])aud(?![a-z])", r"(?<![a-z])a\$", r"australian\s+dollars?"]),
    ("EUR", [r"(?<![a-z])eur(?![a-z])", r"€", r"\beuros?\b"]),
    ("INR", [r"(?<![a-z])inr(?![a-z])", r"₹", r"(?<![a-z])rs\.?(?![a-z])", r"indian\s+rupees?", r"\brupees?\b"]),
    ("IDR", [r"(?<![a-z])idr(?![a-z])", r"(?<![a-z])rp\.?(?![a-z])", r"indonesian\s+rupiah", r"\brupiah\b"]),
    ("BND", [r"(?<![a-z])bnd(?![a-z])", r"(?<![a-z])bn\$", r"brunei\s+dollars?"]),
    ("KHR", [r"(?<![a-z])khr(?![a-z])", r"cambodian\s+riel", r"\briel\b"]),
    ("LAK", [r"(?<![a-z])lak(?![a-z])", r"lao\s+kip", r"\bkip\b"]),
    ("MMK", [r"(?<![a-z])mmk(?![a-z])", r"myanmar\s+kyat", r"burmese\s+kyat", r"\bkyat\b"]),
    ("PHP", [r"(?<![a-z])php(?![a-z])", r"₱", r"philippine\s+pesos?", r"filipino\s+pesos?"]),
    ("THB", [r"(?<![a-z])thb(?![a-z])", r"฿", r"thai\s+baht", r"\bbaht\b"]),
    ("VND", [r"(?<![a-z])vnd(?![a-z])", r"₫", r"vietnamese\s+(?:dong|đồng)", r"\b(?:dong|đồng)\b"]),
    ("CNY", [r"(?<![a-z])cny(?![a-z])", r"(?<![a-z])rmb(?![a-z])", r"chinese\s+yuan", r"yuan\s+renminbi", r"\brenminbi\b", r"\byuan\b"]),
    ("HKD", [r"(?<![a-z])hkd(?![a-z])", r"(?<![a-z])hk\$", r"hong\s+kong\s+dollars?"]),
]


def _ja_salary_currency_candidates_from_field(raw):
    """Return supported currency aliases found in one salary field, in text order.

    The caller must pass only Current Salary Breakdown or Expected Salary.  The
    result is deliberately evidence-bearing so an AI response cannot override a
    single explicit alias and can only disambiguate between aliases actually
    present in the same field.
    """
    text = _ja_salary_normalize_recruiter_typos(raw)
    if not text.strip():
        return []
    by_code = {}
    for code, patterns in _JA_CURRENCY_ALIAS_PATTERNS:
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.I):
                item = {
                    "code": code,
                    "start": int(match.start()),
                    "end": int(match.end()),
                    "evidence": match.group(0),
                }
                previous = by_code.get(code)
                if previous is None or item["start"] < previous["start"]:
                    by_code[code] = item
    return sorted(by_code.values(), key=lambda item: (item["start"], item["code"]))


def _ja_salary_currency_from_field(raw):
    """Detect a supported JobAdder currency from one salary field only.

    A single explicit alias is authoritative.  When a field genuinely contains
    multiple currencies, this compatibility helper returns the earliest textual
    clue; `_ja_currency_selection` may let AI disambiguate only among those
    explicit candidates.
    """
    candidates = _ja_salary_currency_candidates_from_field(raw)
    return candidates[0]["code"] if candidates else None


def _ja_salary_plain_number(raw):
    tokens = _ja_salary_amount_tokens(raw)
    return int(tokens[0]["value"]) if tokens else None


def _ja_salary_has_actual_amount(raw):
    text = _ja_salary_normalize_recruiter_typos(raw).replace(",", "")
    return bool(re.search(r"\b\d+(?:\.\d+)?\s*[kK]\b", text) or re.search(r"\b\d{4,8}\b", text))


_JA_SALARY_ANNUAL_COMPONENT_RE = re.compile(
    r"(?:\b(?:1[2-9]|2[0-4])(?:\.\d+)?\s*(?:th|st|nd|rd)?\s*(?:mon+ths?|mnths?|mths?|mos?)\b|"
    r"(?:x|×)\s*(?:1[2-9]|2[0-4])(?:\.\d+)?\b|\b(?:1[2-9]|2[0-4])(?:\.\d+)?\s*(?:th|st|nd|rd)\s*(?:salary|pay|bonus)\b|\bAWS\b|\bannual\s+wage\s+supplement\b|"
    r"\b(?:contractual|guaranteed|fixed)\s+bonus\b|\bbonus\s+(?:contractual|guaranteed|fixed)\b)",
    re.I,
)


_JA_SALARY_EXCLUDED_COMPONENT_RE = re.compile(
    r"(?:\bbonus\b|\bannual\s+wage\s+supplement\b|\bAWS\b|\bEPF\b|\bKWSP\b|\bSOCSO\b|\bEIS\b|"
    r"\bcommission\b|\bincentive\b|\bvariable\b|\bperformance\b|\bRSU\b|\bESOP\b|\bstock\b|\bshares?\b|"
    r"\boptions?\b|\bclaims?\b|\bclaimable\b|\breimburse(?:ment|able)?\b|\bmedical\b|\binsurance\b|"
    r"\bemployer\s+contribution\b|\btravel\s+claim\b|\bparking\s+claim\b)",
    re.I,
)


def _ja_round_currency(value):
    """Round positive salary values consistently across Python and JavaScript.

    Python's built-in round uses banker's rounding while JavaScript Math.round
    rounds .5 upward for positive numbers. ROUND_HALF_UP removes that drift.
    """
    try:
        return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except Exception:
        return None


def _ja_salary_component_parts(raw):
    """Split a salary breakdown without breaking thousand separators."""
    normalized = _ja_salary_normalize_recruiter_typos(raw)
    return [
        part.strip()
        for part in re.split(r"\s*\+\s*|[;\n]+|,(?!\d{3}\b)", normalized)
        if part and part.strip()
    ]


def _ja_salary_amount_tokens(raw):
    """Return normalized salary amount tokens while ignoring periods/percentages.

    Besides K shorthand, support common regional salary notation used by the
    configured currency list: M/million, Indian lakh/lac/L and crore/Cr.  A bare
    `m` is treated as million only when the salary field contains an explicit
    currency clue, and `2m bonus`-style month shorthand is excluded.
    """
    text = _ja_salary_normalize_recruiter_typos(raw).replace(",", "")
    field_currency = _ja_salary_currency_from_field(text)
    # JobAdder stores monthly salary.  Annual/per-annum amounts are normalized
    # per salary component, not across the whole field.  This matters for input
    # such as ``RM120k annual + RM500 monthly allowance``: only the first
    # component is divided by 12.
    annual_re = re.compile(
        r"(?:\bper\s+annum\b|\bp\.?\s*a\.?\b|/\s*annum\b|"
        r"\bannual(?:ly)?\b|\bper\s+year\b|/\s*year\b|\byearly\b|\blpa\b)",
        re.I,
    )
    out = []
    currency_after = r"(?:RM|MYR|SGD|USD|AUD|EUR|IDR|PHP|BND|KHR|LAK|MMK|THB|VND|CNY|HKD|INR)"
    # Recruiter notes often omit whitespace between an amount and the component
    # label (for example ``32sllowance`` or ``16epf``).  Permit only known
    # salary-component labels here so the tokenizer does not start accepting
    # arbitrary digits embedded in prose.
    component_after = (
        r"(?:allowance|allowence|alowance|sllowance|epf|kwsp|socso|eis|"
        r"bonus|commission|incentive|claim|claims|reimbursement|reimbursements)"
    )
    pattern = re.compile(
        r"(\d+(?:\.\d+)?)(?![\d.])\s*"
        r"(million|millions|mil|crore|crores|cr|lpa|lakh|lakhs|lac|lacs|[kKmMLl])?"
        r"(?=\s*" + currency_after + r"\b|\s*" + component_after + r"\b|\b)",
        re.I,
    )
    for m in pattern.finditer(text):
        number = float(m.group(1))
        suffix_token = str(m.group(2) or "")
        suffix_lower = suffix_token.lower()
        suffix = text[m.end():m.end() + 32]
        prefix = text[max(0, m.start() - 16):m.start()]
        # Do not reinterpret the lower bound of ``15-30%`` as a fixed salary
        # amount.  The upper bound is already caught by the direct-percent
        # guard below; this companion guard covers the first number.
        if not suffix_token and re.match(
            r"\s*(?:-|–|—|to\b)\s*\d+(?:\.\d+)?\s*(?:%|percent\b|pct\b)",
            suffix,
            re.I,
        ):
            continue
        if re.match(r"\s*(?:%|percent\b|pct\b)", suffix, re.I):
            continue
        if re.match(r"\s*(?:th|st|nd|rd)?\s*(?:day|days|week|weeks|mon+th|mon+ths|mnth|mnths|mth|mths|mo|mos|year|years)\b", suffix, re.I):
            continue
        if 12 <= number <= 36 and re.match(r"\s*(?:th|st|nd|rd)\s*(?:salary|pay|bonus)\b", suffix, re.I):
            continue
        if 12 <= number <= 36 and re.search(r"(?:x|×)\s*$", prefix, re.I):
            continue
        if suffix_lower == "m" and number <= 12 and re.match(r"\s*(?:bonus|salary\s+months?|months?|mths?)\b", suffix, re.I):
            continue
        if re.search(r"(?:date|day|week|month|year)\s*$", prefix, re.I) and not suffix_token and number < 1000:
            continue

        scale = 1
        kind = "plain"
        if suffix_lower == "k":
            scale, kind = 1000, "thousand"
        elif suffix_lower in ("million", "millions", "mil"):
            scale, kind = 1000000, "million"
        elif suffix_lower == "m":
            if not field_currency:
                # Ambiguous without a salary currency clue; let AI assist rather
                # than deterministically turning month shorthand into millions.
                continue
            scale, kind = 1000000, "million"
        elif suffix_lower == "lpa":
            scale, kind = 100000, "lakh_per_annum"
        elif suffix_lower in ("l", "lakh", "lakhs", "lac", "lacs"):
            if suffix_lower == "l" and field_currency != "INR":
                continue
            scale, kind = 100000, "lakh"
        elif suffix_lower in ("cr", "crore", "crores"):
            scale, kind = 10000000, "crore"

        component_start = max(text.rfind("+", 0, m.start()), text.rfind(";", 0, m.start()), text.rfind("\n", 0, m.start())) + 1
        component_ends = [pos for pos in (text.find("+", m.end()), text.find(";", m.end()), text.find("\n", m.end())) if pos >= 0]
        component_end = min(component_ends) if component_ends else len(text)
        token_component = text[component_start:component_end]
        annual_divisor = 12 if (annual_re.search(token_component) or suffix_lower == "lpa") else 1
        value = _ja_round_currency(Decimal(str(number)) * Decimal(scale) / Decimal(annual_divisor))
        if value is None or value <= 0:
            continue
        out.append({
            "start": m.start(), "end": m.end(), "value": value,
            "raw": m.group(0), "isK": scale == 1000, "scale": scale,
            "scaleKind": kind, "numeric": number,
            "sourceFrequency": "annual" if annual_divisor == 12 else "monthly_or_unspecified",
            "annualDivisor": annual_divisor,
        })
    return out


def _ja_salary_component_is_excluded(part):
    text = _ja_salary_normalize_recruiter_typos(part)
    if _JA_SALARY_ANNUAL_COMPONENT_RE.search(text):
        return True
    if _JA_SALARY_EXCLUDED_COMPONENT_RE.search(text):
        return True
    if re.search(r"\d+(?:\.\d+)?\s*%", text):
        return True
    if re.fullmatch(r"\s*\d+(?:\.\d+)?\s*(?:days?|weeks?|months?|years?)\s*", text, re.I):
        return True
    return False


def _ja_salary_currency_label(currency):
    code = str(currency or "").upper()
    return {"MYR": "RM", "SGD": "SGD", "USD": "USD", "AUD": "AUD", "GBP": "GBP", "EUR": "EUR", "IDR": "IDR", "PHP": "PHP", "BND": "BND"}.get(code, code)


def _ja_salary_display(currency, min_value, max_value=None, equivalent=False):
    if min_value is None:
        return ""
    label = _ja_salary_currency_label(currency)
    left = "{:,}".format(int(min_value))
    prefix = (label + " ") if label else ""
    if max_value is not None and int(max_value) != int(min_value):
        body = "{}{} to {}{}".format(prefix, left, prefix, "{:,}".format(int(max_value)))
    else:
        body = prefix + left
    return body + ("/month equivalent" if equivalent else "/month")


def _ja_salary_parse_range(raw):
    clean = _ja_salary_normalize_recruiter_typos(raw).replace(",", "")
    pct = re.search(r"%|\bpercent\b|\bpct\b", clean, re.I)
    if pct:
        before = clean[:pct.start()]
        if not _ja_salary_amount_tokens(before):
            return None
    tokens = _ja_salary_amount_tokens(clean)
    if not tokens:
        return None
    if len(tokens) >= 2:
        first, second = tokens[0], tokens[1]
        between = clean[first["end"]:second["start"]]
        if re.search(r"(?:-|–|—|\bto\b|~)", between, re.I):
            left, right = int(first["value"]), int(second["value"])
            # In 13-15k / 20-25m shorthand, inherit the scale from the right.
            if int(first.get("scale") or 1) == 1 and int(second.get("scale") or 1) > 1 and float(first.get("numeric") or 0) < 1000:
                left = _ja_round_currency(
                    Decimal(str(first.get("numeric") or 0))
                    * Decimal(int(second.get("scale") or 1))
                    / Decimal(int(second.get("annualDivisor") or 1))
                )
            return {"min": min(left, right), "max": max(left, right)} if left > 0 and right > 0 else None
    value = int(tokens[0]["value"])
    return {"min": value, "max": value} if value > 0 else None


def _ja_salary_parse_percent_increment(raw):
    text = _ja_salary_normalize_recruiter_typos(raw).replace("％", "%")
    if not re.search(r"%|\bpercent\b|\bpct\b", text, re.I):
        return None
    num = r"([+-]?\d+(?:\.\d+)?)"
    unit = r"(?:%|percent|pct)"
    sep = r"(?:-|–|—|to|until|~)"
    patterns = [
        re.compile(num + r"\s*" + unit + r"\s*" + sep + r"\s*" + num + r"(?:\s*" + unit + r")?", re.I),
        re.compile(num + r"\s*(?:" + unit + r")?\s*" + sep + r"\s*" + num + r"\s*" + unit, re.I),
    ]
    for pattern in patterns:
        m = pattern.search(text)
        if m:
            lo, hi = float(m.group(1)), float(m.group(2))
            if lo > -100 and hi > -100 and max(abs(lo), abs(hi)) <= 500:
                return {"min": min(lo, hi), "max": max(lo, hi), "raw": m.group(0)}
    m = re.search(num + r"\s*" + unit, text, re.I)
    if m:
        value = float(m.group(1))
        if value > -100 and abs(value) <= 500:
            return {"min": value, "max": value, "raw": m.group(0)}
    return None


def _ja_salary_ai_num(value, minimum=0, maximum=1000000000):
    try:
        if value is None or isinstance(value, bool):
            return None
        number = Decimal(str(value))
        if number < Decimal(str(minimum)) or number > Decimal(str(maximum)):
            return None
        return float(number) if number != number.to_integral_value() else int(number)
    except Exception:
        return None


def _ja_salary_ai_sanitize(obj):
    if not isinstance(obj, dict):
        return None
    cur = obj.get("current") if isinstance(obj.get("current"), dict) else {}
    exp = obj.get("expected") if isinstance(obj.get("expected"), dict) else {}
    allowed = set(_JA_CURRENCY_OPTIONS)
    current_currency = str(cur.get("currency") or obj.get("currentCurrency") or "").strip().upper()
    expected_currency = str(exp.get("currency") or obj.get("expectedCurrency") or "").strip().upper()
    # Ignore legacy top-level currency output. It cannot prove which salary
    # field supplied the clue and could violate the strict field-scope rule.
    if current_currency not in allowed: current_currency = None
    if expected_currency not in allowed: expected_currency = None
    base = _ja_salary_ai_num(cur.get("baseMonthly"), 1)
    months = _ja_salary_ai_num(cur.get("guaranteedSalaryMonths"), 12, 36)
    allowance = _ja_salary_ai_num(cur.get("fixedMonthlyAllowance"), 0) or 0
    other = _ja_salary_ai_num(cur.get("otherFixedMonthlyCash"), 0) or 0
    # Employer EPF/KWSP is excluded from this workflow unless a future explicit
    # opt-in setting is added. Never let AI silently include it as monthly cash.
    epf = 0
    expected = {
        "currency": expected_currency,
        "explicitAmount": _ja_salary_ai_num(exp.get("explicitAmount"), 1),
        "explicitMin": _ja_salary_ai_num(exp.get("explicitMin"), 1),
        "explicitMax": _ja_salary_ai_num(exp.get("explicitMax"), 1),
        "sameAsCurrent": bool(exp.get("sameAsCurrent")),
        "percent": _ja_salary_ai_num(exp.get("percent"), 0, 500),
        "percentMin": _ja_salary_ai_num(exp.get("percentMin"), 0, 500),
        "percentMax": _ja_salary_ai_num(exp.get("percentMax"), 0, 500),
        "open": bool(exp.get("open")),
        "confidence": str(exp.get("confidence") or "").lower()[:12],
    }
    current = {
        "currency": current_currency,
        "baseMonthly": base,
        "guaranteedSalaryMonths": months,
        "fixedMonthlyAllowance": allowance,
        "otherFixedMonthlyCash": other,
        "includedEmployerEpf": epf,
        "excludedComponents": [],
        "evidence": [],
        "confidence": str(cur.get("confidence") or "").lower()[:12],
    }
    if base is None and not any(v is not None for v in (expected["explicitAmount"], expected["explicitMin"], expected["percent"], expected["percentMin"])) and not expected["sameAsCurrent"] and not expected["open"] and not current_currency and not expected_currency:
        return None
    selected = expected_currency or current_currency
    return {
        "currency": selected,
        "currentCurrency": current_currency,
        "expectedCurrency": expected_currency,
        "current": current,
        "expected": expected,
    }


def _ja_salary_usage_int(usage, *keys):
    for key in keys:
        try:
            if (usage or {}).get(key) is not None:
                return int((usage or {}).get(key) or 0)
        except Exception:
            pass
    return 0


def _ja_salary_cost_provenance(cost, paid_call_status):
    cost = cost if isinstance(cost, dict) else {}
    output = {
        "paidCallStatus": str(paid_call_status or ""),
        "estimatedCostUsd": cost.get("estimated_cost_usd"),
        "costValueType": str(cost.get("cost_value_type") or "local_estimate"),
        "costAuthority": str(cost.get("cost_authority") or "local_rate_table"),
        "usageAuthority": str(cost.get("usage_authority") or "not_returned"),
        "providerBillingStatus": str(
            cost.get("provider_billing_status") or "unavailable"
        ),
        "providerAuthoritativeCostUsd": cost.get(
            "provider_authoritative_cost_usd"
        ),
        "providerAuthoritativeCostUsdText": cost.get(
            "provider_authoritative_cost_usd_text"
        ),
        "providerAuthoritativeCost": cost.get(
            "provider_authoritative_cost"
        ),
        "providerAuthoritativeCostText": cost.get(
            "provider_authoritative_cost_text"
        ),
        "providerAuthoritativeCostCurrency": cost.get(
            "provider_authoritative_cost_currency"
        ),
        "providerBillingCurrency": cost.get("provider_billing_currency"),
        "providerBillingSource": cost.get("provider_billing_source"),
        "reconciliationStatus": str(
            cost.get("reconciliation_status")
            or "provider_billing_unavailable"
        ),
        "reconciliationDifferenceUsd": cost.get(
            "reconciliation_difference_usd"
        ),
        "billingDataMissing": bool(cost.get("billing_data_missing", True)),
        "billingDataInvalid": bool(cost.get("billing_data_invalid", False)),
        "estimateStatus": str(cost.get("estimate_status") or ""),
        "usageValidationStatus": str(
            cost.get("usage_validation_status") or ""
        ),
        "usageValidationReason": str(
            cost.get("usage_validation_reason") or ""
        ),
        "guardrailEnabled": bool(cost.get("guardrail_enabled")),
        "guardrailLimitUsd": cost.get("guardrail_limit_usd"),
        "guardrailStatus": str(cost.get("guardrail_status") or ""),
    }
    if str(paid_call_status or "").startswith("not_called"):
        output.update({
            "providerBillingStatus": "not_applicable",
            "reconciliationStatus": "not_called",
            "billingDataMissing": False,
        })
    return output


def _ja_salary_llm_text(data):
    out = []
    for block in (data or {}).get("content") or []:
        if isinstance(block, dict) and block.get("type") in ("text", "output_text"):
            out.append(str(block.get("text") or ""))
        elif isinstance(block, str):
            out.append(block)
    return "".join(out).strip()
