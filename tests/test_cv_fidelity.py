"""Contract tests for the CV parse fidelity stage (cvstudio_cv_fidelity).

Pins the audit seam that would have caught the dropped-bullet regression:
the stage compares a reconciled/normalized CV against its source text and
flags dropped employers and material bullet loss -- while guaranteeing it
never mutates the parsed data it inspects. Pure functions, exercised directly.
"""

import copy
import unittest

import cvstudio_cv_fidelity as fid


def _source_table(companies):
    """A pipe-delimited employment table the source extractor recognises."""
    lines = ["EMPLOYMENT HISTORY", ""]
    year = 2010
    for company, title in companies:
        lines.append(f"Jan {year} - Dec {year + 1} | {company} | {title}")
        year += 2
    return "\n".join(lines)


def _parsed_from(companies, bullets_per_role=1):
    return {
        "work_experiences": [
            {
                "company": company,
                "roles": [
                    {
                        "title": title,
                        "bullets": [f"Did {title} thing {i}" for i in range(bullets_per_role)],
                    }
                ],
            }
            for company, title in companies
        ]
    }


SIX_EMPLOYERS = [
    ("Acme", "Software Engineer"),
    ("Globex", "Senior Engineer"),
    ("Initech", "Lead Engineer"),
    ("Umbrella", "Principal Engineer"),
    ("Wayne", "Engineering Manager"),
    ("Stark", "Director of Engineering"),
]


class EmployerFidelityTests(unittest.TestCase):
    def test_six_source_employers_all_present_is_ok(self):
        cv_text = _source_table(SIX_EMPLOYERS)
        parsed = _parsed_from(SIX_EMPLOYERS)
        report = fid.evaluate_cv_fidelity(parsed, cv_text)
        self.assertTrue(report["ok"])
        self.assertEqual(report["employers"]["source"], 6)
        self.assertEqual(report["employers"]["parsed"], 6)
        self.assertEqual(report["employers"]["missing"], [])

    def test_dropped_employer_is_flagged(self):
        cv_text = _source_table(SIX_EMPLOYERS)
        parsed = _parsed_from(SIX_EMPLOYERS[:-1])  # Stark dropped by the pipeline
        report = fid.evaluate_cv_fidelity(parsed, cv_text)
        self.assertFalse(report["ok"])
        self.assertEqual(report["employers"]["source"], 6)
        self.assertEqual(report["employers"]["parsed"], 5)
        self.assertIn("Stark", " ".join(report["employers"]["missing"]))

    def test_reworded_employer_still_counts_as_present(self):
        # "Globex Sdn Bhd" vs parsed "Globex" -- suffix stripping + token
        # overlap must treat them as the same employer, not a drop.
        cv_text = _source_table([("Globex Sdn Bhd", "Senior Engineer")])
        parsed = _parsed_from([("Globex", "Senior Engineer")])
        report = fid.evaluate_cv_fidelity(parsed, cv_text)
        self.assertEqual(report["employers"]["missing"], [])
        self.assertTrue(report["ok"])


class BulletFidelityTests(unittest.TestCase):
    def _cv_with_bullets(self, n):
        header = "EMPLOYMENT HISTORY\n\nJan 2020 - Dec 2021 | Acme | Software Engineer\n"
        return header + "\n".join(f"• Delivered project {i}" for i in range(n))

    def test_large_bullet_shortfall_is_flagged(self):
        cv_text = self._cv_with_bullets(11)
        parsed = _parsed_from([("Acme", "Software Engineer")], bullets_per_role=4)
        report = fid.evaluate_cv_fidelity(parsed, cv_text)
        self.assertTrue(report["bullets"]["shortfall"])
        self.assertFalse(report["ok"])
        self.assertEqual(report["bullets"]["source_estimate"], 11)
        self.assertEqual(report["bullets"]["parsed"], 4)

    def test_preserved_bullets_are_not_flagged(self):
        cv_text = self._cv_with_bullets(11)
        parsed = _parsed_from([("Acme", "Software Engineer")], bullets_per_role=11)
        report = fid.evaluate_cv_fidelity(parsed, cv_text)
        self.assertFalse(report["bullets"]["shortfall"])
        self.assertTrue(report["ok"])

    def test_small_cv_shortfall_is_not_flagged(self):
        # Below the source-bullet floor, a low count is not treated as loss.
        cv_text = self._cv_with_bullets(3)
        parsed = _parsed_from([("Acme", "Software Engineer")], bullets_per_role=0)
        report = fid.evaluate_cv_fidelity(parsed, cv_text)
        self.assertFalse(report["bullets"]["shortfall"])

    def test_bulleted_skills_section_does_not_inflate_source_count(self):
        # Bullets in SKILLS / EDUCATION sit outside the experience section and
        # must not count against work-history bullets, or a normal CV with a
        # bulleted skills list would falsely warn.
        cv_text = (
            "SKILLS\n"
            + "\n".join(f"- Skill {i}" for i in range(8))
            + "\n\nEMPLOYMENT HISTORY\n"
            + "Jan 2020 - Dec 2021 | Acme | Software Engineer\n"
            + "- Built the thing\n- Shipped the thing\n\n"
            + "EDUCATION\n- BSc, Somewhere\n- MSc, Elsewhere\n"
        )
        parsed = _parsed_from([("Acme", "Software Engineer")], bullets_per_role=2)
        report = fid.evaluate_cv_fidelity(parsed, cv_text)
        self.assertEqual(report["bullets"]["source_estimate"], 2)
        self.assertFalse(report["bullets"]["shortfall"])
        self.assertTrue(report["ok"])

    def test_no_experience_heading_disables_bullet_check(self):
        # Without a locatable experience section, the bullet check backs off
        # (source_estimate None, never flags) rather than risk a false positive.
        cv_text = "Some narrative CV.\n- a\n- b\n- c\n- d\n- e\n- f\n- g\n"
        parsed = _parsed_from([("Acme", "Engineer")], bullets_per_role=0)
        report = fid.evaluate_cv_fidelity(parsed, cv_text)
        self.assertIsNone(report["bullets"]["source_estimate"])
        self.assertFalse(report["bullets"]["scoped"])
        self.assertFalse(report["bullets"]["shortfall"])


class SafetyContractTests(unittest.TestCase):
    def test_evaluate_never_mutates_parsed(self):
        cv_text = _source_table(SIX_EMPLOYERS)
        parsed = _parsed_from(SIX_EMPLOYERS[:-1])
        before = copy.deepcopy(parsed)
        fid.evaluate_cv_fidelity(parsed, cv_text)
        self.assertEqual(parsed, before)

    def test_degenerate_inputs_do_not_raise(self):
        for parsed, cv_text in [
            ({}, ""),
            (None, None),
            ({"work_experiences": None}, "no table here"),
            ({"work_experiences": [None, {"roles": None}]}, ""),
        ]:
            report = fid.evaluate_cv_fidelity(parsed, cv_text)
            self.assertIn("ok", report)

    def test_summary_is_none_when_ok_and_string_when_not(self):
        ok_report = fid.evaluate_cv_fidelity(_parsed_from(SIX_EMPLOYERS), _source_table(SIX_EMPLOYERS))
        self.assertIsNone(fid.summarize_fidelity_warning(ok_report))

        bad_report = fid.evaluate_cv_fidelity(_parsed_from(SIX_EMPLOYERS[:-1]), _source_table(SIX_EMPLOYERS))
        summary = fid.summarize_fidelity_warning(bad_report)
        self.assertIsInstance(summary, str)
        self.assertIn("Stark", summary)


if __name__ == "__main__":
    unittest.main()
