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
        ):
            self.assertIs(getattr(app, name), getattr(score, name), name)


if __name__ == "__main__":
    unittest.main()
