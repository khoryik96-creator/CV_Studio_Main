from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest

from owner_build_tools.repo_consistency import BATCH_FILES


ROOT = Path(__file__).resolve().parents[1]
UPDATE_LAUNCHER = ROOT / "UPDATE.bat"
SOURCE_LAUNCHER = ROOT / "CV Studio.bat"
UPDATE_PREFLIGHT = ROOT / "UPDATE_PREFLIGHT.ps1"


def _windows_tesseract_is_available() -> bool:
    candidates = [shutil.which("tesseract")]
    for variable in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        base = os.environ.get(variable)
        if base:
            suffix = (
                Path("Programs") / "Tesseract-OCR" / "tesseract.exe"
                if variable == "LOCALAPPDATA"
                else Path("Tesseract-OCR") / "tesseract.exe"
            )
            candidates.append(str(Path(base) / suffix))
    return any(candidate and Path(candidate).is_file() for candidate in candidates)


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
    preflight_exit: int = 0,
    stop_exit: int = 0,
    start_exit: int = 0,
) -> Path:
    git = shutil.which("git")
    assert git is not None

    source = tmp_path / "source"
    remote = tmp_path / "remote.git"
    source.mkdir()
    shutil.copy2(UPDATE_LAUNCHER, source / "UPDATE.bat")
    (source / "UPDATE_PREFLIGHT.ps1").write_text(
        f"param([string]$Root)\nexit {preflight_exit}\n",
        encoding="utf-8",
    )
    (source / "FORCE_STOP.ps1").write_text(
        f"param([string]$Root)\nSet-Content -LiteralPath (Join-Path $PSScriptRoot 'stopped.txt') -Value stopped\nexit {stop_exit}\n",
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
    _run(
        [git, "add", "UPDATE.bat", "UPDATE_PREFLIGHT.ps1", "FORCE_STOP.ps1", "CV Studio.bat"],
        cwd=source,
    )
    _run([git, "commit", "-m", "launcher fixture"], cwd=source)
    _run([git, "checkout", "-b", branch], cwd=source)
    _run([git, "remote", "add", "origin", str(remote)], cwd=source)
    _run([git, "push", "-u", "origin", "HEAD"], cwd=source)
    return source


def _run_windows_launcher(source: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["CVSTUDIO_UPDATE_STATE_DIR"] = str(source / "update-state")
    return subprocess.run(
        ["cmd.exe", "/d", "/c", "UPDATE.bat"],
        cwd=source,
        input="\n",
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )


def test_update_launcher_hardening_source_contract() -> None:
    text = UPDATE_LAUNCHER.read_text(encoding="utf-8")
    assert "echo Current branch: %BRANCH%" not in text
    assert '"%GIT%" rev-parse --abbrev-ref HEAD' in text
    stop_call = text.index('powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0FORCE_STOP.ps1"')
    stop_result = text.index('set "STOP_RC=%ERRORLEVEL%"')
    stop_gate = text.index('if not "%STOP_RC%"=="0" goto :stop_failed')
    preflight_call = text.index('powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0UPDATE_PREFLIGHT.ps1"')
    start_call = text.index('call "%~dp0CV Studio.bat" --wait')
    assert preflight_call < stop_call < stop_result < stop_gate < start_call
    assert 'set "START_RC=%ERRORLEVEL%"' in text[start_call:]
    assert 'exit /b %START_RC%' in text[start_call:]
    assert "Previous source commit:" in text
    assert "source_update.log" in text

    source_launcher = SOURCE_LAUNCHER.read_text(encoding="utf-8")
    assert 'if /i "%~1"=="--wait" goto :wait_for_start' in source_launcher
    assert 'cscript.exe //nologo "%~dp0START_HIDDEN.vbs"' in source_launcher


def test_update_launcher_is_in_batch_byte_validation() -> None:
    assert "UPDATE.bat" in BATCH_FILES
    protected_builder = (ROOT / "owner_build_tools" / "build_protected.py").read_text(
        encoding="utf-8"
    )
    validation_start = protected_builder.index("def validate_repository_dependency_state")
    validation_end = protected_builder.index("def validate_source", validation_start)
    validation = protected_builder[validation_start:validation_end]
    assert "for rel in REPOSITORY_BATCH_FILES" in validation
    assert "batch_files =" not in validation


def test_update_preflight_preserves_single_executable_candidates_as_arrays() -> None:
    text = UPDATE_PREFLIGHT.read_text(encoding="utf-8")
    for variable in ("nodeCandidates", "pythonCandidates", "tesseractCandidates"):
        assignment = text.index(f"${variable} = @(")
        first_candidate = text.index("@(", assignment + len(f"${variable} = @("))
        count_gate = text.index(f"if (${variable}.Count -eq 0)", assignment)
        assert assignment < first_candidate < count_gate


@pytest.mark.skipif(
    os.name != "nt" or shutil.which("node") is None or not _windows_tesseract_is_available(),
    reason="Windows Node/Tesseract updater preflight",
)
def test_real_update_preflight_accepts_single_system_runtime_candidates(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    shutil.copy2(UPDATE_PREFLIGHT, source / "UPDATE_PREFLIGHT.ps1")
    for name in (
        "CV Studio.bat",
        "START_HIDDEN.vbs",
        "FORCE_STOP.ps1",
        "requirements.txt",
    ):
        (source / name).write_text("fixture\n", encoding="utf-8")
    (source / "package.json").write_text("{}\n", encoding="utf-8")
    (source / "INSTALL_RECEIPT.ps1").write_text("exit 0\n", encoding="utf-8")
    native = source / "runtime" / "native"
    native.mkdir(parents=True)
    (native / "CVStudio.exe").write_bytes(b"fixture")
    shutil.copytree(
        ROOT / "node_modules" / "adm-zip",
        source / "node_modules" / "adm-zip",
    )

    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(source / "UPDATE_PREFLIGHT.ps1"),
            "-Root",
            str(source),
        ],
        cwd=source,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Update preflight passed" in result.stdout


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
    assert (source / "stopped.txt").is_file()
    assert not (source / "started.txt").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows cmd.exe launcher behavior")
def test_update_launcher_leaves_server_untouched_after_preflight_failure(tmp_path: Path) -> None:
    source = _make_windows_fixture(tmp_path, preflight_exit=8)
    result = _run_windows_launcher(source)
    assert result.returncode == 8, result.stdout + result.stderr
    assert "current CV Studio server was left untouched" in result.stdout
    assert not (source / "stopped.txt").exists()
    assert not (source / "started.txt").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows cmd.exe launcher behavior")
def test_update_launcher_propagates_start_failure(tmp_path: Path) -> None:
    source = _make_windows_fixture(tmp_path, start_exit=13)
    result = _run_windows_launcher(source)
    assert result.returncode == 13, result.stdout + result.stderr
    assert (source / "started.txt").is_file()
