"""Coverage for the blank-custom-field review queue in the AI Crawler.

A JobAdder candidate carries custom fields a recruiter fills in by hand. When one
is blank, an eligibility filter on that field drops the candidate, and the drop
reads the same as a real mismatch even though nobody ever typed a value in. These
tests pin the difference: a blank field sets the candidate aside for review, a
mismatch still discards them, and the ranked results do not change either way.

The end-to-end search test below is the one that matters. An earlier version of
this feature collected the queue inside the scorer, which never sees these
candidates because the eligibility pass has already dropped them. Every unit test
passed and the feature returned an empty queue on every real search. Unit tests
alone cannot catch that, so the route is exercised here for real.
"""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

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


class BlankFieldFromGateStateTests(unittest.TestCase):
    """The queue keys on the gate's verdict, not on the sentence it displays."""

    def test_each_taggable_field_is_recognised(self):
        for gate, field in (
            ("industry", "industry"),
            ("it_skills", "it_skills"),
            ("qualifications", "qualifications"),
        ):
            with self.subTest(gate=gate):
                self.assertEqual(
                    score._spider_blank_fields_from_states({gate: "unknown"}), [field]
                )

    def test_several_blank_fields_are_all_reported(self):
        self.assertEqual(
            score._spider_blank_fields_from_states({
                "industry": "unknown",
                "it_skills": "unknown",
                "qualifications": "unknown",
            }),
            ["industry", "it_skills", "qualifications"],
        )

    def test_a_blank_field_beside_a_passing_gate_still_qualifies(self):
        self.assertEqual(
            score._spider_blank_fields_from_states({
                "industry": "unknown",
                "country": "match",
                "salary": "match_missing",
            }),
            ["industry"],
        )

    def test_a_real_mismatch_is_never_a_blank_field(self):
        for status in ("mismatch", "invalid", "excluded", ""):
            with self.subTest(status=status):
                self.assertEqual(
                    score._spider_blank_fields_from_states({
                        "industry": "unknown",
                        "it_skills": status,
                    }),
                    [],
                )

    def test_an_undecided_gate_the_cv_cannot_answer_disqualifies(self):
        # Residential status, country and salary are not tags this queue offers
        # to fill, so a candidate undecided on one is not a review row.
        for gate in ("residential", "country", "salary"):
            with self.subTest(gate=gate):
                self.assertEqual(
                    score._spider_blank_fields_from_states(
                        {"industry": "unknown", gate: "unknown"}
                    ),
                    [],
                )

    def test_residential_status_is_never_offered_for_tagging(self):
        self.assertNotIn("residential", score._SPIDER_BLANK_FIELD_GATES)
        self.assertNotIn("residential", score.SPIDER_WRITABLE_FIELDS)

    def test_malformed_input_is_empty_rather_than_an_error(self):
        for states in (None, {}, [], "unknown", 0, {"industry": None}):
            with self.subTest(states=states):
                self.assertEqual(score._spider_blank_fields_from_states(states), [])

    def test_a_fully_matching_candidate_is_not_a_review_row(self):
        self.assertEqual(
            score._spider_blank_fields_from_states(
                {"industry": "match", "it_skills": "match_missing"}
            ),
            [],
        )


