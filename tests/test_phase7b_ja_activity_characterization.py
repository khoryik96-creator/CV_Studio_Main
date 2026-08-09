"""Characterization tests for the JobAdder activity diagnostic/result helpers.

Locks the behaviour of the pure helpers extracted into ``cvstudio_ja_activity``:
response-header redaction, network-error labelling, the conservative read
diagnostic summary, and the activity-id parsers for list and post results.
These are a verbatim move from the legacy web shell, so every assertion below
equally describes the pre-extraction ``app.py`` behaviour. The expected values
were captured from the original ``app._ja_activity_*`` functions before the move.
"""

import unittest

import cvstudio_ja_activity as activity
from cvstudio_clients import ExternalServiceError


class DiagnosticResponseHeadersTests(unittest.TestCase):
    def test_keeps_useful_headers_and_drops_auth_and_cookies(self):
        headers = {
            "Content-Type": "application/json",
            "X-Request-Id": "abc",
            "Set-Cookie": "session=1",
            "Set-Cookie2": "legacy=1",
            "Authorization": "Bearer secret",
            "Proxy-Authorization": "Basic zzz",
        }
        self.assertEqual(
            activity._ja_activity_diagnostic_response_headers(headers),
            {"Content-Type": "application/json", "X-Request-Id": "abc"},
        )

    def test_header_exclusion_is_case_insensitive(self):
        headers = {"set-COOKIE": "x", "AUTHORIZATION": "y", "Accept": "application/json"}
        self.assertEqual(
            activity._ja_activity_diagnostic_response_headers(headers),
            {"Accept": "application/json"},
        )

    def test_non_mapping_returns_empty_dict(self):
        self.assertEqual(activity._ja_activity_diagnostic_response_headers(None), {})
        self.assertEqual(activity._ja_activity_diagnostic_response_headers(42), {})


class DiagnosticNetworkErrorTests(unittest.TestCase):
    def test_external_service_error_uses_safe_detail(self):
        err = ExternalServiceError("jobadder", "boom message", detail="safe detail here")
        self.assertEqual(
            activity._ja_activity_diagnostic_network_error(err),
            str(err.safe_detail or err),
        )

    def test_plain_exception_falls_back_to_reason_then_str(self):
        class _WithReason(Exception):
            reason = "connection timed out"

        self.assertEqual(
            activity._ja_activity_diagnostic_network_error(_WithReason()),
            "connection timed out",
        )
        self.assertEqual(
            activity._ja_activity_diagnostic_network_error(ValueError("plain text")),
            "plain text",
        )


class DiagnosticSummaryTests(unittest.TestCase):
    def test_any_success_status_reports_success(self):
        summary = activity._ja_activity_diagnostic_summary([{"status": 201}, {"status": 404}])
        self.assertIn("At least one OAuth activity GET succeeded", summary)

    def test_two_not_found_or_method_not_allowed_reports_unavailable(self):
        summary = activity._ja_activity_diagnostic_summary([{"status": 404}, {"status": 405}])
        self.assertIn("Both OAuth activity GET routes returned 404/405", summary)

    def test_unauthorised_status_reports_reconnect(self):
        summary = activity._ja_activity_diagnostic_summary([{"status": 401}, {"status": 404}])
        self.assertIn("unauthorised", summary)

    def test_mixed_or_empty_returns_default_review_message(self):
        default = activity._ja_activity_diagnostic_summary([{"status": 500}])
        self.assertIn("did not expose a successful activity model", default)
        self.assertIn("did not expose a successful activity model",
                      activity._ja_activity_diagnostic_summary([]))


class ActivityIdsFromListResultTests(unittest.TestCase):
    def test_collects_activity_ids_across_id_spellings(self):
        result = {"response_json": {"items": [
            {"activityId": 5},
            {"activityID": "7"},
            {"other": 1},
            "not-a-dict",
        ]}}
        self.assertEqual(activity._ja_activity_ids_from_list_result(result), [5, 7])

    def test_missing_or_non_list_items_returns_empty(self):
        self.assertEqual(activity._ja_activity_ids_from_list_result({"response_json": {"items": "x"}}), [])
        self.assertEqual(activity._ja_activity_ids_from_list_result({}), [])
        self.assertEqual(activity._ja_activity_ids_from_list_result(None), [])


class ActivityIdFromPostResultTests(unittest.TestCase):
    def test_top_level_id(self):
        self.assertEqual(activity._ja_activity_id_from_post_result({"response_json": {"activityId": 9}}), 9)
        self.assertEqual(activity._ja_activity_id_from_post_result({"response_json": {"activityID": "11"}}), 11)

    def test_nested_container_id(self):
        self.assertEqual(
            activity._ja_activity_id_from_post_result({"response_json": {"activity": {"activityId": 13}}}),
            13,
        )

    def test_location_header_id(self):
        self.assertEqual(
            activity._ja_activity_id_from_post_result(
                {"response_headers": {"Location": "https://api.example/candidates/1/activities/21"}}
            ),
            21,
        )
        self.assertEqual(
            activity._ja_activity_id_from_post_result(
                {"response_headers": {"Location": "https://api.example/activities/21?trace=1"}}
            ),
            21,
        )

    def test_no_id_returns_none(self):
        self.assertIsNone(activity._ja_activity_id_from_post_result({}))
        self.assertIsNone(activity._ja_activity_id_from_post_result(
            {"response_headers": {"Location": "https://api.example/candidates/1"}}
        ))


if __name__ == "__main__":
    unittest.main()
