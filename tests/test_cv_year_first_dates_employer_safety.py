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

    def test_an_already_month_first_range_comes_back_identical(self):
        for text in ("Jun 2015 - august  2017", "Apr 2019 - Mar 2022",
                     "June 2025 - current", "Sept 2024 to April 2025"):
            with self.subTest(text=text):
                self.assertEqual(
                    normalize._cv_pretranslate_year_first_month_names(text), text
                )

    def test_a_mixed_range_has_only_its_year_first_half_turned_round(self):
        self.assertEqual(
            normalize._cv_pretranslate_year_first_month_names("Jun 2015 - 2017 august"),
            "Jun 2015 - august 2017",
        )
        self.assertEqual(
            normalize._cv_pretranslate_year_first_month_names("2015 june - Aug 2017"),
            "june 2015 - Aug 2017",
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

    def test_only_a_line_that_is_entirely_a_date_is_touched(self):
        # The rewrite is anchored to the whole line on purpose. An earlier draft
        # rewrote "YYYY Month" anywhere it appeared and did real damage: it
        # reworded the candidate's own sentences, and interleaved the years and
        # months of a line carrying several dates.
        for text in (
            "figures for 2023 may be revised",
            "Since 2021 March, led the migration",
            "Won the 2024 March tender",
            "-Built batch pipelines in 2025 june using Airflow",
            "Revenue doubled between 2019 August and 2021 May",
            "Company: Acme Sdn Bhd | Industry Banking",
            "2025 june- current   Senior Data Engineer",
        ):
            with self.subTest(text=text):
                self.assertEqual(
                    normalize._cv_pretranslate_year_first_month_names(text), text
                )

    def test_a_line_of_several_dates_is_never_reordered(self):
        # Each of these scrambled under the first draft, because a year can close
        # one date while a month opens the next.
        for text in (
            "Jan 2018 Dec 2019 Jan 2020 Dec 2021",
            "Jun 2020 Jun 2021 Jun 2022",
            "Jun 2015   august  2017   Mar 2013   Jun 2015",
            "2015 - 2018    Jun 2019 - Present",
            "2003-2006 May 2007 - Dec 2009",
            "Jun\u20092020 Jun\u20092021",
            "Jun.2020 Jun.2021",
            "June, 2020 June, 2021",
        ):
            with self.subTest(text=text):
                self.assertEqual(
                    normalize._cv_pretranslate_year_first_month_names(text), text
                )

    def test_a_wide_unicode_space_does_not_hide_a_date(self):
        # Word and PDF use these between a month and its year, and the sibling
        # helpers already treat them as ordinary date separators.
        for space in ("\u00a0", "\u1680", "\u2000", "\u2007", "\u2009", "\u202f",
                      "\u205f", "\u3000"):
            with self.subTest(space=repr(space)):
                self.assertEqual(
                    normalize._cv_pretranslate_year_first_month_names("2025" + space + "June"),
                    "June 2025",
                )

    def test_every_line_of_a_document_is_considered_independently(self):
        document = "\n".join([
            "Experience",
            "company: Acme Sdn Bhd | Industry Banking",
            "2025 june- current",
            "Senior Data Engineer",
            "-Delivered the 2024 March release on time",
            "2022 march - 2024 august",
        ])
        out = normalize._cv_pretranslate_year_first_month_names(document)
        lines = out.splitlines()
        self.assertEqual(lines[2], "june 2025- current")
        self.assertEqual(lines[5], "march 2022 - august 2024")
        # The bullet keeps the candidate's own wording.
        self.assertEqual(lines[4], "-Delivered the 2024 March release on time")
        # Line count and every other line are byte-identical.
        self.assertEqual(len(lines), len(document.splitlines()))

    def test_a_date_cell_in_a_joined_table_row_is_turned_round(self):
        # The upload route joins a table row's cells with " | ", so a date cell
        # never sits alone on its line. The line-anchored version of this pass
        # changed nothing on the CV it was written for; its tests passed because
        # they fed it a different extractor's output.
        f = normalize._cv_pretranslate_year_first_month_names
        self.assertEqual(f("2025 june- current | Senior Data Engineer"),
                         "june 2025- current | Senior Data Engineer")
        self.assertEqual(f("2024 sept -2025 April | Data Engineer"),
                         "sept 2024 -April 2025 | Data Engineer")
        self.assertEqual(f("2022 march - 2024 august | Senior ETL Data Engineer"),
                         "march 2022 - august 2024 | Senior ETL Data Engineer")
        # The date may be any cell, and the separator spacing is preserved.
        self.assertEqual(f("Senior Data Engineer | 2025 june - current"),
                         "Senior Data Engineer | june 2025 - current")
        self.assertEqual(f("2025 june- current | Senior Data Engineer "),
                         "june 2025- current | Senior Data Engineer ")

    def test_only_a_cell_that_is_entirely_a_date_is_touched(self):
        f = normalize._cv_pretranslate_year_first_month_names
        for text in (
            "Apr 2019 - Mar 2022 | Assistant manager data analyst",
            "company: Acme Sdn Bhd(Brand Sdn Bhd) | Industry Banking",
            "2003-2006\tNORTHWIND UNIVERSITY | Bachelor's Degree | Australia",
            "figures for 2023 may be revised | see appendix",
            "Won the 2024 March tender | Led a team of 5",
            "Jan 2018 Dec 2019 | Jan 2020 Dec 2021",
            "2015 - 2018 | Jun 2019 - Present",
            "Skills | Java | Python",
            "a || b", "|", " | ",
        ):
            with self.subTest(text=text):
                self.assertEqual(f(text), text)

    def test_line_endings_survive(self):
        for ending in ("\n", "\r\n"):
            with self.subTest(ending=repr(ending)):
                text = "2025 june- current" + ending + "next line"
                out = normalize._cv_pretranslate_year_first_month_names(text)
                self.assertEqual(out, "june 2025- current" + ending + "next line")

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
        "company: Orbix IT outsourcing sdn bhd(lumen bank sdn bhd) | Industry Banking",
        "June 2025- current",
        "Senior Data Engineer",
        "-Built batch processing pipelines.",
        "Experience",
        "Company: Kelsoft Sdn Bhd | industry Gaming",
        "Sept 2024 -April 2025",
        "Data Engineer",
        "-Designed real-time streaming pipelines.",
        "Company:QRS Digital Sdn Bhd | Industry:Finance",
        "Apr 2019 - Mar 2022",
        "Assistant manager data analyst",
        "-Responsible in building data ETL.",
        "Education",
        "2003-2006 LATROBE UNIVERSITY",
    ])

    def test_labelled_employers_are_seen_without_a_work_history_table(self):
        found = fidelity._source_employers(self.SOURCE, None)
        self.assertEqual(len(found), 3)
        self.assertIn("Kelsoft Sdn Bhd", found)
        self.assertIn("QRS Digital Sdn Bhd", found)

    def test_the_industry_cell_is_not_read_as_part_of_the_name(self):
        # The extractor joins a table row's cells with " | ".
        self.assertEqual(
            fidelity._source_labelled_companies("Company:QRS Digital Sdn Bhd | Industry:Finance"),
            ["QRS Digital Sdn Bhd"],
        )
        self.assertEqual(
            fidelity._source_labelled_companies("company: Acme Sdn Bhd Industry: Retail"),
            ["Acme Sdn Bhd"],
        )

    def test_a_missing_employer_is_reported_instead_of_shipped(self):
        parsed = {"work_experiences": [
            {"date_range": "Apr 2019 to Mar 2022", "company": "QRS Digital Sdn Bhd",
             "roles": [{"title": "Assistant Manager Data Analyst", "bullets": ["x"]}]},
        ]}
        report = fidelity.evaluate_cv_fidelity(parsed, self.SOURCE)
        self.assertFalse(report["ok"])
        missing = report["employers"]["missing"]
        self.assertIn("Kelsoft Sdn Bhd", missing)
        self.assertTrue(any("Orbix" in name for name in missing))
        warning = fidelity.summarize_fidelity_warning(report)
        self.assertIn("missing from the parsed result", warning)

    def test_a_complete_parse_raises_nothing(self):
        parsed = {"work_experiences": [
            {"date_range": "Jun 2025 to Present",
             "company": "Orbix IT outsourcing sdn bhd(lumen bank sdn bhd)",
             "roles": [{"title": "Senior Data Engineer", "bullets": ["x"]}]},
            {"date_range": "Sep 2024 to Apr 2025", "company": "Kelsoft Sdn Bhd",
             "roles": [{"title": "Data Engineer", "bullets": ["x"]}]},
            {"date_range": "Apr 2019 to Mar 2022", "company": "QRS Digital Sdn Bhd",
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
        # One employer, and the entry says which one by its dates -- the flattened
        # rows carry exp_date/role_date, so reading "date_range" off them located
        # nothing and always fell through to the separator itself.
        self.assertEqual(report["employers"]["unnamed"], ["Apr 2019 to Mar 2022"])
        self.assertIn("came back with no name", fidelity.summarize_fidelity_warning(report))
        self.assertIn("Apr 2019 to Mar 2022", fidelity.summarize_fidelity_warning(report))

    def test_one_employer_with_several_roles_counts_once(self):
        # Counted per flattened role, one lost company field read as "3 work
        # entries came back with no employer name".
        parsed = {"work_experiences": [
            {"date_range": "Apr 2019 to Mar 2022", "company": "|", "roles": [
                {"title": "Analyst"}, {"title": "Senior Analyst"}, {"title": "Manager"},
            ]},
        ]}
        report = fidelity.evaluate_cv_fidelity(parsed, self.SOURCE)
        self.assertEqual(len(report["employers"]["unnamed"]), 1)
        self.assertIn("1 employer came back", fidelity.summarize_fidelity_warning(report))

    def test_a_referees_block_is_not_scanned_for_employers(self):
        # A referees block names employers and job titles. Expecting the referee's
        # own company warned on a flawless parse.
        source = "\n".join([
            "WORK EXPERIENCE",
            "Company: Acme Sdn Bhd | Industry: Banking",
            "Jun 2020 - Present",
            "REFEREES",
            "Company: Other Firm Sdn Bhd",
            "Name: A Referee",
        ])
        parsed = {"work_experiences": [
            {"date_range": "Jun 2020 to Present", "company": "Acme Sdn Bhd",
             "roles": [{"title": "Engineer", "bullets": ["x"]}]},
        ]}
        report = fidelity.evaluate_cv_fidelity(parsed, source)
        self.assertEqual(report["employers"]["missing"], [])
        self.assertIsNone(fidelity.summarize_fidelity_warning(report))

    def test_a_longer_labelled_name_matches_the_employer_the_parse_kept(self):
        # The label often carries a parenthesised brand or a branch location that
        # the parse legitimately drops; token overlap alone scored these as missing.
        cases = [
            ("company: Orbix IT outsourcing sdn bhd(lumen bank sdn bhd)",
             ["Orbix IT Outsourcing Sdn Bhd", "Lumen Bank Sdn Bhd",
              "Orbix IT outsourcing sdn bhd(lumen bank sdn bhd)"]),
            ("Company: Acme Engineering Sdn Bhd, Shah Alam, Selangor",
             ["Acme Engineering Sdn Bhd"]),
            ("Company: Acme Sdn Bhd - Klang Valley", ["Acme Sdn Bhd"]),
        ]
        for label, kept_names in cases:
            source = "Experience\n" + label + "\nJun 2020 - Present\nEngineer\n"
            for kept in kept_names:
                with self.subTest(label=label, kept=kept):
                    parsed = {"work_experiences": [
                        {"date_range": "Jun 2020 to Present", "company": kept,
                         "roles": [{"title": "Engineer", "bullets": ["x"]}]},
                    ]}
                    report = fidelity.evaluate_cv_fidelity(parsed, source)
                    self.assertEqual(report["employers"]["missing"], [])

    def test_a_hyphenated_prose_word_is_not_a_company_label(self):
        # "Company-wide rollout of ..." produced the employer candidate
        # "wide rollout of ..." and showed it to the user as a missing employer.
        for line in (
            "Company-wide rollout of the new payroll platform for 3000 staff",
            "Company-paid training in cloud architecture",
            "Company - wide restructuring programme",
        ):
            with self.subTest(line=line):
                self.assertEqual(fidelity._source_labelled_companies(line), [])

    def test_the_label_is_found_in_a_pipe_row_and_as_company_name(self):
        self.assertEqual(
            fidelity._source_labelled_companies(
                "Position: Engineer | Company: Acme Sdn Bhd | Duration: 2020-2022"
            ),
            ["Acme Sdn Bhd"],
        )
        self.assertEqual(
            fidelity._source_labelled_companies("Company Name: Acme Sdn Bhd"),
            ["Acme Sdn Bhd"],
        )

    def test_a_real_name_is_never_called_a_separator(self):
        for company in ("QRS Digital Sdn Bhd", "ZETA-X Sdn Bhd", "3M", "AT&T", "東京商事"):
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
