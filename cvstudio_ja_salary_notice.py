"""JobAdder salary-notice computation for CV Studio.

Behaviour-preserving extraction from the app shell: expected-vs-current salary
resolution from AI components, fixed-salary detail calculation, guaranteed-months
extraction, currency selection, notice availability, and the SPA salary-update
payload/helper. Pure functions of their inputs -- no Flask, no globals, no
network. This module never imports ``app``.
"""

import calendar
import json
import re
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from cvstudio_ja_typos import _ja_correct_notice_typos
from cvstudio_salary_parse import (
    _JA_CURRENCY_OPTIONS,
    _JA_SALARY_EXCLUDED_COMPONENT_RE,
    _ja_round_currency,
    _ja_salary_amount_tokens,
    _ja_salary_component_is_excluded,
    _ja_salary_component_parts,
    _ja_salary_currency_candidates_from_field,
    _ja_salary_display,
    _ja_salary_parse_percent_increment,
    _ja_salary_parse_range,
)


def _ja_spa_salary_update_helper_js(salary_canonical):
    """Apply backend-calculated canonical salary values in the emergency helper.

    No salary text is reparsed in the JobAdder browser. The same canonical object
    that the backend calculated is embedded and applied directly.
    """
    canonical_json = json.dumps(salary_canonical or {}, ensure_ascii=False, separators=(",", ":"))
    return r"""
  const CV_CANONICAL_SALARY = %s;
  function cvSalaryFormatMoney(n) {
    if (n === null || n === undefined || !Number.isFinite(Number(n))) return '';
    return String(Math.round(Number(n))).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  }
  const CV_SALARY_PERMANENT_WORKTYPE = { workTypeID: 6727, name: 'Permanent', salaryType: 'NotSpecified', placementType: null };
  function cvSalaryRangeText(min, max) {
    if (min === null || min === undefined) return null;
    if (max === null || max === undefined || Number(max) === Number(min)) return cvSalaryFormatMoney(min);
    return `${cvSalaryFormatMoney(min)} - ${cvSalaryFormatMoney(max)}`;
  }
  function cvSetSalaryBlock(existingBlock, min, max) {
    const block = Object.assign({}, existingBlock || {});
    const oldSalary = Object.assign({}, block.salary || {});
    block.workType = Object.assign({}, CV_SALARY_PERMANENT_WORKTYPE);
    oldSalary.type = 'PerMonth';
    if (min !== null && min !== undefined && Number.isFinite(Number(min))) {
      oldSalary.salaryMin = Number(min);
      oldSalary.salaryMax = Number(max ?? min);
      oldSalary.salaryRange = cvSalaryRangeText(min, max ?? min);
    }
    if (!('unitPerUnit' in oldSalary)) oldSalary.unitPerUnit = null;
    block.salary = oldSalary;
    return block;
  }
  function cvCandidatePayloadClone(existing) {
    const payload = Object.assign({}, existing || {});
    ['candidateID','name','status','resume','formattedResume','coverLetter','otherSalaries','recruiters','seeking','rank','dateResumeUpdated','dateUpdatedUtc','lastContactedAt','lastPlaced','careerUpdateProfileLastUpdatedAt','rsmInTimeEmbeddedUrl','attachmentTypeNames','internalRating','remoteLookedUp','talentPoolIDs'].forEach(k => delete payload[k]);
    return payload;
  }
  async function cvFetchJson(url) {
    const r = await fetch(url, { credentials: 'same-origin', headers: {'Accept':'application/json, text/plain, */*', 'x-jobadder-spa':'1'} });
    const text = await readText(r);
    let data = null;
    try { data = JSON.parse(text || '{}'); } catch(e) {}
    return { ok: r.ok, status: r.status, data, text };
  }
  async function cvPutJson(url, body) {
    const r = await fetch(url, {
      method: 'PUT', credentials: 'same-origin',
      headers: {'Accept':'application/json, text/plain, */*', 'Content-Type':'application/json', 'x-jobadder-spa':'1', 'x-correlation-id': Math.random().toString(36).slice(2, 14)},
      body: JSON.stringify(body)
    });
    return { ok: r.ok, status: r.status, text: await readText(r) };
  }
  async function cvStudioOneNoteSalaryUpdate() {
    const canonical = CV_CANONICAL_SALARY || {};
    const results = { canonicalSalary: canonical };
    const candidateUrl = location.origin + '/spa/api/candidates/' + encodeURIComponent(candidateId);
    const g = await cvFetchJson(candidateUrl);
    if (!g.ok || !g.data) return { ok:false, reason:`Could not read candidate salary API (HTTP ${g.status})`, canonicalSalary:canonical };
    const candidatePayload = cvCandidatePayloadClone(g.data);
    const current = canonical.current || {};
    const expected = canonical.expected || {};
    let currentMin = null;
    if (current.writeToProfile && Number.isFinite(Number(current.monthlyEquivalent))) {
      currentMin = Number(current.monthlyEquivalent);
      candidatePayload.currentSalary = cvSetSalaryBlock(g.data.currentSalary, currentMin, currentMin);
      results.currentSalary = { ok:true, value:currentMin, fingerprint:(canonical.validation||{}).salaryFingerprint };
    } else {
      candidatePayload.currentSalary = cvSetSalaryBlock(g.data.currentSalary, null, null);
      results.currentSalary = { ok:true, skipped:true, reason:'Canonical current salary did not request an overwrite' };
    }
    let idealMin = expected.minAmount, idealMax = expected.maxAmount;
    const existingCurrent = Number((((g.data.currentSalary||{}).salary||{}).salaryMin));
    if (!Number.isFinite(Number(idealMin)) && expected.type === 'same_as_current_unresolved' && Number.isFinite(existingCurrent)) {
      idealMin = existingCurrent; idealMax = existingCurrent;
    }
    if (!Number.isFinite(Number(idealMin)) && String(expected.type||'').startsWith('percent') && Number.isFinite(existingCurrent)) {
      const pmin = Number(expected.percentMin), pmax = Number(expected.percentMax);
      if (Number.isFinite(pmin) && Number.isFinite(pmax)) {
        idealMin = Math.round(existingCurrent * (1 + pmin / 100));
        idealMax = Math.round(existingCurrent * (1 + pmax / 100));
      }
    }
    if (Number.isFinite(Number(idealMin))) {
      candidatePayload.idealSalary = cvSetSalaryBlock(g.data.idealSalary, Number(idealMin), Number(idealMax ?? idealMin));
      results.expectedSalary = { ok:true, min:Number(idealMin), max:Number(idealMax ?? idealMin), basisCurrentAmount:expected.basisCurrentAmount ?? existingCurrent };
    } else {
      candidatePayload.idealSalary = cvSetSalaryBlock(g.data.idealSalary, null, null);
      results.expectedSalary = { ok:true, skipped:true, reason:'Canonical expected salary did not request an overwrite' };
    }
    const currencySelection = canonical.currencySelection || {};
    const currencyOption = String(currencySelection.jobAdderOption || '').trim();
    if (currencyOption) {
      const customFields = Object.assign({}, g.data.customFields || {});
      const existingCurrency = Object.assign({}, customFields[4] || customFields['4'] || { fieldID:4, valueList:[] });
      existingCurrency.fieldID = 4;
      existingCurrency.value = currencyOption;
      if (!Array.isArray(existingCurrency.valueList)) existingCurrency.valueList = [];
      customFields[4] = existingCurrency;
      candidatePayload.customFields = customFields;
      results.currencyField = { ok:true, fieldID:4, value:currencyOption, selectionRule:currencySelection.selectionRule || null };
    } else {
      results.currencyField = { ok:true, skipped:true, reason:'No supported canonical currency option' };
    }
    const notice = canonical.notice || {};
    if (notice.spaPayload) {
      candidatePayload.availability = { type:notice.spaPayload.type, date:notice.spaPayload.date };
      results.noticePeriod = { ok:true, matched:notice.display, payload:notice.spaPayload };
    } else {
      results.noticePeriod = { ok:true, skipped:true, reason:'No supported canonical SPA notice payload' };
    }
    const put = await cvPutJson(candidateUrl, candidatePayload);
    results.put = { ok:put.ok, status:put.status, text:String(put.text||'').slice(0,300) };
    results.ok = !!put.ok;
    if (!put.ok) results.reason = `Salary/notice PUT failed (HTTP ${put.status})`;
    return results;
  }
""" % canonical_json


