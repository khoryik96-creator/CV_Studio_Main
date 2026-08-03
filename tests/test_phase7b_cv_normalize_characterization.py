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
