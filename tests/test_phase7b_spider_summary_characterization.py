"""Characterization tests for the Spider candidate data-shaping helpers.

Locks the behaviour of the pure helpers extracted into
``cvstudio_spider_summary`` (Phase 7B): numeric coercion, salary/notice/card
snapshots, JobAdder custom-field lookup, record-identity keys, and the
summary/detail deep-merge. These are a verbatim move from the legacy web shell,
so every assertion below equally describes the pre-extraction ``app.py``
behaviour. The expected values were captured from the original ``app._spider_*``
functions before the move.
"""

import unittest

import cvstudio_spider_summary as summary


class NumberTests(unittest.TestCase):
    def test_parses_currency_formatted_text(self):
        self.assertEqual(summary._spider_number("RM 12,500.50"), 12500.5)

    def test_none_and_unparseable_return_none(self):
        self.assertIsNone(summary._spider_number(None))
        self.assertIsNone(summary._spider_number("abc"))


class SalarySnapshotTests(unittest.TestCase):
    def test_single_rate_snapshot(self):
        self.assertEqual(
            summary._spider_salary_snapshot(
                {"currency": "myr", "ratePer": "Month", "rate": 8000}, False
            ),
            {"display": "MYR 8,000 / Month", "sort": 8000.0, "currency": "MYR", "ratePer": "Month"},
        )

    def test_range_snapshot_uses_yearly_to_monthly_factor(self):
        self.assertEqual(
            summary._spider_salary_snapshot(
                {"currencyCode": "SGD", "period": "year", "rateLow": 90000, "rateHigh": 120000}, True
            ),
            {"display": "SGD 90,000 to 120,000 / year", "sort": 7500.0, "currency": "SGD", "ratePer": "year"},
        )

    def test_non_dict_returns_none(self):
        self.assertIsNone(summary._spider_salary_snapshot("x", False))


class CustomFieldValueTests(unittest.TestCase):
    def setUp(self):
        self.candidate = {
            "custom": [
                {"name": "Notice Period", "value": "1 month"},
                {"label": "Other", "value": "z"},
            ]
        }

    def test_alias_match_returns_value(self):
        self.assertEqual(
            summary._spider_custom_field_value(self.candidate, ["notice period", "notice"]), "1 month"
        )

    def test_no_alias_match_returns_none(self):
        self.assertIsNone(summary._spider_custom_field_value(self.candidate, ["salary"]))


class NoticeSnapshotTests(unittest.TestCase):
    def test_immediate_availability(self):
        self.assertEqual(
            summary._spider_notice_snapshot({"availability": {"immediate": True}}),
            {"display": "Immediate", "sort": 0},
        )

    def test_relative_period_in_months(self):
        self.assertEqual(
            summary._spider_notice_snapshot({"availability": {"relative": {"period": 2, "unit": "months"}}}),
            {"display": "2 months", "sort": 60.0},
        )

    def test_custom_field_fallback(self):
        self.assertEqual(
            summary._spider_notice_snapshot({"custom": [{"name": "notice", "value": "2 weeks"}]}),
            {"display": "2 weeks", "sort": 14.0},
        )

    def test_empty_returns_none(self):
        self.assertIsNone(summary._spider_notice_snapshot({}))


class CardFieldsTests(unittest.TestCase):
    def test_full_card_projection(self):
        candidate = {
            "employment": {
                "current": {"salary": {"currency": "MYR", "ratePer": "month", "rate": 8000}},
                "ideal": {"salary": {"currency": "MYR", "ratePer": "month", "rateLow": 10000, "rateHigh": 12000}},
            },
            "availability": {"immediate": True},
        }
        self.assertEqual(
            summary._spider_card_fields(candidate),
            {
                "currentSalary": {"display": "MYR 8,000 / month", "sort": 8000.0, "currency": "MYR", "ratePer": "month"},
                "expectedSalary": {"display": "MYR 10,000 to 12,000 / month", "sort": 10000.0, "currency": "MYR", "ratePer": "month"},
                "notice": {"display": "Immediate", "sort": 0},
            },
        )


class RecordKeyTests(unittest.TestCase):
    def test_custom_record_key_prefers_field_id(self):
        self.assertEqual(summary._spider_custom_record_key({"fieldId": "F1", "name": "X"}), "id:f1")

    def test_work_record_key_normalizes_work_type_name(self):
        self.assertEqual(
            summary._spider_work_record_key({"workType": {"name": "Permanent Role"}}), "work:permanentrole"
        )


class MergeTests(unittest.TestCase):
    def test_merge_record_lists_fills_missing_by_identity(self):
        primary = [{"id": "1", "value": "a"}]
        secondary = [{"id": "1", "extra": "b"}, {"id": "2", "value": "c"}]
        self.assertEqual(
            summary._spider_merge_record_lists(primary, secondary, summary._spider_custom_record_key),
            [{"id": "1", "value": "a", "extra": "b"}, {"id": "2", "value": "c"}],
        )

    def test_merge_missing_json_keeps_primary_and_fills_blanks(self):
        self.assertEqual(
            summary._spider_merge_missing_json({"a": 1, "b": ""}, {"b": 2, "c": 3}),
            {"a": 1, "b": 2, "c": 3},
        )

    def test_merge_candidate_summary_and_detail(self):
        result = summary._spider_merge_candidate_summary_and_detail(
            {"name": "Ada", "custom": [{"fieldId": "F1", "value": "keep"}]},
            {"email": "a@x.com", "custom": [{"fieldId": "F1", "value": "new"}, {"fieldId": "F2", "value": "add"}]},
        )
        self.assertEqual(result["name"], "Ada")
        self.assertEqual(result["email"], "a@x.com")
        # Summary custom values stay authoritative; detail-only records are added.
        self.assertEqual(
            result["custom"],
            [{"fieldId": "F1", "value": "keep"}, {"fieldId": "F2", "value": "add"}],
        )
        # A private scoring copy of the raw detail is retained.
        self.assertEqual(result["_spiderDetail"]["email"], "a@x.com")


class ReExportTests(unittest.TestCase):
    def test_app_reexports_are_the_module_objects(self):
        import app  # noqa: PLC0415 - importing the shell is the point of this check

        for name in (
            "_spider_number",
            "_spider_salary_snapshot",
            "_spider_custom_field_value",
            "_spider_notice_snapshot",
            "_spider_card_fields",
            "_spider_custom_record_key",
            "_spider_work_record_key",
            "_spider_merge_record_lists",
            "_spider_merge_missing_json",
            "_spider_merge_candidate_summary_and_detail",
        ):
            self.assertIs(getattr(app, name), getattr(summary, name), name)


if __name__ == "__main__":
    unittest.main()
