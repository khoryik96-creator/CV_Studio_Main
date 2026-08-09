"""Characterization tests for the JobAdder Screening Call payload builders.

Locks the behaviour of the pure builders extracted into ``cvstudio_ja_screening``:
OneNote screening-field cleaning, the strict 1-4 Presentability rating parser,
the standard and browser-SPA answer-array builders, and the candidate-activity
payload variants. These are a verbatim move from the legacy web shell (verified
byte-for-byte against pre-move output across 138 answer-shape/mode combinations),
so every assertion below equally describes the pre-extraction ``app.py`` behaviour.
"""

import unittest

import cvstudio_ja_screening as screening


_FIELDS = {
    "brief_overview": "  Senior   engineer\r\n\r\n\r\nwith   leadership. ",
    "reason_leaving": "Restructuring",
    "looking_for": "",
    "current_salary_breakdown": "RM 10,000 base",
    "expected_salary": "RM 13,000",
    "notice_period": "1 month",
    "leads": "Active (ClientX - Lead, Interview, Y)",
    "remarks": "",
    "red_flags": "None noted",
    "presentability_rating": "3/4",
    "name": "Jane Doe",
}


class CleanFieldValueTests(unittest.TestCase):
    def test_normalises_newlines_tabs_and_trims(self):
        self.assertEqual(screening._onenote_clean_field_value("  a\r\nb\t\tc  "), "a\nb c")

    def test_collapses_three_or_more_blank_lines(self):
        self.assertEqual(screening._onenote_clean_field_value("line1\n\n\n\n\nline2"), "line1\n\nline2")

    def test_strips_control_characters(self):
        self.assertEqual(screening._onenote_clean_field_value("\x00\x07bad\x1fchars"), "bad chars")

    def test_truncates_with_ellipsis_at_max_len(self):
        self.assertEqual(screening._onenote_clean_field_value("z" * 100, max_len=10), "zzzzzzzzzz…")

    def test_none_becomes_empty(self):
        self.assertEqual(screening._onenote_clean_field_value(None), "")


class PresentabilityRatingTests(unittest.TestCase):
    def test_accepted_forms(self):
        cases = {"3": 3, "3/4": 3, "4 out of 4": 4, "rating 2": 2, "score: 1": 1,
                 "presentability 3 - good": 3}
        for text, expected in cases.items():
            self.assertEqual(
                screening._onenote_presentability_rating_int({"presentability_rating": text}),
                expected, text,
            )

    def test_rejected_forms(self):
        for text in ["14", "40", "10/4", "4 years", ""]:
            self.assertIsNone(
                screening._onenote_presentability_rating_int({"presentability_rating": text}), text,
            )


class ScreeningRemarksTests(unittest.TestCase):
    def test_prefers_explicit_remarks_field_over_note(self):
        self.assertEqual(screening._onenote_screening_remarks_value(_FIELDS, "note body"), "None noted")

    def test_falls_back_to_red_flags(self):
        self.assertEqual(screening._onenote_screening_remarks_value({"red_flags": "flag"}, ""), "flag")

    def test_blank_when_no_remarks_fields_even_with_note(self):
        self.assertEqual(screening._onenote_screening_remarks_value({}, "just a note"), "")


class ScreeningCallAnswersTests(unittest.TestCase):
    def test_default_builds_six_text_plus_leads_remarks_plus_presentability(self):
        answers = screening._ja_screening_call_answers(_FIELDS)
        self.assertEqual(len(answers), 9)
        last = answers[-1]
        self.assertEqual(last["questionID"], 62988)
        self.assertEqual(last["ratingValue"], 3)
        self.assertEqual(last["questionText"], "Presentability (Confidence, Comms, Business Awareness)")


class SpaScreeningAnswersTests(unittest.TestCase):
    def test_basic_has_six_text_plus_presentability(self):
        self.assertEqual(len(screening._ja_spa_screening_call_answers(_FIELDS, "note")), 7)

    def test_extended_adds_leads_and_remarks(self):
        self.assertEqual(len(screening._ja_spa_screening_call_answers(_FIELDS, "note", include_extended=True)), 9)

    def test_empty_fields_blank_brief_overview_and_na_elsewhere(self):
        answers = screening._ja_spa_screening_call_answers({"presentability_rating": "rating 4"}, "")
        by_qid = {a["questionID"]: a for a in answers}
        self.assertEqual(by_qid[41172]["textValue"], "")      # brief overview stays blank
        self.assertEqual(by_qid[41173]["textValue"], "N/A")   # others default to N/A
        self.assertEqual(by_qid[62988]["textValue"], "4")
        self.assertEqual(by_qid[62988]["numericValue"], 4)


class SpaScreeningPayloadTests(unittest.TestCase):
    def test_payload_shape(self):
        payload = screening._ja_spa_screening_call_payload("123", _FIELDS, "note", include_extended=True)
        self.assertEqual(payload["activityID"], 0)  # no activity_id supplied
        self.assertEqual(payload["activitySettingID"], 8225)
        self.assertEqual(payload["actionName"], "Candidate Screening Call")
        self.assertEqual(payload["activityType"], "Screening")
        self.assertEqual(payload["entity"], {"entityID": 123})

    def test_activity_id_is_coerced(self):
        payload = screening._ja_spa_screening_call_payload("123", _FIELDS, "note", activity_id="999")
        self.assertEqual(payload["activityID"], 999)