class BlankFieldSearchRouteTests(unittest.TestCase):
    """The queue as the search actually produces it."""

    @staticmethod
    def _headers():
        return {"Origin": "http://127.0.0.1:5000", "X-CV-Studio-Request": "1"}

    @staticmethod
    def _summary(candidate_id, custom):
        return {
            "candidateId": candidate_id,
            "firstName": "Ayu",
            "lastName": "Candidate {}".format(candidate_id),
            "summary": "Senior finance systems lead",
            "_spiderSearchTerms": ["SAP"],
        }

    def _run(self, candidates, filters, resume_text="Ten years running SAP FICO."):
        """candidates: {id: custom-field list}. A blank list means nothing filled."""
        summaries = [self._summary(cid, custom) for cid, custom in candidates.items()]
        details = {
            str(cid): {"candidateId": int(cid), "custom": list(custom)}
            for cid, custom in candidates.items()
        }
        metadata = {
            "mode": "plain",
            "query": "Finance",
            "returned": len(summaries),
            "search": {"reported_total": len(summaries), "warnings": [], "pages": 1},
        }
        with mock.patch.object(
            app, "_ja_refresh_access_token", return_value="fixture-token"
        ), mock.patch.object(
            app, "_spider_plain_keyword_jobadder_candidates",
            return_value=(summaries, metadata),
        ), mock.patch.object(
            app, "_spider_fetch_candidate_detail",
            side_effect=lambda _t, cid: details.get(str(cid)),
        ), mock.patch.object(
            app, "_spider_fetch_candidate_resume_text",
            return_value=(resume_text, "latest resume"),
        ) as fetch_resume:
            response = app.app.test_client().post(
                "/jobadder/spider_search",
                json={"query": "Finance", "limit": 10, "filters": filters},
                headers=self._headers(),
            )
        return response, fetch_resume

    def test_a_blank_field_candidate_reaches_the_queue(self):
        # The regression this whole file exists for: candidate 2 has no Industry
        # value at all, so the eligibility pass drops them before ranking. They
        # must still come back for review.
        response, _ = self._run(
            {
                1: [{"fieldId": 1, "name": "Industry", "value": ["Financial Services"]}],
                2: [],
            },
            {"role": "Finance", "industry": "Financial Services"},
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        payload = response.get_json()
        self.assertEqual([item["candidateId"] for item in payload["items"]], [1])
        queue = payload["needs_checking"]
        self.assertEqual([row["candidate_id"] for row in queue], ["2"])
        self.assertEqual(queue[0]["blank_fields"], ["industry"])
        self.assertEqual(payload["filter_summary"]["needs_checking_count"], 1)

    def test_the_queue_row_carries_a_name_and_the_cv(self):
        response, _ = self._run(
            {2: []}, {"role": "Finance", "it_skills": "SAP"}
        )
        row = response.get_json()["needs_checking"][0]
        # A recruiter decides from this row whether to write into a live record,
        # so it has to say who the person is.
        self.assertEqual(row["name"], "Ayu Candidate 2")
        self.assertNotIn("Candidate 2", row["name"].replace("Ayu Candidate 2", ""))
        self.assertIn("SAP FICO", row["resume_excerpt"])
        self.assertEqual(row["resume_source"], "latest resume")
        self.assertGreater(row["resume_characters"], 0)

    def test_a_real_mismatch_stays_out_of_the_queue(self):
        response, _ = self._run(
            {
                2: [{"fieldId": 3, "name": "IT Skills", "value": ["Oracle"]}],
            },
            {"role": "Finance", "it_skills": "SAP"},
        )
        payload = response.get_json()
        self.assertEqual(payload["items"], [])
        self.assertEqual(payload["needs_checking"], [])

    def test_a_blank_field_beside_a_mismatch_stays_out(self):
        # Industry is blank but IT Skills actively disagrees, so this candidate
        # was rejected for a real reason and is not a review row.
        response, _ = self._run(
            {
                2: [{"fieldId": 3, "name": "IT Skills", "value": ["Oracle"]}],
            },
            {"role": "Finance", "industry": "Financial Services", "it_skills": "SAP"},
        )
        self.assertEqual(response.get_json()["needs_checking"], [])

    def test_a_kept_candidate_is_never_also_a_review_row(self):
        response, _ = self._run(
            {1: [{"fieldId": 3, "name": "IT Skills", "value": ["SAP"]}]},
            {"role": "Finance", "it_skills": "SAP"},
        )
        payload = response.get_json()
        self.assertEqual([item["candidateId"] for item in payload["items"]], [1])
        self.assertEqual(payload["needs_checking"], [])

    def test_the_queue_is_bounded_and_says_so(self):
        many = {cid: [] for cid in range(1, app._SPIDER_NEEDS_CHECKING_LIMIT + 6)}
        response, _ = self._run(many, {"role": "Finance", "it_skills": "SAP"})
        payload = response.get_json()
        self.assertEqual(
            len(payload["needs_checking"]), app._SPIDER_NEEDS_CHECKING_LIMIT
        )
        self.assertTrue(payload["filter_summary"]["needs_checking_truncated"])

    def test_no_filter_means_no_queue(self):
        response, _ = self._run({1: [], 2: []}, {"role": "Finance"})
        payload = response.get_json()
        self.assertEqual(payload["needs_checking"], [])
        self.assertEqual(payload["filter_summary"]["needs_checking_count"], 0)

    def test_ranked_results_are_identical_with_and_without_the_queue(self):
        # The queue must be additive. Same search, one candidate blank: the kept
        # list and its order do not move.
        filters = {"role": "Finance", "it_skills": "SAP"}
        filled = {
            1: [{"fieldId": 3, "name": "IT Skills", "value": ["SAP"]}],
            3: [{"fieldId": 3, "name": "IT Skills", "value": ["SAP"]}],
        }
        with_blank = dict(filled)
        with_blank[2] = []
        baseline = self._run(filled, filters)[0].get_json()
        widened = self._run(with_blank, filters)[0].get_json()
        self.assertEqual(
            [item["candidateId"] for item in baseline["items"]],
            [item["candidateId"] for item in widened["items"]],
        )
        self.assertEqual(baseline["filter_summary"]["kept"],
                         widened["filter_summary"]["kept"])
        self.assertEqual([row["candidate_id"] for row in widened["needs_checking"]], ["2"])


class BlankFieldResponseContractTests(unittest.TestCase):
    def test_the_search_response_always_declares_the_queue(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn('response_obj["needs_checking"] = needs_checking', source)
        self.assertIn('"needs_checking_count": len(needs_checking)', source)
        self.assertIn('"needs_checking_truncated": needs_checking_truncated', source)

    def test_the_queue_is_collected_where_candidates_are_dropped(self):
        # Pinned deliberately: collecting anywhere downstream of the eligibility
        # pass sees none of these candidates, which is how this shipped broken.
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("collect_blank_field_candidate(candidate, states)", source)
        self.assertIn("custom_filter_excluded_count += 1", source)
        collect_at = source.index("collect_blank_field_candidate(candidate, states)")
        raw_items_at = source.index("raw_items = eligibility_matched_items")
        self.assertLess(collect_at, raw_items_at)


if __name__ == "__main__":
    unittest.main()
