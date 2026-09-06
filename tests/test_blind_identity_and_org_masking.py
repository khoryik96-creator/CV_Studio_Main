"""Regression tests for blind-CV identity scrubbing and organisation masking.

Two defects motivated these tests.

* The organisation sweep matched curated names case-insensitively, so ordinary
  CV vocabulary was rewritten into ``[Company]``: "shell scripting",
  "boost revenue", "metadata", "boosted" and "yesterday" all lost text.
* The deterministic sweep only ever protected ``summary_bullets``. A candidate's
  name, email, phone and personal links survived anywhere else in the blinded
  document and reached the client in the exported blind CV.
"""

import inspect
import json
import os
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent))
import tempfile
import unittest
from unittest import mock

import cvstudio_blind_mask as bm

_MODULE_TEMPORARY = tempfile.TemporaryDirectory(prefix="cvstudio-blind-identity-")
_ORIGINAL_DATABASE_OVERRIDE = os.environ.get("CVSTUDIO_DB_PATH")
os.environ["CVSTUDIO_DB_PATH"] = str(
    Path(_MODULE_TEMPORARY.name) / "state" / "cv_studio.sqlite3"
)
from owner_build_tools.build_protected import write_test_receipt

write_test_receipt(Path(__file__).resolve().parents[1])
try:
    import app
finally:
    if _ORIGINAL_DATABASE_OVERRIDE is None:
        os.environ.pop("CVSTUDIO_DB_PATH", None)
    else:
        os.environ["CVSTUDIO_DB_PATH"] = _ORIGINAL_DATABASE_OVERRIDE


class OrganisationMaskCaseTests(unittest.TestCase):
    """Curated names that are also everyday words must not eat ordinary prose."""

    def test_lowercase_common_words_survive_the_org_sweep(self):
        text = (
            "Automated ETL with shell scripting, worked to boost revenue, "
            "helped grab market share, built the metadata catalog, boosted "
            "margins and yesterday shipped the release."
        )
        out = bm._blind_replace_org_terms_in_text(
            text, ["Shell", "Boost", "Grab", "Meta", "Yes", "MISC"]
        )
        self.assertEqual(out, text)

    def test_capitalised_employer_is_still_masked(self):
        out = bm._blind_replace_org_terms_in_text(
            "Shell was the employer; ran shell scripting daily.", ["Shell"]
        )
        self.assertEqual(
            out, "[Company] was the employer; ran shell scripting daily."
        )

    def test_product_brand_prefix_is_still_masked(self):
        out = bm._blind_replace_org_terms_in_text(
            "Launched GrabFood and Maybank2u.", ["Grab", "Maybank"]
        )
        self.assertNotIn("GrabFood", out)
        self.assertNotIn("Maybank2u", out)
        self.assertIn("[Company]Food", out)
        self.assertIn("[Company]2u", out)

    def test_inflected_forms_keep_their_first_syllable(self):
        # ``re.I`` used to let the product-prefix lookahead match a lowercase
        # letter, turning "metadata" into "[Company]data".
        for term, text in (
            ("Boost", "Boosted revenue by 30%."),
            ("Grab", "Grabbing market share early."),
            ("Meta", "Metadata lineage was rebuilt."),
            ("Yes", "Yesterday the pipeline ran clean."),
            ("Shell", "Shelling out weekly reports."),
        ):
            with self.subTest(term=term):
                self.assertEqual(bm._blind_replace_org_terms_in_text(text, [term]), text)

    def test_all_caps_word_is_not_treated_as_a_brand_prefix(self):
        out = bm._blind_replace_org_terms_in_text("GRABBING THE LEAD EARLY", ["Grab"])
        self.assertEqual(out, "GRABBING THE LEAD EARLY")

    def test_multi_word_org_still_masks_case_insensitively(self):
        out = bm._blind_replace_org_terms_in_text(
            "Delivered for hong leong bank last year.", ["Hong Leong Bank"]
        )
        self.assertIn("[Company]", out)


