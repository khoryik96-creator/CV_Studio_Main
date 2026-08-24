#!/usr/bin/env python3
"""Repair/verify the private repository's deterministic protected-build state.

This owner-only helper prevents these known drift classes:
1. stale package-lock/npm-ci state overriding adm-zip@0.6.0;
2. Git line-ending conversion changing owner-vetted dependency bytes;
3. LF-only or BOM-bearing Windows batch files breaking cmd.exe;
4. BOM-bearing or CRLF macOS command scripts invalidating their shebangs;
5. BOM-bearing PowerShell port/stop helpers producing noisy or ambiguous starts;
6. UTF-8-BOM VBS launchers crashing Windows Script Host with 800A0408.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ADM_ZIP_VERSION = "0.6.0"
BASE_INSTALL = "npm install --ignore-scripts --no-audit --no-fund --package-lock=false"
OBFUSCATOR_INSTALL = "npm install --no-save --ignore-scripts --no-audit --no-fund --package-lock=false javascript-obfuscator@4.1.1"
GIT_CONFIG_COMMAND = "git config --global core.autocrlf false"
GIT_ATTRIBUTES_RULE = "* -text"
CHECKOUT_ACTION = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1"
PINNED_CHECKOUT_ACTION_RE = re.compile(
    r"actions/checkout@[0-9a-f]{40}\s+#\s+v\d+(?:\.\d+){0,2}"
)
LOCK_FILES = ("package-lock.json", "npm-shrinkwrap.json")
BATCH_FILES = (
    "CV Studio.bat",
    "INSTALL.bat",
    "INSTALL_CORE.bat",
    "MERGE_TITLE_CACHE.bat",
    "RESTORE_PREVIOUS.bat",
    "STOP.bat",
    "FORCE_STOP.bat",
    "UPDATE.bat",
    "owner_build_tools/BUILD_PROTECTED_WINDOWS.bat",
    "owner_build_tools/APPLY_PRIVATE_REPO_FIX_WINDOWS.bat",
)
NO_BOM_UTF8_FILES = (
    "INSTANCE_PORT.ps1",
    "STOP_CORE.ps1",
    "FORCE_STOP.ps1",
    "RESTORE_PREVIOUS.ps1",
    "PYTHON_RUNTIME.ps1",
    "UPDATE_CORE.ps1",
    "UPDATE_PREFLIGHT.ps1",
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
ANTIWORD_REQUIRED_HASHES = {
    "vendor/antiword/packages/antiword_1.3.5_windows_x64_r46.zip":
        "9a99f67680475605de009cb85ba94c7dc546eb261a4256d743597fbb24b0ddf8",
    "vendor/antiword/source/antiword_1.3.5.tar.gz":
        "72e84b33b54c11101cb70d63304ca0283f57a6d0ef518ca6329ff5e6490ad630",
    "vendor/antiword/GPL-2.0.txt":
        "edaef632cbb643e4e7a221717a6c441a4c1a7c918e6e4d56debc3d8739b233f6",
    "vendor/antiword/fixtures/UDHR-english.doc":
        "f430cdfe9446c4b943074d4bf804232761c284f2caa3d4125006b158d8b14af8",
    "vendor/antiword/windows-x64/SHA256SUMS":
        "7d365a89f268a2fc34f815b369474124bc6a1aac02e9b0b57e6dfd5eb5368da0",
    "vendor/antiword/packages/antiword_1.3.5_macos_x86_64_r46.tgz":
        "0416f1389dc01398cb820ec014e976a5c2198bb103a725f290efce1598f0fced",
    "vendor/antiword/packages/antiword_1.3.5_macos_arm64_r46.tgz":
        "1536939cca2c1b9cfcab7721c8982933bf8093eda0460f0e38055e7c826eae9a",
    "vendor/antiword/macos-intel/SHA256SUMS":
        "7e403a00b2acd1186c714bc55fe382f2b8a03fb5c430edd16e4d447e3f9f4ee8",
    "vendor/antiword/macos-arm64/SHA256SUMS":
        "6c59492af62df5d342c16b3126e588a4bbe855f3ba37f1f9120dc3e5352f6ce3",
}


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


def find_pinned_checkout_action(text: str) -> str | None:
    match = PINNED_CHECKOUT_ACTION_RE.search(text)
    return match.group(0) if match else None


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
        changes.append("pinned package.json adm-zip to 0.6.0")

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
        checkout = f"      - name: Check out private source\n        uses: {CHECKOUT_ACTION}\n"
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

    # The Windows installer's step 7/7 "Verifying Node DOCX runtime" check pins an
    # exact adm-zip version in a node one-liner (p.version!=='X'). Nothing else
    # cross-checked it against package.json/ADM_ZIP_VERSION, so it silently drifted
    # to 0.5.17 while the dependency moved to 0.6.0 -- every fresh install (source
    # AND protected) then failed step 7 because npm fetched the correct 0.6.0 that
    # the stale check rejected. Guard both the version-check one-liners and the
    # user-facing "adm-zip <ver>" messages so this class of drift cannot recur.
    installer_path = root / "INSTALL_CORE.ps1"
    if not installer_path.is_file():
        errors.append("INSTALL_CORE.ps1 is missing")
    else:
        installer_text = installer_path.read_text(encoding="utf-8-sig")
        pinned = re.findall(r"p\.version!=='([^']*)'", installer_text)
        if not pinned:
            errors.append(
                "INSTALL_CORE.ps1 no longer contains the adm-zip Node DOCX runtime "
                "version check (p.version!=='<ver>'); it may have been renamed or removed"
            )
        for found in pinned:
            if found != ADM_ZIP_VERSION:
                errors.append(
                    f"INSTALL_CORE.ps1 Node DOCX runtime check pins adm-zip {found} "
                    f"but must match package.json/ADM_ZIP_VERSION ({ADM_ZIP_VERSION})"
                )
        for found in re.findall(r"adm-zip (\d+\.\d+\.\d+)", installer_text):
            if found != ADM_ZIP_VERSION:
                errors.append(
                    f"INSTALL_CORE.ps1 references adm-zip {found} in a status message "
                    f"but must match ADM_ZIP_VERSION ({ADM_ZIP_VERSION})"
                )

    for name in LOCK_FILES:
        if (root / name).exists():
            errors.append(f"{name} must not exist in the deliberate no-lock private source")

    for relative, expected in ANTIWORD_REQUIRED_HASHES.items():
        path = root / relative
        if not path.is_file():
            errors.append(f"mandatory pinned Antiword artifact is missing: {relative}")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            errors.append(
                f"mandatory pinned Antiword artifact hash mismatch: {relative}"
            )
    if not (root / "cvstudio_antiword.py").is_file():
        errors.append("mandatory Antiword runtime verifier is missing: cvstudio_antiword.py")
    if not (root / "cvstudio_tesseract.py").is_file():
        errors.append("mandatory Tesseract runtime verifier is missing: cvstudio_tesseract.py")

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
        else:
            checkout_action = find_pinned_checkout_action(text)
            if checkout_action is None:
                errors.append("protected workflow must pin actions/checkout to a 40-character commit SHA")
            elif text.index(GIT_CONFIG_COMMAND) > text.index(f"uses: {checkout_action}"):
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
        "antiword": "1.3.5 pinned Windows x64, macOS Intel and macOS arm64 runtimes with corresponding source",
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
    print("Private repository is byte-stable and consistent: adm-zip 0.6.0, Antiword 1.3.5 Windows/macOS runtimes and source, mandatory Tesseract verifier, no lock file, exact Git bytes, no-BOM CRLF batch files, BOM-free CRLF .vbs launchers, no-BOM LF POSIX scripts, and BOM-free PowerShell helpers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
