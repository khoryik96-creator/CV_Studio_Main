from __future__ import annotations

import json
import random
from decimal import Decimal
from pathlib import Path

from salary_comparison.calculator import calculate_scenario, progressive_tax


def _rules():
    data = json.loads((Path(__file__).resolve().parents[2] / "salary_comparison/data/tax_rules.json").read_text())
    return {rule["country"]: rule for rule in data["rules"]}


def test_progressive_tax_randomized_monotonicity_and_nonnegative():
    random.seed(20260731)
    for rule in _rules().values():
        incomes = sorted(Decimal(str(random.uniform(0, 3_000_000))) for _ in range(1000))
        previous = Decimal("0")
        for income in incomes:
            tax = progressive_tax(income, rule["tax_brackets"])
            assert tax >= 0
            assert tax >= previous
            assert tax <= income
            previous = tax


def test_randomized_salary_accounting_identities():
    random.seed(5601)
    for country, rule in _rules().items():
        for _ in range(500):
            base = random.uniform(0, 100000)
            allowance = random.uniform(0, 10000)
            guaranteed = random.uniform(0, 5)
            sign_on = random.uniform(0, 50000)
            variable_months = random.uniform(0, 5)
            other = random.uniform(0, 20000)
            relief = random.uniform(0, 50000)
            deductions = random.uniform(0, 10000)
            scenario = {
                "country": country,
                "tax_year": 2025,
                "residency": "Resident",
                "monthly_base": base,
                "monthly_fixed_allowance": allowance,
                "guaranteed_bonus_months": guaranteed,
                "sign_on_bonus": sign_on,
                "variable_bonus_mode": "months",
                "variable_bonus_months": variable_months,
                "other_taxable_income": other,
                "personal_tax_reliefs": relief,
                "other_after_tax_deductions": deductions,
                "include_bonus_in_contribution_base": bool(random.getrandbits(1)),
                "reporting_currency": rule["currency"],
            }
            result = calculate_scenario(scenario, rule, 1)
            # Gross monthly annualises the fixed cash only (excludes variable bonus).
            assert abs(result.gross_monthly_cash * 12 - result.gross_annual_cash_ex_variable) <= 0.12
            assert abs(
                result.net_annual_cash
                - (result.gross_annual_cash - result.employee_contribution - result.estimated_income_tax - result.other_after_tax_deductions)
            ) <= 0.04
            assert abs(result.total_employer_cost - (result.gross_annual_cash + result.employer_contribution)) <= 0.03
            assert result.estimated_income_tax >= 0
            assert result.employee_contribution >= 0
            assert result.employer_contribution >= 0
