"""A label-style table CV, driven through the real routes.

Reported CV: nine employers in the source, six in the output, the three most
recent missing, two education rows rendered as jobs, and every employer shown
as "|". The first two attempts at a fix blamed the AI and tested helpers in
isolation. Driving the real /extract-text and /parse routes showed what actually
happened: a PERFECT provider parse came out exactly that broken, because the
source-table reconciler rebuilt the work history from a table it had misread.

 * The upload route joins each table row's cells with " | ". A row such as
   "Apr 2019 - Mar 2022 | Assistant manager data analyst" has no company cell --
   in this layout the company sits on the line above, "Company: X | Industry: Y"
   -- and the reader took the leftover "|" as the company.
 * The explicit pipe reader was not confined to the work history, so an
   education row "2003-2006 UNIVERSITY | Bachelor's Degree | Australia" read as
   date, company and role.
 * Year-first dates ("2025 june- current") were not recognised, so those rows
   were absent from the table and the rebuild dropped them.

Every test here uses a synthetic CV of the same shape. No real candidate data.
"""

import io
import json
import os
from pathlib import Path
import tempfile
import unittest

from owner_build_tools.build_protected import write_test_receipt


ROOT = Path(__file__).resolve().parents[1]
_MODULE_TEMPORARY = tempfile.TemporaryDirectory(prefix="cvstudio-label-table-")
_ORIGINAL_DATABASE_OVERRIDE = os.environ.get("CVSTUDIO_DB_PATH")
os.environ["CVSTUDIO_DB_PATH"] = str(
    Path(_MODULE_TEMPORARY.name) / "state" / "cv_studio.sqlite3"
)
write_test_receipt(ROOT)
try:
    import app
    import cvstudio_cv_reconcile as reconcile
finally:
    if _ORIGINAL_DATABASE_OVERRIDE is None:
        os.environ.pop("CVSTUDIO_DB_PATH", None)
    else:
        os.environ["CVSTUDIO_DB_PATH"] = _ORIGINAL_DATABASE_OVERRIDE


HEADERS = {"Origin": "http://127.0.0.1:5000", "X-CV-Studio-Request": "1"}

# (company label line, industry, date cell, title, duties). The first three are
# written year-first, exactly as the reported CV wrote its three newest roles.
EMPLOYERS = [
    ("Northwind Data Sdn Bhd", "Banking", "2025 june- current", "Senior Data Engineer"),
    ("Contoso Streams Sdn Bhd", "Gaming", "2024 sept -2025 April", "Data Engineer"),
    ("Fabrikam Games Sdn Bhd", "Gaming", "2022 march - 2024 august", "Senior ETL Data Engineer"),
    ("Tailspin Pay Sdn Bhd", "Finance", "Apr 2019 - Mar 2022", "Assistant manager data analyst"),
    ("Litware Credit Sdn Bhd", "Banking", "Sep 2017 - Apr 2019", "Core Developer"),
    ("Adatum Clinics Sdn Bhd", "Hospitality", "Jun 2015 - august  2017", "Senior Programmer"),
]


