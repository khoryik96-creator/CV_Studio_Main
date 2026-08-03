from __future__ import annotations

import hmac
import json
from io import BytesIO
from pathlib import Path
from typing import Any

from flask import Blueprint, current_app, jsonify, render_template, request, send_file

from .ai_rule_updater import AiRuleUpdateError, preview_rule_update
from .bootstrap import ensure_data_dir
from .calculator import CalculationError, calculate_scenario, compare_results
from .exporter import build_docx_report, build_pdf_report, safe_filename
from .fx_service import FxService, FxServiceError
from .repository import JsonRuleRepository, RuleNotFoundError, RuleRepositoryError
from .validators import RuleValidationError

bp = Blueprint(
    "salary_comparison",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/salary-comparison-static",
)


def _data_dir() -> Path:
    configured = current_app.config.get("SALARY_COMPARISON_DATA_DIR")
    if configured:
        return ensure_data_dir(Path(configured))
    return ensure_data_dir(Path(__file__).resolve().parent / "data")


def _repo() -> JsonRuleRepository:
    return JsonRuleRepository(_data_dir() / "tax_rules.json")


def _fx() -> FxService:
    endpoint = current_app.config.get(
        "SALARY_COMPARISON_FX_ENDPOINT",
        "https://api.frankfurter.dev/v2/rate/{base}/{quote}",
    )
    return FxService(
        _data_dir() / "fx_cache.json",
        endpoint=endpoint,
        max_age_hours=float(current_app.config.get("SALARY_COMPARISON_FX_MAX_AGE_HOURS", 24)),
    )


def _country_map() -> list[dict[str, str]]:
    path = _data_dir() / "country_currency.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuleRepositoryError(f"Unable to read country/currency data: {exc}") from exc
    countries = payload.get("countries") if isinstance(payload, dict) else None
    if not isinstance(countries, list):
        raise RuleRepositoryError("Country/currency data must contain a countries list.")
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in countries:
        if not isinstance(item, dict):
            continue
        country = str(item.get("country") or "").strip()
        currency = str(item.get("currency") or "").strip().upper()
        if not country or len(currency) != 3 or not currency.isalpha():
            continue
        key = country.casefold()
        if key not in seen:
            result.append({"country": country, "currency": currency})
            seen.add(key)
    if not result:
        raise RuleRepositoryError("No valid country/currency mappings are available.")
    return result


def _admin_allowed() -> bool:
    token = str(current_app.config.get("SALARY_COMPARISON_ADMIN_TOKEN") or "")
    if not token:
        return True
    supplied = str(request.headers.get("X-Salary-Admin-Token") or "")
    return hmac.compare_digest(supplied, token)


def _json_object() -> dict[str, Any]:
    try:
        payload = request.get_json(silent=True)
    except TypeError:  # Compatibility with the lightweight route-test fake.
        payload = request.get_json(force=True)
    if payload is None:
        raise CalculationError("Request body must contain valid JSON.")
    if not isinstance(payload, dict):
        raise CalculationError("Request body must be a JSON object.")
    return payload


def _request_bool(value: Any, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, "", 0, "0", "false", "False", "no", "off"):
        return False
    if value in (1, "1", "true", "True", "yes", "on"):
        return True
    raise CalculationError(f"{field_name} must be true or false.")


@bp.get("/")
def index():
    # When a host key resolver is wired (CV Studio), the provider key is
    # resolved server-side; the page must not prompt for or send a key.
    host_managed_ai = bool(current_app.config.get("SALARY_COMPARISON_KEY_RESOLVER"))
    return render_template(
        "salary_comparison/index.html", host_managed_ai=host_managed_ai
    )


@bp.get("/api/config")
def config_api():
    rules = _repo().list_rules()
    years_by_country: dict[str, list[int]] = {}
    for rule in rules:
        years_by_country.setdefault(rule["country"], []).append(int(rule["tax_year"]))
    years_by_country = {key: sorted(set(value), reverse=True) for key, value in years_by_country.items()}
    return jsonify({
        "countries": _country_map(),
        "years_by_country": years_by_country,
        "residency_profiles": ["Resident", "Non-Resident"],
        "rules": [
            {
                "country": rule["country"],
                "tax_year": rule["tax_year"],
                "residency": rule["residency"],
                "currency": rule["currency"],
                "verified": rule.get("verified", False),
                "tax_brackets_verified": rule.get("tax_brackets_verified", False),
                "contribution_rule_verified": rule.get("contribution_rule_verified", False),
                "last_updated": rule.get("last_updated"),
            }
            for rule in rules
        ],
    })


@bp.post("/api/fx")
def fx_api():
    payload = _json_object()
    result = _fx().get_rate(
        payload.get("base"),
        payload.get("quote"),
        refresh=_request_bool(payload.get("refresh", False), "refresh"),
    )
    return jsonify(result)


