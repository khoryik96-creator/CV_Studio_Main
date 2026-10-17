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

import copy
import json
from pathlib import Path
import re
import threading
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]

# These are pure modules: no installation receipt or application state needed.
import cvstudio_cv_fidelity as fidelity
import cvstudio_cv_normalize as normalize
import cvstudio_cv_reconcile as reconcile
import cvstudio_document_safety as document_safety
import cvstudio_blind_mask as blind_mask

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
    def test_incomplete_work_reconciliation_keeps_the_provider_history(self):
        for case in _cases("work_reconcile"):
            with self.subTest(case=case["id"]):
                result = reconcile._reconcile_work_experience_with_authoritative_table(
                    copy.deepcopy(case["parsed"]), "\n".join(case["lines"])
                )
                self.assertEqual(result, case["expect"], case["note"])

    def test_rows(self):
        for case in _cases("rows"):
            with self.subTest(case=case["id"]):
                rows = _rows(case["lines"], case["titles"])
                self.assertEqual([r["company"] for r in rows], case["expect_companies"], case["note"])
                if "expect_titles" in case:
                    self.assertEqual([r["title"] for r in rows], case["expect_titles"], case["note"])
                if "expect_bullets" in case:
                    self.assertEqual([r.get("source_bullets", []) for r in rows], case["expect_bullets"], case["note"])

    def test_set_aside_rows_are_read_outside_education(self):
        # A row set aside inside Education must be one the reader otherwise takes,
        # or the case proves nothing about the education rule.
        for case in _cases("rows"):
            if case["rule"] == "R4" and not case["expect_companies"] or case["id"].startswith("R3-stay"):
                with self.subTest(case=case["id"]):
                    self.assertEqual(len(_rows(case["lines"][-1:])), 1)


class SourceCheckGuardrails(unittest.TestCase):
    def test_resolved_review_keeps_header_conflicts_visible(self):
        for case in _cases("format_review"):
            with self.subTest(case=case["id"]):
                review = fidelity.validate_cv_format_review(json.dumps({"issues": [{
                    "message": "Check the source job.", "source_quote": case["source"], "operation": case["operation"]}]}),
                    case["source"], copy.deepcopy(case["parsed"]))
                self.assertEqual(review["status"], "reviewed")
                self.assertEqual(len(review["issues"]), case["expect_issue_count"], case["note"])
                for issue in review["issues"]:
                    self.assertEqual(issue["can_apply"], case["expect_can_apply"])

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