def _label_table_docx():
    """A synthetic CV laid out like the reported one: label cells, date | title rows."""
    import docx

    document = docx.Document()
    personal = document.add_table(rows=2, cols=1)
    personal.rows[0].cells[0].text = "Personal Info"
    personal.rows[1].cells[0].text = "Name: Test Candidate"

    work = document.add_table(rows=0, cols=2)
    for index, (company, industry, dates, title) in enumerate(EMPLOYERS):
        if index < 3:
            # The reported CV repeated the section label before each newer role.
            heading = work.add_row().cells
            heading[0].text = "Experience"
        label = work.add_row().cells
        label[0].text = "Company: " + company
        label[1].text = "Industry: " + industry
        role = work.add_row().cells
        role[0].text = dates
        role[1].text = title + "\nposition level: senior executive\n-Delivered duty one for " + title + "\n-Delivered duty two"

    education = document.add_table(rows=3, cols=2)
    education.rows[0].cells[0].text = "Education"
    education.rows[1].cells[0].text = "2003-2006\tNORTHWIND UNIVERSITY"
    education.rows[1].cells[1].text = "Bachelor's Degree in Computer Science | Australia\nMajor\tIT"
    education.rows[2].cells[0].text = "2000-2001\tSekolah Menengah Contoh"
    education.rows[2].cells[1].text = "SPM in Sciences | Malaysia\nGrade A"

    summary = document.add_table(rows=1, cols=1)
    summary.rows[0].cells[0].text = "SUMMARY:\nData engineer with batch and streaming experience."

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _perfect_parse():
    return {
        "candidate": {"name": "Test Candidate", "email": "test@example.com"},
        "education": [
            {"degree": "Bachelor's Degree in Computer Science", "institution": "Northwind University", "date_range": "2003 to 2006"},
            {"degree": "SPM in Sciences", "institution": "Sekolah Menengah Contoh", "date_range": "2000 to 2001"},
        ],
        "certifications": [], "skills": [],
        "work_experiences": [
            {"date_range": d, "company": c, "roles": [
                {"title": t, "date_range": d, "bullets": ["Delivered duty one for " + t, "Delivered duty two"]}]}
            for c, d, t in (
                ("Northwind Data Sdn Bhd", "Jun 2025 to Present", "Senior Data Engineer"),
                ("Contoso Streams Sdn Bhd", "Sep 2024 to Apr 2025", "Data Engineer"),
                ("Fabrikam Games Sdn Bhd", "Mar 2022 to Aug 2024", "Senior ETL Data Engineer"),
                ("Tailspin Pay Sdn Bhd", "Apr 2019 to Mar 2022", "Assistant Manager Data Analyst"),
                ("Litware Credit Sdn Bhd", "Sep 2017 to Apr 2019", "Core Developer"),
                ("Adatum Clinics Sdn Bhd", "Jun 2015 to Aug 2017", "Senior Programmer"),
            )
        ],
    }


