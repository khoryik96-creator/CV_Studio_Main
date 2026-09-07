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
from cvstudio_ai_costs import AICostGuardrailError

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
        from cvstudio_ai_costs import (
            AI_COST_DEFAULT_REQUEST_CEILING_USD,
            AI_COST_GUARDRAIL_ENV,
            guardrail_configuration,
        )

        # Pass the mapping explicitly: another test module pops this variable out of
        # os.environ permanently, so reading the live process environment here would
        # make the result depend on test order.
        config = guardrail_configuration(environ={})
        self.assertTrue(config["enabled"])
        self.assertEqual(
            config["limit_usd"], float(AI_COST_DEFAULT_REQUEST_CEILING_USD)
        )
        off = guardrail_configuration(environ={AI_COST_GUARDRAIL_ENV: "off"})
        self.assertFalse(off["enabled"])

    def test_default_ceiling_clears_the_priciest_legitimate_request(self):
        from cvstudio_ai_costs import enforce_request_guardrail

        # 64k output tokens on a "pro" model, and on any unrecognised model id, price
        # at the provider ceiling. A 500KB CV must still go through; 5MB must not.
        def payload(model, chars):
            return {
                "model": model,
                "max_tokens": 64000,
                "messages": [{"role": "user", "content": "x" * chars}],
            }

        for model in ("gpt-5.5-pro", "gpt-9-not-in-the-price-table"):
            with self.subTest(model=model):
                allowed = enforce_request_guardrail(
                    "openai", payload(model, 500_000), environ={}
                )
                self.assertEqual(allowed["status"], "allowed")
                with self.assertRaises(AICostGuardrailError):
                    enforce_request_guardrail(
                        "openai", payload(model, 5_000_000), environ={}
                    )

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