_JA_CURRENCY_CUSTOM_FIELD_ID = 4


def _ja_candidate_existing_currency(candidate):
    employment = (candidate or {}).get("employment") if isinstance(candidate, dict) else {}
    if isinstance(employment, dict):
        # Expected/ideal currency is preferred when a saved profile already has
        # two different currencies, mirroring the OneNote expected-wins rule.
        for branch in ("ideal", "current"):
            item = employment.get(branch)
            salary = item.get("salary") if isinstance(item, dict) else None
            code = str((salary or {}).get("currency") or "").strip().upper() if isinstance(salary, dict) else ""
            if code in _JA_CURRENCY_OPTIONS:
                return code
    for item in (candidate or {}).get("custom") or []:
        if not isinstance(item, dict):
            continue
        try:
            field_id = int(item.get("fieldId") or 0)
        except Exception:
            continue
        if field_id != _JA_CURRENCY_CUSTOM_FIELD_ID:
            continue
        value = str(item.get("value") or "")
        for code, label in _JA_CURRENCY_OPTIONS.items():
            if value == label or re.search(r"\({}\)".format(re.escape(code)), value, re.I):
                return code
    return None


def _ja_currency_option_for_code(code):
    return _JA_CURRENCY_OPTIONS.get(str(code or "").strip().upper())


