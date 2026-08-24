from __future__ import annotations

import hashlib
from pathlib import Path
import xml.etree.ElementTree as ET

from owner_build_tools import build_protected


ROOT = Path(__file__).resolve().parents[1]


def test_protected_zip_checksum_sidecar_is_standard_and_verifiable(tmp_path: Path) -> None:
    artifact = tmp_path / "example colleague.zip"
    artifact.write_bytes(b"protected fixture")

    sidecar = build_protected.write_sha256_sidecar(artifact)

    expected = hashlib.sha256(artifact.read_bytes()).hexdigest()
    assert sidecar.name == "example colleague.zip.sha256"
    assert sidecar.read_text(encoding="ascii") == f"{expected}  {artifact.name}\n"


def test_nuitka_report_copy_removes_source_build_and_user_paths(tmp_path: Path) -> None:
    source_root = tmp_path / "Users" / "private-owner" / "CV Studio"
    work_root = tmp_path / "Users" / "private-owner" / "Temp" / "native-build"
    report = tmp_path / "report.xml"
    output = tmp_path / "safe-report.xml"
    report.write_text(
        "<?xml version='1.0' encoding='utf-8'?>\n"
        "<nuitka-compilation-report completion='yes'>"
        f"<option value='{source_root / 'app.py'}'/>"
        f"<output run_filename='{work_root / 'CVStudio.exe'}'/>"
        "</nuitka-compilation-report>",
        encoding="utf-8",
    )

    build_protected.copy_sanitized_nuitka_report(
        report,
        output,
        source_root=source_root,
        work_root=work_root,
    )

    text = output.read_text(encoding="utf-8")
    ET.fromstring(text)
    assert "private-owner" not in text
    assert "${source_root}" in text
    assert "${build_root}" in text


def test_native_source_seals_every_blind_cv_prompt(tmp_path: Path) -> None:
    staged, report = build_protected.prepare_native_source(ROOT, tmp_path)

    staged_text = staged.read_text(encoding="utf-8")
    assert set(report["sealed_constants"]) == {
        "SYSTEM_PROMPT",
        "BLIND_SYSTEM_PROMPT",
        "BLIND_CANDIDATE_GENDER_NEUTRALIZATION_INSTRUCTION",
    }
    assert "You are a professional CV parser" not in staged_text
    assert "You are a CV anonymisation specialist" not in staged_text
    assert "CANDIDATE GENDER NEUTRALIZATION" not in staged_text


def test_manual_protected_workflow_uploads_checksum_with_colleague_zip() -> None:
    workflow = (ROOT / ".github" / "workflows" / "build-protected.yml").read_text(
        encoding="utf-8"
    )
    assert "protected-output/*colleague.zip.sha256" in workflow
    assert "workflow_dispatch:" in workflow
    assert "pull_request:" not in workflow
