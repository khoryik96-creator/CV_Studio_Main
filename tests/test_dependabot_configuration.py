from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / ".github" / "dependabot.yml"


def test_dependabot_updates_python_and_actions_weekly() -> None:
    text = CONFIG.read_text(encoding="utf-8")
    assert text.startswith("version: 2\n")
    assert text.count('package-ecosystem: "pip"') == 1
    assert text.count('package-ecosystem: "github-actions"') == 1
    assert text.count('interval: "weekly"') == 2
    assert text.count('timezone: "Asia/Kuala_Lumpur"') == 2
    assert 'applies-to: "version-updates"' in text


def test_dependabot_does_not_auto_bump_owner_vetted_adm_zip() -> None:
    text = CONFIG.read_text(encoding="utf-8")
    assert 'package-ecosystem: "npm"' not in text
    assert "adm-zip is pinned to 0.6.0" in text
