"""OneNote desktop-app integration (Windows COM / PowerShell) — Phase 7B.

Verbatim move of the legacy web-shell ``_onenote_desktop_*`` cluster: the
Windows-only OneNote desktop bridge (win32com COM automation with a PowerShell
fallback), local-notebook section discovery, manual-link resolution and page
text extraction. The Flask route handlers stay in the web shell and call these
helpers. Windows COM modules are imported lazily inside the functions, so this
module imports cleanly on any platform (the desktop paths raise/return
gracefully when the OneNote app or pywin32 is unavailable).

NOTE: this cluster is Windows-desktop-only and cannot be exercised on Linux/CI;
it was moved byte-for-byte from app.py and is verified by compile, import and
the sealed route contract only.

This module never imports ``app``.
"""

import base64
import hashlib
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

from cvstudio_onenote_text import (
    _onenote_date_filtered_items,
    _onenote_desktop_parse_sections_xml,
    _onenote_html_to_text,
    _onenote_iso,
    _onenote_manual_candidates,
    _onenote_manual_search_terms,
    _onenote_text_search_items,
    _onenote_xml_nodes,
)


def _onenote_desktop_available():
    if not sys.platform.lower().startswith("win"):
        return False, "Desktop OneNote reading is only available on Windows."
    # v24.6.93: desktop OneNote reading can use either pywin32 OR a PowerShell
    # COM fallback.  pywin32 is still installed by INSTALL.bat where possible,
    # but do not hard-block desktop reading just because pywin32 is missing or
    # its OneNote generated wrapper is broken on a specific Office install.
    return True, ""

def _onenote_desktop_app():
    ok, msg = _onenote_desktop_available()
    if not ok:
        raise RuntimeError(msg)
    try:
        import pythoncom, win32com.client  # type: ignore
    except Exception:
        return None
    try:
        pythoncom.CoInitialize()
    except Exception:
        pass
    # EnsureDispatch builds/uses the generated COM wrapper where possible.
    # OneNote's COM API exposes XML through out parameters, and plain Dispatch
    # can show an unhelpful "OneNote.Application.GetHierarchy" error on some
    # Windows/Office installs.  v24.6.93 adds a PowerShell COM fallback below.
    for prog_id in ("OneNote.Application", "OneNote.Application.16", "OneNote.Application.15", "OneNote.Application.14", "OneNote.Application.12"):
        try:
            return win32com.client.gencache.EnsureDispatch(prog_id)
        except Exception:
            try:
                return win32com.client.Dispatch(prog_id)
            except Exception:
                pass
    return None

def _onenote_com_error_label(exc):
    text = str(exc or "").strip()
    try:
        # pywintypes.com_error frequently stores the useful message in args.
        args = getattr(exc, "args", None) or []
        parts = []
        for a in args:
            if isinstance(a, (tuple, list)):
                parts.extend(str(x) for x in a if x is not None)
            elif a is not None:
                parts.append(str(a))
        joined = " | ".join(x for x in parts if x and x != text)
        if joined:
            text = (text + " | " + joined).strip(" |")
    except Exception:
        pass
    return text or exc.__class__.__name__

def _onenote_desktop_bstr_out():
    """Create a BYREF BSTR output parameter for OneNote COM calls.

    Some pywin32 builds expose VARIANT as win32com.client.VARIANT rather than
    pythoncom.VARIANT.  v24.6.91 incorrectly assumed pythoncom.VARIANT existed,
    which caused desktop OneNote scanning to fail before OneNote could return
    hierarchy/page XML.
    """
    import pythoncom, win32com.client  # type: ignore
    variant_factory = getattr(pythoncom, "VARIANT", None) or getattr(win32com.client, "VARIANT", None)
    if not variant_factory:
        raise RuntimeError("pywin32 VARIANT helper is unavailable; reinstall pywin32 with INSTALL.bat.")
    return variant_factory(pythoncom.VT_BYREF | pythoncom.VT_BSTR, "")

