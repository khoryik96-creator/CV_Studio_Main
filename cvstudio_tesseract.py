"""Mandatory native Tesseract discovery and functional health checks."""

from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Iterable


class TesseractDependencyError(RuntimeError):
    code = "TESSERACT_DEPENDENCY_UNAVAILABLE"
    http_status = 424
    retryable = False
    recovery_action = "run_installer"

    def __init__(self, reason: str):
        self.reason = str(reason or "unavailable")
        super().__init__(
            "Tesseract OCR is a mandatory CV Studio dependency but is not "
            "ready. Re-run the CV Studio installer, then retry."
        )


def _unique(paths: Iterable[str | os.PathLike[str]]) -> list[Path]:
    result: list[Path] = []
    seen: set[str] = set()
    for value in paths:
        if not value:
            continue
        path = Path(value).expanduser()
        key = os.path.normcase(str(path.resolve(strict=False)))
        if key not in seen:
            seen.add(key)
            result.append(path)
    return result


def tesseract_candidates(package_root: str | os.PathLike[str]) -> list[Path]:
    root = Path(package_root)
    local_app_data = os.environ.get("LOCALAPPDATA") or ""
    discovered = shutil.which("tesseract") or shutil.which("tesseract.exe") or ""
    return _unique((
        root / "tesseract" / "tesseract.exe",
        Path(os.environ.get("PROGRAMFILES") or r"C:\Program Files") / "Tesseract-OCR" / "tesseract.exe",
        Path(os.environ.get("PROGRAMFILES(X86)") or r"C:\Program Files (x86)") / "Tesseract-OCR" / "tesseract.exe",
        Path(local_app_data) / "Programs" / "Tesseract-OCR" / "tesseract.exe" if local_app_data else "",
        "/opt/homebrew/bin/tesseract",
        "/usr/local/bin/tesseract",
        "/usr/bin/tesseract",
        discovered,
    ))


def resolve_tesseract(package_root: str | os.PathLike[str]) -> tuple[Path | None, dict[str, Any]]:
    failures: list[str] = []
    for candidate in tesseract_candidates(package_root):
        if not candidate.is_file():
            continue
        try:
            executable = candidate.resolve(strict=True)
            version_result = subprocess.run(
                [str(executable), "--version"], capture_output=True, text=True, timeout=10
            )
            version_text = "\n".join(
                part for part in (version_result.stdout, version_result.stderr) if part
            ).strip()
            match = re.search(r"tesseract\s+v?([0-9][^\s]*)", version_text, re.I)
            if version_result.returncode != 0 or not match:
                failures.append("version-check-failed")
                continue
            language_result = subprocess.run(
                [str(executable), "--list-langs"], capture_output=True, text=True, timeout=15
            )
            language_text = "\n".join(
                part for part in (language_result.stdout, language_result.stderr) if part
            )
            languages = {
                line.strip().lower() for line in language_text.splitlines()
                if line.strip() and not line.lower().startswith("list of available languages")
            }
            if language_result.returncode != 0 or "eng" not in languages:
                failures.append("english-language-data-missing")
                continue
            return executable, {
                "available": True,
                "functional": True,
                "version": match.group(1),
                "executable": str(executable),
                "english_language_data": True,
                "reason": "",
                "recovery_action": "",
            }
        except subprocess.TimeoutExpired:
            failures.append("functional-check-timeout")
        except Exception:
            failures.append("functional-check-failed")
    return None, {
        "available": False,
        "functional": False,
        "version": "",
        "executable": "",
        "english_language_data": False,
        "reason": failures[0] if failures else "not-found",
        "recovery_action": "run_installer",
    }


def tesseract_health(package_root: str | os.PathLike[str]) -> dict[str, Any]:
    return resolve_tesseract(package_root)[1]


def find_tesseract(package_root: str | os.PathLike[str]) -> str | None:
    executable, _health = resolve_tesseract(package_root)
    return str(executable) if executable else None


def require_tesseract(package_root: str | os.PathLike[str]) -> str:
    executable, health = resolve_tesseract(package_root)
    if executable:
        return str(executable)
    raise TesseractDependencyError(str(health.get("reason") or "unavailable"))


__all__ = [
    "TesseractDependencyError",
    "find_tesseract",
    "require_tesseract",
    "resolve_tesseract",
    "tesseract_candidates",
    "tesseract_health",
]
