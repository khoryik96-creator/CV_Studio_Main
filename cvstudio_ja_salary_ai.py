"""JobAdder salary-AI storage service for CV Studio.

Behaviour-preserving extraction of the salary-AI component cache from the app
shell. The SQLite repository and legacy-JSON cache path are injected as
zero-argument callables (not bound objects) so the service always reads the
current app-level globals at call time -- the Phase 2A storage-corruption route
tests rebind ``_CVSTUDIO_SALARY_REPOSITORY`` / ``_SALARY_AI_CACHE_PATH`` and the
code must observe the rebind. This module never imports ``app``.
"""

from datetime import datetime


class SalaryAiCacheService:
    """Row-level SQLite cache for AI-extracted salary components.

    Mirrors the established cache-service shape (see ``LeadCacheService``):
    dependencies come in through the constructor, storage handles are resolved
    late through callables, and the legacy JSON mirror is kept consistent while
    SQLite stays authoritative.
    """

    def __init__(
        self,
        *,
        repository,
        cache_path,
        lock,
        legacy_json_read,
        legacy_json_write,
        storage_error,
    ):
        # ``repository``/``cache_path`` are zero-arg callables returning the
        # current app globals; ``lock`` is the shared threading lock object.
        self._repository = repository
        self._cache_path = cache_path
        self._lock = lock
        self._legacy_json_read = legacy_json_read
        self._legacy_json_write = legacy_json_write
        self._storage_error = storage_error

    def load(self):
        legacy, fingerprint = self._legacy_json_read(self._cache_path(), dict)
        try:
            if legacy is not None:
                self._repository().import_legacy(legacy, fingerprint)
            return self._repository().load()
        except self._storage_error:
            raise
        except Exception:
            return legacy if isinstance(legacy, dict) else {}

    def import_legacy_locked(self):
        """Import any legacy JSON once (fingerprint-guarded in the repository)."""
        legacy, fingerprint = self._legacy_json_read(self._cache_path(), dict)
        if legacy is not None:
            self._repository().import_legacy(legacy, fingerprint)
        return legacy

    def get(self, cache_key):
        key = str(cache_key or "")
        with self._lock:
            try:
                self.import_legacy_locked()
                item = self._repository().get(key)  # single-row read, no whole-map load
            except self._storage_error:
                raise
            except Exception:
                item = None
        return item if isinstance(item, dict) else None

    def put(self, cache_key, components, provider, model):
        if not cache_key or not isinstance(components, dict):
            return
        entry = {
            "components": components,
            "provider": provider,
            "model": model,
            "savedAt": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        }
        with self._lock:
            try:
                self.import_legacy_locked()
                # Row-level upsert + newest-500 trim in one transaction, instead
                # of loading, mutating and rewriting the entire map.
                self._repository().put(str(cache_key), entry, cap=500)
            except self._storage_error:
                raise
            except Exception:
                return
            try:
                # Keep the legacy JSON mirror consistent with SQLite
                # (compatibility contract). SQLite is authoritative if the mirror
                # cannot be updated.
                self._legacy_json_write(self._cache_path(), self._repository().load(), indent=2)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Salary-AI extraction + JobAdder salary/notice submission (Phase 7B slice).
#
# These build on the cache service above plus the already-extracted salary
# parse/notice helpers. Shell dependencies that must stay in app.py (the paid
# LLM entry point, the OneNote field cleaner, LLM cost/failure helpers, the
# JobAdder HTTP wrappers and the salary cache delegators) are injected as
# late-binding callables via bind_salary_ai_dependencies() so test patches on
# app.* are observed at call time. This module never imports ``app``.
# ---------------------------------------------------------------------------

import hashlib
import json
import re
import urllib.error
import urllib.parse

from cvstudio_ja_typos import _ja_salary_normalize_recruiter_typos
from cvstudio_lead_enrich import _lead_extract_json
from cvstudio_salary_parse import (
    _ja_salary_ai_sanitize,
    _ja_salary_cost_provenance,
    _ja_salary_display,
    _ja_salary_has_actual_amount,
    _ja_salary_llm_text,
    _ja_salary_plain_number,
)
from cvstudio_ja_salary_notice import (
    _JA_CURRENCY_CUSTOM_FIELD_ID,
    _ja_build_expected_canonical,
    _ja_calc_fixed_salary_detailed,
    _ja_currency_option_for_code,
    _ja_currency_selection,
    _ja_current_from_ai_components,
    _ja_existing_current_salary,
    _ja_expected_from_ai_components,
    _ja_notice_availability,
    _ja_notice_spa_payload,
    _ja_validate_ai_current_components,
    _ja_validate_ai_expected_components,
)

