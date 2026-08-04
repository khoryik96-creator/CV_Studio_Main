from decimal import Decimal

import pytest

from salary_comparison.calculator import CalculationError, calculate_scenario, compare_results, marginal_tax_rate, progressive_tax


def base_scenario(**overrides):
    scenario = {
        "country": "Malaysia",
        "tax_year": 2025,
        "residency": "Resident",
        "monthly_base": 12000,
        "monthly_fixed_allowance": 500,
        "guaranteed_bonus_months": 1,
        "sign_on_bonus": 0,
        "variable_bonus_mode": "percentage",
        "variable_bonus_pct": 0.10,
        "other_taxable_income": 0,
        "personal_tax_reliefs": 9000,
        "other_after_tax_deductions": 0,
        "include_bonus_in_contribution_base": True,
        "reporting_currency": "MYR",
    }
    scenario.update(overrides)
    return scenario


def test_progressive_tax_simple():
    brackets = [
        {"lower": 0, "upper": 100, "rate": 0.0},
        {"lower": 100, "upper": 200, "rate": 0.10},
        {"lower": 200, "upper": None, "rate": 0.20},
    ]
    assert progressive_tax(Decimal("250"), brackets) == Decimal("20")


def test_malaysia_sample_calculation(malaysia_rule):
    result = calculate_scenario(base_scenario(), malaysia_rule, 1.0)
    assert result.annual_base == 144000
    assert result.annual_fixed_allowance == 6000
    assert result.guaranteed_bonus == 12000
    assert result.variable_bonus == 14400
    assert result.gross_annual_cash == 176400
    # Gross monthly excludes the variable performance bonus: 162000 / 12.
    assert result.gross_monthly_cash == 13500
    assert result.employee_contribution == 19404
    assert result.estimated_income_tax == 26250
    assert result.marginal_income_tax_rate == 0.25
    assert result.net_annual_cash == 130746
    assert result.net_monthly_cash == 10895.5
    assert result.total_employer_cost == 197568


def test_gross_ex_variable_subtracts_the_variable_bonus(malaysia_rule):
    result = calculate_scenario(base_scenario(), malaysia_rule, 1.0)
    assert result.variable_bonus == 14400
    assert result.gross_annual_cash_ex_variable == result.gross_annual_cash - result.variable_bonus
    assert result.gross_annual_cash_ex_variable == 162000


def test_net_ex_variable_recomputes_tax_and_contributions(malaysia_rule):
    result = calculate_scenario(base_scenario(), malaysia_rule, 1.0)
    # Removing the variable bonus lowers net cash, but by less than the bonus
    # itself because the bonus also drew income tax and statutory contributions.
    dropped = result.net_annual_cash - result.net_annual_cash_ex_variable
    assert 0 < dropped < result.variable_bonus
    assert result.net_annual_cash_ex_variable == 121530


def test_gross_monthly_excludes_variable_bonus(malaysia_rule):
    result = calculate_scenario(base_scenario(), malaysia_rule, 1.0)
    # Monthly gross is the fixed annual cash (excl. variable bonus) over 12.
    assert result.gross_monthly_cash == round(result.gross_annual_cash_ex_variable / 12, 2)
    assert result.gross_monthly_cash < result.gross_annual_cash / 12


def test_ex_variable_equals_full_when_no_variable_bonus(malaysia_rule):
    result = calculate_scenario(base_scenario(variable_bonus_pct=0), malaysia_rule, 1.0)
    assert result.variable_bonus == 0
    assert result.gross_annual_cash_ex_variable == result.gross_annual_cash
    assert result.net_annual_cash_ex_variable == result.net_annual_cash


def test_sign_on_bonus_and_other_income(malaysia_rule):
    result = calculate_scenario(
        base_scenario(monthly_base=10000, sign_on_bonus=2000, other_taxable_income=1000),
        malaysia_rule,
        1,
    )
    assert result.sign_on_bonus == 2000
    assert result.other_taxable_income == 1000
    assert result.gross_annual_cash == 151000


