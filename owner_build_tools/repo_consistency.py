#!/usr/bin/env python3
"""Repair/verify the private repository's deterministic protected-build state.

This owner-only helper prevents these known drift classes:
1. stale package-lock/npm-ci state overriding adm-zip@0.5.17;
2. Git line-ending conversion changing owner-vetted dependency bytes;
3. LF-only or BOM-bearing Windows batch files breaking cmd.exe;
4. BOM-bearing or CRLF macOS command scripts invalidating their shebangs;
5. BOM-bearing PowerShell port/stop helpers producing noisy or ambiguous starts;
6. UTF-8-BOM VBS launchers crashing Windows Script Host with 800A0408.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ADM_ZIP_VERSION = "0.5.17"
BASE_INSTALL = "npm install --ignore-scripts --no-audit --no-fund --package-lock=false"
OBFUSCATOR_INSTALL = "npm install --no-save --ignore-scripts --no-audit --no-fund --package-lock=false javascript-obfuscator@4.1.1"
GIT_CONFIG_COMMAND = "git config --global core.autocrlf false"
GIT_ATTRIBUTES_RULE = "* -text"
LOCK_FILES = ("package-lock.json", "npm-shrinkwrap.json")
BATCH_FILES = (
    "CV Studio.bat",
    "INSTALL.bat",
    "INSTALL_CORE.bat",
    "MERGE_TITLE_CACHE.bat",
    "RESTORE_PREVIOUS.bat",
    "STOP.bat",
    "owner_build_tools/BUILD_PROTECTED_WINDOWS.bat",
    "owner_build_tools/APPLY_PRIVATE_REPO_FIX_WINDOWS.bat",
)
NO_BOM_UTF8_FILES = (
    "INSTANCE_PORT.ps1",
    "STOP_CORE.ps1",
    "RESTORE_PREVIOUS.ps1",
)
VBS_FILES = (
    "START_HIDDEN.vbs",
    "WATCHDOG.vbs",
)
POSIX_SCRIPT_FILES = (
    "install.sh",
    "start.sh",
    "restore_previous.sh",
    "owner_build_tools/BUILD_PROTECTED_MAC.command",
    "owner_build_tools/APPLY_PRIVATE_REPO_FIX_MAC.command",
)
UTF8_BOM = b"\xef\xbb\xbf"


def _write_text_if_changed(path: Path, text: str, *, newline: str = "\n") -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    data = normalized.replace("\n", newline).encode("utf-8")
    if path.is_file() and path.read_bytes() == data:
        return False
    path.write_bytes(data)
    return True


def _normalize_batch_crlf(path: Path) -> bool:
    """Write a Windows batch file as UTF-8 without BOM and CRLF only."""
    if not path.is_file():
        return False
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    fixed = text.replace("\n", "\r\n").encode("utf-8")
    if fixed == raw:
        return False
    path.write_bytes(fixed)
    return True


def _normalize_vbs_crlf(path: Path) -> bool:
    """Write a Windows Script Host file as UTF-8 without BOM and CRLF only."""
    if not path.is_file():
        return False
    raw = path.read_bytes()
    content = raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    fixed = content.replace("\n", "\r\n").encode("utf-8")
    if fixed == raw:
        return False
    path.write_bytes(fixed)
    return True


def _normalize_utf8_no_bom(path: Path) -> bool:
    """Remove a UTF-8 BOM without changing the file's newline convention."""
    if not path.is_file():
        return False
    raw = path.read_bytes()
    if not raw.startswith(UTF8_BOM):
        return False
    path.write_bytes(raw[len(UTF8_BOM):])
    return True


def _normalize_posix_lf(path: Path) -> bool:
    """Write a POSIX shell/command script as UTF-8 without BOM and LF only."""
    if not path.is_file():
        return False
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    fixed = text.encode("utf-8")
    if fixed == raw:
        return False
    path.write_bytes(fixed)
    return True


def _has_only_crlf(raw: bytes) -> bool:
    return b"\n" not in raw.replace(b"\r\n", b"") and b"\r" not in raw.replace(b"\r\n", b"")


def _has_only_lf(raw: bytes) -> bool:
    return b"\r" not in raw


