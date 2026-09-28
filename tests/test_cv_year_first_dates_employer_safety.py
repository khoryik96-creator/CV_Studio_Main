"""Coverage for two source-anchored protections on the CV parse.

A table-based CV that wrote its three most recent roles year-first ("2025 june -
current") and its older ones month-first came back missing exactly the year-first
three, with two education rows rendered as jobs and every employer name replaced
by the cell separator. Extraction was perfect and the Word generator was correct;
the loss was entirely in what the model returned.

These tests pin the two protections that follow from that. First, the year-first
form written with a month NAME is normalised before a provider sees it, the same
way the numeric ISO form already was. Second, the fidelity audit can see employers
in a CV that labels them "Company:" rather than laying them out in a
Dates/Organization/Role table, so a shortfall is reported instead of shipping a CV
without the candidate's current job.
"""

import os
from pathlib import Path
import tempfile
import unittest

from owner_build_tools.build_protected import write_test_receipt


ROOT = Path(__file__).resolve().parents[1]
_MODULE_TEMPORARY = tempfile.TemporaryDirectory(prefix="cvstudio-cv-yearfirst-")
_ORIGINAL_DATABASE_OVERRIDE = os.environ.get("CVSTUDIO_DB_PATH")
os.environ["CVSTUDIO_DB_PATH"] = str(
    Path(_MODULE_TEMPORARY.name) / "state" / "cv_studio.sqlite3"
)
write_test_receipt(ROOT)
try:
    import cvstudio_cv_fidelity as fidelity
    import cvstudio_cv_normalize as normalize
finally:
    if _ORIGINAL_DATABASE_OVERRIDE is None:
        os.environ.pop("CVSTUDIO_DB_PATH", None)
    else:
        os.environ["CVSTUDIO_DB_PATH"] = _ORIGINAL_DATABASE_OVERRIDE


# The three date cells from the CV that lost its three most recent employers,
# verbatim, beside the six month-first cells from the same CV that survived.
YEAR_FIRST_SOURCE = "2025 june- current"
YEAR_FIRST_RANGE = "2024 sept -2025 April"
YEAR_FIRST_BOTH_ENDS = "2022 march - 2024 august"
MONTH_FIRST_SURVIVORS = (
    "Apr 2019 - Mar 2022",
    "Sep 2017 - Apr 2019",
    "Jun 2015 - august  2017",
    "Mar 2013 - Jun 2015",
    "Jul 2007 - Feb 2013",
    "April 2006 - May 2007",
)


