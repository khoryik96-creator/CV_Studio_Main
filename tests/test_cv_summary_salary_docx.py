"""The candidate's pay never reaches the generated Summary box.

A generated summary is written from the whole CV, and a CV can state the
candidate's current and expected salary. The one filter
(_cv_strip_pay_from_summary in cvstudio_cv_normalize.py) runs where each summary
is made -- /generate-ai for the CV Summary callers, /blind for a promoted source
summary -- so the preview shows exactly what the Word file will carry, and
/generate-docx runs it again on both of its paths as a last net. The rule itself
is pinned by the "summary_salary" cases in tests/fixtures/cv_guardrail_cases.json.
All data is synthetic.
"""

import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

from owner_build_tools.build_protected import write_test_receipt

ROOT = Path(__file__).resolve().parents[1]
_MODULE_TEMPORARY = tempfile.TemporaryDirectory(prefix="cvstudio-summary-salary-")
_ORIGINAL_DATABASE_OVERRIDE = os.environ.get("CVSTUDIO_DB_PATH")
os.environ["CVSTUDIO_DB_PATH"] = str(Path(_MODULE_TEMPORARY.name) / "state" / "cv_studio.sqlite3")
write_test_receipt(ROOT)
try:
    import app
finally:
    if _ORIGINAL_DATABASE_OVERRIDE is None:
        os.environ.pop("CVSTUDIO_DB_PATH", None)
    else:
        os.environ["CVSTUDIO_DB_PATH"] = _ORIGINAL_DATABASE_OVERRIDE

HEADERS = {"Origin": "http://127.0.0.1:5000", "X-CV-Studio-Request": "1"}

SUMMARY = [
    "**Senior Data Engineer** with 11 years in banking and gaming.",
    "Built streaming pipelines on Apache Flink. Expected salary RM16,000 per month.",
    "Current salary of MYR 12,000; salary expectations are negotiable.",
    "Expertise in compensation and benefits reporting for 500 staff.",
]
PAY_TEXT = ("RM16,000", "MYR 12,000", "Expected salary", "salary expectations")


def _cv(summary_bullets):
    return {
        "candidate": {"name": "Test Candidate", "current_company": "Northwind Data Sdn Bhd",
                      "current_position": "Senior Data Engineer"},
        "summary_bullets": summary_bullets,
        "work_experiences": [
            {"date_range": "Jun 2025 to Present", "company": "Northwind Data Sdn Bhd",
             "roles": [{"title": "Senior Data Engineer", "bullets": ["Built batch pipelines."]}]},
        ],
        "education": [], "certifications": [], "skills": [],
    }


def _document_xml(docx_bytes):
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as archive:
        return archive.read("word/document.xml").decode("utf-8")


