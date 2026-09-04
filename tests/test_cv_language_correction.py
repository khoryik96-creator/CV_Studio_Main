"""Auto-correct spelling/punctuation/capitalization toggle for formatted CVs.

The base parse prompt already contains a light "fix spelling/typos silently"
line. When the user enables the toggle, that single line is REPLACED with a
fuller, self-consistent language-correction directive (spelling + punctuation +
capitalization + known product-name casing, with names/facts preserved) -- never
appended as a second, conflicting rule. Off is the base prompt unchanged.
"""

import app
import cvstudio_storage


def test_base_prompt_still_carries_the_replace_anchor():
    # The ON path replaces this exact line; if the base prompt is reworded this
    # test flags that the anchor (and _parse_system_prompt) must be updated.
    assert app._CV_BASE_TEXT_INSTRUCTION in app.SYSTEM_PROMPT


def test_parse_prompt_is_unchanged_when_disabled():
    assert app._parse_system_prompt() == app.SYSTEM_PROMPT
    assert app._parse_system_prompt(False) == app.SYSTEM_PROMPT
    # Only an explicit True enables correction.
    assert app._parse_system_prompt("true") == app.SYSTEM_PROMPT
    assert app._parse_system_prompt(None) == app.SYSTEM_PROMPT


def test_enabled_prompt_replaces_the_blanket_line_without_contradiction():
    enabled = app._parse_system_prompt(True)
    assert enabled != app.SYSTEM_PROMPT
    # The contradictory blanket "fix spelling/typos silently, preserve everything
    # else" line is gone -- replaced, not appended alongside.
    assert app._CV_BASE_TEXT_INSTRUCTION not in enabled
    assert app.CV_LANGUAGE_CORRECTION_INSTRUCTION in enabled
    # It must not have grown a second copy of the correction directive.
    assert enabled.count("correct spelling, punctuation, and capitalization") == 1


def test_directive_states_scope_casing_and_preservation():
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
