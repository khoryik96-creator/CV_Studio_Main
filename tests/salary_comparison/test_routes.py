
def scenario(country, reporting, base, allowance=0, reliefs=0):
    return {
        "country": country,
        "tax_year": 2025,
        "residency": "Resident",
        "monthly_base": base,
        "monthly_fixed_allowance": allowance,
        "guaranteed_bonus_months": 1,
        "sign_on_bonus": 0,
        "variable_bonus_mode": "percentage",
        "variable_bonus_pct": 0.10,
        "other_taxable_income": 0,
        "personal_tax_reliefs": reliefs,
        "other_after_tax_deductions": 0,
        "include_bonus_in_contribution_base": True,
        "reporting_currency": reporting,
        "fx_rate_override": 1,
    }


def test_index_loads(client):
    response = client.get("/salary-comparison/")
    assert response.status_code == 200
    assert b"International Salary Comparison" in response.data
    assert b"Tax rule updater" in response.data
    assert b"Export PDF" in response.data
    assert b"Export Excel" in response.data
    assert b"Sign-On Bonus" in response.data
    assert b"Percentage of annual base" in response.data
    assert b"Months of monthly base" in response.data
    assert b"Total Gross plus Employer EPF" in response.data
    assert b"Gross monthly" in response.data
    assert b"Marginal tax rate" in response.data


def test_standalone_index_prompts_for_one_time_key(client):
    # Without a host key resolver the page must keep its own one-time key field.
    response = client.get("/salary-comparison/")
    html = response.get_data(as_text=True)
    assert "window.SALARY_HOST_MANAGED = false" in html
    assert 'id="rule_api_key" type="password"' in html


def test_config_lists_countries_and_rules(client):
    response = client.get("/salary-comparison/api/config")
    data = response.get_json()
    assert response.status_code == 200
    assert any(item["country"] == "Malaysia" for item in data["countries"])
    assert 2025 in data["years_by_country"]["Malaysia"]
    assert "Non-Resident" in data["residency_profiles"]
    malaysia_nonresident = next(
        rule for rule in data["rules"]
        if rule["country"] == "Malaysia" and rule["residency"] == "Non-Resident"
    )
    assert malaysia_nonresident["personal_reliefs_allowed"] is False
    assert {profile["id"] for profile in malaysia_nonresident["contribution_profiles"]} >= {
        "employment_pass", "residence_pass_talent", "permanent_resident", "spousal_visa",
    }
    assert data["official_rule_sources"]["malaysia"]["tax_url"] == (
        "https://www.hasil.gov.my/wp-content/uploads/navigasi-hasil-2026.pdf"
    )


def test_compare_endpoint(client):
    response = client.post("/salary-comparison/api/compare", json={
        "scenario_a": scenario("Malaysia", "MYR", 12000, 500, 9000),
        "scenario_b": scenario("Singapore", "MYR", 9000, 600, 0),
    })
    data = response.get_json()
    assert response.status_code == 200
    assert data["scenario_a"]["local_currency"] == "MYR"
    assert data["scenario_b"]["local_currency"] == "SGD"
    assert data["scenario_a"]["gross_monthly_cash"] == 13500
    assert data["scenario_a"]["marginal_income_tax_rate"] == 0.25
    assert data["comparison"]["reporting_currency"] == "MYR"


def test_export_pdf_endpoint(client):
    response = client.post("/salary-comparison/api/export/pdf", json={
        "scenario_a": scenario("Malaysia", "MYR", 12000, 500, 9000),
        "scenario_b": scenario("Singapore", "MYR", 9000, 600, 0),
    })
    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF")
    assert "attachment" in response.headers["Content-Disposition"]


def test_export_excel_endpoint(client):
    response = client.post("/salary-comparison/api/export/excel", json={
        "scenario_a": scenario("Malaysia", "MYR", 12000, 500, 9000),
        "scenario_b": scenario("Singapore", "MYR", 9000, 600, 0),
    })
    assert response.status_code == 200
    assert response.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert response.data.startswith(b"PK")
    assert response.headers["Content-Disposition"].endswith('.xlsx"') or ".xlsx" in response.headers["Content-Disposition"]
    assert "attachment" in response.headers["Content-Disposition"]


def test_export_rejects_unknown_format(client):
    response = client.post("/salary-comparison/api/export/csv", json={
        "scenario_a": scenario("Malaysia", "MYR", 12000, 500, 9000),
        "scenario_b": scenario("Singapore", "MYR", 9000, 600, 0),
    })
    assert response.status_code == 400
    assert "PDF or Excel" in response.get_json()["error"]


def test_compare_missing_rule_returns_clear_error(client):
    response = client.post("/salary-comparison/api/compare", json={
        "scenario_a": scenario("Japan", "JPY", 100000),
        "scenario_b": scenario("Malaysia", "JPY", 12000),
    })
    assert response.status_code == 400
    assert "No rules for Japan" in response.get_json()["error"]


def test_publish_requires_admin_token_when_configured(app):
    app.config["SALARY_COMPARISON_ADMIN_TOKEN"] = "secret"
    client = app.test_client()
    response = client.post("/salary-comparison/api/rules/publish", json={"rule": {}})
    assert response.status_code == 403


def test_unwritable_data_dir_returns_clean_handled_error(tmp_path):
    # A data directory that cannot be seeded must surface a clear 400, not an
    # opaque 500 "Unexpected salary-comparison error."
    from flask import Flask
    import salary_comparison

    blocked_parent = tmp_path / "not-a-directory"
    blocked_parent.write_text("fixture", encoding="utf-8")
    application = Flask(__name__)
    application.config.update(
        TESTING=True,
        SALARY_COMPARISON_DATA_DIR=str(blocked_parent / "cannot-create-here"),
    )
    salary_comparison.init_app(application, url_prefix="/salary-comparison")
    response = application.test_client().get("/salary-comparison/api/config")
    assert response.status_code == 400
    payload = response.get_json()
    assert payload["type"] == "RuleRepositoryError"
    assert "data directory" in payload["error"].lower()


def test_unexpected_error_response_is_diagnosable(client, monkeypatch):
    # An unexpected (unhandled) exception must report its type and detail so the
    # actual failure is visible instead of only the generic message.
    from salary_comparison import routes as sc_routes

    def boom():
        raise RuntimeError("synthetic failure for diagnostics")

    monkeypatch.setattr(sc_routes, "_country_map", boom)
    response = client.get("/salary-comparison/api/config")
    assert response.status_code == 500
    payload = response.get_json()
    assert payload["error"] == "Unexpected salary-comparison error."
    assert payload["type"] == "RuntimeError"
    assert "synthetic failure for diagnostics" in payload["detail"]
