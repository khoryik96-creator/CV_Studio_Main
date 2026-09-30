"""Importing CV tests must not replace an owner's installation or local data.

Each test is collected alone in a fresh interpreter. The pretend installation
is intentionally outside that test's temporary state, as on an owner's PC.
"""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULES = (
    "test_cv_guardrail_cases", "test_cv_year_first_dates_employer_safety",
    "test_cv_summary_salary_docx", "test_cv_source_detail_restore",
    "test_cv_label_table_reconciliation", "test_cv_title_above_place_rows",
    "test_cv_download_folders_routes",
)


@unittest.skipUnless(os.name == "nt", "Windows folder-bound receipt regression")
class CvTestStateIsolationTests(unittest.TestCase):
    def test_collecting_each_cv_test_preserves_the_owners_state(self):
        for module in MODULES:
            with self.subTest(module=module), tempfile.TemporaryDirectory(prefix="cvstudio-owner-sentinel-") as folder:
                state = Path(folder)
                receipt = state / "TheGuoLab" / "CVStudio" / "install_receipt.json"
                receipt.parent.mkdir(parents=True)
                receipt.write_bytes(b'{"synthetic_owner_receipt":"leave untouched"}')
                env = dict(os.environ, LOCALAPPDATA=folder, APPDATA=folder,
                           CVSTUDIO_DB_PATH=str(state / "owner.sqlite3"),
                           CVSTUDIO_STATE_DIR=str(state / "owner-state"),
                           CVSTUDIO_JOB_STATE_PATH=str(state / "owner-jobs.json"),
                           SALARY_COMPARISON_DATA_DIR=str(state / "owner-salary"))
                code = """
import importlib.util, os, sys
keys = ('LOCALAPPDATA', 'APPDATA', 'CVSTUDIO_DB_PATH', 'CVSTUDIO_STATE_DIR',
        'CVSTUDIO_JOB_STATE_PATH', 'SALARY_COMPARISON_DATA_DIR')
before = {key: os.environ.get(key) for key in keys}
spec = importlib.util.spec_from_file_location('isolated_cv_test', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assert {key: os.environ.get(key) for key in keys} == before, 'test leaked environment overrides'
"""
                result = subprocess.run([sys.executable, "-c", code, str(ROOT / "tests" / (module + ".py"))],
                                        cwd=ROOT, env=env, capture_output=True, text=True, timeout=45)
                self.assertEqual(result.returncode, 0, result.stderr[-2000:])
                self.assertEqual(receipt.read_bytes(), b'{"synthetic_owner_receipt":"leave untouched"}')
                self.assertFalse((state / "owner.sqlite3").exists())
                self.assertFalse((state / "owner-state").exists())
                self.assertFalse((state / "owner-jobs.json").exists())
                self.assertFalse((state / "owner-salary").exists())