class SourceRestoreGuardrails(unittest.TestCase):
    def test_generated_blind_contribution_hints_stay_with_returned_text(self):
        category = "Contribution towards Projects / Taskforce"
        for index in range(100):
            original = {"skills": [{"category": category,
                "items": ["Northwind " + str(index), "2020", "Won an award."],
                "item_headings": ["Northwind " + str(index), "2020"]}]}
            reply = copy.deepcopy(original)
            label = "Leading Bank " + str(index)
            reply["skills"][0]["items"][0] = label
            result = blind_mask._blind_restore_cv_bullet_structure(reply, original)
            self.assertEqual(result["skills"][0]["item_headings"], [label, "2020"])
            self.assertNotIn("Northwind", json.dumps(result))
            self.assertEqual(reply["skills"][0]["item_headings"], original["skills"][0]["item_headings"])

    def test_additional_item_separators_keep_same_words_and_shape(self):
        for separator in ["\r", "\r\n", "\n", "\v", "\f", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029"]:
            items = separator.join(["Northwind", "2020", "Won an award."])
            self.assertEqual(normalize._strip_cv_additional_bullet_markers(items),
                             "Northwind\n2020\nWon an award.")

    def test_blind_contribution_headings_use_only_returned_text(self):
        for case in _cases("blind_contribution_headings"):
            with self.subTest(case=case["id"]):
                original, reply = copy.deepcopy(case["original"]), copy.deepcopy(case["reply"])
                result = blind_mask._blind_restore_cv_bullet_structure(reply, original)
                self.assertEqual(result, case["expect"], case["note"])
                self.assertEqual(original, case["original"])
                self.assertEqual(reply, case["reply"])

    def test_contribution_headings(self):
        for case in _cases("contribution_headings"):
            with self.subTest(case=case["id"]):
                result = normalize._normalize_cv_data_for_output(
                    copy.deepcopy(case["parsed"]), "\n".join(case["lines"])
                )
                self.assertEqual(result["skills"], case["expect"], case["note"])

    def test_contribution_layout_preserves_generated_items_and_is_idempotent(self):
        for index in range(200):
            year = str(1980 + index % 45)
            company = "Northwind " + str(index)
            items = [company, year, "2 Annual awards.", "Led a project."]
            parsed = {"work_experiences": [{"company": company + " Bank"}],
                      "skills": [{"category": "Contribution towards Projects / Taskforce", "items": items[:]}]}
            source = "\n".join(["Contribution towards Projects / Taskforce", company, year,
                                "-2 Annual awards.", "- Led a project.", "Education"])
            result = normalize._restore_cv_contribution_headings(parsed, source)
            self.assertEqual(result["skills"][0]["items"], items)
            self.assertEqual(result["skills"][0]["item_headings"], [company, year])
            self.assertEqual(normalize._restore_cv_contribution_headings(copy.deepcopy(result), source), result)

    def test_contribution_optional_scan_is_bounded(self):
        case = _cases("contribution_headings")[0]
        for source in ["x" * 1000001, "line\n" * 12001]:
            parsed = copy.deepcopy(case["parsed"])
            started = time.perf_counter()
            self.assertEqual(normalize._restore_cv_contribution_headings(parsed, source), case["parsed"])
            self.assertLess(time.perf_counter() - started, 1)

    def test_contribution_duplicates_across_generated_entries(self):
        category = "Contribution towards Projects / Taskforce"
        for index in range(100):
            company = "Northwind " + str(index)
            years = [str(1980 + index % 40), str(1981 + index % 40)]
            skills = [
                {"category": category, "items": [company, years[0], "Won an award."],
                 "item_headings": [company, years[0]]},
                {"category": category, "items": [company.upper(), years[1], "Led a project."],
                 "item_headings": [company.upper(), years[1]]},
            ]
            parsed = {"work_experiences": [{"company": company + " Bank"}], "skills": skills}
            source = "\n".join([category, company, years[0], "- Won an award.",
                                years[1], "- Led a project.", "Education"])
            original_items = [s["items"][:] for s in skills]
            result = normalize._restore_cv_contribution_headings(parsed, source)
            self.assertEqual([s["items"] for s in result["skills"]], original_items)
            self.assertEqual([s["item_headings"] for s in result["skills"]], [[y] for y in years])
            self.assertEqual(normalize._restore_cv_contribution_headings(copy.deepcopy(result), source), result)

    def test_contribution_many_duplicate_entries_are_bounded(self):
        category = "Contribution towards Projects / Taskforce"
        parsed = {"work_experiences": [{"company": "Northwind Bank"}],
                  "skills": [{"category": category, "items": ["Northwind", "2020", "Won an award."]}
                             for _ in range(4000)]}
        started = time.perf_counter()
        result = normalize._restore_cv_contribution_headings(
            parsed, "\n".join([category, "Northwind", "2020", "- Won an award.", "Education"]))
        self.assertTrue(all("item_headings" not in s for s in result["skills"]))
        self.assertLess(time.perf_counter() - started, 2)

    def test_company_restore(self):
        for case in _cases("company_restore"):
            with self.subTest(case=case["id"]):
                parsed = {"candidate": {"current_company": case["company"]},
                          "work_experiences": [{"company": case["company"]}]}
                out = reconcile._restore_labelled_company_qualifiers(parsed, "\n".join(case["lines"]))
                self.assertEqual(out["work_experiences"][0]["company"], case["expect"], case["note"])
                self.assertEqual(out["candidate"]["current_company"], case["expect"])

    def test_degree_above_school_scan_stays_fast_on_repeated_input(self):
        source = "Bachelor of Science\nContoso University\nMajor: Physics\n" * 20000
        started = time.perf_counter()
        blocks = normalize._education_source_blocks({"institution": "Contoso University"}, source, for_labels=True)
        self.assertEqual(len(blocks), 20000)
        self.assertEqual(blocks[0], ["Contoso University", "Bachelor of Science", "Major: Physics"])
        self.assertLess(time.perf_counter() - started, 2.0)

    def test_education_restore(self):
        for case in _cases("education_restore"):
            with self.subTest(case=case["id"]):
                entry = dict(case["entry"])
                normalize._recover_education_source_labels(entry, "\n".join(case["lines"]))
                for field, expected in case["expect"].items():
                    self.assertEqual(entry.get(field), expected)


class SummarySalaryGuardrails(unittest.TestCase):
    def test_summary_salary(self):
        for case in _cases("summary_salary"):
            with self.subTest(case=case["id"]):
                self.assertEqual(normalize._cv_strip_pay_from_summary(case["bullets"]), case["expect"], case["note"])

    def test_summary_salary_text(self):
        # The provider's raw summary text, as /generate-ai filters it.
        for case in _cases("summary_salary_text"):
            with self.subTest(case=case["id"]):
                text, removed = normalize._cv_strip_pay_from_summary_text(case["text"])
                self.assertEqual(text, case["expect"], case["note"])
                self.assertEqual(removed, case["removed"])


class DateRewriteGuardrails(unittest.TestCase):
    def test_primary_ocr_precedes_optional_scans(self):
        for case in _cases("ocr_schedule"):
            with self.subTest(case=case["id"]):
                elapsed = [0]
                images = []
                class Image:
                    size = (200, 200)
                    def close(self):
                        self.closed = True
                def render(*args, **kwargs):
                    elapsed[0] += case["render_seconds"]
                    image = Image()
                    images.append(image)
                    return [image]
                renderer = mock.Mock(side_effect=render)
                provider = mock.Mock()
                provider.image_to_string.side_effect = case["texts"]
                semaphore = threading.BoundedSemaphore(1)
                with mock.patch.object(document_safety, "rendered_pdf_page_is_visually_blank", return_value=False):
                    result = document_safety.ocr_pdf_pages_pagewise(b"synthetic", provider,
                        pdf_page_count=lambda _: 3, render_pdf_page_images=renderer, ocr_semaphore=semaphore,
                        max_ocr_pages=30, max_image_pixels=40000, deadline_seconds=180,
                        monotonic=lambda: elapsed[0])
                self.assertEqual(result, {i + 1: text for i, text in enumerate(case["expect"])}, case["note"])
                self.assertEqual([call.kwargs["dpi"] for call in renderer.call_args_list[:3]], [220, 220, 220])
                self.assertTrue(all(image.closed for image in images))
                self.assertTrue(semaphore.acquire(blocking=False))
                semaphore.release()

    def test_ocr_date_recheck(self):
        for case in _cases("ocr_date_recheck"):
            with self.subTest(case=case["id"]):
                self.assertEqual(document_safety._ocr_repair_header_dates(
                    case["primary"], case["alternatives"]), case["expect"], case["note"])

    def test_dates(self):
        for case in _cases("date"):
            with self.subTest(case=case["id"]):
                self.assertEqual(
                    normalize._cv_pretranslate_year_first_month_names(case["text"]), case["expect"]
                )


if __name__ == "__main__":
    unittest.main()