def _ja_currency_selection(current_raw, expected_raw, candidate=None, ai_components=None):
    """Resolve per-field currencies and the single JobAdder dropdown value.

    Deterministic explicit aliases outrank AI.  AI can assist only when a salary
    field contains multiple explicit supported currencies, or when no explicit
    alias is present.  Expected Salary still wins the one JobAdder dropdown.
    """
    ai_components = ai_components if isinstance(ai_components, dict) else {}
    ai_cur = str(ai_components.get("currentCurrency") or ((ai_components.get("current") or {}).get("currency") if isinstance(ai_components.get("current"), dict) else "") or "").upper()
    ai_exp = str(ai_components.get("expectedCurrency") or ((ai_components.get("expected") or {}).get("currency") if isinstance(ai_components.get("expected"), dict) else "") or "").upper()
    if ai_cur not in _JA_CURRENCY_OPTIONS:
        ai_cur = None
    if ai_exp not in _JA_CURRENCY_OPTIONS:
        ai_exp = None

    current_candidates = _ja_salary_currency_candidates_from_field(current_raw)
    expected_candidates = _ja_salary_currency_candidates_from_field(expected_raw)

    def resolve(candidates, ai_code, field_name):
        codes = [item["code"] for item in candidates]
        if len(codes) == 1:
            warning = None
            if ai_code and ai_code != codes[0]:
                warning = "AI currency {} conflicted with explicit {} alias {}; explicit alias was retained.".format(ai_code, field_name, codes[0])
            return codes[0], field_name + "_explicit_alias", warning
        if len(codes) > 1:
            if ai_code in codes:
                return ai_code, field_name + "_ai_disambiguated_explicit_aliases", None
            warning = "Multiple explicit currencies were found in {} ({}); earliest textual alias {} was used.".format(field_name.replace("_", " "), ", ".join(codes), codes[0])
            if ai_code:
                warning += " AI suggested {} but it was not one of the explicit aliases.".format(ai_code)
            return codes[0], field_name + "_ambiguous_earliest_alias", warning
        if ai_code:
            return ai_code, field_name + "_ai_only", None
        return None, field_name + "_none", None

    current_currency, current_source, current_warning = resolve(current_candidates, ai_cur, "current_salary")
    expected_currency, expected_source, expected_warning = resolve(expected_candidates, ai_exp, "expected_salary")
    existing_currency = _ja_candidate_existing_currency(candidate)
    selected = expected_currency or current_currency or existing_currency
    if expected_currency:
        rule = "expected_salary_currency_wins"
        source = expected_source
    elif current_currency:
        rule = "current_salary_currency_used"
        source = current_source
    elif existing_currency:
        rule = "existing_candidate_currency_preserved"
        source = "existing_candidate_profile"
    else:
        rule = "no_currency_detected"
        source = "none"
    warnings = [x for x in (current_warning, expected_warning) if x]
    return {
        "currentCurrency": current_currency,
        "expectedCurrency": expected_currency,
        "selectedCurrency": selected,
        "jobAdderOption": _ja_currency_option_for_code(selected),
        "selectionRule": rule,
        "selectionSource": source,
        "detectionScope": ["current_salary_breakdown", "expected_salary"],
        "ignoredScreeningFields": ["brief_overview", "reason_leaving", "looking_for", "leads", "remarks", "presentability_rating", "notice_period"],
        "localCurrentCurrency": current_candidates[0]["code"] if current_candidates else None,
        "localExpectedCurrency": expected_candidates[0]["code"] if expected_candidates else None,
        "localCurrentCandidates": current_candidates,
        "localExpectedCandidates": expected_candidates,
        "aiCurrentCurrency": ai_cur,
        "aiExpectedCurrency": ai_exp,
        "existingCurrency": existing_currency,
        "optionSource": "configured_supported_list" if selected else "none",
        "optionValidated": False,
        "warning": " ".join(warnings) if warnings else None,
    }


def _ja_salary_currency(raw_values, candidate=None):
    values = list(raw_values or [])
    current_raw = values[0] if values else ""
    expected_raw = values[1] if len(values) > 1 else ""
    return _ja_currency_selection(current_raw, expected_raw, candidate).get("selectedCurrency")


_JA_SALARY_ALLOWANCE_COMPONENT_RE = re.compile(
    r"(?:(?<![a-z])(?:allowance|allowence|alowance|sllowance)\b|\btransport\b|\bphone\b|\bmobile\b|"
    r"\bhousing\b|\bcar\b|\bmeal\b|\bcash\s+allowance\b)",
    re.I,
)


_JA_SALARY_FIXED_RECURRING_RE = re.compile(r"\b(?:fixed|monthly|per\s+month|recurring|regular)\b", re.I)


_JA_SALARY_BASE_HINT_RE = re.compile(r"\b(?:current|salary|base|basic|last\s+drawn|monthly\s+pay|package)\b", re.I)


def _ja_extract_guaranteed_salary_months(raw):
    """Return one canonical guaranteedSalaryMonths value.

    Total-package expressions (13, 13.5, 14, 14.5 months, x13, etc.)
    establish a total. AWS/13th month establishes 13. Explicit N-month
    contractual/guaranteed/fixed bonuses are additions to the total salary
    months. Performance/variable/discretionary bonuses are never additions.
    """
    raw_text = str(raw or "")
    parts = _ja_salary_component_parts(raw_text)
    total_candidates = []
    bonus_additions = []
    evidence = []

    total_patterns = [
        re.compile(r"\b((?:1[2-9]|2[0-4])(?:\.\d+)?)\s*(?:th|st|nd|rd)?\s*(?:mon+ths?|mnths?|mths?|mos?)\b", re.I),
        # Recruiter shorthand often appears as "13.5th bonus" or
        # "14th bonus". In salary breakdown context this describes the
        # guaranteed total salary-month package, not an additional 13.5/14
        # bonus months. Treat it as the same total as "13.5 months".
        re.compile(r"\b((?:1[2-9]|2[0-4])(?:\.\d+)?)\s*(?:th|st|nd|rd)\s*(?:month(?:ly)?|salary|pay|bonus)\b", re.I),
        re.compile(r"(?:x|×)\s*((?:1[2-9]|2[0-4])(?:\.\d+)?)\b", re.I),
    ]
    bonus_patterns = [
        re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:mon+ths?|mnths?|mths?)\s*(?:of\s+)?(?:contractual|guaranteed|fixed)\s*(?:cash\s+)?bonus\b", re.I),
        re.compile(r"\b(?:contractual|guaranteed|fixed)\s*(?:cash\s+)?bonus(?:\s+(?:of|equivalent\s+to))?\s*(\d+(?:\.\d+)?)\s*(?:mon+ths?|mnths?|mths?)\b", re.I),
    ]

    for part in parts or [raw_text]:
        for pattern in total_patterns:
            for m in pattern.finditer(part):
                value = float(m.group(1))
                if 12 <= value <= 36:
                    total_candidates.append(value)
                    evidence.append({"type": "total_salary_months", "months": value, "raw": m.group(0)})
        if re.search(r"\b(?:AWS|annual\s+wage\s+supplement)\b", part, re.I):
            total_candidates.append(13.0)
            evidence.append({"type": "aws", "months": 13.0, "raw": part})
        # 13th month is already caught by the total pattern. Keep this explicit
        # fallback for unusual wording such as "13th-month pay".
        if re.search(r"\b13th[-\s]+(?:mon+th|mnth|mth)(?:\s+pay|\s+salary|\s+bonus)?\b", part, re.I):
            total_candidates.append(13.0)
        for pattern in bonus_patterns:
            for m in pattern.finditer(part):
                value = float(m.group(1))
                if 0 < value < 12:
                    # "inclusive/included" usually describes a total package,
                    # so do not add the same bonus twice.
                    if re.search(r"\b(?:incl|including|included|inclusive|comprising)\b", part, re.I):
                        continue
                    bonus_additions.append(value)
                    evidence.append({"type": "guaranteed_bonus_months", "months": value, "raw": m.group(0)})

    # Overlapping shorthand patterns can both match the same phrase (for
    # example ``13th month``).  Keep one evidence item so records remain stable
    # and readable even though duplicate candidates would not change max().
    deduped_evidence = []
    seen_evidence = set()
    for item in evidence:
        key = (str(item.get("type") or ""), float(item.get("months") or 0), str(item.get("raw") or "").strip().lower())
        if key in seen_evidence:
            continue
        seen_evidence.add(key)
        deduped_evidence.append(item)
    evidence = deduped_evidence

    base_total = max(total_candidates) if total_candidates else 12.0
    total = base_total + sum(bonus_additions)
    if total < 12:
        total = 12.0
    if total > 36:
        total = 36.0
    return {
        "guaranteedSalaryMonths": float(total),
        "baseSalaryMonths": float(base_total),
        "additionalGuaranteedBonusMonths": float(sum(bonus_additions)),
        "evidence": evidence,
    }


