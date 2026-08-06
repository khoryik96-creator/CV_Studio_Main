import copy
import io
import json
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock
import zipfile

from owner_build_tools import build_protected


_TEMP = tempfile.TemporaryDirectory(prefix="cvstudio-long-cv-")
_ROOT = Path(__file__).resolve().parents[1]
os.environ["CVSTUDIO_DB_PATH"] = str(Path(_TEMP.name) / "state.sqlite3")
os.environ["LOCALAPPDATA"] = str(Path(_TEMP.name) / "local")
build_protected.write_test_receipt(_ROOT)

import app


class LongCvOutputCorrectiveTests(unittest.TestCase):
    def fixture(self):
        return {
            "candidate": {
                "name": "Saik Eng Joo",
                "current_position": "Insurance Agent/Financial Advisor (assumed from duties)",
                "current_company": "MANULIFE",
            },
            "work_experiences": [{
                "date_range": "2023 to Present",
                "company": "Example Sdn Bhd",
                "roles": [{
                    "title": "Insurance Agent/Financial Advisor (likely based on responsibilities)",
                    "date_range": "",
                    "reason_for_leaving": "",
                    "bullets": [
                        "Key responsibilities",
                        '{"heading":"Responsibilities","bullets":["Achievement"]}',
                        '{"bullets":["Successfully achieved over 100% of the annual sales target.","Honored with Best Performing Business Development Manager for year 2024."],"heading":"Business Set up"}',
                        '{"bullets":["Successfully achieved 120% of the annual sales target."],"heading":"Manpower"}',
                        '{"heading":"malformed","bullets":[}',
                    ],
                }],
            }],
            "education": [],
            "certifications": ["", "  "],
            "skills": [{"category": "Skills", "items": "Leadership"}, {"category": "", "items": ""}],
        }

    def test_long_cv_timeout_is_bounded_and_role_dense(self):
        self.assertEqual(app._cv_parse_backend_timeout_seconds("x" * 17999), 180)
        self.assertEqual(app._cv_parse_backend_timeout_seconds("x" * 18000), 300)
        dense = "\n".join(["Key responsibilities"] * 7)
        self.assertEqual(app._cv_parse_backend_timeout_seconds(dense), 180)
        dense += "\nKey achievement"
        self.assertEqual(app._cv_parse_backend_timeout_seconds(dense), 300)

    def test_parse_route_passes_long_timeout_to_provider(self):
        provider_result = {
            "content": [{"type": "text", "text": json.dumps({
                "candidate": {}, "work_experiences": [], "education": [],
                "certifications": [], "skills": [],
            })}],
            "usage": {},
        }
        with (
            mock.patch.object(app, "call_llm", return_value=provider_result) as call,
            mock.patch.object(app, "_ai_spend_session_allowed", return_value=True),
        ):
            response = app.app.test_client().post(
                "/parse",
                json={"api_key": "fixture-key", "cv_text": "x" * 18000},
                headers={"Origin": "http://127.0.0.1:5000", "X-CV-Studio-Request": "1"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(call.call_args.args[2]["_timeout_seconds"], 300)

    def test_structured_normalization_is_idempotent_and_factual(self):
        normalized = app._normalize_cv_structured_content(self.fixture())
        role = normalized["work_experiences"][0]["roles"][0]
        self.assertEqual(normalized["candidate"]["current_position"], "")
        self.assertEqual(role["title"], "")
        self.assertEqual(role["bullets"][0], {
            "heading": "Key responsibilities",
            "bullets": [],
            "kind": "section",
        })
        self.assertEqual(role["bullets"][1], {
            "heading": "Key responsibilities",
            "bullets": ["Achievement"],
            "kind": "section",
        })
        self.assertEqual(role["bullets"][2]["heading"], "Business Set up")
        self.assertEqual(role["bullets"][4], '{"heading":"malformed","bullets":[}')
        self.assertEqual(normalized["certifications"], [])
        self.assertEqual(normalized["skills"], [{"category": "Skills", "items": "Leadership"}])
        self.assertEqual(app._normalize_cv_structured_content(copy.deepcopy(normalized)), normalized)

    def test_standalone_sections_and_bounded_inference_variants_are_normalized(self):
        self.assertEqual(app._normalize_cv_bullet_items(["Key achievement", "Delivered result"]), [
            {"heading": "Key achievements", "bullets": [], "kind": "section"},
            "Delivered result",
        ])
        for title in (
            "Advisor (inferred from duties)",
            "Advisor (implied from responsibilities)",
            "Advisor (assumed from duties)",
            "Advisor (guessed from context)",
            "Advisor (likely based on responsibilities)",
        ):
            self.assertEqual(app._strip_cv_inferred_title(title), "")
        self.assertEqual(app._strip_cv_inferred_title("Advisor"), "Advisor")
        self.assertEqual(app._strip_cv_inferred_title("Advisor (likely to succeed)"), "Advisor (likely to succeed)")

    def test_docx_xml_never_serializes_structured_bullets_or_inferred_title(self):
        response = app.app.test_client().post(
            "/generate-docx",
            json={"data": self.fixture()},
            headers={"Origin": "http://127.0.0.1:5000"},
        )
        self.assertEqual(response.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            document_xml = archive.read("word/document.xml").decode("utf-8")
        self.assertNotIn('&quot;heading&quot;:&quot;Business Set up&quot;', document_xml)
        self.assertNotIn('&quot;heading&quot;:&quot;Responsibilities&quot;', document_xml)
        self.assertNotIn("assumed from duties", document_xml)
        self.assertNotIn("likely based on responsibilities", document_xml)
        self.assertIn("Key responsibilities", document_xml)
        heading_paragraphs = [
            paragraph for paragraph in re.findall(r"<w:p\b.*?</w:p>", document_xml, re.S)
            if "Key responsibilities" in paragraph
        ]
        self.assertTrue(heading_paragraphs)
        self.assertTrue(all("<w:numPr>" not in paragraph for paragraph in heading_paragraphs))
        self.assertIn("Business Set up", document_xml)
        self.assertIn("Successfully achieved over 100%", document_xml)
        self.assertEqual(document_xml.count("<w:t>Skills:</w:t>"), 1)
        self.assertNotIn("E D U C A T I O N S  &amp;  T R A I N I N G", document_xml)
        self.assertNotIn("<w:t>Example Sdn Bhd</w:t></w:r></w:p></w:tc>\n    <w:tc", document_xml)

    def test_prompt_forbids_inferred_titles_and_serialized_groups(self):
        self.assertIn("Never invent, infer, imply, annotate, or explain a title", app.SYSTEM_PROMPT)
        self.assertIn("never as JSON serialized inside a string", app.SYSTEM_PROMPT)

    def test_prompt_keeps_notice_verbatim_cert_dates_and_separate_stints(self):
        # #3 notice period must be copied verbatim, not coerced into a month count.
        self.assertIn("map to candidate.notice_period VERBATIM", app.SYSTEM_PROMPT)
        self.assertNotIn('"notice_period": "X month(s) or empty string"', app.SYSTEM_PROMPT)
        # #4 certification/training dates must be preserved.
        self.assertIn("CERTIFICATION/TRAINING DATES — KEEP THEM", app.SYSTEM_PROMPT)
        # #2 distinct stints at the same employer stay separate entries.
        self.assertIn("SEPARATE STINTS AT THE SAME EMPLOYER", app.SYSTEM_PROMPT)

    def test_prompt_omits_salary_and_remuneration_details(self):
        # Candidates sometimes include current/expected salary or a remuneration
        # section in their source CV; the formatted CV must never carry it over.
        self.assertIn("SALARY / REMUNERATION — OMIT ENTIRELY", app.SYSTEM_PROMPT)
        self.assertIn("expected/asking/desired/target salary", app.SYSTEM_PROMPT)
        # The catch-all extra-section mapping must not re-capture salary content.
        self.assertIn(
            "never apply this catch-all to salary/remuneration/compensation content",
            app.SYSTEM_PROMPT,
        )
        # Notice period stays a first-class candidate field, not salary.
        self.assertIn("Notice period is NOT salary", app.SYSTEM_PROMPT)

    def test_ai_crawler_backend_no_longer_requires_password(self):
        with app.app.test_request_context("/jobadder/spider_options"):
            self.assertTrue(app._ai_crawler_lock_allowed({}))

    def test_company_header_span_recomputed_and_left_candidate_is_last_position(self):
        parsed = {
            "candidate": {"current_position": "Head of Modern Trade", "is_employed": True},
            "work_experiences": [
                {"company": "Mondelez", "date_range": "Jun 2024 to Jul 2026",
                 "roles": [{"title": "Head of Modern Trade", "date_range": ""}]},
                {"company": "Unilever", "date_range": "Jan 2020 to Dec 2019", "roles": [
                    {"title": "Head of Trade Marketing", "date_range": "Jan 2020 to Mar 2021"},
                    {"title": "Head of Sales Operation", "date_range": "Apr 2018 to Dec 2019"},
                    {"title": "National Sales Manager", "date_range": "Dec 2015 to Mar 2018"},
                ]},
            ],
        }
        out = app._order_same_company_roles_newest_first(parsed)
        # #1 backwards/incomplete company header recomputed from roles.
        self.assertEqual(out["work_experiences"][1]["date_range"], "Dec 2015 to Mar 2021")
        # Single-role employer with the date on the entry (not the role) is left as-is.
        self.assertEqual(out["work_experiences"][0]["date_range"], "Jun 2024 to Jul 2026")
        # #3 latest role ends on a concrete past date (no "Present") -> candidate has left.
        self.assertFalse(out["candidate"]["is_employed"])

    def test_present_latest_role_marks_candidate_employed(self):
        parsed = {
            "candidate": {},
            "work_experiences": [
                {"company": "Acme", "date_range": "",
                 "roles": [{"title": "Engineer", "date_range": "Jan 2024 to Present"}]},
            ],
        }
        out = app._order_same_company_roles_newest_first(parsed)
        self.assertTrue(out["candidate"]["is_employed"])

    def test_title_first_header_lines_are_authoritative_over_provider_drift(self):
        # "<Title> — <Company> <DateRange>" lines under an EXPERIENCE heading
        # (date trailing) must be extracted from the source and correct provider
        # hallucinations of employer name, title, and dates.
        cv_text = app._cv_pretranslate_iso_dates(
            "EXPERIENCE\n"
            "Senior Linux System Administrator — Zand Bank 2025-03 – Present\n"
            "AVP Non-Wintel System Administrator — UOB Indonesia 2020-06 – 2025-07\n"
            "Dispatcher Technical Support — PT. Supra Primatama Nusantara (Biznet) 2011-03 – 2013-02\n"
            "IT Support — PT. Elka Prakarsa Utama 2010-01 – 2011-12\n"
            "EDUCATION\n"
            "Bina Nusantara University 2019 – 2021\n"
        )
        rows = app._extract_authoritative_work_rows(cv_text, {})
        # Four work rows; the education line is not captured.
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]["title"], "Senior Linux System Administrator")
        self.assertEqual(rows[0]["company"], "Zand Bank")
        self.assertEqual(rows[1]["date_range"], "Jun 2020 to Jul 2025")
        self.assertEqual(rows[3]["company"], "PT. Elka Prakarsa Utama")

        # Provider hallucinated a different company/title; reconciliation corrects it.
        parsed = {"work_experiences": [
            {"company": "Nusa Network Prakarsa", "date_range": "Feb 2010 to Feb 2011",
             "roles": [{"title": "Customer Care Consultant", "date_range": "", "bullets": ["kept bullet"]}]},
        ]}
        out = app._reconcile_work_experience_with_authoritative_table(parsed, cv_text)
        companies = {e["company"] for e in out["work_experiences"]}
        titles = {r.get("title") for e in out["work_experiences"] for r in e["roles"]}
        self.assertIn("PT. Elka Prakarsa Utama", companies)
        self.assertNotIn("Nusa Network Prakarsa", companies)
        self.assertIn("IT Support", titles)
        self.assertNotIn("Customer Care Consultant", titles)

    def test_prompt_requires_employer_and_title_fidelity(self):
        self.assertIn("EMPLOYER NAME FIDELITY", app.SYSTEM_PROMPT)
        self.assertIn("ROLE TITLE FIDELITY", app.SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
