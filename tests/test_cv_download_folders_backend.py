import base64
import io
import json
import os
from pathlib import Path
import subprocess
import zipfile

import pytest
from pypdf import PdfWriter

import cvstudio_downloads
from cvstudio_downloads import (
    DOWNLOAD_ALLOWED_EXTENSIONS,
    DOWNLOAD_KINDS,
    DownloadFolderError,
    LocalDownloadService,
    _publish_file_no_replace,
    default_download_state_path,
    safe_download_filename,
)


def _docx_bytes(text="generated"):
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", zipfile.ZIP_STORED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<document>{}</document>".format(text))
    return payload.getvalue()


def _pdf_bytes():
    payload = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.write(payload)
    return payload.getvalue()


def _html_doc_bytes():
    return b'<!DOCTYPE html><html><body><p>Generated</p></body></html>'


def test_default_state_path_is_absolute_and_user_scoped_on_macos(tmp_path):
    runtime = Path("~\\AppData\\Local") / "TheGuoLab" / "CVStudio"
    result = default_download_state_path(
        runtime,
        local_appdata=None,
        system_name="Darwin",
        user_home=tmp_path,
    )
    assert result == str(tmp_path / ".guo_lab_cv_studio" / "download_folders.json")
    assert Path(result).is_absolute()


def test_default_state_path_preserves_explicit_local_appdata_override(tmp_path):
    runtime = tmp_path / "isolated-runtime"
    assert default_download_state_path(
        runtime,
        local_appdata=str(tmp_path),
        system_name="Darwin",
    ) == str(runtime / "download_folders.json")


def test_filename_is_windows_safe_and_bounded():
    assert safe_download_filename("Hyppies CV - Lee.docx") == "Hyppies CV - Lee.docx"
    assert safe_download_filename("../CON.docx") == "_CON.docx"
    assert safe_download_filename('A/B\\C:*?"<>|.docx') == "A_B_C_______.docx"
    assert len(safe_download_filename("x" * 240 + ".docx")) <= 180


def test_folders_are_persisted_separately_and_clear_is_non_destructive(tmp_path):
    formatted = tmp_path / "formatted"
    blind = tmp_path / "blind"
    formatted.mkdir()
    blind.mkdir()
    selections = iter((str(formatted), str(blind)))
    service = LocalDownloadService(
        tmp_path / "state" / "download_folders.json",
        system_name=lambda: "Windows",
    )
    service._choose_folder_native = lambda _initial: next(selections)

    assert service.select_folder("formatted")["path"] == str(formatted)
    assert service.select_folder("blind")["path"] == str(blind)
    stored = json.loads(service.state_path.read_text(encoding="utf-8"))
    assert stored == {
        "schema": 1,
        "folders": {"formatted": str(formatted), "blind": str(blind)},
    }
    marker = formatted / "keep.docx"
    marker.write_bytes(b"keep")
    service.clear_folder("formatted")
    assert marker.read_bytes() == b"keep"
    payload = service.folders()
    assert payload["folders"]["formatted"]["configured"] is False
    assert payload["folders"]["blind"]["path"] == str(blind)
    assert set(payload["folders"]) == set(DOWNLOAD_KINDS)


def test_all_expected_destinations_have_an_explicit_file_type_contract():
    assert DOWNLOAD_ALLOWED_EXTENSIONS == {
        "formatted": frozenset({".docx"}),
        "blind": frozenset({".docx"}),
        "company_profile": frozenset({".doc", ".docx", ".pdf"}),
        "summary": frozenset({".docx"}),
        "blind_jd": frozenset({".doc", ".docx", ".pdf"}),
        "owl": frozenset({".doc", ".docx", ".pdf"}),
    }


def test_save_uses_configured_folder_and_never_overwrites(tmp_path):
    folder = tmp_path / "CV Output"
    folder.mkdir()
    service = LocalDownloadService(tmp_path / "download_folders.json")
    service._write_state_unlocked({"formatted": str(folder)})
    original = folder / "Hyppies CV.docx"
    original.write_bytes(b"original")

    generated = _docx_bytes()
    result = service.save_file(
        "formatted", "Hyppies CV.docx", io.BytesIO(generated)
    )

    assert result["method"] == "folder"
    assert result["filename"] == "Hyppies CV (1).docx"
    assert result["folder"] == str(folder)
    assert result["path"] == str(folder / "Hyppies CV (1).docx")
    assert original.read_bytes() == b"original"
    assert (folder / "Hyppies CV (1).docx").read_bytes() == generated


