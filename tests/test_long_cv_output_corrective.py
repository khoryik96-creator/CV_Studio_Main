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
        self.assertEqual(app._cv_parse_backend_timeout_seconds("x" * 7999), 180)
        self.assertEqual(app._cv_parse_backend_timeout_seconds("x" * 8000), 300)
        # A real dense 8-page CV extracts to ~9-10k chars and must get the long
        # (300s) budget, not be cut off at 180s.
        self.assertEqual(app._cv_parse_backend_timeout_seconds("x" * 9808), 300)
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

    def test_parse_retry_does_not_shorten_candidate_content(self):
        # When the first parse returns unrepairable JSON, the retry must NOT ask
        # the model to shorten the CV (a formatter must never silently drop
        # bullets/roles/skills). It re-requests full, complete JSON instead.
        valid = json.dumps({
            "candidate": {}, "work_experiences": [], "education": [],
            "certifications": [], "skills": [],
        })
        calls = []

        def fake_call_llm(provider, api_key, payload):
            calls.append(payload)
            text = "This is not valid JSON at all." if len(calls) == 1 else valid
            return {"content": [{"type": "text", "text": text}], "usage": {}}

        with (
            mock.patch.object(app, "call_llm", side_effect=fake_call_llm),
            mock.patch.object(app, "_ai_spend_session_allowed", return_value=True),
        ):
            response = app.app.test_client().post(
                "/parse",
                json={"api_key": "fixture-key", "cv_text": "Kelana Edy Zainudin\nWork Experience\n"},
                headers={"Origin": "http://127.0.0.1:5000", "X-CV-Studio-Request": "1"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(calls), 2, "the retry strategy should have fired")
        retry_prompt = calls[1]["messages"][0]["content"]
        self.assertNotIn("max 15 words", retry_prompt)
        self.assertNotIn("max 8 bullet", retry_prompt)
        self.assertNotIn("keep output short", retry_prompt)
        self.assertIn("Preserve EVERY", retry_prompt)

    def test_truncated_parse_is_salvaged_and_flagged_degraded(self):
        # A truncated AI response that json.loads cannot read but the bracket
        # salvage (try_close_json) can. The CV must STILL be repaired and
        # returned, and the response must carry a degraded flag + warning so the
        # caller knows completeness is not guaranteed. Flagging never blocks the
        # repair.
        truncated = (
            '{"candidate": {"name": "Jane Doe", "current_company": "Acme"}, '
            '"work_experiences": [{"company": "Acme", "date_range": "2020 to Present", '
            '"roles": [{"title": "Engineer", "date_range": "", "reason_for_leaving": "", '
            '"bullets": ["Built systems", "Led a team'
        )
        calls = []

        def fake_call_llm(provider, api_key, payload):
            calls.append(payload)
            return {"content": [{"type": "text", "text": truncated}], "usage": {}}

        with (
            mock.patch.object(app, "call_llm", side_effect=fake_call_llm),
            mock.patch.object(app, "_ai_spend_session_allowed", return_value=True),
        ):
            response = app.app.test_client().post(
                "/parse",
                json={"api_key": "fixture-key", "cv_text": "Jane Doe\nWork Experience\n"},
                headers={"Origin": "http://127.0.0.1:5000", "X-CV-Studio-Request": "1"},
            )
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        # Salvaged in one shot -- no wasteful Strategy 2/3 re-send.
        self.assertEqual(len(calls), 1)
        # Repair still happened: the readable content is returned.
        self.assertEqual(body["data"]["candidate"]["name"], "Jane Doe")
        # And it is flagged so an incomplete parse is not reported as clean.
        self.assertTrue(body.get("degraded"))
        self.assertEqual(body.get("degraded_reason"), "truncated_response_bracket_salvage")
        self.assertTrue(str(body.get("warning") or "").strip())

    def test_clean_parse_is_not_flagged_degraded(self):
        # A first-try valid parse is lossless and must NOT carry the degraded
        # flag or a warning -- the happy-path response shape is unchanged.
        valid = json.dumps({
            "candidate": {"name": "John Smith"}, "work_experiences": [],
            "education": [], "certifications": [], "skills": [],
        })

        def fake_call_llm(provider, api_key, payload):
            return {"content": [{"type": "text", "text": valid}], "usage": {}}

        with (
            mock.patch.object(app, "call_llm", side_effect=fake_call_llm),
            mock.patch.object(app, "_ai_spend_session_allowed", return_value=True),
        ):
            response = app.app.test_client().post(
                "/parse",
                json={"api_key": "fixture-key", "cv_text": "John Smith\nWork Experience\n"},
                headers={"Origin": "http://127.0.0.1:5000", "X-CV-Studio-Request": "1"},
            )
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["data"]["candidate"]["name"], "John Smith")
        self.assertNotIn("degraded", body)
        self.assertNotIn("warning", body)

    def test_structured_normalization_is_idempotent_and_factual(self):
        normalized = app._normalize_cv_structured_content(self.fixture())
        role = normalized["work_experiences"][0]["roles"][0]
        self.assertEqual(normalized["candidate"]["current_position"], "")
        self.assertEqual(role["title"], "")
        # The orphan "Key responsibilities" label (no bullets of its own,
        # immediately followed by another section) is dropped; the real
        # "Key responsibilities" section with its bullet survives as the first.
        self.assertEqual(role["bullets"][0], {
            "heading": "Key responsibilities",
            "bullets": ["Achievement"],
            "kind": "section",
        })
        self.assertEqual(role["bullets"][1]["heading"], "Business Set up")
        self.assertEqual(role["bullets"][2]["heading"], "Manpower")
        self.assertEqual(role["bullets"][3], '{"heading":"malformed","bullets":[}')
        self.assertEqual(normalized["certifications"], [])
        self.assertEqual(normalized["skills"], [{"category": "Skills", "items": "Leadership"}])
        self.assertEqual(app._normalize_cv_structured_content(copy.deepcopy(normalized)), normalized)

    def test_standalone_sections_and_bounded_inference_variants_are_normalized(self):
        # A standalone label followed by loose bullets absorbs them (rather than
        # rendering as a bare label above orphaned siblings).
        self.assertEqual(app._normalize_cv_bullet_items(["Key achievement", "Delivered result"]), [
            {"heading": "Key achievements", "bullets": ["Delivered result"], "kind": "section"},
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

    def test_docx_education_renders_single_year_and_omits_missing_date_separator(self):
        data = {
            "candidate": {"name": "Education Fixture"},
            "work_experiences": [],
            "education": [
                {
                    "institution": "University of Tenaga Nasional",
                    "degree": "Bachelor's Degree in Computer Science",
                    "date_range": "to 2001",
                },
                {
                    "institution": "Undated University",
                    "degree": "Certificate",
                    "date_range": "",
                },
            ],
            "certifications": [],
            "skills": [],
        }

        response = app.app.test_client().post(
            "/generate-docx",
            json={"data": data},
            headers={"Origin": "http://127.0.0.1:5000"},
        )

        self.assertEqual(response.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            document_xml = archive.read("word/document.xml").decode("utf-8")
        self.assertIn("2001 | University of Tenaga Nasional", document_xml)
        self.assertNotIn("to 2001", document_xml)
        self.assertIn("Undated University", document_xml)
        self.assertNotIn("| Undated University", document_xml)

    def test_docx_renders_linked_cv_summary_bullets_with_inline_bold(self):
        data = {
            "candidate": {"name": "Summary Fixture"},
            "summary_bullets": [
                "**Cloud platforms** leader across regional delivery.",
                "Built engineering teams & delivery standards.",
            ],
            "work_experiences": [
                {
                    "company": "Example Sdn Bhd",
                    "date_range": "Jan 2020 to Present",
                    "roles": [{"title": "Director", "bullets": []}],
                }
            ],
            "education": [],
            "certifications": [],
            "skills": [],
        }

        response = app.app.test_client().post(
            "/generate-docx",
            json={"data": data},
            headers={"Origin": "http://127.0.0.1:5000"},
        )

        self.assertEqual(response.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            document_xml = archive.read("word/document.xml").decode("utf-8")
        self.assertIn("S U M M A R Y", document_xml)
        self.assertIn("Cloud platforms", document_xml)
        self.assertIn("Built engineering teams &amp; delivery standards.", document_xml)
        self.assertLess(document_xml.index("S U M M A R Y"), document_xml.index("W O R K   E X P E R I E N C E S"))
        self.assertRegex(
            document_xml,
            r"<w:r><w:rPr><w:b/><w:bCs/>.*?<w:t>Cloud platforms</w:t></w:r>",
        )

    def test_docx_restores_source_project_training_and_omits_untrusted_metadata(self):
        source = """Other Information
[PROJECT INVOLVEMENT HISTORY]:
* Firewalls Configuring & VPN Services
* Network Infrastructure Enhancement & Redesign
[PARTICIPATED TRAINING PROGRAMME]:
* Enhancing Performance Through Teamwork
* Professional Trainer Programme (Train The Trainer)
[SOFT SKILLS]:
* Vendor Management & Negotiation Skills
"""
        parsed = {
            "candidate": {"name": "Kwong Yew Leong"},
            "work_experiences": [],
            "education": [],
            "certifications": [],
            "skills": [
                {
                    "category": "Summary",
                    "items": (
                        "Position: Retrieved Resumes (SiVA folder: Prescreened); "
                        "Date Applied: 30 Mar 2022"
                    ),
                },
                {
                    "category": "Portfolio & Links",
                    "items": "GitHub: https://github.com/unknown",
                },
            ],
        }
        normalized = app._normalize_cv_data_for_output(parsed, source)

        response = app.app.test_client().post(
            "/generate-docx",
            json={"data": normalized},
            headers={"Origin": "http://127.0.0.1:5000"},
        )

        self.assertEqual(response.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            document_xml = archive.read("word/document.xml").decode("utf-8")
        self.assertIn("Project Involvement History:", document_xml)
        self.assertIn("Network Infrastructure Enhancement &amp; Redesign", document_xml)
        self.assertIn("Participated Training Programme:", document_xml)
        self.assertIn("Professional Trainer Programme (Train The Trainer)", document_xml)
        self.assertNotIn("Retrieved Resumes", document_xml)
        self.assertNotIn("github.com/unknown", document_xml)

    def test_docx_route_omits_placeholder_github_without_source_context(self):
        response = app.app.test_client().post(
            "/generate-docx",
            json={
                "data": {
                    "candidate": {"name": "Source-Free Export"},
                    "work_experiences": [],
                    "education": [],
                    "certifications": [],
                    "skills": [
                        {
                            "category": "Portfolio & Links",
                            "items": "GitHub: https://github.com/unknown",
                        }
                    ],
                }
            },
            headers={"Origin": "http://127.0.0.1:5000"},
        )

        self.assertEqual(response.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            document_xml = archive.read("word/document.xml").decode("utf-8")
        self.assertNotIn("github.com/unknown", document_xml)
        self.assertNotIn("Portfolio &amp; Links", document_xml)

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

    def test_prompt_omits_recruitment_metadata_and_forbids_invented_links(self):
        self.assertIn("RECRUITMENT-SYSTEM METADATA — OMIT ENTIRELY", app.SYSTEM_PROMPT)
        self.assertIn("https://github.com/unknown", app.SYSTEM_PROMPT)
        self.assertIn("Project Involvement History", app.SYSTEM_PROMPT)
        self.assertIn("Participated Training Programme", app.SYSTEM_PROMPT)

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

    def test_company_first_dash_headers_keep_fields_bullets_and_extra_roles(self):
        # "<Company> — <Title> | <DateRange>" headers (the reverse of the Zand
        # Bank layout). The authoritative-row extractor must NOT swap employer and
        # title, and reconciliation must not blank the bullets or drop a role the
        # single-line row regex could not see (multi-line / undated entries).
        cv_text = app._cv_pretranslate_iso_dates(
            "Work Experience\n"
            "TDCX – Product Support Engineer | Mar 2026 – Present\n"
            "Fujitsu Malaysia Sdn. Bhd. – System Engineer | Nov 2023 – Feb 2026\n"
            "Hong Leong Bank – IT Manager (Unix & Storage) | May 2022 – Nov 2023\n"
            "Hewlett-Packard – ITO Service Delivery | Aug 2009 – Dec 2018\n"
            "Education\n"
        )
        parsed = {
            "candidate": {"current_company": "TDCX", "current_position": "Product Support Engineer"},
            "work_experiences": [
                {"company": "TDCX", "date_range": "Mar 2026 to Present",
                 "roles": [{"title": "Product Support Engineer", "date_range": "Mar 2026 to Present", "bullets": ["b1", "b2", "b3"]}]},
                {"company": "Fujitsu Malaysia Sdn. Bhd.", "date_range": "Nov 2023 to Feb 2026",
                 "roles": [{"title": "System Engineer", "date_range": "Nov 2023 to Feb 2026", "bullets": ["b1"]}]},
                {"company": "Hong Leong Bank", "date_range": "May 2022 to Nov 2023",
                 "roles": [{"title": "IT Manager (Unix & Storage)", "date_range": "May 2022 to Nov 2023", "bullets": ["b1"]}]},
                # Present in the parse but NOT as a one-line table row (multi-line
                # in the real CV). Must survive reconciliation, not be dropped.
                {"company": "Toyota Malaysia", "date_range": "Dec 2018 to May 2022",
                 "roles": [{"title": "Resident Infrastructure Engineer", "date_range": "Dec 2018 to May 2022", "bullets": ["b1", "b2"]}]},
                {"company": "Hewlett-Packard", "date_range": "Aug 2009 to Dec 2018",
                 "roles": [{"title": "ITO Service Delivery", "date_range": "Aug 2009 to Dec 2018", "bullets": ["b1"]}]},
            ],
        }

        # Fix A: the extracted rows must not swap title/company.
        rows = app._extract_authoritative_work_rows(cv_text, parsed)
        tdcx_row = next(r for r in rows if app._cv_match_key(r["company"]) == app._cv_match_key("TDCX"))
        self.assertEqual(app._cv_match_key(tdcx_row["title"]), app._cv_match_key("Product Support Engineer"))

        # Fix B: reconciliation preserves every role (incl. the off-table one) with bullets.
        out = app._reconcile_work_experience_with_authoritative_table(
            __import__("json").loads(__import__("json").dumps(parsed)), cv_text)
        companies = [e["company"] for e in out["work_experiences"]]
        self.assertEqual(len(out["work_experiences"]), 5)
        self.assertIn("Toyota Malaysia", companies)
        self.assertEqual(out["work_experiences"][0]["company"], "TDCX")
        self.assertEqual(out["work_experiences"][0]["roles"][0]["title"], "Product Support Engineer")
        self.assertTrue(all(e["roles"][0]["bullets"] for e in out["work_experiences"]))
        self.assertEqual(out["candidate"]["current_company"], "TDCX")
        self.assertEqual(out["candidate"]["current_position"], "Product Support Engineer")

    def test_prompt_requires_employer_and_title_fidelity(self):
        self.assertIn("EMPLOYER NAME FIDELITY", app.SYSTEM_PROMPT)
        self.assertIn("ROLE TITLE FIDELITY", app.SYSTEM_PROMPT)

    def test_all_languages_kept_despite_interleaved_two_column_layout(self):
        # LANGUAGES sidebar interleaved with work history by PDF extraction: all
        # three declared languages must survive (not just the first), and be
        # canonicalised. A language with no source line is still dropped.
        cv_text = (
            "LANGUAGES Head of Modern Trade 07/2023 - 05/2024\n"
            "Reckitt\n"
            "Chinese (Professional Working):\n"
            "• Reignited MT business with quarter-to-quarter growth\n"
            "Malay (Professional Working):\n"
            "• Led both MT key account management teams\n"
            "English (Professional Working):\n"
        )
        parsed = {"candidate": {"languages": "Chinese, Malay, English, French"}}
        out = app._normalize_candidate_languages(parsed, cv_text)
        result = out["candidate"]["languages"]
        self.assertIn("English", result)
        self.assertIn("Bahasa Malaysia", result)
        self.assertIn("Chinese", result)
        self.assertNotIn("French", result)  # no source line -> dropped


if __name__ == "__main__":
    unittest.main()
