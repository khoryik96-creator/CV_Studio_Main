"""Pre-extraction characterization for the salary-AI extract/notice functions.

These functions (_ja_build_salary_notice_canonical, _ja_update_candidate_salary_notice,
_ja_salary_cost_details) had no direct coverage. This pins their current behaviour
BEFORE they move into the salary-AI service module, so the (non-verbatim) service
extraction stays behaviour-preserving. Date-dependent notice fields are deliberately
not asserted.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from owner_build_tools.build_protected import write_test_receipt

ROOT = Path(__file__).resolve().parents[1]
_TMP = tempfile.TemporaryDirectory(prefix="cvstudio-ja-salary-extract-")
os.environ.setdefault("CVSTUDIO_DB_PATH", str(Path(_TMP.name) / "state" / "cv_studio.sqlite3"))
write_test_receipt(ROOT)

import app  # noqa: E402


class BuildSalaryNoticeCanonicalTests(unittest.TestCase):
    def test_parsed_currency_and_raw_fields(self):
        out = app._ja_build_salary_notice_canonical(
            {"current_salary_breakdown": "RM 5000 basic", "expected_salary": "RM 6000", "notice_period": "1 month"},
            candidate=None, ai_components=None, processing=None, spelling_correction=True,
        )
        self.assertEqual(out["currency"], "MYR")
        self.assertEqual(out["current"]["raw"], "RM 5000 basic")
        self.assertEqual(out["current"]["currency"], "MYR")
        self.assertEqual(out["expected"]["raw"], "RM 6000")
        # notice: assert stable (non-date) fields only
        self.assertEqual(out["notice"]["display"], "1 Month")
        self.assertTrue(out["notice"]["ok"])
        self.assertEqual(out["notice"]["payload"], {"relative": {"period": 1, "unit": "Month"}})
        self.assertEqual(
            set(out.keys()),
            {"canonicalVersion", "currency", "currencySelection", "current", "currentCurrency",
             "expected", "expectedCurrency", "normalization", "notice", "processing", "validation"},
        )

    def test_blank_input(self):
        out = app._ja_build_salary_notice_canonical({}, None, None, None, True)
        self.assertIsNone(out["currency"])
        self.assertEqual(out["current"]["source"], "blank")


class SalaryCostDetailsTests(unittest.TestCase):
    def test_token_and_provider_fields(self):
        cost = app._ja_salary_cost_details("deepseek-v4", {"prompt_tokens": 100, "completion_tokens": 50}, "deepseek")
        self.assertEqual(cost["input_tokens"], 100)
        self.assertEqual(cost["output_tokens"], 50)
        self.assertEqual(cost["total_tokens"], 150)
        self.assertEqual(cost["provider"], "deepseek")
        self.assertEqual(cost["model"], "deepseek-v4")
        self.assertEqual(cost["cost_value_type"], "local_estimate")


class UpdateCandidateSalaryNoticeTests(unittest.TestCase):
    _FIELDS = {"current_salary_breakdown": "RM 5000", "expected_salary": "RM 6000", "notice_period": "1 month"}

    def test_read_failure_returns_skipped_preview(self):
        with mock.patch.object(app, "_ja_get_json", side_effect=RuntimeError("boom")):
            result = app._ja_update_candidate_salary_notice("cand-1", self._FIELDS)
        self.assertFalse(result["ok"])
        self.assertTrue(result["skipped"])
        self.assertIsNone(result["candidate_read_status"])
        self.assertIn("Could not read existing candidate profile", result["candidate_read_warning"])
        self.assertIsInstance(result["payload_fields"], list)

    def test_happy_path_puts_to_candidate_path(self):
        put_calls = []

        def fake_put(path, payload, timeout=25):
            put_calls.append((path, payload))
            return 200, {"updated": True}

        with (
            mock.patch.object(app, "_ja_get_json", return_value=(200, {"candidateId": 1})),
            mock.patch.object(app, "_ja_put_json", side_effect=fake_put),
        ):
            result = app._ja_update_candidate_salary_notice("cand-1", self._FIELDS)
        self.assertTrue(result["ok"])
        self.assertEqual(result["candidate_read_status"], 200)
        if put_calls:  # a non-empty payload was produced -> it must PUT to the candidate path
            self.assertEqual(put_calls[0][0], "candidates/cand-1")
            self.assertEqual(result["status"], 200)
            self.assertFalse(result["skipped"])


if __name__ == "__main__":
    unittest.main()