def test_save_validates_temporary_stage_before_publishing_final_docx(tmp_path, monkeypatch):
    folder = tmp_path / "CV Output"
    folder.mkdir()
    service = LocalDownloadService(tmp_path / "download_folders.json")
    service._write_state_unlocked({"formatted": str(folder)})
    generated = _docx_bytes("atomic")
    real_zip_file = zipfile.ZipFile
    inspected = []

    def inspect_staged_file(path, *args, **kwargs):
        inspected.append(Path(path))
        assert Path(path).suffix == ".tmp"
        assert list(folder.glob("*.docx")) == []
        return real_zip_file(path, *args, **kwargs)

    monkeypatch.setattr(cvstudio_downloads.zipfile, "ZipFile", inspect_staged_file)
    result = service.save_file(
        "formatted", "Atomic.docx", io.BytesIO(generated)
    )

    assert inspected
    assert result["path"] == str(folder / "Atomic.docx")
    assert (folder / "Atomic.docx").read_bytes() == generated
    assert not list(folder.glob(".cvstudio-download-*.tmp"))


def test_posix_publish_leaves_staging_cleanup_to_the_caller(tmp_path, monkeypatch):
    staged = tmp_path / "stage.tmp"
    destination = tmp_path / "Published.docx"
    staged.write_bytes(b"complete")

    monkeypatch.setattr(cvstudio_downloads.os, "name", "posix")
    monkeypatch.setattr(cvstudio_downloads.platform, "system", lambda: "Linux")
    _publish_file_no_replace(staged, destination)

    assert destination.read_bytes() == b"complete"
    assert staged.read_bytes() == b"complete"


def test_failed_or_oversized_save_removes_partial_file(tmp_path):
    folder = tmp_path / "CV Output"
    folder.mkdir()
    service = LocalDownloadService(tmp_path / "download_folders.json")
    service._write_state_unlocked({"blind": str(folder)})

    with pytest.raises(DownloadFolderError) as raised:
        service.save_file(
            "blind", "Blinded.docx", io.BytesIO(b"PK\x03\x04too large"), maximum_bytes=2
        )
    assert raised.value.code == "DOWNLOAD_FILE_TOO_LARGE"
    assert list(folder.iterdir()) == []


def test_invalid_state_and_unconfigured_save_fail_visibly(tmp_path):
    state = tmp_path / "download_folders.json"
    state.write_text('{"schema":1,"folders":{"formatted":"relative"}}', encoding="utf-8")
    service = LocalDownloadService(state)
    with pytest.raises(DownloadFolderError) as invalid:
        service.folders()
    assert invalid.value.code == "DOWNLOAD_SETTINGS_INVALID"

    chosen = tmp_path / "chosen"
    chosen.mkdir()
    service._choose_folder_native = lambda _initial: str(chosen)
    assert service.select_folder("formatted")["path"] == str(chosen)
    assert service.folders()["folders"]["formatted"]["path"] == str(chosen)

    state.unlink()
    with pytest.raises(DownloadFolderError) as missing:
        service.save_file("formatted", "CV.docx", io.BytesIO(b"data"))
    assert missing.value.code == "DOWNLOAD_FOLDER_NOT_CONFIGURED"


def test_empty_or_non_docx_content_is_rejected_and_removed(tmp_path):
    folder = tmp_path / "CV Output"
    folder.mkdir()
    service = LocalDownloadService(tmp_path / "download_folders.json")
    service._write_state_unlocked({"formatted": str(folder)})

    with pytest.raises(DownloadFolderError) as empty:
        service.save_file("formatted", "Empty.docx", io.BytesIO(b""))
    assert empty.value.code == "DOWNLOAD_FILE_EMPTY"
    with pytest.raises(DownloadFolderError) as invalid:
        service.save_file("formatted", "Text.docx", io.BytesIO(b"not a docx"))
    assert invalid.value.code == "DOWNLOAD_FILE_INVALID"
    with pytest.raises(DownloadFolderError) as fake_zip:
        service.save_file(
            "formatted", "Fake.docx", io.BytesIO(b"PK\x03\x04not-a-real-zip")
        )
    assert fake_zip.value.code == "DOWNLOAD_FILE_INVALID"
    assert list(folder.iterdir()) == []


