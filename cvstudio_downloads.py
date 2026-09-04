"""Native local download-folder service for generated CV Studio files.

Browser download APIs cannot reliably write to an arbitrary folder in every
embedded Chromium host.  This service keeps the chosen folders in CV Studio's
private local runtime state and performs the actual file write in the local
Python process.  It is deliberately independent of Flask and ``app.py``.
"""

from __future__ import annotations

import base64
import codecs
import ctypes
import errno
from html.parser import HTMLParser
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


DOWNLOAD_ALLOWED_EXTENSIONS = {
    "formatted": frozenset({".docx"}),
    "blind": frozenset({".docx"}),
    "company_profile": frozenset({".doc", ".docx", ".pdf"}),
    "summary": frozenset({".docx"}),
    "blind_jd": frozenset({".doc", ".docx", ".pdf"}),
    "owl": frozenset({".doc", ".docx", ".pdf"}),
}
DOWNLOAD_KINDS = tuple(DOWNLOAD_ALLOWED_EXTENSIONS)
MAX_DOWNLOAD_BYTES = 80 * 1024 * 1024
_WINDOWS_RESERVED_STEM_RE = re.compile(
    r"^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])$", re.IGNORECASE
)
_UNSAFE_FILENAME_RE = re.compile(r'[\\/\x00-\x1f<>:"|?*]')
_DARWIN_RENAME_EXCL = 0x00000004
_HTML_VOID_ELEMENTS = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)

_WINDOWS_FOLDER_PICKER_SCRIPT = r'''Add-Type -AssemblyName System.Windows.Forms
$source = @"
using System;
using System.IO;
using System.Runtime.InteropServices;

namespace CVStudio {
    [Flags]
    internal enum FileOpenOptions : uint {
        FOS_PICKFOLDERS = 0x00000020,
        FOS_FORCEFILESYSTEM = 0x00000040,
        FOS_PATHMUSTEXIST = 0x00000800,
        FOS_DONTADDTORECENT = 0x02000000
    }

    internal enum Sigdn : uint {
        SIGDN_FILESYSPATH = 0x80058000
    }

    [ComImport]
    [Guid("DC1C5A9C-E88A-4DDE-A5A1-60F82A20AEF7")]
    internal class FileOpenDialogCom { }

    [ComImport]
    [Guid("42F85136-DB7E-439C-85F1-E4075D135FC8")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    internal interface IFileDialog {
        [PreserveSig] int Show(IntPtr parent);
        void SetFileTypes(uint count, IntPtr filterSpec);
        void SetFileTypeIndex(uint index);
        void GetFileTypeIndex(out uint index);
        void Advise(IntPtr events, out uint cookie);
        void Unadvise(uint cookie);
        void SetOptions(FileOpenOptions options);
        void GetOptions(out FileOpenOptions options);
        void SetDefaultFolder(IShellItem item);
        void SetFolder(IShellItem item);
        void GetFolder(out IShellItem item);
        void GetCurrentSelection(out IShellItem item);
        void SetFileName([MarshalAs(UnmanagedType.LPWStr)] string name);
        void GetFileName([MarshalAs(UnmanagedType.LPWStr)] out string name);
        void SetTitle([MarshalAs(UnmanagedType.LPWStr)] string title);
        void SetOkButtonLabel([MarshalAs(UnmanagedType.LPWStr)] string text);
        void SetFileNameLabel([MarshalAs(UnmanagedType.LPWStr)] string label);
        void GetResult(out IShellItem item);
        void AddPlace(IShellItem item, int alignment);
        void SetDefaultExtension([MarshalAs(UnmanagedType.LPWStr)] string extension);
        void Close(int result);
        void SetClientGuid(ref Guid guid);
        void ClearClientData();
        void SetFilter(IntPtr filter);
    }

    [ComImport]
    [Guid("43826D1E-E718-42EE-BC55-A1E261C37BFE")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    internal interface IShellItem {
        void BindToHandler(IntPtr bindContext, ref Guid handler, ref Guid iid, out IntPtr result);
        void GetParent(out IShellItem parent);
        void GetDisplayName(Sigdn name, out IntPtr value);
        void GetAttributes(uint mask, out uint attributes);
        void Compare(IShellItem item, uint hint, out int order);
    }

    public static class NativeFolderPicker {
        [DllImport("shell32.dll", CharSet = CharSet.Unicode, PreserveSig = false)]
        private static extern void SHCreateItemFromParsingName(
            [MarshalAs(UnmanagedType.LPWStr)] string path,
            IntPtr bindContext,
            ref Guid iid,
            [MarshalAs(UnmanagedType.Interface)] out IShellItem item);

        public static string Pick(IntPtr owner, string initialPath) {
            IFileDialog dialog = null;
            IShellItem result = null;
            try {
                dialog = (IFileDialog)new FileOpenDialogCom();
                FileOpenOptions options;
                dialog.GetOptions(out options);
                dialog.SetOptions(options
                    | FileOpenOptions.FOS_PICKFOLDERS
                    | FileOpenOptions.FOS_FORCEFILESYSTEM
                    | FileOpenOptions.FOS_PATHMUSTEXIST
                    | FileOpenOptions.FOS_DONTADDTORECENT);
                dialog.SetTitle("Choose where CV Studio saves generated files");
                dialog.SetOkButtonLabel("Select Folder");

                if (!String.IsNullOrWhiteSpace(initialPath) && Directory.Exists(initialPath)) {
                    IShellItem initial = null;
                    try {
                        Guid shellItemId = new Guid("43826D1E-E718-42EE-BC55-A1E261C37BFE");
                        SHCreateItemFromParsingName(initialPath, IntPtr.Zero, ref shellItemId, out initial);
                        dialog.SetFolder(initial);
                    } catch { }
                    finally {
                        if (initial != null) Marshal.FinalReleaseComObject(initial);
                    }
                }

                int status = dialog.Show(owner);
                if (status == unchecked((int)0x800704C7)) return null;
                if (status != 0) Marshal.ThrowExceptionForHR(status);
                dialog.GetResult(out result);
                IntPtr rawPath;
                result.GetDisplayName(Sigdn.SIGDN_FILESYSPATH, out rawPath);
                try { return Marshal.PtrToStringUni(rawPath); }
                finally { Marshal.FreeCoTaskMem(rawPath); }
            } finally {
                if (result != null) Marshal.FinalReleaseComObject(result);
                if (dialog != null) Marshal.FinalReleaseComObject(dialog);
            }
        }
    }
}
"@
Add-Type -TypeDefinition $source -Language CSharp
$owner = New-Object System.Windows.Forms.Form
$owner.TopMost = $true
$owner.ShowInTaskbar = $false
$owner.StartPosition = 'CenterScreen'
$owner.Size = New-Object System.Drawing.Size(1, 1)
$owner.Opacity = 0
$selected = $null
try {
    $owner.Show()
    $selected = [CVStudio.NativeFolderPicker]::Pick($owner.Handle, $env:CVSTUDIO_PICKER_INITIAL)
} finally {
    $owner.Close()
    $owner.Dispose()
}
if ([String]::IsNullOrWhiteSpace($selected)) { exit 2 }
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::Out.Write($selected)
exit 0
'''


