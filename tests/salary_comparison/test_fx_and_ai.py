import json

import pytest

from salary_comparison.ai_rule_updater import _extract_json, _call_claude, _call_deepseek
from salary_comparison.fx_service import FxService, FxServiceError


def test_fx_identity_is_exact(tmp_path):
    service = FxService(tmp_path / "fx.json")
    result = service.get_rate("MYR", "MYR")
    assert result["rate"] == 1.0
    assert result["source"] == "identity"


def test_fx_invalid_currency_rejected(tmp_path):
    service = FxService(tmp_path / "fx.json")
    with pytest.raises(FxServiceError):
        service.get_rate("RM", "USD")


def test_extract_json_plain_and_fenced():
    assert _extract_json('{"ok": true}') == {"ok": True}
    assert _extract_json('```json\n{"ok": true}\n```') == {"ok": True}
    assert _extract_json('Here: {"ok": true} done') == {"ok": True}


def test_deepseek_response_parser(monkeypatch):
    class Response:
        def raise_for_status(self): pass
        def json(self):
            return {
                "choices": [{"message": {"content": '{"country":"Malaysia"}'}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }
    monkeypatch.setattr("salary_comparison.ai_rule_updater.requests.post", lambda *a, **k: Response())
    body, usage = _call_deepseek("key", "model", "prompt")
    assert body["country"] == "Malaysia"
    assert usage == {"input_tokens": 10, "output_tokens": 5}


def test_claude_response_parser(monkeypatch):
    class Response:
        def raise_for_status(self): pass
        def json(self):
            return {
                "content": [{"type": "text", "text": '{"country":"Singapore"}'}],
                "usage": {"input_tokens": 12, "output_tokens": 6},
            }
    monkeypatch.setattr("salary_comparison.ai_rule_updater.requests.post", lambda *a, **k: Response())
    body, usage = _call_claude("key", "model", "prompt")
    assert body["country"] == "Singapore"
    assert usage == {"input_tokens": 12, "output_tokens": 6}

def test_fx_fetch_and_cache(monkeypatch, tmp_path):
    class Response:
        def raise_for_status(self): pass
        def json(self): return {"base": "SGD", "quote": "MYR", "rate": 3.2, "date": "2026-07-31"}
    monkeypatch.setattr("salary_comparison.fx_service.requests.get", lambda *a, **k: Response())
    service = FxService(tmp_path / "fx.json", max_age_hours=24)
    first = service.get_rate("SGD", "MYR")
    second = service.get_rate("SGD", "MYR")
    assert first["rate"] == 3.2
    assert first["cached"] is False
    assert second["rate"] == 3.2
    assert second["cached"] is True


def test_fx_stale_cache_fallback(monkeypatch, tmp_path):
    cache = tmp_path / "fx.json"
    cache.write_text('''{
      "rates": {
        "SGD/MYR": {
          "base": "SGD", "quote": "MYR", "rate": 3.1,
          "date": "2026-01-01", "source": "cached",
          "refreshed_at": "2026-01-01T00:00:00+00:00"
        }
      }
    }''', encoding="utf-8")
    def fail(*args, **kwargs):
        raise RuntimeError("offline")
    monkeypatch.setattr("salary_comparison.fx_service.requests.get", fail)
    result = FxService(cache, max_age_hours=1).get_rate("SGD", "MYR")
    assert result["rate"] == 3.1
    assert result["stale"] is True
