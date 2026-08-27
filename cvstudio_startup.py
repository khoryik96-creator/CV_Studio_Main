"""Cross-platform startup (login-item) service for CV Studio.

The application remains responsible for registering the ``/startup/*`` Flask
routes.  This module receives its environment (the installation root and the
running instance identifier) through explicit callbacks and never imports the
application, any credential store, or shared mutable state.  The operating
system operations are a verbatim move of the legacy web-shell handlers so the
observable behaviour, response payloads and status codes are unchanged.
"""

from __future__ import annotations

import os
import ntpath
import platform
import plistlib
import re
import subprocess
from typing import Any, Callable


_WINDOWS_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_WINDOWS_RUN_VALUE = "GUOLabCVStudio"
_WINDOWS_WSCRIPT_COMMAND_RE = re.compile(
    r'^\s*(?:"(?:[^"\r\n]*[\\/])?wscript(?:\.exe)?"|'
    r'(?:[^\s"\r\n]*[\\/])?wscript(?:\.exe)?)\s+"([^"\r\n]+)"\s*$',
    re.IGNORECASE,
)


def _managed_windows_startup_path(command: str) -> str:
    """Return the VBS path only for CV Studio's exact legacy Run command."""
    match = _WINDOWS_WSCRIPT_COMMAND_RE.fullmatch(str(command or ""))
    if not match:
        return ""
    path = match.group(1).strip()
    if not ntpath.isabs(path):
        return ""
    if ntpath.basename(path).lower() != "start_hidden.vbs":
        return ""
    return ntpath.normpath(path)


