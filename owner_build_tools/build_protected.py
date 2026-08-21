#!/usr/bin/env python3
"""Owner-only native protected colleague package builder for CV Studio.

This keeps the normal readable source untouched and emits a separate Nuitka
standalone package for the current host platform. Never distribute this file.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import importlib.util
import io
import json
import os
import platform
import re
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
import zlib
from pathlib import Path

VERSION = "v24.6.349"
VERSION_SLUG = "v24_6_349"
PRODUCT = "TheGuoLab-CVStudio"
RECEIPT_SCHEMA = 2
TOTP_MASK = bytes([147,57,36,83,116,245,122,57,165,162,176,168,249,50,204,128,45,174,232,56])
TOTP_MASKED = bytes([49,16,244,145,19,123,118,27,71,171,180,177,120,122,255,68,100,150,118,10])
ADM_ZIP_VERSION = "0.6.0"
# Aggregate hash of the vetted unpacked adm-zip 0.6.0 file tree. This catches
# a replaced/repacked dependency even when package.json still claims 0.6.0.
ADM_ZIP_TREE_SHA256 = "8f58883815becd3cf6e02bb67d8c8edff5787ec6a5477521411ad4666d480bce"
RELEASE_TARGETS = ("windows-x64", "macos-intel", "macos-arm64")

RUNTIME_ASSETS = ("index.html","generate.js","template.docx","cv_studio_logo.png","cv_studio.ico","vendor")
FRONTEND_MODULES = (
    "lazy-loader.js",
    "api-transport.js",
    "page-nav.js",
    "server-heartbeat.js",
    "candidate-summary.js",
    "blind-jd.js",
    "company-profile.js",
    "fcv-upload.js",
    "appearance.js",
    "cv-scoring.js",
    "docx-export.js",
    "the-owl.js",
    "ai-crawler.js",
    "ai-proxy.js",
    "ai-routing.js",
    "runtime-core.js",
    "jobadder-upload.js",
    "cv-format.js",
    "ai-keys.js",
    "tab-status.js",
    "lead-finder.js",
    "ppc.js",
    "batch-format.js",
    "screening-notes.js",
    "create-profile.js",
    "page-tabs.js",
    "stats.js",
    "hyppies-export.js",
    "settings.js",
    "locks.js",
    "input-file.js",
)
# Non-JS vendor assets served from /vendor/cvstudio/. Copied verbatim into the
# protected build - never node --check'd or obfuscated (they carry no logic).
FRONTEND_STATIC_ASSETS = (
    "app.css",
)
SALARY_COMPARISON_MODULES = (
    "salary_comparison/__init__.py",
    "salary_comparison/routes.py",
    "salary_comparison/calculator.py",
    "salary_comparison/fx_service.py",
    "salary_comparison/repository.py",
    "salary_comparison/validators.py",
    "salary_comparison/exporter.py",
    "salary_comparison/ai_rule_updater.py",
    "salary_comparison/bootstrap.py",
)
ROOT_FILES = (
    "CV Studio.bat","INSTALL.bat","INSTALL_CORE.bat","INSTALL_CORE.ps1","INSTALL_RECEIPT.ps1",
    "START_HIDDEN.vbs","STOP.bat","STOP_CORE.ps1","FORCE_STOP.bat","FORCE_STOP.ps1","WATCHDOG.vbs","INSTANCE_PORT.ps1","RESTORE_PREVIOUS.bat","RESTORE_PREVIOUS.ps1","install.sh","start.sh","restore_previous.sh",
    "package.json","requirements.txt","cv_studio_logo.png","cv_studio.ico",
)
BANNED_DIRS = {"__pycache__",".git",".pytest_cache",".mypy_cache"}
BANNED_FILES = {".DS_Store","package-lock.json","npm-shrinkwrap.json","startup_authorization_error.txt","startup_timing.log","install_health_report.json","install_log.txt"}
BANNED_SUFFIXES = {".pyc",".pyo",".bak"}


def run(cmd: list[str], *, cwd: Path | None = None, env: dict[str,str] | None = None,
        timeout: int | None = None) -> subprocess.CompletedProcess:
    print("+", " ".join(map(str,cmd)), flush=True)
    result = subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env,
                            text=True, capture_output=True, timeout=timeout)
    if result.stdout: print(result.stdout, end="")
    if result.stderr: print(result.stderr, end="", file=sys.stderr)
    if result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(cmd)}")
    return result


def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""): h.update(block)
    return h.hexdigest()


def sha256_tree(root: Path) -> str:
    """Return a deterministic aggregate hash on Windows, macOS and Linux.

    Sorting ``Path`` objects directly is platform-dependent: WindowsPath uses
    case-insensitive ordering while PosixPath uses case-sensitive ordering. The
    vetted adm-zip tree contains an uppercase ``LICENSE`` file, so v24.6.190
    produced a false integrity failure on Windows despite identical bytes. Sort
    by the explicit POSIX relative-path string instead.
    """
    h=hashlib.sha256()
    files=[p for p in root.rglob("*") if p.is_file()]
    for path in sorted(files, key=lambda p: p.relative_to(root).as_posix()):
        rel=path.relative_to(root).as_posix().encode("utf-8")
        h.update(rel+b"\0"+bytes.fromhex(sha256_file(path)))
    return h.hexdigest()


def detect_target(value: str) -> str:
    if value != "auto": return value
    system=platform.system().lower(); machine=platform.machine().lower()
    if system=="windows" and machine in {"amd64","x86_64"}: return "windows-x64"
    if system=="darwin" and machine in {"arm64","aarch64"}: return "macos-arm64"
    if system=="darwin" and machine in {"amd64","x86_64"}: return "macos-intel"
    raise RuntimeError("CV Studio protected builds require native Windows x64, Intel macOS, or Apple Silicon macOS.")


def validate_target_host(target: str) -> None:
    system=platform.system().lower(); machine=platform.machine().lower()
    if target not in RELEASE_TARGETS: raise RuntimeError("Unsupported protected target: "+target)
    if target=="windows-x64" and (system!="windows" or machine not in {"amd64","x86_64"}): raise RuntimeError("Windows x64 packages require native Windows x64.")
    if target=="macos-intel" and (system!="darwin" or machine not in {"amd64","x86_64"}): raise RuntimeError("Intel macOS packages require a native Intel Mac runner.")
    if target=="macos-arm64" and (system!="darwin" or machine not in {"arm64","aarch64"}): raise RuntimeError("Apple Silicon packages require a native arm64 Mac runner.")



def validate_repository_dependency_state(root: Path) -> None:
    """Reject stale lock/workflow drift before an expensive native build."""
    package_path = root / "package.json"
    data = json.loads(package_path.read_text(encoding="utf-8-sig"))
    version = str((data.get("dependencies") or {}).get("adm-zip") or "")
    if version != ADM_ZIP_VERSION:
        raise RuntimeError(f"package.json must pin adm-zip exactly to {ADM_ZIP_VERSION}; found {version or 'missing'}.")
    stale = [name for name in ("package-lock.json", "npm-shrinkwrap.json") if (root / name).exists()]
    if stale:
        raise RuntimeError(
            "Stale npm lock file(s) conflict with the deliberate no-lock protected build: "
            + ", ".join(stale)
            + ". Run owner_build_tools/repo_consistency.py --root . --repair."
        )
    workflow = root / ".github" / "workflows" / "build-protected.yml"
    if not workflow.is_file():
        raise RuntimeError("Protected GitHub workflow is missing from the private source.")
    workflow_text = workflow.read_text(encoding="utf-8-sig")
    if re.search(r"(?m)^\s*npm\s+ci(?:\s.*)?$", workflow_text):
        raise RuntimeError("Protected workflow still uses npm ci. Replace it with the current owner-kit workflow.")
    required = "npm install --ignore-scripts --no-audit --no-fund --package-lock=false"
    if required not in workflow_text:
        raise RuntimeError("Protected workflow is missing the required deterministic no-lock npm install command.")
    attrs = root / ".gitattributes"
    attr_lines = attrs.read_text(encoding="utf-8-sig").splitlines() if attrs.is_file() else []
    if "* -text" not in [line.strip() for line in attr_lines]:
        raise RuntimeError(".gitattributes must contain '* -text' before protected CI builds.")
    git_guard = "git config --global core.autocrlf false"
    if git_guard not in workflow_text or workflow_text.index(git_guard) > workflow_text.index("uses: actions/checkout@v4"):
        raise RuntimeError("Protected workflow must disable core.autocrlf before actions/checkout.")
    batch_files = (
        "CV Studio.bat", "INSTALL.bat", "INSTALL_CORE.bat", "MERGE_TITLE_CACHE.bat", "RESTORE_PREVIOUS.bat", "STOP.bat", "FORCE_STOP.bat",
        "owner_build_tools/BUILD_PROTECTED_WINDOWS.bat",
        "owner_build_tools/APPLY_PRIVATE_REPO_FIX_WINDOWS.bat",
    )
    posix_files = (
        "install.sh", "start.sh", "restore_previous.sh",
        "owner_build_tools/BUILD_PROTECTED_MAC.command",
        "owner_build_tools/APPLY_PRIVATE_REPO_FIX_MAC.command",
    )
    for rel in batch_files:
        raw = (root / rel).read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            raise RuntimeError(f"Windows batch file contains a UTF-8 BOM: {rel}. Run repo_consistency.py --repair.")
        if not raw.lower().startswith(b"@echo"):
            raise RuntimeError(f"Windows batch file does not begin with @echo at byte zero: {rel}. Run repo_consistency.py --repair.")
        if b"\n" in raw.replace(b"\r\n", b"") or b"\r" in raw.replace(b"\r\n", b""):
            raise RuntimeError(f"Windows batch file is not CRLF-only: {rel}. Run repo_consistency.py --repair.")
    for rel in ("START_HIDDEN.vbs", "WATCHDOG.vbs"):
        raw = (root / rel).read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            raise RuntimeError(f"{rel} contains a UTF-8 BOM; Windows Script Host will reject it (800A0408). Run repo_consistency.py --repair.")
        if b"\n" in raw.replace(b"\r\n", b"") or b"\r" in raw.replace(b"\r\n", b""):
            raise RuntimeError(f"{rel} is not CRLF-only. Run repo_consistency.py --repair.")
        if not raw.lower().startswith(b"option explicit"):
            raise RuntimeError(f"{rel} does not begin with Option Explicit at byte zero.")
    for rel in ("INSTANCE_PORT.ps1", "STOP_CORE.ps1", "FORCE_STOP.ps1", "RESTORE_PREVIOUS.ps1"):
        helper_raw = (root / rel).read_bytes()
        if helper_raw.startswith(b"\xef\xbb\xbf"):
            raise RuntimeError(f"{rel} contains a UTF-8 BOM. Run repo_consistency.py --repair.")
    for rel in posix_files:
        raw = (root / rel).read_bytes()
        if raw.startswith(b"\xef\xbb\xbf") or not raw.startswith(b"#!"):
            raise RuntimeError(f"POSIX script shebang is not at byte zero: {rel}. Run repo_consistency.py --repair.")
        if b"\r" in raw:
            raise RuntimeError(f"POSIX script is not LF-only: {rel}. Run repo_consistency.py --repair.")

def validate_source(root: Path) -> None:
    required=("app.py","cvstudio_architecture.py","cvstudio_ai_costs.py","cvstudio_ai_providers.py","cvstudio_antiword.py","cvstudio_tesseract.py","cvstudio_clients.py","cvstudio_storage.py","cvstudio_storage_bridge.py","cvstudio_diagnostics.py","cvstudio_document_safety.py","cvstudio_jobs.py","cvstudio_startup.py","cvstudio_runtime.py","cvstudio_web_assets.py","cvstudio_secrets.py","cvstudio_jobadder_request.py","cvstudio_jobadder_read.py","cvstudio_jobadder_write.py","cvstudio_onenote_text.py","cvstudio_outlook_crypto.py","cvstudio_cv_normalize.py","cvstudio_cv_reconcile.py","cvstudio_cv_fidelity.py","cvstudio_lead_match.py","cvstudio_lead_enrich.py","cvstudio_lead_cache.py","cvstudio_lead_search.py","cvstudio_spider_boolean.py","cvstudio_spider_summary.py","cvstudio_spider_score.py","cvstudio_spider_documents.py","cvstudio_ja_typos.py","cvstudio_salary_parse.py","cvstudio_ja_answers.py","cvstudio_ja_activity.py","cvstudio_ja_screening.py","cvstudio_ja_salary_notice.py","cvstudio_ja_salary_ai.py","cvstudio_blind_mask.py","cvstudio_ppc.py","cvstudio_msgraph.py","cvstudio_onenote_desktop.py","index.html","generate.js","template.docx","package.json","requirements.txt","merge_title_cache.py") + tuple(
        "vendor/cvstudio/" + filename for filename in FRONTEND_MODULES
    ) + tuple(
        "vendor/cvstudio/" + filename for filename in FRONTEND_STATIC_ASSETS
    ) + SALARY_COMPARISON_MODULES
    missing=[x for x in required if not (root/x).exists()]
    if missing: raise RuntimeError("Missing source files: "+", ".join(missing))
    # Build only from the readable owner patch base. The separate Authy QR/key
    # folder is not required for compilation and may be excluded from a private
    # CI repository; the owner marker and real source distinguish this from a
    # protected colleague package.
    if not (root/"KEEP_PRIVATE_PATCH_BASE.txt").is_file():
        raise RuntimeError("Private patch-base marker is absent; refusing to build from a colleague package.")
    app_text=(root/"app.py").read_text(encoding="utf-8-sig")
    if "SYSTEM_PROMPT" not in app_text or len(app_text)<100000:
        raise RuntimeError("Readable owner backend source is absent; refusing to build from a colleague package.")
    if VERSION not in app_text or VERSION not in (root/"index.html").read_text(encoding="utf-8-sig"):
        raise RuntimeError(f"Source version surfaces do not contain {VERSION}.")
    validate_repository_dependency_state(root)


def validate_antiword_runtime(
    root: Path,
    target: str | None = None,
    vendor_root: Path | None = None,
) -> dict:
    module_path = root / "cvstudio_antiword.py"
    spec = importlib.util.spec_from_file_location(
        "cvstudio_antiword_build_validation", module_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Mandatory Antiword verifier could not be loaded.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    vendor = (
        Path(vendor_root)
        if vendor_root is not None
        else root / "vendor" / "antiword"
    )
    for relative, expected in module.ANTIWORD_DISTRIBUTION_HASHES.items():
        artifact = vendor / relative
        if not artifact.is_file() or module._sha256_file(artifact) != expected:
            raise RuntimeError(
                "Mandatory Antiword distribution artifact failed verification: "
                + relative
            )
    for tag, config in module._PLATFORMS.items():
        runtime = vendor / tag
        entries = module._parse_manifest(
            runtime, str(config["manifest_sha256"])
        )
        actual = {
            path.relative_to(runtime).as_posix()
            for path in module._safe_runtime_files(runtime)
        }
        if actual != set(entries):
            raise RuntimeError(
                f"Mandatory Antiword {tag} runtime file set is invalid."
            )
        for relative, expected in entries.items():
            if module._sha256_file(runtime / relative) != expected:
                raise RuntimeError(
                    f"Mandatory Antiword {tag} runtime hash failed: {relative}"
                )
    if target == "linux-x64-test":
        return {
            "available": False,
            "trusted": True,
            "functional": False,
            "platform": "linux-x64-test",
            "version": module.ANTIWORD_PACKAGE_VERSION,
            "static_platform_manifests_verified": len(module._PLATFORMS),
            "test_only": True,
        }
    tag = str(target or "") or module._platform_tag()
    if tag not in module._PLATFORMS:
        raise RuntimeError(
            "Mandatory Antiword native preflight target is unsupported: "
            + str(tag or "unknown")
        )
    _executable, health = module._verify_candidate(
        "bundled",
        vendor / tag,
        vendor / "fixtures" / "UDHR-english.doc",
        tag,
    )
    if not (
        health.get("available")
        and health.get("trusted")
        and health.get("functional")
        and health.get("manifest_verified")
        and health.get("functional_fixture_verified")
    ):
        raise RuntimeError(
            "Mandatory Antiword runtime failed native preflight: "
            + str(health.get("reason") or "unknown verification failure")
        )
    return health


def validate_tesseract_runtime(root: Path) -> dict:
    module_path = root / "cvstudio_tesseract.py"
    spec = importlib.util.spec_from_file_location("cvstudio_tesseract_build_validation", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Mandatory Tesseract verifier could not be loaded.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    health = module.tesseract_health(root)
    if not (health.get("available") and health.get("functional") and health.get("english_language_data")):
        raise RuntimeError("Mandatory Tesseract preflight failed: " + str(health.get("reason") or "unavailable"))
    return health


def vetted_adm_zip_dir(root: Path) -> Path:
    return root / "owner_build_tools" / "vetted_node" / "adm-zip"


def validate_vetted_adm_zip(root: Path) -> Path:
    """Validate the owner-bundled, platform-neutral adm-zip payload.

    The protected colleague package is built from this immutable owner copy,
    not from npm's working node_modules tree. npm may add harmless metadata or
    leave stale files on Windows; those must not make a valid build fail, and
    they must never enter the protected package.
    """
    adm_zip = vetted_adm_zip_dir(root)
    package_json = adm_zip / "package.json"
    if not package_json.is_file():
        raise RuntimeError("Owner-vetted adm-zip payload is missing. Re-extract the private owner build kit.")
    try:
        metadata = json.loads(package_json.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError("Owner-vetted adm-zip package.json is unreadable.") from exc
    if str(metadata.get("version") or "") != ADM_ZIP_VERSION:
        raise RuntimeError(f"Owner-vetted adm-zip version mismatch: expected {ADM_ZIP_VERSION}.")
    actual = sha256_tree(adm_zip)
    if actual != ADM_ZIP_TREE_SHA256:
        raise RuntimeError(
            "Owner-vetted adm-zip payload is damaged or changed. "
            f"Expected {ADM_ZIP_TREE_SHA256}, found {actual}. Re-extract the private owner build kit."
        )
    return adm_zip


def preflight_source(root: Path, target: str | None = None) -> None:
    run([sys.executable,"-m","py_compile",str(root/"app.py"),str(root/"cvstudio_architecture.py"),str(root/"cvstudio_ai_costs.py"),str(root/"cvstudio_ai_providers.py"),str(root/"cvstudio_antiword.py"),str(root/"cvstudio_tesseract.py"),str(root/"cvstudio_clients.py"),str(root/"cvstudio_storage.py"),str(root/"cvstudio_storage_bridge.py"),str(root/"cvstudio_diagnostics.py"),str(root/"cvstudio_document_safety.py"),str(root/"cvstudio_jobs.py"),str(root/"cvstudio_startup.py"),str(root/"cvstudio_runtime.py"),str(root/"cvstudio_web_assets.py"),str(root/"cvstudio_secrets.py"),str(root/"cvstudio_jobadder_request.py"),str(root/"cvstudio_jobadder_read.py"),str(root/"cvstudio_jobadder_write.py"),str(root/"cvstudio_onenote_text.py"),str(root/"cvstudio_outlook_crypto.py"),str(root/"cvstudio_cv_normalize.py"),str(root/"cvstudio_cv_reconcile.py"),str(root/"cvstudio_cv_fidelity.py"),str(root/"cvstudio_lead_match.py"),str(root/"cvstudio_lead_enrich.py"),str(root/"cvstudio_lead_cache.py"),str(root/"cvstudio_lead_search.py"),str(root/"cvstudio_spider_boolean.py"),str(root/"cvstudio_spider_summary.py"),str(root/"cvstudio_spider_score.py"),str(root/"cvstudio_spider_documents.py"),str(root/"cvstudio_ja_typos.py"),str(root/"cvstudio_salary_parse.py"),str(root/"cvstudio_ja_answers.py"),str(root/"cvstudio_ja_activity.py"),str(root/"cvstudio_ja_screening.py"),str(root/"cvstudio_ja_salary_notice.py"),str(root/"cvstudio_ja_salary_ai.py"),str(root/"cvstudio_blind_mask.py"),str(root/"cvstudio_ppc.py"),str(root/"cvstudio_msgraph.py"),str(root/"cvstudio_onenote_desktop.py"),str(root/"merge_title_cache.py")]+[str(root/rel) for rel in SALARY_COMPARISON_MODULES])
    run(["node","--check",str(root/"generate.js")])
    for filename in FRONTEND_MODULES:
        run(["node","--check",str(root/"vendor"/"cvstudio"/filename)])
    validate_vetted_adm_zip(root)
    health = validate_antiword_runtime(root, target)
    print(
        "Antiword preflight: "
        f"{health.get('platform')} {health.get('version')} "
        f"trusted={health.get('trusted')} functional={health.get('functional')}"
        + (
            " static-test-only=true"
            if health.get("test_only")
            else ""
        )
    )
    tesseract = validate_tesseract_runtime(root)
    print(
        "Tesseract preflight: "
        f"{tesseract.get('version')} functional={tesseract.get('functional')} "
        f"english={tesseract.get('english_language_data')}"
    )
    # The owner/source installation still needs a working local module for
    # direct source-mode DOCX generation and for the owner's own testing. Only
    # its exact version and behavior matter here; the protected artifact never
    # copies this mutable npm working tree.
    run(["node","-e",
         f"const p=require('adm-zip/package.json');if(p.version!=='{ADM_ZIP_VERSION}')process.exit(2);"
         "const A=require('adm-zip');const z=new A();z.addFile('probe.txt',Buffer.from('ok'));"
         "const b=z.toBuffer();if(new A(b).readAsText('probe.txt')!=='ok')process.exit(3);"],cwd=root)
    html=(root/"index.html").read_text(encoding="utf-8-sig")
    with tempfile.TemporaryDirectory(prefix="cvstudio-js-check-") as td:
        for i,body in enumerate(re.findall(r"(?is)<script(?:\s[^>]*)?>(.*?)</script>",html)):
            if not body.strip(): continue
            p=Path(td)/f"inline_{i}.js"; p.write_text(body,encoding="utf-8")
            run(["node","--check",str(p)])


def find_obfuscator(root: Path) -> Path | None:
    names=("javascript-obfuscator.cmd","javascript-obfuscator") if os.name=="nt" else ("javascript-obfuscator",)
    for name in names:
        for p in (root/"node_modules"/".bin"/name,Path.cwd()/"node_modules"/".bin"/name):
            if p.exists(): return p
    found=shutil.which("javascript-obfuscator")
    return Path(found) if found else None


def obfuscate_args(src: Path, dst: Path, rename_globals: bool) -> list[str]:
    return [str(src),"--output",str(dst),"--compact","true","--control-flow-flattening","false",
            "--dead-code-injection","false","--debug-protection","false","--disable-console-output","false",
            "--identifier-names-generator","hexadecimal","--log","false","--numbers-to-expressions","false",
            "--rename-globals","true" if rename_globals else "false","--self-defending","false","--simplify","true",
            "--split-strings","false","--string-array","true","--string-array-encoding","base64",
            "--string-array-threshold","0.45","--transform-object-keys","false","--unicode-escape-sequence","false"]


def protect_javascript(root: Path, work: Path, skip: bool) -> tuple[Path,Path,Path,dict]:
    source_index=root/"index.html"; source_generate=root/"generate.js"
    out_index=work/"index.html"; out_generate=work/"generate.js"
    source_modules=root/"vendor"/"cvstudio"; out_modules=work/"vendor"/"cvstudio"
    out_modules.mkdir(parents=True,exist_ok=True)
    report={"mode":"copy","inline_blocks":0,
            "source_sha256":{"index.html":sha256_file(source_index),"generate.js":sha256_file(source_generate)},
            "protected_sha256":{},
            "frontend_modules":{"mode":"copy","source_sha256":{},"protected_sha256":{}}}
    for filename in FRONTEND_MODULES:
        report["frontend_modules"]["source_sha256"][filename]=sha256_file(source_modules/filename)
    ob=None if skip else find_obfuscator(root)
    if ob is None:
        if not skip: raise RuntimeError("javascript-obfuscator is required. Run npm install --no-save javascript-obfuscator@4.1.1")
        shutil.copy2(source_index,out_index); shutil.copy2(source_generate,out_generate)
        for filename in FRONTEND_MODULES:
            shutil.copy2(source_modules/filename,out_modules/filename)
    else:
        html=source_index.read_text(encoding="utf-8-sig")
        pat=re.compile(r"(?is)(<script([^>]*)>)(.*?)(</script>)")
        pieces=[]; cursor=0; block=0
        for m in pat.finditer(html):
            pieces.append(html[cursor:m.start()]); open_tag,attrs,body,close=m.group(1),m.group(2),m.group(3),m.group(4)
            if "src=" in attrs.lower() or len(body.strip())<1000:
                pieces.append(m.group(0))
            else:
                block+=1; src=work/f"inline_{block}.source.js"; dst=work/f"inline_{block}.protected.js"
                src.write_text(body,encoding="utf-8")
                run([str(ob)]+obfuscate_args(src,dst,False),cwd=root,timeout=300)
                pieces.append(open_tag+dst.read_text(encoding="utf-8")+close)
            cursor=m.end()
        pieces.append(html[cursor:]); out_index.write_text("".join(pieces),encoding="utf-8")
        run([str(ob)]+obfuscate_args(source_generate,out_generate,True),cwd=root,timeout=300)
        for filename in FRONTEND_MODULES:
            run(
                [str(ob)]+obfuscate_args(source_modules/filename,out_modules/filename,False),
                cwd=root,
                timeout=300,
            )
        report.update(mode="javascript-obfuscator-conservative",inline_blocks=block)
        report["frontend_modules"]["mode"]="javascript-obfuscator-conservative"
    # Non-JS vendor assets (e.g. app.css) are copied verbatim regardless of the
    # obfuscation mode; they carry no logic so they are never node --check'd.
    report["frontend_static_assets"]={"mode":"copy","source_sha256":{},"protected_sha256":{}}
    for filename in FRONTEND_STATIC_ASSETS:
        shutil.copy2(source_modules/filename,out_modules/filename)
        report["frontend_static_assets"]["source_sha256"][filename]=sha256_file(source_modules/filename)
        report["frontend_static_assets"]["protected_sha256"][filename]=sha256_file(out_modules/filename)
    run(["node","--check",str(out_generate)])
    for filename in FRONTEND_MODULES:
        run(["node","--check",str(out_modules/filename)])
        report["frontend_modules"]["protected_sha256"][filename]=sha256_file(out_modules/filename)
    for i,body in enumerate(re.findall(r"(?is)<script(?:\s[^>]*)?>(.*?)</script>",out_index.read_text(encoding="utf-8"))):
        if not body.strip(): continue
        p=work/f"protected_inline_{i}.js"; p.write_text(body,encoding="utf-8"); run(["node","--check",str(p)])
    report["protected_sha256"]={"index.html":sha256_file(out_index),"generate.js":sha256_file(out_generate)}
    return out_index,out_generate,out_modules,report


def _seal_native_text(value: str, seed: str) -> str:
    raw=value.encode("utf-8")
    comp=zlib.compress(raw,9)
    key=hashlib.sha256(seed.encode("utf-8")).digest()
    cipher=bytes(b^key[i%len(key)]^((i*29+73)&255) for i,b in enumerate(comp))
    return base64.b85encode(cipher).decode("ascii")


def prepare_native_source(root: Path, work: Path) -> tuple[Path,dict]:
    """Seal the two largest proprietary prompt constants before native compile.

    The readable owner source remains untouched. This does not make an offline
    binary impossible to reverse engineer, but it prevents ordinary `strings`
    scans from exposing the complete CV-formatting/anonymising prompts.
    """
    source_path=root/"app.py"
    source_bytes=source_path.read_bytes()
    source_text=source_bytes.decode("utf-8-sig")
    # Work with BOM-free UTF-8 bytes because AST column offsets are UTF-8 byte
    # offsets. The staged file intentionally does not need a BOM.
    body=source_text.encode("utf-8")
    tree=__import__("ast").parse(source_text)
    line_starts=[0]
    for line in body.splitlines(keepends=True): line_starts.append(line_starts[-1]+len(line))
    targets={"SYSTEM_PROMPT","BLIND_SYSTEM_PROMPT"}
    replacements=[]; report={"sealed_constants":{},"mode":"zlib-xor-b85-runtime-decode"}
    for node in tree.body:
        if not isinstance(node,__import__("ast").Assign) or not isinstance(node.value,__import__("ast").Constant) or not isinstance(node.value.value,str):
            continue
        names={t.id for t in node.targets if isinstance(t,__import__("ast").Name)}
        matched=targets & names
        if not matched: continue
        name=sorted(matched)[0]
        seed=f"CVStudio|{VERSION}|native-prompt|{name}|TheGuoLab"
        payload=_seal_native_text(node.value.value,seed)
        expression=f'_cvstudio_unseal_native_text({payload!r},{seed!r})'.encode("ascii")
        start=line_starts[node.value.lineno-1]+node.value.col_offset
        end=line_starts[node.value.end_lineno-1]+node.value.end_col_offset
        replacements.append((start,end,expression))
        report["sealed_constants"][name]={"source_chars":len(node.value.value),"payload_chars":len(payload),"source_sha256":hashlib.sha256(node.value.value.encode("utf-8")).hexdigest()}
    missing=targets-set(report["sealed_constants"])
    if missing: raise RuntimeError("Could not locate proprietary prompt constants: "+", ".join(sorted(missing)))
    for start,end,replacement in sorted(replacements,reverse=True): body=body[:start]+replacement+body[end:]
    first=min(start for start,_,_ in replacements)
    helper=(
        b"\n# Build-generated native prompt unsealer. Owner source remains readable.\n"
        b"def _cvstudio_unseal_native_text(_payload,_seed):\n"
        b" import base64 as _b,hashlib as _h,zlib as _z\n"
        b" _c=_b.b85decode(_payload.encode('ascii'));_k=_h.sha256(_seed.encode('utf-8')).digest()\n"
        b" _x=bytes(v^_k[i%len(_k)]^((i*29+73)&255) for i,v in enumerate(_c))\n"
        b" return _z.decompress(_x).decode('utf-8')\n\n"
    )
    # Insert at the beginning of the first prompt assignment line, after all
    # imports/helpers that the application has already defined.
    line_start=body.rfind(b"\n",0,first)+1
    body=body[:line_start]+helper+body[line_start:]
    staged=work/"app.native_protected.py"
    staged.write_bytes(body)
    __import__("ast").parse(staged.read_text(encoding="utf-8"))
    staged_text=staged.read_text(encoding="utf-8")
    for name,meta in report["sealed_constants"].items():
        # The full source prompt must not survive in the staged compile input.
        original_hash=meta["source_sha256"]
        if original_hash==hashlib.sha256(staged_text.encode("utf-8")).hexdigest():
            raise RuntimeError("Prompt sealing verification failed for "+name)
    if "You are a professional CV parser" in staged_text or "You are a CV anonymisation specialist" in staged_text:
        raise RuntimeError("Plaintext proprietary prompt remained in native compile source")
    report["staged_sha256"]=sha256_file(staged)
    return staged,report


def compile_native(root: Path, work: Path, target: str, source_entry: Path | None = None) -> tuple[Path,Path]:
    out=work/"nuitka-output"; out.mkdir()
    report=work/f"nuitka-{target}-report.xml"
    cmd=[sys.executable,"-m","nuitka","--mode=standalone","--assume-yes-for-downloads",
         "--low-memory","--jobs=1","--output-dir="+str(out),"--output-filename=CVStudio",
         "--report="+str(report),"--include-package-data=certifi",
         "--include-package=pypdfium2","--include-package=pypdfium2_raw",
         "--include-package-data=pypdfium2","--include-package-data=pypdfium2_raw",
         # The salary_comparison blueprint ships non-Python assets (data/*.json
         # seed files, Jinja templates, static CSS/JS). Nuitka standalone omits
         # package data unless told, so the protected build must bundle them or
         # the module fails at runtime (missing seed data -> ensure_data_dir
         # FileNotFoundError; missing templates -> render_template error).
         "--include-package=salary_comparison","--include-package-data=salary_comparison",
         # Waitress is imported lazily inside app._run_cvstudio_server() (so the
         # dev-server fallback still works if it is absent). Nuitka does not
         # follow that conditional import, so force it in -- otherwise the frozen
         # build ships without Waitress and silently serves on the Werkzeug dev
         # server instead of the intended production server.
         "--include-package=waitress"]
    if target=="windows-x64":
        cmd += ["--windows-console-mode=disable","--windows-icon-from-ico="+str(root/"cv_studio.ico")]
        # Imports are present in app.py and followed by Nuitka. Keep explicit
        # modules small; do not force the whole win32com package tree.
        try:
            import importlib.util
            if importlib.util.find_spec("pythoncom"):
                cmd += ["--include-module=pythoncom","--include-module=pywintypes","--include-module=win32com.client"]
        except Exception: pass
    cmd.append(str(source_entry or (root/"app.py")))
    run(cmd,cwd=root,timeout=5400)
    dist_dirs=sorted(out.glob("*.dist"),key=lambda p:p.stat().st_mtime,reverse=True)
    if not dist_dirs: raise RuntimeError("Nuitka did not produce a .dist directory.")
    dist=dist_dirs[0]
    exe=next((p for p in sorted(dist.iterdir(),key=lambda p:len(p.name)) if p.is_file() and p.name.lower().startswith("cvstudio")),None)
    if exe is None: raise RuntimeError("Compiled CVStudio executable missing.")
    if target.startswith("macos-"):
        run(["codesign","--force","--deep","--sign","-","--timestamp=none",str(exe)],timeout=300)
        run(["codesign","--verify","--deep","--strict",str(exe)],timeout=120)
    return dist,report


def copy_item(src: Path,dst: Path) -> None:
    if src.is_dir(): shutil.copytree(src,dst,dirs_exist_ok=True)
    else: dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)


def prune(root: Path) -> None:
    for p in sorted(root.rglob("*"),key=lambda x:len(x.parts),reverse=True):
        if p.is_dir() and p.name in BANNED_DIRS: shutil.rmtree(p,ignore_errors=True)
        elif p.is_file() and (p.name in BANNED_FILES or p.suffix.lower() in BANNED_SUFFIXES or "startup.log" in p.name.lower() or p.name.lower().endswith(".map")):
            p.unlink(missing_ok=True)


def encode_source_removed(data: bytes, seed_text: str) -> bytes:
    comp=zlib.compress(data,9); seed=hashlib.sha256(seed_text.encode()).digest()
    return base64.b85encode(bytes(b^seed[i%len(seed)]^((i*31+17)&255) for i,b in enumerate(comp)))


def helper_stub(payload: str) -> str:
    seed=f"merge_title_cache.py|CVStudio|{VERSION}|TheGuoLab"
    return f'''# CV Studio source-removed helper launcher\nimport base64 as _b,hashlib as _h,os as _o,zlib as _z\n_R=_o.path.dirname(_o.path.abspath(__file__));_P=_o.path.join(_R,"runtime",{payload!r});_S={seed!r}\ndef _l():\n e=_b.b85decode(open(_P,"rb").read());s=_h.sha256(_S.encode()).digest();c=bytes(x^s[i%len(s)]^((i*31+17)&255) for i,x in enumerate(e));return _z.decompress(c).decode("utf-8")\nexec(compile(_l(),_o.path.join(_R,"merge_title_cache.py"),"exec"),{{"__name__":"__main__","__file__":_o.path.join(_R,"merge_title_cache.py")}})\n'''


def launcher_stub(binary: str) -> str:
    return f'''# CV Studio native protected launcher
# Readable backend source is not included.
import os,subprocess,sys
R=os.path.dirname(os.path.abspath(__file__));B=os.path.join(R,"runtime","native",{binary!r})
if not os.path.isfile(B): raise SystemExit("Protected CV Studio runtime is missing. Re-extract the package.")
try: os.chmod(B,os.stat(B).st_mode|0o111)
except Exception: pass
A=[B]+sys.argv[1:]
if os.name=="nt":
 F=int(getattr(subprocess,"CREATE_NO_WINDOW",0))|int(getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0))
 subprocess.Popen(A,cwd=R,creationflags=F,close_fds=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 raise SystemExit(0)
os.execv(B,A)
'''

def patch_launchers(root: Path,target: str) -> None:
    """Validate platform launchers; source files are already cross-platform aware."""
    if target=="windows-x64":
        for rel in ("START_HIDDEN.vbs", "WATCHDOG.vbs"):
            raw=(root/rel).read_bytes()
            if raw.startswith(b"\xef\xbb\xbf"):
                raise RuntimeError(f"{rel} contains a UTF-8 BOM; Windows Script Host will reject it (800A0408).")
        start=(root/"START_HIDDEN.vbs").read_text(encoding="utf-8")
        stop=(root/"STOP.bat").read_text(encoding="utf-8-sig")
        stop_core=(root/"STOP_CORE.ps1").read_text(encoding="utf-8-sig")
        watchdog=(root/"WATCHDOG.vbs").read_text(encoding="utf-8")
        helper=(root/"INSTANCE_PORT.ps1").read_text(encoding="utf-8-sig")
        if r"runtime\native\CVStudio.exe" not in start or "ServerXMLHTTP.6.0" not in start or "/instance-id" not in start:
            raise RuntimeError("Windows hidden launcher lacks native/timeout/instance validation.")
        if "STOP_CORE.ps1" not in stop or "cvstudio.$instance.pid.json" not in stop_core or "INSTANCE_PORT.ps1" not in stop_core or "-Mode Stop" not in stop_core:
            raise RuntimeError("Windows shutdown is not instance/PID/port-identity scoped.")
        if r"runtime\native\CVStudio.exe" not in watchdog or "/instance-id" not in watchdog:
            raise RuntimeError("Windows watchdog lacks native package identity checks.")
        if "ExpectedPid" not in helper or "Get-NetTCPConnection" not in helper or "/instance" not in helper or "root_hash" not in helper or "Stop-CVStudioWatchdogs" not in helper:
            raise RuntimeError("Windows verified port ownership/watchdog helper is missing.")
        restore_ps=(root/"RESTORE_PREVIOUS.ps1").read_text(encoding="utf-8-sig")
        restore_bat=(root/"RESTORE_PREVIOUS.bat").read_text(encoding="utf-8-sig")
        if "update_state.json" not in restore_ps or "install_receipt.before_restore" not in restore_ps or "CV Studio.lnk" not in restore_ps or "RESTORE_PREVIOUS.ps1" not in restore_bat:
            raise RuntimeError("Windows transactional rollback launcher is missing or incomplete.")
        force_bat=(root/"FORCE_STOP.bat").read_text(encoding="utf-8-sig")
        force_ps=(root/"FORCE_STOP.ps1").read_text(encoding="utf-8-sig")
        if "FORCE_STOP.ps1" not in force_bat or "Get-NetTCPConnection" not in force_ps or "watchdog.vbs" not in force_ps.lower() or "LocalPort 5000" not in force_ps:
            raise RuntimeError("Windows FORCE_STOP launcher is missing or not port-5000/watchdog scoped.")
    elif target.startswith("macos-"):
        start=(root/"start.sh").read_text(encoding="utf-8-sig")
        install=(root/"install.sh").read_text(encoding="utf-8-sig")
        restore=(root/"restore_previous.sh").read_text(encoding="utf-8-sig")
        if "--connect-timeout 2 --max-time 4" not in start or "/instance-id" not in start:
            raise RuntimeError("macOS launcher lacks bounded package identity checks.")
        if "Protected native backend detected" not in install or "install-receipt-v1" not in install or "Verifying mandatory Antiword" not in install:
            raise RuntimeError("macOS installer lacks native receipt or mandatory dependency checks.")
        if "update_state.json" not in restore or "install_receipt.before_restore" not in restore or "CV Studio.command" not in restore:
            raise RuntimeError("macOS transactional rollback launcher is missing or incomplete.")


def prune_target_incompatible_launchers(root: Path, target: str) -> None:
    """Do not ship launchers for an operating system the artifact cannot run on."""
    if target == "windows-x64":
        remove = ("install.sh", "start.sh", "restore_previous.sh")
    elif target.startswith("macos-"):
        remove = (
            "CV Studio.bat", "INSTALL.bat", "INSTALL_CORE.bat", "INSTALL_CORE.ps1",
            "INSTALL_RECEIPT.ps1", "START_HIDDEN.vbs", "STOP.bat", "STOP_CORE.ps1",
            "WATCHDOG.vbs", "INSTANCE_PORT.ps1", "RESTORE_PREVIOUS.bat",
            "RESTORE_PREVIOUS.ps1", "cv_studio.ico",
        )
    else:
        remove = ()
    for name in remove:
        path = root / name
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)


def bundle_node_runtime_dependency(source: Path, package: Path) -> None:
    """Bundle the immutable owner-vetted adm-zip runtime dependency.

    Never copy from source/node_modules: npm's mutable working tree can contain
    harmless metadata, stale files, or local modifications. The protected
    artifact always receives the exact owner-vetted tree whose aggregate hash
    is pinned above.
    """
    src = validate_vetted_adm_zip(source)
    dst = package / "node_modules" / "adm-zip"
    shutil.copytree(src, dst)
    if sha256_tree(dst) != ADM_ZIP_TREE_SHA256:
        raise RuntimeError("Bundled adm-zip copy failed integrity verification")


def build_package(source: Path,work: Path,out_dir: Path,target: str,dist: Path,nuitka_report: Path,
                  protected_index: Path,protected_generate: Path,protected_modules: Path,
                  protection: dict) -> tuple[Path,Path]:
    package=work/"package"/"cv_formatter"; native=package/"runtime"/"native"
    shutil.copytree(dist,native)
    for name in RUNTIME_ASSETS:
        src=source/name; dst=native/name
        if name=="index.html": shutil.copy2(protected_index,dst)
        elif name=="generate.js": shutil.copy2(protected_generate,dst)
        else: copy_item(src,dst)
    packaged_modules=native/"vendor"/"cvstudio"
    shutil.rmtree(packaged_modules)
    shutil.copytree(protected_modules,packaged_modules)
    for name in ROOT_FILES: copy_item(source/name,package/name)
    bundle_node_runtime_dependency(source, package)
    patch_launchers(package,target)
    prune_target_incompatible_launchers(package,target)
    binaries=[p for p in native.iterdir() if p.is_file() and p.name.lower().startswith("cvstudio")]
    if not binaries: raise RuntimeError("Native executable missing during packaging.")
    binary=sorted(binaries,key=lambda p:len(p.name))[0]
    binary_bytes=binary.read_bytes()
    for marker in (b"You are a professional CV parser", b"You are a CV anonymisation specialist"):
        if marker in binary_bytes:
            raise RuntimeError("Plaintext proprietary prompt leaked into native executable")
    (package/"app.py").write_text(launcher_stub(binary.name),encoding="utf-8")
    (package/"COLLEAGUE_BUILD_INFO.txt").write_text(
        f"CV Studio {VERSION}\nNative protected colleague package: {target}\nReadable Python backend source and owner build tools are not included.\nThe browser UI is transformed for copy-hardening but remains inspectable by a determined user.\nThe exact adm-zip runtime package is bundled; a Node.js executable is still required.\nThe owner-only title-cache merge utility is not included in colleague packages.\nRun the normal Authy-protected installer before first launch.\n",encoding="utf-8")
    (package/"PROTECTED_RUNTIME_README.txt").write_text("Keep the private-source ZIP for future patches. Never patch from this colleague package.\n",encoding="utf-8")
    (package/"PROTECTED_PLATFORM_TARGET.txt").write_text(target+"\n",encoding="utf-8")
    prune(package)
    forbidden={"KEEP_PRIVATE_PATCH_BASE.txt","AUTHY_MANUAL_SETUP_KEY.txt","AUTHY_SETUP_URI.txt","README_SCAN_FIRST.txt","salary_notice_logic_handover.md","build_protected.py","PROTECTED_BUILD_GUIDE.md","merge_title_cache.py","MERGE_TITLE_CACHE.bat"}
    leaks=[str(p.relative_to(package)) for p in package.rglob("*") if p.is_file() and p.name in forbidden]
    if leaks: raise RuntimeError("Private/source files leaked: "+", ".join(leaks))
    stub=(package/"app.py").read_text(encoding="utf-8")
    if "SYSTEM_PROMPT" in stub or len(stub)>5000: raise RuntimeError("app.py is not a minimal launcher stub.")
    if target=="windows-x64":
        for rel in ("START_HIDDEN.vbs", "WATCHDOG.vbs"):
            raw=(package/rel).read_bytes()
            if raw.startswith(b"\xef\xbb\xbf"):
                raise RuntimeError(f"Protected Windows package contains BOM-damaged {rel} (WSH 800A0408).")
        hidden=(package/"START_HIDDEN.vbs").read_text(encoding="utf-8")
        if "runtime\\native\\CVStudio.exe" not in hidden or ', 0, False' not in hidden:
            raise RuntimeError("Protected Windows hidden native launcher is missing.")
        if "CREATE_NO_WINDOW" not in stub or "subprocess.Popen" not in stub:
            raise RuntimeError("Protected Windows app.py launcher is not detached/no-console.")
        stop_text=(package/"STOP.bat").read_text(encoding="utf-8-sig")
        stop_core=(package/"STOP_CORE.ps1").read_text(encoding="utf-8-sig")
        if "taskkill /f /im python" in stop_text.lower() or "STOP_CORE.ps1" not in stop_text:
            raise RuntimeError("Protected Windows shutdown is not PID-scoped.")
        instance_helper=(package/"INSTANCE_PORT.ps1").read_text(encoding="utf-8-sig")
        if "cvstudio.$instance.pid.json" not in stop_core or "INSTANCE_PORT.ps1" not in stop_core or "-Mode Stop" not in stop_core:
            raise RuntimeError("Protected Windows scoped shutdown helper is missing.")
        if "/instance" not in instance_helper or "root_hash" not in instance_helper or "Stop-CVStudioWatchdogs" not in instance_helper:
            raise RuntimeError("Protected Windows verified old-instance shutdown is missing.")
        watchdog=(package/"WATCHDOG.vbs").read_text(encoding="utf-8")
        if r"runtime\native\CVStudio.exe" not in watchdog or "/instance-id" not in watchdog:
            raise RuntimeError("Protected Windows watchdog does not launch the native runtime directly.")
    pyfiles=[p for p in package.rglob("*.py")]
    allowed={(package/"app.py").resolve()}
    unexpected=[str(p.relative_to(package)) for p in pyfiles if p.resolve() not in allowed]
    if unexpected: raise RuntimeError("Unexpected readable Python files: "+", ".join(unexpected[:20]))
    packaged_antiword = validate_antiword_runtime(
        source,
        target,
        native / "vendor" / "antiword",
    )
    if packaged_antiword.get("source") != "bundled":
        raise RuntimeError(
            "Packaged Antiword validation did not resolve the copied bundle."
        )
    manifest={"product":"CV Studio","version":VERSION,"target":target,"package_type":"native-compiled-protected-colleague",
              "built_at_utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),"frontend_protection":protection,"files":{}}
    for p in sorted(package.rglob("*")):
        if p.is_file(): manifest["files"][p.relative_to(package).as_posix()]={"sha256":sha256_file(p),"bytes":p.stat().st_size}
    (package/"PROTECTED_BUILD_MANIFEST.json").write_text(json.dumps(manifest,indent=2,sort_keys=True),encoding="utf-8")
    out_dir.mkdir(parents=True,exist_ok=True)
    shutil.copy2(nuitka_report,out_dir/f"cv_studio_{VERSION_SLUG}_{target}_nuitka_report.xml")
    artifact=out_dir/f"the_guo_lab_{VERSION_SLUG}_native_protected_{target}_colleague.zip"
    if artifact.exists(): artifact.unlink()
    with zipfile.ZipFile(artifact,"w",zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        info=zipfile.ZipInfo("cv_formatter/"); info.external_attr=(0o755&0xffff)<<16|0x10; z.writestr(info,b"")
        for p in sorted(package.rglob("*")):
            rel="cv_formatter/"+p.relative_to(package).as_posix()
            if p.is_dir():
                info=zipfile.ZipInfo(rel.rstrip("/")+"/"); info.external_attr=(0o755&0xffff)<<16|0x10; z.writestr(info,b"")
            else:
                info=zipfile.ZipInfo.from_file(p,rel)
                if p==binary or p.suffix in {".sh",".command"}: info.external_attr=(0o755&0xffff)<<16
                z.writestr(info,p.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    return artifact,package


def machine_source() -> str:
    system=platform.system().lower()
    if system=="windows":
        value=""
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r"SOFTWARE\Microsoft\Cryptography",0,winreg.KEY_READ|getattr(winreg,"KEY_WOW64_64KEY",0)) as key:
                value=str(winreg.QueryValueEx(key,"MachineGuid")[0] or "").strip()
        except Exception: pass
        return "windows|"+(value or os.environ.get("COMPUTERNAME") or platform.node() or "unknown").lower()
    if system=="darwin":
        value=""
        try:
            r=subprocess.run(["ioreg","-rd1","-c","IOPlatformExpertDevice"],capture_output=True,text=True,timeout=4)
            m=re.search(r'"IOPlatformUUID"\s*=\s*"([^"]+)"',r.stdout or "",re.I); value=m.group(1).strip() if m else ""
        except Exception: pass
        return "macos|"+(value or platform.node() or "unknown").lower()
    value=""
    for name in ("/etc/machine-id","/var/lib/dbus/machine-id"):
        try:
            value=Path(name).read_text().strip()
            if value: break
        except Exception: pass
    return "linux|"+(value or platform.node() or "unknown").lower()


def receipt_path(environment: dict[str,str] | None = None) -> Path:
    env = environment or os.environ
    home = Path(env.get("HOME") or str(Path.home()))
    if os.name=="nt": return Path(env.get("LOCALAPPDATA") or str(home/"AppData"/"Local"))/"TheGuoLab"/"CVStudio"/"install_receipt.json"
    return home/".guo_lab_cv_studio"/"install_receipt.json"


def write_test_receipt(package_root: Path, environment: dict[str,str] | None = None) -> tuple[Path,bytes|None]:
    path=receipt_path(environment); prior=path.read_bytes() if path.exists() else None
    secret=bytes(a^b for a,b in zip(TOTP_MASK,TOTP_MASKED)); machine=hashlib.sha256(machine_source().encode()).hexdigest()
    issued=time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()); key=hashlib.sha256(secret+b"|CVStudio|install-receipt-v1").digest()
    root_text=os.path.normcase(os.path.realpath(str(package_root))); root_hash=hashlib.sha256(root_text.encode("utf-8",errors="surrogatepass")).hexdigest()
    msg=f"{RECEIPT_SCHEMA}|{PRODUCT}|{machine}|{VERSION}|{root_hash}|{issued}"; signature=hmac.new(key,msg.encode(),hashlib.sha256).hexdigest()
    path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"schema":RECEIPT_SCHEMA,"product":PRODUCT,"machine":machine,"version":VERSION,"rootHash":root_hash,"issuedAt":issued,"signature":signature},separators=(",",":")),encoding="utf-8"); tmp.replace(path)
    return path,prior


def _tail_text(path: Path, max_chars: int = 12000) -> str:
    try:
        text=path.read_text(encoding="utf-8",errors="replace")
    except Exception:
        return ""
    return text[-max_chars:]


def _loopback_port_is_occupied(port: int) -> bool:
    probe=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    try:
        probe.bind(("127.0.0.1",int(port)))
        return False
    except OSError:
        return True
    finally:
        probe.close()


def _choose_smoke_port() -> int:
    probe=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    try:
        probe.bind(("127.0.0.1",0))
        port=int(probe.getsockname()[1])
    finally:
        probe.close()
    if not (1024 <= port <= 65535):
        raise RuntimeError("Unable to reserve a safe loopback port for the protected-build smoke test.")
    return port


def protected_smoke_environment(state_root: Path) -> dict[str,str]:
    """Return an environment whose supported app state stays below state_root."""

    root=Path(state_root).resolve()
    home=root/"home"
    local_app_data=root/"localappdata"
    state=root/"state"
    for directory in (home,local_app_data,state):
        directory.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy()
    env["HOME"]=str(home)
    env["LOCALAPPDATA"]=str(local_app_data)
    env["CVSTUDIO_STATE_DIR"]=str(state)
    env["CVSTUDIO_DB_PATH"]=str(state/"cv_studio.sqlite3")
    env["CVSTUDIO_JOB_STATE_PATH"]=str(state/"cv_studio_jobs.json")
    env["CVSTUDIO_ANTIWORD_PACKAGE_ONLY"]="1"
    return env


def smoke_test(package: Path,source: Path,output: Path,target: str,timeout_seconds: int = 240) -> dict:
    production_port_occupied=_loopback_port_is_occupied(5000)
    smoke_port=_choose_smoke_port()
    base_url=f"http://127.0.0.1:{smoke_port}"
    native=package/"runtime"/"native"; binary=sorted([p for p in native.iterdir() if p.is_file() and p.name.lower().startswith("cvstudio")],key=lambda p:len(p.name))[0]
    binary.chmod(binary.stat().st_mode|stat.S_IXUSR|stat.S_IXGRP|stat.S_IXOTH)
    smoke_state=tempfile.TemporaryDirectory(
        prefix="cvstudio-protected-smoke-state-"
    )
    env=protected_smoke_environment(Path(smoke_state.name))
    receipt,prior=write_test_receipt(package,env); process=None
    result={
        "ok":False,
        "checks":[],
        "target":target,
        "timeout_seconds":int(timeout_seconds),
        "smoke_port":smoke_port,
        "production_port_5000_occupied":production_port_occupied,
    }
    output.mkdir(parents=True,exist_ok=True)
    log=output/f"cv_studio_{VERSION_SLUG}_{target}_protected_smoke_runtime.log"
    failure_json=output/f"cv_studio_{VERSION_SLUG}_{target}_protected_smoke_failure.json"
    startup_log=package/"startup_timing.log"
    started=time.time()
    try:
        # Do not borrow owner node_modules during smoke testing. generate.js
        # must resolve the exact adm-zip copy inside the colleague package.
        env.pop("NODE_PATH", None)
        env["PYTHONUNBUFFERED"]="1"
        env["CVSTUDIO_OWNER_BUILD_SMOKE"]="1"
        env["CVSTUDIO_OWNER_BUILD_SMOKE_PORT"]=str(smoke_port)
        native_runtime_log=output/f"cv_studio_{VERSION_SLUG}_{target}_native_runtime.log"
        env["CVSTUDIO_RUNTIME_LOG_PATH"]=str(native_runtime_log)
        with log.open("wb") as f:
            popen_kwargs={"cwd":str(native),"env":env,"stdout":f,"stderr":subprocess.STDOUT}
            if target=="windows-x64":
                popen_kwargs["creationflags"]=int(getattr(subprocess,"CREATE_NO_WINDOW",0))|int(getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0))
            process=subprocess.Popen([str(binary)],**popen_kwargs)
        deadline=time.time()+max(30,int(timeout_seconds)); next_progress=time.time()+15
        while time.time()<deadline:
            code=process.poll()
            if code is not None:
                runtime_tail=_tail_text(log)
                timing_tail=_tail_text(startup_log,4000)
                detail=f"Compiled server exited before becoming ready (exit code {code})."
                if runtime_tail: detail += "\nRuntime log tail:\n"+runtime_tail
                if timing_tail: detail += "\nStartup timing tail:\n"+timing_tail
                raise RuntimeError(detail)
            try:
                with urllib.request.urlopen(base_url+"/ping",timeout=1) as r:
                    # CV Studio intentionally returns 204 No Content for /ping.
                    # Accept both 200 and 204 so a healthy server is not polled
                    # continuously until the timeout expires.
                    if r.status in (200,204):
                        break
            except Exception:
                pass
            now=time.time()
            if now>=next_progress:
                print(f"Smoke test: waiting for compiled server ({int(now-started)}s/{int(timeout_seconds)}s)...",flush=True)
                next_progress=now+15
            time.sleep(.25)
        else:
            runtime_tail=_tail_text(log)
            timing_tail=_tail_text(startup_log,4000)
            detail=f"Compiled server did not become ready within {int(timeout_seconds)} seconds."
            if runtime_tail: detail += "\nRuntime log tail:\n"+runtime_tail
            if timing_tail: detail += "\nStartup timing tail:\n"+timing_tail
            raise RuntimeError(detail)
        for url in (
            base_url+"/ping",
            base_url+"/status",
            base_url+"/",
            base_url+"/vendor/jspdf.umd.min.js?v=qa",
            *(base_url+"/vendor/cvstudio/"+filename+"?v=qa" for filename in FRONTEND_MODULES),
        ):
            with urllib.request.urlopen(url,timeout=15) as r:
                body=r.read()
                is_ping=url.endswith("/ping")
                valid_status=r.status in ((200,204) if is_ping else (200,))
                valid_body=is_ping or bool(body)
                if not valid_status or not valid_body:
                    raise RuntimeError(f"Smoke URL failed: {url} (HTTP {r.status}, {len(body)} bytes)")
                result["checks"].append({"url":url,"status":r.status,"bytes":len(body)})
        with urllib.request.urlopen(base_url+"/instance",timeout=15) as r:
            ident=json.loads(r.read().decode("utf-8"))
            expected_root=os.path.normcase(os.path.realpath(str(package)))
            if (
                ident.get("version")!=VERSION
                or os.path.normcase(os.path.realpath(str(ident.get("root") or "")))!=expected_root
                or int(ident.get("port") or 0)!=smoke_port
                or int(ident.get("pid") or 0)!=int(process.pid)
            ):
                raise RuntimeError(f"Compiled package identity mismatch: {ident}")
            result["checks"].append({"url":"/instance","status":r.status,"instance_id":ident.get("instance_id"),"root_verified":True,"pid_verified":True,"port_verified":True})
        with urllib.request.urlopen(base_url+"/diagnostics/runtime",timeout=30) as r:
            diagnostics=json.loads(r.read().decode("utf-8"))
            dependencies=diagnostics.get("dependencies") or {}
            dependency=dependencies.get("antiword_health") or {}
            tesseract_dependency=dependencies.get("tesseract_health") or {}
            if not (
                dependencies.get("tesseract")
                and tesseract_dependency.get("available")
                and tesseract_dependency.get("functional")
                and tesseract_dependency.get("english_language_data")
            ):
                raise RuntimeError(
                    "Compiled package Tesseract diagnostics failed: "
                    + str(tesseract_dependency.get("reason") or "missing health evidence")
                )
            if target=="linux-x64-test":
                if (
                    dependencies.get("antiword")
                    or dependency.get("available")
                    or dependency.get("reason")!="unsupported-platform"
                ):
                    raise RuntimeError(
                        "Linux test-only package misreported Antiword support."
                    )
                result["checks"].append({
                    "url":"/diagnostics/runtime",
                    "status":r.status,
                    "antiword_platform":"unsupported",
                    "antiword_test_only":True,
                })
            else:
                if not (
                    dependencies.get("antiword")
                    and dependency.get("available")
                    and dependency.get("trusted")
                    and dependency.get("functional")
                    and dependency.get("manifest_verified")
                    and dependency.get("functional_fixture_verified")
                    and dependency.get("source")=="bundled"
                ):
                    raise RuntimeError(
                        "Compiled package Antiword diagnostics failed: "
                        + str(dependency.get("reason") or "missing health evidence")
                    )
                result["checks"].append({
                    "url":"/diagnostics/runtime",
                    "status":r.status,
                    "antiword_version":dependency.get("version"),
                    "antiword_platform":dependency.get("platform"),
                    "antiword_source":"bundled",
                    "antiword_runtime_root_verified":True,
                    "antiword_trusted":True,
                    "tesseract_version":tesseract_dependency.get("version"),
                    "tesseract_functional":True,
                    "tesseract_english_language_data":True,
                    "antiword_functional":True,
                })
        if target!="linux-x64-test":
            fixture=(source/"vendor"/"antiword"/"fixtures"/"UDHR-english.doc").read_bytes()
            boundary="----CVStudioAntiwordProtectedSmoke"
            legacy_doc_body=(
                f"--{boundary}\r\n"
                'Content-Disposition: form-data; name="file"; filename="UDHR-english.doc"\r\n'
                "Content-Type: application/msword\r\n\r\n"
            ).encode("ascii")+fixture+f"\r\n--{boundary}--\r\n".encode("ascii")
            req=urllib.request.Request(
                base_url+"/extract-text",
                data=legacy_doc_body,
                headers={
                    "Content-Type":f"multipart/form-data; boundary={boundary}",
                    "X-CV-Studio-Request":"1",
                },
                method="POST",
            )
            with urllib.request.urlopen(req,timeout=60) as r:
                extracted=json.loads(r.read().decode("utf-8"))
                text=str(extracted.get("text") or "")
                if (
                    r.status!=200
                    or not extracted.get("ok")
                    or "Universal Declaration of Human Rights" not in text
                    or "\ufffd" in text
                ):
                    raise RuntimeError("Compiled legacy .doc extraction did not return verified Antiword text.")
                result["checks"].append({
                    "url":"/extract-text",
                    "status":r.status,
                    "fixture_sha256":hashlib.sha256(fixture).hexdigest(),
                    "content_verified":True,
                    "unicode_replacement_absent":True,
                })
        sample={
            "alignment":"justify",
            "data":{
                "candidate":{
                    "name":"Protected Build Test",
                    "email":"qa@example.com",
                    "notice_period":"1 Month",
                    "current_position":"Senior Consultant",
                    "current_company":"Example LLC",
                    "languages":"English",
                },
                "work_experiences":[{
                    "date_range":"Jan 2024 to Present",
                    "company":"Example LLC",
                    "roles":[{
                        "title":"Senior Consultant",
                        "date_range":"Jan 2024 to Present",
                        "bullets":["Delivered a deterministic protected-build smoke test."],
                    }],
                }],
                "education":[{
                    "date_range":"2018 to 2021",
                    "institution":"Example University",
                    "degree":"Bachelor of Testing",
                }],
                "skills":["Testing"],
                "certifications":["Protected Build QA"],
            },
        }
        req=urllib.request.Request(base_url+"/generate-docx",data=json.dumps(sample).encode(),headers={"Content-Type":"application/json","X-CV-Studio-Request":"1"},method="POST")
        with urllib.request.urlopen(req,timeout=60) as r:
            data=r.read()
            if r.status!=200 or not data.startswith(b"PK"): raise RuntimeError("Compiled DOCX generation failed.")
            try:
                with zipfile.ZipFile(io.BytesIO(data),"r") as archive:
                    document_xml=archive.read("word/document.xml").decode("utf-8",errors="replace")
            except Exception as exc:
                raise RuntimeError("Compiled DOCX response is not a readable Word package.") from exc
            for expected_text in ("Protected Build Test","Example LLC","Senior Consultant","Delivered a deterministic protected-build smoke test."):
                if expected_text not in document_xml:
                    raise RuntimeError("Compiled DOCX smoke test did not render expected content: "+expected_text)
            result["checks"].append({"url":"/generate-docx","status":r.status,"bytes":len(data),"content_verified":True})
        result["ok"]=True
        result["startup_seconds"]=round(time.time()-started,2)
        failure_json.unlink(missing_ok=True)
        return result
    except Exception as exc:
        result["error"]=str(exc)
        result["runtime_log"]=str(log)
        if 'native_runtime_log' in locals() and native_runtime_log.exists():
            result["native_runtime_log"]=str(native_runtime_log)
            native_tail=_tail_text(native_runtime_log)
            if native_tail and native_tail not in result.get("error", ""):
                result["error"] += "\nNative runtime log tail:\n" + native_tail
        if startup_log.exists():
            copied=output/f"cv_studio_{VERSION_SLUG}_{target}_startup_timing_failure.log"
            try: shutil.copy2(startup_log,copied); result["startup_timing_log"]=str(copied)
            except Exception: pass
        failure_json.write_text(json.dumps(result,indent=2),encoding="utf-8")
        raise RuntimeError(str(exc)+f"\nDiagnostics kept at: {log}\nFailure report: {failure_json}") from exc
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try: process.wait(8)
            except subprocess.TimeoutExpired: process.kill()
        if prior is None: receipt.unlink(missing_ok=True)
        else: receipt.write_bytes(prior)
        smoke_state.cleanup()


def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument("--source-root",default=str(Path(__file__).resolve().parents[1])); ap.add_argument("--output-dir",default="protected-output")
    ap.add_argument("--target",choices=("auto","windows-x64","macos-intel","macos-arm64"),default="auto")
    ap.add_argument("--smoke-timeout",type=int,default=240,help="Seconds to wait for the compiled server during native smoke testing.")
    ap.add_argument("--skip-obfuscation",action="store_true"); ap.add_argument("--skip-smoke",action="store_true"); args=ap.parse_args()
    source=Path(args.source_root).resolve(); output=Path(args.output_dir).resolve(); target=detect_target(args.target)
    print(f"CV Studio protected build: {VERSION} -> {target}")
    validate_target_host(target); validate_source(source); preflight_source(source,target)
    try:
        with tempfile.TemporaryDirectory(prefix="cvstudio-protected-build-") as td:
            work=Path(td); pi,pg,pm,protection=protect_javascript(source,work,args.skip_obfuscation); native_source,native_prompt_report=prepare_native_source(source,work); protection["native_prompt_protection"]=native_prompt_report; dist,report=compile_native(source,work,target,native_source)
            artifact,package=build_package(source,work,output,target,dist,report,pi,pg,pm,protection)
            try: smoke={"ok":None,"skipped":True} if args.skip_smoke else smoke_test(package,source,output,target,args.smoke_timeout)
            except Exception: artifact.unlink(missing_ok=True); raise
            smoke_path=output/f"cv_studio_{VERSION_SLUG}_{target}_protected_smoke.json"; smoke_path.write_text(json.dumps(smoke,indent=2),encoding="utf-8")
            print("Artifact:",artifact); print("SHA256:",sha256_file(artifact)); print("Smoke:",smoke_path)
    except Exception:
        # Failed builds must never leave a misleading distributable ZIP.
        for p in output.glob(f"the_guo_lab_{VERSION_SLUG}_native_protected_{target}_colleague.zip"): p.unlink(missing_ok=True)
        raise
    return 0

if __name__=="__main__": raise SystemExit(main())
