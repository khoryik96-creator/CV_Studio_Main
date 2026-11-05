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


def test_obfuscator_namespaces_are_unique_and_independent_of_checkout_path(tmp_path: Path) -> None:
    def prefix(source: Path) -> str:
        args = build_protected.obfuscate_args(source, tmp_path / "out.js", False)
        return args[args.index("--identifiers-prefix") + 1]

    # Punctuation must remain distinguishable; a sanitized stem alone can
    # alias ai-keys.js and ai_keys.js. Owner directory names must not leak.
    assert prefix(Path("private-checkout/ai-keys.js")) == prefix(Path("other/ai-keys.js"))
    assert len({prefix(Path(name)) for name in (
        "ai-keys.js", "ai_keys.js", "ai-routing.js", "inline_1.source.js", "generate.js"
    )}) == 5
    assert "private-checkout" not in prefix(Path("private-checkout/ai-keys.js"))


def test_protected_helper_collision_fails_build_without_logging_source(tmp_path: Path) -> None:
    import pytest

    first, second = tmp_path / "first.js", tmp_path / "second.js"
    first.write_text("function a0_0x563a(){return 'fictional private fixture'}", encoding="utf-8")
    second.write_text("var a0_0x563a;", encoding="utf-8")
    with pytest.raises(RuntimeError, match="helper collision: first / second") as error:
        build_protected.validate_obfuscated_helpers({"first": first, "second": second})
    assert "fictional private fixture" not in str(error.value)
    first.write_text("function cvs_6669727374_0x563a(){}", encoding="utf-8")
    second.write_text("function cvs_7365636f6e64_0x563a(){}", encoding="utf-8")
    build_protected.validate_obfuscated_helpers({"first": first, "second": second})
