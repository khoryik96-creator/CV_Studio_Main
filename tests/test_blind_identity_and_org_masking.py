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

    def test_short_surname_is_swept_but_a_company_sharing_it_is_not(self):
        # Three letters is enough for a name word here - Tan, Nur and Wei are ordinary
        # given names and surnames - while "Tan Chong Motor" keeps its proper-noun
        # protection, because the words beside it belong to nobody in this name.
        out = bm._blind_scrub_candidate_identity(
            {"bullets": ["Tan led delivery for Tan Chong Motor."]},
            self._original("Tan Wei Ming"),
        )
        self.assertEqual(
            out["bullets"], ["The candidate led delivery for Tan Chong Motor."]
        )

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

    def test_brand_compound_masks_when_the_word_is_the_employer(self):
        # The employer path is what carries a brand compound: Grab is collected from the
        # employer field, so GrabFood is masked while "Grabbing" keeps its first syllable.
        cv = {
            "work_experiences": [
                {
                    "company": "Grab",
                    "bullets": ["Launched GrabFood.", "Grabbing market share.", "worked at grab"],
                }
            ]
        }
        out = bm._blind_postprocess_company_mentions(json.loads(json.dumps(cv)), cv)
        bullets = out["work_experiences"][0]["bullets"]
        self.assertEqual(bullets[0], "Launched [Company]Food.")
        self.assertEqual(bullets[1], "Grabbing market share.")
        self.assertEqual(bullets[2], "worked at [Company]")

    def test_brand_compound_alone_does_not_register_an_unrelated_word(self):
        # Deliberate trade: a CamelCase compound is not evidence that an everyday word
        # names this candidate's employer. MetaTrader and MetaBase are unrelated
        # products, and collecting "Meta" from them would export "[Company]Trader".
        cv = {
            "work_experiences": [
                {
                    "company": "Acme Widgets",
                    "bullets": ["Used MetaTrader 5 and MetaBase dashboards."],
                }
            ]
        }
        self.assertNotIn("Meta", bm._blind_collect_org_mask_terms(cv))
        out = bm._blind_postprocess_company_mentions(json.loads(json.dumps(cv)), cv)
        self.assertEqual(
            out["work_experiences"][0]["bullets"][0],
            "Used MetaTrader 5 and MetaBase dashboards.",
        )

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


