from __future__ import annotations

from pathlib import Path
import re

from owner_build_tools import build_protected


ROOT = Path(__file__).resolve().parents[1]


def _assert_action_is_immutably_pinned(workflow: str, action: str, count: int) -> None:
    pins = re.findall(
        rf"{re.escape(action)}@[0-9a-f]{{40}}\s+#\s+v\d+(?:\.\d+){{0,2}}",
        workflow,
    )
    assert len(pins) == count
    assert re.search(rf"{re.escape(action)}@(?![0-9a-f]{{40}})", workflow) is None


def test_regression_ci_runs_on_pull_requests_and_merged_master() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "push:\n    branches:\n      - master" in workflow
    assert "pull_request:\n    branches:\n      - master" in workflow
    _assert_action_is_immutably_pinned(workflow, "actions/checkout", 2)
    _assert_action_is_immutably_pinned(workflow, "actions/setup-python", 2)
    _assert_action_is_immutably_pinned(workflow, "actions/setup-node", 1)


def test_protected_build_is_manual_only_and_uses_live_version() -> None:
    workflow = (ROOT / ".github" / "workflows" / "build-protected.yml").read_text(
        encoding="utf-8"
    )
    assert "pull_request:" not in workflow
    assert "workflow_dispatch:" in workflow
    assert "group: cv-studio-protected-${{ github.ref }}" in workflow
    assert "cancel-in-progress: true" in workflow
    assert "timeout-minutes: 150" in workflow
    assert build_protected.NATIVE_COMPILE_TIMEOUT_SECONDS == 7200
    assert "timeout=NATIVE_COMPILE_TIMEOUT_SECONDS" in Path(
        build_protected.__file__
    ).read_text(encoding="utf-8")
    _assert_action_is_immutably_pinned(workflow, "actions/checkout", 1)
    _assert_action_is_immutably_pinned(workflow, "actions/setup-python", 1)
    _assert_action_is_immutably_pinned(workflow, "actions/setup-node", 1)
    _assert_action_is_immutably_pinned(workflow, "actions/upload-artifact", 2)
    assert "id: package-version" in workflow
    assert "steps.package-version.outputs.value" in workflow
    assert "cv-studio-v24.6.246" not in workflow
