"""A job title above a "Company | Place | Dates" row, through /parse and the Word file.

A reported CV wrote each job as a title line with "<Employer> | <City, Country> |
<dates>" beneath it. The work-row reader took the title as the company's line
and the place as the company, glued each next job's title onto the previous
job's last bullet, and split "<Employer> – <Brand>" at the dash. The reconciler
then printed every job under "Kuala Lumpur, Malaysia", made the place the
candidate's current company, and dropped the stated graduation years. Even a
perfect provider parse came out broken.

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
_MODULE_TEMPORARY = tempfile.TemporaryDirectory(prefix="cvstudio-title-above-")
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
PLACE = "Kuala Lumpur, Malaysia"

SOURCE = "\n".join([
    "TEST CANDIDATE",
    "Brand Strategy & Marketing Leadership",
    "PROFESSIONAL SUMMARY",
    "Marketing leader with 20 years of experience.",
    "PROFESSIONAL EXPERIENCE",
    "Independent Marketing Consultant",
    "Self-employed | Kuala Lumpur, Malaysia | Jun 2025 – Present",
    "Providing fractional marketing leadership to consumer businesses.",
    "General Manager – Head of Consumer Electronics",
    "Acme Holdings | Kuala Lumpur, Malaysia | Apr 2019 – Dec 2024",
    "Served as commercial owner for six consumer categories.",
    "• Led the companywide brand programme, reporting",
    "to the President Director and a cross-functional team.",
    "• Improved margin by 3% across categories.",
    "• Built a dedicated sales team for three categories.",
    "Product Marketing Manager – Audio and Imaging",
    "Acme Holdings | Kuala Lumpur, Malaysia | Apr 2014 – Mar 2019",
    "Additional role: Marketing Communication Manager | Jun 2016 – Mar 2019",
    "• Led integrated marketing programmes across the portfolio.",
    "• Built the creative community programme.",
    "Supervisor – Sales and Marketing",
    "Acme Holdings | Kuala Lumpur, Malaysia | Jul 2007 – Mar 2014",
    "• Managed modern trade sales.",
    "• Moved into marketing for audio and imaging.",
    "Marketing Manager",
    "Contoso Media – Northwind Books| Kuala Lumpur, Malaysia | Aug 2002 – Apr 2007",
    "Progressed from retail operations to managing marketing programmes.",
    "ENTREPRENEURIAL EXPERIENCE",
    "Co-Founder and Strategic Lead",
    "Fabrikam Studio – Tailspin Film School | Kuala Lumpur, Malaysia | 2025 – Present",
    "Co-founded a vocational education business.",
    "EDUCATION",
    "• Master of Management – Northwind Business School, graduated 2007.",
    "• Bachelor of Mechanical Engineering – Contoso University, graduated 2002.",
])

GM_BULLETS = [
    "Led the companywide brand programme, reporting to the President Director and a cross-functional team.",
    "Improved margin by 3% across categories.",
    "Built a dedicated sales team for three categories.",
]
PMM_BULLETS = [
    "Led integrated marketing programmes across the portfolio.",
    "Built the creative community programme.",
]
SUP_BULLETS = ["Managed modern trade sales.", "Moved into marketing for audio and imaging."]


def _role(title, bullets, date=""):
    return {"title": title, "date_range": date, "bullets": list(bullets)}


def _provider_parse():
    """A correct reading of the source, as a good provider returns it."""
    return {
        "candidate": {"name": "Test Candidate", "current_position": "Independent Marketing Consultant",
                      "current_company": "Self-employed"},
        "summary_bullets": [],
        "work_experiences": [
            {"company": "Self-employed", "date_range": "Jun 2025 to Present", "roles": [
                _role("Independent Marketing Consultant",
                      ["Providing fractional marketing leadership to consumer businesses."], "Jun 2025 to Present")]},
            {"company": "Acme Holdings", "date_range": "Jul 2007 to Dec 2024", "roles": [
                _role("General Manager – Head of Consumer Electronics",
                      ["Served as commercial owner for six consumer categories."] + GM_BULLETS, "Apr 2019 to Dec 2024"),
                _role("Product Marketing Manager – Audio and Imaging",
                      ["Additional role: Marketing Communication Manager (Jun 2016 to Mar 2019)."] + PMM_BULLETS,
                      "Apr 2014 to Mar 2019"),
                _role("Supervisor – Sales and Marketing", SUP_BULLETS, "Jul 2007 to Mar 2014"),
            ]},
            {"company": "Contoso Media – Northwind Books", "date_range": "Aug 2002 to Apr 2007", "roles": [
                _role("Marketing Manager",
                      ["Progressed from retail operations to managing marketing programmes."], "Aug 2002 to Apr 2007")]},
            {"company": "Fabrikam Studio – Tailspin Film School", "date_range": "2025 to Present", "roles": [
                _role("Co-Founder and Strategic Lead", ["Co-founded a vocational education business."], "2025 to Present")]},
        ],
        # The provider left the stated graduation years out.
        "education": [
            {"institution": "Northwind Business School", "degree": "Master of Management", "date_range": ""},
            {"institution": "Contoso University", "degree": "Bachelor of Mechanical Engineering", "date_range": ""},
        ],
        "certifications": [], "skills": [],
    }


class TitleAbovePlaceRowTests(unittest.TestCase):
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

    def _docx_lines(self, data):
        response = self.client.post("/generate-docx", json={"data": data}, headers=HEADERS)
        self.assertEqual(response.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            root = ET.fromstring(archive.read("word/document.xml"))
        return ["".join(t.text or "" for t in p.iter(W + "t")) for p in root.iter(W + "p")]

    def test_every_employer_and_title_is_the_sources(self):
        data = self._parse(_provider_parse())["data"]
        self.assertEqual(
            [(e["company"], [r["title"] for r in e["roles"]]) for e in data["work_experiences"]],
            [
                ("Self-employed", ["Independent Marketing Consultant"]),
                ("Acme Holdings", ["General Manager – Head of Consumer Electronics",
                                   "Product Marketing Manager – Audio and Imaging",
                                   "Supervisor – Sales and Marketing"]),
                ("Contoso Media – Northwind Books", ["Marketing Manager"]),
                ("Fabrikam Studio – Tailspin Film School", ["Co-Founder and Strategic Lead"]),
            ],
        )
        self.assertEqual(data["candidate"]["current_company"], "Self-employed")
        self.assertEqual(data["candidate"]["current_position"], "Independent Marketing Consultant")

    def test_no_title_is_glued_onto_a_bullet(self):
        data = self._parse(_provider_parse())["data"]
        acme = data["work_experiences"][1]["roles"]
        self.assertEqual(acme[0]["bullets"][-1], GM_BULLETS[-1])
        self.assertEqual(acme[1]["bullets"][-1], PMM_BULLETS[-1])
        self.assertEqual(acme[2]["bullets"][-1], SUP_BULLETS[-1])
        # The provider's intro line and additional role survive.
        self.assertIn("Served as commercial owner for six consumer categories.", acme[0]["bullets"])
        self.assertIn("Additional role: Marketing Communication Manager (Jun 2016 to Mar 2019).", acme[1]["bullets"])

    def test_the_graduation_years_are_back(self):
        education = self._parse(_provider_parse())["data"]["education"]
        self.assertEqual([e["date_range"] for e in education], ["2007", "2002"])

    def test_the_word_document_names_no_place_as_an_employer(self):
        lines = self._docx_lines(self._parse(_provider_parse())["data"])
        text = "\n".join(lines)
        self.assertNotIn(PLACE, text)
        self.assertIn("Contoso Media – Northwind Books", text)
        for title in ("Product Marketing Manager – Audio and Imaging", "Supervisor – Sales and Marketing",
                      "Marketing Manager"):
            self.assertFalse([line for line in lines if line.endswith(". " + title)], title)
        self.assertTrue([line for line in lines if "2007" in line and "Northwind Business School" in line])

    def test_a_row_with_no_title_above_keeps_the_providers_reading(self):
        # With the first title line missing the reader is unsure about that row,
        # so the provider's own reading of the job is kept, never the place.
        source = SOURCE.replace("Independent Marketing Consultant\n", "", 1)
        data = self._parse(_provider_parse(), source=source)["data"]
        self.assertNotIn(PLACE, [e["company"] for e in data["work_experiences"]])
        self.assertNotEqual(data["candidate"]["current_company"], PLACE)
        self.assertEqual(data["work_experiences"][0]["company"], "Self-employed")


if __name__ == "__main__":
    unittest.main()
