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


class SmokeAndHygieneTests(unittest.TestCase):
    def test_symbols_present(self):
        for name in [
            "_blind_walk_strings", "_blind_add_mask_term", "_blind_collect_org_mask_terms",
            "_blind_replace_org_terms_in_text", "_blind_mask_org_terms_recursive",
            "_blind_postprocess_company_mentions", "_blind_restore_cv_bullet_structure",
        ]:
            self.assertTrue(callable(getattr(bm, name)), name)

    def test_module_does_not_import_app(self):
        self.assertNotIn("app", getattr(bm, "__dict__", {}))


if __name__ == "__main__":
    unittest.main()