def _ja_calc_fixed_salary_detailed(raw, currency=None):
    """Calculate one deterministic monthly-equivalent current salary object.

    The helper has a stable mapping contract: unparseable or incomplete input
    returns an empty dict rather than None, so future direct callers can safely
    inspect fields without a NoneType failure.
    """
    if not str(raw or "").strip():
        return {}
    parts = _ja_salary_component_parts(raw)
    if not parts:
        return {}

    token_parts = []
    for index, part in enumerate(parts):
        for token in _ja_salary_amount_tokens(part):
            token_parts.append((index, part, token))
    if not token_parts:
        return {}

    # Month markers, percentages, EPF and bonus counters must never become the
    # base salary. Token filtering removes those markers; eligibility then keeps
    # salary-sized values or a smaller amount explicitly labelled base/current.
    eligible = []
    for item in token_parts:
        _index, part, token = item
        base_hint = bool(_JA_SALARY_BASE_HINT_RE.search(part))
        allowance_only = bool(_JA_SALARY_ALLOWANCE_COMPONENT_RE.search(part)) and not re.search(r"\b(?:base|basic|current|last\s+drawn)\b", part, re.I)
        salary_sized = bool(token["isK"] or token["value"] >= 1000)
        if (salary_sized or (base_hint and not allowance_only)) and not (token["value"] < 1000 and _JA_SALARY_EXCLUDED_COMPONENT_RE.search(part)):
            eligible.append(item)
    if not eligible:
        return {}

    base_item = None
    for item in eligible:
        index, part, token = item
        if _JA_SALARY_BASE_HINT_RE.search(part) and not (
            _JA_SALARY_ALLOWANCE_COMPONENT_RE.search(part)
            and not re.search(r"\b(?:base|basic|current|salary|last\s+drawn)\b", part, re.I)
        ):
            base_item = item
            break
    if base_item is None:
        base_item = next((item for item in eligible if item[2]["isK"] or item[2]["value"] >= 1000), None)
    if base_item is None:
        base_item = eligible[0]

    base_index, base_part, base_token = base_item
    base = int(base_token["value"])
    allowances = 0
    included = []
    excluded = []

    month_info = _ja_extract_guaranteed_salary_months(raw)
    guaranteed_months = float(month_info["guaranteedSalaryMonths"])

    for index, part in enumerate(parts):
        tokens = _ja_salary_amount_tokens(part)
        is_excluded = _ja_salary_component_is_excluded(part)
        allowance_like = bool(_JA_SALARY_ALLOWANCE_COMPONENT_RE.search(part))
        fixed_recurring = bool(_JA_SALARY_FIXED_RECURRING_RE.search(part))
        base_hint = bool(_JA_SALARY_BASE_HINT_RE.search(part))
        if is_excluded:
            # If the same component combines a real base with an annual marker,
            # preserve the base but never add the marker's number as cash.
            non_base_tokens = [t for t in tokens if not (index == base_index and t["start"] == base_token["start"] and t["value"] == base)]
            if non_base_tokens or index != base_index:
                if part not in excluded:
                    excluded.append(part)
            continue
        for token in tokens:
            if index == base_index and token["start"] == base_token["start"] and token["value"] == base:
                continue
            stripped_cash = re.sub(
                r"(?i)(?:RM|MYR|SGD|USD|AUD|GBP|EUR|IDR|PHP|BND|KHR|LAK|MMK|THB|VND|CNY|HKD|INR|S\$|US\$|A\$|HK\$|BN\$)",
                "",
                part,
            ).strip()
            bare_additive_cash = bool(
                index != base_index
                and len(tokens) == 1
                and int(token["value"]) >= 50
                and re.fullmatch(r"\d+(?:\.\d+)?\s*[kK]?", stripped_cash)
            )
            include_as_allowance = allowance_like or (fixed_recurring and not base_hint) or bare_additive_cash
            if include_as_allowance:
                allowances += int(token["value"])
                included.append({
                    "raw": part,
                    "value": int(token["value"]),
                    "classification": "bare_additive_fixed_cash" if bare_additive_cash else "labelled_fixed_allowance",
                })
            elif token["value"] != base and part not in excluded:
                excluded.append(part)

    multiplier = guaranteed_months / 12.0
    adjusted_base = _ja_round_currency(Decimal(base) * Decimal(str(guaranteed_months)) / Decimal(12))
    value = _ja_round_currency(Decimal(base) * Decimal(str(guaranteed_months)) / Decimal(12) + Decimal(allowances))
    return {
        "value": value,
        "base": base,
        "baseMonthly": base,
        "guaranteedSalaryMonths": guaranteed_months,
        "baseSalaryMonths": month_info["baseSalaryMonths"],
        "additionalGuaranteedBonusMonths": month_info["additionalGuaranteedBonusMonths"],
        "monthEvidence": month_info["evidence"],
        "multiplier": multiplier,
        "adjustedBase": adjusted_base,
        "allowances": int(allowances),
        "fixedMonthlyAllowance": int(allowances),
        "otherFixedMonthlyCash": 0,
        "includedEmployerEpf": 0,
        "includedAllowances": included,
        "excluded": excluded,
        "monthlyEquivalent": value,
        "display": _ja_salary_display(currency, value, equivalent=True),
        "breakdown": str(raw or "").strip(),
        "monthlyRule": "canonical_guaranteed_months_plus_fixed_monthly_cash",
        "roundingRule": "ROUND_HALF_UP_TO_WHOLE_CURRENCY",
    }