class LabelTableRouteTests(unittest.TestCase):
    """The real routes, with only the provider call replaced."""

    def setUp(self):
        self.client = app.app.test_client()
        response = self.client.post(
            "/extract-text",
            data={"file": (io.BytesIO(_label_table_docx()), "label_table.docx")},
            headers=HEADERS, content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.text = response.get_json()["text"]
        self.seen = {}

    def _parse(self, parsed):
        seen = self.seen

        def fake_call(provider, key, payload):
            seen["source"] = payload["messages"][0]["content"]
            return {"content": [{"type": "text", "text": json.dumps(parsed)}], "usage": {}}

        originals = (app.call_llm, app._ai_spend_session_allowed, app._resolve_request_api_key)
        app.call_llm = fake_call
        app._ai_spend_session_allowed = lambda *a, **k: True
        app._resolve_request_api_key = lambda *a, **k: "fixture-key"
        try:
            response = self.client.post("/parse", json={"cv_text": self.text}, headers=HEADERS)
        finally:
            app.call_llm, app._ai_spend_session_allowed, app._resolve_request_api_key = originals
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()

    def test_the_upload_route_joins_a_table_row_onto_one_line(self):
        # Pinned because two earlier fixes were written against a different
        # extractor, which puts each cell on its own line, and did nothing here.
        self.assertIn("2025 june- current | Senior Data Engineer", self.text)
        self.assertIn("Company: Tailspin Pay Sdn Bhd | Industry: Finance", self.text)

    def test_the_model_receives_month_first_dates(self):
        self._parse(_perfect_parse())
        source = self.seen["source"]
        self.assertIn("june 2025- current | Senior Data Engineer", source)
        self.assertIn("sept 2024 -April 2025 | Data Engineer", source)
        self.assertIn("march 2022 - august 2024 | Senior ETL Data Engineer", source)
        self.assertNotIn("2025 june", source)
        # Month-first rows reach the model exactly as written.
        self.assertIn("Apr 2019 - Mar 2022 | Assistant manager data analyst", source)

    def test_a_correct_parse_comes_out_correct(self):
        # The heart of it: on the previous code this exact input came out with the
        # three newest employers dropped, the degree and school as jobs, and every
        # employer rendered as "|".
        out = self._parse(_perfect_parse())
        exps = out["data"]["work_experiences"]
        self.assertEqual(
            [e["company"] for e in exps],
            [c for c, _i, _d, _t in EMPLOYERS],
        )
        for exp in exps:
            with self.subTest(company=exp["company"]):
                self.assertNotIn("|", exp["company"])
        companies = " ".join(e["company"] for e in exps).lower()
        self.assertNotIn("university", companies)
        self.assertNotIn("bachelor", companies)
        self.assertNotIn("spm", companies)
        self.assertFalse(out.get("degraded"))
        self.assertIsNone(out.get("warning"))

    def test_a_parse_that_drops_employers_is_flagged(self):
        parsed = _perfect_parse()
        parsed["work_experiences"] = parsed["work_experiences"][3:]
        out = self._parse(parsed)
        self.assertTrue(out.get("degraded"))
        self.assertEqual(out.get("degraded_reason"), "fidelity_check")
        for company in ("Northwind Data", "Contoso Streams", "Fabrikam Games"):
            with self.subTest(company=company):
                self.assertIn(company, out["warning"])

    def test_nothing_else_the_model_reads_is_changed(self):
        import re
        self._parse(_perfect_parse())
        # The route's own whitespace compression and ISO pass, applied here so the
        # only difference left is the year-first rewrite.
        expected = re.sub(r"\n{3,}", "\n\n", self.text)
        expected = re.sub(r"[ \t]{2,}", " ", expected).strip()
        expected = app._cv_pretranslate_iso_dates(expected)
        # The model's message opens with an instruction line before the CV itself.
        received = self.seen["source"].split("\n\n", 1)[1]
        before, after = expected.splitlines(), received.splitlines()
        self.assertEqual(len(before), len(after))
        changed = [(a, b) for a, b in zip(before, after) if a != b]
        self.assertEqual(
            changed,
            [
                ("2025 june- current | Senior Data Engineer",
                 "june 2025- current | Senior Data Engineer"),
                ("2024 sept -2025 April | Data Engineer",
                 "sept 2024 -April 2025 | Data Engineer"),
                ("2022 march - 2024 august | Senior ETL Data Engineer",
                 "march 2022 - august 2024 | Senior ETL Data Engineer"),
            ],
        )


class AuthoritativeRowReaderTests(unittest.TestCase):
    """The reader the reconciler rebuilds a work history from."""

    def rows(self, lines, titles=()):
        parsed = {"work_experiences": [
            {"company": "Known Co", "roles": [{"title": t}]} for t in titles
        ]}
        return reconcile._extract_authoritative_work_rows("\n".join(lines), parsed)

    def test_a_date_then_title_row_names_no_employer_and_is_left_out(self):
        self.assertEqual(self.rows(
            ["WORK EXPERIENCE", "Apr 2019 - Mar 2022 | Assistant manager data analyst"],
            titles=["Assistant manager data analyst"],
        ), [])

    def test_a_date_then_company_and_title_cell_splits_cleanly(self):
        # These already reached the reader; every one came out prefixed with "|".
        rows = self.rows(
            ["WORK EXPERIENCE",
             "Oct 2022 - Present | EY Technology Solutions Sdn Bhd Manager",
             "Jan 2019 - Sep 2022 | Acme Sdn Bhd Senior Consultant"],
            titles=["Manager", "Senior Consultant"],
        )
        self.assertEqual(
            [(r["company"], r["title"]) for r in rows],
            [("EY Technology Solutions Sdn Bhd", "Manager"), ("Acme Sdn Bhd", "Senior Consultant")],
        )

    def test_a_title_the_provider_did_not_find_is_never_guessed_inside_a_cell(self):
        # The generic title pattern split "Senior Data Engineer" into a company
        # "Senior Data" and a title "Engineer".
        self.assertEqual(self.rows(
            ["WORK EXPERIENCE", "Jun 2025 - Present | Senior Data Engineer"],
        ), [])

    def test_a_separator_is_never_a_company(self):
        # Master read "| | | Engineer" as the company "| | |": the reported bug.
        for company in ("|", " | "):
            with self.subTest(company=company):
                self.assertEqual(self.rows(
                    ["WORK EXPERIENCE", "Jan 2020 - Dec 2021 | " + company + " | Engineer"],
                ), [])

    def test_a_placeholder_company_is_kept_as_it_always_was(self):
        # A CV writes "-" in the company column for a career break or freelance
        # work. That is the source's own content; dropping the row would drop the
        # whole entry from the rebuilt work history. Master kept these rows.
        for company in ("-", "\u2014", "\u2013", "::", "N/A"):
            with self.subTest(company=company):
                rows = self.rows(
                    ["WORK EXPERIENCE", "Jan 2020 - Dec 2021 | " + company + " | Engineer"],
                )
                self.assertEqual(
                    [(r["date_range"], r["company"], r["title"]) for r in rows],
                    [("Jan 2020 to Dec 2021", company, "Engineer")],
                )

    def test_education_rows_are_not_read_as_employment(self):
        self.assertEqual(self.rows([
            "Education",
            "2003-2006 NORTHWIND UNIVERSITY | Bachelor's Degree in Computer Science | Australia",
            "2000-2001 Sekolah Menengah Contoh | SPM in Sciences | Malaysia",
        ]), [])

    def test_a_work_table_after_education_is_still_read(self):
        rows = self.rows([
            "EDUCATION",
            "2003-2006 NORTHWIND UNIVERSITY | Bachelor's Degree | Australia",
            "WORK EXPERIENCE",
            "Jan 2020 - Dec 2021 | Acme Sdn Bhd | Engineer",
            "Jan 2018 - Dec 2019 | Contoso Sdn Bhd | Analyst",
        ])
        self.assertEqual([r["company"] for r in rows], ["Acme Sdn Bhd", "Contoso Sdn Bhd"])

    def test_an_unlisted_work_heading_still_ends_the_education_section(self):
        # Neither the boundary list nor the history pattern knows these, and a work
        # table after them must not be swallowed.
        for heading in ("Employment Record", "Relevant Experience", "Job History"):
            with self.subTest(heading=heading):
                rows = self.rows([
                    "Education",
                    "2003-2006 NORTHWIND UNIVERSITY | Bachelor's Degree | Australia",
                    heading,
                    "Jan 2020 - Dec 2021 | Acme Sdn Bhd | Engineer",
                ])
                self.assertEqual([r["company"] for r in rows], ["Acme Sdn Bhd"])

    def test_a_three_cell_work_table_with_no_heading_is_unchanged(self):
        # No education heading anywhere: the explicit reader behaves exactly as it
        # always did.
        rows = self.rows([
            "Jan 2020 - Dec 2021 | Acme Sdn Bhd | Engineer",
            "Jan 2018 - Dec 2019 | Contoso Sdn Bhd | Analyst",
        ])
        self.assertEqual(
            [(r["company"], r["title"]) for r in rows],
            [("Acme Sdn Bhd", "Engineer"), ("Contoso Sdn Bhd", "Analyst")],
        )

    def test_an_employer_named_after_education_is_still_an_employer(self):
        # Only a line that IS an education heading switches state.
        rows = self.rows([
            "WORK EXPERIENCE",
            "Jan 2020 - Dec 2021 | Ministry of Education | Officer",
            "Jan 2018 - Dec 2019 | Northwind University | Lecturer",
        ])
        self.assertEqual(
            [r["company"] for r in rows], ["Ministry of Education", "Northwind University"]
        )


    def test_a_role_or_employer_starting_with_education_does_not_hide_work_rows(self):
        # Only a line that is an education heading and nothing else enters the
        # section. Starting with the word is not enough.
        for line in ("Education Consultant", "Academic Coordinator", "Educational Designer",
                     "Education Queensland", "Education Officer"):
            with self.subTest(line=line):
                rows = self.rows([
                    "WORK EXPERIENCE",
                    "Jan 2020 - Present | Acme Corp | Senior Engineer",
                    line,
                    "Jan 2018 - Dec 2019 | Beta Bhd | Engineer",
                    "Jan 2016 - Dec 2017 | Gamma Bhd | Engineer",
                ])
                self.assertEqual([r["company"] for r in rows], ["Acme Corp", "Beta Bhd", "Gamma Bhd"])

    def test_a_line_starting_with_education_is_not_a_heading_even_before_a_school_employer(self):
        # A school or university can be the employer. Under a real education
        # heading its row would be set aside, so the heading test itself has to
        # reject a job title that only starts with the word.
        for line in ("Education Consultant", "Academic Coordinator"):
            with self.subTest(line=line):
                rows = self.rows([
                    "WORK EXPERIENCE",
                    "Jan 2020 - Present | Acme Corp | Senior Engineer",
                    line,
                    "Jan 2018 - Dec 2019 | Northwind University | Lecturer",
                    # A row naming a qualification is set aside inside an education
                    # section, so this one is read only if the line above was
                    # correctly NOT taken as an education heading.
                    "Jan 2016 - Dec 2017 | Contoso College | Diploma Programme Lecturer",
                ])
                self.assertEqual(
                    [r["company"] for r in rows],
                    ["Acme Corp", "Northwind University", "Contoso College"],
                )

    def test_a_capitalised_heading_on_no_list_ends_education(self):
        # No work word, no list: only the capitalised-heading rule ends the section,
        # and the work row names a qualification, so without that rule it is lost.
        rows = self.rows([
            "EDUCATION",
            "2003-2006 | Northwind University | Bachelor",
            "WHERE I HAVE WORKED",
            "Jan 2020 - Present | Contoso College | Diploma Programme Coordinator",
        ])
        self.assertEqual([r["company"] for r in rows], ["Contoso College"])

    def test_a_capitalised_heading_ends_education_before_a_school_employer(self):
        rows = self.rows([
            "EDUCATION",
            "2003 - 2006 | Northwind University | Bachelor",
            "POSITIONS HELD",
            "Jan 2020 - Present | Contoso College | Lecturer",
        ])
        self.assertEqual([r["company"] for r in rows], ["Contoso College"])

    def test_education_headings_in_their_usual_forms_are_recognised(self):
        for heading in ("Education", "EDUCATION:", "Educational Background",
                        "Academic Qualifications", "Education & Training", "Education and Training"):
            with self.subTest(heading=heading):
                self.assertEqual(self.rows([
                    heading,
                    "2003-2006 NORTHWIND UNIVERSITY | Bachelor's Degree | Australia",
                ]), [])

    def test_a_work_table_after_education_under_any_heading_is_read(self):
        # Master read these; an earlier draft of the education guard dropped them
        # because the heading was on no list.
        for heading in ("POSITIONS HELD", "APPOINTMENTS", "PROFESSIONAL BACKGROUND",
                        "Positions Held", "Appointments"):
            with self.subTest(heading=heading):
                rows = self.rows([
                    "EDUCATION",
                    "2003 - 2006 | Northwind University | Bachelor",
                    heading,
                    "Jan 2020 - Present | Acme Corp | Engineer",
                    "Jan 2018 - Dec 2019 | Beta Bhd | Analyst",
                ])
                self.assertEqual([r["company"] for r in rows], ["Acme Corp", "Beta Bhd"])

    def test_notes_between_education_rows_do_not_end_the_section(self):
        rows = self.rows([
            "Education",
            "2003-2006 NORTHWIND UNIVERSITY | Bachelor's Degree | Australia",
            "Major IT and management",
            "CGPA 2.0 / 4.0",
            "2002-2002 CONTOSO INSTITUTE | Certificate in computer science | Malaysia",
            "2000-2001 Sekolah Menengah Contoh | SPM | Malaysia",
        ])
        self.assertEqual(rows, [])

    def test_a_company_sharing_the_date_cell_loses_its_separator(self):
        rows = self.rows(
            ["WORK EXPERIENCE", "Jan 2020 - Present Acme Corp | Senior Engineer"],
            titles=["Senior Engineer"],
        )
        self.assertEqual([(r["company"], r["title"]) for r in rows], [("Acme Corp", "Senior Engineer")])

    def test_a_generic_title_is_the_whole_last_cell(self):
        rows = self.rows(["WORK EXPERIENCE", "Jan 2020 - Present Beta Holdings | Data Analyst"])
        self.assertEqual([(r["company"], r["title"]) for r in rows], [("Beta Holdings", "Data Analyst")])

    def test_a_borderless_row_with_no_cells_is_unchanged(self):
        # No separator: the whitespace split behaves exactly as it always did.
        rows = self.rows(["WORK EXPERIENCE", "Jan 2020 - Present Beta Holdings Data Analyst"])
        self.assertEqual([(r["company"], r["title"]) for r in rows], [("Beta Holdings Data", "Analyst")])

    def test_a_referees_block_ends_the_borderless_work_section(self):
        rows = self.rows([
            "WORK EXPERIENCE",
            "Jan 2020 - Present Acme Corp Senior Engineer",
            "REFEREES (available on request)",
            "Jan 2018 - Dec 2019 Beta Holdings Manager",
        ], titles=["Senior Engineer"])
        self.assertEqual([r["company"] for r in rows], ["Acme Corp"])

    def test_an_employer_that_is_a_school_or_foundation_is_kept(self):
        # A heading on no list leaves the education section open. Only a row that
        # names a qualification is set aside there; an institution, a foundation,
        # a Scrum Master or a business analyst ("BA") is a job.
        rows = self.rows([
            "EDUCATION",
            "2003 - 2006 | Northwind University | Bachelor of Science",
            "Where I Have Worked",
            "2019 - Present | Acme Foundation | Program Manager",
            "Jan 2017 - Dec 2018 | Contoso Academy | Trainer",
            "Jan 2015 - Dec 2016 | Northwind Institute | Scrum Master",
            "Jan 2013 - Dec 2014 | Fabrikam College | BA",
        ])
        self.assertEqual(
            [r["company"] for r in rows],
            ["Acme Foundation", "Contoso Academy", "Northwind Institute", "Fabrikam College"],
        )

    def test_a_title_case_positions_held_ends_education(self):
        rows = self.rows([
            "EDUCATION",
            "2003 - 2006 | Northwind University | Bachelor",
            "Positions Held",
            "2019 - Present | Contoso College | Diploma Programme Coordinator",
        ])
        self.assertEqual([r["company"] for r in rows], ["Contoso College"])

    def test_every_kind_of_qualification_row_is_still_set_aside(self):
        for row in ("2001-2002 | Northwind College | Foundation in Science",
                    "2002-2002 | Contoso Institute | Certificate in Accounting",
                    "2003-2005 | Contoso Polytechnic | Diploma in IT",
                    "2006-2008 | Northwind University | Master of Science",
                    "2006-2008 | Northwind University | MBA",
                    "2003-2006 | Northwind University | B.A. Economics",
                    "2000-2001 | Sekolah Menengah Contoh | SPM",
                    "2003-2006 | Northwind University | CGPA 3.5"):
            with self.subTest(row=row):
                # Outside an education section the reader does take this row, so
                # the empty result below is the education guard at work.
                self.assertEqual(len(self.rows([row])), 1)
                self.assertEqual(self.rows(["Education", row]), [])

    def test_an_institution_on_its_own_line_does_not_end_education(self):
        row = "2003-2006 | Bachelor of Science | Australia"
        self.assertEqual(len(self.rows([row])), 1)
        self.assertEqual(self.rows(["EDUCATION", "NORTHWIND UNIVERSITY", row]), [])

    def test_the_readers_and_the_audit_share_one_stop_list(self):
        from cvstudio_cv_fidelity import _AUDIT_TRAILING_STOP_WORDS, _SECTION_STOP_HEADING_RE
        self.assertIn("REFEREES", reconcile._WORK_HISTORY_STOP_WORDS)
        for word in reconcile._WORK_HISTORY_STOP_WORDS + _AUDIT_TRAILING_STOP_WORDS:
            self.assertIn(word, _SECTION_STOP_HEADING_RE.pattern)

    def test_the_audit_and_the_reader_share_one_work_heading(self):
        from cvstudio_cv_fidelity import _EXPERIENCE_HEADING_RE
        self.assertIs(_EXPERIENCE_HEADING_RE, reconcile._WORK_HISTORY_HEADING_RE)


if __name__ == "__main__":
    unittest.main()