class CandidateScreeningPayloadShapeTests(unittest.TestCase):
    def test_items_shape_wraps_answers_in_items(self):
        payload = screening._ja_candidate_screening_call_payload(
            "123", _FIELDS, "note", reference="ref1", answers_shape="items")
        self.assertIn("items", payload["answers"])
        self.assertEqual(payload["reference"], "ref1")
        self.assertEqual(payload["entityID"], 123)

    def test_array_shape_answers_is_a_bare_list(self):
        payload = screening._ja_candidate_screening_call_payload(
            "123", _FIELDS, "note", answers_shape="array")
        self.assertIsInstance(payload["answers"], list)

    def test_map_full_keys_answers_by_question_id(self):
        payload = screening._ja_candidate_screening_call_payload(
            "123", _FIELDS, "note", answers_shape="map_full")
        self.assertIsInstance(payload["answers"], dict)
        self.assertIn("62988", payload["answers"])

    def test_top_rating_items_exposes_top_level_rating_collections(self):
        payload = screening._ja_candidate_screening_call_payload(
            "123", _FIELDS, "note", answers_shape="top_rating_items",
            presentability_question_id=62988, presentability_mode="rating_full")
        self.assertIn("ratingAnswers", payload)
        self.assertIn("ratingsByQuestionID", payload)

    def test_unknown_shape_defaults_to_items(self):
        payload = screening._ja_candidate_screening_call_payload(
            "123", _FIELDS, "note", answers_shape="totally_unknown")
        self.assertIn("items", payload["answers"])

    def test_activity_id_added_when_supplied(self):
        payload = screening._ja_candidate_screening_call_payload(
            "123", _FIELDS, "note", answers_shape="items", activity_id="7")
        self.assertEqual(payload["activityID"], 7)


class ActivityPayloadVariantsTests(unittest.TestCase):
    def test_browser_and_precise_variant_counts(self):
        self.assertEqual(len(screening._ja_browser_activity_answer_list_payload_variants(
            "123", _FIELDS, "note", "ref1")), 12)
        self.assertEqual(len(screening._ja_precise_qid_activity_payload_variants(
            "123", _FIELDS, "note", "ref1")), 15)

    def test_activity_variants_returns_list_with_base_tail(self):
        variants = screening._ja_activity_payload_variants(
            "123", "Screening", "Candidate Screening Call", "note", _FIELDS, "ref1", "2026-08-09T00:00:00Z")
        self.assertIsInstance(variants, list)
        self.assertEqual(len(variants), 116)
        # tail is [setting_named, with_candidate, base]
        base = variants[-1]
        self.assertEqual(base["subject"], "Candidate Screening Call")
        self.assertIn("items", base["answers"])


class OfficialScreeningActivityPayloadTests(unittest.TestCase):
    def test_official_v2_payload_shape_and_rating(self):
        payload = screening._ja_official_screening_activity_payload(_FIELDS, "note")
        self.assertEqual(payload["activitySettingId"], 8225)
        answers = payload["answers"]
        self.assertEqual(answers["listValueAnswers"], [])
        self.assertEqual(answers["dateRangeValueAnswers"], [])
        self.assertEqual(answers["ratingValueAnswers"], [{"questionId": 62988, "rating": 3}])
        # Optional text fields: blank ones (looking_for/remarks) are omitted, not N/A-filled.
        keys = {a["questionId"] for a in answers["textAnswers"]}
        self.assertIn(41172, keys)          # brief_overview present
        self.assertNotIn(41174, keys)       # looking_for is blank -> omitted

    def test_minimal_fields_keeps_only_rating(self):
        payload = screening._ja_official_screening_activity_payload({"presentability_rating": "4"}, "")
        self.assertEqual(payload["answers"]["textAnswers"], [])
        self.assertEqual(payload["answers"]["ratingValueAnswers"], [{"questionId": 62988, "rating": 4}])

    def test_rating_out_of_range_raises(self):
        with self.assertRaises(ValueError):
            screening._ja_official_screening_activity_payload({"presentability_rating": "9"}, "")
        with self.assertRaises(ValueError):
            screening._ja_official_screening_activity_payload({}, "")


class SpaBrowserBridgeTests(unittest.TestCase):
    """The create-only SPA browser helper depends on one injected app-state helper
    (the JobAdder candidate Activity URL builder); everything else is in-module or
    imported. Bind a fake URL builder and pass an explicit salary_canonical so the
    generator runs without app or bound salary-AI dependencies."""

    def setUp(self):
        self._saved = screening._jobadder_candidate_activity_url
        screening.bind_screening_dependencies(
            jobadder_candidate_activity_url=lambda cid: "https://app.jobadder.com/candidates/{}?tab=2&activityView=Activity".format(cid),
        )

    def tearDown(self):
        screening._jobadder_candidate_activity_url = self._saved

    def test_bridge_report_shape_and_embedded_version(self):
        report = screening._ja_spa_browser_bridge(
            "41262878", _FIELDS, "the note", email="x@y.com",
            salary_canonical={"current": {"display": "RM 10,000"}}, spelling_correction=True,
        )
        self.assertEqual(report["candidate_id"], "41262878")
        self.assertEqual(report["email"], "x@y.com")
        self.assertEqual(report["profile_url"], "https://app.jobadder.com/candidates/41262878?tab=2&activityView=Activity")
        self.assertIn("/standardactivity", report["endpoint"])
        # create-only: the generated helper posts to standardactivity and never edits
        self.assertIn("activities/standardactivity", report["script"])
        self.assertIn("CREATE-ONLY", report["method"])
        # the embedded helper version literal is the managed one (bump_version anchor)
        import bump_version
        self.assertIn(
            "const helperVersion = '{}'".format(bump_version.dotted(bump_version.read_version())),
            report["script"],
        )

    def test_bridge_requires_binding(self):
        screening._jobadder_candidate_activity_url = None
        with self.assertRaises(TypeError):
            screening._ja_spa_browser_bridge("1", _FIELDS, "n", salary_canonical={})


if __name__ == "__main__":
    unittest.main()