class ThirdReviewRegressionTests(unittest.TestCase):
    """Cases a third review of these fixes found."""

    def _scrub(self, text, name, **extra):
        candidate = {"name": name}
        candidate.update(extra)
        return bm._blind_scrub_candidate_identity(
            {"b": [text]}, {"candidate": candidate}
        )["b"][0]

    def test_mononym_is_masked_even_when_it_is_an_everyday_word(self):
        # A single-word name is the candidate's entire identity: nothing else in the
        # document names them, so the denylists must not veto it.
        self.assertEqual(
            self._scrub("Ali led the migration.", "Ali"),
            "The candidate led the migration.",
        )
        self.assertEqual(
            self._scrub("Grace led delivery. Contact Grace.", "Grace"),
            "The candidate led delivery. Contact the candidate.",
        )

    def test_mononym_that_is_an_everyday_word_still_spares_prose(self):
        # The capitalisation rule keeps doing the work.
        self.assertEqual(
            self._scrub("The grace period ended early.", "Grace"),
            "The grace period ended early.",
        )

    def test_mononym_is_masked_beside_another_capitalised_word(self):
        # With no second name word there is nothing to corroborate against, so a
        # mononym is sweept beside a capital rather than left to leak.
        self.assertEqual(
            self._scrub("Suharto Widodo led delivery.", "Suharto"),
            "The candidate Widodo led delivery.",
        )

    def test_acronyms_and_headings_do_not_shield_the_name(self):
        for text, expected in (
            ("Vinay ETL Pipeline Rebuild", "The candidate ETL Pipeline Rebuild"),
            ("Vinay AWS migration lead", "The candidate AWS migration lead"),
            ("VINAY LED THE MIGRATION", "The candidate LED THE MIGRATION"),
        ):
            with self.subTest(text=text):
                self.assertEqual(self._scrub(text, "Vinay Lariya"), expected)

    def test_full_name_with_a_middle_name_is_replaced_as_one_run(self):
        # Two of the candidate's own name words in one run confirm the person.
        self.assertEqual(
            self._scrub("Vinay Kumar Lariya led it.", "Vinay Lariya"),
            "The candidate led it.",
        )

    def test_a_different_person_sharing_a_first_name_survives(self):
        self.assertEqual(
            self._scrub("Worked with Vinay Kumar too.", "Vinay Lariya"),
            "Worked with Vinay Kumar too.",
        )

    def test_short_name_word_still_corroborates(self):
        # "Tan" is too short to be a sweep term on its own, but it still confirms that
        # "Ming Tan" is the candidate.
        self.assertEqual(
            self._scrub("Ming Tan led the rollout.", "Tan Wei Ming"),
            "The candidate led the rollout.",
        )

    def test_run_edged_by_an_everyday_word_is_still_collected(self):
        # Only a particle edge disqualifies a run; "Wei Long" is two ordinary name words.
        self.assertEqual(
            self._scrub("Wei Long led the project.", "Lee Wei Long"),
            "The candidate led the project.",
        )

    def test_indian_lineage_particle_does_not_rewrite_another_person(self):
        self.assertEqual(
            self._scrub("Referee: Devi a/p Raman was contacted.", "Muthu a/p Raman"),
            "Referee: Devi a/p Raman was contacted.",
        )
        self.assertEqual(
            self._scrub("Muthu a/p Raman owned delivery.", "Muthu a/p Raman"),
            "The candidate owned delivery.",
        )

    def test_employer_masking_never_eats_an_inflection(self):
        # Provenance decides whether a lowercase match is masked; it must not also relax
        # the brand-prefix rule, or "Grabbing" loses its first syllable.
        cv = {
            "work_experiences": [
                {
                    "company": "Grab",
                    "bullets": ["Grabbing market share.", "metadata rebuilt."],
                }
            ]
        }
        out = bm._blind_postprocess_company_mentions(json.loads(json.dumps(cv)), cv)
        self.assertEqual(
            out["work_experiences"][0]["bullets"],
            ["Grabbing market share.", "metadata rebuilt."],
        )

    def test_everyday_employer_words_keep_their_inflections(self):
        for company, text in (
            ("Meta", "metadata lineage rebuilt."),
            ("Yes", "Yesterday's run was clean."),
            ("Boost", "Boosted revenue by 30%."),
            ("Shell", "Shelling out weekly reports."),
        ):
            with self.subTest(company=company):
                cv = {"work_experiences": [{"company": company, "bullets": [text]}]}
                out = bm._blind_postprocess_company_mentions(
                    json.loads(json.dumps(cv)), cv
                )
                self.assertEqual(out["work_experiences"][0]["bullets"], [text])

    def test_large_decimals_are_not_phone_numbers(self):
        for text in (
            "Saved RM 250000.00 annually.",
            "Grew revenue to 1250000.50 this year.",
            "Uptime of 99.9999999 percent.",
        ):
            with self.subTest(text=text):
                self.assertEqual(bm._blind_redact_phone_candidates(text), text)

    def test_dotted_phone_is_still_redacted(self):
        self.assertIn(
            "[Phone Redacted]",
            bm._blind_redact_phone_candidates("Reach me on 44.7911123456"),
        )


class CodexReviewRegressionTests(unittest.TestCase):
    """Cases the automated PR review on #198 found."""

    def _scrub(self, text, name):
        return bm._blind_scrub_candidate_identity(
            {"b": [text]}, {"candidate": {"name": name}}
        )["b"][0]

    def test_accented_names_are_matched(self):
        # An ASCII-only word class stops partway through "Jose" and leaks the name.
        self.assertEqual(
            self._scrub("Jos\u00e9 led the migration.", "Jos\u00e9"),
            "The candidate led the migration.",
        )
        self.assertEqual(
            self._scrub("Fran\u00e7ois led it.", "Fran\u00e7ois Dubois"),
            "The candidate led it.",
        )

    def test_sentence_leading_word_does_not_shield_the_name(self):
        # "Contact" and "Ask" are capitalised because they open a sentence, not because
        # they are somebody's name.
        for text, expected in (
            ("Contact Vinay.", "Contact the candidate."),
            ("Ask Vinay tomorrow.", "Ask the candidate tomorrow."),
            ("References\nVinay led it.", "References\nThe candidate led it."),
        ):
            with self.subTest(text=text):
                self.assertEqual(self._scrub(text, "Vinay Lariya"), expected)

    def test_longer_proper_nouns_are_preserved(self):
        # The exemption must not be limited to runs of exactly two words.
        self.assertEqual(
            self._scrub("Based in Greater Victoria Area.", "Victoria Lee"),
            "Based in Greater Victoria Area.",
        )
        self.assertEqual(
            self._scrub("Worked with Vinay Kumar Singh.", "Vinay Lariya"),
            "Worked with Vinay Kumar Singh.",
        )

    def test_dotted_phone_with_a_short_subscriber_part_is_redacted(self):
        for text in ("Reach me at 65.91234567", "Call 44.7911123456 now"):
            with self.subTest(text=text):
                self.assertIn("[Phone Redacted]", bm._blind_redact_phone_candidates(text))

    def test_long_decimals_beside_a_unit_stay_measurements(self):
        for text in (
            "Uptime of 99.9999999 percent.",
            "Handled 99.999999 percent uptime.",
            "Availability 99.99999999 held.",
            "Cost RM 12.345678 million.",
            "Saved RM 250000.00 annually.",
        ):
            with self.subTest(text=text):
                self.assertEqual(bm._blind_redact_phone_candidates(text), text)


