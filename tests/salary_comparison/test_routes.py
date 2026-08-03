
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
    assert b"Export Word" in response.data
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


def test_compare_endpoint(client):
    response = client.post("/salary-comparison/api/compare", json={
        "scenario_a": scenario("Malaysia", "MYR", 12000, 500, 9000),
        "scenario_b": scenario("Singapore", "MYR", 9000, 600, 0),
    })
    data = response.get_json()
    assert response.status_code == 200
    assert data["scenario_a"]["local_currency"] == "MYR"
    assert data["scenario_b"]["local_currency"] == "SGD"
    assert data["scenario_a"]["gross_monthly_cash"] == 14700
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


def test_export_word_endpoint(client):
    response = client.post("/salary-comparison/api/export/word", json={
        "scenario_a": scenario("Malaysia", "MYR", 12000, 500, 9000),
        "scenario_b": scenario("Singapore", "MYR", 9000, 600, 0),
    })
    assert response.status_code == 200
    assert response.mimetype == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert response.data.startswith(b"PK")
    assert "attachment" in response.headers["Content-Disposition"]


def test_export_rejects_unknown_format(client):
    response = client.post("/salary-comparison/api/export/xlsx", json={
        "scenario_a": scenario("Malaysia", "MYR", 12000, 500, 9000),
        "scenario_b": scenario("Singapore", "MYR", 9000, 600, 0),
    })
    assert response.status_code == 400
    assert "PDF or Word" in response.get_json()["error"]


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
