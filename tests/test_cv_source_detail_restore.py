"""Source details a provider drops are put back before the CV is written.

The reported CV came back with three small losses even after its employers were
fixed: the bank in "company: <outsourcer> sdn bhd(<bank> sdn bhd)" was cut from the
employer name, "CGPA 2.0 / 4.0" arrived as a bare "2.0 / 4.0", and the "Major"
lines under two qualifications disappeared because education had no field for
them. The provider is told to keep all three, and still did not, so each is also
restored from the source after the parse.

Driven through the real /parse and /generate-docx routes, with only the provider
call replaced. All names are synthetic.
"""

import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

from owner_build_tools.build_protected import write_test_receipt

ROOT = Path(__file__).resolve().parents[1]
_MODULE_TEMPORARY = tempfile.TemporaryDirectory(prefix="cvstudio-source-detail-")
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
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

# Laid out as the upload route delivers the reported CV: labelled employers, a
# date | title row, and education rows with Major / CGPA lines beneath them.
SOURCE = "\n".join([
    "Personal Info",
    "Name: Test Candidate",
    "Experience",
    "company: Northwind outsourcing sdn bhd(contoso bank sdn bhd) | Industry Banking",
    "Jun 2025 - current | Senior Data Engineer",
    "-Built batch pipelines.",
    "-Built e-statement pipelines.",
    "Experience",
    "Company: Fabrikam Games Sdn Bhd | Industry:Gaming",
    "Sep 2024 - Apr 2025 | Data Engineer",
    "-Built streaming pipelines.",
    "Education",
    "2003-2006\tNORTHWIND UNIVERSITY | Bachelor's Degree in Computer Science | Australia",
    "Major\tIT and management",
    " \tCGPA\t2.0 / 4.0",
    "2002-2002 CONTOSO INSTITUTE | Certificate in computer science",
    "2000-2001\tSekolah Menengah Contoh | SPM in Sciences | Malaysia",
    " \tMajor\tscience",
    " \tGrade\tGrade A",
    "SUMMARY:",
    "Data engineer with batch and streaming experience.",
])


def _provider_parse(**overrides):
    """What the provider returned for the reported CV: bracket, label and majors lost."""
    parsed = {
        "candidate": {"name": "Test Candidate", "current_company": "Northwind Outsourcing Sdn Bhd",
                      "current_position": "Senior Data Engineer"},
        "work_experiences": [
            {"date_range": "Jun 2025 to Present", "company": "Northwind Outsourcing Sdn Bhd", "roles": [
                {"title": "Senior Data Engineer", "bullets": ["Built batch pipelines.", "Built e-statement pipelines."]}]},
            {"date_range": "Sep 2024 to Apr 2025", "company": "Fabrikam Games Sdn Bhd", "roles": [
                {"title": "Data Engineer", "bullets": ["Built streaming pipelines."]}]},
        ],
        "education": [
            {"date_range": "2003 to 2006", "institution": "Northwind University",
             "degree": "Bachelor's Degree in Computer Science", "cgpa": "2.0 / 4.0"},
            {"date_range": "2002", "institution": "Contoso Institute", "degree": "Certificate in Computer Science"},
            {"date_range": "2000 to 2001", "institution": "Sekolah Menengah Contoh",
             "degree": "SPM in Sciences", "honors": "Grade A"},
        ],
        "certifications": [], "skills": [],
    }
    parsed.update(overrides)
    return parsed


