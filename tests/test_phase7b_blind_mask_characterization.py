"""Characterization tests for the Blind CV/JD organisation-masking helpers.

Locks the behaviour of the stateless masking logic extracted into
``cvstudio_blind_mask`` (Phase 7B-6f): collecting mask terms, replacing
organisation mentions in text, and recursively masking parsed structures.
"""

import unittest

import cvstudio_blind_mask as bm


class ReplaceTests(unittest.TestCase):
    def test_replace_masks_org_and_keeps_other_text(self):
        out = bm._blind_replace_org_terms_in_text("I worked at Bolttech on Python", ["Bolttech"])
        self.assertNotIn("Bolttech", out)
        self.assertIn("Python", out)
        self.assertIn("[Company]", out)

    def test_replace_no_terms_is_noop(self):
        text = "Nothing to mask here"
        self.assertEqual(bm._blind_replace_org_terms_in_text(text, []), text)


class CollectTests(unittest.TestCase):
    def test_collect_returns_list(self):
        terms = bm._blind_collect_org_mask_terms({"experience": [{"company": "Bolttech Sdn Bhd"}]})
        self.assertIsInstance(terms, list)

class RecursiveTests(unittest.TestCase):
    def test_prepare_summary_promotes_about_box_and_removes_duplicate_skill(self):
        prepared = bm._blind_prepare_summary_bullets(
            {
                "summary_bullets": [],
                "skills": [
                    {
                        "category": "About Him / Her",
                        "items": "- Led Maybank delivery\n- Built regional platforms",
                    },
                    {"category": "Technology", "items": "Python, SQL"},
                ],
            }
        )
        self.assertEqual(
            prepared["summary_bullets"],
            ["Led Maybank delivery", "Built regional platforms"],
        )
        self.assertEqual(
            prepared["skills"],
            [{"category": "Technology", "items": "Python, SQL"}],
        )

    def test_mask_recursive_scrubs_nested_strings(self):
        data = {"summary": "Led a team at Bolttech", "skills": ["Python", "worked at Bolttech"]}
        masked = bm._blind_mask_org_terms_recursive(data, ["Bolttech"])
        blob = str(masked)
        self.assertNotIn("Bolttech", blob)
        self.assertIn("Python", blob)

    def test_walk_strings_yields_all(self):
        # _blind_walk_strings(obj) is a generator over the nested string values.
        seen = set(bm._blind_walk_strings({"a": "x", "b": ["y", {"c": "z"}]}))
        self.assertEqual(seen, {"x", "y", "z"})

    def test_restore_cv_bullet_structure_keeps_blinded_text(self):
        original = {
            "work_experiences": [{"roles": [{"bullets": [
                {"heading": "Implementation", "bullets": [
                    "Configured Acme systems",
                    "Delivered Acme rollout",
                ], "kind": "section", "unexpected_source_note": "Acme secret"},
                "Plain duty",
            ]}]}],
        }
        blinded = {
            "work_experiences": [{"roles": [{"bullets": [
                "Implementation",
                "Configured [Company] systems",
                "Delivered [Company] rollout",
                "Plain duty",
            ]}]}],
        }
        repaired = bm._blind_restore_cv_bullet_structure(blinded, original)
        section = repaired["work_experiences"][0]["roles"][0]["bullets"][0]
        self.assertEqual(section, {
            "heading": "Implementation",
            "bullets": [
                "Configured [Company] systems",
                "Delivered [Company] rollout",
            ],
            "kind": "section",
        })
        self.assertNotIn("unexpected_source_note", section)
        self.assertEqual(
            repaired["work_experiences"][0]["roles"][0]["bullets"][1],
            "Plain duty",
        )
        self.assertNotIn("Acme", str(repaired))

    def test_restore_cv_bullet_structure_does_not_guess_on_count_mismatch(self):
        original = {"work_experiences": [{"roles": [{"bullets": [
            {"heading": "Acme Implementation", "bullets": ["One", "Two"], "kind": "section"},
        ]}]}]}
        blinded = {"work_experiences": [{"roles": [{"bullets": [
            "[Company] Implementation", "One",
        ]}]}]}
        repaired = bm._blind_restore_cv_bullet_structure(blinded, original)
        self.assertEqual(
            repaired["work_experiences"][0]["roles"][0]["bullets"],
            ["[Company] Implementation", "One"],
        )
        self.assertNotIn("Acme", str(repaired))

    def test_restore_cv_bullet_structure_ignores_malformed_nested_source_item(self):
        original = {"work_experiences": [{"roles": [{"bullets": [
            {"heading": "Implementation", "bullets": ["One", 7], "kind": "section"},
        ]}]}]}
        blinded = {"work_experiences": [{"roles": [{"bullets": [
            "Implementation", "One",
        ]}]}]}
        repaired = bm._blind_restore_cv_bullet_structure(blinded, original)
        self.assertEqual(
            repaired["work_experiences"][0]["roles"][0]["bullets"],
            ["Implementation", "One"],
        )

    def test_restore_cv_bullet_structure_does_not_apply_to_shifted_role(self):
        original = {"work_experiences": [{"roles": [{
            "title": "First role",
            "date_range": "2020 to 2021",
            "bullets": [{"heading": "Support", "bullets": ["One"], "kind": "section"}],
        }]}]}
        blinded = {"work_experiences": [{"roles": [{
            "title": "Second role",
            "date_range": "2022 to 2023",
            "bullets": ["Support", "One"],
        }]}]}
        repaired = bm._blind_restore_cv_bullet_structure(blinded, original)
        self.assertEqual(
            repaired["work_experiences"][0]["roles"][0]["bullets"],
            ["Support", "One"],
        )

    def test_restore_cv_bullet_structure_tolerates_unexpected_nested_shapes(self):
        original = {"work_experiences": [{"roles": [{}]}]}
        malformed_values = (
            {"bad": "shape"},
            "not a list",
            7,
        )
        for value in malformed_values:
            blinded = {"work_experiences": value}
            self.assertEqual(
                bm._blind_restore_cv_bullet_structure(blinded, original),
                blinded,
            )
        for value in malformed_values:
            blinded = {"work_experiences": [{"roles": value}]}
            self.assertEqual(
                bm._blind_restore_cv_bullet_structure(blinded, original),
                blinded,
            )

    def test_finalize_summary_preserves_count_and_scrubs_direct_identity(self):
        original = {
            "candidate": {
                "name": "Jane Candidate",
                "email": "jane@example.com",
                "phone": "+60 12-345 6789",
                "linkedin": "https://linkedin.com/in/jane-candidate",
            },
            "summary_bullets": ["One", "Two"],
            "education": [{"institution": "Fixture Technology University"}],
        }
        blinded = {
            "summary_bullets": [
                "Jane Candidate led delivery; jane@example.com",
                "Studied at Fixture Technology University; see https://linkedin.com/in/jane-candidate or +60 12-345 6789",
            ]
        }

        finalized = bm._blind_finalize_summary_bullets(blinded, original)

        self.assertEqual(len(finalized["summary_bullets"]), 2)
        blob = " ".join(finalized["summary_bullets"])
        self.assertNotIn("Jane Candidate", blob)
        self.assertNotIn("jane@example.com", blob)
        self.assertNotIn("linkedin.com/in/jane-candidate", blob)
        self.assertNotIn("+60 12-345 6789", blob)
        self.assertNotIn("Fixture Technology University", blob)
        self.assertIn("the candidate", blob)
        self.assertIn("[Email Redacted]", blob)
        self.assertIn("[Link Redacted]", blob)
        self.assertIn("[Phone Redacted]", blob)
        self.assertIn("[Institution]", blob)

    def test_finalize_summary_does_not_duplicate_generic_candidate_label(self):
        original = {
            "candidate": {"name": "Candidate"},
            "summary_bullets": ["One"],
        }
        finalized = bm._blind_finalize_summary_bullets(
            {"summary_bullets": ["The candidate led delivery."]}, original
        )
        self.assertEqual(
            finalized["summary_bullets"], ["The candidate led delivery."]
        )

    def test_finalize_summary_uses_identifier_boundaries_and_safe_single_case(self):
        original = {
            "candidate": {"name": "May"},
            "summary_bullets": ["One"],
            "education": [{"institution": "MIT"}],
        }
        finalized = bm._blind_finalize_summary_bullets(
            {"summary_bullets": ["This role may require long-term commitment."]},
            original,
        )
        self.assertEqual(
            finalized["summary_bullets"],
            ["This role may require long-term commitment."],
        )

    def test_finalize_summary_masks_unknown_context_names_and_strips_markers(self):
        original = {
            "candidate": {"name": "Jane Example"},
            "summary_bullets": ["Delivered the FalconX rollout for Novacore."],
            "work_experiences": [],
            "education": [],
        }
        finalized = bm._blind_finalize_summary_bullets(
            {"summary_bullets": ["- Delivered the FalconX rollout for Novacore."]},
            original,
        )
        self.assertEqual(
            finalized["summary_bullets"],
            ["Delivered the [Product] rollout for [Company]."],
        )

    def test_finalize_generated_summary_scrubs_source_identifiers(self):
        finalized = bm._blind_finalize_generated_summary_text(
            "- Jane Example led the FalconX rollout for Novacore. Contact jane@example.com",
            "Jane Example\nCurrent Company: Novacore\nWorked on the FalconX rollout for Novacore.\nEmail: jane@example.com",
        )
        self.assertEqual(
            finalized,
            "- the candidate led the [Product] rollout for [Company]. Contact [Email Redacted]",
        )

    def test_finalize_generated_summary_preserves_role_and_technology_terms(self):
        finalized = bm._blind_finalize_generated_summary_text(
            "- Experienced Software Engineer skilled with Microsoft Excel.",
            "Software Engineer\n2020 | University of Tenaga Nasional\nSkilled with Microsoft Excel",
        )
        self.assertEqual(
            finalized,
            "- Experienced Software Engineer skilled with Microsoft Excel.",
        )

    def test_finalize_generated_summary_preserves_other_people(self):
        finalized = bm._blind_finalize_generated_summary_text(
            "- the candidate worked with John Smith on regional delivery.",
            "Jane Example\nWorked with John Smith on regional delivery.",
        )
        self.assertEqual(
            finalized,
            "- the candidate worked with John Smith on regional delivery.",
        )

    def test_phone_redaction_keeps_real_date_ranges(self):
        self.assertEqual(
            bm._blind_redact_phone_candidates("Worked from 2020 - 2023."),
            "Worked from 2020 - 2023.",
        )
        self.assertEqual(
            bm._blind_redact_phone_candidates("Call +60 12-345 6789."),
            "Call [Phone Redacted].",
        )

    def test_finalize_summary_refuses_silent_provider_loss(self):
        original = {"summary_bullets": ["One", "Two"]}
        with self.assertRaisesRegex(ValueError, "preserve every"):
            bm._blind_finalize_summary_bullets(
                {"summary_bullets": ["Only one"]}, original
            )


class SmokeAndHygieneTests(unittest.TestCase):
    def test_symbols_present(self):
        for name in [
            "_blind_walk_strings", "_blind_add_mask_term", "_blind_collect_org_mask_terms",
            "_blind_replace_org_terms_in_text", "_blind_mask_org_terms_recursive",
            "_blind_postprocess_company_mentions", "_blind_restore_cv_bullet_structure",
            "_blind_prepare_summary_bullets", "_blind_finalize_summary_bullets",
            "_blind_finalize_generated_summary_text",
        ]:
            self.assertTrue(callable(getattr(bm, name)), name)

    def test_module_does_not_import_app(self):
        self.assertNotIn("app", getattr(bm, "__dict__", {}))


if __name__ == "__main__":
    unittest.main()
