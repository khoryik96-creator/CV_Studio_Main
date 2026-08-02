"""Pinned Antiword dependency verification for legacy Microsoft Word files.

The dependency is intentionally app-independent.  It accepts explicit package
and runtime roots, trusts only the owner-vetted bundled/managed locations, and
never searches PATH or other user-writable executable locations.
"""

from __future__ import annotations

import hashlib
import os
import platform
import re
import shutil
import stat
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence


ANTIWORD_PACKAGE_VERSION = "1.3.5"
ANTIWORD_ENGINE_VERSION = "0.37"
ANTIWORD_SOURCE_COMMIT = "51441d45283512081c08010835b8002af79fe5e6"
ANTIWORD_SOURCE_SHA256 = (
    "72e84b33b54c11101cb70d63304ca0283f57a6d0ef518ca6329ff5e6490ad630"
)
ANTIWORD_FIXTURE_SHA256 = (
    "f430cdfe9446c4b943074d4bf804232761c284f2caa3d4125006b158d8b14af8"
)
ANTIWORD_RUNTIME_FILE_COUNT = 37
ANTIWORD_DISTRIBUTION_HASHES = {
    "packages/antiword_1.3.5_windows_x64_r46.zip": (
        "9a99f67680475605de009cb85ba94c7dc546eb261a4256d743597fbb24b0ddf8"
    ),
    "packages/antiword_1.3.5_macos_x86_64_r46.tgz": (
        "0416f1389dc01398cb820ec014e976a5c2198bb103a725f290efce1598f0fced"
    ),
    "packages/antiword_1.3.5_macos_arm64_r46.tgz": (
        "1536939cca2c1b9cfcab7721c8982933bf8093eda0460f0e38055e7c826eae9a"
    ),
    "source/antiword_1.3.5.tar.gz": ANTIWORD_SOURCE_SHA256,
    "GPL-2.0.txt": (
        "edaef632cbb643e4e7a221717a6c441a4c1a7c918e6e4d56debc3d8739b233f6"
    ),
    "fixtures/UDHR-english.doc": ANTIWORD_FIXTURE_SHA256,
}

_PLATFORMS = {
    "windows-x64": {
        "executable": "bin/antiword.exe",
        "executable_sha256": (
            "2cbab2831854ccd5141ea328824a77cb889586db2e97129873d543a52cf3e15c"
        ),
        "manifest_sha256": (
            "7d365a89f268a2fc34f815b369474124bc6a1aac02e9b0b57e6dfd5eb5368da0"
        ),
        "package_sha256": (
            "9a99f67680475605de009cb85ba94c7dc546eb261a4256d743597fbb24b0ddf8"
        ),
        "native_signature": "unsigned upstream binary; pinned SHA-256",
    },
    "macos-intel": {
        "executable": "bin/antiword",
        "executable_sha256": "afeec28ba1bc3f89e9552f26402312c84d072b91f301200710f113afed36dea7",
        "manifest_sha256": "7e403a00b2acd1186c714bc55fe382f2b8a03fb5c430edd16e4d447e3f9f4ee8",
        "package_sha256": "0416f1389dc01398cb820ec014e976a5c2198bb103a725f290efce1598f0fced",
        "native_signature": "official Mach-O x86_64 binary; pinned SHA-256",
    },
    "macos-arm64": {
        "executable": "bin/antiword",
        "executable_sha256": "dd4be2c485c589cd4ac8495c9de77510b7496d2acc44deadebab80ec88d6769d",
        "manifest_sha256": "6c59492af62df5d342c16b3126e588a4bbe855f3ba37f1f9120dc3e5352f6ce3",
        "package_sha256": "1536939cca2c1b9cfcab7721c8982933bf8093eda0460f0e38055e7c826eae9a",
        "native_signature": "official Mach-O arm64 binary; pinned SHA-256",
    },
}

_MANIFEST_LINE = re.compile(r"^([0-9a-fA-F]{64})  ([^\r\n]+)$")
_FUNCTIONAL_MARKERS = (
    "Universal Declaration of Human Rights",
    "All people everywhere have the same human rights",
)


