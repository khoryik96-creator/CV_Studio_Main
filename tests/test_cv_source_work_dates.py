"""Date recovery changes fields only when a source job header is unambiguous."""
import copy
import time
import unittest

from cvstudio_cv_reconcile import _reconcile_work_experience_with_authoritative_table, _restore_work_dates_from_source_headers


def cv(company="Contoso Systems", title="Technical Specialist", date="Aug 2017 to May 2015"):
    return {"candidate": {"current_company": company, "current_position": title},
            "work_experiences": [{"company": company, "date_range": date,
                "roles": [{"title": title, "date_range": "", "bullets": ["Kept original duty."]}]}],
            "education": []}


class SourceWorkDateTests(unittest.TestCase):
    def reconcile(self, source, data=None):
        return _reconcile_work_experience_with_authoritative_table(copy.deepcopy(data or cv()), source)

    def test_title_above_employer_dates_restores_exact_year_without_rebuilding(self):
        data = cv()
        data["work_experiences"].append({"company": "Unlisted Co", "roles": [{"title": "Intern", "bullets": ["Kept internship."]}]})
        expected = copy.deepcopy(data)
        expected["work_experiences"][0]["date_range"] = "Aug 2011 to May 2015"
        self.assertEqual(self.reconcile("WORK EXPERIENCES\nTechnical Specialist\nContoso Systems | Aug 2011 - May 2015", data), expected)

    def test_long_exact_title_and_valid_but_wrong_date_are_supported(self):
        title = "Senior Infrastructure Engineer - Storage and Backup Platform Development and Operations for Regional Compute Services"
        data = cv(title=title, date="Jan 2020 to Present")
        expected = copy.deepcopy(data)
        expected["work_experiences"][0]["date_range"] = "Jan 2025 to Present"
        self.assertEqual(self.reconcile("WORK EXPERIENCE\n" + title + "\nContoso Systems | January 2025 - Present", data), expected)

    def test_missing_role_date_is_restored_without_guessing_company_span(self):
        data = cv(date="2011 to 2025")
        data["work_experiences"][0]["roles"].append({"title": "Engineer", "date_range": "2015 to 2025", "bullets": ["Kept later duty."]})
        expected = copy.deepcopy(data)
        expected["work_experiences"][0]["roles"][0]["date_range"] = "Aug 2011 to May 2015"
        self.assertEqual(self.reconcile("WORK EXPERIENCE\nTechnical Specialist\nContoso Systems | Aug 2011 - May 2015", data), expected)

    def test_uncertain_source_or_target_never_changes_dates(self):
        good = "Technical Specialist\nContoso Systems | Aug 2011 - May 2015"
        for source in (good, "EDUCATION\n" + good, "WORK EXPERIENCE\nEDUCATION\n" + good,
                       "WORK EXPERIENCE\nPROFESSIONAL REFERENCES\n" + good,
                       "WORK EXPERIENCE\nA W A R D S ____\n" + good,
                       "WORK EXPERIENCE\nDifferent Title\nContoso Systems | Aug 2011 - May 2015",
                       "WORK EXPERIENCE\nTechnical Specialist\nOther Systems | Aug 2011 - May 2015",
                       "WORK EXPERIENCE\nTechnical Specialist\nContoso Systems | Aug 2017 - May 2015",
                       "WORK EXPERIENCE\nTechnical Specialist\nContoso Systems | Aug 2018 - May 2015",
                       "WORK EXPERIENCE\nTechnical Specialist\nContoso Systems | 2011 - 2015 (project dates)",
                       "WORK EXPERIENCE\n" + good + "\n" + good,
                       "WORK EXPERIENCE\n" + good + "\nTechnical Specialist\nContoso Systems | 2012 - 2015"):
            with self.subTest(source=source):
                self.assertEqual(self.reconcile(source), cv())
        data = cv()
        data["work_experiences"].append(copy.deepcopy(data["work_experiences"][0]))
        self.assertEqual(self.reconcile("WORK EXPERIENCE\n" + good, data), data)

    def test_single_role_explicit_conflicting_dates_stay_unchanged(self):
        data = cv()
        data["work_experiences"][0]["roles"][0]["date_range"] = "2012 to 2014"
        self.assertEqual(self.reconcile("WORK EXPERIENCE\nTechnical Specialist\nContoso Systems | Aug 2011 - May 2015", data), data)

    def test_repeated_stints_in_other_supported_layouts_do_not_overwrite_dates(self):
        data = cv(title="Analyst", date="2020 to 2024")
        for header in (
            "Analyst | Contoso Systems | 2020 - 2024",
            "Contoso Systems | Analyst | 2020 - 2024",
            "2020 - 2024 | Contoso Systems | Analyst",
            "2020 - 2024 Contoso Systems Analyst",
            "Analyst\nContoso Systems | Singapore | 2020 - 2024",
        ):
            source = "WORK EXPERIENCE\nAnalyst\nContoso Systems | 2011 - 2015\n" + header
            with self.subTest(header=header):
                self.assertEqual(self.reconcile(source, data), data)
                self.assertEqual(_restore_work_dates_from_source_headers(copy.deepcopy(data), source), data)

    def test_another_layout_blocks_recovery_even_when_its_dates_are_identical(self):
        data = cv(title="Analyst", date="2020 to 2024")
        source = "WORK EXPERIENCE\nAnalyst\nContoso Systems | 2011 - 2015\nAnalyst | Contoso Systems | 2011 - 2015"
        self.assertEqual(self.reconcile(source, data), data)

    def test_house_style_titles_and_employers_cannot_hide_a_repeated_stint(self):
        for company, title in (("Contoso Systems", "SR Engineer"), ("Contoso Systems", "JR Engineer"),
                               ("Contoso Systems", "SR ENGINEER"), ("CONTOSO SYSTEMS SDN BHD", "Analyst"),
                               ("iFAST SDN BHD", "SR Engineer")):
            data = cv(company=company, title=title, date="2020 to 2024")
            source = f"WORK EXPERIENCE\n{title}\n{company} | 2011 - 2015\n{title} | {company} | 2020 - 2024"
            with self.subTest(company=company, title=title):
                self.assertEqual(self.reconcile(source, data), data)
                self.assertEqual(_restore_work_dates_from_source_headers(copy.deepcopy(data), source), data)

    def test_repeated_pairs_in_later_work_sections_do_not_supply_unique_dates(self):
        data = cv(title="Analyst", date="2020 to 2024")
        for boundary in ("EDUCATION\nFabrikam University", "SKILLS\nPython", "LANGUAGES\nEnglish",
                         "REFERENCES\nAvailable on request"):
            for header in ("Analyst | Contoso Systems | 2020 - 2024",
                           "2020 - 2024 Contoso Systems Analyst",
                           "Analyst\nContoso Systems | Singapore | 2020 - 2024"):
                source = "WORK EXPERIENCE\nAnalyst\nContoso Systems | 2011 - 2015\n" + boundary + "\nWORK EXPERIENCE\n" + header
                with self.subTest(boundary=boundary, header=header):
                    self.assertEqual(self.reconcile(source, data), data)
                    self.assertEqual(_restore_work_dates_from_source_headers(copy.deepcopy(data), source), data)

    def test_normalized_repeated_pair_is_found_in_a_third_work_section(self):
        data = cv(title="SR Engineer", date="2020 to 2024")
        source = "WORK EXPERIENCE\nSR Engineer\nContoso Systems | 2011 - 2015\nEDUCATION\nFabrikam University\nWORK EXPERIENCE\nAnalyst | Northwind Systems | 2016 - 2019\nSKILLS\nPython\nWORK EXPERIENCE\nSR Engineer | Contoso Systems | 2020 - 2024"
        self.assertEqual(self.reconcile(source, data), data)

    def test_unique_abbreviated_title_still_recovers_its_own_dates(self):
        data = cv(title="SR Engineer")
        expected = copy.deepcopy(data)
        expected["work_experiences"][0]["date_range"] = "Aug 2011 to May 2015"
        self.assertEqual(self.reconcile("WORK EXPERIENCE\nSR Engineer\nContoso Systems | Aug 2011 - May 2015", data), expected)

    def test_later_unrelated_work_and_non_work_headers_do_not_block_unique_recovery(self):
        data = cv(title="SR Engineer")
        expected = copy.deepcopy(data)
        expected["work_experiences"][0]["date_range"] = "Aug 2011 to May 2015"
        first = "WORK EXPERIENCE\nSR Engineer\nContoso Systems | Aug 2011 - May 2015\n"
        for later in ("EDUCATION\nFabrikam University\nWORK EXPERIENCE\nAnalyst | Northwind Systems | 2020 - 2024",
                      "EDUCATION\nFabrikam University\nWORK EXPERIENCE\nSenior Engineer | Contoso Systems | 2020 - 2024",
                      "REFERENCES\nSR Engineer | Contoso Systems | 2020 - 2024"):
            with self.subTest(later=later):
                self.assertEqual(self.reconcile(first + later, data), expected)

    def test_generated_abbreviated_repeats_across_sections_keep_every_field(self):
        for year in range(1980, 2020):
            data = cv(title="JR Engineer", date=f"{year + 10} to {year + 14}")
            source = f"WORK EXPERIENCE\nJR Engineer\nContoso Systems | {year} - {year + 4}\nEDUCATION\nFabrikam University\nWORK EXPERIENCE\nJR Engineer | Contoso Systems | {year + 10} - {year + 14}"
            with self.subTest(year=year):
                self.assertEqual(self.reconcile(source, data), data)

    def test_many_sections_stop_work_once_the_pair_is_ambiguous(self):
        data = cv(title="SR Engineer", date="2020 to 2024")
        source = "WORK EXPERIENCE\nSR Engineer\nContoso Systems | 2011 - 2015\nEDUCATION\nFabrikam University\nWORK EXPERIENCE\nSR Engineer | Contoso Systems | 2020 - 2024\n" + "EDUCATION\nFabrikam University\nWORK EXPERIENCE\nUndated job\n" * 20000
        started = time.perf_counter()
        self.assertEqual(_restore_work_dates_from_source_headers(copy.deepcopy(data), source), data)
        self.assertLess(time.perf_counter() - started, 3.0)

    def test_generated_mixed_layout_repeats_preserve_every_field(self):
        for year in range(1980, 2020):
            data = cv(company=f"Contoso Systems {year}", title="Analyst", date=f"{year + 10} to {year + 14}")
            source = f"WORK EXPERIENCE\nAnalyst\nContoso Systems {year} | {year} - {year + 4}\nAnalyst | Contoso Systems {year} | {year + 10} - {year + 14}"
            with self.subTest(year=year):
                self.assertEqual(self.reconcile(source, data), data)

    def test_generated_headers_keep_every_other_field_and_are_idempotent(self):
        for year in range(1980, 2025):
            data = cv(company=f"Contoso Systems {year}", date=f"Aug {year + 6} to May {year + 4}")
            source = f"WORK EXPERIENCE\nTechnical Specialist\nContoso Systems {year} | August {year} — May {year + 4}"
            expected = copy.deepcopy(data)
            expected["work_experiences"][0]["date_range"] = f"Aug {year} to May {year + 4}"
            with self.subTest(year=year):
                self.assertEqual(self.reconcile(source, data), expected)
                self.assertEqual(self.reconcile(source, expected), expected)

    def test_repeated_input_remains_bounded(self):
        source = "WORK EXPERIENCE\n" + "Technical Specialist\nContoso Systems | Aug 2011 - May 2015\n" * 20000
        started = time.perf_counter()
        self.assertEqual(_restore_work_dates_from_source_headers(cv(), source), cv())
        self.assertLess(time.perf_counter() - started, 3.0)