class YearFirstMonthNameTests(unittest.TestCase):
    def test_a_year_before_a_month_name_is_swapped(self):
        self.assertEqual(
            normalize._cv_pretranslate_year_first_month_names(YEAR_FIRST_SOURCE),
            "june 2025- current",
        )
        self.assertEqual(
            normalize._cv_pretranslate_year_first_month_names(YEAR_FIRST_BOTH_ENDS),
            "march 2022 - august 2024",
        )

    def test_both_ends_of_a_mixed_range_are_swapped(self):
        out = normalize._cv_pretranslate_year_first_month_names(YEAR_FIRST_RANGE)
        self.assertIn("sept 2024", out)
        self.assertIn("April 2025", out)
        self.assertNotIn("2024 sept", out)

    def test_the_source_spelling_of_the_month_is_kept(self):
        # Rewriting "june" to "Jun" would edit the CV rather than reorder it.
        for text, expected in (
            ("2025 june", "june 2025"),
            ("2025 JUNE", "JUNE 2025"),
            ("2025 Jun", "Jun 2025"),
            ("2024 sept", "sept 2024"),
            ("2024 September", "September 2024"),
        ):
            with self.subTest(text=text):
                self.assertEqual(normalize._cv_pretranslate_year_first_month_names(text), expected)

    def test_month_first_dates_are_left_exactly_as_they_are(self):
        for text in MONTH_FIRST_SURVIVORS:
            with self.subTest(text=text):
                self.assertEqual(normalize._cv_pretranslate_year_first_month_names(text), text)

    def test_the_numeric_iso_form_still_works(self):
        # Unchanged, and still the separate helper it always was.
        self.assertEqual(normalize._cv_pretranslate_iso_dates("2019-12"), "Dec 2019")
        self.assertEqual(normalize._cv_pretranslate_iso_dates("2020-06-15"), "Jun 2020")
        # The existing guard: a day followed by a month name is not an ISO date.
        self.assertEqual(
            normalize._cv_pretranslate_iso_dates("Apr 2022-11 Jul 2026"),
            "Apr 2022-11 Jul 2026",
        )

    def test_a_year_closing_a_month_first_date_is_left_alone(self):
        # "Jun 2020 Jun 2021" is two dates: the 2020 closes the first and the Jun
        # after it opens the second. Reordering produced "Jun Jun 2020 2021".
        for text in ("Jun 2020 Jun 2021", "May 2019 May 2020", "Sept 2024 April 2025"):
            with self.subTest(text=text):
                self.assertEqual(
                    normalize._cv_pretranslate_year_first_month_names(text), text
                )

    def test_the_field_level_date_normaliser_is_untouched(self):
        # It is mirrored in two JavaScript copies; a rule added on one side only
        # would break their shared contract.
        self.assertEqual(
            normalize._normalize_cv_date_range("Jun 2020 Jun 2021"), "Jun 2020 Jun 2021"
        )
        self.assertEqual(
            normalize._normalize_cv_date_range("2020-06"), "Jun 2020"
        )

    def test_a_year_only_range_is_untouched(self):
        # Education rows in the same CV. Swapping anything here would corrupt them.
        for text in ("2003-2006", "2002-2002", "2000-2001", "2003 - 2006"):
            with self.subTest(text=text):
                self.assertEqual(normalize._cv_pretranslate_year_first_month_names(text), text)

    def test_things_that_only_look_like_dates_are_untouched(self):
        for text in (
            "Salary:RM14500",
            "0164127086",
            "CGPA 2.0 / 4.0",
            "PHP 7.1 laravel 6",
            "MSSQL 2014/Visual Studio",
            "Windows Server 2003",
            "MSSQL 2000, 2005, 2008R, 2012",
            # A year glued to a prefix is not a date token.
            "FY2024 Sept quarter",
            "ISO27001 May audit",
        ):
            with self.subTest(text=text):
                self.assertEqual(normalize._cv_pretranslate_year_first_month_names(text), text)

    def test_a_line_break_between_year_and_month_is_not_crossed(self):
        # A year ending one line and a month opening the next are two dates.
        self.assertEqual(
            normalize._cv_pretranslate_year_first_month_names("Graduated 2000\nMay joined Acme"),
            "Graduated 2000\nMay joined Acme",
        )

    def test_the_helper_is_safe_on_junk(self):
        for value in (None, "", 0, [], {}):
            with self.subTest(value=value):
                normalize._cv_pretranslate_year_first_month_names(value)