def _scenario_with_fx(scenario: dict[str, Any]) -> tuple[dict[str, Any], float, dict[str, Any]]:
    if not isinstance(scenario, dict):
        raise CalculationError("Each scenario must be a JSON object.")
    country = str(scenario.get("country") or "").strip()
    residency = str(scenario.get("residency") or "Resident").strip()
    if not country:
        raise CalculationError("Country is required for each scenario.")
    try:
        tax_year = int(scenario.get("tax_year"))
    except (TypeError, ValueError) as exc:
        raise CalculationError("Tax year must be a whole number for each scenario.") from exc

    rule = _repo().get_rule(country, tax_year, residency)
    local_currency = str(rule["currency"]).strip().upper()
    reporting_currency = str(scenario.get("reporting_currency") or local_currency).strip().upper()
    if len(reporting_currency) != 3 or not reporting_currency.isalpha():
        raise CalculationError("Reporting currency must be a three-letter code.")
    scenario["country"] = country
    scenario["tax_year"] = tax_year
    scenario["residency"] = residency
    scenario["local_currency"] = local_currency
    scenario["reporting_currency"] = reporting_currency

    override = scenario.get("fx_rate_override")
    if override not in (None, ""):
        # calculate_scenario performs the authoritative finite/positive validation.
        fx_rate = override
        fx_metadata = {
            "base": local_currency,
            "quote": reporting_currency,
            "rate": override,
            "source": "manual override",
            "cached": False,
        }
    else:
        fx_metadata = _fx().get_rate(local_currency, reporting_currency, refresh=False)
        fx_rate = fx_metadata["rate"]
    return rule, fx_rate, fx_metadata


def _calculate_comparison(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if not isinstance(payload, dict):
        raise CalculationError("Comparison request must be a JSON object.")
    scenario_a_raw = payload.get("scenario_a")
    scenario_b_raw = payload.get("scenario_b")
    if not isinstance(scenario_a_raw, dict) or not isinstance(scenario_b_raw, dict):
        raise CalculationError("Both scenario_a and scenario_b must be JSON objects.")
    scenario_a = dict(scenario_a_raw)
    scenario_b = dict(scenario_b_raw)
    rule_a, fx_a, fx_meta_a = _scenario_with_fx(scenario_a)
    rule_b, fx_b, fx_meta_b = _scenario_with_fx(scenario_b)
    result_a = calculate_scenario(scenario_a, rule_a, fx_a)
    result_b = calculate_scenario(scenario_b, rule_b, fx_b)
    comparison = compare_results(result_a, result_b)
    response = {
        "scenario_a": result_a.as_dict(),
        "scenario_b": result_b.as_dict(),
        "comparison": comparison,
        "fx": {"scenario_a": fx_meta_a, "scenario_b": fx_meta_b},
    }
    return scenario_a, scenario_b, response


@bp.post("/api/compare")
def compare_api():
    _, _, response = _calculate_comparison(_json_object())
    return jsonify(response)


@bp.post("/api/export/<export_format>")
def export_api(export_format: str):
    format_name = str(export_format or "").strip().lower()
    if format_name not in {"pdf", "word", "docx"}:
        return jsonify({"error": "Export format must be PDF or Word."}), 400

    scenario_a, scenario_b, response = _calculate_comparison(_json_object())
    name_a = str(scenario_a.get("name") or "Scenario-A")
    name_b = str(scenario_b.get("name") or "Scenario-B")
    base_name = safe_filename(f"salary-comparison-{name_a}-vs-{name_b}")

    export_args = (
        scenario_a,
        scenario_b,
        response["scenario_a"],
        response["scenario_b"],
        response["comparison"],
        response["fx"],
    )
    if format_name == "pdf":
        content = build_pdf_report(*export_args)
        mimetype = "application/pdf"
        extension = "pdf"
    else:
        content = build_docx_report(*export_args)
        mimetype = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        extension = "docx"
    return send_file(
        BytesIO(content),
        mimetype=mimetype,
        as_attachment=True,
        download_name=f"{base_name}.{extension}",
        max_age=0,
    )


@bp.post("/api/rules/preview")
def rules_preview_api():
    if not _admin_allowed():
        return jsonify({"error": "Invalid administrator token."}), 403
    resolver = current_app.config.get("SALARY_COMPARISON_KEY_RESOLVER")
    if resolver is not None and not callable(resolver):
        resolver = None
    return jsonify(preview_rule_update(_json_object(), key_resolver=resolver))


@bp.post("/api/rules/publish")
def rules_publish_api():
    if not _admin_allowed():
        return jsonify({"error": "Invalid administrator token."}), 403
    payload = _json_object()
    rule = payload.get("rule")
    if not isinstance(rule, dict):
        raise RuleValidationError("rule must be a JSON object.")
    published = _repo().publish(rule)
    return jsonify({"published": published})


@bp.errorhandler(CalculationError)
@bp.errorhandler(RuleNotFoundError)
@bp.errorhandler(RuleValidationError)
@bp.errorhandler(RuleRepositoryError)
@bp.errorhandler(FxServiceError)
@bp.errorhandler(AiRuleUpdateError)
def handled_error(exc: Exception):
    return jsonify({"error": str(exc), "type": type(exc).__name__}), 400


@bp.errorhandler(Exception)
def unexpected_error(exc: Exception):
    current_app.logger.exception("Salary comparison error")
    return jsonify({"error": "Unexpected salary-comparison error."}), 500
