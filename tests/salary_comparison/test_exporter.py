from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

from docx import Document
from pypdf import PdfReader

from salary_comparison.calculator import calculate_scenario, compare_results
from salary_comparison.exporter import build_docx_report, build_pdf_report, safe_filename


def _rule(country: str) -> dict:
    path = Path(__file__).resolve().parents[2] / "salary_comparison" / "data" / "tax_rules.json"
    rules = json.loads(path.read_text(encoding="utf-8"))["rules"]
    return next(item for item in rules if item["country"] == country and item["tax_year"] == 2025)


def _scenario(country: str, name: str, base: float, allowance: float, reliefs: float) -> dict:
    return {
        "name": name,
        "country": country,
        "tax_year": 2025,
        "residency": "Resident",
        "monthly_base": base,
        "monthly_fixed_allowance": allowance,
        "guaranteed_bonus_months": 1,
        "sign_on_bonus": 1500,
        "variable_bonus_mode": "months",
        "variable_bonus_months": 1.5,
        "variable_bonus_pct": 0,
        "other_taxable_income": 0,
        "personal_tax_reliefs": reliefs,
        "other_after_tax_deductions": 0,
        "include_bonus_in_contribution_base": True,
        "reporting_currency": "MYR",
    }


def _report_args():
    scenario_a = _scenario("Malaysia", "Current role", 12000, 500, 9000)
    scenario_b = _scenario("Singapore", "Overseas offer", 9000, 600, 0)
    rule_a = _rule("Malaysia")
    rule_b = _rule("Singapore")
    scenario_a["local_currency"] = rule_a["currency"]
    scenario_b["local_currency"] = rule_b["currency"]
    result_a = calculate_scenario(scenario_a, rule_a, 1.0)
    result_b = calculate_scenario(scenario_b, rule_b, 3.2)
    comparison = compare_results(result_a, result_b)
    fx = {
        "scenario_a": {"source": "identity", "cached": False, "stale": False},
        "scenario_b": {"source": "test reference rate", "cached": True, "stale": False},
    }
    return scenario_a, scenario_b, result_a.as_dict(), result_b.as_dict(), comparison, fx


def test_safe_filename_removes_unsafe_characters():
    assert safe_filename("Salary: A / B?") == "Salary-A-B"


def test_pdf_export_is_valid_and_contains_report_text():
    content = build_pdf_report(*_report_args())
    assert content.startswith(b"%PDF")
    reader = PdfReader(BytesIO(content))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "International Salary Comparison" in text
    assert "Current role" in text
    assert "Overseas offer" in text
    assert "Net annual difference" in text
    assert "Gross monthly cash" in text
    assert "Marginal income tax rate" in text
    assert "Sign-On Bonus" in text
    assert "1.5 months of monthly base" in text
    assert "Total Gross plus Employer EPF" in text


def test_pdf_export_escapes_scenario_markup():
    args = list(_report_args())
    scenario_a = dict(args[0])
    scenario_a["name"] = "Current <Role> & Package"
    args[0] = scenario_a
    content = build_pdf_report(*args)
    reader = PdfReader(BytesIO(content))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Current <Role> & Package" in text


def test_word_export_is_valid_and_contains_report_text():
    content = build_docx_report(*_report_args())
    assert content.startswith(b"PK")
    document = Document(BytesIO(content))
    combined = "\n".join(
        node.text or "" for node in document.element.xpath(".//w:t")
    )
    assert "International Salary Comparison" in combined
    assert "Current role" in combined
    assert "Overseas offer" in combined
    assert "Net annual difference" in combined
    assert "Gross monthly cash" in combined
    assert "Marginal income tax rate" in combined
    assert "Sign-On Bonus" in combined
    assert "1.5 months of monthly base" in combined
    assert "Total Gross plus Employer EPF" in combined