class SummarySalaryDocxTests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()

    def _format(self, summary_bullets):
        response = self.client.post("/generate-docx", json={"data": _cv(summary_bullets)}, headers=HEADERS)
        self.assertEqual(response.status_code, 200)
        return response.data

    def test_format_cv_never_writes_pay_into_the_summary_box(self):
        xml = _document_xml(self._format(SUMMARY))
        for text in PAY_TEXT:
            self.assertNotIn(text, xml)
        # Everything that is not pay is kept, including the rest of a bullet that
        # also stated pay, and HR work that merely mentions compensation.
        self.assertIn("Senior Data Engineer", xml)
        self.assertIn("Built streaming pipelines on Apache Flink.", xml)
        self.assertIn("Expertise in compensation and benefits reporting for 500 staff.", xml)

    def test_the_uploaded_docx_summary_path_never_writes_pay(self):
        source = self._format(["Placeholder summary."])
        response = self.client.post(
            "/generate-docx",
            data={"source_docx": (io.BytesIO(source), "CV.docx"), "summary_bullets": json.dumps(SUMMARY)},
            content_type="multipart/form-data", headers={"Origin": "http://127.0.0.1:5000"},
        )
        self.assertEqual(response.status_code, 200)
        xml = _document_xml(response.data)
        for text in PAY_TEXT:
            self.assertNotIn(text, xml)
        self.assertIn("Built streaming pipelines on Apache Flink.", xml)
        self.assertIn("Expertise in compensation and benefits reporting for 500 staff.", xml)

    def test_the_uploaded_docx_path_reports_what_it_removed(self):
        source = self._format(["Placeholder summary."])
        response = self.client.post(
            "/generate-docx",
            data={"source_docx": (io.BytesIO(source), "CV.docx"),
                  "summary_bullets": json.dumps(["Built pipelines.", "Current salary RM 9k; expected RM 11k."])},
            content_type="multipart/form-data", headers={"Origin": "http://127.0.0.1:5000"},
        )
        self.assertEqual(response.status_code, 200)
        # One sentence, counted once however many clauses it had.
        self.assertEqual(response.headers.get("X-CV-Summary-Pay-Removed"), "1")
        clean = self.client.post(
            "/generate-docx",
            data={"source_docx": (io.BytesIO(source), "CV.docx"), "summary_bullets": json.dumps(["Built pipelines."])},
            content_type="multipart/form-data", headers={"Origin": "http://127.0.0.1:5000"},
        )
        self.assertEqual(clean.status_code, 200)
        self.assertNotIn("X-CV-Summary-Pay-Removed", clean.headers)

    def test_the_upload_helper_filters_once_and_keeps_its_old_shape(self):
        source = self._format(["Placeholder summary."])
        calls = []
        real = app._cv_strip_pay_from_summary_counted

        def counted(bullets):
            calls.append(1)
            return real(bullets)

        with mock.patch.object(app, "_cv_strip_pay_from_summary_counted", side_effect=counted):
            document, removed = app._insert_summary_into_docx_bytes_counted(
                source, ["Built pipelines.", "Expected salary RM 9k."])
        self.assertEqual((len(calls), removed), (1, 1))
        self.assertNotIn("RM 9k", _document_xml(document))
        # The original helper still returns the document alone.
        self.assertIsInstance(app._insert_summary_into_docx_bytes(source, ["Built pipelines."]), bytes)

    def test_the_filter_reads_only_what_the_word_file_can_use(self):
        seen = []
        real = app._cv_strip_pay_from_summary_counted

        def counted(bullets):
            seen.append(bullets)
            return real(bullets)

        huge = ["Built pipelines. " * 5000] + ["Led a team."] * 500
        with mock.patch.object(app, "_cv_strip_pay_from_summary_counted", side_effect=counted):
            response = self.client.post("/generate-docx", json={"data": _cv(huge)}, headers=HEADERS)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(seen[-1]), app._CV_SUMMARY_FILTER_MAX_ITEMS)
        self.assertLessEqual(max(len(item) for item in seen[-1]), app._CV_SUMMARY_FILTER_MAX_CHARS)
        # The uploaded-DOCX path reads no more than that either.
        source = self._format(["Placeholder summary."])
        with mock.patch.object(app, "_cv_strip_pay_from_summary_counted", side_effect=counted):
            app._insert_summary_into_docx_bytes_counted(source, huge)
        self.assertEqual(len(seen[-1]), app._CV_SUMMARY_FILTER_MAX_ITEMS)
        self.assertLessEqual(max(len(item) for item in seen[-1]), app._CV_SUMMARY_FILTER_MAX_CHARS)
        # A normal summary is passed through untouched.
        normal = ["Built pipelines.", "Led a team."]
        self.assertEqual(app._bounded_summary_bullets(normal), normal)
        self.assertEqual(app._bounded_summary_bullets([0, None, "x"]), [0, None, "x"])

    def test_a_summary_without_pay_is_written_unchanged(self):
        clean = ["**Senior Data Engineer** with 11 years in banking.", "Built streaming pipelines."]
        self.assertEqual(app._cv_strip_pay_from_summary(list(clean)), clean)
        xml = _document_xml(self._format(clean))
        self.assertIn("Built streaming pipelines.", xml)

    def test_a_summary_that_was_only_pay_says_so(self):
        source = self._format(["Placeholder summary."])
        response = self.client.post(
            "/generate-docx",
            data={"source_docx": (io.BytesIO(source), "CV.docx"),
                  "summary_bullets": json.dumps(["Expected salary RM16,000.", "Salary: RM 12k"])},
            content_type="multipart/form-data", headers={"Origin": "http://127.0.0.1:5000"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("only stated the candidate's pay", response.get_json()["error"])
        # An empty request keeps its original message.
        empty = self.client.post(
            "/generate-docx",
            data={"source_docx": (io.BytesIO(source), "CV.docx"), "summary_bullets": "[]"},
            content_type="multipart/form-data", headers={"Origin": "http://127.0.0.1:5000"},
        )
        self.assertEqual(empty.get_json()["error"], "No CV Summary bullets provided")

    def _generate_ai(self, text, **extra):
        body = {"prompt": "fixture prompt", "provider": "anthropic"}
        body.update(extra)
        with mock.patch.object(app, "_resolve_request_api_key", return_value="<fixture-credential>"), \
                mock.patch.object(app, "_ai_spend_session_allowed", return_value=True), \
                mock.patch.object(app, "call_llm", return_value={
                    "content": [{"type": "text", "text": text}], "usage": {}}):
            response = self.client.post("/generate-ai", json=body, headers=HEADERS)
        self.assertEqual(response.status_code, 200)
        return response.get_json()

    def test_generate_ai_filters_the_summary_when_asked(self):
        raw = "- **Senior engineer** with 11 years.\n- Expected salary RM16,000.\n- Built pipelines."
        out = self._generate_ai(raw, strip_candidate_pay=True)
        self.assertEqual(out["content"][0]["text"], "- **Senior engineer** with 11 years.\n- Built pipelines.")
        self.assertEqual(out["summary_pay_removed"], 1)
        # A clean summary is returned exactly as the provider wrote it.
        clean = self._generate_ai("- Built pipelines.", strip_candidate_pay=True)
        self.assertEqual(clean["content"], [{"type": "text", "text": "- Built pipelines."}])
        self.assertEqual(clean["summary_pay_removed"], 0)

    def test_generate_ai_is_unchanged_for_every_other_caller(self):
        # Blind JD, Company Profile and the rest do not ask, so nothing changes.
        raw = "Offered salary RM16,000 for the role."
        out = self._generate_ai(raw)
        self.assertEqual(out["content"][0]["text"], raw)
        self.assertNotIn("summary_pay_removed", out)
        out = self._generate_ai(raw, strip_candidate_pay="yes")
        self.assertEqual(out["content"][0]["text"], raw)

    def test_the_anonymized_summary_is_filtered_too(self):
        out = self._generate_ai(
            "- Built pipelines.\n- Expected salary RM16,000.",
            strip_candidate_pay=True, feature="summary_anonymized",
            source_cv_text="Test Candidate\nSalary Expectations: 16000",
        )
        self.assertNotIn("RM16,000", out["content"][0]["text"])
        self.assertIn("Built pipelines.", out["content"][0]["text"])

    def test_the_blind_summary_is_filtered_before_the_provider_sees_it(self):
        seen = {}

        def fake_call(provider, key, payload):
            sent = json.loads(payload["messages"][0]["content"].split("\n\n", 1)[1])
            seen["summary"] = sent.get("summary_bullets")
            return {"content": [{"type": "text", "text": json.dumps(sent)}], "usage": {}}

        cv = _cv([])
        cv["skills"] = [{"category": "Summary",
                         "items": "Data engineer with 11 years in banking.\nSeeking a role with salary above 10000."}]
        with mock.patch.object(app, "_resolve_request_api_key", return_value="<fixture-credential>"), \
                mock.patch.object(app, "_ai_spend_session_allowed", return_value=True), \
                mock.patch.object(app, "call_llm", side_effect=fake_call):
            response = self.client.post("/blind", json={"cv_data": cv, "provider": "anthropic"}, headers=HEADERS)
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(seen["summary"], ["Data engineer with 11 years in banking."])
        # The preview the browser gets is the summary the Word file will carry,
        # and the removal is reported.
        self.assertEqual(response.get_json()["data"]["summary_bullets"], ["Data engineer with 11 years in banking."])
        self.assertEqual(response.get_json()["summary_pay_removed"], 1)

    def test_a_format_summary_that_was_only_pay_still_writes_the_cv(self):
        # The summary is one part of the CV: the Word file is still written, with
        # an empty box, and the removal is reported so the page can say so.
        response = self.client.post(
            "/generate-docx", json={"data": _cv(["**Salary:** RM 17,000 per month.", "Expected salary RM 9k."])},
            headers=HEADERS,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("X-CV-Summary-Pay-Removed"), "2")
        xml = _document_xml(response.data)
        self.assertNotIn("RM 17,000", xml)
        self.assertNotIn("RM 9k", xml)
        # Nothing removed, nothing reported.
        clean = self.client.post("/generate-docx", json={"data": _cv(["Built pipelines."])}, headers=HEADERS)
        self.assertEqual(clean.status_code, 200)
        self.assertNotIn("X-CV-Summary-Pay-Removed", clean.headers)
        self.assertEqual(self.client.post("/generate-docx", json={"data": _cv([])}, headers=HEADERS).status_code, 200)

    def test_the_parsed_summary_is_filtered_so_the_preview_matches_the_word_file(self):
        parsed = _cv(["Data engineer with 11 years in banking.", "Current salary of **RM 12,000** per month."])

        def fake_call(provider, key, payload):
            return {"content": [{"type": "text", "text": json.dumps(parsed)}], "usage": {}}

        with mock.patch.object(app, "_resolve_request_api_key", return_value="<fixture-credential>"), \
                mock.patch.object(app, "_ai_spend_session_allowed", return_value=True), \
                mock.patch.object(app, "call_llm", side_effect=fake_call):
            response = self.client.post("/parse", json={"cv_text": "Test Candidate\nData engineer."}, headers=HEADERS)
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(response.get_json()["data"]["summary_bullets"], ["Data engineer with 11 years in banking."])
        self.assertEqual(response.get_json()["summary_pay_removed"], 1)

    def test_a_parse_with_nothing_removed_reports_nothing(self):
        parsed = _cv(["Data engineer with 11 years in banking."])

        def fake_call(provider, key, payload):
            return {"content": [{"type": "text", "text": json.dumps(parsed)}], "usage": {}}

        with mock.patch.object(app, "_resolve_request_api_key", return_value="<fixture-credential>"), \
                mock.patch.object(app, "_ai_spend_session_allowed", return_value=True), \
                mock.patch.object(app, "call_llm", side_effect=fake_call):
            response = self.client.post("/parse", json={"cv_text": "Test Candidate\nData engineer."}, headers=HEADERS)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("summary_pay_removed", response.get_json())

    def test_an_intro_line_is_not_left_as_the_summary(self):
        for raw in ("Here is the summary:\n- Expected salary RM 9k",
                    "Here is the summary:\n1. Salary: RM 9,000\n2. Expected salary RM 10k"):
            with self.subTest(raw=raw):
                out = self._generate_ai(raw, strip_candidate_pay=True)
                self.assertEqual(out["content"], [{"type": "text", "text": ""}])
                self.assertGreater(out["summary_pay_removed"], 0)

    def test_the_summary_instructions_forbid_pay(self):
        source = (ROOT / "vendor" / "cvstudio" / "candidate-summary.js").read_text(encoding="utf-8")
        self.assertIn("Never mention the candidate\\'s salary or pay in any form", source)


if __name__ == "__main__":
    unittest.main()