# Injected app-shell dependencies (populated by bind_salary_ai_dependencies).
call_llm = None
_onenote_clean_field_value = None
_llm_cost_details = None
_llm_paid_failure_fields = None
safe_json = None
_ja_get_json = None
_ja_put_json = None
_ja_salary_ai_cache_get = None
_ja_salary_ai_cache_put = None


def bind_salary_ai_dependencies(**deps):
    """Bind the late-binding app-shell callables this module invokes."""
    globals().update(deps)


def _ja_compact_error_body(body, max_len=1200):
    raw = str(body or "").strip()
    if not raw:
        return ""
    try:
        parsed = safe_json(raw, {})
        if isinstance(parsed, dict):
            for k in ("message", "error_description", "error", "detail", "title"):
                if parsed.get(k):
                    return str(parsed.get(k))[:max_len]
            return json.dumps(parsed, ensure_ascii=False)[:max_len]
    except Exception:
        pass
    return raw[:max_len]


_ONENOTE_JA_PERMANENT_WORKTYPE_ID = 6727


def _ja_validate_currency_option_with_api(selection):
    """Validate custom field 4 against the tenant's official field definition.

    If the read fails, use the exact supported option list supplied for this
    tenant. If the field definition is read successfully but the option is not
    present, skip the custom-field write rather than submitting an invalid value.
    """
    selection = dict(selection or {})
    code = str(selection.get("selectedCurrency") or "").upper()
    default = _ja_currency_option_for_code(code)
    if not code or not default:
        return selection
    try:
        status, data = _ja_get_json("candidates/fields/custom/{}".format(_JA_CURRENCY_CUSTOM_FIELD_ID), timeout=15)
        values = data.get("values") if isinstance(data, dict) else None
        values = [str(x) for x in (values or []) if str(x).strip()]
        if values:
            exact = default if default in values else next((x for x in values if re.search(r"\({}\)".format(re.escape(code)), x, re.I)), None)
            if exact:
                selection.update({"jobAdderOption": exact, "optionSource": "official_candidate_custom_field_definition", "optionValidated": True, "definitionStatus": status})
            else:
                selection.update({"jobAdderOption": None, "optionSource": "official_candidate_custom_field_definition", "optionValidated": False, "definitionStatus": status, "warning": "Detected {} but JobAdder Currency field 4 did not advertise a matching option.".format(code)})
        else:
            selection.update({"jobAdderOption": default, "optionSource": "configured_supported_list_empty_api_values", "optionValidated": False, "definitionStatus": status})
    except Exception as e:
        selection.update({"jobAdderOption": default, "optionSource": "configured_supported_list_api_read_failed", "optionValidated": False, "definitionError": str(e)[:300]})
    return selection


def _ja_salary_cost_details(model, usage, provider):
    return _llm_cost_details(model, usage, provider)