# Every line a blind CV must NOT change, whatever the candidate is called. Ordinary CV
# prose, technology, places, months, money and third parties.
_BLIND_PROSE_CORPUS = (
    "Delivered long-term roadmap and a sharp reduction in cost.",
    "Served the local church community programme.",
    "Automated ETL with shell scripting and Python.",
    "Built the metadata catalog and boosted margins.",
    "Yesterday the pipeline ran clean; grabbing share early.",
    "Based in Shah Alam and Petaling Jaya.",
    "Based in Greater Victoria Area.",
    "May 2023 to June 2024 covered the migration.",
    "Long Term Incentive Plan was revised.",
    "Ruby on Rails, Java, Kafka and Cassandra.",
    "Used MetaTrader 5 and MetaBase dashboards.",
    "Saved RM 250000.00 annually.",
    "Uptime of 99.9999999 percent.",
    "Processed 123456789 records nightly.",
    "Referee: Suresh Nair was contacted.",
    "Coordinated with Siti binti Rahman on payroll.",
    "van der Waals forces apply.",
    "Revenue rose from 12% to 40%.",
    "Tuning max_connections and thread_max_size.",
    "Used ada_boost and grid_search for the model.",
    "Owns cust_order_fact and dim_date tables.",
    "Escalated to the min_value and sum_total defaults.",
)

# Candidate names spanning the shapes this market actually sees.
_BLIND_NAME_CORPUS = (
    "Vinay Lariya",
    "Tan Wei Ming",
    "Nur Aisyah binti Rahman",
    "Muthu a/p Raman",
    "Marieke van der Meer",
    "Jos\u00e9 Fern\u00e1ndez",
    "Fran\u00e7ois Dubois",
    "Suharto",
    "Ali",
    "Mary Smith-Jones",
    "Sean O'Brien",
    "Jean-Luc Picard",
    "Nur Aisyah binti Abdul-Rahman",
)

# Sentence frames a model actually produces, with {name} standing for whatever the
# provider left behind. Each one must lose the name.
_BLIND_LEAK_FRAMES = (
    "{name} led the Kafka migration.",
    "Worked with {name} on the platform.",
    "Contact {name}.",
    "Ask {name} tomorrow.",
    "{name}'s team shipped it.",
    "{name}\u2019s role expanded.",
    "References\n{name} led it.",
    "{name} ETL Pipeline Rebuild",
    "{name} AWS migration lead",
    "- {name} owned delivery.",
    "Project lead: {name} delivered on time.",
    "{name} Senior Data Engineer at Acme.",
    "Reference available from Mr {name}.",
    "Contact Dr {name} for details.",
    "Escalated to {name} and closed it.",
    "{name} Lead Architect, Cloud Platform",
)


class BlindSweepInvariantTests(unittest.TestCase):
    """Two invariants over a corpus, rather than one test per reported example.

    Every fix in this area has been a judgement about natural language, and each round
    of review probed inputs the previous round did not. Checking both directions across
    a corpus catches that class of case here instead.
    """

    @staticmethod
    def _scrub(text, name):
        return bm._blind_scrub_candidate_identity(
            {"b": [text]}, {"candidate": {"name": name}}
        )["b"][0]

    def test_no_candidate_name_survives_any_frame(self):
        for name in _BLIND_NAME_CORPUS:
            words = [
                word
                for word in name.split()
                if word.casefold() not in bm._BLIND_NAME_PARTICLES
            ]
            for frame in _BLIND_LEAK_FRAMES:
                for written in (name, words[0], words[-1]):
                    with self.subTest(name=name, frame=frame, written=written):
                        out = self._scrub(frame.format(name=written), name)
                        self.assertNotIn(
                            written,
                            out,
                            "{!r} survived in {!r}".format(written, out),
                        )

    def test_ordinary_cv_prose_is_never_rewritten(self):
        for name in _BLIND_NAME_CORPUS:
            for line in _BLIND_PROSE_CORPUS:
                with self.subTest(name=name, line=line):
                    self.assertEqual(self._scrub(line, name), line)

    def test_everyday_word_names_do_not_rewrite_their_own_word(self):
        # The hardest shape: the candidate's whole name is also an ordinary word. The
        # capitalisation and number rules carry these.
        for name, line in (
            ("May", "May 2023 to June 2024 covered the migration."),
            ("Long", "Long Term Incentive Plan was revised."),
            ("Victoria", "Based in Greater Victoria Area."),
            ("Grace", "The grace period ended early."),
        ):
            with self.subTest(name=name):
                self.assertEqual(self._scrub(line, name), line)