class LabelledCompanyFidelityTests(unittest.TestCase):
    """A CV that labels its employers instead of tabulating them."""

    SOURCE = "\n".join([
        "Personal Info",
        "Name: A Candidate",
        "Experience",
        "company: Avows IT outsourcing sdn bhd(boost bank sdn bhd) | Industry Banking",
        "June 2025- current",
        "Senior Data Engineer",
        "-Built batch processing pipelines.",
        "Experience",
        "Company: Snssoft Sdn Bhd | industry Gaming",
        "Sept 2024 -April 2025",
        "Data Engineer",
        "-Designed real-time streaming pipelines.",
        "Company:TNG Digital Sdn Bhd | Industry:Finance",
        "Apr 2019 - Mar 2022",
        "Assistant manager data analyst",
        "-Responsible in building data ETL.",
        "Education",
        "2003-2006 LATROBE UNIVERSITY",
    ])

    def test_labelled_employers_are_seen_without_a_work_history_table(self):
        found = fidelity._source_employers(self.SOURCE, None)
        self.assertEqual(len(found), 3)
        self.assertIn("Snssoft Sdn Bhd", found)
        self.assertIn("TNG Digital Sdn Bhd", found)

    def test_the_industry_cell_is_not_read_as_part_of_the_name(self):
        # The extractor joins a table row's cells with " | ".
        self.assertEqual(
            fidelity._source_labelled_companies("Company:TNG Digital Sdn Bhd | Industry:Finance"),
            ["TNG Digital Sdn Bhd"],
        )
        self.assertEqual(
            fidelity._source_labelled_companies("company: Acme Sdn Bhd Industry: Retail"),
            ["Acme Sdn Bhd"],
        )

    def test_a_missing_employer_is_reported_instead_of_shipped(self):
        parsed = {"work_experiences": [
            {"date_range": "Apr 2019 to Mar 2022", "company": "TNG Digital Sdn Bhd",
             "roles": [{"title": "Assistant Manager Data Analyst", "bullets": ["x"]}]},
        ]}
        report = fidelity.evaluate_cv_fidelity(parsed, self.SOURCE)
        self.assertFalse(report["ok"])
        missing = report["employers"]["missing"]
        self.assertIn("Snssoft Sdn Bhd", missing)
        self.assertTrue(any("Avows" in name for name in missing))
        warning = fidelity.summarize_fidelity_warning(report)
        self.assertIn("missing from the parsed result", warning)

    def test_a_complete_parse_raises_nothing(self):
        parsed = {"work_experiences": [
            {"date_range": "Jun 2025 to Present",
             "company": "Avows IT outsourcing sdn bhd(boost bank sdn bhd)",
             "roles": [{"title": "Senior Data Engineer", "bullets": ["x"]}]},
            {"date_range": "Sep 2024 to Apr 2025", "company": "Snssoft Sdn Bhd",
             "roles": [{"title": "Data Engineer", "bullets": ["x"]}]},
            {"date_range": "Apr 2019 to Mar 2022", "company": "TNG Digital Sdn Bhd",
             "roles": [{"title": "Assistant Manager Data Analyst", "bullets": ["x"]}]},
        ]}
        report = fidelity.evaluate_cv_fidelity(parsed, self.SOURCE)
        self.assertEqual(report["employers"]["missing"], [])
        self.assertEqual(report["employers"]["unnamed"], [])
        self.assertIsNone(fidelity.summarize_fidelity_warning(report))

    def test_a_company_that_is_only_a_separator_is_named(self):
        # The finished CV shows an empty employer, which reads as a layout fault
        # rather than as the dropped field it is.
        parsed = {"work_experiences": [
            {"date_range": "Apr 2019 to Mar 2022", "company": "|",
             "roles": [{"title": "Assistant Manager Data Analyst", "bullets": ["x"]}]},
        ]}
        report = fidelity.evaluate_cv_fidelity(parsed, self.SOURCE)
        self.assertFalse(report["ok"])
        self.assertEqual(len(report["employers"]["unnamed"]), 1)
        self.assertIn("no employer name", fidelity.summarize_fidelity_warning(report))

    def test_a_real_name_is_never_called_a_separator(self):
        for company in ("TNG Digital Sdn Bhd", "RISK-X Sdn Bhd", "3M", "AT&T", "東京商事"):
            with self.subTest(company=company):
                parsed = {"work_experiences": [
                    {"date_range": "Apr 2019 to Mar 2022", "company": company,
                     "roles": [{"title": "Engineer", "bullets": ["x"]}]},
                ]}
                report = fidelity.evaluate_cv_fidelity(parsed, self.SOURCE)
                self.assertEqual(report["employers"]["unnamed"], [])

    def test_a_company_label_outside_the_work_history_makes_no_claim(self):
        # A referees block or cover note can also say "Company:". Expecting an
        # employer from there would warn on a perfectly good parse.
        source = "Referees\nCompany: Some Other Firm\nName: A Referee"
        self.assertEqual(fidelity._source_employers(source, None), [])

    def test_an_empty_or_absurd_label_is_ignored(self):
        self.assertEqual(fidelity._source_labelled_companies("Company:"), [])
        self.assertEqual(fidelity._source_labelled_companies("Company:   "), [])
        self.assertEqual(fidelity._source_labelled_companies("Company: |"), [])
        self.assertEqual(fidelity._source_labelled_companies("Company: " + "x" * 200), [])

    def test_the_audit_is_safe_on_junk(self):
        for parsed in (None, {}, {"work_experiences": None}, {"work_experiences": [None]}):
            with self.subTest(parsed=parsed):
                fidelity.evaluate_cv_fidelity(parsed, self.SOURCE)
        for text in (None, "", 0):
            with self.subTest(text=text):
                fidelity.evaluate_cv_fidelity({"work_experiences": []}, text)


if __name__ == "__main__":
    unittest.main()
