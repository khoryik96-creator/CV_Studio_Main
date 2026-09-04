"""Auto-correct spelling/punctuation/capitalization toggle for formatted CVs.

The toggle is an opt-in language-correction directive appended to the CV parse
system prompt. It must be off by default (base prompt unchanged), and when on it
must instruct correction of only spelling/punctuation/capitalization while
preserving names, technical terms, facts, and the JSON schema.
"""

import app
import cvstudio_storage


def test_parse_prompt_is_unchanged_by_default():
    assert app._parse_system_prompt() == app.SYSTEM_PROMPT
    assert app._parse_system_prompt(False) == app.SYSTEM_PROMPT
    # Anything other than an explicit True leaves the base prompt untouched.
    assert app._parse_system_prompt("true") == app.SYSTEM_PROMPT
    assert app._parse_system_prompt(None) == app.SYSTEM_PROMPT


def test_parse_prompt_appends_correction_directive_when_enabled():
    enabled = app._parse_system_prompt(True)
    assert enabled.startswith(app.SYSTEM_PROMPT)
    assert enabled != app.SYSTEM_PROMPT
    assert enabled.endswith(app.CV_LANGUAGE_CORRECTION_INSTRUCTION)


def test_correction_directive_states_scope_and_preservation():
    text = app.CV_LANGUAGE_CORRECTION_INSTRUCTION.lower()
    # Corrects the three things the user asked for.
    assert "spelling" in text
    assert "punctuation" in text
    assert "capitali" in text  # capitalization / capitalisation
    # Preserves identity/technical tokens and never rewrites meaning.
    for keep in ("proper noun", "acronym", "do not rewrite", "json"):
        assert keep in text, keep


def test_autocorrect_key_is_allowlisted_for_durable_storage():
    assert "cvstudio_autocorrect_language_v1" in cvstudio_storage.BROWSER_SETTING_KEYS
