"""Coverage for writing a reviewed AI Crawler tag back into JobAdder.

This is the only part of the review queue that changes a live candidate record,
so the guards belong on the server and are pinned here: a value outside the
tenant's own option list is refused, and a field that already holds something is
never overwritten.
"""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from owner_build_tools.build_protected import write_test_receipt


ROOT = Path(__file__).resolve().parents[1]
_MODULE_TEMPORARY = tempfile.TemporaryDirectory(prefix="cvstudio-spider-apply-")
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


def _custom(field_id, name, values):
    return {"fieldId": field_id, "name": name, "value": list(values)}


class WritableFieldResolverTests(unittest.TestCase):
    def test_each_writable_field_resolves_to_its_jobadder_field(self):
        targets, rejected = score._spider_writable_field_targets("it_skills", ["SAP"])
        self.assertEqual(targets, {score.SPIDER_IT_SKILLS_FIELD_ID: ["SAP"]})
        self.assertEqual(rejected, [])
        targets, rejected = score._spider_writable_field_targets("qualifications", ["ACCA"])
        self.assertEqual(targets, {score.SPIDER_QUALIFICATIONS_FIELD_ID: ["ACCA"]})
        self.assertEqual(rejected, [])

    def test_industry_picks_its_field_from_the_value(self):
        # A broad category is custom field #1; a sub-category is #2.
        self.assertEqual(
            score._spider_writable_field_targets("industry", ["Financial Services"])[0],
            {1: ["Financial Services"]},
        )
        self.assertEqual(
            score._spider_writable_field_targets("industry", ["FSI - Insurance"])[0],
            {2: ["FSI - Insurance"]},
        )

    def test_a_value_outside_the_taxonomy_is_rejected_not_written(self):
        targets, rejected = score._spider_writable_field_targets(
            "industry", ["Financial Services", "Totally Invented Industry"]
        )
        self.assertEqual(targets, {1: ["Financial Services"]})
        self.assertEqual(rejected, ["Totally Invented Industry"])

    def test_an_unwritable_field_key_is_refused_whole(self):
        # Residential Status is never inferred, so it must not be writable either.
        for key in ("residential", "residential_status", "salary", "", None):
            with self.subTest(key=key):
                targets, rejected = score._spider_writable_field_targets(key, ["Local Citizen"])
                self.assertEqual(targets, {})
                self.assertEqual(rejected, ["Local Citizen"])
        self.assertNotIn("residential", score.SPIDER_WRITABLE_FIELDS)

    def test_blank_and_filled_fields_are_told_apart(self):
        self.assertTrue(score._spider_field_is_blank({}, 3, ("IT Skills",)))
        self.assertTrue(
            score._spider_field_is_blank({"custom": []}, 3, ("IT Skills",))
        )
        self.assertFalse(
            score._spider_field_is_blank(
                {"custom": [_custom(3, "IT Skills", ["Oracle"])]}, 3, ("IT Skills",)
            )
        )


