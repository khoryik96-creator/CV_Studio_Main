from __future__ import annotations

import importlib.util
import sys
import types
from io import BytesIO
from pathlib import Path


def _load_routes_with_fake_flask(monkeypatch):
    class FakeBlueprint:
        def __init__(self, *args, **kwargs):
            pass

        def get(self, *args, **kwargs):
            return lambda function: function

        def post(self, *args, **kwargs):
            return lambda function: function

        def errorhandler(self, *args, **kwargs):
            return lambda function: function

    fake_request = types.SimpleNamespace(get_json=lambda force=True: {})
    fake_app = types.SimpleNamespace(config={}, logger=types.SimpleNamespace(exception=lambda *args, **kwargs: None))

    def fake_send_file(file_object, **kwargs):
        return {
            "content": file_object.read(),
            "mimetype": kwargs["mimetype"],
            "download_name": kwargs["download_name"],
            "as_attachment": kwargs["as_attachment"],
        }

    fake_flask = types.ModuleType("flask")
    fake_flask.Blueprint = FakeBlueprint
    fake_flask.current_app = fake_app
    fake_flask.jsonify = lambda value: value
    fake_flask.render_template = lambda *args, **kwargs: "rendered"
    fake_flask.request = fake_request
    fake_flask.send_file = fake_send_file
    monkeypatch.setitem(sys.modules, "flask", fake_flask)

    route_path = Path(__file__).resolve().parents[2] / "salary_comparison" / "routes.py"
    module_name = "salary_comparison._routes_export_simulated"
    spec = importlib.util.spec_from_file_location(module_name, route_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module, fake_request


def _stub_calculation():
    scenario_a = {"name": "Current / Role"}
    scenario_b = {"name": "Offer: Singapore"}
    response = {
        "scenario_a": {},
        "scenario_b": {},
        "comparison": {},
        "fx": {},
    }
    return scenario_a, scenario_b, response


def test_simulated_pdf_export_route(monkeypatch):
    routes, fake_request = _load_routes_with_fake_flask(monkeypatch)
    fake_request.get_json = lambda force=True: {"scenario_a": {}, "scenario_b": {}}
    monkeypatch.setattr(routes, "_calculate_comparison", lambda payload: _stub_calculation())
    monkeypatch.setattr(routes, "build_pdf_report", lambda *args: b"%PDF-test")
    result = routes.export_api("pdf")
    assert result["content"] == b"%PDF-test"
    assert result["mimetype"] == "application/pdf"
    assert result["download_name"].endswith(".pdf")
    assert "/" not in result["download_name"]


def test_simulated_excel_export_route(monkeypatch):
    routes, fake_request = _load_routes_with_fake_flask(monkeypatch)
    fake_request.get_json = lambda force=True: {"scenario_a": {}, "scenario_b": {}}
    monkeypatch.setattr(routes, "_calculate_comparison", lambda payload: _stub_calculation())
    monkeypatch.setattr(routes, "build_xlsx_report", lambda *args: b"PK-test")
    result = routes.export_api("excel")
    assert result["content"] == b"PK-test"
    assert result["mimetype"].endswith("spreadsheetml.sheet")
    assert result["download_name"].endswith(".xlsx")


def test_simulated_export_route_rejects_unknown_format(monkeypatch):
    routes, fake_request = _load_routes_with_fake_flask(monkeypatch)
    fake_request.get_json = lambda force=True: {"scenario_a": {}, "scenario_b": {}}
    monkeypatch.setattr(routes, "_calculate_comparison", lambda payload: _stub_calculation())
    response, status = routes.export_api("csv")
    assert status == 400
    assert "PDF or Excel" in response["error"]
