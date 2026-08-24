from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from owner_build_tools.repo_consistency import BATCH_FILES


ROOT = Path(__file__).resolve().parents[1]
UPDATE_LAUNCHER = ROOT / "UPDATE.bat"
UPDATE_CORE = ROOT / "UPDATE_CORE.ps1"
SOURCE_LAUNCHER = ROOT / "CV Studio.bat"
UPDATE_PREFLIGHT = ROOT / "UPDATE_PREFLIGHT.ps1"
PYTHON_RUNTIME = ROOT / "PYTHON_RUNTIME.ps1"


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
    branch: str = "master",
    preflight_exit: int = 0,
    stop_exit: int = 0,
    start_exit: int = 0,
) -> Path:
    git = shutil.which("git")
    assert git is not None

    source = tmp_path / "CV Studio source"
    remote = tmp_path / "remote.git"
    source.mkdir()
    shutil.copy2(UPDATE_LAUNCHER, source / "UPDATE.bat")
    shutil.copy2(UPDATE_CORE, source / "UPDATE_CORE.ps1")
    (source / "UPDATE_PREFLIGHT.ps1").write_text(
        "param([string]$Root = $PSScriptRoot)\n"
        "try { $Root = [IO.Path]::GetFullPath($Root).TrimEnd('\\','/') } "
        "catch { exit 2 }\n"
        "if (-not (Test-Path -LiteralPath (Join-Path $Root 'CV Studio.bat'))) { exit 2 }\n"
        f"exit {preflight_exit}\n",
        encoding="utf-8",
    )
    (source / "FORCE_STOP.ps1").write_text(
        f"param([string]$Root = $PSScriptRoot)\nSet-Content -LiteralPath (Join-Path $Root 'stopped.txt') -Value stopped\nexit {stop_exit}\n",
        encoding="utf-8",
    )
    (source / "requirements.txt").write_text(
        "fixture-package==1.0\n", encoding="utf-8"
    )
    (source / "PYTHON_RUNTIME.ps1").write_text("exit 0\n", encoding="utf-8")
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
        [
            git,
            "add",
            "UPDATE.bat",
            "UPDATE_CORE.ps1",
            "UPDATE_PREFLIGHT.ps1",
            "FORCE_STOP.ps1",
            "CV Studio.bat",
            "requirements.txt",
            "PYTHON_RUNTIME.ps1",
        ],
        cwd=source,
    )
    _run([git, "commit", "-m", "launcher fixture"], cwd=source)
    _run([git, "branch", "-M", branch], cwd=source)
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


def _push_self_update(
    tmp_path: Path,
    *,
    branch: str = "master",
    candidate_preflight_exit: int | None = None,
    dependency_manifest_change: bool = False,
) -> None:
    git = shutil.which("git")
    assert git is not None
    writer = tmp_path / "writer"
    _run([git, "clone", str(tmp_path / "remote.git"), str(writer)], cwd=tmp_path)
    _run([git, "checkout", branch], cwd=writer)
    _run([git, "config", "user.name", "CV Studio update test"], cwd=writer)
    _run([git, "config", "user.email", "update@example.invalid"], cwd=writer)
    launcher = (writer / "UPDATE.bat").read_text(encoding="utf-8")
    launcher = launcher.replace(
        "title CV Studio - Update\n",
        "rem pulled self-update fixture\ntitle CV Studio - Update\n",
        1,
    )
    (writer / "UPDATE.bat").write_bytes(
        launcher.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n").encode("utf-8")
    )
    (writer / "pulled.txt").write_text("pulled\n", encoding="utf-8")
    changed = ["UPDATE.bat", "pulled.txt"]
    if candidate_preflight_exit is not None:
        preflight = (writer / "UPDATE_PREFLIGHT.ps1").read_text(encoding="utf-8")
        before, marker, _last = preflight.rpartition("exit 0")
        assert marker
        (writer / "UPDATE_PREFLIGHT.ps1").write_text(
            before + f"exit {candidate_preflight_exit}" + _last,
            encoding="utf-8",
        )
        changed.append("UPDATE_PREFLIGHT.ps1")
    if dependency_manifest_change:
        (writer / "requirements.txt").write_text(
            "fixture-package==2.0\n", encoding="utf-8"
        )
        changed.append("requirements.txt")
    _run([git, "add", *changed], cwd=writer)
    _run([git, "commit", "-m", "update running launcher"], cwd=writer)
    _run([git, "push", "origin", branch], cwd=writer)