@pytest.mark.parametrize("kind", ["company_profile", "blind_jd", "owl"])
@pytest.mark.parametrize(
    ("filename", "content"),
    [
        ("Export.doc", _html_doc_bytes()),
        ("Export.docx", _docx_bytes()),
        ("Export.pdf", _pdf_bytes()),
    ],
)
def test_multi_format_destinations_accept_valid_word_and_pdf_files(
    tmp_path, kind, filename, content
):
    folder = tmp_path / kind
    folder.mkdir()
    service = LocalDownloadService(tmp_path / "download_folders.json")
    service._write_state_unlocked({kind: str(folder)})

    result = service.save_file(kind, filename, io.BytesIO(content))

    assert result["path"] == str(folder / filename)
    assert (folder / filename).read_bytes() == content


def test_pdf_validation_accepts_the_bundled_jspdf_output(tmp_path):
    jspdf_path = Path(__file__).resolve().parents[1] / "vendor" / "jspdf.umd.min.js"
    script = (
        "require({});"
        "const doc=new global.jspdf.jsPDF();"
        "doc.text('CV Studio validation',10,10);"
        "process.stdout.write(Buffer.from(doc.output('arraybuffer')));"
    ).format(json.dumps(str(jspdf_path)))
    generated = subprocess.run(
        ["node", "-e", script],
        capture_output=True,
        timeout=30,
        check=True,
    ).stdout
    folder = tmp_path / "owl"
    folder.mkdir()
    service = LocalDownloadService(tmp_path / "download_folders.json")
    service._write_state_unlocked({"owl": str(folder)})

    result = service.save_file("owl", "Bundled jsPDF.pdf", io.BytesIO(generated))

    assert result["path"] == str(folder / "Bundled jsPDF.pdf")
    assert (folder / "Bundled jsPDF.pdf").read_bytes() == generated


@pytest.mark.parametrize(
    ("kind", "filename", "content", "code"),
    [
        ("formatted", "Wrong.pdf", _pdf_bytes(), "DOWNLOAD_FILE_TYPE_INVALID"),
        ("summary", "Wrong.pdf", _pdf_bytes(), "DOWNLOAD_FILE_TYPE_INVALID"),
        ("company_profile", "Wrong.exe", b"MZ", "DOWNLOAD_FILE_TYPE_INVALID"),
        ("blind_jd", "Fake.pdf", b"not a pdf", "DOWNLOAD_FILE_INVALID"),
        ("owl", "Fake.doc", b"not word html", "DOWNLOAD_FILE_INVALID"),
    ],
)
def test_destination_type_mismatches_are_rejected_without_partial_files(
    tmp_path, kind, filename, content, code
):
    folder = tmp_path / kind
    folder.mkdir()
    service = LocalDownloadService(tmp_path / "download_folders.json")
    service._write_state_unlocked({kind: str(folder)})

    with pytest.raises(DownloadFolderError) as raised:
        service.save_file(kind, filename, io.BytesIO(content))

    assert raised.value.code == code
    assert list(folder.iterdir()) == []


@pytest.mark.parametrize(
    ("kind", "filename", "content"),
    [
        ("company_profile", "Truncated.pdf", b"%PDF-"),
        ("blind_jd", "Truncated.doc", b"<html"),
        (
            "owl",
            "Unbalanced.doc",
            b"<html><head></head><body><p>Generated</body></html>",
        ),
    ],
)
def test_truncated_or_unbalanced_exports_are_rejected_before_publication(
    tmp_path, kind, filename, content
):
    folder = tmp_path / kind
    folder.mkdir()
    service = LocalDownloadService(tmp_path / "download_folders.json")
    service._write_state_unlocked({kind: str(folder)})

    with pytest.raises(DownloadFolderError) as raised:
        service.save_file(kind, filename, io.BytesIO(content))

    assert raised.value.code == "DOWNLOAD_FILE_INVALID"
    assert list(folder.iterdir()) == []