class FourthReviewRegressionTests(unittest.TestCase):
    """Cases a fourth review of these fixes found, plus one it led me to."""

    def _scrub(self, text, name, **extra):
        candidate = {"name": name}
        candidate.update(extra)
        return bm._blind_scrub_candidate_identity(
            {"b": [text]}, {"candidate": candidate}
        )["b"][0]

    def test_compound_surname_standing_alone_is_replaced(self):
        # The matcher recognised these but the replacer compared alphabetic parts
        # against the whole compound, so it matched and then did nothing.
        for name, text in (
            ("Mary Smith-Jones", "Smith-Jones delivered the platform."),
            ("Sean O'Brien", "O'Brien led the migration."),
            ("Jean-Luc Picard", "Jean-Luc owned delivery."),
        ):
            with self.subTest(name=name):
                out = self._scrub(text, name)
                self.assertEqual(out, "The candidate " + text.split(" ", 1)[1])

    def test_either_half_of_a_compound_surname_is_replaced(self):
        self.assertEqual(
            self._scrub("Jones delivered it.", "Mary Smith-Jones"),
            "The candidate delivered it.",
        )

    def test_honorific_does_not_shield_the_name_and_goes_with_it(self):
        for text, expected in (
            ("Reference available from Mr Lariya.", "Reference available from the candidate."),
            ("Contact Dr Lariya for details.", "Contact the candidate for details."),
        ):
            with self.subTest(text=text):
                self.assertEqual(self._scrub(text, "Vinay Lariya"), expected)

    def test_possessive_survives_the_replacement(self):
        # The honorific span must not swallow the possessive of a bare name.
        self.assertEqual(
            self._scrub("Mary's team shipped it.", "Mary Smith-Jones"),
            "The candidate's team shipped it.",
        )
        self.assertEqual(
            self._scrub("Vinay\u2019s role grew.", "Vinay Lariya"),
            "The candidate\u2019s role grew.",
        )

    def test_honorific_before_a_full_name_goes_with_it(self):
        self.assertEqual(
            self._scrub("Contact Dr Vinay Lariya today.", "Vinay Lariya"),
            "Contact the candidate today.",
        )

    def test_ordinary_snake_case_identifiers_survive(self):
        # One short, common part is not evidence: max_connections is configuration, and
        # ada_boost is an algorithm.
        for name, text in (
            ("Max Chen", "Tuning max_connections and thread_max_size."),
            ("Ada Wong", "Used ada_boost for the model."),
        ):
            with self.subTest(name=name):
                self.assertEqual(self._scrub(text, name), text)

    def test_identifier_carrying_the_name_is_still_replaced(self):
        self.assertEqual(
            self._scrub("Rebuilt vinay_lariya_pipeline nightly.", "Vinay Lariya"),
            "Rebuilt the candidate nightly.",
        )
        self.assertEqual(
            self._scrub("Owner_Vinay signed off.", "Vinay Lariya"),
            "The candidate signed off.",
        )

    def test_first_last_email_does_not_leave_a_dangling_article(self):
        out = self._scrub(
            "Reach me at vinay_lariya@corp.com anytime.",
            "Vinay Lariya",
            email="vinay_lariya@corp.com",
        )
        self.assertEqual(out, "Reach me at [Email Redacted] anytime.")

    def test_address_at_the_end_of_a_sentence_is_redacted(self):
        # The trailing guard excluded ".", so an address written last in a bullet - the
        # commonest place for one - was never redacted.
        self.assertEqual(
            bm._BLIND_SUMMARY_EMAIL_RE.sub(
                "[Email Redacted]", "Referee: someone@else.com."
            ),
            "Referee: [Email Redacted].",
        )
        self.assertEqual(
            bm._BLIND_SUMMARY_EMAIL_RE.sub("[Email Redacted]", "Mail user@corp.com.my now"),
            "Mail [Email Redacted] now",
        )


if __name__ == "__main__":
    unittest.main()
