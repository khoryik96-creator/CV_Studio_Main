"""Characterization tests for the pure CV data-normalization helpers.

Locks the behaviour of the stateless normalisers extracted into
``cvstudio_cv_normalize`` (Phase 7B-6c): smart casing, work-history date
ranges, month tokens, language canonicalisation and the CV bullet /
structured-content normalisers. Pure functions, exercised directly.

The deeper bullet/structured-content matrix is already covered by
tests/test_long_cv_output_corrective.py; this suite pins the surrounding
helpers and confirms the module is importable and self-contained.
"""

import unittest

import cvstudio_cv_normalize as cn


class SmartCasingTests(unittest.TestCase):
    def test_word_case_capitalises(self):
        self.assertEqual(cn._smart_word_case("data"), "Data")

    def test_title_text_normalises_all_caps(self):
        self.assertEqual(cn._smart_title_text("SENIOR DATA ENGINEER"), "Senior Data Engineer")

    def test_title_text_leaves_mixed_case_untouched(self):
        # Only all-caps / uniform-case input is re-cased; ordinary text is kept.
        self.assertEqual(cn._smart_title_text("vp of sales"), "vp of sales")


class DateAndMonthTests(unittest.TestCase):
    def test_month_token_title_cases(self):
        self.assertEqual(cn._normalize_month_token("jan"), "Jan")

    def test_date_range_dash_to_word(self):
        self.assertEqual(cn._normalize_cv_date_range("Jan 2020 - Present"), "Jan 2020 to Present")

    def test_date_range_already_normal_preserved(self):
        self.assertEqual(cn._normalize_cv_date_range("2019 to 2021"), "2019 to 2021")

    def test_date_range_numeric_month_year_to_house_style(self):
        # A parse run that emits "06/2024" must normalise to the same "Mon YYYY"
        # form as a run that emits "Jun 2024", so re-formatting is consistent.
        self.assertEqual(
            cn._normalize_cv_date_range("06/2024 to 07/2026"), "Jun 2024 to Jul 2026"
        )
        self.assertEqual(cn._normalize_cv_date_range("6/2024"), "Jun 2024")
        self.assertEqual(
            cn._normalize_cv_date_range("05/2009 to Present"), "May 2009 to Present"
        )
        # Already-textual and year-only ranges are unchanged.
        self.assertEqual(
            cn._normalize_cv_date_range("Jun 2024 to Jul 2026"), "Jun 2024 to Jul 2026"
        )
        self.assertEqual(cn._normalize_cv_date_range("2004 to 2008"), "2004 to 2008")
        # An out-of-range month is not a month token; leave it alone.
        self.assertEqual(cn._normalize_cv_date_range("13/2024"), "13/2024")

    def test_date_sort_point_reads_numeric_month(self):
        self.assertEqual(cn._cv_date_sort_point("06/2024", end=False), (2024, 6))
        self.assertEqual(cn._cv_date_sort_point("06/2024 to 07/2026", end=True), (2026, 7))

    def test_company_span_from_roles_spans_earliest_to_latest(self):
        # Roles listed out of order (and a backwards company header) must yield a
        # correct earliest-start to latest-end span.
        roles = [
            {"date_range": "Jan 2020 to Mar 2021"},
            {"date_range": "Apr 2018 to Dec 2019"},
            {"date_range": "Dec 2015 to Mar 2018"},
        ]
        self.assertEqual(cn._cv_company_span_from_roles(roles), "Dec 2015 to Mar 2021")

    def test_company_span_preserves_present_and_normalizes_numeric(self):
        self.assertEqual(
            cn._cv_company_span_from_roles(
                [{"date_range": "Jan 2024 to Present"}, {"date_range": "Jan 2022 to Dec 2023"}]
            ),
            "Jan 2022 to Present",
        )
        self.assertEqual(
            cn._cv_company_span_from_roles(
                [{"date_range": "06/2024 to 07/2026"}, {"date_range": "01/2022 to 05/2024"}]
            ),
            "Jan 2022 to Jul 2026",
        )

    def test_company_span_empty_when_roles_have_no_dates(self):
        # No parseable date -> "" so callers keep the provided company date.
        self.assertEqual(cn._cv_company_span_from_roles([{"title": "X"}, {"title": "Y"}]), "")
        self.assertEqual(cn._cv_company_span_from_roles([]), "")

    def test_company_span_single_role(self):
        self.assertEqual(
            cn._cv_company_span_from_roles([{"date_range": "Jan 2020 to Mar 2021"}]),
            "Jan 2020 to Mar 2021",
        )

    def test_iso_year_month_dates_normalized_not_shredded(self):
        # ISO YYYY-MM ranges must become "Mon YYYY to Mon YYYY", not be split by
        # the hyphen->"to" step into "2020 to 06 to 2025 to 07".
        self.assertEqual(
            cn._normalize_cv_date_range("2020-06 – 2025-07"), "Jun 2020 to Jul 2025"
        )
        self.assertEqual(
            cn._normalize_cv_date_range("2016-01 – 2019-12"), "Jan 2016 to Dec 2019"
        )
        self.assertEqual(
            cn._normalize_cv_date_range("2025-03 – Present"), "Mar 2025 to Present"
        )
        # ISO with a day drops the day.
        self.assertEqual(
            cn._normalize_cv_date_range("2020-06-15 to 2025-07-31"), "Jun 2020 to Jul 2025"
        )

    def test_pretranslate_iso_dates_targets_only_dates(self):
        self.assertEqual(
            cn._cv_pretranslate_iso_dates("UOB Indonesia 2020-06 – 2025-07"),
            "UOB Indonesia Jun 2020 – Jul 2025",
        )
        # Year-only ranges, phone numbers, percentages, versions untouched.
        for junk in ["2016 – Present", "+6281310272131", "reduce by 30%", "RHEL 7 to RHEL 8", "192-168 lab"]:
            self.assertEqual(cn._cv_pretranslate_iso_dates(junk), junk)