class ApplyTagsRouteTests(unittest.TestCase):
    CANDIDATE_ID = "4242"

    def _headers(self):
        return {"X-CV-Studio-Request": "1", "X-AI-Crawler-Code": "test"}

    def _post(self, body, detail=None, request_json=None):
        detail = {"candidateId": 4242} if detail is None else detail
        recorded = {}

        def fake_request_json(endpoint, **kwargs):
            recorded["endpoint"] = endpoint
            recorded["method"] = kwargs.get("method")
            recorded["body"] = kwargs.get("body")
            return 200, (request_json if request_json is not None else {"candidateId": 4242})

        with mock.patch.object(
            app, "_ja_refresh_access_token", return_value="fixture-token"
        ), mock.patch.object(
            app, "_spider_fetch_candidate_detail", return_value=detail
        ), mock.patch.object(
            app._JOBADDER_CLIENT, "request_json", side_effect=fake_request_json
        ):
            response = app.app.test_client().post(
                "/jobadder/spider_apply_tags", json=body, headers=self._headers()
            )
        return response, recorded

    # ── the write itself ─────────────────────────────────────────────────────
    def test_a_blank_field_is_filled(self):
        response, recorded = self._post({
            "candidate_id": self.CANDIDATE_ID,
            "fields": {"it_skills": ["SAP"]},
        })
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        payload = response.get_json()
        self.assertEqual(payload["applied"], {"it_skills": ["SAP"]})
        self.assertEqual(recorded["method"], "PUT")
        self.assertEqual(recorded["endpoint"], "candidates/4242")
        self.assertEqual(
            json.loads(recorded["body"].decode()),
            {"custom": {str(score.SPIDER_IT_SKILLS_FIELD_ID): ["SAP"]}},
        )

    def test_a_filled_field_is_never_overwritten(self):
        detail = {
            "candidateId": 4242,
            "custom": [_custom(score.SPIDER_IT_SKILLS_FIELD_ID, "IT Skills", ["Oracle"])],
        }
        response, recorded = self._post(
            {"candidate_id": self.CANDIDATE_ID, "fields": {"it_skills": ["SAP"]}},
            detail=detail,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["applied"], {})
        self.assertEqual(len(payload["skipped"]), 1)
        self.assertIn("already filled", payload["skipped"][0]["reason"])
        # Nothing at all was sent to JobAdder.
        self.assertEqual(recorded, {})

    def test_a_value_outside_the_allowed_list_never_reaches_jobadder(self):
        response, recorded = self._post({
            "candidate_id": self.CANDIDATE_ID,
            "fields": {"industry": ["Totally Invented Industry"]},
        })
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["applied"], {})
        self.assertEqual(len(payload["rejected"]), 1)
        self.assertEqual(recorded, {})

    def test_a_good_value_writes_while_a_bad_one_beside_it_is_dropped(self):
        response, recorded = self._post({
            "candidate_id": self.CANDIDATE_ID,
            "fields": {"industry": ["Financial Services", "Totally Invented Industry"]},
        })
        payload = response.get_json()
        self.assertEqual(payload["applied"], {"industry": ["Financial Services"]})
        self.assertEqual([item["value"] for item in payload["rejected"]],
                         ["Totally Invented Industry"])
        self.assertEqual(json.loads(recorded["body"].decode()), {"custom": {"1": ["Financial Services"]}})

    def test_a_field_that_cannot_be_written_is_refused(self):
        response, recorded = self._post({
            "candidate_id": self.CANDIDATE_ID,
            "fields": {"residential": ["Local Citizen"]},
        })
        payload = response.get_json()
        self.assertEqual(payload["applied"], {})
        self.assertEqual(payload["rejected"][0]["reason"], "not a writable field")
        self.assertEqual(recorded, {})

    def test_the_candidate_is_re_read_before_every_write(self):
        # The queue was built earlier in the search; somebody may have filled the
        # field in since, so the decision uses a fresh read, not the queue.
        with mock.patch.object(
            app, "_ja_refresh_access_token", return_value="fixture-token"
        ), mock.patch.object(
            app, "_spider_fetch_candidate_detail", return_value={"candidateId": 4242}
        ) as fetch_detail, mock.patch.object(
            app._JOBADDER_CLIENT, "request_json", return_value=(200, {})
        ):
            app.app.test_client().post(
                "/jobadder/spider_apply_tags",
                json={"candidate_id": self.CANDIDATE_ID, "fields": {"it_skills": ["SAP"]}},
                headers=self._headers(),
            )
        fetch_detail.assert_called_once()

    # ── refusals ─────────────────────────────────────────────────────────────
    def test_a_missing_candidate_or_field_is_a_bad_request(self):
        for body in (
            {},
            {"fields": {"it_skills": ["SAP"]}},
            {"candidate_id": ""},
            {"candidate_id": "4242"},
            {"candidate_id": "4242", "fields": {}},
            {"candidate_id": "4242", "fields": "SAP"},
        ):
            with self.subTest(body=body):
                response, _ = self._post(body)
                self.assertEqual(response.status_code, 400)

    def test_no_jobadder_token_is_refused_before_any_work(self):
        with mock.patch.object(app, "_ja_refresh_access_token", return_value=None), \
             mock.patch.object(app, "_ja_public_info", return_value={}):
            response = app.app.test_client().post(
                "/jobadder/spider_apply_tags",
                json={"candidate_id": "4242", "fields": {"it_skills": ["SAP"]}},
                headers=self._headers(),
            )
        self.assertEqual(response.status_code, 401)

    def test_a_candidate_jobadder_cannot_return_is_not_written(self):
        response, recorded = self._post(
            {"candidate_id": self.CANDIDATE_ID, "fields": {"it_skills": ["SAP"]}},
            detail={},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(recorded, {})


class RouteContractTests(unittest.TestCase):
    def test_the_route_is_registered_as_a_guarded_post(self):
        rules = {rule.rule: rule for rule in app.app.url_map.iter_rules()}
        self.assertIn("/jobadder/spider_apply_tags", rules)
        rule = rules["/jobadder/spider_apply_tags"]
        self.assertEqual(rule.methods & {"GET", "POST"}, {"POST"})
        self.assertEqual(rule.endpoint, "jobadder_spider_apply_tags")

    def test_the_sealed_route_count_was_bumped_deliberately(self):
        source = Path(ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("expected_route_count=119,", source)
        self.assertNotIn("expected_route_count=118,", source)


if __name__ == "__main__":
    unittest.main()
