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

import copy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET
import zipfile

from owner_build_tools.build_protected import write_test_receipt

ROOT = Path(__file__).resolve().parents[1]
_MODULE_TEMPORARY = tempfile.TemporaryDirectory(prefix="cvstudio-title-above-")
with mock.patch.dict(os.environ, {
    "LOCALAPPDATA": _MODULE_TEMPORARY.name, "APPDATA": _MODULE_TEMPORARY.name,
    "CVSTUDIO_DB_PATH": str(Path(_MODULE_TEMPORARY.name) / "state" / "cv_studio.sqlite3"),
    "CVSTUDIO_STATE_DIR": str(Path(_MODULE_TEMPORARY.name) / "state"),
    "CVSTUDIO_JOB_STATE_PATH": str(Path(_MODULE_TEMPORARY.name) / "jobs.json"),
    "SALARY_COMPARISON_DATA_DIR": str(Path(_MODULE_TEMPORARY.name) / "salary"),
}), mock.patch("pathlib.Path.home", return_value=Path(_MODULE_TEMPORARY.name)), \
        mock.patch("os.path.expanduser", side_effect=lambda path: (
            str(Path(_MODULE_TEMPORARY.name) / path[2:]) if path.startswith("~/") else path)):
    write_test_receipt(ROOT)
    import app

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

    def test_reporting_prose_never_replaces_the_title_in_word(self):
        for phrase in ("Reporting directly to the Finance Director",
                       "Working closely with the Managing Director"):
            with self.subTest(phrase=phrase):
                source = "\n".join([
                    "TEST CANDIDATE", "PROFESSIONAL EXPERIENCE", "Senior Engineer",
                    "Acme Holdings | Singapore | Jan 2022 - Present", "• Built systems.",
                    "Finance Analyst", phrase,
                    "Beta Holdings | Singapore | Jan 2018 - Dec 2021", "• Managed forecasts.",
                ])
                parsed = _provider_parse()
                parsed["work_experiences"] = [
                    {"company": "Acme Holdings", "date_range": "Jan 2022 to Present",
                     "roles": [_role("Senior Engineer", ["Built systems."])]},
                    {"company": "Beta Holdings", "date_range": "Jan 2018 to Dec 2021",
                     "roles": [_role("Finance Analyst", ["Managed forecasts."])]},
                ]
                data = self._parse(parsed, source)["data"]
                self.assertEqual(data["work_experiences"][1]["roles"][0]["title"], "Finance Analyst")
                lines = self._docx_lines(data)
                self.assertIn("Finance Analyst", lines)
                self.assertNotIn(phrase, lines)
                self.assertIn("Built systems.", lines)

    def test_uncertain_history_does_not_delete_a_job_or_its_duties_in_word(self):
        cases = json.loads((ROOT / "tests/fixtures/cv_guardrail_cases.json").read_text(encoding="utf-8"))["cases"]
        case = next(c for c in cases if c["id"] == "R7-incomplete-rebuild-keeps-uncertain-job")
        parsed = _provider_parse()
        parsed["work_experiences"] = copy.deepcopy(case["parsed"]["work_experiences"])
        data = self._parse(parsed, "\n".join(case["lines"]))["data"]
        self.assertEqual(len(data["work_experiences"]), 4)
        self.assertIn("Contoso - Executive Search", [e["company"] for e in data["work_experiences"]])
        lines = self._docx_lines(data)
        self.assertIn("Filled senior vacancies.", lines)
        self.assertIn("Led projects.", lines)

    def test_shared_line_graduation_year_stays_with_its_degree_in_word(self):
        source = SOURCE.split("EDUCATION\n")[0] + (
            "EDUCATION\nBachelor of Science - Contoso University; "
            "Master of Science - Northwind University, graduated 2015."
        )
        parsed = _provider_parse()
        parsed["education"] = [
            {"institution": "Contoso University", "degree": "Bachelor of Science", "date_range": ""},
            {"institution": "Northwind University", "degree": "Master of Science", "date_range": ""},
        ]
        data = self._parse(parsed, source)["data"]
        self.assertEqual({e["institution"]: e["date_range"] for e in data["education"]},
                         {"Contoso University": "", "Northwind University": "2015"})
        lines = self._docx_lines(data)
        self.assertIn("2015 | Northwind University", lines)
        self.assertIn("Contoso University", lines)
        self.assertNotIn("2015 | Contoso University", lines)

    def test_complete_work_rows_still_correct_provider_drift(self):
        source = "\n".join([
            "TEST CANDIDATE", "PROFESSIONAL EXPERIENCE", "Senior Engineer",
            "Acme Holdings | Singapore | Jan 2022 - Present", "• Built systems.",
            "Analyst", "Beta Holdings | Singapore | Jan 2018 - Dec 2021", "• Managed forecasts.",
            "EDUCATION", "An uncertain line below is not a work row.",
            "Contoso Holdings | Singapore | Jan 2010 - Dec 2011",
        ])
        parsed = _provider_parse()
        parsed["work_experiences"] = [
            {"company": "Acme Holdings", "date_range": "Jan 2022 to Present",
             "roles": [_role("Senior Engineer", ["Built systems."])]},
            {"company": "Singapore", "date_range": "Jan 2018 to Dec 2021",
             "roles": [_role("Operations Lead", ["Managed forecasts."])]},
        ]
        data = self._parse(parsed, source)["data"]
        self.assertEqual([e["company"] for e in data["work_experiences"]],
                         ["Acme Holdings", "Beta Holdings"])
        self.assertEqual(data["work_experiences"][1]["roles"][0]["title"], "Analyst")
        self.assertIn("Managed forecasts.", self._docx_lines(data))

    def test_degree_above_school_keeps_its_own_major_and_grade_in_word(self):
        source = SOURCE.split("EDUCATION\n")[0] + "EDUCATION\n" + "\n".join([
            "Bachelor of Science", "Contoso University | 2010", "Major: Physics", "GPA 3.8 / 4.0",
            "Master of Science", "Contoso University | 2015", "Major: Finance", "CGPA 3.8 / 4.0",
        ])
        parsed = _provider_parse()
        parsed["education"] = [
            {"institution": "Contoso University", "degree": "Bachelor of Science",
             "date_range": "2010", "cgpa": "3.8 / 4.0"},
            {"institution": "Contoso University", "degree": "Master of Science",
             "date_range": "", "cgpa": "3.8 / 4.0"},
        ]
        data = self._parse(parsed, source)["data"]
        by_degree = {entry["degree"]: entry for entry in data["education"]}
        self.assertEqual(by_degree["Bachelor of Science"]["major"], "Physics")
        self.assertEqual(by_degree["Master of Science"]["major"], "Finance")
        self.assertEqual(by_degree["Master of Science"]["cgpa"], "CGPA 3.8 / 4.0")
        lines = self._docx_lines(data)
        self.assertEqual(lines[lines.index("Master of Science") + 1], "Major: Finance")

    def test_institution_first_qualifications_keep_the_masters_year_in_word(self):
        for separator in ("; ", " | "):
            with self.subTest(separator=separator):
                source = SOURCE.split("EDUCATION\n")[0] + (
                    "EDUCATION\nContoso University | Bachelor of Science" + separator
                    + "Northwind University | Master of Science | Graduation: 2015"
                )
                parsed = _provider_parse()
                parsed["education"] = [
                    {"institution": "Contoso University", "degree": "Bachelor of Science", "date_range": ""},
                    {"institution": "Northwind University", "degree": "Master of Science", "date_range": ""},
                ]
                data = self._parse(parsed, source)["data"]
                self.assertEqual({entry["institution"]: entry["date_range"] for entry in data["education"]},
                                 {"Contoso University": "", "Northwind University": "2015"})
                lines = self._docx_lines(data)
                self.assertIn("2015 | Northwind University", lines)
                self.assertNotIn("2015 | Contoso University", lines)

    def test_employee_job_role_pay_never_reaches_the_summary_or_word(self):
        parsed = _provider_parse()
        work = "Managed payroll with salary of RM 8k for each employee."
        own_pay = "Led HR with salary of RM 12k for the employee relations manager role."
        parsed["summary_bullets"] = [work, own_pay, "Built the HR function."]
        response = self._parse(parsed)
        self.assertEqual(response["data"]["summary_bullets"], [work, "Built the HR function."])
        self.assertEqual(response["summary_pay_removed"], 1)
        lines = self._docx_lines(response["data"])
        self.assertIn(work, lines)
        self.assertNotIn(own_pay, lines)


if __name__ == "__main__":
    unittest.main()
