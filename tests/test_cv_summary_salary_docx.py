"""The candidate's pay never reaches the Summary box of a Word file.

A generated summary is written from the whole CV, and a CV can state the
candidate's current and expected salary. The browser already removes pay
sentences from the summary it shows (tests/test_cv_summary_salary_parity.js);
the server removes them again on both routes that write the box, so no summary
that bypassed the page -- or was generated before this rule existed -- can put a
salary in a CV sent to a client. The rule itself is pinned by the "summary_salary"
cases in tests/fixtures/cv_guardrail_cases.json. All data is synthetic.
"""

import io
import json
import os
from pathlib import Path
import tempfile
import unittest
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

    def test_a_summary_without_pay_is_written_unchanged(self):
        clean = ["**Senior Data Engineer** with 11 years in banking.", "Built streaming pipelines."]
        self.assertEqual(app._cv_strip_pay_from_summary(list(clean)), clean)
        xml = _document_xml(self._format(clean))
        self.assertIn("Built streaming pipelines.", xml)

    def test_the_summary_instructions_forbid_pay(self):
        source = (ROOT / "vendor" / "cvstudio" / "candidate-summary.js").read_text(encoding="utf-8")
        self.assertIn("Never mention the candidate\\'s salary or pay in any form", source)


if __name__ == "__main__":
    unittest.main()
