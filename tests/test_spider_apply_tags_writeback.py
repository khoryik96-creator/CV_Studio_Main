"""Coverage for writing a reviewed AI Crawler tag back into JobAdder.

This is the only part of the review queue that changes a live candidate record,
so the guards belong on the server and are pinned here: a value outside the
tenant's own option list is refused, a field that already holds something is
never overwritten, and every custom field the write is not changing survives it.

That last one is the hazard this codebase already documents elsewhere: JobAdder's
UpdateCandidate takes the whole custom collection, and a tenant may treat it as a
replacement, so sending one field alone can clear the rest.
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


TENANT_OPTIONS = {
    score.SPIDER_IT_SKILLS_FIELD_ID: ["SAP", "SAP FICO", "Oracle"],
    score.SPIDER_QUALIFICATIONS_FIELD_ID: ["ACCA", "CPA"],
}


class WritableFieldResolverTests(unittest.TestCase):
    def test_a_value_the_tenant_offers_resolves_to_its_field(self):
        targets, rejected = score._spider_writable_field_targets(
            "it_skills", ["SAP"], allowed=TENANT_OPTIONS[score.SPIDER_IT_SKILLS_FIELD_ID]
        )
        self.assertEqual(targets, {score.SPIDER_IT_SKILLS_FIELD_ID: ["SAP"]})
        self.assertEqual(rejected, [])
        targets, _ = score._spider_writable_field_targets(
            "qualifications", ["ACCA"],
            allowed=TENANT_OPTIONS[score.SPIDER_QUALIFICATIONS_FIELD_ID],
        )
        self.assertEqual(targets, {score.SPIDER_QUALIFICATIONS_FIELD_ID: ["ACCA"]})

    def test_a_free_text_value_outside_the_option_list_is_rejected(self):
        # The gap that shipped: only industry was ever checked, so any string at
        # all could be written into IT Skills and Qualifications.
        for field, allowed in (
            ("it_skills", TENANT_OPTIONS[score.SPIDER_IT_SKILLS_FIELD_ID]),
            ("qualifications", TENANT_OPTIONS[score.SPIDER_QUALIFICATIONS_FIELD_ID]),
        ):
            with self.subTest(field=field):
                targets, rejected = score._spider_writable_field_targets(
                    field, ["totally made up value"], allowed=allowed
                )
                self.assertEqual(targets, {})
                self.assertEqual(rejected, ["totally made up value"])

    def test_without_an_option_list_nothing_is_written(self):
        # Nothing can vouch for the value, so the safe answer is to refuse.
        targets, rejected = score._spider_writable_field_targets("it_skills", ["SAP"])
        self.assertEqual(targets, {})
        self.assertEqual(rejected, ["SAP"])

    def test_the_tenants_own_spelling_is_what_gets_written(self):
        targets, _ = score._spider_writable_field_targets(
            "it_skills", ["  sap fico "],
            allowed=TENANT_OPTIONS[score.SPIDER_IT_SKILLS_FIELD_ID],
        )
        self.assertEqual(targets, {score.SPIDER_IT_SKILLS_FIELD_ID: ["SAP FICO"]})

    def test_industry_picks_its_field_from_the_value(self):
        self.assertEqual(
            score._spider_writable_field_targets("industry", ["Financial Services"])[0],
            {1: ["Financial Services"]},
        )
        self.assertEqual(
            score._spider_writable_field_targets("industry", ["FSI - Insurance"])[0],
            {2: ["FSI - Insurance"]},
        )

    def test_an_industry_outside_the_taxonomy_is_rejected_not_written(self):
        targets, rejected = score._spider_writable_field_targets(
            "industry", ["Financial Services", "Totally Invented Industry"]
        )
        self.assertEqual(targets, {1: ["Financial Services"]})
        self.assertEqual(rejected, ["Totally Invented Industry"])

    def test_a_bare_string_is_refused_rather_than_spelled_out(self):
        # Iterating a string writes one tag per character.
        targets, rejected = score._spider_writable_field_targets(
            "it_skills", "SAP", allowed=TENANT_OPTIONS[score.SPIDER_IT_SKILLS_FIELD_ID]
        )
        self.assertEqual(targets, {})
        self.assertEqual(rejected, ["SAP"])

    def test_non_list_and_non_string_values_are_refused(self):
        for values in ({"a": 1}, 7, True):
            with self.subTest(values=values):
                targets, _ = score._spider_writable_field_targets(
                    "it_skills", values,
                    allowed=TENANT_OPTIONS[score.SPIDER_IT_SKILLS_FIELD_ID],
                )
                self.assertEqual(targets, {})

    def test_an_absurd_number_or_length_of_values_is_capped(self):
        targets, rejected = score._spider_writable_field_targets(
            "industry", ["Financial Services"] * 40
        )
        self.assertEqual(targets, {1: ["Financial Services"]})
        self.assertTrue(rejected)
        _targets, rejected = score._spider_writable_field_targets(
            "it_skills", ["x" * 400], allowed=["x" * 400]
        )
        self.assertEqual(len(rejected), 1)

    def test_an_unwritable_field_key_is_refused_whole(self):
        for key in ("residential", "residential_status", "salary", "", None):
            with self.subTest(key=key):
                targets, rejected = score._spider_writable_field_targets(key, ["Local Citizen"])
                self.assertEqual(targets, {})
                self.assertEqual(rejected, ["Local Citizen"])
        self.assertNotIn("residential", score.SPIDER_WRITABLE_FIELDS)

    def test_blank_and_filled_fields_are_told_apart_by_field_id(self):
        self.assertTrue(score._spider_field_is_blank({}, 3))
        self.assertTrue(score._spider_field_is_blank({"custom": []}, 3))
        self.assertFalse(
            score._spider_field_is_blank({"custom": [_custom(3, "IT Skills", ["Oracle"])]}, 3)
        )

    def test_a_renamed_field_still_reads_as_filled(self):
        # The matching gates read this field by id and ignore its label. Reading
        # it any more strictly here would call a renamed-but-filled field blank
        # and overwrite what somebody typed in.
        self.assertFalse(
            score._spider_field_is_blank(
                {"custom": [_custom(1, "Sector (renamed)", ["Financial Services"])]}, 1
            )
        )


class CustomWritePayloadTests(unittest.TestCase):
    def test_every_untouched_custom_field_survives_the_write(self):
        candidate = {"custom": [
            _custom(4, "Currency", ["SGD"]),
            _custom(5, "Residential Status", ["Permanent Resident"]),
        ]}
        payload, ok = score._spider_custom_write_payload(candidate, {3: ["SAP"]})
        self.assertTrue(ok)
        self.assertEqual(payload, [
            {"fieldId": 4, "value": ["SGD"]},
            {"fieldId": 5, "value": ["Permanent Resident"]},
            {"fieldId": 3, "value": ["SAP"]},
        ])

    def test_the_payload_is_jobadders_list_shape_not_a_keyed_object(self):
        payload, _ok = score._spider_custom_write_payload(
            {"custom": []}, {3: ["SAP"]}
        )
        self.assertIsInstance(payload, list)
        self.assertEqual(payload, [{"fieldId": 3, "value": ["SAP"]}])

    def test_a_field_already_present_is_replaced_in_place(self):
        candidate = {"custom": [_custom(3, "IT Skills", []), _custom(4, "Currency", ["SGD"])]}
        payload, _ok = score._spider_custom_write_payload(candidate, {3: ["SAP"]})
        self.assertEqual(payload[0], {"fieldId": 3, "value": ["SAP"]})
        self.assertIn({"fieldId": 4, "value": ["SGD"]}, payload)
        self.assertEqual(len([row for row in payload if row["fieldId"] == 3]), 1)

    def test_a_record_without_its_custom_collection_refuses_the_write(self):
        for candidate in ({}, {"candidateId": 1}, {"custom": None}, {"custom": {}}):
            with self.subTest(candidate=candidate):
                payload, ok = score._spider_custom_write_payload(candidate, {3: ["SAP"]})
                self.assertFalse(ok)
                self.assertEqual(payload, [])


class ApplyTagsRouteTests(unittest.TestCase):
    CANDIDATE_ID = "4242"

    def _headers(self):
        return {"X-CV-Studio-Request": "1", "X-AI-Crawler-Code": "test"}

    def _post(self, body, detail=None, options=None):
        if detail is None:
            detail = {"candidateId": 4242, "custom": []}
        recorded = {}

        def fake_request_json(endpoint, **kwargs):
            if endpoint.startswith("candidates/fields/custom/"):
                field_id = int(endpoint.rsplit("/", 1)[-1])
                supplied = TENANT_OPTIONS if options is None else options
                return 200, {"values": list(supplied.get(field_id) or [])}
            recorded["endpoint"] = endpoint
            recorded["method"] = kwargs.get("method")
            recorded["body"] = kwargs.get("body")
            return 200, {"candidateId": 4242}

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
    def test_a_blank_field_is_filled_in_jobadders_own_shape(self):
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
            {"custom": [{"fieldId": score.SPIDER_IT_SKILLS_FIELD_ID, "value": ["SAP"]}]},
        )

    def test_the_write_preserves_every_other_custom_field(self):
        detail = {"candidateId": 4242, "custom": [
            _custom(4, "Currency", ["SGD"]),
            _custom(5, "Residential Status", ["Permanent Resident"]),
        ]}
        response, recorded = self._post(
            {"candidate_id": self.CANDIDATE_ID, "fields": {"it_skills": ["SAP"]}},
            detail=detail,
        )
        sent = json.loads(recorded["body"].decode())["custom"]
        by_id = {row["fieldId"]: row["value"] for row in sent}
        self.assertEqual(by_id[4], ["SGD"])
        self.assertEqual(by_id[5], ["Permanent Resident"])
        self.assertEqual(by_id[score.SPIDER_IT_SKILLS_FIELD_ID], ["SAP"])
        self.assertEqual(response.get_json()["preserved_custom_field_count"], 2)

    def test_a_record_without_its_custom_fields_is_not_written(self):
        response, recorded = self._post(
            {"candidate_id": self.CANDIDATE_ID, "fields": {"it_skills": ["SAP"]}},
            detail={"candidateId": 4242},
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(recorded, {})

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
        self.assertEqual(recorded, {})

    def test_a_value_outside_the_tenant_option_list_never_reaches_jobadder(self):
        response, recorded = self._post({
            "candidate_id": self.CANDIDATE_ID,
            "fields": {"it_skills": ["totally made up value"]},
        })
        payload = response.get_json()
        self.assertEqual(payload["applied"], {})
        self.assertEqual(len(payload["rejected"]), 1)
        self.assertEqual(recorded, {})

    def test_an_invented_industry_never_reaches_jobadder(self):
        response, recorded = self._post({
            "candidate_id": self.CANDIDATE_ID,
            "fields": {"industry": ["Totally Invented Industry"]},
        })
        self.assertEqual(response.get_json()["applied"], {})
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
        self.assertEqual(
            json.loads(recorded["body"].decode()),
            {"custom": [{"fieldId": 1, "value": ["Financial Services"]}]},
        )

    def test_an_unreadable_option_list_refuses_the_field(self):
        response, recorded = self._post(
            {"candidate_id": self.CANDIDATE_ID, "fields": {"it_skills": ["SAP"]}},
            options={},
        )
        payload = response.get_json()
        self.assertEqual(payload["applied"], {})
        self.assertTrue(payload["rejected"])
        self.assertEqual(recorded, {})

    def test_a_field_that_cannot_be_written_is_refused(self):
        response, recorded = self._post({
            "candidate_id": self.CANDIDATE_ID,
            "fields": {"residential": ["Local Citizen"]},
        })
        payload = response.get_json()
        self.assertEqual(payload["applied"], {})
        self.assertEqual(payload["rejected"][0]["reason"], "not a writable field")
        self.assertEqual(recorded, {})

    def test_the_candidate_id_is_escaped_into_the_jobadder_path(self):
        response, recorded = self._post({
            "candidate_id": "4242/../../jobs",
            "fields": {"industry": ["Financial Services"]},
        })
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(recorded["endpoint"], "candidates/4242%2F..%2F..%2Fjobs")

    def test_the_candidate_is_re_read_before_every_write(self):
        with mock.patch.object(
            app, "_ja_refresh_access_token", return_value="fixture-token"
        ), mock.patch.object(
            app, "_spider_fetch_candidate_detail",
            return_value={"candidateId": 4242, "custom": []},
        ) as fetch_detail, mock.patch.object(
            app._JOBADDER_CLIENT, "request_json",
            return_value=(200, {"values": ["Financial Services"]}),
        ):
            app.app.test_client().post(
                "/jobadder/spider_apply_tags",
                json={"candidate_id": self.CANDIDATE_ID,
                      "fields": {"industry": ["Financial Services"]}},
                headers=self._headers(),
            )
        fetch_detail.assert_called_once()

    def test_a_successful_write_does_not_wipe_shared_caches(self):
        with mock.patch.object(app, "_spider_resume_text_cache_clear") as clear:
            self._post({
                "candidate_id": self.CANDIDATE_ID,
                "fields": {"it_skills": ["SAP"]},
            })
        clear.assert_not_called()

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
