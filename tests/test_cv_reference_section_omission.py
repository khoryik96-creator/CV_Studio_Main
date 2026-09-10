"""Tests for referees/references removal from the formatted CV.

A CV's referee block is contact data for third parties, so it has no place in the
document sent to a client. The AI parse prompt asks for it to be dropped, but its
catch-all "any other section" rule used to sweep it into a skills category, and
CV data parsed before this pass existed can still carry one. The removal is
therefore deterministic, and these tests pin both halves of it: every shape of a
referees heading goes, and a real skill whose name merely contains the word
"reference" stays.
"""

import re
from pathlib import Path
import unittest

from cvstudio_cv_reconcile import (
    _drop_reference_sections as drop,
    _reads_as_reference_heading as reads_as_heading,
)

_APP_SOURCE = (Path(__file__).resolve().parent.parent / "app.py").read_text(encoding="utf-8")
_CV_FORMAT_SOURCE = (
    Path(__file__).resolve().parent.parent / "vendor" / "cvstudio" / "cv-format.js"
).read_text(encoding="utf-8")


REFEREE_HEADINGS = [
    "References",
    "Reference",
    "Referees",
    "Referee",
    "REFERENCES",
    "referees",
    "Referee Details",
    "Reference Details",
    "Referee Contact Details",
    "Professional References",
    "Personal References",
    "Character References",
    "Work References",
    "Employment References",
    "Academic Referees",
    "Business Referees",
    "References & Referees",
    "Referees and References",
    "Reference Contacts",
    "References:",
    "References Available Upon Request",
    "Referees Available On Request",
    "Reference Information",
    "Referee List",
    "References Section",
]

# Labels that contain a reference word but name a discipline, not a referee.
KEPT_HEADINGS = [
    "Reference Data Management",
    "Reference Architecture",
    "Reference Data Governance",
    "Cross-Reference Checking",
    "References and Publications",
    "Credit Reference Analysis",
    "Self-Reference Resolution",
]

# Labels with no reference word at all, which the pass must never look at twice.
UNRELATED_HEADINGS = [
    "Skills",
    "Summary",
    "Contact Information",
    "Awards & Achievements",
    "Volunteer & Community",
    "Portfolio & Links",
    "Patents",
    "Publications",
    "Interests",
    "Professional Memberships",
    "",
]


class ReferenceHeadingDetection(unittest.TestCase):
    def test_every_referee_heading_shape_is_detected(self):
        for label in REFEREE_HEADINGS:
            with self.subTest(label=label):
                self.assertTrue(reads_as_heading(label))

    def test_reference_named_skills_are_not_referee_headings(self):
        for label in KEPT_HEADINGS:
            with self.subTest(label=label):
                self.assertFalse(reads_as_heading(label))

    def test_unrelated_headings_are_not_referee_headings(self):
        for label in UNRELATED_HEADINGS:
            with self.subTest(label=label):
                self.assertFalse(reads_as_heading(label))

    def test_non_string_labels_do_not_raise(self):
        for label in (None, 0, 12, [], {}, object()):
            with self.subTest(label=label):
                self.assertFalse(reads_as_heading(label))

    def test_a_label_wrapped_in_a_list_is_read_by_its_text(self):
        # Malformed, but a referees heading either way, and the browser mirror
        # stringifies it identically.
        self.assertTrue(reads_as_heading(["References"]))
        self.assertFalse(reads_as_heading(["Reference Data Management"]))


