"""Import ``app`` for a route test without touching the owner's real state.

When a route test runs on its own, nothing has imported the application yet.
This points every receipt, vault, database and log location at a fresh
temporary folder before writing the test install receipt and importing the
application. When another suite already imported it (the normal full run),
that isolated import is reused unchanged.
"""
import os
import sys
import tempfile
from pathlib import Path

_STATE = None


def load_app():
    global _STATE
    if "app" not in sys.modules:
        _STATE = tempfile.TemporaryDirectory(prefix="cvstudio-route-test-")
        state = Path(_STATE.name)
        for key, value in {
            "HOME": state / "home", "USERPROFILE": state / "home", "LOCALAPPDATA": state / "local",
            "APPDATA": state / "roaming", "CVSTUDIO_STATE_DIR": state / "state",
            "CVSTUDIO_DB_PATH": state / "state" / "cv_studio.sqlite3",
            "CVSTUDIO_JOB_STATE_PATH": state / "state" / "jobs.json",
            "CVSTUDIO_RUNTIME_LOG_PATH": state / "state" / "runtime.log",
            "CVSTUDIO_DOWNLOAD_FOLDERS_PATH": state / "state" / "download_folders.json",
            "SALARY_COMPARISON_DATA_DIR": state / "salary",
        }.items():
            os.environ[key] = str(value)
        for folder in ("home", "local", "roaming", "state", "salary"):
            (state / folder).mkdir(parents=True, exist_ok=True)
        from owner_build_tools import build_protected
        build_protected.write_test_receipt(Path(__file__).resolve().parents[1])
    import app
    return app
