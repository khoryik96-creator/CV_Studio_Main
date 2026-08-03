"""Characterization tests for the Lead Finder location/company-matching helpers.

Locks the behaviour of the stateless helpers extracted into
``cvstudio_lead_match`` (Phase 7B-6d). The company-name normaliser and matcher
have clear, stable contracts and are pinned directly; the region/location
helpers take internal argument shapes exercised by the wider Lead Finder
suite, so here they are covered as import/callable smoke plus module hygiene.
"""

import unittest

import cvstudio_lead_match as lm


class CompanyNameTests(unittest.TestCase):
    def test_norm_strips_legal_suffixes_and_lowercases(self):
        self.assertEqual(lm._lead_norm_company_name("Bolttech Sdn Bhd"), "bolttech")
        self.assertEqual(lm._lead_norm_company_name("  Acme, Inc.  "), "acme")

    def test_norm_empty(self):
        self.assertEqual(lm._lead_norm_company_name(""), "")

    def test_names_match_ignores_suffix_and_case(self):
        self.assertTrue(lm._lead_company_names_match("Bolttech", "BOLTTECH Pte Ltd"))

    def test_names_do_not_match_different_companies(self):
        self.assertFalse(lm._lead_company_names_match("Bolttech", "Google Asia"))


class SmokeTests(unittest.TestCase):
    def test_expected_symbols_present_and_callable(self):
        for name in [
            "_lead_region_aliases", "_lead_has_apac", "_lead_regions_allow_apac_remote",
            "_lead_blob_has_alias", "_lead_text_blob", "_lead_location_allowed",
            "_lead_norm_company_name", "_lead_company_names_match",
            "_lead_company_is_actually_role_text", "_lead_location_instruction",
            "_lead_company_matches_title_angles",
        ]:
            self.assertTrue(callable(getattr(lm, name)), name)

    def test_location_allowed_empty_filter_allows(self):
        # No region filter => any location is allowed.
        self.assertTrue(lm._lead_location_allowed("Anywhere", []))


class ModuleHygieneTests(unittest.TestCase):
    def test_module_does_not_import_app(self):
        self.assertNotIn("app", getattr(lm, "__dict__", {}))


if __name__ == "__main__":
    unittest.main()
