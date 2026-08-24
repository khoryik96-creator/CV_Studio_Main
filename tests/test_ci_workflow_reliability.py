from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_regression_ci_runs_on_pull_requests_and_merged_master() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "push:\n    branches:\n      - master" in workflow
    assert "pull_request:\n    branches:\n      - master" in workflow
    assert workflow.count("actions/checkout@v7") == 2
    assert workflow.count("actions/setup-python@v7") == 2
    assert workflow.count("actions/setup-node@v7") == 1
    assert "actions/checkout@v4" not in workflow
    assert "actions/setup-python@v5" not in workflow
    assert "actions/setup-node@v4" not in workflow


def test_protected_build_runs_for_packaging_changes_and_uses_live_version() -> None:
    workflow = (ROOT / ".github" / "workflows" / "build-protected.yml").read_text(
        encoding="utf-8"
    )
    assert "pull_request:\n    branches:\n      - master\n    paths:" in workflow
    assert '      - "owner_build_tools/**"' in workflow
    assert '      - ".github/workflows/build-protected.yml"' in workflow
    assert '      - "UPDATE*.bat"' in workflow
    assert '      - "UPDATE*.ps1"' in workflow
    assert "actions/checkout@v7" in workflow
    assert "actions/setup-python@v7" in workflow
    assert "actions/setup-node@v7" in workflow
    assert workflow.count("actions/upload-artifact@v7") == 2
    assert "id: package-version" in workflow
    assert "steps.package-version.outputs.value" in workflow
    assert "cv-studio-v24.6.246" not in workflow
