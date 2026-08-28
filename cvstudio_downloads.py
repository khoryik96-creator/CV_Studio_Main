"""Native local download-folder service for generated CV documents.

Browser download APIs cannot reliably write to an arbitrary folder in every
embedded Chromium host.  This service keeps the chosen folders in CV Studio's
private local runtime state and performs the actual file write in the local
Python process.  It is deliberately independent of Flask and ``app.py``.
"""

from __future__ import annotations

import ctypes
import errno
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import tempfile
import threading
from typing import BinaryIO, Callable
import zipfile


DOWNLOAD_KINDS = ("formatted", "blind")
MAX_DOWNLOAD_BYTES = 80 * 1024 * 1024
_WINDOWS_RESERVED_STEM_RE = re.compile(
    r"^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])$", re.IGNORECASE
)
_UNSAFE_FILENAME_RE = re.compile(r'[\\/\x00-\x1f<>:"|?*]')
_DARWIN_RENAME_EXCL = 0x00000004


class DownloadFolderError(RuntimeError):
    """Handled local download configuration/save failure."""

    def __init__(self, code: str, public_message: str, *, status: int = 400):
        super().__init__(public_message)
        self.code = str(code)
        self.public_message = str(public_message)
        self.status = int(status)


def normalize_download_kind(kind: object) -> str:
    value = str(kind or "").strip().lower()
    if value not in DOWNLOAD_KINDS:
        raise DownloadFolderError(
            "DOWNLOAD_KIND_INVALID",
            "Choose either the Formatted CV or Blind CV download folder.",
        )
    return value


def safe_download_filename(filename: object) -> str:
    value = _UNSAFE_FILENAME_RE.sub("_", str(filename or "CV Studio download.docx"))
    value = value.lstrip(". ").rstrip(". ").strip()
    if not value:
        value = "CV Studio download.docx"
    dot = value.rfind(".")
    extension = value[dot:] if dot > 0 else ""
    stem = value[:dot] if dot > 0 else value
    if _WINDOWS_RESERVED_STEM_RE.fullmatch(stem):
        stem = "_" + stem
    maximum = 180
    if len(stem + extension) > maximum:
        stem = stem[: max(1, maximum - len(extension))].rstrip(". ")
    return (stem or "CV Studio download") + extension


def default_download_state_path(
    runtime_state_dir: os.PathLike[str] | str,
    *,
    local_appdata: str | None = None,
    system_name: str | None = None,
    user_home: os.PathLike[str] | str | None = None,
) -> str:
    """Return an absolute per-user settings path on every supported platform."""
    system = str(system_name or platform.system())
    if local_appdata or system == "Windows":
        return str(Path(runtime_state_dir) / "download_folders.json")
    home = Path(user_home) if user_home is not None else Path.home()
    return str(home.expanduser().resolve() / ".guo_lab_cv_studio" / "download_folders.json")


def _publish_file_no_replace(staged_path: Path, destination: Path) -> None:
    """Publish one same-directory file atomically without replacing a peer."""
    if os.name == "nt":
        # Windows rename is atomic and refuses an existing destination.
        os.rename(staged_path, destination)
        return
    if platform.system() == "Darwin":
        # macOS renamex_np supplies the no-replace guarantee that plain POSIX
        # rename lacks, including on volumes that do not support hard links.
        libc = ctypes.CDLL(None, use_errno=True)
        rename_exclusive = libc.renamex_np
        rename_exclusive.argtypes = (
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_uint,
        )
        rename_exclusive.restype = ctypes.c_int
        result = rename_exclusive(
            os.fsencode(staged_path),
            os.fsencode(destination),
            _DARWIN_RENAME_EXCL,
        )
        if result == 0:
            return
        error_number = ctypes.get_errno()
        if error_number == errno.EEXIST:
            raise FileExistsError(error_number, os.strerror(error_number), destination)
        raise OSError(error_number, os.strerror(error_number), destination)
    # The native picker is unsupported elsewhere, but retain safe behavior for
    # tests or explicitly preconfigured local state.
    os.link(staged_path, destination)
    staged_path.unlink()


