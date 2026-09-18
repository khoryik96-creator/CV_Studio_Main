"""Coverage for the blank-custom-field review queue in the AI Crawler.

A JobAdder candidate carries custom fields a recruiter fills in by hand. When one
is blank, an eligibility filter on that field drops the candidate, and the drop
reads the same as a real mismatch even though nobody ever typed a value in. These
tests pin the difference: a blank field sets the candidate aside for review, a
mismatch still discards them, and the ranked results do not change either way.
"""

import os
from pathlib import Path
import tempfile
import unittest

from owner_build_tools.build_protected import write_test_receipt


ROOT = Path(__file__).resolve().parents[1]
_MODULE_TEMPORARY = tempfile.TemporaryDirectory(prefix="cvstudio-spider-blank-")
_ORIGINAL_DATABASE_OVERRIDE = os.environ.get("CVSTUDIO_DB_PATH")
os.environ["CVSTUDIO_DB_PATH"] = str(
    Path(_MODULE_TEMPORARY.name) / "state" / "cv_studio.sqlite3"
)
write_test_receipt(ROOT)
try:
    import app
    import cvstudio_spider_score as score
finally:
    if _ORIGINAL_DATABASE_OVERRIDE is None:
        os.environ.pop("CVSTUDIO_DB_PATH", None)
    else:
        os.environ["CVSTUDIO_DB_PATH"] = _ORIGINAL_DATABASE_OVERRIDE


BLANK = score._SPIDER_BLANK_FIELD_REASONS


class BlankProfileFieldTests(unittest.TestCase):
    def test_each_taggable_custom_field_is_recognised(self):
        self.assertEqual(
            sorted(BLANK.values()), ["industry", "it_skills", "qualifications"]
        )
        for reason, field in BLANK.items():
            with self.subTest(reason=reason):
                self.assertEqual(score._spider_blank_profile_fields([reason]), [field])

    def test_several_blank_fields_are_all_reported(self):
        self.assertEqual(
            score._spider_blank_profile_fields(list(BLANK)),
            ["industry", "it_skills", "qualifications"],
        )

    def test_a_real_mismatch_is_never_a_blank_field(self):
        for reason in (
            "IT skills mismatch: SAP",
            "industry mismatch: FMCG",
            "qualifications mismatch: ACCA",
            "years experience below minimum 8: 3",
            "expected salary mismatch: 200000",
            "country mismatch: Singapore",
            "match fit below 10%",
        ):
            with self.subTest(reason=reason):
                self.assertEqual(score._spider_blank_profile_fields([reason]), [])

    def test_one_mismatch_beside_a_blank_field_still_discards(self):
        # Mixed reasons mean the source actively disqualified them, so they are not
        # a review case however many blanks sit alongside it.
        for other in ("industry mismatch: FMCG", "match fit below 10%"):
            with self.subTest(other=other):
                self.assertEqual(
                    score._spider_blank_profile_fields(
                        ["IT Skills not visible in JobAdder custom field", other]
                    ),
                    [],
                )

    def test_residential_status_is_deliberately_excluded(self):
        # Legal status is not something a CV is authority for, and guessing it would
        # be both unreliable and unfair. It stays a plain exclusion.
        self.assertEqual(
            score._spider_blank_profile_fields(
                ["Residential Status not visible in JobAdder custom field"]
            ),
            [],
        )
        self.assertNotIn(
            "Residential Status not visible in JobAdder custom field", BLANK
        )

    def test_nothing_and_malformed_input_is_safe(self):
        for excluded in (None, [], [""], [None], ["   "], 0, "not a list"):
            with self.subTest(excluded=excluded):
                self.assertEqual(score._spider_blank_profile_fields(excluded), [])


class BlankFieldGateTests(unittest.TestCase):
    """The gate itself, so the reason strings the queue keys on cannot drift."""

    BASE_CANDIDATE = {
        "candidateId": 4242,
        "firstName": "Alex",
        "lastName": "Tan",
        "resumeText": "Head of Operations. SAP implementation lead across six plants.",
    }

    def _score(self, filters):
        return score._spider_item_score(dict(self.BASE_CANDIDATE), filters, enriched=True)

    def test_a_blank_it_skills_field_produces_the_queue_reason(self):
        result = self._score({"it_skills": ["SAP"], "it_skills_mode": "any"})
        keep, excluded = result[0], result[4]
        self.assertFalse(keep)
        self.assertEqual(score._spider_blank_profile_fields(excluded), ["it_skills"])

    def test_a_blank_qualifications_field_produces_the_queue_reason(self):
        result = self._score({"qualifications": ["ACCA"], "qualifications_mode": "any"})
        keep, excluded = result[0], result[4]
        self.assertFalse(keep)
        self.assertEqual(score._spider_blank_profile_fields(excluded), ["qualifications"])

    def test_a_filled_field_that_mismatches_is_not_queued(self):
        candidate = dict(self.BASE_CANDIDATE)
        candidate["custom"] = [{"fieldId": app.SPIDER_IT_SKILLS_FIELD_ID, "name": "IT Skills", "value": ["Oracle"]}]
        result = score._spider_item_score(
            candidate, {"it_skills": ["SAP"], "it_skills_mode": "any"}, enriched=True
        )
        keep, excluded = result[0], result[4]
        self.assertFalse(keep)
        self.assertEqual(score._spider_blank_profile_fields(excluded), [])

    def test_no_filter_on_the_field_means_no_queue_and_no_drop(self):
        result = self._score({"must": "SAP"})
        self.assertEqual(score._spider_blank_profile_fields(result[4]), [])


class SearchResponseContractTests(unittest.TestCase):
    """The queue is a separate list and the ranked results are untouched."""

    def test_the_route_collects_rather_than_discarding(self):
        source = Path(ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("def collect_blank_field_candidate(", source)
        self.assertIn(
            "collect_blank_field_candidate(\n                    scoring_for_fit, excluded, resume_text, resume_source\n                )",
            source,
        )

    def test_the_queue_is_returned_beside_items_and_never_inside_them(self):
        source = Path(ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn('response_obj["needs_checking"] = needs_checking', source)
        self.assertIn('response_obj["items"] = filtered', source)
        # items is assigned from the ranked list alone.
        self.assertNotIn('response_obj["items"] = filtered + needs_checking', source)

    def test_the_queue_is_bounded_and_says_when_it_truncates(self):
        self.assertIsInstance(app._SPIDER_NEEDS_CHECKING_LIMIT, int)
        self.assertGreater(app._SPIDER_NEEDS_CHECKING_LIMIT, 0)
        self.assertLessEqual(app._SPIDER_NEEDS_CHECKING_LIMIT, 250)
        source = Path(ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn('"needs_checking_truncated": needs_checking_truncated', source)
        self.assertIn('"needs_checking_count": len(needs_checking)', source)

    def test_the_excerpt_is_bounded(self):
        self.assertIsInstance(app._SPIDER_NEEDS_CHECKING_EXCERPT_CHARS, int)
        self.assertGreater(app._SPIDER_NEEDS_CHECKING_EXCERPT_CHARS, 0)
        self.assertLessEqual(app._SPIDER_NEEDS_CHECKING_EXCERPT_CHARS, 4000)


if __name__ == "__main__":
    unittest.main()
