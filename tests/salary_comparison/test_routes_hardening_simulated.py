from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest


def load_routes(monkeypatch, json_value=None):
    class FakeBlueprint:
        def __init__(self, *args, **kwargs): pass
        def get(self, *args, **kwargs): return lambda fn: fn
        def post(self, *args, **kwargs): return lambda fn: fn
        def errorhandler(self, *args, **kwargs): return lambda fn: fn

    class Request:
        headers = {}
        def get_json(self, silent=False, force=False):
            return json_value

    fake_request = Request()
    fake_app = types.SimpleNamespace(config={}, logger=types.SimpleNamespace(exception=lambda *args, **kwargs: None))
    fake_flask = types.ModuleType("flask")
    fake_flask.Blueprint = FakeBlueprint
    fake_flask.current_app = fake_app
    fake_flask.jsonify = lambda value: value
    fake_flask.render_template = lambda *args, **kwargs: "rendered"
    fake_flask.request = fake_request
    fake_flask.send_file = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "flask", fake_flask)

    path = Path(__file__).resolve().parents[2] / "salary_comparison/routes.py"
    name = "salary_comparison._routes_hardening_simulated"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader
    spec.loader.exec_module(module)
    return module, fake_request, fake_app


def test_json_object_rejects_missing_json(monkeypatch):
    routes, _, _ = load_routes(monkeypatch, None)
    with pytest.raises(routes.CalculationError, match="valid JSON"):
        routes._json_object()


def test_json_object_rejects_array(monkeypatch):
    routes, _, _ = load_routes(monkeypatch, [])
    with pytest.raises(routes.CalculationError, match="JSON object"):
        routes._json_object()


def test_refresh_string_false_is_false(monkeypatch):
    routes, _, _ = load_routes(monkeypatch, {})
    assert routes._request_bool("false", "refresh") is False
    assert routes._request_bool("true", "refresh") is True
    with pytest.raises(routes.CalculationError):
        routes._request_bool("maybe", "refresh")


def test_admin_token_uses_exact_match(monkeypatch):
    routes, request, app = load_routes(monkeypatch, {})
    app.config["SALARY_COMPARISON_ADMIN_TOKEN"] = "secret"
    request.headers = {"X-Salary-Admin-Token": "secret"}
    assert routes._admin_allowed() is True
    request.headers = {"X-Salary-Admin-Token": "SECRET"}
    assert routes._admin_allowed() is False


def test_calculate_rejects_missing_scenarios(monkeypatch):
    routes, _, _ = load_routes(monkeypatch, {})
    with pytest.raises(routes.CalculationError, match="scenario_a"):
        routes._calculate_comparison({})


def test_scenario_rejects_bad_tax_year_before_repository(monkeypatch):
    routes, _, _ = load_routes(monkeypatch, {})
    with pytest.raises(routes.CalculationError, match="Tax year"):
        routes._scenario_with_fx({"country": "Malaysia", "tax_year": None})