class DropReferenceSections(unittest.TestCase):
    def test_referee_category_is_removed_with_its_contact_details(self):
        parsed = {"skills": [
            {"category": "Technical Skills", "items": "Python, SQL"},
            {"category": "Referees", "items": "Jane Tan, Head of Ops, Acme Sdn Bhd, +60 12-345 6789, jane@acme.com"},
        ]}
        self.assertEqual(
            drop(parsed)["skills"],
            [{"category": "Technical Skills", "items": "Python, SQL"}],
        )

    def test_multiple_referee_categories_all_go(self):
        parsed = {"skills": [
            {"category": "References", "items": "Referee one"},
            {"category": "Summary", "items": "A seasoned operator."},
            {"category": "Referee Details", "items": "Referee two"},
        ]}
        self.assertEqual(
            [entry["category"] for entry in drop(parsed)["skills"]],
            ["Summary"],
        )

    def test_reference_named_skill_category_survives_with_its_items(self):
        parsed = {"skills": [
            {"category": "Reference Data Management", "items": "Golden record design\nData stewardship"},
        ]}
        self.assertEqual(
            drop(parsed)["skills"],
            [{"category": "Reference Data Management", "items": "Golden record design\nData stewardship"}],
        )

    def test_available_on_request_line_goes_from_a_kept_category(self):
        parsed = {"skills": [
            {"category": "Additional Information", "items": "Willing to travel\nReferences available upon request\nFull driving licence"},
        ]}
        self.assertEqual(
            drop(parsed)["skills"][0]["items"],
            "Willing to travel\nFull driving licence",
        )

    def test_available_on_request_line_goes_from_a_list_of_items(self):
        parsed = {"skills": [
            {"category": "Additional Information", "items": ["Willing to travel", "Referees available on request."]},
        ]}
        self.assertEqual(
            drop(parsed)["skills"][0]["items"],
            ["Willing to travel"],
        )

    def test_a_category_left_with_nothing_printable_is_removed(self):
        parsed = {"skills": [
            {"category": "Technical Skills", "items": "Python"},
            {"category": "Additional Information", "items": "References available upon request"},
        ]}
        self.assertEqual(
            [entry["category"] for entry in drop(parsed)["skills"]],
            ["Technical Skills"],
        )

    def test_every_on_request_phrasing_is_recognised(self):
        phrasings = [
            "References available upon request",
            "References available on request.",
            "Reference available upon request",
            "Referees available upon request",
            "Referee available on request!",
            "References are available upon request",
            "References will be provided on request",
            "Referees can be furnished upon request",
            "References shall be supplied on request",
            "  References available upon request  ",
            "REFERENCES AVAILABLE UPON REQUEST",
            "References available",
        ]
        for phrasing in phrasings:
            with self.subTest(phrasing=phrasing):
                parsed = {"skills": [{"category": "Interests", "items": "Hiking\n" + phrasing}]}
                self.assertEqual(drop(parsed)["skills"][0]["items"], "Hiking")

    def test_a_sentence_that_merely_mentions_a_reference_is_kept(self):
        keepers = [
            "Built the reference data platform available to all desks",
            "Available on request: a portfolio of past campaigns",
            "References to ISO 27001 controls throughout the rollout",
        ]
        for line in keepers:
            with self.subTest(line=line):
                parsed = {"skills": [{"category": "Achievements", "items": line}]}
                self.assertEqual(drop(parsed)["skills"][0]["items"], line)

    def test_other_sections_are_untouched(self):
        parsed = {
            "candidate": {"name": "Jane Tan", "email": "jane@example.com"},
            "work_experiences": [{"company": "Acme", "roles": [{"title": "Head of Ops", "bullets": ["Ran the team"]}]}],
            "education": [{"institution": "A University"}],
            "certifications": ["PMP (2019)"],
            "skills": [{"category": "References", "items": "Referee one"}],
        }
        result = drop(parsed)
        self.assertEqual(result["candidate"]["name"], "Jane Tan")
        self.assertEqual(result["work_experiences"][0]["company"], "Acme")
        self.assertEqual(result["education"], [{"institution": "A University"}])
        self.assertEqual(result["certifications"], ["PMP (2019)"])
        self.assertEqual(result["skills"], [])

    def test_malformed_input_is_returned_unchanged(self):
        for parsed in (None, "", 0, [], {"skills": None}, {"skills": "References"}, {}):
            with self.subTest(parsed=parsed):
                self.assertEqual(drop(parsed), parsed)

    def test_non_dict_skill_entries_survive(self):
        parsed = {"skills": ["a bare string", None, {"category": "References", "items": "x"}]}
        self.assertEqual(drop(parsed)["skills"], ["a bare string", None])

    def test_untouched_input_keeps_its_skills_list_identity(self):
        skills = [{"category": "Technical Skills", "items": "Python"}]
        parsed = {"skills": skills}
        self.assertIs(drop(parsed)["skills"], skills)


class PipelineWiring(unittest.TestCase):
    def test_parse_runs_the_pass(self):
        self.assertIn("parsed = _drop_reference_sections(parsed)", _APP_SOURCE)

    def test_generate_docx_runs_the_pass(self):
        # The second call site is what protects CV data parsed before the pass
        # existed, or edited by hand in the browser.
        self.assertIn("cv_data = _drop_reference_sections(cv_data)", _APP_SOURCE)

    def test_preview_mirrors_the_pass(self):
        self.assertIn("cvDropReferenceSkills(data.skills)", _CV_FORMAT_SOURCE)

    def test_prompt_omits_referees_entirely(self):
        self.assertIn("REFERENCES / REFEREES — OMIT ENTIRELY", _APP_SOURCE)

    def test_prompt_catch_all_no_longer_maps_references(self):
        catch_all = re.search(
            r"- Any other section that does not fit work_experiences[^\n]*",
            _APP_SOURCE,
        )
        self.assertIsNotNone(catch_all)
        self.assertNotIn("References", catch_all.group(0))

    def test_prompt_and_code_agree_on_keeping_reference_named_skills(self):
        self.assertIn("Reference Data Management", _APP_SOURCE)
        for label in ("Reference Data Management", "Reference Architecture"):
            self.assertFalse(reads_as_heading(label))


class PreviewAndCodeParity(unittest.TestCase):
    """The browser preview mirrors the Python pass, so the word lists must match."""

    def _js_list(self, name):
        match = re.search(name + r"\s*=\s*\[(.*?)\];", _CV_FORMAT_SOURCE, re.S)
        self.assertIsNotNone(match, name)
        return frozenset(re.findall(r"'([^']*)'", match.group(1)))

    def test_heading_word_lists_match(self):
        from cvstudio_cv_reconcile import _REFERENCE_HEADING_WORDS
        self.assertEqual(self._js_list("CV_REFERENCE_HEADING_WORDS"), _REFERENCE_HEADING_WORDS)

    def test_filler_word_lists_match(self):
        from cvstudio_cv_reconcile import _REFERENCE_HEADING_FILLER
        self.assertEqual(self._js_list("CV_REFERENCE_HEADING_FILLER"), _REFERENCE_HEADING_FILLER)

    def test_on_request_patterns_match(self):
        from cvstudio_cv_reconcile import _REFERENCE_ON_REQUEST_RE
        match = re.search(r"CV_REFERENCE_ON_REQUEST_RE\s*=\s*/(.*)/i;", _CV_FORMAT_SOURCE)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), _REFERENCE_ON_REQUEST_RE.pattern)


if __name__ == "__main__":
    unittest.main()