class ReviewRegressionTests(unittest.TestCase):
    """Cases a review of the first attempt at these fixes found."""

    @staticmethod
    def _original(name="Vinay Lariya", **extra):
        candidate = {"name": name}
        candidate.update(extra)
        return {"candidate": candidate}

    def test_real_employer_is_masked_whatever_its_casing(self):
        # The first fix spared every lowercase single-token match, which also spared
        # genuine employers written in lowercase.
        for text, terms, expected in (
            ("Worked at petronas on upstream data.", ["Petronas"], "[Company]"),
            ("Senior engineer at iflix", ["iflix"], "[Company]"),
        ):
            with self.subTest(text=text):
                self.assertIn(expected, bm._blind_replace_org_terms_in_text(text, terms))

    def test_brand_compound_in_capitals_is_still_masked(self):
        self.assertEqual(
            bm._blind_replace_org_terms_in_text("LED THE MAXISONE LAUNCH", ["Maxis"]),
            "LED THE [Company]ONE LAUNCH",
        )

    def test_all_caps_prose_does_not_register_an_ambiguous_name(self):
        terms = bm._blind_collect_org_mask_terms(
            {
                "work_experiences": [
                    {
                        "company": "Acme Widgets",
                        "bullets": ["BOOSTED REVENUE", "METADATA CATALOG", "YESTERDAY SHIPPED"],
                    }
                ]
            }
        )
        self.assertEqual(terms, ["Acme Widgets"])

    def test_name_in_capitals_is_scrubbed(self):
        out = bm._blind_scrub_candidate_identity(
            {"b": ["VINAY LED THE MIGRATION"]}, self._original()
        )
        self.assertNotIn("VINAY", out["b"][0])

    def test_name_beside_an_underscore_is_scrubbed(self):
        out = bm._blind_scrub_candidate_identity(
            {"b": ["Vinay led it. Owner_Vinay signed off."]}, self._original()
        )
        self.assertNotIn("Vinay", out["b"][0])

    def test_whole_snake_case_identifier_is_replaced_once(self):
        out = bm._blind_scrub_candidate_identity(
            {"b": ["Rebuilt the vinay_lariya_pipeline DAG."]}, self._original()
        )
        self.assertEqual(out["b"], ["Rebuilt the candidate DAG."])

    def test_unrelated_snake_case_tables_are_untouched(self):
        text = "Owns cust_order_fact and dim_date tables."
        out = bm._blind_scrub_candidate_identity({"b": [text]}, self._original())
        self.assertEqual(out["b"], [text])

    def test_phone_is_scrubbed_however_it_is_punctuated(self):
        original = self._original(phone="+60123456789")
        for text in (
            "Reach him on +60 12-345 6789 anytime.",
            "Mobile 012-345 6789 today.",
            "Direct line 0123456789.",
        ):
            with self.subTest(text=text):
                out = bm._blind_scrub_candidate_identity({"b": [text]}, original)
                self.assertIn("[Phone Redacted]", out["b"][0])

    def test_metric_sharing_a_digit_tail_is_not_a_phone_number(self):
        original = self._original(phone="+60123456789")
        for text in (
            "Processed 123456789 records nightly.",
            "Cut cost from 1,250,000 to 900,000.",
        ):
            with self.subTest(text=text):
                out = bm._blind_scrub_candidate_identity({"b": [text]}, original)
                self.assertEqual(out["b"], [text])

    def test_link_is_scrubbed_with_or_without_its_scheme(self):
        original = self._original(linkedin="https://linkedin.com/in/vinaylariya")
        for text in (
            "See https://linkedin.com/in/vinaylariya",
            "Profile at linkedin.com/in/vinaylariya",
            "Profile at www.linkedin.com/in/vinaylariya",
        ):
            with self.subTest(text=text):
                out = bm._blind_scrub_candidate_identity({"b": [text]}, original)
                self.assertNotIn("vinaylariya", out["b"][0])
                self.assertIn("[Link Redacted]", out["b"][0])

    def test_technology_that_is_also_a_given_name_survives(self):
        out = bm._blind_scrub_candidate_identity(
            {"skills": ["Ruby on Rails", "Java", "Kafka"]}, self._original("Ruby Tan")
        )
        self.assertEqual(out["skills"], ["Ruby on Rails", "Java", "Kafka"])

    def test_lineage_particle_is_not_swept_on_its_own(self):
        text = "Coordinated with Siti binti Rahman on payroll."
        out = bm._blind_scrub_candidate_identity(
            {"b": [text]}, self._original("Nur Aisyah binti Abdullah")
        )
        self.assertEqual(out["b"], [text])

    def test_bullet_marker_still_opens_with_a_capital(self):
        out = bm._blind_scrub_candidate_identity(
            {"b": ["- Vinay Lariya led it."]}, self._original()
        )
        self.assertEqual(out["b"], ["- The candidate led it."])

    def test_markdown_split_name_is_replaced_as_one_name(self):
        out = bm._blind_scrub_candidate_identity(
            {"b": ["**Vinay** Lariya owned it."]}, self._original()
        )
        self.assertEqual(out["b"], ["The candidate owned it."])

    def test_generic_label_is_never_swept_as_a_name(self):
        # "Fixture Candidate" must not make the sweep rewrite its own placeholder.
        out = bm._blind_scrub_candidate_identity(
            {"b": ["the candidate led delivery."]}, self._original("Fixture Candidate")
        )
        self.assertEqual(out["b"], ["The candidate led delivery."])

    def test_header_label_keeps_surrounding_text(self):
        for name, expected in (
            ("Vinay Lariya | Data Engineer", "Candidate | Data Engineer"),
            ("[Vinay Lariya]", "[Candidate]"),
            ("Vinay Lariya", "Candidate"),
        ):
            with self.subTest(name=name):
                out = bm._blind_scrub_candidate_identity(
                    {"candidate": {"name": name}}, self._original()
                )
                self.assertEqual(out["candidate"]["name"], expected)

    def test_blind_jd_exports_are_named_hyppies(self):
        source = (
            Path(__file__).resolve().parents[1] / "vendor" / "cvstudio" / "blind-jd.js"
        ).read_text(encoding="utf-8")
        self.assertNotIn("'blind-jd-'", source)
        self.assertEqual(source.count("'hyppies-jd-'"), 2)

    def test_stale_server_action_error_asks_for_a_restart(self):
        source = (
            Path(__file__).resolve().parents[1] / "vendor" / "cvstudio" / "settings.js"
        ).read_text(encoding="utf-8")
        self.assertIn("DOWNLOAD_FOLDER_ACTION_INVALID", source)
        self.assertIn("still running the previous version", source)