class CuratedTermCollectionTests(unittest.TestCase):
    def test_lowercase_only_mention_does_not_register_a_curated_name(self):
        terms = bm._blind_collect_org_mask_terms(
            {
                "work_experiences": [
                    {
                        "company": "Acme Widgets",
                        "bullets": ["shell scripting and boost revenue"],
                    }
                ]
            }
        )
        self.assertNotIn("Shell", terms)
        self.assertNotIn("Boost", terms)
        self.assertIn("Acme Widgets", terms)

    def test_capitalised_mention_registers_the_curated_name(self):
        terms = bm._blind_collect_org_mask_terms(
            {"work_experiences": [{"company": "Shell", "bullets": ["ran shell jobs"]}]}
        )
        self.assertIn("Shell", terms)


class CandidateIdentitySweepTests(unittest.TestCase):
    """The candidate's own identity must not depend on the model alone."""

    @staticmethod
    def _original(name="Vinay Lariya"):
        return {
            "candidate": {
                "name": name,
                "email": "vinay.lariya@gmail.com",
                "phone": "+60123456789",
                "linkedin": "https://linkedin.com/in/vinaylariya",
            }
        }

    def test_direct_identity_is_removed_from_every_field(self):
        blinded = {
            "candidate": {"name": "Candidate"},
            "work_experiences": [
                {
                    "roles": [
                        {
                            "bullets": [
                                "Vinay Lariya led the Kafka migration.",
                                "Reachable at vinay.lariya@gmail.com or +60123456789.",
                                "Profile: https://linkedin.com/in/vinaylariya",
                            ]
                        }
                    ]
                }
            ],
            "additional_information": ["Referee contact: vinay.lariya@gmail.com"],
        }
        out = bm._blind_scrub_candidate_identity(blinded, self._original())
        blob = json.dumps(out)
        self.assertNotIn("Vinay", blob)
        self.assertNotIn("Lariya", blob)
        self.assertNotIn("vinay.lariya@gmail.com", blob)
        self.assertNotIn("60123456789", blob)
        self.assertNotIn("linkedin.com/in/vinaylariya", blob)
        self.assertIn("[Email Redacted]", blob)
        self.assertIn("Kafka", blob)

    def test_first_name_alone_is_removed(self):
        out = bm._blind_scrub_candidate_identity(
            {"summary_bullets": ["Vinay is a data engineer."]}, self._original()
        )
        self.assertEqual(out["summary_bullets"], ["The candidate is a data engineer."])

    def test_generic_label_is_capitalised_at_a_sentence_start(self):
        out = bm._blind_scrub_candidate_identity(
            {"bullets": ["Vinay Lariya led delivery. Vinay Lariya then scaled it."]},
            self._original(),
        )
        self.assertEqual(
            out["bullets"], ["The candidate led delivery. The candidate then scaled it."]
        )

    def test_label_is_not_capitalised_mid_sentence(self):
        out = bm._blind_scrub_candidate_identity(
            {"bullets": ["Kafka migration: Vinay led the rollout."]}, self._original()
        )
        self.assertEqual(
            out["bullets"], ["Kafka migration: the candidate led the rollout."]
        )

    def test_multi_word_name_run_is_replaced_as_one_name(self):
        out = bm._blind_scrub_candidate_identity(
            {"bullets": ["Wei Ming shipped the release."]},
            self._original("Tan Wei Ming"),
        )
        # Sweeping "Ming" on its own would leave the fragment "Wei the candidate".
        self.assertEqual(out["bullets"], ["The candidate shipped the release."])

    def test_common_word_names_are_left_to_the_prompt(self):
        text = "Will deliver the migration; the grace period was extended."
        out = bm._blind_scrub_candidate_identity(
            {"bullets": [text]}, self._original("Will Grace")
        )
        self.assertEqual(out["bullets"], [text])

    def test_short_surnames_are_not_swept(self):
        text = "Tan led delivery for Tan Chong Motor."
        out = bm._blind_scrub_candidate_identity(
            {"bullets": [text]}, self._original("Tan Wei Ming")
        )
        self.assertEqual(out["bullets"], [text])

    def test_header_name_is_normalised_when_the_model_left_it(self):
        out = bm._blind_scrub_candidate_identity(
            {"candidate": {"name": "Vinay Lariya"}}, self._original()
        )
        self.assertEqual(out["candidate"]["name"], "Candidate")

    def test_no_candidate_details_is_a_noop(self):
        payload = {"bullets": ["Nothing to scrub."]}
        self.assertEqual(bm._blind_scrub_candidate_identity(payload, {}), payload)


