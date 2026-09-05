"""Auto-correct spelling/punctuation/capitalization toggle for formatted CVs.

The base parse prompt already contains a light "fix spelling/typos silently"
line. When the user enables the toggle, that single line is REPLACED with a
fuller, self-consistent language-correction directive (spelling + punctuation +
capitalization + known product-name casing, with names/facts preserved) -- never
appended as a second, conflicting rule. Off is the base prompt unchanged.
"""

import importlib
import json
import os
from pathlib import Path

import pytest

import cvstudio_storage


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    # Standalone runs must never depend on another test creating authorization
    # or use the owner's installed receipt, credentials or durable data.
    from owner_build_tools import build_protected

    state = tmp_path_factory.mktemp("language-correction")
    with pytest.MonkeyPatch.context() as env:
        env.setenv("LOCALAPPDATA", str(state / "local"))
        env.setenv("CVSTUDIO_DB_PATH", str(state / "state.sqlite3"))
        env.setenv("CVSTUDIO_STATE_DIR", str(state / "state"))
        env.setenv("CVSTUDIO_JOB_STATE_PATH", str(state / "jobs.json"))
        env.setenv("SALARY_COMPARISON_DATA_DIR", str(state / "salary"))
        build_protected.write_test_receipt(Path(__file__).resolve().parents[1], os.environ)
        yield importlib.import_module("app")


def test_base_prompt_still_carries_the_replace_anchor(app):
    # The ON path replaces this exact line; if the base prompt is reworded this
    # test flags that the anchor (and _parse_system_prompt) must be updated.
    assert app._CV_BASE_TEXT_INSTRUCTION in app.SYSTEM_PROMPT


def test_parse_prompt_is_unchanged_when_disabled(app):
    assert app._parse_system_prompt() == app.SYSTEM_PROMPT
    assert app._parse_system_prompt(False) == app.SYSTEM_PROMPT
    # Only an explicit True enables correction.
    assert app._parse_system_prompt("true") == app.SYSTEM_PROMPT
    assert app._parse_system_prompt(None) == app.SYSTEM_PROMPT


def test_enabled_prompt_replaces_the_blanket_line_without_contradiction(app):
    enabled = app._parse_system_prompt(True)
    assert enabled != app.SYSTEM_PROMPT
    # The contradictory blanket "fix spelling/typos silently, preserve everything
    # else" line is gone -- replaced, not appended alongside.
    assert app._CV_BASE_TEXT_INSTRUCTION not in enabled
    assert app.CV_LANGUAGE_CORRECTION_INSTRUCTION in enabled
    # It must not have grown a second copy of the correction directive.
    assert enabled.count("correct spelling, punctuation, and capitalization") == 1


def test_directive_states_scope_casing_and_preservation(app):
    text = app.CV_LANGUAGE_CORRECTION_INSTRUCTION.lower()
    for token in ("spelling", "punctuation", "capitali"):
        assert token in text, token
    # Normalises well-known product/tech name casing (the Kafka case).
    assert "kafka -> kafka" in text
    # Preserves people's names and never changes meaning/facts.
    assert "preserve people's names" in text
    assert "do not" in text and "meaning" in text


def test_autocorrect_key_is_allowlisted_for_durable_storage():
    assert "cvstudio_autocorrect_language_v1" in cvstudio_storage.BROWSER_SETTING_KEYS


@pytest.mark.parametrize("flag", [True, False, None, "true", 1])
@pytest.mark.parametrize("attempts", [1, 2, 3])
def test_route_applies_language_preference_to_each_attempt(app, monkeypatch, flag, attempts):
    calls = []
    candidate = {"name": "Example Candidate"}
    valid = json.dumps({"candidate": candidate, "work_experiences": [],
                        "education": [], "certifications": [], "skills": []})

    def fake_call(provider, key, payload):
        calls.append(payload)
        # A blank initial response cannot be bracket-salvaged. For the third
        # strategy it also permits the returned continuation to be complete JSON.
        text = valid if len(calls) == attempts else ""
        return {"content": [{"type": "text", "text": text}], "usage": {}}

    monkeypatch.setattr(app, "call_llm", fake_call)
    monkeypatch.setattr(app, "_ai_spend_session_allowed", lambda *a, **k: True)
    monkeypatch.setattr(app, "_resolve_request_api_key", lambda *a, **k: "fixture-key")
    response = app.app.test_client().post("/parse", json={
        "cv_text": "Example Candidate\nBuilt kafka APIs; reduced cost by 3.5% in 2025.",
        "auto_correct_language": flag,
    }, headers={"Origin": "http://127.0.0.1:5000", "X-CV-Studio-Request": "1"})
    assert response.status_code == 200, response.get_json()
    assert len(calls) == attempts
    for index, payload in enumerate(calls):
        if flag is True:
            assert payload["system"] == app._parse_system_prompt(True)
            assert app._CV_BASE_TEXT_INSTRUCTION not in payload["system"]
        elif index < 2:
            assert payload["system"] == app.SYSTEM_PROMPT
        else:
            assert "system" not in payload  # preserve the existing OFF continuation
        source = payload["messages"][0]["content"]
        assert "3.5% in 2025" in source
        assert "Example Candidate" in source
    assert response.get_json()["data"]["candidate"]["name"] == candidate["name"]
