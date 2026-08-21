from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Mapping

MONEY_DP = Decimal("0.01")
RATE_DP = Decimal("0.000001")
MAX_ABSOLUTE_NUMBER = Decimal("1000000000000000")  # Defensive API/input ceiling.
BRACKET_TOLERANCE = Decimal("0.000001")


class CalculationError(ValueError):
    """Raised when a salary comparison cannot be calculated safely."""


def _d(value: Any, default: str = "0") -> Decimal:
    if value in (None, ""):
        value = default
    try:
        number = Decimal(str(value))
    except Exception as exc:  # pragma: no cover - defensive conversion guard
        raise CalculationError(f"Invalid numeric value: {value!r}") from exc
    if not number.is_finite():
        raise CalculationError(f"Numeric value must be finite: {value!r}")
    if abs(number) > MAX_ABSOLUTE_NUMBER:
        raise CalculationError("Numeric value is outside the supported range.")
    return number


def _money(value: Decimal) -> float:
    try:
        return float(value.quantize(MONEY_DP, rounding=ROUND_HALF_UP))
    except InvalidOperation as exc:  # pragma: no cover - guarded by _d/range checks
        raise CalculationError("Unable to round monetary result safely.") from exc


def _rate(value: Decimal) -> float:
    try:
        return float(value.quantize(RATE_DP, rounding=ROUND_HALF_UP))
    except InvalidOperation as exc:  # pragma: no cover - guarded by _d/range checks
        raise CalculationError("Unable to round rate result safely.") from exc


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().casefold()
    if text in {"true", "yes", "1", "on"}:
        return True
    if text in {"false", "no", "0", "off", ""}:
        return False
    raise CalculationError(f"Invalid boolean value: {value!r}")


def _bounded_rate(value: Any, field_name: str) -> Decimal:
    rate = _d(value)
    if rate < 0 or rate > 1:
        raise CalculationError(f"{field_name} must be between 0 and 1.")
    return rate


def _validated_brackets(brackets: list[Mapping[str, Any]]) -> list[tuple[Decimal, Decimal | None, Decimal]]:
    if not brackets:
        raise CalculationError("No income-tax brackets are available for this rule.")

    normalized: list[tuple[Decimal, Decimal | None, Decimal]] = []
    previous_upper: Decimal | None = None
    open_ended_seen = False
    for index, bracket in enumerate(brackets):
        if not isinstance(bracket, Mapping):
            raise CalculationError(f"Tax bracket {index + 1} is invalid.")
        if open_ended_seen:
            raise CalculationError("An open-ended tax bracket must be the final bracket.")
        lower = _d(bracket.get("lower"))
        upper_raw = bracket.get("upper")
        upper = None if upper_raw in (None, "") else _d(upper_raw)
        rate = _bounded_rate(bracket.get("rate"), "Tax bracket rate")

        if lower < 0:
            raise CalculationError(f"Tax bracket {index + 1} has a negative lower bound.")
        if index == 0 and abs(lower) > BRACKET_TOLERANCE:
            raise CalculationError("The first tax bracket must start at zero.")
        if previous_upper is not None and abs(lower - previous_upper) > BRACKET_TOLERANCE:
            raise CalculationError(f"Tax brackets are not contiguous at bracket {index + 1}.")
        if upper is not None and upper <= lower:
            raise CalculationError(f"Tax bracket {index + 1} has an invalid upper bound.")

        normalized.append((lower, upper, rate))
        previous_upper = upper
        open_ended_seen = upper is None

    if not open_ended_seen:
        raise CalculationError("The final tax bracket must be open-ended.")
    return normalized


@dataclass(frozen=True)
class ScenarioResult:
    country: str
    tax_year: int
    residency: str
    local_currency: str
    reporting_currency: str
    fx_rate: float
    annual_base: float
    annual_fixed_allowance: float
    guaranteed_bonus: float
    sign_on_bonus: float
    variable_bonus: float
    other_taxable_income: float
    gross_annual_cash: float
    gross_annual_cash_ex_variable: float
    gross_monthly_cash: float
    contribution_base: float
    employee_contribution_rate: float
    employer_contribution_rate: float
    employee_contribution: float
    employer_contribution: float
    taxable_income: float
    estimated_income_tax: float
    marginal_income_tax_rate: float
    other_after_tax_deductions: float
    net_annual_cash: float
    net_annual_cash_ex_variable: float
    net_monthly_cash: float
    total_employer_cost: float
    effective_income_tax_rate: float
    total_employee_deduction_rate: float
    net_annual_reporting: float
    employer_cost_reporting: float
    rule_metadata: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        data = self.__dict__.copy()
        # Backward compatibility for integrations built against v1.1.0.
        data["fixed_annual_bonus"] = data["sign_on_bonus"]
        return data