class StartupService:
    """Explicitly wired handlers behind the established startup endpoints."""

    def __init__(
        self,
        *,
        jsonify: Callable[[Any], Any],
        root_path: Callable[[], str],
        instance_id: Callable[[], str],
    ):
        self._jsonify = jsonify
        self._root_path = root_path
        self._instance_id = instance_id

    def status(self):
        """Check if CV Studio is in startup (cross-platform)."""
        instance_id = self._instance_id()
        try:
            if platform.system() == "Windows":
                import winreg
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                    _WINDOWS_RUN_KEY, 0, winreg.KEY_READ)
                try:
                    value = str(winreg.QueryValueEx(key, _WINDOWS_RUN_VALUE)[0] or "")
                    expected = os.path.realpath(os.path.join(self._root_path(), "START_HIDDEN.vbs"))
                    expected_command = 'wscript.exe "{}"'.format(expected)
                    configured = os.path.normcase(value.strip()) == os.path.normcase(expected_command)
                    managed_path = _managed_windows_startup_path(value)
                    repair_required = bool(
                        not configured
                        and managed_path
                        and not os.path.isfile(managed_path)
                    )
                    return self._jsonify({
                        "enabled": bool(configured or repair_required),
                        "configured": bool(configured),
                        "repair_required": repair_required,
                        "other_installation": bool(
                            not configured
                            and managed_path
                            and os.path.isfile(managed_path)
                        ),
                        "command": value if configured else "",
                        "instance_id": instance_id,
                    })
                except FileNotFoundError:
                    return self._jsonify({"enabled": False, "instance_id": instance_id})
                finally:
                    winreg.CloseKey(key)
            elif platform.system() == "Darwin":
                plist = os.path.expanduser("~/Library/LaunchAgents/com.hyppies.cvstudio.{}.plist".format(instance_id))
                if not os.path.exists(plist):
                    return self._jsonify({"enabled": False, "instance_id": instance_id})
                try:
                    with open(plist, "rb") as handle:
                        data = plistlib.load(handle)
                    args = data.get("ProgramArguments") or []
                    valid = len(args) >= 2 and os.path.realpath(str(args[1])) == os.path.realpath(os.path.join(self._root_path(), "start.sh"))
                    proc = subprocess.run(["/bin/launchctl", "print", "gui/{}/com.hyppies.cvstudio.{}".format(os.getuid(), instance_id)], capture_output=True, timeout=8, check=False)
                    return self._jsonify({"enabled": bool(valid and proc.returncode == 0), "configured": bool(valid), "loaded": proc.returncode == 0, "instance_id": instance_id})
                except Exception as exc:
                    return self._jsonify({"enabled": False, "error": str(exc), "instance_id": instance_id})
            else:
                return self._jsonify({"enabled": False, "platform": platform.system()})
        except Exception as e:
            return self._jsonify({"enabled": False, "error": str(e)})

    def enable(self):
        """Add CV Studio to startup (cross-platform)."""
        script_dir = self._root_path()
        try:
            if platform.system() == "Windows":
                import winreg
                vbs_path = os.path.join(script_dir, "START_HIDDEN.vbs")
                cmd = f'wscript.exe "{vbs_path}"'
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                    _WINDOWS_RUN_KEY, 0, winreg.KEY_SET_VALUE)
                winreg.SetValueEx(key, _WINDOWS_RUN_VALUE, 0, winreg.REG_SZ, cmd)
                winreg.CloseKey(key)
            elif platform.system() == "Darwin":
                sh_path = os.path.realpath(os.path.join(script_dir, "start.sh"))
                plist_dir = os.path.expanduser("~/Library/LaunchAgents")
                os.makedirs(plist_dir, exist_ok=True)
                label = "com.hyppies.cvstudio.{}".format(self._instance_id())
                plist_path = os.path.join(plist_dir, label + ".plist")
                payload = {
                    "Label": label,
                    "ProgramArguments": ["/bin/bash", sh_path],
                    "RunAtLoad": True,
                    "KeepAlive": False,
                    "ProcessType": "Interactive",
                }
                temp_path = plist_path + ".tmp"
                with open(temp_path, "wb") as handle:
                    plistlib.dump(payload, handle, fmt=plistlib.FMT_XML, sort_keys=True)
                os.replace(temp_path, plist_path)
                domain = "gui/{}".format(os.getuid())
                subprocess.run(["/bin/launchctl", "bootout", domain + "/" + label], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8, check=False)
                proc = subprocess.run(["/bin/launchctl", "bootstrap", domain, plist_path], capture_output=True, text=True, timeout=12, check=False)
                if proc.returncode != 0:
                    return self._jsonify({"ok": False, "error": (proc.stderr or proc.stdout or "launchctl bootstrap failed")[:800]}), 500
            else:
                return self._jsonify({"ok": False, "error": "Unsupported platform"})
            return self._jsonify({"ok": True})
        except Exception as e:
            return self._jsonify({"ok": False, "error": str(e)})

    def disable(self):
        """Remove CV Studio from startup (cross-platform)."""
        try:
            if platform.system() == "Windows":
                import winreg
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                    _WINDOWS_RUN_KEY, 0, winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE)
                try:
                    value = str(winreg.QueryValueEx(key, _WINDOWS_RUN_VALUE)[0] or "")
                    expected = os.path.realpath(os.path.join(self._root_path(), "START_HIDDEN.vbs"))
                    expected_command = 'wscript.exe "{}"'.format(expected)
                    managed_path = _managed_windows_startup_path(value)
                    if (
                        os.path.normcase(value.strip()) == os.path.normcase(expected_command)
                        or (managed_path and not os.path.isfile(managed_path))
                    ):
                        winreg.DeleteValue(key, _WINDOWS_RUN_VALUE)
                except FileNotFoundError:
                    pass
                finally:
                    winreg.CloseKey(key)
            elif platform.system() == "Darwin":
                label = "com.hyppies.cvstudio.{}".format(self._instance_id())
                plist_path = os.path.expanduser("~/Library/LaunchAgents/" + label + ".plist")
                domain = "gui/{}".format(os.getuid())
                subprocess.run(["/bin/launchctl", "bootout", domain + "/" + label], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8, check=False)
                if os.path.exists(plist_path):
                    os.remove(plist_path)
            return self._jsonify({"ok": True})
        except Exception as e:
            return self._jsonify({"ok": False, "error": str(e)})
