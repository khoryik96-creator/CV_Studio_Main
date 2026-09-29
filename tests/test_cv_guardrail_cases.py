"""Every guardrail the CV source-reading rules must keep, in one place.

The rules that read a CV's own tables and labels -- the authoritative work-row
reader, the fidelity audit's employer check and the year-first date rewrite --
are heuristics, and five review rounds each found a case the previous fix had
broken. Every one of those cases is recorded in
``tests/fixtures/cv_guardrail_cases.json`` and explained in
``CV_SOURCE_CHECK_GUARDRAILS.md``; this file runs all of them, so a later change
cannot quietly undo an earlier decision.

Add a case for every new rule or review finding. Never delete or edit one to make
a change pass without the owner's agreement: a failing case here means the change
breaks a behaviour that was deliberately chosen.
"""

import json
import os
from pathlib import Path
import re
import tempfile
import unittest

from owner_build_tools.build_protected import write_test_receipt

ROOT = Path(__file__).resolve().parents[1]
_MODULE_TEMPORARY = tempfile.TemporaryDirectory(prefix="cvstudio-cv-guardrails-")
_ORIGINAL_DATABASE_OVERRIDE = os.environ.get("CVSTUDIO_DB_PATH")
os.environ["CVSTUDIO_DB_PATH"] = str(Path(_MODULE_TEMPORARY.name) / "state" / "cv_studio.sqlite3")
write_test_receipt(ROOT)
try:
    import cvstudio_cv_fidelity as fidelity
    import cvstudio_cv_normalize as normalize
    import cvstudio_cv_reconcile as reconcile
finally:
    if _ORIGINAL_DATABASE_OVERRIDE is None:
        os.environ.pop("CVSTUDIO_DB_PATH", None)
    else:
        os.environ["CVSTUDIO_DB_PATH"] = _ORIGINAL_DATABASE_OVERRIDE

CASES = json.loads((ROOT / "tests" / "fixtures" / "cv_guardrail_cases.json").read_text(encoding="utf-8"))["cases"]
GUARDRAILS_DOC = (ROOT / "CV_SOURCE_CHECK_GUARDRAILS.md").read_text(encoding="utf-8")


def _cases(kind):
    return [case for case in CASES if case["kind"] == kind]


def _rows(lines, titles=()):
    parsed = {"work_experiences": [{"company": "Known Co", "roles": [{"title": t}]} for t in titles]}
    return reconcile._extract_authoritative_work_rows("\n".join(lines), parsed)


class GuardrailRegistryTests(unittest.TestCase):
    def test_every_case_has_a_unique_id_and_a_documented_rule(self):
        ids = [case["id"] for case in CASES]
        self.assertEqual(len(ids), len(set(ids)))
        documented = set(re.findall(r"^### ([A-Z]\d+)\b", GUARDRAILS_DOC, re.M))
        used = {case["rule"] for case in CASES}
        self.assertEqual(used - documented, set(), "every rule a case cites is written down")
        self.assertEqual(documented - used, set(), "every written-down rule has at least one case")


class WorkRowReaderGuardrails(unittest.TestCase):
    def test_rows(self):
        for case in _cases("rows"):
            with self.subTest(case=case["id"]):
                rows = _rows(case["lines"], case["titles"])
                self.assertEqual([r["company"] for r in rows], case["expect_companies"], case["note"])

    def test_set_aside_rows_are_read_outside_education(self):
        # A row set aside inside Education must be one the reader otherwise takes,
        # or the case proves nothing about the education rule.
        for case in _cases("rows"):
            if case["rule"] == "R4" and not case["expect_companies"] or case["id"].startswith("R3-stay"):
                with self.subTest(case=case["id"]):
                    self.assertEqual(len(_rows(case["lines"][-1:])), 1)


class SourceCheckGuardrails(unittest.TestCase):
    def test_missing_employers(self):
        for case in _cases("missing"):
            with self.subTest(case=case["id"]):
                parsed = {"work_experiences": [
                    {"company": name, "roles": [{"title": "Engineer", "bullets": ["x"]}]}
                    for name in case["kept"]
                ]}
                report = fidelity.evaluate_cv_fidelity(parsed, "\n".join(case["lines"]))
                self.assertEqual(report["employers"]["missing"], case["expect_missing"], case["note"])

    def test_labelled_names(self):
        for case in _cases("labels"):
            with self.subTest(case=case["id"]):
                self.assertEqual(fidelity._source_labelled_companies(case["line"]), case["expect"])

    def test_unnamed_employers(self):
        for case in _cases("unnamed"):
            with self.subTest(case=case["id"]):
                report = fidelity.evaluate_cv_fidelity({"work_experiences": [
                    {"date_range": "Apr 2019 to Mar 2022", "company": case["company"],
                     "roles": [{"title": "Analyst"}]},
                ]}, "")
                self.assertEqual(bool(report["employers"]["unnamed"]), case["expect_reported"])


class DateRewriteGuardrails(unittest.TestCase):
    def test_dates(self):
        for case in _cases("date"):
            with self.subTest(case=case["id"]):
                self.assertEqual(
                    normalize._cv_pretranslate_year_first_month_names(case["text"]), case["expect"]
                )


if __name__ == "__main__":
    unittest.main()