def progressive_tax(taxable_income: Decimal, brackets: list[Mapping[str, Any]]) -> Decimal:
    """Calculate progressive income tax from contiguous marginal brackets."""
    taxable_income = _d(taxable_income)
    if taxable_income <= 0:
        return Decimal("0")

    total = Decimal("0")
    for lower, upper, rate in _validated_brackets(brackets):
        if taxable_income <= lower:
            continue
        taxable_slice = taxable_income - lower
        if upper is not None:
            taxable_slice = min(taxable_slice, upper - lower)
        if taxable_slice > 0:
            total += taxable_slice * rate
    return total


def marginal_tax_rate(taxable_income: Decimal, brackets: list[Mapping[str, Any]]) -> Decimal:
    """Return the marginal rate applying to the final currency unit of chargeable income."""
    taxable_income = _d(taxable_income)
    if taxable_income <= 0:
        return Decimal("0")

    for lower, upper, rate in _validated_brackets(brackets):
        if taxable_income > lower and (upper is None or taxable_income <= upper):
            return rate
    return Decimal("0")  # Defensive; a validated final open bracket should always match.


def _tax_year(rule: Mapping[str, Any], scenario: Mapping[str, Any]) -> int:
    raw = rule.get("tax_year") if rule.get("tax_year") not in (None, "") else scenario.get("tax_year")
    try:
        year = int(raw)
    except (TypeError, ValueError) as exc:
        raise CalculationError("Tax year must be a whole number.") from exc
    if not 1900 <= year <= 2200:
        raise CalculationError("Tax year is outside the supported range.")
    return year


def _selected_contribution_rule(
    rule: Mapping[str, Any], scenario: Mapping[str, Any]
) -> tuple[Mapping[str, Any], str, str]:
    fallback = rule.get("contribution_rule") or {}
    if not isinstance(fallback, Mapping):
        raise CalculationError("Contribution rule is invalid.")
    profiles = rule.get("contribution_profiles") or []
    if not profiles:
        return fallback, "", str(fallback.get("scheme") or "Standard contribution profile")
    if not isinstance(profiles, list):
        raise CalculationError("Contribution profiles are invalid.")
    selected = str(
        scenario.get("contribution_profile") or rule.get("default_contribution_profile") or ""
    ).strip()
    for profile in profiles:
        if isinstance(profile, Mapping) and str(profile.get("id") or "") == selected:
            return profile, selected, str(profile.get("label") or selected)
    raise CalculationError("Select a valid contribution or pass profile for this tax rule.")


def _effective_contribution_rate(contribution_rule: Mapping[str, Any], key: str) -> Decimal:
    periods = contribution_rule.get("periods") or []
    if not periods:
        return _bounded_rate(contribution_rule.get(key, 0), key.replace("_", " ").title())
    weighted = Decimal("0")
    months_seen = 0
    for period in periods:
        if not isinstance(period, Mapping):
            raise CalculationError("Contribution profile period is invalid.")
        try:
            start = int(period.get("start_month"))
            end = int(period.get("end_month"))
        except (TypeError, ValueError) as exc:
            raise CalculationError("Contribution profile period months are invalid.") from exc
        month_count = end - start + 1
        if month_count <= 0:
            raise CalculationError("Contribution profile period is invalid.")
        weighted += _bounded_rate(period.get(key, 0), key.replace("_", " ").title()) * month_count
        months_seen += month_count
    if months_seen != 12:
        raise CalculationError("Contribution profile periods must cover all 12 months.")
    return weighted / Decimal("12")


