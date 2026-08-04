from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JS = ROOT / "salary_comparison/static/salary_comparison/salary-comparison.js"
HTML = ROOT / "salary_comparison/templates/salary_comparison/index.html"
CSS = ROOT / "salary_comparison/static/salary_comparison/salary-comparison.css"


def test_javascript_syntax_with_node():
    result = subprocess.run(["node", "--check", str(JS)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_browser_has_stale_request_protection_and_finite_validation():
    text = JS.read_text(encoding="utf-8")
    assert "AbortController" in text
    assert "calculationSequence" in text
    assert "Number.isFinite" in text
    assert "clearCalculatedDisplay" in text


def test_all_literal_dom_ids_referenced_by_js_exist_in_template():
    js = JS.read_text(encoding="utf-8")
    html = HTML.read_text(encoding="utf-8")
    referenced = set(re.findall(r'\bel\("([A-Za-z0-9_-]+)"\)', js))
    present = set(re.findall(r'\bid="([A-Za-z0-9_-]+)"', html))
    missing = sorted(referenced - present)
    assert not missing, missing


def test_required_export_and_bonus_controls_exist():
    html = HTML.read_text(encoding="utf-8")
    for text in [
        "Export PDF", "Export Excel", "Sign-On Bonus", "Percentage of annual base",
        "Months of monthly base", "Gross monthly", "Net monthly", "Total Gross plus Employer EPF",
    ]:
        assert text in html


def test_reset_and_clear_controls_exist():
    html = HTML.read_text(encoding="utf-8")
    assert 'id="resetButton"' in html
    assert 'id="clearButton"' in html
    assert "Clear all" in html


def test_inputs_persist_across_reload_via_local_storage():
    js = JS.read_text(encoding="utf-8")
    # The last entered inputs are remembered so a reload does not snap back to
    # the sample defaults, and can be wiped by the Clear all control.
    assert "INPUT_STORAGE_KEY" in js
    assert "restoreInputs" in js
    assert "saveInputs" in js
    assert "clearInputs" in js
    assert "localStorage.setItem(INPUT_STORAGE_KEY" in js


def test_css_has_responsive_and_loading_states():
    css = CSS.read_text(encoding="utf-8")
    assert "@media" in css
    assert ".loading" in css
    assert ".button:disabled" in css


