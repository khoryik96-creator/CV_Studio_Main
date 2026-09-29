"""Rule P1 on generated sentences, and the properties every summary must keep.

The hand-written cases in tests/fixtures/cv_guardrail_cases.json pin single
decisions. These tests sweep the combinations a reviewer would try next: every
way of stating the candidate's own pay (heading x joiner x amount x period) must
be removed, and every piece of pay-related work (work verb x object x amount x
period) must be kept. Across all cases and random combinations of them, the
filter must give the same answer when run again, the provider-text path and the
bullet path must agree, and a removal must never leave a lone "**".
All data is synthetic.
"""

import itertools
import json
from pathlib import Path
import random
import unittest

import cvstudio_cv_normalize as normalize

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / "tests" / "fixtures" / "cv_guardrail_cases.json").read_text(encoding="utf-8"))["cases"]

AMOUNTS = ["RM 9,000", "RM9k", "MYR 12,500", "SGD 8,000", "$85,000", "USD 90k", "₹ 18 LPA", "12 LPA",
           "RM 15,000.00", "S$7.5k", "PHP 60,000"]
PERIODS = ["", " per month", " a month", "/month", " monthly", " per annum", " p.a.", "/yr"]
OWN_HEADINGS = ["Current salary", "Expected salary", "Last drawn salary", "Asking salary", "Present salary",
                "Expected monthly salary", "My current salary", "Current package", "Expected package", "Current CTC",
                "Expected CTC", "Current basic salary", "Candidate's current salary", "Salary", "Monthly salary",
                "Basic salary", "Gross salary", "Take-home pay", "Salary expectation", "Expected remuneration",
                "Current remuneration", "Total compensation"]
JOINERS = [": ", " ", " of ", " is ", " - ", " around ", " approx. ", " about "]
WORK_VERBS = ["Managed", "Administered", "Oversaw", "Processed", "Reconciled", "Benchmarked", "Negotiated", "Led",
              "Owned", "Designed", "Reviewed", "Budgeted", "Forecasted", "Audited", "Handled", "Ran", "Planned",
              "Restructured", "Streamlined", "Supervised"]
WORK_OBJECTS = ["salaries of {a}{p} for 400 staff", "total compensation of {a} across APAC", "a {a} salary budget",
                "payroll of {a}{p} for the group", "compensation costs of {a}", "a salary and bonus pool of {a}",
                "commission payouts of {a}{p} to the sales team", "EPF contributions of {a}{p} for 900 employees",
                "remuneration packages worth {a} for 30 executives", "salary increments worth {a} for the firm"]


class GeneratedSalaryGuardrails(unittest.TestCase):
    def test_every_way_of_stating_own_pay_is_removed(self):
        missed = [
            text for text in (
                f"{heading}{joiner}{amount}{period}."
                for heading, joiner, amount, period in itertools.product(OWN_HEADINGS, JOINERS, AMOUNTS, PERIODS)
            )
            if normalize._cv_strip_pay_from_summary([text]) != []
        ]
        self.assertEqual(missed[:10], [])

    def test_pay_related_work_is_kept(self):
        dropped = [
            text for text in (
                f"{verb} {obj.format(a=amount, p=period)}."
                for verb, obj, amount, period in itertools.product(WORK_VERBS, WORK_OBJECTS, AMOUNTS[:8], PERIODS[:4])
            )
            if normalize._cv_strip_pay_from_summary([text]) != [text]
        ]
        self.assertEqual(dropped[:10], [])

    def test_filtering_is_stable_consistent_and_balanced(self):
        corpus = [
            bullet for case in CASES if case["kind"] == "summary_salary"
            for bullet in case["bullets"] if isinstance(bullet, str) and bullet.strip()
        ]
        rng = random.Random(7)
        base = corpus[:400]
        for _ in range(2000):
            first, second = rng.sample(base, 2)
            corpus.append(rng.choice([
                first.rstrip(".") + ". " + second, first + "; " + second, "**" + first + "** " + second,
                first + " **" + second + "**", "**" + first.rstrip(".") + "; " + second + "**",
            ]))
        for text in corpus:
            once = normalize._cv_strip_pay_from_summary([text])
            with self.subTest(text=text):
                # Run again -- as /generate-docx does after /generate-ai -- nothing more goes.
                self.assertEqual(normalize._cv_strip_pay_from_summary(once), once)
                # The provider-text path keeps exactly what the bullet path keeps.
                filtered, _ = normalize._cv_strip_pay_from_summary_text("- " + text)
                self.assertEqual([line[2:] for line in filtered.split("\n") if line.startswith("- ")], once)
                # A removal never leaves a lone "**".
                if once and once != [text] and text.count("**") % 2 == 0:
                    self.assertEqual(once[0].count("**") % 2, 0)


if __name__ == "__main__":
    unittest.main()
