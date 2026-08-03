"""Characterization tests for the Spider boolean/keyword matching helpers.

Locks the behaviour of the stateless candidate-matching logic extracted into
``cvstudio_spider_boolean`` (Phase 7B-6e): boolean rule tokenisation and
positive/negative term extraction have clear contracts and are pinned
directly; the fuller expression/coverage matchers are covered as
import/callable smoke plus module hygiene.
"""

import unittest

import cvstudio_spider_boolean as sb


class TermExtractionTests(unittest.TestCase):
    def test_positive_terms(self):
        self.assertEqual(sb._spider_boolean_positive_terms("python AND java NOT php"), ["python", "java"])

    def test_not_terms(self):
        self.assertEqual(sb._spider_boolean_not_terms("python NOT php NOT ruby"), ["php", "ruby"])

    def test_positive_terms_empty(self):
        self.assertEqual(sb._spider_boolean_positive_terms(""), [])


class TokeniserTests(unittest.TestCase):
    def test_tokens_types(self):
        toks = sb._spider_boolean_tokens("python AND (java OR go)")
        kinds = [t[0] for t in toks]
        self.assertIn("TERM", kinds)
        self.assertIn("AND", kinds)
        self.assertIn("OR", kinds)
        self.assertIn("LP", kinds)
        self.assertIn("RP", kinds)
        # First token is the first term.
        self.assertEqual(toks[0], ("TERM", "python"))

    def test_expression_match_returns_tuple(self):
        result = sb._spider_boolean_expression_match("python AND java", "I know python and java")
        self.assertIsInstance(result, tuple)
        self.assertTrue(result[0])


class SmokeTests(unittest.TestCase):
    def test_symbols_present_and_callable(self):
        for name in [
            "_spider_terms", "_spider_boolean_not_terms", "_spider_boolean_positive_terms",
            "_spider_terms_for_fit", "_spider_term_matches", "_spider_normalized_record_label",
            "_spider_hit_terms", "_spider_boolean_tokens", "_spider_boolean_terms",
            "_spider_boolean_expression_match", "_spider_discovery_keyword_match",
            "_spider_term_coverage", "_spider_clean_doc_text_for_preview",
            "_spider_boolean_fallback_atoms", "_spider_boolean_fallback_terms",
        ]:
            self.assertTrue(callable(getattr(sb, name)), name)

    def test_clean_doc_text_for_preview(self):
        out = sb._spider_clean_doc_text_for_preview("  Hello\n\n\nworld  ")
        self.assertIsInstance(out, str)


class ModuleHygieneTests(unittest.TestCase):
    def test_module_does_not_import_app(self):
        self.assertNotIn("app", getattr(sb, "__dict__", {}))


if __name__ == "__main__":
    unittest.main()