def calculate_scenario(
    scenario: Mapping[str, Any],
    rule: Mapping[str, Any],
    fx_rate: float,
) -> ScenarioResult:
    """Calculate one scenario using a validated country/year rule."""
    if not isinstance(scenario, Mapping):
        raise CalculationError("Scenario must be a JSON object.")
    if not isinstance(rule, Mapping):
        raise CalculationError("Tax rule must be a JSON object.")

    monthly_base = _d(scenario.get("monthly_base"))
    monthly_allowance = _d(scenario.get("monthly_fixed_allowance"))
    guaranteed_bonus_months = _d(scenario.get("guaranteed_bonus_months"))
    sign_on_bonus = _d(scenario.get("sign_on_bonus", scenario.get("fixed_annual_bonus", 0)))
    variable_bonus_mode = str(scenario.get("variable_bonus_mode") or "").strip().casefold()
    if not variable_bonus_mode:
        variable_bonus_mode = "months" if scenario.get("variable_bonus_months") not in (None, "") else "percentage"
    if variable_bonus_mode not in {"percentage", "months"}:
        raise CalculationError("Variable bonus mode must be percentage or months.")

    variable_bonus_pct = Decimal("0")
    variable_bonus_months = Decimal("0")
    if variable_bonus_mode == "percentage":
        variable_bonus_pct = _bounded_rate(scenario.get("variable_bonus_pct", 0), "Variable bonus rate")
    else:
        variable_bonus_months = _d(scenario.get("variable_bonus_months", 0))
        if variable_bonus_months < 0:
            raise CalculationError("Variable bonus months cannot be negative.")
    other_taxable_income = _d(scenario.get("other_taxable_income"))
    personal_reliefs_allowed = _as_bool(rule.get("personal_reliefs_allowed"), True)
    personal_reliefs = _d(scenario.get("personal_tax_reliefs")) if personal_reliefs_allowed else Decimal("0")
    other_after_tax_deductions = _d(scenario.get("other_after_tax_deductions"))

    for field_name, value in {
        "Monthly base salary": monthly_base,
        "Monthly fixed allowance": monthly_allowance,
        "Guaranteed bonus months": guaranteed_bonus_months,
        "Sign-on bonus": sign_on_bonus,
        "Other taxable income": other_taxable_income,
        "Personal tax reliefs": personal_reliefs,
        "Other after-tax deductions": other_after_tax_deductions,
    }.items():
        if value < 0:
            raise CalculationError(f"{field_name} cannot be negative.")

    contribution_rule, contribution_profile, contribution_profile_label = _selected_contribution_rule(
        rule, scenario
    )
    employee_override = scenario.get("employee_contribution_rate_override")
    employer_override = scenario.get("employer_contribution_rate_override")
    cap_override = scenario.get("contribution_cap_override")

    employee_rate = _bounded_rate(
        _effective_contribution_rate(contribution_rule, "employee_rate")
        if employee_override in (None, "") else employee_override,
        "Employee contribution rate",
    )
    employer_rate = _bounded_rate(
        _effective_contribution_rate(contribution_rule, "employer_rate")
        if employer_override in (None, "") else employer_override,
        "Employer contribution rate",
    )

    annual_base = monthly_base * Decimal("12")
    annual_allowance = monthly_allowance * Decimal("12")
    guaranteed_bonus = monthly_base * guaranteed_bonus_months
    variable_bonus = (
        annual_base * variable_bonus_pct
        if variable_bonus_mode == "percentage"
        else monthly_base * variable_bonus_months
    )
    gross = (
        annual_base
        + annual_allowance
        + guaranteed_bonus
        + sign_on_bonus
        + variable_bonus
        + other_taxable_income
    )
    if gross > MAX_ABSOLUTE_NUMBER:
        raise CalculationError("Calculated annual gross is outside the supported range.")

    include_bonus = scenario.get("include_bonus_in_contribution_base")
    if include_bonus is None:
        include_bonus = _as_bool(contribution_rule.get("include_bonus"), True)
    else:
        include_bonus = _as_bool(include_bonus)

    contribution_base = gross if include_bonus else annual_base + annual_allowance
    cap_raw = contribution_rule.get("annual_cap") if cap_override in (None, "") else cap_override
    cap = None if cap_raw in (None, "") else _d(cap_raw)
    if cap is not None and cap < 0:
        raise CalculationError("Contribution cap cannot be negative.")
    contributable = contribution_base if cap is None else min(contribution_base, cap)

    employee_contribution = contributable * employee_rate
    employer_contribution = contributable * employer_rate

    deductible = _as_bool(contribution_rule.get("employee_contribution_tax_deductible"), False)
    taxable_income = gross - personal_reliefs - (employee_contribution if deductible else Decimal("0"))
    taxable_income = max(Decimal("0"), taxable_income)
    brackets = list(rule.get("tax_brackets") or [])
    estimated_tax = progressive_tax(taxable_income, brackets)
    marginal_rate = marginal_tax_rate(taxable_income, brackets)

    net_annual = gross - employee_contribution - estimated_tax - other_after_tax_deductions
    employer_cost = gross + employer_contribution

    # Same offer with the non-guaranteed variable performance bonus removed.
    # Recompute contributions and income tax from the reduced gross rather than
    # simply subtracting the bonus, so the "excluding variable bonus" net cash
    # reflects the tax and statutory contributions that the bonus itself drew.
    gross_ex_variable = gross - variable_bonus
    contribution_base_ex = gross_ex_variable if include_bonus else annual_base + annual_allowance
    contributable_ex = contribution_base_ex if cap is None else min(contribution_base_ex, cap)
    employee_contribution_ex = contributable_ex * employee_rate
    taxable_income_ex = max(
        Decimal("0"),
        gross_ex_variable - personal_reliefs - (employee_contribution_ex if deductible else Decimal("0")),
    )
    estimated_tax_ex = progressive_tax(taxable_income_ex, brackets)
    net_annual_ex_variable = (
        gross_ex_variable - employee_contribution_ex - estimated_tax_ex - other_after_tax_deductions
    )

    fx = _d(fx_rate)
    if fx <= 0:
        raise CalculationError("FX rate must be greater than zero.")

    effective_tax_rate = Decimal("0") if gross == 0 else estimated_tax / gross
    total_deduction_rate = (
        Decimal("0")
        if gross == 0
        else (employee_contribution + estimated_tax + other_after_tax_deductions) / gross
    )

    local_currency = str(rule.get("currency") or scenario.get("local_currency") or "").strip().upper()
    reporting_currency = str(scenario.get("reporting_currency") or local_currency).strip().upper()
    if len(local_currency) != 3 or not local_currency.isalpha():
        raise CalculationError("Local currency must be a three-letter code.")
    if len(reporting_currency) != 3 or not reporting_currency.isalpha():
        raise CalculationError("Reporting currency must be a three-letter code.")

    return ScenarioResult(
        country=str(rule.get("country") or scenario.get("country") or "").strip(),
        tax_year=_tax_year(rule, scenario),
        residency=str(rule.get("residency") or scenario.get("residency") or "Resident").strip(),
        local_currency=local_currency,
        reporting_currency=reporting_currency,
        fx_rate=_rate(fx),
        annual_base=_money(annual_base),
        annual_fixed_allowance=_money(annual_allowance),
        guaranteed_bonus=_money(guaranteed_bonus),
        sign_on_bonus=_money(sign_on_bonus),
        variable_bonus=_money(variable_bonus),
        other_taxable_income=_money(other_taxable_income),
        gross_annual_cash=_money(gross),
        gross_annual_cash_ex_variable=_money(gross_ex_variable),
        # Gross monthly reflects only fixed cash and fixed bonuses; the
        # non-guaranteed variable performance bonus is excluded because it is not
        # a dependable monthly figure.
        gross_monthly_cash=_money(gross_ex_variable / Decimal("12")),
        contribution_base=_money(contribution_base),
        employee_contribution_rate=_rate(employee_rate),
        employer_contribution_rate=_rate(employer_rate),
        employee_contribution=_money(employee_contribution),
        employer_contribution=_money(employer_contribution),
        taxable_income=_money(taxable_income),
        estimated_income_tax=_money(estimated_tax),
        marginal_income_tax_rate=_rate(marginal_rate),
        other_after_tax_deductions=_money(other_after_tax_deductions),
        net_annual_cash=_money(net_annual),
        net_annual_cash_ex_variable=_money(net_annual_ex_variable),
        net_monthly_cash=_money(net_annual / Decimal("12")),
        total_employer_cost=_money(employer_cost),
        effective_income_tax_rate=_rate(effective_tax_rate),
        total_employee_deduction_rate=_rate(total_deduction_rate),
        net_annual_reporting=_money(net_annual * fx),
        employer_cost_reporting=_money(employer_cost * fx),
        rule_metadata={
            "verified": _as_bool(rule.get("verified"), False),
            "tax_brackets_verified": _as_bool(
                rule.get("tax_brackets_verified"), _as_bool(rule.get("verified"), False)
            ),
            "contribution_rule_verified": _as_bool(
                rule.get("contribution_rule_verified"), _as_bool(rule.get("verified"), False)
            ),
            "tax_schedule_title": rule.get("tax_schedule_title"),
            "last_updated": rule.get("last_updated"),
            "source_urls": rule.get("source_urls") or [],
            "notes": rule.get("notes") or [],
            "scheme": contribution_rule.get("scheme"),
            "contribution_profile": contribution_profile,
            "contribution_profile_label": contribution_profile_label,
            "personal_reliefs_allowed": personal_reliefs_allowed,
        },
    )


def compare_results(a: ScenarioResult, b: ScenarioResult) -> dict[str, Any]:
    if a.reporting_currency.upper() != b.reporting_currency.upper():
        raise CalculationError("Both scenarios must use the same reporting currency.")

    net_difference = Decimal(str(b.net_annual_reporting)) - Decimal(str(a.net_annual_reporting))
    cost_difference = Decimal(str(b.employer_cost_reporting)) - Decimal(str(a.employer_cost_reporting))
    base_net = Decimal(str(a.net_annual_reporting))
    uplift = Decimal("0") if base_net == 0 else net_difference / base_net
    return {
        "reporting_currency": a.reporting_currency.upper(),
        "net_annual_difference": _money(net_difference),
        "employer_cost_difference": _money(cost_difference),
        "net_uplift_rate": _rate(uplift),
    }