class SourceDetailRestoreTests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()

    def _parse(self, parsed, source=SOURCE):
        def fake_call(provider, key, payload):
            return {"content": [{"type": "text", "text": json.dumps(parsed)}], "usage": {}}

        originals = (app.call_llm, app._ai_spend_session_allowed, app._resolve_request_api_key)
        app.call_llm = fake_call
        app._ai_spend_session_allowed = lambda *a, **k: True
        app._resolve_request_api_key = lambda *a, **k: "fixture-key"
        try:
            response = self.client.post("/parse", json={"cv_text": source}, headers=HEADERS)
        finally:
            app.call_llm, app._ai_spend_session_allowed, app._resolve_request_api_key = originals
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()

    def _docx_text(self, data):
        response = self.client.post("/generate-docx", json={"data": data}, headers=HEADERS)
        self.assertEqual(response.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            root = ET.fromstring(archive.read("word/document.xml"))
        return ["".join(t.text or "" for t in p.iter(W + "t")) for p in root.iter(W + "p")]

    def test_the_bracketed_brand_is_back_in_the_employer_name(self):
        data = self._parse(_provider_parse())["data"]
        self.assertEqual(data["work_experiences"][0]["company"],
                         "Northwind Outsourcing Sdn Bhd (Contoso Bank Sdn Bhd)")
        self.assertEqual(data["candidate"]["current_company"],
                         "Northwind Outsourcing Sdn Bhd (Contoso Bank Sdn Bhd)")
        # Only the employer whose source name carries a bracket changes.
        self.assertEqual(data["work_experiences"][1]["company"], "Fabrikam Games Sdn Bhd")

    def test_the_cgpa_label_and_majors_are_back(self):
        education = self._parse(_provider_parse())["data"]["education"]
        self.assertEqual(education[0]["cgpa"], "CGPA 2.0 / 4.0")
        self.assertEqual(education[0]["major"], "IT and management")
        self.assertNotIn("major", education[1])
        self.assertEqual(education[2]["major"], "Science")
        self.assertEqual(education[2]["honors"], "Grade A")

    def test_the_restored_parse_is_not_flagged(self):
        out = self._parse(_provider_parse())
        self.assertTrue(out["fidelity"]["ok"], out["fidelity"])
        self.assertNotIn("warning", out)

    def test_all_three_reach_the_word_document(self):
        lines = self._docx_text(self._parse(_provider_parse())["data"])
        text = "\n".join(lines)
        self.assertIn("Northwind Outsourcing Sdn Bhd (Contoso Bank Sdn Bhd)", text)
        self.assertIn("CGPA 2.0 / 4.0", lines)
        self.assertIn("Major: IT and management", lines)
        self.assertIn("Major: Science", lines)
        # The major sits under its own qualification, right after the degree.
        degree = lines.index("Bachelor's Degree in Computer Science")
        self.assertEqual(lines[degree + 1], "Major: IT and management")

    def test_a_parse_that_kept_everything_is_left_alone(self):
        kept = _provider_parse()
        kept["work_experiences"][0]["company"] = "Northwind Outsourcing Sdn Bhd (Contoso Bank Sdn Bhd)"
        kept["candidate"]["current_company"] = "Northwind Outsourcing Sdn Bhd (Contoso Bank Sdn Bhd)"
        kept["education"][0].update(cgpa="CGPA 2.0 / 4.0", major="IT and management")
        data = self._parse(kept)["data"]
        self.assertEqual(data["work_experiences"][0]["company"],
                         "Northwind Outsourcing Sdn Bhd (Contoso Bank Sdn Bhd)")
        self.assertEqual(data["education"][0]["cgpa"], "CGPA 2.0 / 4.0")
        self.assertEqual(data["education"][0]["major"], "IT and management")

    def test_nothing_is_added_that_the_source_does_not_say(self):
        plain = "\n".join([
            "Experience", "Company: Northwind Outsourcing Sdn Bhd | Industry Banking",
            "Jun 2025 - current | Senior Data Engineer", "-Built batch pipelines.",
            "Education", "2003-2006 NORTHWIND UNIVERSITY | Bachelor's Degree in Computer Science",
            "Result 2.0 / 4.0",
        ])
        parsed = _provider_parse()
        parsed["education"] = parsed["education"][:1]
        data = self._parse(parsed, source=plain)["data"]
        self.assertEqual(data["work_experiences"][0]["company"], "Northwind Outsourcing Sdn Bhd")
        self.assertEqual(data["education"][0]["cgpa"], "2.0 / 4.0")
        self.assertNotIn("major", data["education"][0])

    def test_an_entry_without_a_major_prints_no_major_line(self):
        lines = self._docx_text(_provider_parse())
        self.assertFalse([line for line in lines if line.startswith("Major:")])


if __name__ == "__main__":
    unittest.main()