class AntiwordDependencyError(RuntimeError):
    """Failure of the mandatory, verified legacy-.doc dependency."""

    code = "ANTIWORD_DEPENDENCY_UNAVAILABLE"
    http_status = 424
    retryable = False
    recovery_action = "run_installer"

    def __init__(self, reason: str, message: str | None = None):
        self.reason = str(reason or "unavailable")
        self.public_message = message or (
            "Verified Antiword is required for legacy .doc files but is not "
            "ready. Re-run the CV Studio installer, then retry this file."
        )
        super().__init__(self.public_message)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_link_or_reparse(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
    except Exception:
        return True
    try:
        is_junction = getattr(path, "is_junction", None)
        if callable(is_junction) and is_junction():
            return True
    except Exception:
        return True
    if os.name == "nt":
        try:
            attributes = int(
                getattr(path.lstat(), "st_file_attributes", 0) or 0
            )
            return bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
        except Exception:
            return True
    return False


def _platform_tag() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "windows" and machine in {"amd64", "x86_64"}:
        return "windows-x64"
    if system == "darwin" and machine in {"x86_64", "amd64"}:
        return "macos-intel"
    if system == "darwin" and machine in {"arm64", "aarch64"}:
        return "macos-arm64"
    return ""


def _managed_runtime_root(tag: str) -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(
            Path.home() / "AppData" / "Local"
        )
        state = Path(base) / "TheGuoLab" / "CVStudio"
    else:
        state = Path.home() / ".guo_lab_cv_studio"
    return (
        state
        / "dependencies"
        / "antiword"
        / ANTIWORD_PACKAGE_VERSION
        / tag
    )


def _unique_paths(paths: Iterable[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        try:
            key = os.path.normcase(str(path.resolve(strict=False)))
        except Exception:
            key = os.path.normcase(str(path))
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def _candidate_runtimes(
    package_root: str | os.PathLike[str],
    runtime_root: str | os.PathLike[str] | None,
    tag: str,
) -> list[tuple[str, Path, Path]]:
    package = Path(package_root)
    runtime = Path(runtime_root) if runtime_root else package
    vendor_bases = _unique_paths(
        (
            package / "vendor" / "antiword",
            runtime / "vendor" / "antiword",
            package / "runtime" / "native" / "vendor" / "antiword",
        )
    )
    candidates: list[tuple[str, Path, Path]] = []
    # Owner protected-build smoke must certify the copied package, never an
    # already installed managed runtime on the build host.
    if str(
        os.environ.get("CVSTUDIO_ANTIWORD_PACKAGE_ONLY") or ""
    ).strip() != "1":
        candidates.append(
            (
                "managed",
                _managed_runtime_root(tag),
                _managed_runtime_root(tag)
                / "fixtures"
                / "UDHR-english.doc",
            )
        )
    for base in vendor_bases:
        candidates.append(
            (
                "bundled",
                base / tag,
                base / "fixtures" / "UDHR-english.doc",
            )
        )
    return candidates


def _safe_runtime_files(root: Path) -> list[Path]:
    root_resolved = root.resolve(strict=True)
    files: list[Path] = []
    for folder_name in ("bin", "share"):
        folder = root / folder_name
        if not folder.is_dir() or _is_link_or_reparse(folder):
            raise AntiwordDependencyError(
                "runtime-layout-invalid",
                "The managed Antiword runtime is incomplete. Re-run the CV "
                "Studio installer to repair it.",
            )
        for path in folder.rglob("*"):
            if _is_link_or_reparse(path):
                raise AntiwordDependencyError(
                    "runtime-link-rejected",
                    "The managed Antiword runtime failed its trust check. "
                    "Re-run the CV Studio installer to repair it.",
                )
            if not path.is_file():
                continue
            resolved = path.resolve(strict=True)
            try:
                resolved.relative_to(root_resolved)
            except ValueError as exc:
                raise AntiwordDependencyError(
                    "runtime-path-escaped",
                    "The managed Antiword runtime failed its trust check. "
                    "Re-run the CV Studio installer to repair it.",
                ) from exc
            files.append(path)
    return files


def _parse_manifest(root: Path, expected_hash: str) -> dict[str, str]:
    manifest = root / "SHA256SUMS"
    if not manifest.is_file() or _is_link_or_reparse(manifest):
        raise AntiwordDependencyError("manifest-missing")
    if _sha256_file(manifest) != expected_hash:
        raise AntiwordDependencyError(
            "manifest-integrity-failed",
            "The managed Antiword manifest failed verification. Re-run the CV "
            "Studio installer to repair it.",
        )
    entries: dict[str, str] = {}
    try:
        lines = manifest.read_text(encoding="utf-8").splitlines()
    except Exception as exc:
        raise AntiwordDependencyError("manifest-unreadable") from exc
    for line in lines:
        match = _MANIFEST_LINE.fullmatch(line)
        if not match:
            raise AntiwordDependencyError("manifest-invalid")
        digest, relative = match.groups()
        relative = relative.replace("\\", "/")
        parts = Path(relative).parts
        if (
            relative.startswith("/")
            or not parts
            or parts[0] not in {"bin", "share"}
            or ".." in parts
            or relative in entries
        ):
            raise AntiwordDependencyError("manifest-path-invalid")
        entries[relative] = digest.lower()
    if len(entries) != ANTIWORD_RUNTIME_FILE_COUNT:
        raise AntiwordDependencyError("manifest-file-count-invalid")
    return entries


def _open_windows_runtime_handle(path: Path, *, directory: bool) -> int:
    """Open a read handle that denies write/delete sharing until it is closed."""

    if os.name != "nt":
        raise AntiwordDependencyError("unsupported-platform")
    import ctypes
    from ctypes import wintypes

    create_file = ctypes.WinDLL(
        "kernel32", use_last_error=True
    ).CreateFileW
    create_file.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    create_file.restype = wintypes.HANDLE
    desired_access = 0x0001 | 0x0080 if directory else 0x80000000
    flags = 0x00200000 if directory else 0x00200000
    if directory:
        flags |= 0x02000000
    handle = create_file(
        str(path),
        desired_access,
        0x00000001,  # FILE_SHARE_READ only: deny write/delete/rename.
        None,
        3,  # OPEN_EXISTING
        flags,  # OPEN_REPARSE_POINT, plus BACKUP_SEMANTICS for directories.
        None,
    )
    invalid_handle = ctypes.c_void_p(-1).value
    if handle == invalid_handle:
        error = ctypes.get_last_error()
        raise AntiwordDependencyError(
            "runtime-lock-failed",
            "The managed Antiword runtime could not be locked for secure "
            "execution. Close programs using its files, re-run the CV Studio "
            f"installer, then retry. (Windows error {error})",
        )
    return int(handle)


def _close_windows_runtime_handle(handle: int) -> None:
    import ctypes
    from ctypes import wintypes

    close_handle = ctypes.WinDLL(
        "kernel32", use_last_error=True
    ).CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL
    close_handle(wintypes.HANDLE(handle))


@contextmanager
def _locked_candidate_runtime(
    root: Path,
    fixture: Path,
    tag: str,
) -> Iterator[tuple[dict[str, str], Path, Path]]:
    """Lock the exact manifest/runtime/fixture tree through process lifetime."""

    if tag.startswith("macos-"):
        if platform.system().lower() != "darwin":
            raise AntiwordDependencyError("unsupported-platform")
        if not root.is_dir() or _is_link_or_reparse(root):
            raise AntiwordDependencyError("runtime-missing")
        immutable = getattr(stat, "UF_IMMUTABLE", None)
        if immutable is None or not hasattr(os, "chflags"):
            raise AntiwordDependencyError("runtime-lock-failed")
        with tempfile.TemporaryDirectory(prefix="cvstudio-antiword-immutable-") as temporary:
            snapshot = Path(temporary) / tag
            snapshot_fixture = Path(temporary) / "UDHR-english.doc"
            shutil.copytree(root, snapshot, symlinks=False)
            shutil.copy2(fixture, snapshot_fixture)
            entries = _parse_manifest(snapshot, str(_PLATFORMS[tag]["manifest_sha256"]))
            protected = [snapshot_fixture, snapshot / "SHA256SUMS"] + [
                snapshot / Path(relative) for relative in sorted(entries)
            ]
            directories = sorted(
                {snapshot, *(path.parent for path in protected)},
                key=lambda item: (len(item.parts), str(item)),
                reverse=True,
            )
            executable = snapshot / Path(str(_PLATFORMS[tag]["executable"]))
            try:
                for path in protected:
                    os.chmod(path, 0o500 if path == executable else 0o400)
                    os.chflags(path, int(path.stat().st_flags) | int(immutable), follow_symlinks=False)
                for directory in directories:
                    os.chmod(directory, 0o500)
                    os.chflags(directory, int(directory.stat().st_flags) | int(immutable), follow_symlinks=False)
                yield entries, snapshot, snapshot_fixture
            finally:
                for directory in reversed(directories):
                    try:
                        os.chflags(directory, 0, follow_symlinks=False)
                        os.chmod(directory, 0o700)
                    except OSError:
                        pass
                for path in protected:
                    try:
                        os.chflags(path, 0, follow_symlinks=False)
                        os.chmod(path, 0o600)
                    except OSError:
                        pass
        return
    if os.name != "nt" or tag != "windows-x64":
        raise AntiwordDependencyError("unsupported-platform")
    if not root.is_dir() or _is_link_or_reparse(root):
        raise AntiwordDependencyError("runtime-missing")

    config = _PLATFORMS[tag]
    handles: list[int] = []
    locked: set[str] = set()

    def lock(path: Path, *, directory: bool) -> None:
        key = os.path.normcase(str(path.absolute()))
        if key in locked:
            return
        handles.append(
            _open_windows_runtime_handle(path, directory=directory)
        )
        locked.add(key)

    try:
        # Lock the root and pinned manifest before trusting the manifest's
        # contents to decide which remaining paths must be protected.
        lock(root, directory=True)
        lock(root / "SHA256SUMS", directory=False)
        entries = _parse_manifest(
            root, str(config["manifest_sha256"])
        )

        directories = {root / "bin", root / "share", fixture.parent}
        for relative in entries:
            parent = (root / Path(relative)).parent
            while parent != root:
                directories.add(parent)
                parent = parent.parent
        for directory in sorted(
            directories, key=lambda item: (len(item.parts), str(item))
        ):
            lock(directory, directory=True)

        lock(fixture, directory=False)
        for relative in sorted(entries):
            lock(root / Path(relative), directory=False)
        yield entries, root, fixture
    finally:
        for handle in reversed(handles):
            _close_windows_runtime_handle(handle)


def _run_locked_antiword_process(
    executable: Path,
    arguments: Sequence[str | os.PathLike[str]],
    *,
    timeout: float,
) -> subprocess.CompletedProcess[bytes]:
    """Run Antiword while the caller retains the verified runtime locks."""

    child_env = antiword_subprocess_env(executable)
    kwargs: dict[str, Any] = {}
    if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW"):
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    command = [
        str(executable),
        *(str(argument) for argument in arguments),
    ]
    process = subprocess.Popen(
        command,
        cwd=str(executable.parent),
        env=child_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        **kwargs,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        try:
            process.kill()
        except OSError:
            pass
        try:
            stdout, stderr = process.communicate()
        except Exception:
            stdout = exc.output or b""
            stderr = exc.stderr or b""
        exc.output = stdout
        exc.stderr = stderr
        raise
    except BaseException:
        try:
            process.kill()
        except OSError:
            pass
        try:
            process.communicate()
        except Exception:
            pass
        raise
    return subprocess.CompletedProcess(
        command,
        process.returncode,
        stdout,
        stderr,
    )


def _functional_check_locked(executable: Path, fixture: Path) -> None:
    if not fixture.is_file() or _is_link_or_reparse(fixture):
        raise AntiwordDependencyError("functional-fixture-missing")
    if _sha256_file(fixture) != ANTIWORD_FIXTURE_SHA256:
        raise AntiwordDependencyError("functional-fixture-integrity-failed")
    try:
        result = _run_locked_antiword_process(
            executable,
            ("-t", fixture),
            timeout=12,
        )
    except subprocess.TimeoutExpired as exc:
        raise AntiwordDependencyError("functional-execution-timeout") from exc
    except Exception as exc:
        raise AntiwordDependencyError("functional-execution-failed") from exc
    text = result.stdout.decode("utf-8", errors="replace")
    if result.returncode != 0 or any(
        marker not in text for marker in _FUNCTIONAL_MARKERS
    ):
        raise AntiwordDependencyError(
            "functional-output-failed",
            "Antiword was found but failed its genuine legacy .doc functional "
            "check. Re-run the CV Studio installer to repair it.",
        )


def _verify_candidate_locked(
    source: str,
    root: Path,
    fixture: Path,
    tag: str,
    entries: dict[str, str],
) -> tuple[Path, dict[str, Any]]:
    config = _PLATFORMS[tag]
    actual_files = _safe_runtime_files(root)
    actual_relatives = {
        path.relative_to(root).as_posix() for path in actual_files
    }
    if actual_relatives != set(entries):
        raise AntiwordDependencyError(
            "runtime-file-set-invalid",
            "The managed Antiword runtime has missing or unexpected files. "
            "Re-run the CV Studio installer to repair it.",
        )
    for relative, expected in entries.items():
        if _sha256_file(root / Path(relative)) != expected:
            raise AntiwordDependencyError(
                "runtime-integrity-failed",
                "The managed Antiword runtime failed SHA-256 verification. "
                "Re-run the CV Studio installer to repair it.",
            )
    executable = root / Path(str(config["executable"]))
    if _sha256_file(executable) != str(config["executable_sha256"]):
        raise AntiwordDependencyError("executable-integrity-failed")
    _functional_check_locked(executable, fixture)
    return executable, {
        "available": True,
        "trusted": True,
        "functional": True,
        "version": ANTIWORD_PACKAGE_VERSION,
        "engine_version": ANTIWORD_ENGINE_VERSION,
        "platform": tag,
        "source": source,
        "trust_method": "pinned-sha256-and-complete-runtime-manifest",
        "native_signature": config["native_signature"],
        "manifest_verified": True,
        "functional_fixture_verified": True,
        "runtime_file_count": ANTIWORD_RUNTIME_FILE_COUNT,
        "reason": "",
        "recovery_action": "",
    }


def _verify_candidate(
    source: str,
    root: Path,
    fixture: Path,
    tag: str,
) -> tuple[Path, dict[str, Any]]:
    with _locked_candidate_runtime(root, fixture, tag) as locked:
        entries, locked_root, locked_fixture = locked
        return _verify_candidate_locked(
            source, locked_root, locked_fixture, tag, entries
        )


def _failed_health(tag: str, failures: Sequence[str]) -> dict[str, Any]:
    reason = next(
        (item for item in failures if item != "runtime-missing"),
        failures[0] if failures else "runtime-missing",
    )
    return {
        "available": False,
        "trusted": False,
        "functional": False,
        "version": ANTIWORD_PACKAGE_VERSION,
        "engine_version": ANTIWORD_ENGINE_VERSION,
        "platform": tag,
        "source": "",
        "trust_method": "pinned-sha256-and-complete-runtime-manifest",
        "native_signature": _PLATFORMS[tag]["native_signature"],
        "manifest_verified": False,
        "functional_fixture_verified": False,
        "runtime_file_count": 0,
        "reason": reason,
        "recovery_action": "run_installer",
    }


def resolve_verified_antiword(
    package_root: str | os.PathLike[str],
    runtime_root: str | os.PathLike[str] | None = None,
) -> tuple[Path | None, dict[str, Any]]:
    """Return the first fully verified managed/bundled runtime and health."""

    tag = _platform_tag()
    if not tag or tag not in _PLATFORMS:
        return None, {
            "available": False,
            "trusted": False,
            "functional": False,
            "version": ANTIWORD_PACKAGE_VERSION,
            "engine_version": ANTIWORD_ENGINE_VERSION,
            "platform": tag or "unsupported",
            "source": "",
            "trust_method": "pinned-sha256-and-complete-runtime-manifest",
            "native_signature": "",
            "manifest_verified": False,
            "functional_fixture_verified": False,
            "runtime_file_count": 0,
            "reason": "unsupported-platform",
            "recovery_action": "use_supported_platform",
        }

    failures: list[str] = []
    for source, root, fixture in _candidate_runtimes(
        package_root, runtime_root, tag
    ):
        try:
            return _verify_candidate(source, root, fixture, tag)
        except AntiwordDependencyError as exc:
            failures.append(exc.reason)
        except Exception:
            failures.append("verification-failed")
    return None, _failed_health(tag, failures)


def run_verified_antiword(
    package_root: str | os.PathLike[str],
    arguments: Sequence[str | os.PathLike[str]],
    runtime_root: str | os.PathLike[str] | None = None,
    *,
    timeout: float = 20,
) -> subprocess.CompletedProcess[bytes]:
    """Verify and execute the exact protected native Antiword runtime."""

    tag = _platform_tag()
    if not tag or tag not in _PLATFORMS:
        raise AntiwordDependencyError("unsupported-platform")

    failures: list[str] = []
    for source, root, fixture in _candidate_runtimes(
        package_root, runtime_root, tag
    ):
        try:
            with _locked_candidate_runtime(root, fixture, tag) as locked:
                entries, locked_root, locked_fixture = locked
                executable, _health = _verify_candidate_locked(
                    source, locked_root, locked_fixture, tag, entries
                )
                return _run_locked_antiword_process(
                    executable, arguments, timeout=timeout
                )
        except AntiwordDependencyError as exc:
            failures.append(exc.reason)
        except (subprocess.TimeoutExpired, OSError):
            raise
        except Exception:
            failures.append("verification-failed")

    health = _failed_health(tag, failures)
    raise AntiwordDependencyError(str(health["reason"]))


def antiword_health(
    package_root: str | os.PathLike[str],
    runtime_root: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    return resolve_verified_antiword(package_root, runtime_root)[1]


def find_verified_antiword(
    package_root: str | os.PathLike[str],
    runtime_root: str | os.PathLike[str] | None = None,
) -> str | None:
    executable, _health = resolve_verified_antiword(
        package_root, runtime_root
    )
    return str(executable) if executable else None


def require_verified_antiword(
    package_root: str | os.PathLike[str],
    runtime_root: str | os.PathLike[str] | None = None,
) -> str:
    executable, health = resolve_verified_antiword(
        package_root, runtime_root
    )
    if executable:
        return str(executable)
    raise AntiwordDependencyError(str(health.get("reason") or "unavailable"))


def antiword_subprocess_env(
    executable: str | os.PathLike[str],
) -> dict[str, str]:
    """Return a non-searching child environment for the pinned executable."""

    env = os.environ.copy()
    # The upstream 0.37 build has a long-standing ANTIWORDHOME buffer check bug.
    # It also searches $HOME/.antiword before its installed mapping directory.
    # Bind HOME to the already verified executable *file*. Any attempted
    # $HOME/.antiword lookup therefore fails with ENOTDIR and falls through to
    # the pinned, locked global mapping directory.
    if platform.system().lower() == "darwin":
        env["ANTIWORDHOME"] = str(
            Path(executable).resolve().parent.parent / "share" / "antiword"
        )
    else:
        env.pop("ANTIWORDHOME", None)
    env["HOME"] = str(Path(executable).resolve())
    return env


__all__ = [
    "ANTIWORD_DISTRIBUTION_HASHES",
    "ANTIWORD_ENGINE_VERSION",
    "ANTIWORD_PACKAGE_VERSION",
    "AntiwordDependencyError",
    "antiword_health",
    "antiword_subprocess_env",
    "find_verified_antiword",
    "require_verified_antiword",
    "resolve_verified_antiword",
    "run_verified_antiword",
]
