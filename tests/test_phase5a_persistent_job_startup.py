import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from cvstudio_jobs import PersistentJobStore, deterministic_job_id
from owner_build_tools.build_protected import write_test_receipt


ROOT = Path(__file__).resolve().parents[1]


class Phase5APersistentJobStartupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(
            prefix="cvstudio-phase5a-startup-"
        )
        self.state_dir = Path(self.temporary.name)
        self.job_path = self.state_dir / "cv_studio_jobs.json"
        self.database_path = self.state_dir / "cv_studio.sqlite3"
        self.runtime_dir = self.state_dir / "runtime"
        original_local_app_data = os.environ.get("LOCALAPPDATA")
        try:
            os.environ["LOCALAPPDATA"] = str(self.runtime_dir)
            write_test_receipt(ROOT)
        finally:
            if original_local_app_data is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = original_local_app_data

    def tearDown(self):
        self.temporary.cleanup()

    def _child_environment(self, job_ids=()):
        environment = os.environ.copy()
        environment["CVSTUDIO_JOB_STATE_PATH"] = str(self.job_path)
        environment["CVSTUDIO_DB_PATH"] = str(self.database_path)
        environment.pop("CVSTUDIO_RUNTIME_LOG_PATH", None)
        environment["LOCALAPPDATA"] = str(self.runtime_dir)
        environment["PHASE5A_JOB_IDS"] = ",".join(job_ids)
        return environment

    def _run_app_import(self, job_ids=()):
        script = r"""
import json
import os
import app

job_ids = [
    value for value in os.environ.get("PHASE5A_JOB_IDS", "").split(",")
    if value
]
print(json.dumps({
    "startup_error": (
        getattr(app._CVSTUDIO_JOBS_STARTUP_ERROR, "code", "")
        if app._CVSTUDIO_JOBS_STARTUP_ERROR is not None
        else ""
    ),
    "summary": app._CVSTUDIO_JOBS.summary(),
    "records": {
        job_id: app._CVSTUDIO_JOBS.get(job_id)
        for job_id in job_ids
    },
    "routes": len(list(app.app.url_map.iter_rules())),
}, sort_keys=True))
"""
        completed = subprocess.run(
            [
                sys.executable,
                "-W",
                "error::ResourceWarning",
                "-c",
                script,
            ],
            cwd=ROOT,
            env=self._child_environment(job_ids),
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return json.loads(completed.stdout.strip().splitlines()[-1])

    def test_real_app_startup_reconciles_once_without_replaying_work(self):
        store = PersistentJobStore(self.job_path)
        store.initialize()
        safe_id = deterministic_job_id("safe_startup_fixture", "safe")
        cancel_id = deterministic_job_id(
            "cancel_startup_fixture", "cancel"
        )
        unsafe_id = deterministic_job_id(
            "unsafe_startup_fixture", "unsafe"
        )
        store.begin(
            safe_id,
            kind="safe_startup_fixture",
            safety="safe_idempotent_read",
        )
        store.begin(
            cancel_id,
            kind="cancel_startup_fixture",
            safety="safe_idempotent_read",
        )
        store.request_cancel(cancel_id)
        store.begin(
            unsafe_id,
            kind="unsafe_startup_fixture",
            safety="external_mutation",
        )

        first = self._run_app_import((safe_id, cancel_id, unsafe_id))
        self.assertEqual(first["startup_error"], "")
        self.assertEqual(first["routes"], 107)
        self.assertEqual(
            first["summary"]["startup_recovery"],
            {
                "interrupted": 1,
                "cancelled": 1,
                "needs_attention": 1,
                "recovery_limited": 0,
            },
        )
        self.assertEqual(first["records"][safe_id]["state"], "interrupted")
        self.assertEqual(first["records"][safe_id]["attempts"], 1)
        self.assertEqual(first["records"][cancel_id]["state"], "cancelled")
        self.assertEqual(
            first["records"][unsafe_id]["state"], "needs_attention"
        )
        self.assertFalse(first["records"][unsafe_id]["retryable"])

        second = self._run_app_import((safe_id, cancel_id, unsafe_id))
        self.assertEqual(
            second["summary"]["startup_recovery"],
            {
                "interrupted": 0,
                "cancelled": 0,
                "needs_attention": 0,
                "recovery_limited": 0,
            },
        )
        self.assertEqual(second["records"], first["records"])

    def test_corrupt_journal_keeps_unrelated_routes_available_and_bytes_intact(
        self,
    ):
        original = b"{phase5a corrupt journal fixture"
        self.job_path.write_bytes(original)
        script = r"""
import json
import app

response = app.app.test_client().get("/ping")
print(json.dumps({
    "startup_error": getattr(
        app._CVSTUDIO_JOBS_STARTUP_ERROR, "code", ""
    ),
    "ping_status": response.status_code,
    "routes": len(list(app.app.url_map.iter_rules())),
}, sort_keys=True))
"""
        completed = subprocess.run(
            [
                sys.executable,
                "-W",
                "error::ResourceWarning",
                "-c",
                script,
            ],
            cwd=ROOT,
            env=self._child_environment(),
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        payload = json.loads(
            completed.stdout.strip().splitlines()[-1]
        )
        self.assertEqual(payload["startup_error"], "JOB_STATE_CORRUPT")
        self.assertEqual(payload["ping_status"], 204)
        self.assertEqual(payload["routes"], 107)
        self.assertEqual(self.job_path.read_bytes(), original)

    def test_job_foundation_has_no_worker_network_or_shutdown_hook(self):
        job_source = (ROOT / "cvstudio_jobs.py").read_text(encoding="utf-8")
        for forbidden in (
            "import app",
            "threading.Thread(",
            "ThreadPoolExecutor",
            "atexit",
            "subprocess",
            "urllib",
            "requests",
            ".start()",
        ):
            self.assertNotIn(forbidden, job_source)

        app_source = (ROOT / "app.py").read_text(encoding="utf-8-sig")
        self.assertEqual(
            app_source.count("atexit.register(_remove_runtime_pid_file)"),
            1,
        )
        self.assertNotIn("atexit.register(_CVSTUDIO_JOBS", app_source)


if __name__ == "__main__":
    unittest.main()