class LocalDownloadService:
    """Persist two local folders and save generated DOCX files safely."""

    def __init__(
        self,
        state_path: os.PathLike[str] | str,
        *,
        system_name: Callable[[], str] = platform.system,
        run_process: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ):
        self.state_path = Path(state_path)
        self._system_name = system_name
        self._run_process = run_process
        self._lock = threading.RLock()

    def native_supported(self) -> bool:
        return self._system_name() in {"Windows", "Darwin"}

    def _read_state_unlocked(self) -> dict[str, str]:
        try:
            raw = self.state_path.read_bytes()
        except FileNotFoundError:
            return {}
        except OSError as exc:
            raise DownloadFolderError(
                "DOWNLOAD_SETTINGS_UNAVAILABLE",
                "CV Studio could not read the saved download folders.",
                status=503,
            ) from exc
        if len(raw) > 64 * 1024:
            raise DownloadFolderError(
                "DOWNLOAD_SETTINGS_INVALID",
                "The saved download-folder settings are invalid. Clear and choose the folders again.",
                status=409,
            )
        try:
            parsed = json.loads(raw.decode("utf-8-sig"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise DownloadFolderError(
                "DOWNLOAD_SETTINGS_INVALID",
                "The saved download-folder settings are invalid. Clear and choose the folders again.",
                status=409,
            ) from exc
        if (
            not isinstance(parsed, dict)
            or type(parsed.get("schema")) is not int
            or parsed.get("schema") != 1
        ):
            raise DownloadFolderError(
                "DOWNLOAD_SETTINGS_INVALID",
                "The saved download-folder settings are invalid. Clear and choose the folders again.",
                status=409,
            )
        folders = parsed.get("folders")
        if not isinstance(folders, dict):
            raise DownloadFolderError(
                "DOWNLOAD_SETTINGS_INVALID",
                "The saved download-folder settings are invalid. Clear and choose the folders again.",
                status=409,
            )
        result: dict[str, str] = {}
        for kind in DOWNLOAD_KINDS:
            value = folders.get(kind)
            if value in (None, ""):
                continue
            if not isinstance(value, str) or not os.path.isabs(value):
                raise DownloadFolderError(
                    "DOWNLOAD_SETTINGS_INVALID",
                    "The saved download-folder settings are invalid. Clear and choose the folders again.",
                    status=409,
                )
            result[kind] = os.path.normpath(value)
        return result

    def _write_state_unlocked(self, folders: dict[str, str]) -> None:
        payload = {
            "schema": 1,
            "folders": {
                kind: folders[kind]
                for kind in DOWNLOAD_KINDS
                if isinstance(folders.get(kind), str) and folders[kind]
            },
        }
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.state_path.with_name(
                self.state_path.name + ".{}.tmp".format(os.getpid())
            )
            with temporary.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.state_path)
        except OSError as exc:
            try:
                temporary.unlink(missing_ok=True)
            except Exception:
                # cleanup-only: retain the structured settings-write failure
                pass
            raise DownloadFolderError(
                "DOWNLOAD_SETTINGS_UNAVAILABLE",
                "CV Studio could not save the selected download folder.",
                status=503,
            ) from exc

    def _read_state_for_repair_unlocked(self) -> dict[str, str]:
        try:
            return self._read_state_unlocked()
        except DownloadFolderError as error:
            if error.code == "DOWNLOAD_SETTINGS_INVALID":
                return {}
            raise

    @staticmethod
    def _folder_payload(path: str | None) -> dict[str, object]:
        configured = bool(path)
        available = bool(path and os.path.isdir(path))
        return {
            "configured": configured,
            "path": str(path or ""),
            "available": available,
        }

    def folders(self) -> dict[str, object]:
        with self._lock:
            folders = self._read_state_unlocked()
        return {
            "native_supported": self.native_supported(),
            "folders": {
                kind: self._folder_payload(folders.get(kind)) for kind in DOWNLOAD_KINDS
            },
        }

    def _configured_path(self, kind: object) -> str | None:
        normalized = normalize_download_kind(kind)
        with self._lock:
            return self._read_state_unlocked().get(normalized)

    def select_folder(self, kind: object) -> dict[str, object]:
        normalized = normalize_download_kind(kind)
        with self._lock:
            current = self._read_state_for_repair_unlocked().get(normalized) or ""
        selected = self._choose_folder_native(current)
        if selected is None:
            raise DownloadFolderError(
                "DOWNLOAD_FOLDER_SELECTION_CANCELLED",
                "Folder selection was cancelled.",
                status=409,
            )
        selected = os.path.normpath(os.path.abspath(selected))
        if not os.path.isdir(selected):
            raise DownloadFolderError(
                "DOWNLOAD_FOLDER_UNAVAILABLE",
                "The selected download folder is no longer available.",
                status=409,
            )
        with self._lock:
            folders = self._read_state_for_repair_unlocked()
            folders[normalized] = selected
            self._write_state_unlocked(folders)
        return self._folder_payload(selected)

    def clear_folder(self, kind: object) -> dict[str, object]:
        normalized = normalize_download_kind(kind)
        with self._lock:
            folders = self._read_state_for_repair_unlocked()
            folders.pop(normalized, None)
            self._write_state_unlocked(folders)
        return self._folder_payload(None)

    def check_folder(self, kind: object) -> dict[str, object]:
        normalized = normalize_download_kind(kind)
        path = self._configured_path(normalized)
        if not path:
            raise DownloadFolderError(
                "DOWNLOAD_FOLDER_NOT_CONFIGURED",
                "Choose a download folder first.",
                status=409,
            )
        if not os.path.isdir(path):
            raise DownloadFolderError(
                "DOWNLOAD_FOLDER_UNAVAILABLE",
                "The selected download folder is no longer available. Choose it again.",
                status=409,
            )
        probe = None
        try:
            for index in range(100):
                candidate = Path(path) / ".cvstudio-write-check-{}-{}.tmp".format(
                    os.getpid(), index
                )
                try:
                    probe = candidate.open("xb")
                    break
                except FileExistsError:
                    continue
            if probe is None:
                raise OSError("no unused probe name")
            probe.write(b"CV Studio")
            probe.flush()
            os.fsync(probe.fileno())
        except OSError as exc:
            raise DownloadFolderError(
                "DOWNLOAD_FOLDER_NOT_WRITABLE",
                "CV Studio cannot write to the selected download folder. Choose another folder.",
                status=409,
            ) from exc
        finally:
            if probe is not None:
                try:
                    probe.close()
                except Exception:
                    # cleanup-only: the handled write-probe result is authoritative
                    pass
            try:
                if "candidate" in locals():
                    candidate.unlink(missing_ok=True)
            except Exception:
                # cleanup-only: never replace the handled probe failure
                pass
        payload = self._folder_payload(path)
        payload["writable"] = True
        return payload

    def save_file(
        self,
        kind: object,
        filename: object,
        stream: BinaryIO,
        *,
        maximum_bytes: int = MAX_DOWNLOAD_BYTES,
    ) -> dict[str, object]:
        normalized = normalize_download_kind(kind)
        folder = self._configured_path(normalized)
        if not folder:
            raise DownloadFolderError(
                "DOWNLOAD_FOLDER_NOT_CONFIGURED",
                "No custom download folder is configured.",
                status=409,
            )
        if not os.path.isdir(folder):
            raise DownloadFolderError(
                "DOWNLOAD_FOLDER_UNAVAILABLE",
                "The selected download folder is no longer available. Choose it again.",
                status=409,
            )
        safe_name = safe_download_filename(filename)
        if not safe_name.lower().endswith(".docx"):
            raise DownloadFolderError(
                "DOWNLOAD_FILE_TYPE_INVALID",
                "Only generated CV Word files can use a configured download folder.",
            )
        destination = None
        staged_path = None
        handle = None
        try:
            staged_path, handle = self._open_staged_destination(Path(folder))
            total = 0
            signature = bytearray()
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                if not isinstance(chunk, (bytes, bytearray)):
                    raise DownloadFolderError(
                        "DOWNLOAD_FILE_INVALID",
                        "The generated CV Word file is invalid.",
                    )
                if len(signature) < 4:
                    signature.extend(chunk[: 4 - len(signature)])
                total += len(chunk)
                if total > int(maximum_bytes):
                    raise DownloadFolderError(
                        "DOWNLOAD_FILE_TOO_LARGE",
                        "The generated CV is too large to save.",
                        status=413,
                    )
                handle.write(chunk)
            if total == 0:
                raise DownloadFolderError(
                    "DOWNLOAD_FILE_EMPTY",
                    "The generated CV Word file is empty.",
                )
            if bytes(signature) != b"PK\x03\x04":
                raise DownloadFolderError(
                    "DOWNLOAD_FILE_INVALID",
                    "The generated CV Word file is invalid.",
                )
            handle.flush()
            os.fsync(handle.fileno())
            handle.close()
            handle = None
            try:
                with zipfile.ZipFile(staged_path, "r") as archive:
                    names = set(archive.namelist())
                    required = {"[Content_Types].xml", "word/document.xml"}
                    if not required.issubset(names):
                        raise zipfile.BadZipFile("required DOCX parts are missing")
            except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
                raise DownloadFolderError(
                    "DOWNLOAD_FILE_INVALID",
                    "The generated CV Word file is invalid.",
                ) from exc
            destination = self._publish_staged_destination(
                Path(folder), safe_name, staged_path
            )
            staged_path = None
        except DownloadFolderError:
            raise
        except OSError as exc:
            raise DownloadFolderError(
                "DOWNLOAD_SAVE_FAILED",
                "CV Studio could not write the generated CV to the selected folder.",
                status=503,
            ) from exc
        finally:
            if handle is not None:
                try:
                    handle.close()
                except Exception:
                    # cleanup-only: the original handled save failure is retained
                    pass
            if staged_path is not None:
                try:
                    staged_path.unlink(missing_ok=True)
                except Exception:
                    # cleanup-only: never mask the structured save failure
                    pass
        return {
            "method": "folder",
            "kind": normalized,
            "filename": destination.name,
            "folder": str(Path(folder)),
            "path": str(destination),
        }

    @staticmethod
    def _filename_with_suffix(filename: str, suffix: str) -> str:
        dot = filename.rfind(".")
        extension = filename[dot:] if dot > 0 else ""
        stem = filename[:dot] if dot > 0 else filename
        maximum_stem = max(1, 180 - len(extension) - len(suffix))
        stem = stem[:maximum_stem].rstrip(". ") or "CV Studio download"[:maximum_stem]
        return safe_download_filename(stem + suffix + extension)

    @staticmethod
    def _open_staged_destination(folder: Path):
        try:
            descriptor, raw_path = tempfile.mkstemp(
                prefix=".cvstudio-download-",
                suffix=".tmp",
                dir=str(folder),
            )
            return Path(raw_path), os.fdopen(descriptor, "wb")
        except OSError as exc:
            raise DownloadFolderError(
                "DOWNLOAD_SAVE_FAILED",
                "CV Studio could not write the generated CV to the selected folder.",
                status=503,
            ) from exc

    def _publish_staged_destination(
        self, folder: Path, filename: str, staged_path: Path
    ) -> Path:
        """Atomically expose a validated staged file without overwriting."""
        for index in range(1000):
            suffix = " ({})".format(index) if index else ""
            candidate = folder / self._filename_with_suffix(filename, suffix)
            try:
                # The random staging name, never the final DOCX name, is all
                # that can remain after a process interruption.
                _publish_file_no_replace(staged_path, candidate)
            except FileExistsError:
                continue
            try:
                staged_path.unlink(missing_ok=True)
            except OSError:
                # The published DOCX is complete and valid. A temporary staging
                # link is harmless and can be removed manually if the host
                # filesystem temporarily refused cleanup.
                pass
            return candidate
        raise DownloadFolderError(
            "DOWNLOAD_NAME_EXHAUSTED",
            "CV Studio could not find an unused filename in the selected folder.",
            status=409,
        )

    def _run_picker_process(self, command: list[str], **kwargs):
        try:
            return self._run_process(command, **kwargs)
        except (OSError, subprocess.SubprocessError) as exc:
            raise DownloadFolderError(
                "DOWNLOAD_FOLDER_PICKER_FAILED",
                "CV Studio could not open the system folder picker.",
                status=503,
            ) from exc

    def _choose_folder_native(self, initial_path: str) -> str | None:
        system = self._system_name()
        if system == "Windows":
            script = (
                "Add-Type -AssemblyName System.Windows.Forms;"
                "$dialog=New-Object System.Windows.Forms.FolderBrowserDialog;"
                "$dialog.Description='Choose where CV Studio saves generated CVs';"
                "if($env:CVSTUDIO_PICKER_INITIAL -and (Test-Path -LiteralPath $env:CVSTUDIO_PICKER_INITIAL)){"
                "$dialog.SelectedPath=$env:CVSTUDIO_PICKER_INITIAL};"
                "$owner=New-Object System.Windows.Forms.Form;"
                "$owner.TopMost=$true;$owner.ShowInTaskbar=$false;"
                "$owner.StartPosition='CenterScreen';$owner.Size=New-Object System.Drawing.Size(1,1);"
                "$owner.Opacity=0;$owner.Show();"
                "$result=$dialog.ShowDialog($owner);$owner.Close();"
                "if($result -eq [System.Windows.Forms.DialogResult]::OK){"
                "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8;"
                "[Console]::Out.Write($dialog.SelectedPath);exit 0};exit 2"
            )
            env = os.environ.copy()
            env["CVSTUDIO_PICKER_INITIAL"] = initial_path
            kwargs = {
                "capture_output": True,
                "text": True,
                "encoding": "utf-8",
                "errors": "replace",
                "env": env,
                "timeout": 600,
                "check": False,
            }
            creation_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            if creation_no_window:
                kwargs["creationflags"] = creation_no_window
            process = self._run_picker_process(
                [
                    "powershell.exe",
                    "-NoLogo",
                    "-NoProfile",
                    "-NonInteractive",
                    "-STA",
                    "-WindowStyle",
                    "Hidden",
                    "-Command",
                    script,
                ],
                **kwargs,
            )
        elif system == "Darwin":
            prompt = 'choose folder with prompt "Choose where CV Studio saves generated CVs"'
            process = self._run_picker_process(
                ["/usr/bin/osascript", "-e", "POSIX path of ({})".format(prompt)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=600,
                check=False,
            )
        else:
            raise DownloadFolderError(
                "DOWNLOAD_FOLDER_PICKER_UNSUPPORTED",
                "Native download-folder selection is not supported on this platform.",
                status=501,
            )
        if process.returncode == 2 or (
            system == "Darwin" and process.returncode != 0 and "User canceled" in (process.stderr or "")
        ):
            return None
        if process.returncode != 0:
            raise DownloadFolderError(
                "DOWNLOAD_FOLDER_PICKER_FAILED",
                "CV Studio could not open the system folder picker.",
                status=503,
            )
        # Remove only the process line ending. Path-significant separators (and
        # legal macOS leading/trailing spaces) must remain untouched.
        selected = str(process.stdout or "").rstrip("\r\n")
        if not selected:
            return None
        return selected


__all__ = [
    "DOWNLOAD_KINDS",
    "DownloadFolderError",
    "LocalDownloadService",
    "MAX_DOWNLOAD_BYTES",
    "default_download_state_path",
    "normalize_download_kind",
    "safe_download_filename",
]