def _ja_salary_ai_extract(fields, config=None):
    config = config if isinstance(config, dict) else {}
    enabled = bool(config.get("enabled"))
    provider = str(config.get("provider") or "deepseek").strip().lower()
    if provider == "claude": provider = "anthropic"
    if provider == "gpt": provider = "openai"
    model = str(config.get("model") or ("deepseek-v4-flash" if provider == "deepseek" else "")).strip()
    api_key = str(config.get("api_key") or "").strip()
    # Privacy/scope boundary: only the two salary fields are sent. Summary,
    # RFL, Looking For, Remarks, Leads, Presentability, notice and full note text
    # are never included in this AI request.
    raw = {
        "currentSalaryBreakdown": _onenote_clean_field_value((fields or {}).get("current_salary_breakdown", "")),
        "expectedSalary": _onenote_clean_field_value((fields or {}).get("expected_salary", "")),
    }
    base_processing = {
        "fieldExtraction": "local_label_parser",
        "salaryCalculation": "deterministic_code",
        "aiAttempted": False,
        "aiUsed": False,
        "aiApiCalled": False,
        "cacheHit": False,
        "provider": "none",
        "model": "none",
        "inputTokens": 0,
        "outputTokens": 0,
        "costUsd": 0.0,
        "costReason": "Local deterministic salary parser used; no AI API call.",
    }
    base_processing.update(
        _ja_salary_cost_provenance(
            _ja_salary_cost_details("none", {}, "none"),
            "not_called",
        )
    )
    if not enabled or not any(raw.values()):
        return None, base_processing
    cache_key = hashlib.sha256(json.dumps({"v":"salary-ai-v4-typo-tolerant","provider":provider,"model":model,"raw":raw}, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    cached = _ja_salary_ai_cache_get(cache_key)
    cached_components = _ja_salary_ai_sanitize(cached.get("components")) if isinstance(cached, dict) else None
    if cached_components:
        cached_processing = {
            "fieldExtraction": "ai_component_extraction_cache",
            "salaryCalculation": "deterministic_code",
            "aiAttempted": True,
            "aiUsed": True,
            "aiApiCalled": False,
            "cacheHit": True,
            "cacheKey": cache_key[:20],
            "provider": str(cached.get("provider") or provider),
            "model": str(cached.get("model") or model),
            "inputTokens": 0,
            "outputTokens": 0,
            "costUsd": 0.0,
            "costReason": "Reused cached AI-extracted components; no new token charge. Deterministic code calculated final values.",
        }
        cached_processing.update(
            _ja_salary_cost_provenance(
                _ja_salary_cost_details(
                    str(cached.get("model") or model),
                    {},
                    str(cached.get("provider") or provider),
                ),
                "not_called_cache_hit",
            )
        )
        return cached_components, cached_processing
    if not api_key:
        p=dict(base_processing)
        p.update({"aiAttempted": False, "fallbackReason": "AI salary assist enabled but no saved API key was available.", "costReason": "No AI call; local deterministic fallback."})
        return None, p
    system = """You extract salary and currency components from exactly two recruiter fields: currentSalaryBreakdown and expectedSalary. Return JSON only. Never calculate final current salary, expected salary, or JobAdder values. Never infer an unstated amount or currency. Detect current.currency only from currentSalaryBreakdown. Detect expected.currency only from expectedSalary. Do not copy current currency into expected when expected does not state one. No Summary, RFL, Looking For, Remarks, Leads, Presentability, notice text or full screening note is provided; never infer from those sections. Normalize currency aliases to one of these exact ISO codes only: BND, KHR, IDR, LAK, MYR, MMK, PHP, SGD, THB, VND, CNY, HKD, AUD, EUR, USD, INR. Examples: RM/MYR/ringgit=MYR; Rp/rupiah=IDR; S$/SGD=SGD; US$/USD=USD; Rs/₹/rupee=INR; RMB/yuan/renminbi=CNY; HK$/HKD=HKD; A$/AUD=AUD; euro/€=EUR; peso/₱=PHP; baht/฿=THB; dong/đồng/₫=VND. AWS means a 13-month total package. Wording such as 13.5th bonus, 13.5 months, or x13.5 means total guaranteedSalaryMonths=13.5, not an additional 13.5 months. A phrase such as 2 months contractual/guaranteed/fixed bonus means total 14 months unless the text already states a higher total package. A plain 2 months bonus without contractual/guaranteed/fixed wording is variable and excluded. EPF/KWSP, SOCSO, EIS and employer contributions are always excluded from the JobAdder monthly current salary. Commission, variable/performance/discretionary bonus, claims, reimbursements and stock are excluded. Only a separately stated fixed recurring cash allowance may be included. Recruiter spelling is noisy: interpret obvious salary-field typos such as allwan/alwan/alwance/alowance as allowance; mth/mths/mnth/moth/monnth as month/months; bonous/bouns as bonus; efp as EPF; precent/persent as percent; and rngint/rnggit/ringit as Malaysian Ringgit (MYR). Currency may appear before or after the amount with no space, for example RM2000, 2000RM, MYR10k, 10kMYR, or 2000rngint. A separate additive amount such as +500 may be fixed monthly cash. Fixed expected amount/range has priority over percentage. Output this exact object shape with nulls when unknown: {"current":{"currency":null,"baseMonthly":null,"guaranteedSalaryMonths":null,"fixedMonthlyAllowance":0,"otherFixedMonthlyCash":0,"includedEmployerEpf":0,"excludedComponents":[],"evidence":[],"confidence":"high|medium|low"},"expected":{"currency":null,"explicitAmount":null,"explicitMin":null,"explicitMax":null,"sameAsCurrent":false,"percent":null,"percentMin":null,"percentMax":null,"open":false,"confidence":"high|medium|low"}}"""
    payload = {
        "model": model,
        "max_tokens": 900,
        "temperature": 0,
        "system": system,
        "messages": [{"role":"user","content":json.dumps(raw, ensure_ascii=False)}],
        "_timeout_seconds": 90,
    }
    usage = {}
    api_called = False
    try:
        data = call_llm(provider, api_key, payload)
        api_called = True
        usage = (data or {}).get("usage") or {}
        obj = _lead_extract_json(_ja_salary_llm_text(data))
        components = _ja_salary_ai_sanitize(obj)
        if not components:
            raise ValueError("AI response did not contain usable salary components")
        cost = _ja_salary_cost_details(model, usage, provider)
        _ja_salary_ai_cache_put(cache_key, components, provider, model)
        processing = {
            "fieldExtraction": "ai_component_extraction",
            "salaryCalculation": "deterministic_code",
            "aiAttempted": True,
            "aiUsed": True,
            "aiApiCalled": True,
            "cacheHit": False,
            "cacheKey": cache_key[:20],
            "provider": provider,
            "model": model,
            "inputTokens": int(cost.get("input_tokens") or 0),
            "outputTokens": int(cost.get("output_tokens") or 0),
            "totalTokens": int(cost.get("total_tokens") or 0),
            "apiCalls": int(cost.get("api_calls") or 0),
            "promptCacheHitTokens": int(cost.get("prompt_cache_hit_tokens") or 0),
            "promptCacheMissTokens": int(cost.get("prompt_cache_miss_tokens") or 0),
            "costUsd": float(cost.get("usd") or 0.0),
            "pricingKnown": bool(cost.get("pricing_known")),
            "pricingModelKey": cost.get("pricing_model_key"),
            "costMethod": cost.get("cost_method"),
            "costReason": "AI extracted components only; deterministic code calculated final salary values.",
        }
        processing.update(
            _ja_salary_cost_provenance(cost, "provider_response_received")
        )
        return components, processing
    except Exception as e:
        p = dict(base_processing)
        cost = _ja_salary_cost_details(model, usage, provider)
        if not api_called:
            cost = dict(cost)
            cost.update({
                "pricing_known": False,
                "pricing_model_key": None,
                "cost_method": "no_api_response",
            })
        failure = _llm_paid_failure_fields(
            e,
            model,
            provider,
            usage,
            attempted=True,
        )
        p.update({
            "aiAttempted": True,
            "aiUsed": False,
            "aiApiCalled": bool(api_called),
            "provider": provider,
            "model": model or "none",
            "inputTokens": int(cost.get("input_tokens") or 0),
            "outputTokens": int(cost.get("output_tokens") or 0),
            "totalTokens": int(cost.get("total_tokens") or 0),
            "apiCalls": int(cost.get("api_calls") or 0),
            "promptCacheHitTokens": int(cost.get("prompt_cache_hit_tokens") or 0),
            "promptCacheMissTokens": int(cost.get("prompt_cache_miss_tokens") or 0),
            "costUsd": float(cost.get("usd") or 0.0),
            "pricingKnown": bool(cost.get("pricing_known")),
            "pricingModelKey": cost.get("pricing_model_key"),
            "costMethod": cost.get("cost_method"),
            "fallbackReason": str(e)[:500],
            "costReason": "AI API returned no usable components; returned token usage/cost was still recorded before local deterministic fallback." if api_called else "AI extraction failed before an API response; local deterministic fallback used.",
        })
        p.update(
            _ja_salary_cost_provenance(
                cost,
                failure.get("paid_call_status"),
            )
        )
        p["billingReconciliation"] = failure.get("billing_reconciliation")
        return None, p


def _ja_build_salary_notice_canonical(fields, candidate=None, ai_components=None, processing=None, spelling_correction=True):
    """Build the single canonical object used by JobAdder, UI and records."""
    fields = fields or {}
    candidate = candidate if isinstance(candidate, dict) else {}
    current_raw = _onenote_clean_field_value(fields.get("current_salary_breakdown", ""))
    expected_raw = _onenote_clean_field_value(fields.get("expected_salary", ""))
    notice_raw = _onenote_clean_field_value(fields.get("notice_period", ""))
    current_normalized, current_typo_changes = _ja_salary_normalize_recruiter_typos(current_raw, with_changes=True)
    expected_normalized, expected_typo_changes = _ja_salary_normalize_recruiter_typos(expected_raw, with_changes=True)
    currency_selection = _ja_currency_selection(current_raw, expected_raw, candidate, ai_components)
    currency = currency_selection.get("selectedCurrency")
    current_currency = currency_selection.get("currentCurrency") or currency
    expected_currency = currency_selection.get("expectedCurrency") or currency

    local_current_calc = _ja_calc_fixed_salary_detailed(current_raw, currency=current_currency)
    ai_current_ok, ai_current_reason = _ja_validate_ai_current_components(ai_components, current_raw) if ai_components else (False, "No AI components supplied.")
    ai_current_calc = _ja_current_from_ai_components(ai_components, current_raw, current_currency) if ai_components and ai_current_ok else None
    current_calc = ai_current_calc or local_current_calc
    current = {
        "raw": current_raw,
        "currency": current_currency,
        "source": "blank" if not current_raw else "unparsed",
        "baseMonthly": None,
        "fixedMonthlyAllowance": 0,
        "otherFixedMonthlyCash": 0,
        "includedEmployerEpf": 0,
        "guaranteedSalaryMonths": 12.0,
        "monthlyEquivalent": None,
        "display": "",
        "breakdown": current_raw,
        "writeToProfile": False,
    }
    if current_calc and current_calc.get("monthlyEquivalent") is not None:
        current.update(current_calc)
        current["currency"] = current_currency
        current["display"] = _ja_salary_display(current_currency, current.get("monthlyEquivalent"), equivalent=True)
        current["source"] = "ai_component_extraction_validated" if ai_current_calc else "screening_note"
        current["writeToProfile"] = True
    elif current_raw and _ja_salary_has_actual_amount(current_raw):
        fallback = _ja_salary_plain_number(current_raw)
        if fallback:
            current.update({
                "source": "screening_note_plain_amount", "baseMonthly": fallback,
                "monthlyEquivalent": fallback, "display": _ja_salary_display(current_currency, fallback, equivalent=True),
                "writeToProfile": True, "roundingRule": "ROUND_HALF_UP_TO_WHOLE_CURRENCY",
            })

    existing_current = _ja_existing_current_salary(candidate)
    basis_current = current.get("monthlyEquivalent")
    if basis_current is None and existing_current is not None:
        basis_current = int(existing_current)
        current.update({
            "source": "existing_candidate_profile", "monthlyEquivalent": basis_current,
            "display": _ja_salary_display(current_currency, basis_current, equivalent=True),
            "writeToProfile": False,
        })

    local_expected = _ja_build_expected_canonical(expected_raw, basis_current, currency=expected_currency)
    ai_expected_ok, ai_expected_reason = _ja_validate_ai_expected_components(ai_components, expected_raw, local_expected) if ai_components else (False, "No AI components supplied.")
    expected = _ja_expected_from_ai_components(ai_components, expected_raw, basis_current, expected_currency) if ai_components and ai_expected_ok else None
    if expected is None:
        expected = local_expected
    expected["currency"] = expected_currency

    availability, notice_details = _ja_notice_availability(notice_raw, spelling_correction=spelling_correction)
    notice = {
        "raw": notice_raw,
        "display": notice_details.get("matched") or (notice_raw if notice_raw else ""),
        "ok": notice_details.get("ok") is not False,
        "payload": availability,
        "spaPayload": _ja_notice_spa_payload(availability),
        "details": notice_details,
    }

    expected_basis_ok = True
    if expected.get("type", "").startswith("percent") and expected.get("writeToProfile"):
        expected_basis_ok = expected.get("basisCurrentAmount") == current.get("monthlyEquivalent")
        if not expected_basis_ok and current.get("monthlyEquivalent") is not None:
            expected = _ja_build_expected_canonical(expected_raw, current.get("monthlyEquivalent"), currency=expected_currency)
            expected["currency"] = expected_currency
            expected_basis_ok = expected.get("basisCurrentAmount") == current.get("monthlyEquivalent")

    fingerprint_input = {
        "currentRaw": current_raw,
        "expectedRaw": expected_raw,
        "currentCurrency": current_currency,
        "expectedCurrency": expected_currency,
        "selectedCurrency": currency,
        "basisCurrent": current.get("monthlyEquivalent"),
        "canonicalVersion": "salary-v1",
        "aiComponents": ai_components if isinstance(ai_components, dict) else None,
    }
    fingerprint = hashlib.sha256(json.dumps(fingerprint_input, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:20]
    proc = dict(processing or {
        "fieldExtraction": "local_label_parser",
        "salaryCalculation": "deterministic_code",
        "aiAttempted": False,
        "aiUsed": False,
        "aiApiCalled": False,
        "cacheHit": False,
        "provider": "none",
        "model": "none",
        "inputTokens": 0,
        "outputTokens": 0,
        "costUsd": 0.0,
        "costReason": "Local deterministic salary parser used; no AI provider call."
    })
    proc.update({
        "currencyDetectionScope": ["current_salary_breakdown", "expected_salary"],
        "currencySelectionRule": currency_selection.get("selectionRule"),
        "selectedCurrency": currency,
        "jobAdderCurrencyOption": currency_selection.get("jobAdderOption"),
        "aiCurrentComponentsApplied": bool(ai_current_calc),
        "aiExpectedComponentsApplied": bool(expected.get("componentSource") == "ai_component_extraction"),
        "aiCurrentValidationReason": ai_current_reason,
        "aiExpectedValidationReason": ai_expected_reason,
        "salaryTypoNormalizationVersion": "salary-typo-v1",
        "salaryTypoNormalizationApplied": bool(current_typo_changes or expected_typo_changes),
        "salaryTypoNormalizationCount": len(current_typo_changes) + len(expected_typo_changes),
    })
    return {
        "canonicalVersion": "salary-v1",
        "currency": currency,
        "currentCurrency": current_currency,
        "expectedCurrency": expected_currency,
        "currencySelection": currency_selection,
        "current": current,
        "expected": expected,
        "notice": notice,
        "normalization": {
            "version": "salary-typo-v1",
            "scope": ["current_salary_breakdown", "expected_salary"],
            "currentNormalizedForParsing": current_normalized,
            "expectedNormalizedForParsing": expected_normalized,
            "currentChanges": current_typo_changes,
            "expectedChanges": expected_typo_changes,
        },
        "processing": proc,
        "validation": {
            "salaryFingerprint": fingerprint,
            "expectedBasisMatchesCurrent": bool(expected_basis_ok),
            "roundingRule": "ROUND_HALF_UP_TO_WHOLE_CURRENCY",
            "noDisplayReparse": True,
            "calculationOwner": "deterministic_code",
            "aiOnlyExtractedComponents": bool(ai_components),
            "aiComponentsEvidenceValidated": True,
            "currencyDetectionLimitedToSalaryFields": True,
            "explicitCurrencyAliasesOverrideConflictingAi": True,
            "expectedCurrencyWinsDropdown": True,
            "salaryTypoNormalizationDeterministic": True,
            "salaryTypoNormalizationScopeLimited": True,
        },
    }


def _ja_submit_employment_from_candidate(candidate):
    """Convert the readable candidate employment model to safe update fields.

    Only current/ideal branches are preserved because they are the branches this
    workflow may update. Employment history is deliberately omitted from the PUT
    so the workflow never rewrites CV-derived job history.
    """
    employment = candidate.get("employment") if isinstance(candidate, dict) else None
    if not isinstance(employment, dict):
        return {}
    out = {}
    current = employment.get("current")
    if isinstance(current, dict):
        c = {}
        for key in ("employer", "position"):
            if current.get(key) not in (None, ""):
                c[key] = current.get(key)
        wt = current.get("workType")
        if isinstance(wt, dict) and wt.get("workTypeId") is not None:
            c["workTypeId"] = wt.get("workTypeId")
        salary = current.get("salary")
        if isinstance(salary, dict):
            s = {k: salary.get(k) for k in ("ratePer", "rate", "currency") if salary.get(k) is not None}
            if s:
                c["salary"] = s
        if c:
            out["current"] = c
    ideal = employment.get("ideal")
    if isinstance(ideal, dict):
        i = {}
        if ideal.get("position") not in (None, ""):
            i["position"] = ideal.get("position")
        wt = ideal.get("workType")
        if isinstance(wt, dict) and wt.get("workTypeId") is not None:
            i["workTypeId"] = wt.get("workTypeId")
        salary = ideal.get("salary")
        if isinstance(salary, dict):
            s = {k: salary.get(k) for k in ("ratePer", "rateLow", "rateHigh", "currency") if salary.get(k) is not None}
            if s:
                i["salary"] = s
        other_out = []
        for other in ideal.get("other") or []:
            if not isinstance(other, dict):
                continue
            o = {}
            wt = other.get("workType")
            if isinstance(wt, dict) and wt.get("workTypeId") is not None:
                o["workTypeId"] = wt.get("workTypeId")
            salary = other.get("salary")
            if isinstance(salary, dict):
                s = {k: salary.get(k) for k in ("ratePer", "rateLow", "rateHigh", "currency") if salary.get(k) is not None}
                if s:
                    o["salary"] = s
            if o:
                other_out.append(o)
        if other_out:
            i["other"] = other_out
        if i:
            out["ideal"] = i
    return out


def _ja_candidate_salary_notice_payload(fields, candidate=None, salary_canonical=None):
    fields = fields or {}
    candidate = candidate if isinstance(candidate, dict) else {}
    canonical = salary_canonical if isinstance(salary_canonical, dict) else _ja_build_salary_notice_canonical(fields, candidate)
    current_item = canonical["current"]
    expected_item = canonical["expected"]
    notice_item = canonical["notice"]
    currency = canonical.get("currency")
    current_currency = canonical.get("currentCurrency") or currency
    expected_currency = canonical.get("expectedCurrency") or currency
    currency_selection = canonical.get("currencySelection") if isinstance(canonical.get("currencySelection"), dict) else {}

    details = {
        "currentSalary": {"ok": True, "skipped": True, "reason": "No current salary value"},
        "expectedSalary": {"ok": True, "skipped": True, "reason": "No expected salary value"},
        "noticePeriod": notice_item.get("details") or {"ok": True, "skipped": True},
        "currency": currency,
        "currencyField": {
            "ok": True,
            "skipped": not bool(currency_selection.get("jobAdderOption")),
            "selectedCurrency": currency,
            "currentCurrency": current_currency,
            "expectedCurrency": expected_currency,
            "jobAdderOption": currency_selection.get("jobAdderOption"),
            "selectionRule": currency_selection.get("selectionRule"),
            "optionSource": currency_selection.get("optionSource"),
            "warning": currency_selection.get("warning"),
        },
        "canonicalSalary": canonical,
    }
    employment = _ja_submit_employment_from_candidate(candidate)
    employment_changed = False

    if current_item.get("writeToProfile") and current_item.get("monthlyEquivalent") is not None:
        value = int(current_item["monthlyEquivalent"])
        current = dict(employment.get("current") or {})
        if current.get("workTypeId") is None:
            current["workTypeId"] = _ONENOTE_JA_PERMANENT_WORKTYPE_ID
        salary = {"ratePer": "Month", "rate": value}
        if current_currency:
            salary["currency"] = current_currency
        current["salary"] = salary
        employment["current"] = current
        employment_changed = True
        details["currentSalary"] = {
            "ok": True, "value": value, "raw": current_item.get("raw"),
            "calculation": current_item, "fingerprint": canonical["validation"]["salaryFingerprint"],
        }
    elif current_item.get("raw"):
        details["currentSalary"] = {"ok": False, "reason": "Could not parse current salary", "raw": current_item.get("raw")}

    if expected_item.get("writeToProfile") and expected_item.get("minAmount") is not None:
        lo = int(expected_item["minAmount"])
        hi = int(expected_item.get("maxAmount", lo))
        ideal = dict(employment.get("ideal") or {})
        if ideal.get("workTypeId") is None:
            ideal["workTypeId"] = _ONENOTE_JA_PERMANENT_WORKTYPE_ID
        salary = {"ratePer": "Month", "rateLow": lo, "rateHigh": hi}
        if expected_currency:
            salary["currency"] = expected_currency
        ideal["salary"] = salary
        employment["ideal"] = ideal
        employment_changed = True
        details["expectedSalary"] = {
            "ok": True, "min": lo, "max": hi, "raw": expected_item.get("raw"),
            "calculation": expected_item, "basisCurrentAmount": expected_item.get("basisCurrentAmount"),
            "fingerprint": canonical["validation"]["salaryFingerprint"],
        }
    elif expected_item.get("raw") and expected_item.get("type") not in ("open", "blank"):
        details["expectedSalary"] = {"ok": False, "reason": "Could not parse expected salary", "raw": expected_item.get("raw")}
    elif expected_item.get("type") == "open":
        details["expectedSalary"] = {"ok": True, "skipped": True, "reason": "Expected salary is open/negotiable", "raw": expected_item.get("raw")}

    payload = {}
    if employment_changed:
        payload["employment"] = employment
    if notice_item.get("payload"):
        payload["availability"] = notice_item["payload"]
    currency_option = currency_selection.get("jobAdderOption")
    candidate_custom_present = "custom" in candidate and isinstance(candidate.get("custom"), list)
    if currency_option and not candidate_custom_present:
        details["currencyField"].update({
            "ok": False,
            "skipped": True,
            "reason": "Candidate GET did not include the custom field collection; Currency write was skipped to avoid clearing unseen custom fields.",
            "value": currency_option,
            "fieldId": _JA_CURRENCY_CUSTOM_FIELD_ID,
        })
    elif currency_option:
        existing_option = None
        for custom_item in candidate.get("custom") or []:
            if not isinstance(custom_item, dict):
                continue
            try:
                existing_field_id = int(custom_item.get("fieldId") or 0)
            except Exception:
                continue
            if existing_field_id == _JA_CURRENCY_CUSTOM_FIELD_ID:
                existing_option = str(custom_item.get("value") or "")
                break
        if existing_option != currency_option:
            # Preserve every existing public-API custom field value while
            # replacing/adding field 4. This mirrors Kano's full customFields
            # clone and avoids clearing unrelated Industry/Skills/etc. values
            # if the tenant treats UpdateCandidate.custom as replacement-like.
            custom_payload = []
            currency_replaced = False
            for custom_item in candidate.get("custom") or []:
                if not isinstance(custom_item, dict):
                    continue
                try:
                    field_id = int(custom_item.get("fieldId"))
                except Exception:
                    continue
                value = custom_item.get("value")
                if field_id == _JA_CURRENCY_CUSTOM_FIELD_ID:
                    custom_payload.append({"fieldId": field_id, "value": currency_option})
                    currency_replaced = True
                elif value is not None:
                    custom_payload.append({"fieldId": field_id, "value": value})
            if not currency_replaced:
                custom_payload.append({"fieldId": _JA_CURRENCY_CUSTOM_FIELD_ID, "value": currency_option})
            payload["custom"] = custom_payload
            details["currencyField"].update({"skipped": False, "value": currency_option, "fieldId": _JA_CURRENCY_CUSTOM_FIELD_ID, "preservedCustomFieldCount": max(0, len(custom_payload) - 1)})
        else:
            details["currencyField"].update({"skipped": True, "reason": "Candidate Currency already matched", "value": currency_option, "fieldId": _JA_CURRENCY_CUSTOM_FIELD_ID})
    elif currency_selection.get("selectedCurrency"):
        details["currencyField"].update({"ok": False, "skipped": True, "reason": currency_selection.get("warning") or "No matching JobAdder Currency option"})
    return payload, details


def _ja_update_candidate_salary_notice(candidate_id, fields, ai_components=None, ai_processing=None, spelling_correction=True):
    candidate_path = "candidates/{}".format(urllib.parse.quote(str(candidate_id), safe=""))
    candidate = {}
    read_status = None
    read_warning = None
    try:
        read_status, candidate = _ja_get_json(candidate_path, timeout=20)
        if not isinstance(candidate, dict):
            candidate = {}
    except Exception as e:
        read_warning = "Could not read existing candidate profile before salary/notice update: {}".format(str(e)[:500])
        # Safety boundary: do not write nested employment/availability without
        # first reading the current profile that must be preserved.
        preview_canonical = _ja_build_salary_notice_canonical(fields, {}, ai_components, ai_processing, spelling_correction=spelling_correction)
        preview_payload, preview_details = _ja_candidate_salary_notice_payload(fields, {}, preview_canonical)
        return {
            "ok": False,
            "skipped": True,
            "candidate_read_status": None,
            "candidate_read_warning": read_warning,
            "payload_fields": sorted(preview_payload.keys()),
            "details": preview_details,
            "salary_canonical": preview_details.get("canonicalSalary"),
            "error": read_warning,
        }
    canonical = _ja_build_salary_notice_canonical(fields, candidate, ai_components, ai_processing, spelling_correction=spelling_correction)
    canonical["currencySelection"] = _ja_validate_currency_option_with_api(canonical.get("currencySelection"))
    canonical["processing"]["jobAdderCurrencyOption"] = canonical["currencySelection"].get("jobAdderOption")
    canonical["processing"]["currencyOptionSource"] = canonical["currencySelection"].get("optionSource")
    payload, details = _ja_candidate_salary_notice_payload(fields, candidate, canonical)
    result = {
        "ok": True,
        "skipped": not bool(payload),
        "candidate_read_status": read_status,
        "candidate_read_warning": read_warning,
        "payload_fields": sorted(payload.keys()),
        "details": details,
        "salary_canonical": details.get("canonicalSalary"),
    }
    parse_warnings = []
    for key in ("currentSalary", "expectedSalary", "noticePeriod", "currencyField"):
        item = details.get(key) or {}
        if item.get("ok") is False:
            parse_warnings.append("{}: {}".format(key, item.get("reason") or "could not parse"))
    if not payload:
        result["warning"] = "; ".join(parse_warnings) if parse_warnings else None
        return result
    try:
        status, response = _ja_put_json(candidate_path, payload, timeout=25)
        result.update({"status": status, "response": response, "skipped": False})
        if parse_warnings:
            result["warning"] = "; ".join(parse_warnings)
        return result
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        result.update({
            "ok": False,
            "skipped": False,
            "status": int(e.code),
            "error": "JobAdder candidate profile update failed",
            "detail": _ja_compact_error_body(body),
            "raw": body[:3000],
        })
        return result
    except Exception as e:
        result.update({"ok": False, "skipped": False, "error": str(e)[:1000]})
        return result