class PhoneRedactionTests(unittest.TestCase):
    def test_decimal_measurement_is_not_a_phone_number(self):
        text = "Handled 99.999999 percent uptime across the cluster."
        self.assertEqual(bm._blind_redact_phone_candidates(text), text)

    def test_real_phone_numbers_are_still_redacted(self):
        for text in ("Contact: +60 12-345 6789", "Call 03-2345 6789 for details"):
            with self.subTest(text=text):
                self.assertIn(
                    "[Phone Redacted]", bm._blind_redact_phone_candidates(text)
                )


class BlindRouteIdentityTests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()

    def test_blind_route_scrubs_identity_the_model_left_in_a_bullet(self):
        parsed = {
            "candidate": {
                "name": "Fixture Candidate",
                "email": "fixture@example.com",
                "phone": "+60123456789",
            },
            "work_experiences": [
                {
                    "company": "Fixture Company",
                    "roles": [
                        {"bullets": ["Fixture Candidate delivered the platform."]}
                    ],
                }
            ],
        }
        # A provider that masked the employer but left the candidate in the bullet.
        provider = json.loads(json.dumps(parsed))
        provider["candidate"] = {
            "name": "Candidate",
            "email": "[Email Redacted]",
            "phone": "[Phone Redacted]",
        }
        provider["work_experiences"][0]["company"] = "[Company]"

        with mock.patch.object(
            app, "_resolve_request_api_key", return_value="<fixture-credential>"
        ), mock.patch.object(
            app,
            "call_llm",
            return_value={
                "content": [{"type": "text", "text": json.dumps(provider)}],
                "usage": {},
            },
        ), mock.patch.object(
            app, "_ai_spend_session_allowed", return_value=True
        ):
            response = self.client.post(
                "/blind",
                json={"cv_data": parsed, "provider": "anthropic"},
                headers={
                    "X-CV-Studio-Request": "1",
                    "X-CV-Studio-Request-ID": "blind-identity-sweep",
                },
            )

        self.assertEqual(response.status_code, 200)
        blob = json.dumps(response.get_json()["data"])
        self.assertNotIn("Fixture Candidate", blob)
        self.assertIn("the candidate", blob.lower())


class SpendAndConcurrencyGuardTests(unittest.TestCase):
    def test_ai_request_ceiling_is_enabled_by_default(self):
        from cvstudio_ai_costs import guardrail_configuration

        config = guardrail_configuration()
        self.assertTrue(config["enabled"])
        self.assertEqual(config["limit_usd"], 10.0)

    def test_one_shot_activity_diagnostic_claims_its_slot_under_a_lock(self):
        import threading

        self.assertIsInstance(
            app._JA_ACTIVITY_CREATE_DIAG_LOCK, type(threading.Lock())
        )
        source = inspect.getsource(app.jobadder_onenote_activity_create_diagnostic)
        claim = source.index("_JA_ACTIVITY_CREATE_DIAG_LOCK")
        check = source.index("guard_key in _JA_ACTIVITY_CREATE_DIAG_USED")
        add = source.index("_JA_ACTIVITY_CREATE_DIAG_USED.add")
        # The membership test and the add must both sit inside the lock, or two
        # concurrent server threads can each emit the one-shot POST.
        self.assertLess(claim, check)
        self.assertLess(check, add)


if __name__ == "__main__":
    unittest.main()