def test_windows_picker_uses_environment_for_initial_path(tmp_path):
    selected = tmp_path / "Selected Folder"
    selected.mkdir()
    captured = {}

    def run_process(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, stdout=str(selected), stderr="")

    service = LocalDownloadService(
        tmp_path / "download_folders.json",
        system_name=lambda: "Windows",
        run_process=run_process,
    )
    assert service._choose_folder_native(str(tmp_path)) == str(selected)
    assert captured["command"][0] == "powershell.exe"
    assert "-STA" in captured["command"]
    assert "-EncodedCommand" in captured["command"]
    picker_script = base64.b64decode(captured["command"][-1]).decode("utf-16-le")
    assert "FOS_PICKFOLDERS" in picker_script
    assert 'SetOkButtonLabel("Select Folder")' in picker_script
    assert "dialog.SetFolder(initial)" in picker_script
    assert "FolderBrowserDialog" not in picker_script
    assert captured["kwargs"]["env"]["CVSTUDIO_PICKER_INITIAL"] == str(tmp_path)


@pytest.mark.skipif(os.name != "nt", reason="Windows native folder picker")
def test_windows_explorer_style_folder_picker_compiles_without_opening_dialog():
    source = cvstudio_downloads._WINDOWS_FOLDER_PICKER_SCRIPT
    compile_only = source[: source.index("$owner = New-Object")] + (
        "Write-Output 'Modern folder picker compiled'"
    )
    encoded = base64.b64encode(compile_only.encode("utf-16-le")).decode("ascii")

    result = subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-STA",
            "-WindowStyle",
            "Hidden",
            "-EncodedCommand",
            encoded,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "Modern folder picker compiled"


@pytest.mark.parametrize("selected", ["C:\\", "\\\\server\\share\\"])
def test_windows_picker_preserves_drive_and_unc_roots(tmp_path, selected):
    def run_process(command, **_kwargs):
        return subprocess.CompletedProcess(command, 0, stdout=selected + "\n", stderr="")

    service = LocalDownloadService(
        tmp_path / "download_folders.json",
        system_name=lambda: "Windows",
        run_process=run_process,
    )
    assert service._choose_folder_native("") == selected


def test_macos_picker_preserves_filesystem_root(tmp_path):
    def run_process(command, **_kwargs):
        return subprocess.CompletedProcess(command, 0, stdout="/\n", stderr="")

    service = LocalDownloadService(
        tmp_path / "download_folders.json",
        system_name=lambda: "Darwin",
        run_process=run_process,
    )
    assert service._choose_folder_native("") == "/"


def test_macos_picker_preserves_path_spaces(tmp_path):
    selected = "/tmp/ CV output "

    def run_process(command, **_kwargs):
        return subprocess.CompletedProcess(command, 0, stdout=selected + "\n", stderr="")

    service = LocalDownloadService(
        tmp_path / "download_folders.json",
        system_name=lambda: "Darwin",
        run_process=run_process,
    )
    assert service._choose_folder_native("") == selected


def test_picker_process_failure_is_handled(tmp_path):
    def fail_process(_command, **_kwargs):
        raise FileNotFoundError("powershell missing")

    service = LocalDownloadService(
        tmp_path / "download_folders.json",
        system_name=lambda: "Windows",
        run_process=fail_process,
    )
    with pytest.raises(DownloadFolderError) as raised:
        service._choose_folder_native("")
    assert raised.value.code == "DOWNLOAD_FOLDER_PICKER_FAILED"
    assert "powershell" not in raised.value.public_message.lower()


def test_cancelled_picker_does_not_change_existing_selection(tmp_path):
    folder = tmp_path / "existing"
    folder.mkdir()
    service = LocalDownloadService(tmp_path / "download_folders.json")
    service._write_state_unlocked({"formatted": str(folder)})
    service._choose_folder_native = lambda _initial: None

    with pytest.raises(DownloadFolderError) as cancelled:
        service.select_folder("formatted")
    assert cancelled.value.code == "DOWNLOAD_FOLDER_SELECTION_CANCELLED"
    assert service.folders()["folders"]["formatted"]["path"] == str(folder)


def test_check_folder_performs_and_cleans_real_write_probe(tmp_path):
    folder = tmp_path / "writable"
    folder.mkdir()
    service = LocalDownloadService(tmp_path / "download_folders.json")
    service._write_state_unlocked({"formatted": str(folder)})

    payload = service.check_folder("formatted")

    assert payload["writable"] is True
    assert payload["path"] == str(folder)
    assert list(folder.iterdir()) == []