def test_update_launcher_hardening_source_contract() -> None:
    text = UPDATE_LAUNCHER.read_text(encoding="utf-8")
    assert 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0UPDATE_CORE.ps1"' in text
    assert text.rstrip().endswith(
        'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0UPDATE_CORE.ps1" & exit /b !ERRORLEVEL!'
    )

    core = UPDATE_CORE.read_text(encoding="utf-8")
    stop_call = core.index("& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $stopHelper")
    stop_result = core.index("$stopRc = [int]$LASTEXITCODE")
    stop_gate = core.index("if ($stopRc -ne 0)")
    start_call = core.index("& $launcher '--wait'")
    assert stop_call < stop_result < stop_gate < start_call
    assert "Previous source commit:" in core
    assert "source_update.log" in core
    assert "symbolic-ref --quiet --short HEAD" in core
    assert "$branch -cne 'master'" in core
    assert "diff --quiet --ignore-submodules --" in core
    assert "diff --cached --quiet --ignore-submodules --" in core
    assert "candidate_dependency_manifest_changed" in core
    assert "candidate_python_runtime_missing" in core
    current_preflight = core.index("Checking the current CV Studio installation")
    fetch = core.index("fetch --no-tags origin")
    candidate_preflight = core.index("Checking the downloaded updater")
    merge = core.index("merge --ff-only refs/remotes/origin/master")
    post_preflight = core.index("Checking CV Studio before stopping")
    assert current_preflight < fetch < candidate_preflight < merge < post_preflight < stop_call

    source_launcher = SOURCE_LAUNCHER.read_text(encoding="utf-8")
    assert 'if /i "%~1"=="--wait" goto :wait_for_start' in source_launcher
    assert 'cscript.exe //nologo "%~dp0START_HIDDEN.vbs"' in source_launcher
    hidden_launcher = (ROOT / "START_HIDDEN.vbs").read_text(encoding="utf-8")
    assert "PYTHON_RUNTIME.ps1" in hidden_launcher
    assert "resolvedPython" in hidden_launcher
    assert 'candidates = Array("pythonw"' not in hidden_launcher


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
    assert '"UPDATE_CORE.ps1"' in protected_builder
    assert '"PYTHON_RUNTIME.ps1"' in protected_builder


