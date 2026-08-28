import io
import json
from pathlib import Path
import subprocess
import zipfile

import pytest

import cvstudio_downloads
from cvstudio_downloads import (
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
    assert captured["kwargs"]["env"]["CVSTUDIO_PICKER_INITIAL"] == str(tmp_path)


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