class SecondReviewRegressionTests(unittest.TestCase):
    """Cases a second review of these fixes found."""

    @staticmethod
    def _cv(name, **extra):
        candidate = {"name": name}
        candidate.update(extra)
        return {"candidate": candidate}

    def _scrub(self, text, name, **extra):
        return bm._blind_scrub_candidate_identity(
            {"b": [text]}, self._cv(name, **extra)
        )["b"][0]

    def test_bare_name_does_not_rewrite_lowercase_prose(self):
        # A name word only counts when it is capitalised: prose uses the common word
        # in lower case.
        for name, text in (
            ("Long Wei Ming", "Delivered long-term roadmap."),
            ("Adam Sharp", "Drove a sharp reduction in cost."),
            ("Sarah Church", "Served the local church."),
            ("Rose Tan", "Revenue rose from 12% to 40%."),
        ):
            with self.subTest(name=name):
                self.assertEqual(self._scrub(text, name), text)

    def test_bare_name_inside_a_larger_proper_noun_survives(self):
        # "Shah Alam" is a city and "Vinay Kumar" is a different person.
        self.assertEqual(
            self._scrub("Based in Shah Alam.", "Muhammad Alam"), "Based in Shah Alam."
        )
        self.assertEqual(
            self._scrub("Worked with Vinay Kumar too.", "Vinay Lariya"),
            "Worked with Vinay Kumar too.",
        )

    def test_bare_name_standing_alone_is_still_scrubbed(self):
        self.assertEqual(
            self._scrub("Vinay led the migration.", "Vinay Lariya"),
            "The candidate led the migration.",
        )
        self.assertEqual(
            self._scrub("Worked with Vinay on it.", "Vinay Lariya"),
            "Worked with the candidate on it.",
        )

    def test_all_caps_line_still_loses_the_name(self):
        # On an ALL-CAPS line every word is capitalised, so a capitalised neighbour is
        # not evidence of a larger proper noun.
        self.assertEqual(
            self._scrub("VINAY LED THE MIGRATION", "Vinay Lariya"),
            "The candidate LED THE MIGRATION",
        )

    def test_name_that_is_a_substring_of_the_label_is_still_scrubbed(self):
        # "andi" is a substring of "the candidate"; the self-reference guard must be a
        # whole-word test or this candidate is never masked at all.
        self.assertEqual(
            self._scrub("Andi led the migration.", "Andi"),
            "The candidate led the migration.",
        )

    def test_mononym_is_scrubbed_in_any_casing(self):
        self.assertEqual(
            self._scrub("SUHARTO delivered it. Suharto led the team.", "Suharto"),
            "The candidate delivered it. The candidate led the team.",
        )

    def test_multi_word_run_never_starts_or_ends_on_a_particle(self):
        # "van der" and "binti Rahman" are shared by whole families.
        self.assertEqual(
            self._scrub(
                "Marieke van der Meer shipped it; van der Waals forces apply.",
                "Marieke van der Meer",
            ),
            "The candidate shipped it; van der Waals forces apply.",
        )
        self.assertEqual(
            self._scrub(
                "Coordinated with Siti binti Rahman on payroll.",
                "Nur Aisyah binti Rahman",
            ),
            "Coordinated with Siti binti Rahman on payroll.",
        )

    def test_employer_named_like_an_everyday_word_is_always_masked(self):
        # Provenance, not the word itself, decides. A company the candidate worked for
        # must be masked however it is written.
        cv = {
            "work_experiences": [
                {"company": "Grab", "bullets": ["see grab.com and worked at grab"]}
            ]
        }
        out = bm._blind_postprocess_company_mentions(json.loads(json.dumps(cv)), cv)
        self.assertNotIn("grab", out["work_experiences"][0]["bullets"][0].lower())

    def test_everyday_word_that_is_not_the_employer_still_survives(self):
        cv = {
            "work_experiences": [
                {
                    "company": "Acme Widgets",
                    "bullets": ["Helped grab market share at Grab Holdings."],
                }
            ]
        }
        out = bm._blind_postprocess_company_mentions(json.loads(json.dumps(cv)), cv)
        bullet = out["work_experiences"][0]["bullets"][0]
        self.assertIn("grab market share", bullet)
        self.assertIn("[Company]", bullet)

    def test_brand_compound_only_cv_still_registers_the_name(self):
        # A CV that never writes "Grab" alone, only "GrabFood", must still mask it.
        cv = {
            "work_experiences": [
                {
                    "company": "Acme Widgets",
                    "bullets": ["Launched GrabFood and BoostPay.", "Boosted revenue."],
                }
            ]
        }
        out = bm._blind_postprocess_company_mentions(json.loads(json.dumps(cv)), cv)
        bullets = out["work_experiences"][0]["bullets"]
        self.assertEqual(bullets[0], "Launched [Company]Food and [Company]Pay.")
        self.assertEqual(bullets[1], "Boosted revenue.")

    def test_dotted_phone_number_is_still_redacted(self):
        self.assertIn(
            "[Phone Redacted]",
            bm._blind_redact_phone_candidates("Reach me on 44.7911123456"),
        )

    def test_decimal_measurements_are_still_preserved(self):
        for text in (
            "Handled 99.999999 percent uptime.",
            "Ratio 12.5 to 1 achieved.",
        ):
            with self.subTest(text=text):
                self.assertEqual(bm._blind_redact_phone_candidates(text), text)


if __name__ == "__main__":
    unittest.main()
