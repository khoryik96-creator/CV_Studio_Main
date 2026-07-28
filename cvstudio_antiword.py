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
import subprocess
from pathlib import Path
from typing import Any, Iterable


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
        "501f2cf83b050fd4a56ab1ecff6fe21295c168eb4a9876d46c259e7ca21cb923"
    ),
    "packages/antiword_1.3.5_macos_arm64_r46.tgz": (
        "17cd193eb8ed3b27d092c60fec181e6a7b6d82eda9741dbec03578396d659e25"
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
    "macos-x86_64": {
        "executable": "bin/antiword",
        "executable_sha256": (
            "867f9688d851ec85cb6dd5e70f14abcf53e2c77bf55da20ec6e8b94399904d5f"
        ),
        "manifest_sha256": (
            "e616a696828ce938ad90594ce635ee4889d464787cdfd110f5e42efd12418729"
        ),
        "package_sha256": (
            "501f2cf83b050fd4a56ab1ecff6fe21295c168eb4a9876d46c259e7ca21cb923"
        ),
        "native_signature": "unsigned upstream binary; pinned SHA-256",
    },
    "macos-arm64": {
        "executable": "bin/antiword",
        "executable_sha256": (
            "d4ad0924e195f5dc6a898d5bdcb734a532446ed927af7e3c49865b11ef5e250d"
        ),
        "manifest_sha256": (
            "f07264b33fefd3b12ce0af40f312ea8abd290a71e3d04f2c63a2bb16135cbe9e"
        ),
        "package_sha256": (
            "17cd193eb8ed3b27d092c60fec181e6a7b6d82eda9741dbec03578396d659e25"
        ),
        "native_signature": "upstream arm64 code-signature blob plus pinned SHA-256",
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


def _platform_tag() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "windows" and machine in {"amd64", "x86_64"}:
        return "windows-x64"
    if system == "darwin" and machine in {"arm64", "aarch64"}:
        return "macos-arm64"
    if system == "darwin" and machine in {"x86_64", "amd64"}:
        return "macos-x86_64"
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
    candidates: list[tuple[str, Path, Path]] = [
        (
            "managed",
            _managed_runtime_root(tag),
            _managed_runtime_root(tag) / "fixtures" / "UDHR-english.doc",
        )
    ]
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
        if not folder.is_dir() or folder.is_symlink():
            raise AntiwordDependencyError(
                "runtime-layout-invalid",
                "The managed Antiword runtime is incomplete. Re-run the CV "
                "Studio installer to repair it.",
            )
        for path in folder.rglob("*"):
            if path.is_symlink():
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
    if not manifest.is_file() or manifest.is_symlink():
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


def _functional_check(executable: Path, fixture: Path) -> None:
    if not fixture.is_file() or fixture.is_symlink():
        raise AntiwordDependencyError("functional-fixture-missing")
    if _sha256_file(fixture) != ANTIWORD_FIXTURE_SHA256:
        raise AntiwordDependencyError("functional-fixture-integrity-failed")
    child_env = os.environ.copy()
    child_env.pop("ANTIWORDHOME", None)
    kwargs: dict[str, Any] = {}
    if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW"):
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        result = subprocess.run(
            [str(executable), "-t", str(fixture)],
            cwd=str(executable.parent),
            env=child_env,
            capture_output=True,
            timeout=12,
            check=False,
            **kwargs,
        )
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


def _verify_candidate(
    source: str,
    root: Path,
    fixture: Path,
    tag: str,
) -> tuple[Path, dict[str, Any]]:
    config = _PLATFORMS[tag]
    if not root.is_dir() or root.is_symlink():
        raise AntiwordDependencyError("runtime-missing")
    entries = _parse_manifest(root, str(config["manifest_sha256"]))
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
    _functional_check(executable, fixture)
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
    reason = next(
        (item for item in failures if item != "runtime-missing"),
        failures[0] if failures else "runtime-missing",
    )
    return None, {
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


def antiword_subprocess_env() -> dict[str, str]:
    """Return a non-searching child environment for the pinned executable."""

    env = os.environ.copy()
    # The upstream 0.37 build has a long-standing ANTIWORDHOME buffer check bug.
    # Its complete resources are found relative to the verified bin directory.
    env.pop("ANTIWORDHOME", None)
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
]
