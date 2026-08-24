from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest

from owner_build_tools.repo_consistency import BATCH_FILES


ROOT = Path(__file__).resolve().parents[1]
UPDATE_LAUNCHER = ROOT / "UPDATE.bat"


def _run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _write_batch(path: Path, lines: list[str]) -> None:
    path.write_bytes(("\r\n".join(lines) + "\r\n").encode("utf-8"))


def _make_windows_fixture(
    tmp_path: Path,
    *,
    branch: str = "launcher-test",
    stop_exit: int = 0,
    start_exit: int = 0,
) -> Path:
    git = shutil.which("git")
    assert git is not None

    source = tmp_path / "source"
    remote = tmp_path / "remote.git"
    source.mkdir()
    shutil.copy2(UPDATE_LAUNCHER, source / "UPDATE.bat")
    (source / "FORCE_STOP.ps1").write_text(
        f"param([string]$Root)\nexit {stop_exit}\n",
        encoding="utf-8",
    )
    _write_batch(
        source / "CV Studio.bat",
        [
            "@echo off",
            '> "%~dp0started.txt" echo started',
            f"exit /b {start_exit}",
        ],
    )

    _run([git, "init", "--bare", str(remote)], cwd=tmp_path)
    _run([git, "init"], cwd=source)
    _run([git, "config", "user.name", "CV Studio test"], cwd=source)
    _run([git, "config", "user.email", "test@example.invalid"], cwd=source)
    _run([git, "add", "UPDATE.bat", "FORCE_STOP.ps1", "CV Studio.bat"], cwd=source)
    _run([git, "commit", "-m", "launcher fixture"], cwd=source)
    _run([git, "checkout", "-b", branch], cwd=source)
    _run([git, "remote", "add", "origin", str(remote)], cwd=source)
    _run([git, "push", "-u", "origin", "HEAD"], cwd=source)
    return source


def _run_windows_launcher(source: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["cmd.exe", "/d", "/c", "UPDATE.bat"],
        cwd=source,
        input="\n",
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_update_launcher_hardening_source_contract() -> None:
    text = UPDATE_LAUNCHER.read_text(encoding="utf-8")
    assert "echo Current branch: %BRANCH%" not in text
    assert '"%GIT%" rev-parse --abbrev-ref HEAD' in text
    stop_call = text.index('powershell.exe -NoProfile -ExecutionPolicy Bypass -File')
    stop_result = text.index('set "STOP_RC=%ERRORLEVEL%"')
    stop_gate = text.index('if not "%STOP_RC%"=="0" goto :stop_failed')
    start_call = text.index('call "%~dp0CV Studio.bat"')
    assert stop_call < stop_result < stop_gate < start_call
    assert 'exit /b %ERRORLEVEL%' in text[start_call:]


def test_update_launcher_is_in_batch_byte_validation() -> None:
    assert "UPDATE.bat" in BATCH_FILES
    protected_builder = (ROOT / "owner_build_tools" / "build_protected.py").read_text(
        encoding="utf-8"
    )
    validation_start = protected_builder.index("def validate_repository_dependency_state")
    validation_end = protected_builder.index("def validate_source", validation_start)
    assert '"UPDATE.bat"' in protected_builder[validation_start:validation_end]


@pytest.mark.skipif(os.name != "nt", reason="Windows cmd.exe launcher behavior")
def test_update_launcher_does_not_execute_branch_name(tmp_path: Path) -> None:
    source = _make_windows_fixture(tmp_path, branch="safe&echo.BRANCH_INJECTION")
    result = _run_windows_launcher(source)
    lines = [line.strip() for line in result.stdout.splitlines()]
    assert result.returncode == 0, result.stdout + result.stderr
    assert "safe&echo.BRANCH_INJECTION" in lines
    assert "BRANCH_INJECTION" not in lines
    assert (source / "started.txt").is_file()


@pytest.mark.skipif(os.name != "nt", reason="Windows cmd.exe launcher behavior")
def test_update_launcher_does_not_start_after_stop_failure(tmp_path: Path) -> None:
    source = _make_windows_fixture(tmp_path, stop_exit=2)
    result = _run_windows_launcher(source)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "could not be stopped safely" in result.stdout
    assert not (source / "started.txt").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows cmd.exe launcher behavior")
def test_update_launcher_propagates_start_failure(tmp_path: Path) -> None:
    source = _make_windows_fixture(tmp_path, start_exit=13)
    result = _run_windows_launcher(source)
    assert result.returncode == 13, result.stdout + result.stderr
    assert (source / "started.txt").is_file()
