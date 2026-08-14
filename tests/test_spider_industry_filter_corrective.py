"""Regression coverage for PR #142's canonical JobAdder Industry filter."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import urllib.parse

from owner_build_tools.build_protected import write_test_receipt


ROOT = Path(__file__).resolve().parents[1]
_MODULE_TEMPORARY = tempfile.TemporaryDirectory(prefix="cvstudio-spider-industry-")
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


class IndustryMatchingTests(unittest.TestCase):
    def test_broad_and_subcategory_select_the_written_jobadder_fields(self):
        self.assertEqual(
            score._spider_industry_filter_spec("Financial Services"),
            (1, "Financial Services"),
        )
        self.assertEqual(
            score._spider_industry_filter_spec("FSI - Insurance"),
            (2, "FSI - Insurance"),
        )

    def test_match_uses_exact_value_from_the_selected_custom_field(self):
        candidate = {
            "custom": [
                {"fieldId": 1, "name": "Industry", "value": ["Financial Services"]},
                {"fieldId": 2, "name": "Industry Sub-Category", "value": ["FSI - Insurance"]},
            ]
        }
        self.assertEqual(
            score._spider_industry_match(candidate, "Financial Services"),
            ("match", "Financial Services"),
        )
        self.assertEqual(
            score._spider_industry_match(candidate, "FSI - Insurance"),
            ("match", "FSI - Insurance"),
        )
        self.assertEqual(
            score._spider_industry_match(candidate, "Life Science/Medical"),
            ("mismatch", "Financial Services"),
        )

    def test_match_accepts_nested_embedded_self_candidate_shape(self):
        candidate = {
            "candidateId": 1,
            "_embedded": {
                "self": {
                    "custom": [{"fieldId": 2, "value": ["FSI - Insurance"]}]
                }
            },
        }
        self.assertEqual(
            score._spider_industry_match(candidate, "FSI - Insurance"),
            ("match", "FSI - Insurance"),
        )

    def test_item_score_rejects_mismatch_even_when_resume_keywords_fit(self):
        candidate = {
            "candidateId": 1,
            "summary": "Senior Python AWS engineer",
            "custom": [{"fieldId": 1, "value": ["Life Science/Medical"]}],
            "_spiderSearchTerms": ["Python"],
        }
        result = score._spider_item_score(
            candidate,
            {"role": "Engineer", "must": "Python", "industry": "Financial Services"},
            enriched=True,
        )
        self.assertIs(result[0], False)
        self.assertEqual(result[1], 0)
        self.assertEqual(result[4], ["industry mismatch: Life Science/Medical"])

    def test_missing_custom_field_is_unknown_then_excluded_after_detail(self):
        candidate = {
            "candidateId": 1,
            "summary": "Senior Python AWS engineer",
            "_spiderSearchTerms": ["Python"],
        }
        preliminary = score._spider_item_score(
            candidate,
            {"role": "Engineer", "must": "Python", "industry": "Financial Services"},
            enriched=False,
        )
        enriched = score._spider_item_score(
            candidate,
            {"role": "Engineer", "must": "Python", "industry": "Financial Services"},
            enriched=True,
        )
        self.assertIs(preliminary[0], True)
        self.assertIn("industry requires JobAdder candidate detail", preliminary[3])
        self.assertIs(enriched[0], False)
        self.assertEqual(enriched[4], ["industry not visible in JobAdder custom field"])


class ItSkillsMatchingTests(unittest.TestCase):
    def test_it_skills_match_exact_field_three_values(self):
        candidate = {
            "custom": [{"fieldId": 3, "name": "IT Skills", "value": ["Python", "AWS"]}],
        }
        self.assertEqual(
            score._spider_it_skills_match(candidate, "Python"),
            ("match", "Python"),
        )
        self.assertEqual(
            score._spider_it_skills_match(candidate, "Python, SAP"),
            ("match", "Python"),
        )
        self.assertEqual(
            score._spider_it_skills_match(candidate, "Python, AWS", require_all=True),
            ("match", "Python, AWS"),
        )
        self.assertEqual(
            score._spider_it_skills_match(candidate, "Python, SAP", require_all=True),
            ("mismatch", "Python, AWS"),
        )

    def test_resume_keyword_does_not_override_it_skills_custom_field(self):
        candidate = {
            "candidateId": 1,
            "summary": "Senior Python engineer",
            "custom": [{"fieldId": 3, "name": "IT Skills", "value": ["SAP"]}],
            "_spiderSearchTerms": ["Python"],
        }
        result = score._spider_item_score(
            candidate,
            {"role": "Engineer", "it_skills": "Python"},
            enriched=True,
        )
        self.assertIs(result[0], False)
        self.assertEqual(result[4], ["IT skills mismatch: SAP"])

    def test_field_three_with_an_unexpected_label_is_not_trusted(self):
        candidate = {
            "custom": [{"fieldId": 3, "name": "Different Field", "value": ["Python"]}],
        }
        self.assertEqual(
            score._spider_it_skills_match(candidate, "Python"),
            ("unknown", "Python"),
        )


class AdditionalEligibilityMatchingTests(unittest.TestCase):
    def test_professional_qualifications_use_exact_field_seven_values(self):
        candidate = {
            "custom": [
                {"fieldId": 7, "name": "Professional Qualifications", "value": ["PMP", "ITIL"]}
            ]
        }
        self.assertEqual(
            score._spider_qualifications_match(candidate, "PMP"),
            ("match", "PMP"),
        )
        self.assertEqual(
            score._spider_qualifications_match(candidate, "PMP, ACCA", require_all=True),
            ("mismatch", "PMP, ITIL"),
        )

    def test_residential_status_uses_field_five_and_fallback_aliases(self):
        candidate = {
            "custom": [
                {"fieldId": 5, "name": "Residential Status", "value": ["Malaysian Citizen"]}
            ]
        }
        self.assertEqual(
            score._spider_residential_match(candidate, "Malaysian Citizen"),
            ("match", "Malaysian Citizen"),
        )
        self.assertEqual(
            score._spider_residential_match(candidate, "Local Citizen"),
            ("match", "Malaysian Citizen"),
        )
        self.assertEqual(
            score._spider_residential_match(candidate, "Permanent Resident"),
            ("mismatch", "Malaysian Citizen"),
        )

    def test_expected_monthly_salary_range_and_missing_option(self):
        candidate = {
            "employment": {
                "ideal": {
                    "salary": {"currency": "MYR", "ratePer": "Month", "rateLow": 8000}
                }
            }
        }
        self.assertEqual(score._spider_salary_match(candidate, 7000, 9000)[0], "match")
        self.assertEqual(score._spider_salary_match(candidate, 9000, 12000)[0], "mismatch")
        range_candidate = {
            "employment": {
                "ideal": {
                    "salary": {
                        "currency": "MYR",
                        "ratePer": "Month",
                        "rateLow": 8000,
                        "rateHigh": 10000,
                    }
                }
            }
        }
        self.assertEqual(score._spider_salary_match(range_candidate, 9000, 12000)[0], "match")
        self.assertEqual(score._spider_salary_match(range_candidate, 11000, 12000)[0], "mismatch")
        self.assertEqual(score._spider_salary_match({}, 7000, 9000)[0], "unknown")
        self.assertEqual(
            score._spider_salary_match({}, 7000, 9000, include_missing=True),
            ("match_missing", "not provided (included)"),
        )


class IndustryRouteTests(unittest.TestCase):
    @staticmethod
    def _request_headers():
        return {
            "Origin": "http://127.0.0.1:5000",
            "X-CV-Studio-Request": "1",
        }

    @staticmethod
    def _summary(candidate_id):
        return {
            "candidateId": candidate_id,
            "firstName": "Candidate",
            "lastName": str(candidate_id),
            "summary": "Senior Python AWS software engineer",
            "_spiderSearchTerms": ["Python", "AWS"],
        }

    @staticmethod
    def _detail(_token, candidate_id):
        # The only match is deliberately the later discovery row. With limit=1,
        # this proves Industry filtering happens before ranking/truncation.
        industry = "Financial Services" if str(candidate_id) == "2" else "Life Science/Medical"
        return {
            "candidateId": int(candidate_id),
            "summary": "Senior Python AWS software engineer",
            "custom": [{"fieldId": 1, "name": "Industry", "value": [industry]}],
        }

    def test_industry_options_are_local_and_make_no_jobadder_request(self):
        with mock.patch.object(app, "_ja_refresh_access_token") as refresh, mock.patch.object(
            app._JOBADDER_CLIENT, "request_json"
        ) as request_json:
            response = app.app.test_client().get("/jobadder/spider_options?name=industry")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["canonical"])
        self.assertEqual(len(payload["items"]), 91)
        refresh.assert_not_called()
        request_json.assert_not_called()

    def test_it_skills_options_come_from_candidate_custom_field_three(self):
        definition = {
            "fieldId": 3,
            "name": "IT Skills",
            "type": "List",
            "values": [{"value": "Python"}, {"value": "SAP"}],
        }
        with mock.patch.object(
            app, "_ja_refresh_access_token", return_value="fixture-token"
        ), mock.patch.object(
            app._JOBADDER_CLIENT,
            "request_json",
            return_value=(200, definition),
        ) as request_json:
            response = app.app.test_client().get(
                "/jobadder/spider_options?name=it_skills"
            )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["items"], ["Python", "SAP"])
        self.assertEqual(payload["field_id"], 3)
        self.assertEqual(payload["source"], "candidate_custom_field_definition")
        self.assertFalse(payload["fallback"])
        request_json.assert_called_once_with(
            "candidates/fields/custom/3",
            token="fixture-token",
            timeout=8,
            fallback={},
        )

    def test_it_skills_options_fall_back_if_field_three_has_wrong_label(self):
        with mock.patch.object(
            app, "_ja_refresh_access_token", return_value="fixture-token"
        ), mock.patch.object(
            app._JOBADDER_CLIENT,
            "request_json",
            return_value=(200, {"fieldId": 3, "name": "Different Field", "values": ["Python"]}),
        ):
            response = app.app.test_client().get(
                "/jobadder/spider_options?name=it_skills"
            )
        payload = response.get_json()
        self.assertTrue(payload["fallback"])
        self.assertIn("field 3 is not IT Skills", payload["errors"])

    def test_residential_and_qualification_options_use_tenant_custom_fields(self):
        definitions = {
            "candidates/fields/custom/5": {
                "fieldId": 5,
                "name": "Residential Status",
                "values": ["Malaysian Citizen", "Permanent Resident"],
            },
            "candidates/fields/custom/7": {
                "fieldId": 7,
                "name": "Professional Qualifications",
                "values": ["PMP", "ITIL"],
            },
        }

        def request_json(endpoint, **_kwargs):
            return 200, definitions[endpoint]

        with mock.patch.object(
            app, "_ja_refresh_access_token", return_value="fixture-token"
        ), mock.patch.object(
            app._JOBADDER_CLIENT, "request_json", side_effect=request_json
        ):
            residential = app.app.test_client().get(
                "/jobadder/spider_options?name=residential"
            ).get_json()
            qualifications = app.app.test_client().get(
                "/jobadder/spider_options?name=qualifications"
            ).get_json()
        self.assertEqual(residential["items"], ["Malaysian Citizen", "Permanent Resident"])
        self.assertEqual(residential["field_id"], 5)
        self.assertEqual(qualifications["items"], ["PMP", "ITIL"])
        self.assertEqual(qualifications["field_id"], 7)

    def test_country_options_come_from_authoritative_jobadder_endpoint(self):
        with mock.patch.object(
            app, "_ja_refresh_access_token", return_value="fixture-token"
        ), mock.patch.object(
            app._JOBADDER_CLIENT,
            "request_json",
            return_value=(
                200,
                {"items": [{"code": "MY", "name": "Malaysia"}, {"code": "SG", "name": "Singapore"}]},
            ),
        ) as request_json:
            response = app.app.test_client().get("/jobadder/spider_options?name=country")
        payload = response.get_json()
        self.assertEqual(payload["items"], ["Malaysia", "Singapore"])
        self.assertEqual(payload["source"], "jobadder_countries")
        self.assertTrue(payload["canonical"])
        request_json.assert_called_once_with(
            "countries",
            token="fixture-token",
            timeout=8,
            fallback={"items": []},
        )

    def test_candidate_search_requests_supported_embedded_self_representation(self):
        payload = {
            "items": [{
                "candidateId": 2,
                "custom": [{"fieldId": 1, "value": ["Financial Services"]}],
            }],
            "totalCount": 1,
        }
        with mock.patch.object(
            app,
            "_spider_get_ja_raw",
            return_value=(json.dumps(payload).encode("utf-8"), "application/json", ""),
        ) as request_raw:
            items, metadata = app._spider_jobadder_keyword_items(
                "fixture-token",
                "Software Engineer",
                max_items=1,
                page_size=1,
                embed=True,
                include_self=True,
            )
        query = urllib.parse.parse_qs(
            urllib.parse.urlsplit(request_raw.call_args.args[1]).query
        )
        self.assertEqual(query["Embed"], ["self", "skills", "notes"])
        self.assertEqual(items, payload["items"])
        self.assertTrue(metadata["embed_self_applied"])

    def _run_search(self, *, native_boolean, embedded=False):
        summaries = [self._summary(1), self._summary(2)]
        if embedded:
            for item in summaries:
                item["custom"] = self._detail(
                    "fixture-token", item["candidateId"]
                )["custom"]
        metadata = {
            "mode": "native_boolean" if native_boolean else "plain",
            "query": "Python AND AWS" if native_boolean else "Software Engineer",
            "returned": 2,
            "search": {"reported_total": 2, "warnings": [], "pages": 1},
        }
        if native_boolean:
            for item in summaries:
                item["_spiderNativeBooleanMatched"] = True
                item["_spiderBooleanRule"] = "Python AND AWS"
            discovery_patch = mock.patch.object(
                app, "_spider_native_boolean_jobadder_candidates", return_value=(summaries, metadata)
            )
            filters = {
                "role": "Software Engineer",
                "must": "Python AND AWS",
                "industry": "Financial Services",
            }
            query = "Python AND AWS"
        else:
            discovery_patch = mock.patch.object(
                app, "_spider_plain_keyword_jobadder_candidates", return_value=(summaries, metadata)
            )
            filters = {"role": "Software Engineer", "industry": "Financial Services"}
            query = "Software Engineer"

        with mock.patch.object(
            app, "_ja_refresh_access_token", return_value="fixture-token"
        ), discovery_patch, mock.patch.object(
            app, "_spider_fetch_candidate_detail", side_effect=self._detail
        ) as fetch_detail, mock.patch.object(
            app, "_spider_fetch_candidate_resume_text", return_value=("", "")
        ):
            response = app.app.test_client().post(
                "/jobadder/spider_search",
                json={"query": query, "limit": 1, "filters": filters},
                headers=self._request_headers(),
            )
        return response, fetch_detail

    def test_plain_role_search_filters_before_ranking_and_reuses_detail(self):
        response, fetch_detail = self._run_search(native_boolean=False)
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        payload = response.get_json()
        self.assertEqual([item["candidateId"] for item in payload["items"]], [2])
        summary = payload["filter_summary"]
        self.assertEqual(summary["industry_filter_scanned"], 2)
        self.assertEqual(summary["industry_filter_matched"], 1)
        self.assertEqual(summary["industry_filter_excluded"], 1)
        self.assertEqual(summary["industry_filter_unavailable"], 0)
        self.assertEqual(fetch_detail.call_count, 2)

    def test_embedded_custom_fields_avoid_per_candidate_detail_reads(self):
        response, fetch_detail = self._run_search(
            native_boolean=False, embedded=True
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        payload = response.get_json()
        self.assertEqual([item["candidateId"] for item in payload["items"]], [2])
        summary = payload["filter_summary"]
        self.assertEqual(summary["industry_embedded_records"], 2)
        self.assertEqual(summary["industry_detail_requests"], 0)
        fetch_detail.assert_not_called()

    def test_native_boolean_search_still_applies_industry_filter(self):
        response, fetch_detail = self._run_search(native_boolean=True)
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        payload = response.get_json()
        self.assertEqual([item["candidateId"] for item in payload["items"]], [2])
        self.assertEqual(payload["filter_summary"]["industry_filter_matched"], 1)
        self.assertEqual(fetch_detail.call_count, 2)

    def test_it_skills_filter_uses_embedded_field_three_before_ranking(self):
        summaries = [self._summary(1), self._summary(2)]
        summaries[0]["custom"] = [{"fieldId": 3, "name": "IT Skills", "value": ["SAP"]}]
        summaries[1]["custom"] = [{"fieldId": 3, "name": "IT Skills", "value": ["Python"]}]
        metadata = {
            "mode": "plain",
            "query": "Software Engineer",
            "returned": 2,
            "search": {"reported_total": 2, "warnings": [], "pages": 1},
        }
        with mock.patch.object(
            app, "_ja_refresh_access_token", return_value="fixture-token"
        ), mock.patch.object(
            app,
            "_spider_plain_keyword_jobadder_candidates",
            return_value=(summaries, metadata),
        ) as discover, mock.patch.object(
            app, "_spider_fetch_candidate_detail"
        ) as fetch_detail, mock.patch.object(
            app, "_spider_fetch_candidate_resume_text", return_value=("", "")
        ):
            response = app.app.test_client().post(
                "/jobadder/spider_search",
                json={
                    "query": "Software Engineer",
                    "limit": 1,
                    "filters": {"role": "Software Engineer", "it_skills": "Python"},
                },
                headers=self._request_headers(),
            )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        payload = response.get_json()
        self.assertEqual([item["candidateId"] for item in payload["items"]], [2])
        summary = payload["filter_summary"]
        self.assertTrue(summary["it_skills_filter_active"])
        self.assertEqual(summary["it_skills_filter_field_id"], 3)
        self.assertEqual(summary["it_skills_filter_matched"], 1)
        self.assertEqual(summary["it_skills_filter_excluded"], 1)
        self.assertEqual(summary["it_skills_embedded_records"], 2)
        self.assertEqual(summary["it_skills_detail_requests"], 0)
        self.assertTrue(discover.call_args.kwargs["include_self"])
        fetch_detail.assert_not_called()

    def test_industry_and_it_skills_are_intersected(self):
        summaries = [self._summary(1), self._summary(2)]
        summaries[0]["custom"] = [
            {"fieldId": 1, "name": "Industry", "value": ["Financial Services"]},
            {"fieldId": 3, "name": "IT Skills", "value": ["SAP"]},
        ]
        summaries[1]["custom"] = [
            {"fieldId": 1, "name": "Industry", "value": ["Financial Services"]},
            {"fieldId": 3, "name": "IT Skills", "value": ["Python"]},
        ]
        metadata = {
            "mode": "plain",
            "query": "Software Engineer",
            "returned": 2,
            "search": {"reported_total": 2, "warnings": [], "pages": 1},
        }
        with mock.patch.object(
            app, "_ja_refresh_access_token", return_value="fixture-token"
        ), mock.patch.object(
            app,
            "_spider_plain_keyword_jobadder_candidates",
            return_value=(summaries, metadata),
        ), mock.patch.object(
            app, "_spider_fetch_candidate_detail"
        ) as fetch_detail, mock.patch.object(
            app, "_spider_fetch_candidate_resume_text", return_value=("", "")
        ):
            response = app.app.test_client().post(
                "/jobadder/spider_search",
                json={
                    "query": "Software Engineer",
                    "limit": 1,
                    "filters": {
                        "role": "Software Engineer",
                        "industry": "Financial Services",
                        "it_skills": "Python",
                    },
                },
                headers=self._request_headers(),
            )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        payload = response.get_json()
        self.assertEqual([item["candidateId"] for item in payload["items"]], [2])
        summary = payload["filter_summary"]
        self.assertEqual(summary["industry_filter_matched"], 2)
        self.assertEqual(summary["it_skills_filter_matched"], 1)
        self.assertEqual(summary["excluded_count"], 1)
        fetch_detail.assert_not_called()

    def test_country_residential_qualifications_and_salary_filter_before_ranking(self):
        summaries = [self._summary(1), self._summary(2)]
        for item in summaries:
            passing = item["candidateId"] == 2
            item["address"] = {"country": "Malaysia" if passing else "Singapore"}
            item["custom"] = [
                {
                    "fieldId": 5,
                    "name": "Residential Status",
                    "value": ["Malaysian Citizen" if passing else "Permanent Resident"],
                },
                {
                    "fieldId": 7,
                    "name": "Professional Qualifications",
                    "value": ["PMP" if passing else "ACCA"],
                },
            ]
            item["employment"] = {
                "ideal": {
                    "salary": {
                        "currency": "MYR",
                        "ratePer": "Month",
                        "rateLow": 8000 if passing else 15000,
                    }
                }
            }
        metadata = {
            "mode": "plain",
            "query": "Python",
            "returned": 2,
            "search": {"reported_total": 2, "warnings": [], "pages": 1},
        }
        with mock.patch.object(
            app, "_ja_refresh_access_token", return_value="fixture-token"
        ), mock.patch.object(
            app,
            "_spider_plain_keyword_jobadder_candidates",
            return_value=(summaries, metadata),
        ) as discover, mock.patch.object(
            app, "_spider_fetch_candidate_detail"
        ) as fetch_detail, mock.patch.object(
            app, "_spider_fetch_candidate_resume_text", return_value=("", "")
        ):
            response = app.app.test_client().post(
                "/jobadder/spider_search",
                json={
                    "query": "Python",
                    "limit": 1,
                    "filters": {
                        "must": "Python",
                        "country": "Malaysia",
                        "residential": "Malaysian Citizen",
                        "qualifications": "PMP",
                        "salary_min": 7000,
                        "salary_max": 9000,
                        "include_missing_salary": False,
                    },
                },
                headers=self._request_headers(),
            )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        payload = response.get_json()
        self.assertEqual([item["candidateId"] for item in payload["items"]], [2])
        summary = payload["filter_summary"]
        self.assertEqual(summary["country_filter_matched"], 1)
        self.assertEqual(summary["residential_filter_matched"], 1)
        self.assertEqual(summary["qualifications_filter_matched"], 1)
        self.assertEqual(summary["salary_filter_matched"], 1)
        self.assertEqual(summary["excluded_count"], 1)
        self.assertTrue(discover.call_args.kwargs["include_self"])
        fetch_detail.assert_not_called()

    def test_salary_bounds_are_validated(self):
        with mock.patch.object(app, "_ja_refresh_access_token", return_value="fixture-token"):
            response = app.app.test_client().post(
                "/jobadder/spider_search",
                json={
                    "query": "Python",
                    "filters": {"salary_min": 10000, "salary_max": 5000},
                },
                headers=self._request_headers(),
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn("cannot exceed", response.get_json()["error"])

    def test_include_missing_salary_keeps_candidate_after_detail_check(self):
        summaries = [self._summary(1)]
        metadata = {
            "mode": "plain",
            "query": "Python",
            "returned": 1,
            "search": {"reported_total": 1, "warnings": [], "pages": 1},
        }
        detail = {
            "candidateId": 1,
            "summary": "Senior Python AWS software engineer",
        }
        with mock.patch.object(
            app, "_ja_refresh_access_token", return_value="fixture-token"
        ), mock.patch.object(
            app,
            "_spider_plain_keyword_jobadder_candidates",
            return_value=(summaries, metadata),
        ), mock.patch.object(
            app, "_spider_fetch_candidate_detail", return_value=detail
        ) as fetch_detail, mock.patch.object(
            app, "_spider_fetch_candidate_resume_text", return_value=("", "")
        ):
            response = app.app.test_client().post(
                "/jobadder/spider_search",
                json={
                    "query": "Python",
                    "limit": 1,
                    "filters": {
                        "must": "Python",
                        "salary_min": 7000,
                        "salary_max": 9000,
                        "include_missing_salary": True,
                    },
                },
                headers=self._request_headers(),
            )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        payload = response.get_json()
        self.assertEqual([item["candidateId"] for item in payload["items"]], [1])
        self.assertEqual(payload["filter_summary"]["salary_filter_matched"], 1)
        self.assertTrue(payload["filter_summary"]["salary_include_missing"])
        fetch_detail.assert_called_once_with("fixture-token", "1")

    def test_unknown_industry_value_is_rejected(self):
        with mock.patch.object(app, "_ja_refresh_access_token", return_value="fixture-token"):
            response = app.app.test_client().post(
                "/jobadder/spider_search",
                json={
                    "query": "Engineer",
                    "filters": {"role": "Engineer", "industry": "Not a real taxonomy value"},
                },
                headers=self._request_headers(),
            )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["code"], "INVALID_SPIDER_INDUSTRY")


class IndustryReExportTests(unittest.TestCase):
    def test_app_reexports_industry_helpers(self):
        for name in (
            "_spider_industry_filter_spec",
            "_spider_industry_match",
            "_spider_it_skills_match",
            "_spider_qualifications_match",
            "_spider_residential_match",
            "_spider_salary_match",
        ):
            self.assertIs(getattr(app, name), getattr(score, name), name)


if __name__ == "__main__":
    unittest.main()