def _onenote_desktop_powershell(script, timeout=45):
    """Run a OneNote COM PowerShell script and return its payload.

    v24.6.144 piped scripts through ``powershell.exe -Command -``. On some
    Windows PowerShell 5.1 installations that path can finish with exit code 0
    while producing no captured stdout, which surfaced only as the misleading
    ``PowerShell exited with code 0`` message. Execute a temporary UTF-8 BOM
    script through ``-File`` instead, force a non-zero exit on exceptions, and
    use a base64 payload marker to avoid console-encoding loss in OneNote XML.
    """
    if not sys.platform.lower().startswith("win"):
        raise RuntimeError("PowerShell OneNote fallback is only available on Windows.")

    wrapper = "$ErrorActionPreference = 'Stop'\ntry {\n__BODY__\n} catch {\n" \
        "  $msg = $_.Exception.Message\n" \
        "  if ($_.InvocationInfo -and $_.InvocationInfo.PositionMessage) {\n" \
        "    $msg = $msg + ' | ' + ($_.InvocationInfo.PositionMessage -replace '[\\r\\n]+', ' ')\n" \
        "  }\n" \
        "  [Console]::Error.WriteLine('CVSTUDIO_ONENOTE_ERROR: ' + $msg)\n" \
        "  exit 1\n}\n"
    wrapper = wrapper.replace("__BODY__", str(script or ""))

    temp_path = ""
    try:
        fd, temp_path = tempfile.mkstemp(prefix="cvstudio_onenote_", suffix=".ps1")
        os.close(fd)
        with open(temp_path, "w", encoding="utf-8-sig", newline="\r\n") as handle:
            handle.write(wrapper)

        system_root = os.environ.get("SystemRoot") or r"C:\Windows"
        candidates = []
        # Sysnative lets a 32-bit Python process reach 64-bit Windows PowerShell.
        if os.environ.get("PROCESSOR_ARCHITEW6432"):
            candidates.append(os.path.join(system_root, "Sysnative", "WindowsPowerShell", "v1.0", "powershell.exe"))
        candidates.extend([
            os.path.join(system_root, "System32", "WindowsPowerShell", "v1.0", "powershell.exe"),
            os.path.join(system_root, "SysWOW64", "WindowsPowerShell", "v1.0", "powershell.exe"),
            "powershell.exe",
            "powershell",
            # PowerShell 7 is a last resort; Windows PowerShell 5.1 is preferred
            # because the OneNote desktop COM server is a classic Office API.
            "pwsh.exe",
            "pwsh",
        ])
        seen = set()
        last = ""
        for exe in candidates:
            key = str(exe).lower()
            if key in seen:
                continue
            seen.add(key)
            if os.path.isabs(exe) and not os.path.exists(exe):
                continue
            try:
                proc = subprocess.run(
                    [exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", temp_path],
                    text=True,
                    capture_output=True,
                    timeout=timeout,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                )
            except FileNotFoundError:
                continue
            except Exception as exc:
                last = "{}: {}".format(exe, exc)
                continue

            stdout = str(proc.stdout or "").strip().lstrip("\ufeff")
            stderr = str(proc.stderr or "").strip().lstrip("\ufeff")
            if proc.returncode == 0 and stdout:
                marker = "CVSTUDIO_ONENOTE_B64:"
                pos = stdout.rfind(marker)
                if pos >= 0:
                    encoded = stdout[pos + len(marker):].strip().splitlines()[0].strip()
                    try:
                        return base64.b64decode(encoded).decode("utf-8")
                    except Exception as exc:
                        last = "{} returned an unreadable OneNote XML payload: {}".format(exe, exc)
                        continue
                return stdout
            detail = stderr or stdout
            if not detail and proc.returncode == 0:
                detail = "PowerShell completed but returned no OneNote COM payload"
            elif not detail:
                detail = "PowerShell exited with code {}".format(proc.returncode)
            last = "{}: {}".format(exe, detail)
        raise RuntimeError(last or "Windows PowerShell is not available for OneNote COM fallback.")
    finally:
        if temp_path:
            try:
                os.remove(temp_path)
            except Exception:
                pass

def _onenote_desktop_get_hierarchy_powershell(start_id="", scope=3):
    start_b64 = base64.b64encode(str(start_id or "").encode("utf-8")).decode("ascii")
    scope_int = int(scope or 3)
    script = r'''
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$start = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String('__START_B64__'))
$scope = [int]__SCOPE__
$one = $null
$comErrors = @()
foreach ($progId in @('OneNote.Application', 'OneNote.Application.16', 'OneNote.Application.15', 'OneNote.Application.14', 'OneNote.Application.12')) {
  try {
    $one = New-Object -ComObject $progId
    if ($one) { break }
  } catch {
    $comErrors += ($progId + ': ' + $_.Exception.Message)
  }
}
if (-not $one) {
  throw ('Could not create the desktop OneNote COM object. ' + ($comErrors -join ' | '))
}
[string]$xml = ''
$xmlRef = [ref]$xml
try {
  $one.GetHierarchy($start, $scope, $xmlRef) | Out-Null
} catch {
  [string]$xml = ''
  $xmlRef = [ref]$xml
  $one.GetHierarchy($start, $scope, $xmlRef, 2) | Out-Null
}
$xmlText = [string]$xmlRef.Value
if ([string]::IsNullOrWhiteSpace($xmlText)) {
  throw 'OneNote returned a blank hierarchy. Confirm Microsoft 365 desktop OneNote is installed, signed in, and the notebook or section is open.'
}
$payload = [System.Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($xmlText))
[Console]::Write('CVSTUDIO_ONENOTE_B64:' + $payload)
'''.replace('__START_B64__', start_b64).replace('__SCOPE__', str(scope_int))
    return _onenote_desktop_powershell(script)

def _onenote_desktop_get_page_content_powershell(page_id):
    page_b64 = base64.b64encode(str(page_id or "").replace("desktop:", "").strip().encode("utf-8")).decode("ascii")
    script = r'''
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$pageId = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String('__PAGE_B64__'))
$one = $null
$comErrors = @()
foreach ($progId in @('OneNote.Application', 'OneNote.Application.16', 'OneNote.Application.15', 'OneNote.Application.14', 'OneNote.Application.12')) {
  try {
    $one = New-Object -ComObject $progId
    if ($one) { break }
  } catch {
    $comErrors += ($progId + ': ' + $_.Exception.Message)
  }
}
if (-not $one) {
  throw ('Could not create the desktop OneNote COM object. ' + ($comErrors -join ' | '))
}
[string]$xml = ''
$xmlRef = [ref]$xml
try {
  $one.GetPageContent($pageId, $xmlRef, 0) | Out-Null
} catch {
  [string]$xml = ''
  $xmlRef = [ref]$xml
  $one.GetPageContent($pageId, $xmlRef, 0, 2) | Out-Null
}
$xmlText = [string]$xmlRef.Value
if ([string]::IsNullOrWhiteSpace($xmlText)) {
  throw 'OneNote returned blank page content.'
}
$payload = [System.Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($xmlText))
[Console]::Write('CVSTUDIO_ONENOTE_B64:' + $payload)
'''.replace('__PAGE_B64__', page_b64)
    return _onenote_desktop_powershell(script)

def _onenote_desktop_open_hierarchy_powershell(section_path):
    path_b64 = base64.b64encode(str(section_path or "").encode("utf-8")).decode("ascii")
    script = r'''
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$sectionPath = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String('__PATH_B64__'))
$one = $null
$comErrors = @()
foreach ($progId in @('OneNote.Application', 'OneNote.Application.16', 'OneNote.Application.15', 'OneNote.Application.14', 'OneNote.Application.12')) {
  try {
    $one = New-Object -ComObject $progId
    if ($one) { break }
  } catch {
    $comErrors += ($progId + ': ' + $_.Exception.Message)
  }
}
if (-not $one) {
  throw ('Could not create the desktop OneNote COM object. ' + ($comErrors -join ' | '))
}
[string]$objectId = ''
$idRef = [ref]$objectId
$one.OpenHierarchy($sectionPath, '', $idRef, 0) | Out-Null
$idText = [string]$idRef.Value
if ([string]::IsNullOrWhiteSpace($idText)) {
  throw ('OneNote opened the section path but returned no section ID: ' + $sectionPath)
}
$payload = [System.Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($idText))
[Console]::Write('CVSTUDIO_ONENOTE_B64:' + $payload)
'''.replace('__PATH_B64__', path_b64)
    return _onenote_desktop_powershell(script)


def _onenote_desktop_open_hierarchy(app_obj, section_path):
    path = str(section_path or "").strip()
    if not path:
        raise RuntimeError("Desktop OneNote section path is empty.")
    last_err = None
    if app_obj is not None:
        for args in ((path, "", 0), (path, "")):
            try:
                val = app_obj.OpenHierarchy(*args)
                if isinstance(val, (tuple, list)):
                    val = next((x for x in val if isinstance(x, str) and x.strip()), val[0] if val else "")
                if str(val or "").strip():
                    return str(val).strip()
            except Exception as exc:
                last_err = exc
        try:
            out = _onenote_desktop_bstr_out()
            app_obj.OpenHierarchy(path, "", out, 0)
            if str(getattr(out, "value", "") or "").strip():
                return str(out.value).strip()
        except Exception as exc:
            last_err = exc
    try:
        return str(_onenote_desktop_open_hierarchy_powershell(path) or "").strip()
    except Exception as exc:
        last_err = exc
    raise RuntimeError("Desktop OneNote could not open the section path. Detail: {}".format(_onenote_com_error_label(last_err)))





def _onenote_desktop_local_notebook_sections(raw):
    """Resolve every section under a pasted local notebook-folder link.

    OneNote desktop links can point at the notebook directory instead of one
    ``Section.one`` file. Root COM enumeration is not reliable on every Office
    build, so this helper combines direct notebook-hierarchy enumeration with
    safe filesystem discovery of every local ``.one`` section, including
    section-group subfolders. It never silently selects the first section.
    """
    cand = _onenote_manual_candidates(raw)
    folder_paths = list(cand.get("local_notebook_paths") or [])
    if not folder_paths:
        return [], [], []

    app_obj = _onenote_desktop_app()
    notebooks, sections, warnings = [], [], []
    seen_nb, seen_sec, seen_path = set(), set(), set()
    notebook_by_path = {}

    def add_notebook(path, notebook_id=""):
        clean = str(path or "").rstrip("\\/")
        name = re.split(r"[\\/]", clean)[-1] or "Desktop OneNote notebook"
        path_key = os.path.normcase(clean).lower()
        requested_id = str(notebook_id or "").strip()
        existing = notebook_by_path.get(path_key)
        if existing is not None:
            if requested_id and str(existing.get("id") or "").startswith("local-folder:"):
                seen_nb.discard(str(existing.get("id") or "").lower())
                existing["id"] = requested_id
                seen_nb.add(requested_id.lower())
            return str(existing.get("displayName") or name), str(existing.get("id") or requested_id)
        stable_id = requested_id or ("local-folder:" + hashlib.sha256(clean.lower().encode("utf-8", errors="ignore")).hexdigest()[:20])
        key = stable_id.lower()
        item = {"id": stable_id, "displayName": name, "path": clean, "_source": "desktop-local-folder"}
        notebook_by_path[path_key] = item
        if key not in seen_nb:
            seen_nb.add(key)
            notebooks.append(item)
        return name, stable_id

    def add_section(section, notebook_name, notebook_id, group_path=""):
        section = dict(section or {})
        sid = str(section.get("id") or "").strip()
        path = str(section.get("path") or "").strip()
        key = (sid.lower() if sid else "") or (path.lower() if path else "")
        if not key or key in seen_sec:
            return
        seen_sec.add(key)
        section["_parentNotebookName"] = section.get("_parentNotebookName") or notebook_name
        section["_parentNotebookId"] = section.get("_parentNotebookId") or notebook_id
        section["_sectionGroupPath"] = section.get("_sectionGroupPath") or group_path
        section["_source"] = "desktop-local-folder"
        label = str(section.get("displayName") or "Untitled section")
        if section.get("_sectionGroupPath"):
            label += " · " + str(section.get("_sectionGroupPath"))
        label += " · " + str(section.get("_parentNotebookName") or notebook_name)
        section["_label"] = label
        sections.append(section)

    for folder in folder_paths:
        folder = str(folder or "").rstrip("\\/")
        notebook_name, notebook_id = add_notebook(folder)

        # First ask OneNote to open the notebook folder directly. On supported
        # desktop builds this returns a notebook id and a complete hierarchy.
        try:
            opened_id = _onenote_desktop_open_hierarchy(app_obj, folder)
            if opened_id:
                notebook_name, notebook_id = add_notebook(folder, opened_id)
                xml_text = _onenote_desktop_get_hierarchy(app_obj, opened_id, 3)
                parsed_nbs, parsed_sections = _onenote_desktop_parse_sections_xml(xml_text, notebook_name, notebook_id)
                for nb in parsed_nbs:
                    add_notebook(nb.get("path") or folder, nb.get("id") or notebook_id)
                for sec in parsed_sections:
                    add_section(sec, notebook_name, notebook_id, sec.get("_sectionGroupPath") or "")
        except Exception as exc:
            warnings.append("Notebook hierarchy open failed for {}: {}".format(folder, exc))

        # Supplement COM hierarchy with every actual local .one file. This is
        # the reliable fallback for Office builds that return only the first
        # section from a notebook-folder link.
        if not os.path.isdir(folder):
            warnings.append("Local OneNote notebook folder was not found: {}".format(folder))
            continue
        discovered = []
        try:
            for root_dir, dir_names, file_names in os.walk(folder):
                relative_root = os.path.relpath(root_dir, folder)
                depth = 0 if relative_root in (".", "") else len([part for part in re.split(r"[\\/]", relative_root) if part])
                if depth >= 6:
                    dir_names[:] = []
                dir_names[:] = [d for d in dir_names if not re.fullmatch(r"(?i)(onenote[_ -]?recycle[_ -]?bin|recycle[_ -]?bin|\.trash|\.cache|onenote[_ -]?backups?)", str(d or "").strip())]
                for filename in file_names:
                    if not re.search(r"(?i)\.one$", filename or ""):
                        continue
                    full_path = os.path.join(root_dir, filename)
                    pkey = os.path.normcase(os.path.abspath(full_path))
                    if pkey in seen_path:
                        continue
                    seen_path.add(pkey)
                    discovered.append(full_path)
                    if len(discovered) >= 500:
                        break
                if len(discovered) >= 500:
                    break
        except Exception as exc:
            warnings.append("Could not enumerate local OneNote section files in {}: {}".format(folder, exc))
            discovered = []

        for section_path in sorted(discovered, key=lambda v: str(v).lower()):
            try:
                section_id = _onenote_desktop_open_hierarchy(app_obj, section_path)
                if not section_id:
                    continue
                relative_dir = os.path.relpath(os.path.dirname(section_path), folder)
                group_path = "" if relative_dir in (".", "") else relative_dir.replace("\\", " / ").replace("/", " / ")
                leaf = os.path.basename(section_path)
                label = re.sub(r"(?i)\.one$", "", leaf).strip() or "Desktop OneNote section"
                add_section({"id": section_id, "displayName": label, "path": section_path}, notebook_name, notebook_id, group_path)
            except Exception as exc:
                warnings.append("Could not open OneNote section {}: {}".format(section_path, exc))

    notebooks.sort(key=lambda it: str(it.get("displayName") or "").lower())
    sections.sort(key=lambda it: (str(it.get("_parentNotebookName") or "").lower(), str(it.get("_sectionGroupPath") or "").lower(), str(it.get("displayName") or "").lower()))
    return notebooks, sections, warnings


def _onenote_desktop_resolve_manual_section(raw):
    """Resolve a pasted local onenote:///...Section.one link without root enumeration."""
    cand = _onenote_manual_candidates(raw)
    app_obj = _onenote_desktop_app()
    errors = []
    for path in cand.get("local_paths") or []:
        try:
            section_id = _onenote_desktop_open_hierarchy(app_obj, path)
            if section_id:
                leaf = re.split(r"[\\/]", path)[-1]
                label = re.sub(r"(?i)\.one$", "", leaf).strip() or "Desktop OneNote section"
                return {"id": section_id, "displayName": label, "path": path, "_source": "desktop", "_resolvedDirectly": True}
        except Exception as exc:
            errors.append(str(exc))
    # Some OneNote links include a usable section-id even when the local path is
    # unavailable (for example a Files On-Demand placeholder).
    for section_id in cand.get("section_ids") or []:
        sid = str(section_id or "").strip()
        if not sid:
            continue
        try:
            xml_text = _onenote_desktop_get_hierarchy(app_obj, sid, 4)
            if _onenote_xml_nodes(xml_text, {"Page"}) or str(xml_text or "").strip():
                return {"id": sid, "displayName": "Desktop OneNote section", "path": "", "_source": "desktop", "_resolvedDirectly": True}
        except Exception as exc:
            errors.append(str(exc))
    if errors:
        raise RuntimeError(errors[-1])
    return None


def _onenote_desktop_get_hierarchy(app_obj, start_id="", scope=3):
    start_id = str(start_id or "")
    last_err = None
    # Generated pywin32 wrapper path: out parameter may be returned directly.
    if app_obj is not None:
        for args in ((start_id, scope), (start_id, scope, 2)):
            try:
                val = app_obj.GetHierarchy(*args)
                if isinstance(val, (tuple, list)):
                    val = next((x for x in val if isinstance(x, str) and x.strip()), val[0] if val else "")
                if str(val or "").strip():
                    return str(val)
            except Exception as e:
                last_err = e
        # Late-bound Dispatch fallback: provide the BSTR out parameter explicitly.
        for extra in ((), (2,), (0,)):
            try:
                out = _onenote_desktop_bstr_out()
                app_obj.GetHierarchy(start_id, scope, out, *extra)
                if str(getattr(out, "value", "") or "").strip():
                    return str(out.value)
            except Exception as e:
                last_err = e
    # v24.6.93: PowerShell COM fallback avoids pywin32 OneNote type-library quirks.
    try:
        return _onenote_desktop_get_hierarchy_powershell(start_id, scope)
    except Exception as e:
        last_err = e
    raise RuntimeError("Desktop OneNote hierarchy read failed. Keep OneNote desktop open, then click Load Notebooks / Sections. Detail: {}".format(_onenote_com_error_label(last_err)))

def _onenote_desktop_get_page_content(app_obj, page_id):
    pid = str(page_id or "").replace("desktop:", "").strip()
    last_err = None
    # Generated pywin32 wrapper path.
    if app_obj is not None:
        for args in ((pid,), (pid, 0), (pid, 1), (pid, 0, 2)):
            try:
                val = app_obj.GetPageContent(*args)
                if isinstance(val, (tuple, list)):
                    val = next((x for x in val if isinstance(x, str) and x.strip()), val[0] if val else "")
                if str(val or "").strip():
                    return str(val)
            except Exception as e:
                last_err = e
        # Late-bound Dispatch fallback with explicit BSTR out parameter.
        for page_info in (None, 0, 1, 2):
            for schema in (None, 2, 0):
                try:
                    out = _onenote_desktop_bstr_out()
                    args = [pid, out]
                    if page_info is not None:
                        args.append(page_info)
                    if schema is not None and page_info is not None:
                        args.append(schema)
                    app_obj.GetPageContent(*args)
                    if str(getattr(out, "value", "") or "").strip():
                        return str(out.value)
                except Exception as e:
                    last_err = e
    # v24.6.93: PowerShell COM fallback avoids pywin32 OneNote type-library quirks.
    try:
        return _onenote_desktop_get_page_content_powershell(pid)
    except Exception as e:
        last_err = e
    raise RuntimeError("Desktop OneNote page content failed. Detail: {}".format(_onenote_com_error_label(last_err)))


def _onenote_desktop_sections():
    app_obj = _onenote_desktop_app()
    xml_text = _onenote_desktop_get_hierarchy(app_obj, "", 3)
    notebooks, sections = _onenote_desktop_parse_sections_xml(xml_text)

    def dedupe(items):
        seen, out = set(), []
        for it in items:
            key = str(it.get("id") or it.get("displayName") or it.get("path") or "").strip().lower()
            if not key or key in seen:
                continue
            seen.add(key); out.append(it)
        return out
    return dedupe(notebooks), dedupe(sections)

def _onenote_desktop_pages(section_id, top=50, search="", date_from_iso="", date_to_iso="", date_mode="created"):
    app_obj = _onenote_desktop_app()
    xml_text = _onenote_desktop_get_hierarchy(app_obj, section_id, 4)
    nodes = _onenote_xml_nodes(xml_text, {"Page"})
    pages = []
    for n in nodes:
        pid = n.get("ID") or n.get("id") or ""
        if not pid:
            continue
        pages.append({"id": pid, "desktop_id": pid, "_source": "desktop", "title": n.get("name") or n.get("title") or "Untitled OneNote page", "createdDateTime": _onenote_iso(n.get("dateTime") or n.get("creationTime")), "lastModifiedDateTime": _onenote_iso(n.get("lastModifiedTime") or n.get("lastModifiedDateTime"))})
    pages = _onenote_date_filtered_items(pages, date_from_iso, date_to_iso, date_mode)
    pages = _onenote_text_search_items(pages, search)
    pages.sort(key=lambda it: str((it or {}).get("lastModifiedDateTime") or (it or {}).get("createdDateTime") or ""), reverse=True)
    top = max(1, min(int(top or 50), 100))
    return pages[:top], len(pages)

def _onenote_desktop_page_text(page_id):
    """Return readable desktop OneNote text while preserving free-form note boxes.

    OneNote pages are a canvas: separate candidate notes commonly live in
    separate ``Outline`` text boxes and their XML/document order does not always
    match the visual reading order.  Flattening every leaf ``T`` node into one
    stream therefore lets a no-email note box bleed into the preceding email or
    leaves a trailing email detached from its own fields.

    Keep the v24.6.149 leaf-``T`` de-duplication rule, but group those leaves by
    top-level ``Outline`` and emit a stable block boundary.  The browser parser
    can then create one review row per visual note box, including boxes without
    an email and boxes whose email is written at the bottom.
    """
    app_obj = _onenote_desktop_app()
    xml_text = _onenote_desktop_get_page_content(app_obj, page_id)

    def _local_tag(el):
        return str(getattr(el, "tag", "")).split("}", 1)[-1].lower()

    def _leaf_text_parts(parent):
        values = []
        for el in parent.iter():
            if _local_tag(el) != "t":
                continue
            raw = "".join(el.itertext())
            txt = _onenote_html_to_text(raw)
            if not txt:
                continue
            # Only collapse exact adjacent duplicates. Do not globally dedupe:
            # two candidates can legitimately have identical answers.
            norm = re.sub(r"\s+", " ", txt).strip().lower()
            if values and re.sub(r"\s+", " ", values[-1]).strip().lower() == norm:
                continue
            values.append(txt)
        return values

    blocks = []
    all_parts = []
    try:
        root = ET.fromstring(str(xml_text or ""))
        outlines = []
        for order, outline in enumerate(el for el in root.iter() if _local_tag(el) == "outline"):
            x = y = None
            for child in outline.iter():
                if _local_tag(child) != "position":
                    continue
                try: x = float(child.get("x"))
                except Exception: x = None
                try: y = float(child.get("y"))
                except Exception: y = None
                break
            outlines.append((order, y, x, outline))

        # Position is used only to make the raw preview easier to follow.  The
        # explicit block boundary is the correctness mechanism; missing or odd
        # coordinates safely fall back to XML order.
        outlines.sort(key=lambda item: (
            item[1] is None,
            item[1] if item[1] is not None else item[0],
            item[2] if item[2] is not None else 0,
            item[0],
        ))
        for _order, _y, _x, outline in outlines:
            parts = _leaf_text_parts(outline)
            if parts:
                blocks.append("\n".join(str(part).strip() for part in parts if str(part).strip()))

        # Some OneNote editions can return text outside an Outline. Preserve a
        # safe all-leaf fallback when no usable outline was found.
        if not blocks:
            all_parts = _leaf_text_parts(root)
    except Exception:
        blocks = []
        all_parts = []

    if blocks:
        rendered = []
        for i, block in enumerate(blocks, 1):
            rendered.append("--- OneNote Note Block: {} ---\n{}".format(i, block))
        text = "\n\n".join(rendered)
    elif all_parts:
        text = "\n".join(str(part).strip() for part in all_parts if str(part).strip())
    else:
        # Fallback for malformed XML or unusual Office output. Convert the full
        # payload through the same HTML-aware parser rather than returning tags.
        text = _onenote_html_to_text(str(xml_text or ""))

    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[:60000]

def _onenote_match_desktop_section_from_manual(raw, sections):
    cand = _onenote_manual_candidates(raw)
    guid_terms = [str(x).strip("{} ").lower() for x in (cand.get("section_ids") or []) if x]
    terms = [t.lower() for t in (cand.get("terms") or _onenote_manual_search_terms(raw)) if t]
    best = None
    for sec in sections or []:
        name = str((sec or {}).get("displayName") or "").strip().lower()
        sid = str((sec or {}).get("id") or "").strip().lower()
        path = str((sec or {}).get("path") or "").strip().lower()
        sid_plain = sid.strip("{}")
        for g in guid_terms:
            if g and (g in sid or g == sid_plain or g in path):
                return sec
        for q in terms:
            q2 = re.sub(r"\.one$", "", q, flags=re.I).strip().lower()
            if q2 and (q2 == name or q2 in name or (name and name in q2) or q2 in path):
                best = best or sec
    return best