def test_contribution_bonus_toggle(malaysia_rule):
    result = calculate_scenario(base_scenario(include_bonus_in_contribution_base=False), malaysia_rule, 1)
    assert result.contribution_base == 150000


def test_contribution_overrides_and_cap(malaysia_rule):
    result = calculate_scenario(
        base_scenario(
            employee_contribution_rate_override=0.05,
            employer_contribution_rate_override=0.07,
            contribution_cap_override=100000,
        ),
        malaysia_rule,
        1,
    )
    assert result.employee_contribution_rate == 0.05
    assert result.employer_contribution_rate == 0.07
    assert result.employee_contribution == 5000
    assert result.employer_contribution == 7000


def test_same_currency_fx_is_one(malaysia_rule):
    result = calculate_scenario(base_scenario(), malaysia_rule, 1)
    assert result.fx_rate == 1.0
    assert result.net_annual_reporting == result.net_annual_cash


def test_negative_salary_rejected(malaysia_rule):
    with pytest.raises(CalculationError):
        calculate_scenario(base_scenario(monthly_base=-1), malaysia_rule, 1)


def test_invalid_rate_rejected(malaysia_rule):
    with pytest.raises(CalculationError):
        calculate_scenario(base_scenario(variable_bonus_pct=1.1), malaysia_rule, 1)


def test_zero_income_rates_are_zero(malaysia_rule):
    result = calculate_scenario(
        base_scenario(monthly_base=0, monthly_fixed_allowance=0, guaranteed_bonus_months=0, variable_bonus_pct=0),
        malaysia_rule,
        1,
    )
    assert result.effective_income_tax_rate == 0
    assert result.total_employee_deduction_rate == 0


def test_compare_results_requires_same_currency(malaysia_rule):
    a = calculate_scenario(base_scenario(reporting_currency="MYR"), malaysia_rule, 1)
    b = calculate_scenario(base_scenario(reporting_currency="USD"), malaysia_rule, 0.2)
    with pytest.raises(CalculationError):
        compare_results(a, b)

def test_string_false_for_bonus_toggle_is_respected(malaysia_rule):
    result = calculate_scenario(
        base_scenario(include_bonus_in_contribution_base="false"),
        malaysia_rule,
        1,
    )
    assert result.contribution_base == 150000


def test_variable_bonus_by_months(malaysia_rule):
    result = calculate_scenario(
        base_scenario(
            monthly_base=10000,
            variable_bonus_mode="months",
            variable_bonus_pct=0,
            variable_bonus_months=1.5,
        ),
        malaysia_rule,
        1,
    )
    assert result.variable_bonus == 15000


def test_legacy_fixed_annual_bonus_input_is_still_supported(malaysia_rule):
    scenario = base_scenario()
    scenario.pop("sign_on_bonus")
    scenario["fixed_annual_bonus"] = 2500
    result = calculate_scenario(scenario, malaysia_rule, 1)
    assert result.sign_on_bonus == 2500
    assert result.as_dict()["fixed_annual_bonus"] == 2500


def test_malaysia_ya2025_25_percent_is_marginal(malaysia_rule):
    brackets = malaysia_rule["tax_brackets"]
    assert marginal_tax_rate(Decimal("100000"), brackets) == Decimal("0.19")
    assert marginal_tax_rate(Decimal("100001"), brackets) == Decimal("0.25")
    assert progressive_tax(Decimal("100001"), brackets) == Decimal("9400.25")

def test_gross_monthly_is_annual_gross_averaged_over_twelve(malaysia_rule):
    result = calculate_scenario(
        base_scenario(monthly_base=10000, guaranteed_bonus_months=1, sign_on_bonus=12000, variable_bonus_pct=0),
        malaysia_rule,
        1,
    )
    assert result.gross_annual_cash == 148000
    assert result.gross_monthly_cash == pytest.approx(12333.33)
