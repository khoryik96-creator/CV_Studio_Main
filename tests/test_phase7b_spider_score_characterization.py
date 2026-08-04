"""Characterization tests for the Spider JD-scoring and candidate-fit helpers.

Locks the behaviour of the pure helpers extracted into ``cvstudio_spider_score``
(Phase 7B): job-description heading/relevance parsing, fit-term handling,
weighted term coverage, the candidate fit-percentage and overall item score, and
JobAdder option-payload flattening. These are a verbatim move from the legacy
web shell, so every assertion equally describes the pre-extraction behaviour.
"""

import unittest

import cvstudio_spider_score as score


class JdHeadingTests(unittest.TestCase):
    def test_strip_numeric_and_roman_prefixes(self):
        self.assertEqual(score._spider_strip_jd_heading_prefix("2.1  Lead the team"), "Lead the team")
        self.assertEqual(score._spider_strip_jd_heading_prefix("IV) Manage"), "Manage")

    def test_no_prefix_is_unchanged(self):
        self.assertEqual(score._spider_strip_jd_heading_prefix("Lead the team"), "Lead the team")

    def test_heading_section_classifies_core(self):
        section = score._spider_jd_heading_section("Requirements:")
        self.assertEqual(list(section), ["core", ""])


class RelevanceTermTests(unittest.TestCase):
    def test_relevance_terms_from_a_short_jd(self):
        terms = score._spider_jd_relevance_terms(
            "Requirements:\n- 5 years Python\n- AWS and Docker\n- Lead a team", max_terms=8
        )
        self.assertEqual(terms, ["Python", "AWS", "Docker", "AWS Docker"])


class FitTermTests(unittest.TestCase):
    def test_real_skill_is_not_ignored(self):
        self.assertFalse(score._spider_ignored_fit_term("python"))

    def test_weighted_coverage_fraction_and_matches(self):
        coverage, matched, all_terms, details = score._spider_weighted_coverage(
            "senior python engineer with aws", ["python", "aws", "java"]
        )
        self.assertAlmostEqual(coverage, 2 / 3)
        self.assertEqual(matched, ["python", "aws"])
        self.assertEqual(all_terms, ["python", "aws", "java"])
        missing = [d["term"] for d in details if d["status"] == "missing"]
        self.assertEqual(missing, ["java"])


class OptionPayloadTests(unittest.TestCase):
    def test_extract_option_values_from_items(self):
        self.assertEqual(
            score._spider_extract_option_values({"items": [{"value": "A"}, {"value": "B"}]}), ["A", "B"]
        )


class ScoringTests(unittest.TestCase):
    def _candidate(self):
        return {
            "candidateId": 1,
            "firstName": "Ada",
            "lastName": "L",
            "summary": "Senior Python engineer, 8 years, AWS and Docker, led a team of 5 in Kuala Lumpur",
            "employment": {"current": {"position": "Senior Software Engineer"}},
            "address": {"countryName": "Malaysia"},
        }

    def _filters(self):
        return {"rule": "python AND aws", "must": "python", "nice": "docker", "location": "Malaysia", "minYears": 5}

    def test_match_fit_percent_full_match(self):
        percent, matched, missing, details = score._spider_match_fit_percent(
            self._candidate(),
            self._filters(),
            "senior python engineer 8 years aws docker led a team kuala lumpur malaysia",
            ["python", "aws"],
        )
        self.assertEqual(percent, 100)
        self.assertEqual(details["method"], "normalized_weighted_coverage_v2")
        must = next(c for c in details["components"] if c["key"] == "must")
        self.assertEqual(must["matched"], ["python"])

    def test_item_score_returns_percent_and_matched_terms(self):
        result = score._spider_item_score(self._candidate(), self._filters(), enriched=True)
        self.assertIs(result[0], True)
        self.assertEqual(result[1], 100)
        self.assertIn("python", result[6])


class ReExportTests(unittest.TestCase):
    def test_app_reexports_are_the_module_objects(self):
        import app  # noqa: PLC0415 - importing the shell is the point of this check

        for name in (
            "_spider_strip_jd_heading_prefix",
            "_spider_jd_heading_section",
            "_spider_jd_scoring_lines",
            "_spider_jd_relevance_terms",
            "_spider_ignored_fit_term",
            "_spider_strip_context_fit_term",
            "_spider_context_only_fit_term",
            "_spider_weighted_coverage",
            "_spider_match_fit_percent",
            "_spider_item_score",
            "_spider_option_fallbacks",
            "_spider_extract_option_values",
        ):
            self.assertIs(getattr(app, name), getattr(score, name), name)


if __name__ == "__main__":
    unittest.main()
