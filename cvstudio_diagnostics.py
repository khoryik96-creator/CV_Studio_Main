"""Redacted runtime-diagnostics helpers for CV Studio.

The application remains responsible for assembling runtime state and
registering Flask routes.  This module receives state callbacks explicitly and
never imports the application or any protected credential store.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
from pathlib import Path
import platform
import re
import subprocess
from typing import Any, Callable, Iterable
import zipfile


def system_memory_status() -> dict[str, Any]:
    """Return best-effort physical-memory totals without adding a dependency."""
    total = 0
    available = 0
    source = "unavailable"
    try:
        if os.name == "nt":
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = MEMORYSTATUSEX()
            status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                total = int(status.ullTotalPhys)
                available = int(status.ullAvailPhys)
                source = "GlobalMemoryStatusEx"
        elif os.path.isfile("/proc/meminfo"):
            values = {}
            with open(
                "/proc/meminfo", "r", encoding="utf-8", errors="replace"
            ) as handle:
                for line in handle:
                    match = re.match(r"^([A-Za-z_()]+):\s+(\d+)\s+kB", line)
                    if match:
                        values[match.group(1)] = int(match.group(2)) * 1024
            total = int(values.get("MemTotal") or 0)
            available = int(
                values.get("MemAvailable") or values.get("MemFree") or 0
            )
            source = "/proc/meminfo"
        elif platform.system() == "Darwin":
            total_raw = subprocess.check_output(
                ["/usr/sbin/sysctl", "-n", "hw.memsize"], timeout=3
            )
            total = int(total_raw.decode(errors="replace").strip() or 0)
            vm_raw = subprocess.check_output(
                ["/usr/bin/vm_stat"], timeout=3
            ).decode(errors="replace")
            page_size_match = re.search(r"page size of (\d+) bytes", vm_raw)
            page_size = int(page_size_match.group(1)) if page_size_match else 4096
            free_pages = 0
            for label in (
                "Pages free",
                "Pages inactive",
                "Pages speculative",
                "Pages purgeable",
            ):
                match = re.search(
                    r"^{}:\s+(\d+)\.".format(re.escape(label)), vm_raw, re.M
                )
                if match:
                    free_pages += int(match.group(1))
            available = free_pages * page_size
            source = "sysctl/vm_stat"
        elif hasattr(os, "sysconf"):
            page = int(os.sysconf("SC_PAGE_SIZE"))
            total = page * int(os.sysconf("SC_PHYS_PAGES"))
            available = page * int(os.sysconf("SC_AVPHYS_PAGES"))
            source = "sysconf"
    except Exception:
        total = max(0, int(total or 0))
        available = max(0, int(available or 0))
    return {
        "total_bytes": max(0, total),
        "available_bytes": max(0, available),
        "used_percent": (
            round((1.0 - (float(available) / float(total))) * 100.0, 1)
            if total > 0 and available >= 0
            else None
        ),
        "source": source,
    }


def dependency_status(
    soffice_finder: Callable[[], Any],
    antiword_finder: Callable[[], Any],
    antiword_health: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    modules = [
        "flask",
        "docx",
        "PIL",
        "pdfplumber",
        "pypdfium2",
        "pytesseract",
        "openpyxl",
        "cryptography",
    ]
    result = {name: bool(importlib.util.find_spec(name)) for name in modules}
    try:
        result["libreoffice"] = bool(soffice_finder())
    except Exception:
        result["libreoffice"] = False
    if antiword_health is not None:
        try:
            health = antiword_health()
            result["antiword_health"] = (
                dict(health) if isinstance(health, dict) else {}
            )
            result["antiword"] = bool(
                result["antiword_health"].get("available")
                and result["antiword_health"].get("trusted")
                and result["antiword_health"].get("functional")
            )
        except Exception:
            result["antiword"] = False
            result["antiword_health"] = {
                "available": False,
                "trusted": False,
                "functional": False,
                "reason": "health-check-failed",
                "recovery_action": "run_installer",
            }
    else:
        try:
            result["antiword"] = bool(antiword_finder())
        except Exception:
            result["antiword"] = False
    return result


def redact_support_text(
    text: Any,
    private_paths: Iterable[tuple[Any, str]] = (),
) -> str:
    """Best-effort support-log redaction; preserve diagnostics, not secrets."""
    text = str(text or "")
    text = re.sub(
        r'(?i)\b(https?://[^\s?#"\'<>]+)\?[^\s"\'<>]*',
        r"\1?[query redacted]",
        text,
    )
    text = re.sub(
        r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+",
        r"\1[redacted]",
        text,
    )
    secret_names = (
        r"(?:access_token|refresh_token|client_secret|api_key|"
        r"authorization_code|password)"
    )
    text = re.sub(
        r'(?i)(["\']?'
        + secret_names
        + r'["\']?\s*[:=]\s*)(["\'])(.*?)\2',
        lambda match: (
            match.group(1) + match.group(2) + "[redacted]" + match.group(2)
        ),
        text,
    )
    text = re.sub(
        r'(?i)(["\']?'
        + secret_names
        + r'["\']?\s*[:=]\s*)[^"\'\s,;}]+',
        r"\1[redacted]",
        text,
    )
    text = re.sub(
        r"(?i)([?&](?:access_token|refresh_token|client_secret|api_key|"
        r"code|password)=)[^&\s]+",
        r"\1[redacted]",
        text,
    )
    text = re.sub(
        r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        "[email redacted]",
        text,
    )
    text = re.sub(
        r"(?i)(/candidates/)(?:\d{4,}|[A-Za-z0-9_-]{16,})",
        r"\1[id redacted]",
        text,
    )
    for path, label in private_paths:
        if path:
            variants = {
                str(path),
                str(path).replace("\\", "/"),
                str(path).replace("/", "\\"),
            }
            for variant in sorted(
                (item for item in variants if item), key=len, reverse=True
            ):
                text = re.sub(re.escape(variant), str(label), text, flags=re.I)
    text = re.sub(
        r"(?i)\b[A-Z]:[\\]Users[\\][^\r\n]+", "[home path redacted]", text
    )
    text = re.sub(
        r"(?i)(?<![A-Za-z0-9_])/(?:Users|home)/[^/\s]+(?:/[^\s]*)?",
        "[home path redacted]",
        text,
    )
    return text


def sanitize_browser_diagnostics(
    payload: Any,
    redact_text: Callable[[Any], str],
) -> dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    cache = payload.get("cache") if isinstance(payload.get("cache"), dict) else {}
    viewport = (
        payload.get("viewport")
        if isinstance(payload.get("viewport"), dict)
        else {}
    )
    keys = (
        payload.get("local_storage_keys")
        if isinstance(payload.get("local_storage_keys"), list)
        else []
    )
    recent_errors = (
        payload.get("recent_api_errors")
        if isinstance(payload.get("recent_api_errors"), list)
        else []
    )

    def safe_int(value: Any, maximum: int = 4 * 1024 * 1024 * 1024) -> int:
        try:
            return max(0, min(int(float(value or 0)), int(maximum)))
        except Exception:
            return 0

    def safe_float(value: Any, maximum: float = 100.0) -> float:
        try:
            number = float(value or 0)
            return max(
                0.0,
                min(number if number == number else 0.0, float(maximum)),
            )
        except Exception:
            return 0.0

    return {
        "user_agent": str(payload.get("user_agent") or "")[:500],
        "active_tab": re.sub(
            r"[^A-Za-z0-9_.:-]", "", str(payload.get("active_tab") or "")
        )[:80],
        "visibility_state": str(payload.get("visibility_state") or "")[:40],
        "viewport": {
            "width": safe_int(viewport.get("width"), 100000),
            "height": safe_int(viewport.get("height"), 100000),
            "device_pixel_ratio": safe_float(
                viewport.get("device_pixel_ratio"), 100.0
            ),
        },
        "cache": {
            key: safe_int(cache.get(key))
            for key in (
                "payload_entries",
                "payload_bytes",
                "payload_max_bytes",
                "dom_entries",
                "dom_bytes",
                "dom_max_bytes",
                "prefetch_ready",
                "prefetch_target",
            )
        },
        "memory_mode": re.sub(
            r"[^A-Za-z0-9_.:-]", "", str(payload.get("memory_mode") or "")
        )[:30],
        "local_storage_keys": sorted(
            {
                str(key)[:120]
                for key in keys
                if isinstance(key, str)
                and not re.search(
                    r"token|secret|password|api[_-]?key|credential", key, re.I
                )
            }
        )[:200],
        "recent_api_errors": [
            {
                "at": str(item.get("at") or "")[:40],
                "path": redact_text(
                    re.sub(r"[?#].*$", "", str(item.get("path") or ""))
                )[:240],
                "status": safe_int(item.get("status"), 999),
                "code": re.sub(
                    r"[^A-Z0-9_.:-]",
                    "",
                    str(item.get("code") or "").upper(),
                )[:100],
                "request_id": re.sub(
                    r"[^A-Za-z0-9_.:-]",
                    "",
                    str(item.get("request_id") or ""),
                )[:80],
                "message": redact_text(str(item.get("message") or ""))[:500],
                "action": re.sub(
                    r"[^A-Za-z0-9_.:-]",
                    "",
                    str(item.get("action") or ""),
                )[:80],
                "retryable": bool(item.get("retryable")),
            }
            for item in recent_errors[-20:]
            if isinstance(item, dict)
        ],
    }


class DiagnosticsService:
    """Explicitly wired handlers behind the established diagnostics endpoints."""

    def __init__(
        self,
        *,
        request_json: Callable[[], Any],
        jsonify: Callable[[Any], Any],
        send_file: Callable[..., Any],
        request_id: Callable[[], str],
        runtime_payload: Callable[[], dict[str, Any]],
        cancel_preview_work: Callable[[], Any],
        clear_preview_cache: Callable[[], Any],
        preview_cache_stats: Callable[[], dict[str, Any]],
        redact_text: Callable[[Any], str],
        sanitize_browser: Callable[[Any], dict[str, Any]],
        archive_timestamp: Callable[[], str],
        version: Callable[[], str],
        root_path: Callable[[], str],
        runtime_log_path: Callable[[], str],
    ):
        self._request_json = request_json
        self._jsonify = jsonify
        self._send_file = send_file
        self._request_id = request_id
        self._runtime_payload = runtime_payload
        self._cancel_preview_work = cancel_preview_work
        self._clear_preview_cache = clear_preview_cache
        self._preview_cache_stats = preview_cache_stats
        self._redact_text = redact_text
        self._sanitize_browser = sanitize_browser
        self._archive_timestamp = archive_timestamp
        self._version = version
        self._root_path = root_path
        self._runtime_log_path = runtime_log_path

    def runtime(self):
        return self._jsonify(self._runtime_payload())

    def clear_preview(self):
        self._cancel_preview_work()
        self._clear_preview_cache()
        return self._jsonify(
            {
                "ok": True,
                "request_id": self._request_id(),
                "cache": self._preview_cache_stats(),
            }
        )

    def support_bundle(self):
        body = self._request_json() or {}
        browser = self._sanitize_browser(body.get("browser"))
        version = self._version()
        generated = self._archive_timestamp()
        buffer = io.BytesIO()
        with zipfile.ZipFile(
            buffer,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=6,
        ) as archive:
            runtime_payload = self._runtime_payload()
            archive.writestr(
                "runtime.json",
                json.dumps(runtime_payload, ensure_ascii=False, indent=2),
            )
            archive.writestr(
                "browser.json",
                json.dumps(browser, ensure_ascii=False, indent=2),
            )
            roadmap = Path(self._root_path()) / "BACKBURNER_ROADMAP.md"
            archive.writestr(
                "BACKBURNER_ROADMAP.md",
                (
                    roadmap.read_text(encoding="utf-8")
                    if roadmap.is_file()
                    else "Roadmap note not present in this package."
                ),
            )
            archive.writestr(
                "README.txt",
                (
                    "CV Studio redacted diagnostic bundle\n"
                    "Version: {}\n"
                    "Generated: {}\n"
                    "Request ID: {}\n\n"
                    "No API keys, OAuth tokens, CV files, preview payloads or "
                    "localStorage values are included. Runtime log tails are "
                    "redacted but may still contain technical file names and "
                    "error wording; review before sharing outside the support "
                    "context.\n"
                ).format(
                    version,
                    runtime_payload.get("generated_at"),
                    self._request_id(),
                ),
            )
            active_log = self._runtime_log_path()
            for path, name in (
                (active_log, "runtime.log.tail.txt"),
                (active_log + ".1", "runtime.log.1.tail.txt"),
            ):
                try:
                    if os.path.isfile(path):
                        with open(path, "rb") as handle:
                            handle.seek(max(0, os.path.getsize(path) - 256 * 1024))
                            raw = (
                                handle.read(256 * 1024)
                                .decode("utf-8", errors="replace")
                            )
                        archive.writestr(name, self._redact_text(raw))
                except Exception as exc:
                    archive.writestr(
                        name + ".error.txt",
                        "Could not read log tail: {}".format(type(exc).__name__),
                    )
        buffer.seek(0)
        return self._send_file(
            buffer,
            mimetype="application/zip",
            as_attachment=True,
            download_name="cv_studio_diagnostic_bundle_{}_{}.zip".format(
                version.replace(".", "_"), generated
            ),
            max_age=0,
        )