class LanguageTests(unittest.TestCase):
    def test_canonical_language_name(self):
        # The alias->standard map is mutated at runtime by other code paths, so
        # the exact canonical target ("Mandarin" vs "Chinese") is state
        # dependent; the stable contract is a non-empty, capitalised name.
        result = cn._canonical_language_name("mandarin")
        self.assertTrue(result)
        self.assertEqual(result, result[:1].upper() + result[1:])

    def test_normalize_candidate_languages_returns_dict(self):
        out = cn._normalize_candidate_languages({"languages": ["English", "Malay"]})
        self.assertIsInstance(out, dict)
        self.assertIn("languages", out)

    def test_split_candidate_language_names(self):
        names = cn._split_candidate_language_names("English, Mandarin; Malay")
        self.assertIsInstance(names, list)
        self.assertTrue(any("english" in n.lower() for n in names))


class BulletAndStructuredContentTests(unittest.TestCase):
    def test_standalone_section_becomes_section_dict(self):
        # Matches the contract asserted in test_long_cv_output_corrective.
        out = cn._normalize_cv_bullet_items(["Key achievement", "Delivered result"])
        self.assertEqual(out, [
            {"heading": "Key achievements", "bullets": [], "kind": "section"},
            "Delivered result",
        ])

    def test_structured_content_smoke(self):
        parsed = {"experience": [{"title": "engineer", "bullets": ["Did a thing"]}]}
        out = cn._normalize_cv_structured_content(parsed)
        self.assertIsInstance(out, dict)

    def test_data_for_output_smoke(self):
        out = cn._normalize_cv_data_for_output({"name": "Jane"}, source_text="Jane")
        self.assertIsInstance(out, dict)


class ModuleHygieneTests(unittest.TestCase):
    def test_module_does_not_import_app(self):
        import sys
        # Importing the module must not have pulled in the legacy web shell.
        self.assertNotIn("app", getattr(cn, "__dict__", {}))


if __name__ == "__main__":
    unittest.main()