class DownloadFolderError(RuntimeError):
    """Handled local download configuration/save failure."""

    def __init__(self, code: str, public_message: str, *, status: int = 400):
        super().__init__(public_message)
        self.code = str(code)
        self.public_message = str(public_message)
        self.status = int(status)


class _GeneratedHtmlDocValidator(HTMLParser):
    """Require the complete, balanced HTML document CV Studio generates."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.seen_html = False
        self.seen_head = False
        self.seen_body = False
        self.closed_html = False
        self.invalid = False

    def handle_decl(self, declaration: str) -> None:
        if self.seen_html or str(declaration or "").strip().lower() != "doctype html":
            self.invalid = True

    def unknown_decl(self, _data: str) -> None:
        self.invalid = True

    def handle_starttag(self, tag: str, _attrs) -> None:
        name = str(tag or "").lower()
        if self.closed_html:
            self.invalid = True
            return
        if not self.seen_html:
            if name != "html":
                self.invalid = True
                return
            self.seen_html = True
        elif name == "html":
            self.invalid = True
            return
        if name == "head":
            if self.seen_head or self.stack != ["html"]:
                self.invalid = True
            self.seen_head = True
        elif name == "body":
            if self.seen_body or self.stack != ["html"]:
                self.invalid = True
            self.seen_body = True
        if name not in _HTML_VOID_ELEMENTS:
            self.stack.append(name)

    def handle_startendtag(self, tag: str, attrs) -> None:
        name = str(tag or "").lower()
        self.handle_starttag(name, attrs)
        if name not in _HTML_VOID_ELEMENTS:
            self.handle_endtag(name)

    def handle_endtag(self, tag: str) -> None:
        name = str(tag or "").lower()
        if name in _HTML_VOID_ELEMENTS or not self.stack or self.stack[-1] != name:
            self.invalid = True
            return
        self.stack.pop()
        if name == "html":
            self.closed_html = True

    def handle_data(self, data: str) -> None:
        if str(data or "").strip() and (not self.seen_html or self.closed_html):
            self.invalid = True

    def complete(self) -> bool:
        return bool(
            not self.invalid
            and self.seen_html
            and self.seen_body
            and self.closed_html
            and not self.stack
        )


def normalize_download_kind(kind: object) -> str:
    value = str(kind or "").strip().lower()
    if value not in DOWNLOAD_KINDS:
        raise DownloadFolderError(
            "DOWNLOAD_KIND_INVALID",
            "Choose a supported CV Studio download folder.",
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


def _validate_staged_download(path: Path, extension: str, prefix: bytes) -> None:
    """Validate each generated file type before its final name is exposed."""
    invalid_message = "The generated download file is invalid."
    if extension == ".docx":
        if not prefix.startswith(b"PK\x03\x04"):
            raise DownloadFolderError("DOWNLOAD_FILE_INVALID", invalid_message)
        try:
            with zipfile.ZipFile(path, "r") as archive:
                names = set(archive.namelist())
                required = {"[Content_Types].xml", "word/document.xml"}
                if not required.issubset(names):
                    raise zipfile.BadZipFile("required DOCX parts are missing")
        except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
            raise DownloadFolderError(
                "DOWNLOAD_FILE_INVALID", invalid_message
            ) from exc
        return
    if extension == ".pdf":
        if not prefix.startswith(b"%PDF-"):
            raise DownloadFolderError("DOWNLOAD_FILE_INVALID", invalid_message)
        # Structural checks that need no parser dependency.
        try:
            with path.open("rb") as handle:
                handle.seek(0, os.SEEK_END)
                size = handle.tell()
                handle.seek(max(0, size - 4096), os.SEEK_SET)
                trailer = handle.read()
        except OSError as exc:
            raise DownloadFolderError(
                "DOWNLOAD_FILE_INVALID", invalid_message
            ) from exc
        if not re.search(rb"startxref\s+\d+\s+%%EOF\s*$", trailer):
            raise DownloadFolderError("DOWNLOAD_FILE_INVALID", invalid_message)
        # Deep page validation needs pypdfium2. If the dependency is unavailable
        # at runtime, skip it rather than reject a structurally valid PDF as
        # corrupt -- the magic bytes and trailer above already confirm integrity,
        # and blaming the file for a missing/broken library would silently lose a
        # correctly generated download.
        try:
            import pypdfium2 as pdfium
        except ImportError:
            return
        document = None
        try:
            document = pdfium.PdfDocument(str(path))
            if len(document) < 1:
                raise ValueError("generated PDF contains no pages")
            for index in range(len(document)):
                page = document[index]
                text_page = None
                try:
                    width, height = page.get_size()
                    if width <= 0 or height <= 0:
                        raise ValueError("generated PDF page has invalid dimensions")
                    text_page = page.get_textpage()
                finally:
                    if text_page is not None:
                        text_page.close()
                    page.close()
        except (OSError, RuntimeError, ValueError, TypeError) as exc:
            raise DownloadFolderError(
                "DOWNLOAD_FILE_INVALID", invalid_message
            ) from exc
        finally:
            if document is not None:
                try:
                    document.close()
                except Exception:
                    # cleanup-only: validation success/failure remains authoritative
                    pass
        return
    if extension == ".doc":
        html_prefix = prefix.lstrip(b"\xef\xbb\xbf\x00\t\r\n ").lower()
        if not (
            html_prefix.startswith(b"<html")
            or html_prefix.startswith(b"<!doctype html")
        ):
            raise DownloadFolderError("DOWNLOAD_FILE_INVALID", invalid_message)
        # Validate incrementally: read and decode in bounded chunks and feed the
        # parser as we go, so peak memory stays ~1x the file rather than holding
        # the full bytes and the full decoded string at once (files may approach
        # the 80MB cap).
        validator = _GeneratedHtmlDocValidator()
        decoder = codecs.getincrementaldecoder("utf-8-sig")()
        try:
            with path.open("rb") as handle:
                while True:
                    chunk = handle.read(65536)
                    if not chunk:
                        break
                    if b"\x00" in chunk:
                        raise ValueError("generated HTML document contains NUL bytes")
                    validator.feed(decoder.decode(chunk))
                validator.feed(decoder.decode(b"", final=True))
            validator.close()
            if not validator.complete():
                raise ValueError("generated HTML document is incomplete")
        except (OSError, UnicodeError, ValueError) as exc:
            raise DownloadFolderError(
                "DOWNLOAD_FILE_INVALID", invalid_message
            ) from exc
        return
    raise DownloadFolderError(
        "DOWNLOAD_FILE_TYPE_INVALID",
        "This file type is not supported for the selected download folder.",
    )


class LocalDownloadService:
    """Persist local output folders and save generated files safely."""

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

    def open_folder(self, kind: object) -> dict[str, object]:
        """Open the *stored* folder for this kind in the OS file manager.

        Only ever opens the path already saved for a valid download kind -- never
        a client-supplied path -- so this cannot be used to launch arbitrary
        locations.
        """
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
        system = self._system_name()
        try:
            if system == "Windows":
                # explorer.exe returns a non-zero exit code even on success, so a
                # raised exception -- not the return code -- is the failure signal.
                self._run_process(
                    ["explorer.exe", os.path.normpath(path)], timeout=15, check=False
                )
            elif system == "Darwin":
                result = self._run_process(
                    ["/usr/bin/open", path],
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=False,
                )
                if getattr(result, "returncode", 0):
                    raise DownloadFolderError(
                        "DOWNLOAD_FOLDER_OPEN_FAILED",
                        "CV Studio could not open the download folder.",
                        status=503,
                    )
            else:
                raise DownloadFolderError(
                    "DOWNLOAD_FOLDER_OPEN_UNSUPPORTED",
                    "Opening the download folder is not supported on this platform.",
                    status=501,
                )
        except DownloadFolderError:
            raise
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            raise DownloadFolderError(
                "DOWNLOAD_FOLDER_OPEN_FAILED",
                "CV Studio could not open the download folder.",
                status=503,
            ) from exc
        return self._folder_payload(path)

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
        extension = Path(safe_name).suffix.lower()
        if extension not in DOWNLOAD_ALLOWED_EXTENSIONS[normalized]:
            raise DownloadFolderError(
                "DOWNLOAD_FILE_TYPE_INVALID",
                "This file type is not supported for the selected download folder.",
            )
        destination = None
        staged_path = None
        handle = None
        try:
            staged_path, handle = self._open_staged_destination(Path(folder))
            total = 0
            prefix = bytearray()
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                if not isinstance(chunk, (bytes, bytearray)):
                    raise DownloadFolderError(
                        "DOWNLOAD_FILE_INVALID",
                        "The generated download file is invalid.",
                    )
                if len(prefix) < 8192:
                    prefix.extend(chunk[: 8192 - len(prefix)])
                total += len(chunk)
                if total > int(maximum_bytes):
                    raise DownloadFolderError(
                        "DOWNLOAD_FILE_TOO_LARGE",
                        "The generated file is too large to save.",
                        status=413,
                    )
                handle.write(chunk)
            if total == 0:
                raise DownloadFolderError(
                    "DOWNLOAD_FILE_EMPTY",
                    "The generated download file is empty.",
                )
            handle.flush()
            os.fsync(handle.fileno())
            handle.close()
            handle = None
            _validate_staged_download(staged_path, extension, bytes(prefix))
            destination = self._publish_staged_destination(
                Path(folder), safe_name, staged_path
            )
            staged_path = None
        except DownloadFolderError:
            raise
        except OSError as exc:
            raise DownloadFolderError(
                "DOWNLOAD_SAVE_FAILED",
                "CV Studio could not write the generated file to the selected folder.",
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
                "CV Studio could not write the generated file to the selected folder.",
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
            encoded_script = base64.b64encode(
                _WINDOWS_FOLDER_PICKER_SCRIPT.encode("utf-16-le")
            ).decode("ascii")
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
                    "-EncodedCommand",
                    encoded_script,
                ],
                **kwargs,
            )
        elif system == "Darwin":
            prompt = 'choose folder with prompt "Choose where CV Studio saves generated files"'
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
    "DOWNLOAD_ALLOWED_EXTENSIONS",
    "DownloadFolderError",
    "LocalDownloadService",
    "MAX_DOWNLOAD_BYTES",
    "default_download_state_path",
    "normalize_download_kind",
    "safe_download_filename",
]