def repair(root: Path) -> list[str]:
    changes: list[str] = []
    for name in LOCK_FILES:
        path = root / name
        if path.exists():
            path.unlink()
            changes.append(f"removed stale {name}")

    package_path = root / "package.json"
    data = json.loads(package_path.read_text(encoding="utf-8-sig"))
    deps = data.setdefault("dependencies", {})
    if deps.get("adm-zip") != ADM_ZIP_VERSION:
        deps["adm-zip"] = ADM_ZIP_VERSION
        _write_text_if_changed(package_path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        changes.append("pinned package.json adm-zip to 0.5.17")

    gitignore = root / ".gitignore"
    original_gitignore = gitignore.read_text(encoding="utf-8-sig") if gitignore.exists() else ""
    lines = original_gitignore.splitlines()
    for name in LOCK_FILES:
        if name not in lines:
            lines.append(name)
            changes.append(f"added {name} to .gitignore")
    desired_gitignore = "\n".join(lines).rstrip() + "\n"
    _write_text_if_changed(gitignore, desired_gitignore)

    attrs = root / ".gitattributes"
    attr_lines = attrs.read_text(encoding="utf-8-sig").splitlines() if attrs.exists() else []
    if GIT_ATTRIBUTES_RULE not in [line.strip() for line in attr_lines]:
        _write_text_if_changed(
            attrs,
            "# Preserve exact committed bytes on Windows, macOS, and Linux.\n"
            "# Required for protected dependency hashes and manifest reproducibility.\n"
            f"{GIT_ATTRIBUTES_RULE}\n",
        )
        changes.append("added byte-stable .gitattributes policy")

    for rel in BATCH_FILES:
        path = root / rel
        if _normalize_batch_crlf(path):
            changes.append(f"normalized {rel} to UTF-8 without BOM and CRLF")

    for rel in NO_BOM_UTF8_FILES:
        path = root / rel
        if _normalize_utf8_no_bom(path):
            changes.append(f"removed UTF-8 BOM from {rel}")

    for rel in VBS_FILES:
        path = root / rel
        if _normalize_vbs_crlf(path):
            changes.append(f"normalized {rel} to UTF-8 without BOM and CRLF for Windows Script Host")

    for rel in POSIX_SCRIPT_FILES:
        path = root / rel
        if _normalize_posix_lf(path):
            changes.append(f"normalized {rel} to UTF-8 without BOM and LF")

    workflow = root / ".github" / "workflows" / "build-protected.yml"
    text = workflow.read_text(encoding="utf-8-sig")
    new_lines: list[str] = []
    replaced_install = False
    for line in text.splitlines():
        stripped = line.strip()
        is_bare_install = bool(re.match(r"^npm\s+install(?:\s+--[A-Za-z0-9_-]+(?:=[^\s]+)?)*$", stripped))
        should_replace = bool(re.match(r"^npm\s+ci(?:\s.*)?$", stripped)) or is_bare_install
        if should_replace:
            indent = line[: len(line) - len(line.lstrip())]
            replacement = indent + BASE_INSTALL
            new_lines.append(replacement)
            if replacement != line:
                replaced_install = True
        else:
            new_lines.append(line)
    text2 = "\n".join(new_lines) + "\n"
    if replaced_install:
        changes.append("replaced stale npm ci/bare install with deliberate no-lock npm install")
    if BASE_INSTALL not in text2:
        raise RuntimeError("Protected workflow is missing the required no-lock npm install command.")
    if OBFUSCATOR_INSTALL not in text2:
        base_line = next(line for line in text2.splitlines() if BASE_INSTALL in line)
        indent = base_line[: len(base_line) - len(base_line.lstrip())]
        text2 = text2.replace(base_line + "\n", base_line + "\n" + indent + OBFUSCATOR_INSTALL + "\n", 1)
        changes.append("added pinned javascript-obfuscator install to workflow")
    if GIT_CONFIG_COMMAND not in text2:
        checkout = "      - name: Check out private source\n        uses: actions/checkout@v4\n"
        pre = (
            "      - name: Disable Git line-ending conversion\n"
            "        shell: bash\n"
            "        run: git config --global core.autocrlf false\n\n"
        )
        if checkout not in text2:
            raise RuntimeError("Protected workflow checkout step is not in the expected form.")
        text2 = text2.replace(checkout, pre + checkout, 1)
        changes.append("added pre-checkout Git line-ending protection")
    _write_text_if_changed(workflow, text2)

    return changes


def verify(root: Path) -> dict:
    errors: list[str] = []
    package_path = root / "package.json"
    workflow = root / ".github" / "workflows" / "build-protected.yml"
    if not package_path.is_file():
        errors.append("package.json is missing")
    else:
        try:
            data = json.loads(package_path.read_text(encoding="utf-8-sig"))
            version = str((data.get("dependencies") or {}).get("adm-zip") or "")
            if version != ADM_ZIP_VERSION:
                errors.append(f"package.json must pin adm-zip exactly to {ADM_ZIP_VERSION}; found {version or 'missing'}")
        except Exception as exc:
            errors.append(f"package.json is unreadable: {exc}")

    for name in LOCK_FILES:
        if (root / name).exists():
            errors.append(f"{name} must not exist in the deliberate no-lock private source")

    attrs = root / ".gitattributes"
    attr_lines = attrs.read_text(encoding="utf-8-sig").splitlines() if attrs.exists() else []
    if GIT_ATTRIBUTES_RULE not in [line.strip() for line in attr_lines]:
        errors.append(".gitattributes must contain '* -text' to preserve exact bytes across CI runners")

    for rel in BATCH_FILES:
        path = root / rel
        if not path.is_file():
            errors.append(f"required Windows batch file is missing: {rel}")
            continue
        raw = path.read_bytes()
        if raw.startswith(UTF8_BOM):
            errors.append(f"Windows batch file must not contain a UTF-8 BOM: {rel}")
        if not raw.lower().startswith(b"@echo"):
            errors.append(f"Windows batch file must begin with @echo at byte zero: {rel}")
        if not _has_only_crlf(raw):
            errors.append(f"Windows batch file must use CRLF only: {rel}")

    for rel in NO_BOM_UTF8_FILES:
        path = root / rel
        if not path.is_file():
            errors.append(f"required BOM-free UTF-8 file is missing: {rel}")
            continue
        if path.read_bytes().startswith(UTF8_BOM):
            errors.append(f"file must not contain a UTF-8 BOM: {rel}")

    for rel in VBS_FILES:
        path = root / rel
        if not path.is_file():
            errors.append(f"required Windows Script Host launcher is missing: {rel}")
            continue
        raw = path.read_bytes()
        if raw.startswith(UTF8_BOM):
            errors.append(f"{rel} has a UTF-8 BOM; Windows Script Host will reject it (800A0408)")
        if not _has_only_crlf(raw):
            errors.append(f"Windows Script Host launcher must use CRLF only: {rel}")
        if not raw.lower().startswith(b"option explicit"):
            errors.append(f"Windows Script Host launcher must begin with Option Explicit at byte zero: {rel}")

    for rel in POSIX_SCRIPT_FILES:
        path = root / rel
        if not path.is_file():
            errors.append(f"required POSIX script is missing: {rel}")
            continue
        raw = path.read_bytes()
        if raw.startswith(UTF8_BOM):
            errors.append(f"POSIX script must not contain a UTF-8 BOM before its shebang: {rel}")
        if not _has_only_lf(raw):
            errors.append(f"POSIX script must use LF only: {rel}")
        if not raw.startswith(b"#!"):
            errors.append(f"POSIX script shebang must begin at byte zero: {rel}")

    if not workflow.is_file():
        errors.append(".github/workflows/build-protected.yml is missing")
    else:
        text = workflow.read_text(encoding="utf-8-sig")
        if re.search(r"(?m)^\s*npm\s+ci(?:\s.*)?$", text):
            errors.append("workflow still uses npm ci")
        if BASE_INSTALL not in text:
            errors.append("workflow is missing the required no-lock npm install command")
        if OBFUSCATOR_INSTALL not in text:
            errors.append("workflow is missing the pinned javascript-obfuscator install command")
        if GIT_CONFIG_COMMAND not in text:
            errors.append("workflow must disable core.autocrlf before actions/checkout")
        elif text.index(GIT_CONFIG_COMMAND) > text.index("uses: actions/checkout@v4"):
            errors.append("workflow disables core.autocrlf too late; it must happen before checkout")

    gitignore = root / ".gitignore"
    gi = gitignore.read_text(encoding="utf-8-sig") if gitignore.exists() else ""
    for name in LOCK_FILES:
        if name not in gi.splitlines():
            errors.append(f".gitignore does not exclude {name}")

    return {
        "ok": not errors,
        "errors": errors,
        "adm_zip": ADM_ZIP_VERSION,
        "lock_design": "no-lock",
        "git_bytes": "exact (* -text + pre-checkout core.autocrlf=false)",
        "batch_line_endings": "UTF-8 no-BOM, CRLF",
        "posix_script_line_endings": "UTF-8 no-BOM, LF",
        "powershell_helper_encoding": "UTF-8 no-BOM",
        "vbs_launcher_encoding": "UTF-8 no-BOM, CRLF (WSH-safe)",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument("--repair", action="store_true")
    ap.add_argument("--report")
    args = ap.parse_args()
    root = Path(args.root).resolve()

    changes = repair(root) if args.repair else []
    result = verify(root)
    result["root"] = str(root)
    result["changes"] = changes
    if args.report:
        Path(args.report).write_text(json.dumps(result, indent=2), encoding="utf-8")
    for change in changes:
        print("REPAIRED:", change)
    if result["errors"]:
        for error in result["errors"]:
            print("ERROR:", error)
        return 1
    print("Private repository is byte-stable and consistent: adm-zip 0.5.17, no lock file, exact Git bytes, no-BOM CRLF batch files, BOM-free CRLF .vbs launchers, no-BOM LF POSIX scripts, BOM-free INSTANCE_PORT.ps1/STOP_CORE.ps1/RESTORE_PREVIOUS.ps1.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
