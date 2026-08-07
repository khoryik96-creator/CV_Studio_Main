"""Characterization coverage for the extracted JobAdder salary-notice computation.

These functions were moved verbatim from the web shell into
cvstudio_ja_salary_notice.py; app.py re-exports the names. The tests pin
deterministic behaviour so the extraction (and future edits) stay
behaviour-preserving.
"""

import unittest
from datetime import date

import app


class JaSalaryNoticeCharacterizationTests(unittest.TestCase):
    def test_currency_option_for_code(self):
        self.assertEqual(app._ja_currency_option_for_code("myr"), "Malaysian Ringgit (MYR)")
        self.assertEqual(app._ja_currency_option_for_code(" sgd "), "Singapore Dollar (SGD)")
        self.assertIsNone(app._ja_currency_option_for_code("zzz"))

    def test_expected_means_same_as_current(self):
        self.assertTrue(app._ja_expected_means_same_as_current("Same as current"))
        self.assertTrue(app._ja_expected_means_same_as_current("no increment"))
        self.assertFalse(app._ja_expected_means_same_as_current("6500"))

    def test_expected_is_open(self):
        self.assertTrue(app._ja_expected_is_open("Negotiable"))
        self.assertTrue(app._ja_expected_is_open("open"))
        self.assertFalse(app._ja_expected_is_open("6500"))

    def test_valid_iso_date(self):
        self.assertEqual(app._ja_valid_iso_date(2024, 2, 29), "2024-02-29")  # leap year
        self.assertIsNone(app._ja_valid_iso_date(2023, 2, 29))  # not a leap year

    def test_add_months_iso_clamps_to_month_end(self):
        self.assertEqual(app._ja_add_months_iso(date(2024, 1, 31), 1), "2024-02-29")
        self.assertEqual(app._ja_add_months_iso(date(2023, 12, 15), 2), "2024-02-15")

    def test_existing_current_salary(self):
        cand = {"employment": {"current": {"salary": {"rate": 5000}}}}
        self.assertEqual(app._ja_existing_current_salary(cand), app._ja_round_currency(5000))
        self.assertIsNone(app._ja_existing_current_salary({}))

    def test_module_never_imports_app(self):
        import inspect

        import cvstudio_ja_salary_notice

        self.assertNotIn("import app", inspect.getsource(cvstudio_ja_salary_notice))


if __name__ == "__main__":
    unittest.main()
