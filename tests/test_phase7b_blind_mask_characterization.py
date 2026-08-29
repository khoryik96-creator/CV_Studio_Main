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

    def test_prepare_summary_preserves_more_than_twenty_source_bullets(self):
        source_bullets = [f"Summary bullet {index}" for index in range(1, 26)]

        prepared = bm._blind_prepare_summary_bullets(
            {"summary_bullets": source_bullets, "skills": []}
        )

        self.assertEqual(prepared["summary_bullets"], source_bullets)

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

    def test_finalize_summary_redacts_identifiers_split_by_markdown(self):
        original = {
            "candidate": {
                "name": "Jane Example",
                "current_company": "Acme Sdn Bhd",
            },
            "summary_bullets": [
                "Jane Example led delivery for Acme Sdn Bhd."
            ],
            "work_experiences": [{"company": "Acme Sdn Bhd", "roles": []}],
            "education": [],
        }
        finalized = bm._blind_finalize_summary_bullets(
            {
                "summary_bullets": [
                    "**Jane** Example led delivery for **Acme** Sdn Bhd."
                ]
            },
            original,
        )
        self.assertEqual(
            finalized["summary_bullets"],
            ["the candidate led delivery for [Company]."],
        )
        self.assertEqual(
            bm._blind_replace_identifier("Company", "Company", "[Company]"),
            "[Company]",
        )

    def test_finalize_generated_summary_redacts_labeled_physical_address(self):
        finalized = bm._blind_finalize_generated_summary_text(
            "- the candidate lives at 12 Jalan Ampang, Kuala Lumpur.",
            "Jane Example\nAddress: 12 Jalan Ampang, Kuala Lumpur.",
        )
        self.assertEqual(
            finalized,
            "- the candidate lives at [Address Redacted].",
        )

    def test_pipe_identity_uses_company_column_instead_of_role(self):
        expected = ("Acme", "[Company]", False)
        self.assertEqual(
            bm._blind_summary_pipe_identity(
                "2019 | Acme | Senior Engineer"
            ),
            expected,
        )
        self.assertEqual(
            bm._blind_summary_pipe_identity(
                "Senior Engineer | Acme | 2019"
            ),
            expected,
        )
        self.assertEqual(
            bm._blind_summary_pipe_identity(
                "2019 | Senior Engineer | Acme"
            ),
            expected,
        )

    def test_finalize_generated_summary_preserves_camel_case_technologies(self):
        finalized = bm._blind_finalize_generated_summary_text(
            "- the candidate built PowerBI dashboards with JavaScript and NodeJS.",
            "Jane Example\nBuilt PowerBI dashboards with JavaScript and NodeJS.",
        )
        self.assertEqual(
            finalized,
            "- the candidate built PowerBI dashboards with JavaScript and NodeJS.",
        )

    def test_company_suffix_collection_does_not_consume_sentence_lead_in(self):
        finalized = bm._blind_finalize_generated_summary_text(
            "- the candidate worked with Acme Technology on migration.",
            "Jane Example\nWorked with Acme Technology on migration.",
        )
        self.assertEqual(
            finalized,
            "- the candidate worked with [Company] on migration.",
        )

    def test_finalize_generated_summary_redacts_single_word_candidate_name(self):
        finalized = bm._blind_finalize_generated_summary_text(
            "- **Sukarno** led regional delivery.",
            "Sukarno\nRegional delivery specialist",
        )
        self.assertEqual(
            finalized,
            "- the candidate led regional delivery.",
        )

    def test_finalize_generated_summary_redacts_name_from_mixed_contact_header(self):
        finalized = bm._blind_finalize_generated_summary_text(
            "- Jane Example leads regional delivery.",
            "Jane Example | +60 12-345 6789 | jane@example.com\nSenior Consultant",
        )
        self.assertEqual(finalized, "- the candidate leads regional delivery.")

    def test_finalize_generated_summary_redacts_unicode_and_initialled_names(self):
        cases = (
            ("José García", "- José García leads regional delivery."),
            ("A. R. Rahman", "- A. R. Rahman leads regional delivery."),
            ("Mohd. Faizal", "- Mohd. Faizal leads regional delivery."),
            ("Anita A/P Muthu", "- Anita A/P Muthu leads regional delivery."),
            ("Kumar A/L Raj", "- Kumar A/L Raj leads regional delivery."),
            ("Anita A / P Muthu", "- Anita A / P Muthu leads regional delivery."),
            ("Kumar A / L Raj", "- Kumar A / L Raj leads regional delivery."),
            ("Anita a/p Muthu", "- Anita a/p Muthu leads regional delivery."),
        )
        for source_name, output in cases:
            with self.subTest(source_name=source_name):
                finalized = bm._blind_finalize_generated_summary_text(
                    output,
                    f"{source_name}\nSenior Consultant",
                )
                self.assertEqual(
                    finalized,
                    "- the candidate leads regional delivery.",
                )

    def test_finalize_generated_summary_redacts_normalized_lineage_spacing(self):
        cases = (
            ("Anita A / P Muthu", "- Anita A/P Muthu leads delivery."),
            ("Kumar A/L Raj", "- Kumar A / L Raj leads delivery."),
        )
        for source_name, output in cases:
            with self.subTest(source_name=source_name):
                finalized = bm._blind_finalize_generated_summary_text(
                    output,
                    f"{source_name}\nSenior Consultant",
                )
                self.assertEqual(finalized, "- the candidate leads delivery.")

    def test_finalize_generated_summary_redacts_bare_personal_website(self):
        cases = (
            ("janedoe.dev", "janedoe.dev"),
            ("janedoe.design", "janedoe.design"),
            ("janedoe.design", "https://janedoe.design"),
            ("janedoe.design/work", "janedoe.design"),
            ("b.tech", "b.tech"),
        )
        for source_website, generated_website in cases:
            with self.subTest(generated_website=generated_website):
                finalized = bm._blind_finalize_generated_summary_text(
                    f"- Portfolio: {generated_website}",
                    f"Jane Example\nPortfolio: {source_website}",
                )
                self.assertEqual(finalized, "- Portfolio: [Link Redacted]")

    def test_finalize_generated_summary_preserves_dotted_technology_name(self):
        self.assertEqual(bm._blind_summary_bare_domain("Node.js"), "")
        self.assertEqual(
            bm._blind_apply_summary_replacements(
                "- Built production services with Node.js.", []
            ),
            "Built production services with Node.js.",
        )

    def test_finalize_generated_summary_preserves_dotted_degree_abbreviations(self):
        for degree in ("B.Sc", "M.Sc", "B.Eng", "M.Eng", "B.Tech", "M.Tech"):
            with self.subTest(degree=degree):
                finalized = bm._blind_finalize_generated_summary_text(
                    f"- Holds a {degree} degree.",
                    f"Jane Example\nEDUCATION\n{degree} degree",
                )
                self.assertEqual(finalized, f"- Holds a {degree} degree.")

    def test_finalize_generated_summary_redacts_vertical_standalone_employer(self):
        finalized = bm._blind_finalize_generated_summary_text(
            "- the candidate worked at Acme as a Senior Engineer.",
            "Jane Example\nEXPERIENCE\nAcme\nSenior Engineer\n2020 - Present",
        )
        self.assertEqual(
            finalized,
            "- the candidate worked at [Company] as a Senior Engineer.",
        )

    def test_finalize_generated_summary_redacts_employer_on_date_line(self):
        for dated_employer in (
            "Acme (2020 - Present)",
            "2020 - Present Acme",
            "Acme - 2020 to Present",
            "Acme (2019)",
            "Acme 2019",
            "Senior Engineer at Acme (2019)",
            "Senior Engineer at Acme 2019",
        ):
            with self.subTest(dated_employer=dated_employer):
                finalized = bm._blind_finalize_generated_summary_text(
                    "- the candidate worked at Acme.",
                    f"Jane Example\nEXPERIENCE\n{dated_employer}",
                )
                self.assertEqual(
                    finalized,
                    "- the candidate worked at [Company].",
                )

    def test_finalize_generated_summary_uses_education_section_for_acronym(self):
        finalized = bm._blind_finalize_generated_summary_text(
            "- Graduated from MIT.",
            "Jane Example\nEDUCATION\nMIT\n2010 - 2014",
        )
        self.assertEqual(finalized, "- Graduated from [Institution].")

    def test_finalize_generated_summary_preserves_dated_qualification_acronym(self):
        finalized = bm._blind_finalize_generated_summary_text(
            "- Holds CFA.",
            "Jane Example\nPROFESSIONAL QUALIFICATIONS\nCFA\n2020 - 2023",
        )
        self.assertEqual(finalized, "- Holds CFA.")

    def test_finalize_generated_summary_redacts_unlabeled_street_address(self):
        finalized = bm._blind_finalize_generated_summary_text(
            "- the candidate lives at 12 Jalan Ampang, Kuala Lumpur.",
            "Jane Example\n12 Jalan Ampang, Kuala Lumpur",
        )
        self.assertEqual(
            finalized,
            "- the candidate lives at [Address Redacted].",
        )

    def test_finalize_generated_summary_redacts_malaysian_unit_address(self):
        cases = (
            "B-12-3, Residensi Sentral, Kuala Lumpur",
            "Level 12, Menara Sentral, Kuala Lumpur",
        )
        for address in cases:
            with self.subTest(address=address):
                finalized = bm._blind_finalize_generated_summary_text(
                    f"- Lives at {address}.",
                    f"Jane Example\n{address}",
                )
                self.assertEqual(
                    finalized,
                    "- Lives at [Address Redacted].",
                )

    def test_phone_redaction_preserves_long_unformatted_achievement_metric(self):
        self.assertEqual(
            bm._blind_redact_phone_candidates(
                "Processed 100000000 records annually."
            ),
            "Processed 100000000 records annually.",
        )
        self.assertEqual(
            bm._blind_redact_phone_candidates("Phone: 912345678"),
            "Phone: [Phone Redacted]",
        )

    def test_phone_redaction_uses_contact_context_and_preserves_grouped_metric(self):
        self.assertEqual(
            bm._blind_redact_phone_candidates("Contact number is 912345678"),
            "Contact number is [Phone Redacted]",
        )
        self.assertEqual(
            bm._blind_redact_phone_candidates(
                "Processed 100 000 000 records annually."
            ),
            "Processed 100 000 000 records annually.",
        )
        self.assertEqual(
            bm._blind_redact_phone_candidates(
                "Processed 100.000.000 records annually."
            ),
            "Processed 100.000.000 records annually.",
        )
        self.assertEqual(
            bm._blind_redact_phone_candidates(
                "Improved quality by 3.5% and reduced cost by -5%."
            ),
            "Improved quality by 3.5% and reduced cost by -5%.",
        )

    def test_finalize_generated_summary_redacts_bare_source_phone(self):
        finalized = bm._blind_finalize_generated_summary_text(
            "- Reach the candidate at 91234567.",
            "Jane Example\n91234567\nSenior Consultant",
        )
        self.assertEqual(
            finalized,
            "- Reach the candidate at [Phone Redacted].",
        )

    def test_finalize_generated_summary_redacts_short_labeled_phone(self):
        for label in ("M", "T"):
            with self.subTest(label=label):
                finalized = bm._blind_finalize_generated_summary_text(
                    "- Reach the candidate at 91234567.",
                    f"Jane Example\n{label}: 91234567\nSenior Consultant",
                )
                self.assertEqual(
                    finalized,
                    "- Reach the candidate at [Phone Redacted].",
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