def _ja_expected_means_same_as_current(raw):
    text = str(raw or "").lower().strip()
    patterns = [
        r"\bsame\s+as\s+current\b", r"\bsame\s+current\b", r"\bmaintain\s+(?:the\s+)?current\b",
        r"\bmatch\s+(?:the\s+)?current\b", r"\bno\s+(?:increment|increase|change)\b",
        r"\b(?:horizontal|lateral)\s+move\b", r"\bcurrent\s+(?:salary|package|compensation)\s+(?:is\s+)?(?:ok|okay|fine|acceptable)\b",
        r"\bopen\s+to\s+current\b", r"\bas\s+current\b",
    ]
    return any(re.search(pattern, text, re.I) for pattern in patterns)


def _ja_expected_is_open(raw):
    return bool(re.search(r"\b(?:open|negotiable|nego|discuss|tbd|n/?a|not\s+available|flexible)\b", str(raw or ""), re.I))


def _ja_build_expected_canonical(expected_raw, current_value, currency=None):
    raw = str(expected_raw or "").strip()
    out = {
        "raw": raw,
        "type": "blank" if not raw else "unparsed",
        "monthlyAmount": None,
        "minAmount": None,
        "maxAmount": None,
        "percent": None,
        "percentMin": None,
        "percentMax": None,
        "basisCurrentAmount": None,
        "display": "",
        "writeToProfile": False,
    }
    if not raw:
        return out

    # Priority 1-2: explicit fixed amount/range always wins over percentage.
    explicit = _ja_salary_parse_range(raw)
    if explicit:
        lo, hi = int(explicit["min"]), int(explicit.get("max", explicit["min"]))
        out.update({
            "type": "fixed" if lo == hi else "range",
            "monthlyAmount": lo if lo == hi else None,
            "minAmount": lo,
            "maxAmount": hi,
            "display": _ja_salary_display(currency, lo, hi),
            "writeToProfile": True,
        })
        return out

    # Priority 3: only explicit same-as-current intent, not any mention of current.
    if _ja_expected_means_same_as_current(raw):
        out["type"] = "same_as_current"
        if current_value is not None:
            value = int(current_value)
            out.update({
                "monthlyAmount": value, "minAmount": value, "maxAmount": value,
                "basisCurrentAmount": value, "display": _ja_salary_display(currency, value),
                "writeToProfile": True,
            })
        else:
            out["type"] = "same_as_current_unresolved"
        return out

    # Priority 4-5: percentage increment/range from the one canonical current.
    pct = _ja_salary_parse_percent_increment(raw)
    if pct:
        out.update({
            "type": "percent" if pct["min"] == pct["max"] else "percent_range",
            "percent": pct["min"] if pct["min"] == pct["max"] else None,
            "percentMin": pct["min"], "percentMax": pct["max"],
            "basisCurrentAmount": int(current_value) if current_value is not None else None,
        })
        if current_value is not None:
            lo = _ja_round_currency(Decimal(int(current_value)) * (Decimal(1) + Decimal(str(pct["min"])) / Decimal(100)))
            hi = _ja_round_currency(Decimal(int(current_value)) * (Decimal(1) + Decimal(str(pct["max"])) / Decimal(100)))
            out.update({
                "monthlyAmount": lo if lo == hi else None, "minAmount": lo, "maxAmount": hi,
                "display": _ja_salary_display(currency, lo, hi), "writeToProfile": True,
            })
        else:
            out["type"] += "_unresolved"
        return out

    # Priority 6: open/negotiable/N/A.
    if _ja_expected_is_open(raw):
        out["type"] = "open"
        out["display"] = raw
    return out