def test_update_preflight_uses_shared_exact_python_runtime_resolver() -> None:
    text = UPDATE_PREFLIGHT.read_text(encoding="utf-8")
    for variable in ("nodeCandidates", "tesseractCandidates"):
        assignment = text.index(f"${variable} = @(")
        first_candidate = text.index("@(", assignment + len(f"${variable} = @("))
        count_gate = text.index(f"if (${variable}.Count -eq 0)", assignment)
        assert assignment < first_candidate < count_gate
    assert "PYTHON_RUNTIME.ps1" in text
    assert "exact runtime package versions" in text


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell runtime resolver")
def test_python_runtime_resolver_returns_the_exact_validated_interpreter(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "resolved-python.txt"
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(PYTHON_RUNTIME),
            "-Root",
            str(ROOT),
            "-Candidates",
            sys.executable,
            "-OutputPath",
            str(output_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert not result.stdout.strip()
    resolved = Path(output_path.read_text(encoding="utf-8").strip())
    assert resolved.is_file()
    assert resolved.parent.resolve() == Path(sys.executable).parent.resolve()
    assert resolved.name.lower() in {"python.exe", "pythonw.exe"}


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell runtime resolver")
def test_python_runtime_resolver_rejects_stale_installed_versions(tmp_path: Path) -> None:
    stale_requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").replace(
        "flask==3.1.3", "flask==0.0.0", 1
    )
    (tmp_path / "requirements.txt").write_text(stale_requirements, encoding="utf-8")

    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(PYTHON_RUNTIME),
            "-Root",
            str(tmp_path),
            "-Candidates",
            sys.executable,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 8, result.stdout + result.stderr
    assert not result.stdout.strip()


@pytest.mark.skipif(
    os.name != "nt"
    or shutil.which("python") is None
    or shutil.which("node") is None
    or not _windows_tesseract_is_available(),
    reason="Windows Python/Node/Tesseract updater preflight",
)
def test_real_update_preflight_uses_launcher_path_python_before_stale_fixed_install(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    shutil.copy2(UPDATE_PREFLIGHT, source / "UPDATE_PREFLIGHT.ps1")
    shutil.copy2(PYTHON_RUNTIME, source / "PYTHON_RUNTIME.ps1")
    for name in (
        "CV Studio.bat",
        "START_HIDDEN.vbs",
        "FORCE_STOP.ps1",
    ):
        (source / name).write_text("fixture\n", encoding="utf-8")
    shutil.copy2(ROOT / "requirements.txt", source / "requirements.txt")
    (source / "package.json").write_text("{}\n", encoding="utf-8")
    (source / "INSTALL_RECEIPT.ps1").write_text("exit 0\n", encoding="utf-8")
    shutil.copytree(
        ROOT / "node_modules" / "adm-zip",
        source / "node_modules" / "adm-zip",
    )
    fake_local = tmp_path / "fake-local-app-data"
    fake_python = fake_local / "Programs" / "Python" / "Python312" / "python.exe"
    fake_python.parent.mkdir(parents=True)
    fake_python.write_bytes(b"not an executable")
    env = dict(os.environ)
    env["LOCALAPPDATA"] = str(fake_local)
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")

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
        env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Update preflight passed" in result.stdout


@pytest.mark.skipif(
    os.name != "nt"
    or shutil.which("python") is None
    or shutil.which("node") is None
    or not _windows_tesseract_is_available(),
    reason="Windows Python/Node/Tesseract updater preflight",
)
def test_downloaded_preflight_is_self_contained_for_v357_upgrade_transition(
    tmp_path: Path,
) -> None:
    source = tmp_path / "v357-source"
    source.mkdir()
    candidate_preflight = tmp_path / "candidate_update_preflight.ps1"
    shutil.copy2(UPDATE_PREFLIGHT, candidate_preflight)
    for name in (
        "CV Studio.bat",
        "START_HIDDEN.vbs",
        "FORCE_STOP.ps1",
    ):
        (source / name).write_text("fixture\n", encoding="utf-8")
    shutil.copy2(ROOT / "requirements.txt", source / "requirements.txt")
    (source / "package.json").write_text("{}\n", encoding="utf-8")
    (source / "INSTALL_RECEIPT.ps1").write_text("exit 0\n", encoding="utf-8")
    shutil.copytree(
        ROOT / "node_modules" / "adm-zip",
        source / "node_modules" / "adm-zip",
    )
    env = dict(os.environ)
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")

    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(candidate_preflight),
            "-Root",
            str(source),
        ],
        cwd=source,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Update preflight passed" in result.stdout


@pytest.mark.skipif(os.name != "nt", reason="Windows cmd.exe launcher behavior")
def test_update_launcher_survives_replacing_itself_during_real_pull(tmp_path: Path) -> None:
    source = _make_windows_fixture(tmp_path)
    _push_self_update(tmp_path)

    result = _run_windows_launcher(source)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (source / "pulled.txt").read_text(encoding="utf-8") == "pulled\n"
    assert "rem pulled self-update fixture" in (source / "UPDATE.bat").read_text(encoding="utf-8")
    assert (source / "stopped.txt").is_file()
    assert (source / "started.txt").is_file()


@pytest.mark.skipif(os.name != "nt", reason="Windows cmd.exe launcher behavior")
def test_update_launcher_checks_downloaded_preflight_before_changing_source(
    tmp_path: Path,
) -> None:
    source = _make_windows_fixture(tmp_path)
    before = _run([shutil.which("git") or "git", "rev-parse", "HEAD"], cwd=source).stdout.strip()
    _push_self_update(tmp_path, candidate_preflight_exit=8)

    result = _run_windows_launcher(source)

    after = _run([shutil.which("git") or "git", "rev-parse", "HEAD"], cwd=source).stdout.strip()
    assert result.returncode == 8, result.stdout + result.stderr
    assert "downloaded master version needs installation work" in result.stdout
    assert before == after
    assert not (source / "pulled.txt").exists()
    assert not (source / "stopped.txt").exists()
    assert not (source / "started.txt").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows cmd.exe launcher behavior")
def test_update_launcher_stops_before_pull_when_dependency_manifest_changes(
    tmp_path: Path,
) -> None:
    source = _make_windows_fixture(tmp_path)
    before = _run([shutil.which("git") or "git", "rev-parse", "HEAD"], cwd=source).stdout.strip()
    _push_self_update(tmp_path, dependency_manifest_change=True)

    result = _run_windows_launcher(source)

    after = _run([shutil.which("git") or "git", "rev-parse", "HEAD"], cwd=source).stdout.strip()
    assert result.returncode == 18, result.stdout + result.stderr
    assert "changes runtime dependencies" in result.stdout
    assert before == after
    assert "fixture-package==1.0" in (source / "requirements.txt").read_text(encoding="utf-8")
    assert not (source / "pulled.txt").exists()
    assert not (source / "stopped.txt").exists()
    assert not (source / "started.txt").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows cmd.exe launcher behavior")
def test_update_launcher_does_not_execute_branch_name(tmp_path: Path) -> None:
    source = _make_windows_fixture(tmp_path, branch="safe&echo.BRANCH_INJECTION")
    result = _run_windows_launcher(source)
    lines = [line.strip() for line in result.stdout.splitlines()]
    assert result.returncode == 14, result.stdout + result.stderr
    assert "safe&echo.BRANCH_INJECTION" in lines
    assert "BRANCH_INJECTION" not in lines
    assert "allowed only from the master branch" in result.stdout
    assert not (source / "stopped.txt").exists()
    assert not (source / "started.txt").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows cmd.exe launcher behavior")
def test_update_launcher_refuses_dirty_tracked_master_without_fetch_or_restart(
    tmp_path: Path,
) -> None:
    source = _make_windows_fixture(tmp_path)
    (source / "CV Studio.bat").write_bytes(
        (source / "CV Studio.bat").read_bytes() + b"rem local owner change\r\n"
    )

    result = _run_windows_launcher(source)

    assert result.returncode == 15, result.stdout + result.stderr
    assert "uncommitted tracked changes" in result.stdout
    assert not (source / "stopped.txt").exists()
    assert not (source / "started.txt").exists()


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