# Representative markup mirroring the real Word (.doc) export shells
# (_wordDocShell / theOwlWordShell) so the strict validator is proven to accept
# the constructs those shells actually emit -- tables with colgroup/col, a
# two-column layout table, nested lists, chips, a callout, and void elements
# (meta/img/br). This guards against the validator ever false-rejecting a
# legitimately generated export.
_REAL_SHELL_DOC = (
    b'<html xmlns:o="urn:schemas-microsoft-com:office:office" '
    b'xmlns:w="urn:schemas-microsoft-com:office:word"><head><meta charset="UTF-8">'
    b"<title>Market Map</title><style>body{color:#171717;}</style></head>"
    b'<body><div class="page"><div class="brand">'
    b'<img src="data:image/png;base64,AAAA" alt="Hyppies"></div>'
    b'<div class="hero"><h1>Market Map</h1><p class="subtitle">Hyppies</p></div>'
    b"<h2>Companies</h2>"
    b'<div class="market-table-wrap"><table class="market-table" cellspacing="0" '
    b'cellpadding="0" border="1"><colgroup><col style="width:35%">'
    b'<col style="width:14%"><col style="width:51%"></colgroup><thead><tr>'
    b"<th>Company</th><th>Tier</th><th>Notes</th></tr></thead><tbody><tr>"
    b"<td>Acme</td><td>1</td><td>Primary lead</td></tr></tbody></table></div>"
    b'<table class="market-two-col" role="presentation"><tr>'
    b'<td><ul class="market-doc-list"><li>Left one</li><li>Left two</li></ul></td>'
    b'<td><ul class="market-doc-list"><li>Right one</li></ul></td></tr></table>'
    b'<div class="callout"><h2 style="margin-top:0">Why Join Us</h2>'
    b"<ul><li>Growth<br>and impact</li></ul></div>"
    b'<p>Chips: <span class="chip">Python</span> <span class="chip">Node.js</span></p>'
    b'<div class="footer">Hyppies</div></div></body></html>'
)


@pytest.mark.parametrize("kind", ["company_profile", "blind_jd", "owl"])
def test_generated_word_shells_pass_validation(tmp_path, kind):
    folder = tmp_path / kind
    folder.mkdir()
    service = LocalDownloadService(tmp_path / "download_folders.json")
    service._write_state_unlocked({kind: str(folder)})

    result = service.save_file(kind, "Report.doc", io.BytesIO(_REAL_SHELL_DOC))

    assert result["path"] == str(folder / "Report.doc")
    assert (folder / "Report.doc").read_bytes() == _REAL_SHELL_DOC


def test_valid_pdf_is_accepted_when_pdf_parser_dependency_is_unavailable(
    tmp_path, monkeypatch
):
    # A missing/broken pypdfium2 at request time must not be misreported as a
    # corrupt file: a structurally valid PDF still saves (deep page validation
    # is skipped, the magic-byte + trailer checks still apply).
    import sys

    monkeypatch.setitem(sys.modules, "pypdfium2", None)  # forces ImportError
    folder = tmp_path / "owl"
    folder.mkdir()
    service = LocalDownloadService(tmp_path / "download_folders.json")
    service._write_state_unlocked({"owl": str(folder)})
    content = _pdf_bytes()

    result = service.save_file("owl", "NoParser.pdf", io.BytesIO(content))

    assert result["path"] == str(folder / "NoParser.pdf")
    assert (folder / "NoParser.pdf").read_bytes() == content


def test_corrupt_pdf_still_rejected_when_parser_available(tmp_path):
    # The dependency-unavailable leniency must not weaken corrupt-file detection
    # when the parser IS present: a %PDF- file with a valid-looking trailer but
    # no real pages is still rejected.
    pytest.importorskip("pypdfium2")
    folder = tmp_path / "owl"
    folder.mkdir()
    service = LocalDownloadService(tmp_path / "download_folders.json")
    service._write_state_unlocked({"owl": str(folder)})
    fake = b"%PDF-1.4\n%garbage not a real body\nstartxref 9 %%EOF\n"

    with pytest.raises(DownloadFolderError) as raised:
        service.save_file("owl", "Corrupt.pdf", io.BytesIO(fake))

    assert raised.value.code == "DOWNLOAD_FILE_INVALID"
    assert list(folder.iterdir()) == []