def _ja_expected_salary_range(expected_raw, current_value=None):
    """Compatibility wrapper backed by the canonical expected calculation."""
    item = _ja_build_expected_canonical(expected_raw, current_value)
    if item.get("writeToProfile") and item.get("minAmount") is not None:
        return {"min": int(item["minAmount"]), "max": int(item.get("maxAmount", item["minAmount"]))}
    return None


def _ja_existing_current_salary(candidate):
    try:
        salary = candidate.get("employment", {}).get("current", {}).get("salary", {})
        rate = salary.get("rate")
        return _ja_round_currency(rate) if rate is not None else None
    except Exception:
        return None


def _ja_valid_iso_date(year, month, day):
    try:
        return date(int(year), int(month), int(day)).isoformat()
    except Exception:
        return None


def _ja_notice_availability(raw, spelling_correction=True):
    original_raw_text = str(raw or "").strip()
    raw_text = _ja_correct_notice_typos(original_raw_text, enabled=bool(spelling_correction))
    if not raw_text:
        return None, {"ok": True, "skipped": True, "reason": "No notice period value"}

    raw_lower = raw_text.lower().strip()

    # Specific availability dates must be parsed before normalising hyphens,
    # otherwise an ISO date such as 2026-08-15 is destroyed into plain words.
    m = re.search(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b", raw_lower)
    if m:
        iso = _ja_valid_iso_date(m.group(1), m.group(2), m.group(3))
        if iso:
            return {"date": iso}, {"ok": True, "raw": raw_text, "matched": iso, "payload": {"date": iso}}
        return None, {"ok": False, "raw": raw_text, "reason": "Invalid calendar date"}
    m = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b", raw_lower)
    if m:
        iso = _ja_valid_iso_date(m.group(3), m.group(2), m.group(1))
        if iso:
            return {"date": iso}, {"ok": True, "raw": raw_text, "matched": iso, "payload": {"date": iso}}
        return None, {"ok": False, "raw": raw_text, "reason": "Invalid calendar date"}

    month_map = {
        "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
        "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
        "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
        "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
    }
    date_match = re.search(
        r"\b(\d{1,2})\s+(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)(?:\s*,?\s*(20\d{2}))?\b",
        raw_lower,
        re.I,
    )
    if not date_match:
        date_match = re.search(
            r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(\d{1,2})(?:\s*,?\s*(20\d{2}))?\b",
            raw_lower,
            re.I,
        )
        if date_match:
            month_name, day_text, year_text = date_match.group(1), date_match.group(2), date_match.group(3)
        else:
            month_name = day_text = year_text = None
    else:
        day_text, month_name, year_text = date_match.group(1), date_match.group(2), date_match.group(3)
    if date_match and month_name and day_text:
        month_key = month_name.lower()
        month = month_map.get(month_key) or month_map.get(month_key[:3])
        day = int(day_text)
        today = date.today()
        year = int(year_text) if year_text else today.year
        try:
            candidate_date = date(year, month, day)
            if not year_text and candidate_date < today:
                candidate_date = date(year + 1, month, day)
            iso = candidate_date.isoformat()
            return {"date": iso}, {"ok": True, "raw": raw_text, "matched": iso, "payload": {"date": iso}}
        except Exception:
            pass

    lower = raw_lower.replace("–", " ").replace("—", " ").replace("-", " ")
    word_map = {"one":"1", "a":"1", "an":"1", "two":"2", "three":"3", "four":"4", "five":"5", "six":"6"}
    for word, number in word_map.items():
        lower = re.sub(r"\b" + re.escape(word) + r"\b", number, lower)
    # Standard recruiter abbreviations remain supported even when optional
    # typo correction is off. Obvious misspellings are corrected only when the
    # OneNote setting is enabled.
    lower = re.sub(r"(?<![a-z])(?:mnth|mnths|mth|mths|mthhs|mos|mo)(?![a-z])", "month", lower)
    lower = re.sub(r"(?<![a-z])(?:wk|wks)(?![a-z])", "week", lower)
    lower = re.sub(r"\s+", " ", lower).strip()
    if "immediate" in lower or "immediately" in lower or "available now" in lower or lower in ("0", "none"):
        return {"immediate": True}, {"ok": True, "raw": raw_text, "matched": "Immediate", "payload": {"immediate": True}}
    # Parse the complete numeric token, including decimals. The prior integer-only
    # search could start after the decimal point, so "1.5 months" became
    # "5 Months". Decimal handling is now explicit and never partial:
    #   1.5 months -> 1 Month; 2.5 -> 2 Months; 3.5 -> 3 Months;
    #   0.5 month  -> 2 Weeks.
    m = re.search(r"(?<![\d.])(\d+(?:\.\d+)?)\s*(day|days|week|weeks|month|months)\b", lower)
    if m:
        amount = Decimal(m.group(1))
        raw_unit = m.group(2).lower()
        normalization = None
        if amount <= 0:
            payload = {"immediate": True}
            return payload, {"ok": True, "raw": raw_text, "matched": "Immediate", "payload": payload}

        if raw_unit.startswith("month"):
            whole_months = int(amount)
            if whole_months >= 1:
                period, unit = whole_months, "Month"
                if amount != Decimal(whole_months):
                    normalization = {
                        "rule": "truncate_fractional_month_to_whole_month",
                        "input": str(amount),
                        "output": "%s Month%s" % (period, "s" if period != 1 else ""),
                    }
            else:
                # JobAdder availability accepts whole relative units. For a
                # sub-one-month value, convert the fraction to four-week months.
                # This preserves the user's required 0.5 month -> 2 weeks rule.
                period = max(1, int((amount * Decimal(4)).to_integral_value(rounding=ROUND_HALF_UP)))
                unit = "Week"
                normalization = {
                    "rule": "fractional_month_below_one_to_weeks",
                    "input": str(amount),
                    "output": "%s Week%s" % (period, "s" if period != 1 else ""),
                }
        elif raw_unit.startswith("week"):
            period = int(amount)
            if period <= 0:
                period = 1
            unit = "Week"
            if amount != Decimal(int(amount)):
                normalization = {
                    "rule": "truncate_fractional_week_to_whole_week",
                    "input": str(amount),
                    "output": "%s Week%s" % (period, "s" if period != 1 else ""),
                }
            if period > 4:
                original_period = period
                period, unit = (period + 3) // 4, "Month"
                normalization = normalization or {
                    "rule": "weeks_over_four_to_months",
                    "input": "%s weeks" % original_period,
                    "output": "%s Month%s" % (period, "s" if period != 1 else ""),
                }
        else:
            days = int(amount)
            if days <= 0:
                days = 1
            if amount != Decimal(int(amount)):
                normalization = {
                    "rule": "truncate_fractional_day_to_whole_day",
                    "input": str(amount),
                    "output": "%s day%s" % (days, "s" if days != 1 else ""),
                }
            if days <= 21:
                period, unit = max(1, (days + 6) // 7), "Week"
            else:
                period, unit = max(1, (days + 29) // 30), "Month"

        payload = {"relative": {"period": period, "unit": unit}}
        meta = {"ok": True, "raw": raw_text, "matched": "%s %s%s" % (period, unit, "s" if period != 1 else ""), "payload": payload}
        if normalization:
            meta["normalization"] = normalization
        return payload, meta
    return None, {"ok": False, "raw": raw_text, "reason": "Could not match notice period"}


def _ja_add_months_iso(start_date, months):
    months = int(months)
    month_index = start_date.month - 1 + months
    year = start_date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day).isoformat()


def _ja_notice_spa_payload(availability):
    if not isinstance(availability, dict):
        return None
    if availability.get("immediate"):
        return {"type": "Immediate", "date": None}
    if availability.get("date"):
        # Preserve the date in the canonical object. The normal OAuth update uses
        # the official {date} model. The emergency SPA route may vary by tenant,
        # so no guessed type is sent for date-only availability.
        return None
    rel = availability.get("relative")
    if isinstance(rel, dict):
        period = int(rel.get("period") or 0)
        unit = str(rel.get("unit") or "")
        if period > 0 and unit == "Week":
            return {"type": "In{}Week{}".format(period, "" if period == 1 else "s"), "date": (date.today() + timedelta(days=period * 7)).isoformat()}
        if period > 0 and unit == "Month":
            return {"type": "In{}Month{}".format(period, "" if period == 1 else "s"), "date": _ja_add_months_iso(date.today(), period)}
    return None


def _ja_ai_number_matches_token(value, tokens, tolerance=1):
    if value is None:
        return False
    return any(abs(float(token.get("value") or 0) - float(value)) <= tolerance for token in tokens)


def _ja_validate_ai_current_components(ai_components, current_raw):
    cur = (ai_components or {}).get("current") if isinstance((ai_components or {}).get("current"), dict) else {}
    if not cur or cur.get("baseMonthly") is None:
        return False, "AI did not provide a usable current base salary."
    base = float(cur.get("baseMonthly"))
    months = float(cur.get("guaranteedSalaryMonths") or 12)
    additions = sum(float(cur.get(key) or 0) for key in ("fixedMonthlyAllowance", "otherFixedMonthlyCash", "includedEmployerEpf"))
    tokens = _ja_salary_amount_tokens(current_raw)
    confidence = str(cur.get("confidence") or "").lower()
    if tokens and not _ja_ai_number_matches_token(base, tokens):
        return False, "AI base salary conflicted with explicit numeric salary evidence."
    if not tokens and confidence not in ("high", "medium"):
        return False, "AI current salary had no explicit numeric evidence and insufficient confidence."
    month_info = _ja_extract_guaranteed_salary_months(current_raw)
    if month_info.get("evidence"):
        if abs(float(month_info.get("guaranteedSalaryMonths") or 12) - months) > 0.001:
            return False, "AI guaranteed salary months conflicted with explicit month/AWS evidence."
    elif abs(months - 12.0) > 0.001:
        return False, "AI introduced guaranteed salary months without evidence in Current Salary Breakdown."
    if additions < 0 or additions > max(base * 5, 10000000):
        return False, "AI fixed cash additions were outside conservative salary bounds."
    if tokens:
        remaining = list(tokens)
        for i, token in enumerate(remaining):
            if abs(float(token.get("value") or 0) - base) <= 1:
                remaining.pop(i)
                break
        explicit_addition_ceiling = sum(float(token.get("value") or 0) for token in remaining)
        if additions > explicit_addition_ceiling + 1:
            return False, "AI fixed cash additions exceeded explicit salary amounts in the field."
    return True, None


def _ja_validate_ai_expected_components(ai_components, expected_raw, local_expected):
    exp = (ai_components or {}).get("expected") if isinstance((ai_components or {}).get("expected"), dict) else {}
    if not exp:
        return False, "AI did not provide usable expected salary components."
    # Explicit deterministic parsing always wins where it can identify amount,
    # range, same-as-current, percentage or open/negotiable intent.
    if (local_expected or {}).get("type") not in (None, "blank", "unparsed"):
        return False, "Deterministic Expected Salary evidence was authoritative."
    tokens = _ja_salary_amount_tokens(expected_raw)
    amounts = [exp.get("explicitAmount"), exp.get("explicitMin"), exp.get("explicitMax")]
    for amount in [x for x in amounts if x is not None]:
        if tokens and not _ja_ai_number_matches_token(amount, tokens):
            return False, "AI expected amount conflicted with explicit numeric salary evidence."
    confidence = str(exp.get("confidence") or "").lower()
    has_value = any(x is not None for x in amounts + [exp.get("percent"), exp.get("percentMin"), exp.get("percentMax")]) or exp.get("sameAsCurrent") or exp.get("open")
    if not has_value:
        return False, "AI did not identify an expected salary intent."
    if not tokens and confidence not in ("high", "medium") and not exp.get("sameAsCurrent") and not exp.get("open"):
        return False, "AI expected salary had no explicit numeric evidence and insufficient confidence."
    return True, None


def _ja_current_from_ai_components(ai_components, raw, currency):
    cur = (ai_components or {}).get("current") if isinstance((ai_components or {}).get("current"), dict) else {}
    base = cur.get("baseMonthly")
    if base is None:
        return None
    months = cur.get("guaranteedSalaryMonths") or 12
    allowance = int(cur.get("fixedMonthlyAllowance") or 0)
    other = int(cur.get("otherFixedMonthlyCash") or 0)
    epf = int(cur.get("includedEmployerEpf") or 0)
    adjusted = _ja_round_currency(Decimal(str(base)) * Decimal(str(months)) / Decimal(12))
    value = _ja_round_currency(Decimal(str(base)) * Decimal(str(months)) / Decimal(12) + Decimal(allowance + other + epf))
    return {
        "value": value,
        "base": int(base),
        "baseMonthly": int(base),
        "guaranteedSalaryMonths": float(months),
        "baseSalaryMonths": float(months),
        "additionalGuaranteedBonusMonths": max(0.0, float(months)-12.0),
        "monthEvidence": list(cur.get("evidence") or []),
        "multiplier": float(months)/12.0,
        "adjustedBase": adjusted,
        "allowances": allowance + other + epf,
        "fixedMonthlyAllowance": allowance,
        "otherFixedMonthlyCash": other,
        "includedEmployerEpf": epf,
        "includedAllowances": list(cur.get("evidence") or []),
        "excluded": list(cur.get("excludedComponents") or []),
        "monthlyEquivalent": value,
        "display": _ja_salary_display(currency, value, equivalent=True),
        "breakdown": str(raw or "").strip(),
        "monthlyRule": "ai_components_then_deterministic_guaranteed_months_plus_fixed_cash",
        "roundingRule": "ROUND_HALF_UP_TO_WHOLE_CURRENCY",
        "componentSource": "ai_component_extraction",
        "extractionConfidence": cur.get("confidence") or "",
    }


def _ja_expected_from_ai_components(ai_components, raw, current_value, currency):
    exp = (ai_components or {}).get("expected") if isinstance((ai_components or {}).get("expected"), dict) else {}
    if not exp or not str(raw or "").strip():
        return None
    out = {"raw":str(raw or "").strip(),"type":"unparsed","monthlyAmount":None,"minAmount":None,"maxAmount":None,"percent":None,"percentMin":None,"percentMax":None,"basisCurrentAmount":None,"display":"","writeToProfile":False,"componentSource":"ai_component_extraction"}
    amount=exp.get("explicitAmount"); lo=exp.get("explicitMin"); hi=exp.get("explicitMax")
    if amount is not None:
        value=_ja_round_currency(amount); out.update({"type":"fixed","monthlyAmount":value,"minAmount":value,"maxAmount":value,"display":_ja_salary_display(currency,value),"writeToProfile":True}); return out
    if lo is not None or hi is not None:
        lo=_ja_round_currency(lo if lo is not None else hi); hi=_ja_round_currency(hi if hi is not None else lo); lo,hi=min(lo,hi),max(lo,hi); out.update({"type":"range" if lo!=hi else "fixed","monthlyAmount":lo if lo==hi else None,"minAmount":lo,"maxAmount":hi,"display":_ja_salary_display(currency,lo,hi),"writeToProfile":True}); return out
    if exp.get("sameAsCurrent"):
        out["type"]="same_as_current" if current_value is not None else "same_as_current_unresolved"
        if current_value is not None:
            value=int(current_value); out.update({"monthlyAmount":value,"minAmount":value,"maxAmount":value,"basisCurrentAmount":value,"display":_ja_salary_display(currency,value),"writeToProfile":True})
        return out
    pmin=exp.get("percentMin"); pmax=exp.get("percentMax"); p=exp.get("percent")
    if p is not None: pmin=pmax=p
    if pmin is not None or pmax is not None:
        pmin=float(pmin if pmin is not None else pmax); pmax=float(pmax if pmax is not None else pmin); pmin,pmax=min(pmin,pmax),max(pmin,pmax)
        out.update({"type":"percent" if pmin==pmax else "percent_range","percent":pmin if pmin==pmax else None,"percentMin":pmin,"percentMax":pmax,"basisCurrentAmount":int(current_value) if current_value is not None else None})
        if current_value is not None:
            lo=_ja_round_currency(Decimal(int(current_value))*(Decimal(1)+Decimal(str(pmin))/Decimal(100))); hi=_ja_round_currency(Decimal(int(current_value))*(Decimal(1)+Decimal(str(pmax))/Decimal(100))); out.update({"monthlyAmount":lo if lo==hi else None,"minAmount":lo,"maxAmount":hi,"display":_ja_salary_display(currency,lo,hi),"writeToProfile":True})
        else: out["type"] += "_unresolved"
        return out
    if exp.get("open"):
        out.update({"type":"open","display":str(raw or "").strip()}); return out
    return None
