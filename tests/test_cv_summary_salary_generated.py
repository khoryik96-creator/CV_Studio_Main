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
import time
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

    def test_other_ways_of_stating_own_pay_are_removed(self):
        with_period = ["The candidate is paid {a}{p}.", "He is paid {a}{p}.", "They are paid {a}{p}.",
                       "Receives {a}{p}.", "Makes {a}{p}.", "Gets {a}{p}.", "Currently drawing {a}{p} across base and allowances."]
        any_period = ["Seeking {a}.", "Asking for {a}.", "Current: {a}.", "On a package of {a}.",
                      "Total package {a} across base, bonus and allowances.", "Salary of {a} for the team lead role."]
        texts = [t.format(a=a, p=p) for t, a, p in itertools.product(with_period, AMOUNTS[:8], PERIODS[1:])]
        texts += [t.format(a=a) for t, a in itertools.product(any_period, AMOUNTS[:8])]
        # A pay statement's other clauses go with it.
        texts += [f"Current salary {a}; {tail}." for a, tail in itertools.product(
            AMOUNTS[:8], ["plus 2 months bonus", "RM 1,500 allowances", "excluding EPF", "negotiable", "expected RM 12k"])]
        missed = [text for text in texts if normalize._cv_strip_pay_from_summary([text]) != []]
        self.assertEqual(missed[:10], [])

    def test_words_that_look_like_currency_are_not_money(self):
        kept = [f"{verb} {thing} {figure} {rest}." for verb, thing, figure, rest in itertools.product(
            ["Expert in", "Built", "Maintained"], ["PHP", "Form", "Charms", "Perms"], ["7", "8", "16", "80"],
            ["salary and HR systems", "salary tax compliance", "payroll modules"])]
        dropped = [text for text in kept if normalize._cv_strip_pay_from_summary([text]) != [text]]
        self.assertEqual(dropped[:10], [])

    def test_a_fact_before_a_pay_sentence_stays(self):
        facts = ["Proficient in Python and C.", "Based in the U.S.", "Worked at Acme Co.", "Grade A.",
                 "Worked at Acme Sdn Bhd.", "Joined Contoso Ltd.", "Manages a team of 8.", "Improved margin by 5.5%.",
                 "Skilled in SQL etc.", "Holds a B.Sc.", "Joined in Sept."]
        pay = ["Expected salary RM 9k.", "Current salary RM 12,000.", "Last drawn salary MYR 8,500."]
        for fact, statement in itertools.product(facts, pay):
            with self.subTest(fact=fact, pay=statement):
                self.assertEqual(normalize._cv_strip_pay_from_summary([fact + " " + statement]), [fact])

    def test_more_labels_and_verbs_for_own_pay_are_removed(self):
        texts = [t.format(a=a, p=p) for t, a, p in itertools.product(
            ["Package: {a}{p}.", "Pay: {a}{p}.", "Income: {a}{p}.", "Expected wage {a}{p}.",
             "Current monthly income of {a}{p}.", "Gross {a}/month.", "Nett {a} per month.",
             "Candidate's current role pays {a}{p}.", "Looking for {a}{p}.", "Seeking a senior role with {a}{p}.",
             "Recruiter earning {a} monthly."], AMOUNTS[:8], ["", " per month", " per annum"])]
        missed = [text for text in texts if normalize._cv_strip_pay_from_summary([text]) != []]
        self.assertEqual(missed[:10], [])

    def test_recruiters_describing_the_roles_they_fill_are_kept(self):
        kept = [f"{who} {what} {amount}." for who, what, amount in itertools.product(
            ["Executive search consultant placing C-suite leaders", "Recruitment consultant specialising in placements",
             "Tech recruiter for roles", "Headhunter filling mandates", "Talent acquisition lead for vacancies"],
            ["with compensation above", "with salaries up to", "with a CTC of", "with packages above"],
            ["USD 500k", "RM 30k", "30 LPA", "SGD 250k"])]
        dropped = [text for text in kept if normalize._cv_strip_pay_from_summary([text]) != [text]]
        self.assertEqual(dropped[:10], [])

    def test_work_elsewhere_in_the_sentence_does_not_hide_pay(self):
        # Work is judged around the amount, so a work word in another part of the
        # sentence does not keep the candidate's pay.
        texts = [f"{fact}{joiner}{pay}." for fact, joiner, pay in itertools.product(
            ["Heads the revenue team", "Sales manager across APAC", "Finance Manager for the group",
             "Leads a budget of RM 5M", "Managed hiring for 40 staff"],
            [", ", " with "],
            ["salary RM 20k", "salary of USD 150,000", "a salary of RM 12,000 monthly"])]
        texts += [f"{fact}, earning {a} monthly." for fact, a in itertools.product(
            ["Finance Manager for the group", "Heads the revenue team"], AMOUNTS[:8])]
        leaked = [text for text in texts if any(
            a in "".join(normalize._cv_strip_pay_from_summary([text])) for a in AMOUNTS + ["USD 150,000", "RM 20k", "RM 12,000"])]
        self.assertEqual(leaked[:10], [])

    def test_still_more_ways_of_stating_own_pay_are_removed(self):
        texts = [t.format(a=a) for t, a in itertools.product(
            ["Salary per month: {a}.", "Salary in 2024 was {a}.", "Salary currently stands at {a}.", "Salary drawn: {a}.",
             "Earning {a}.", "Currently earning {a}.", "Takes home {a} monthly.", "Monthly gross {a}.",
             "Current base of {a} plus bonus.", "Basic {a} + allowance RM 1,000.", "Remuneration package worth {a} annually.",
             "Top performer earning {a} in commission annually."], AMOUNTS[:8])]
        texts += ["Salary RM 9 000.", "Salary: MYR 12 500 per month.", "Salary history: RM 5k (2019), RM 7k (2021)."]
        missed = [text for text in texts if normalize._cv_strip_pay_from_summary([text]) != []]
        self.assertEqual(missed[:10], [])

    def test_the_filter_stays_fast_on_hostile_input(self):
        # A long pasted or crafted line must not hang a request.
        for text in ["1," * 10000, "1." * 10000, "9" * 20000, "RM " * 7000, "1,1.1 " * 4000, "$" * 20000,
                     "RM1" * 7000, "Earning " + "a" * 20000 + " RM 9k monthly", ("x" * 50 + ", ") * 400,
                     "." * 40000, "!?" * 20000, "Sr. " * 20000, "A. " * 20000, "e.g. " * 20000,
                     # many pay phrases in one long clause, each judged by the words around it
                     "Managed salary RM 9k with " * 1000, "Led total compensation of RM 2M for 3 staff and " * 600,
                     "expected salary of new hires and " * 1000,
                     "Managed payroll with salary RM 9k for each employee and " * 600,
                     "Managed HR with salary RM 9k for the employee relations manager role and " * 600,
                     "Managed payroll with salary RM 9k for each employee " + "support " * 10000,
                     "earnings of " * 3000, "The candidate receives " * 1500]:
            with self.subTest(text=text[:20]):
                started = time.perf_counter()
                normalize._cv_strip_pay_from_summary([text])
                normalize._cv_strip_pay_from_summary_text("- " + text)
                self.assertLess(time.perf_counter() - started, 2.0)

    def test_explicit_earnings_and_candidate_receipts_are_removed(self):
        templates = ["Earnings of {a}{p}.", "Monthly earnings of {a}.", "Her earnings are {a}{p}.",
                     "His earnings are {a}{p}.", "The candidate receives {a}{p}.",
                     "She receives {a}{p}.", "He makes {a}{p}.", "The candidate gets {a}{p}.",
                     "Recruiter with earnings of {a}{p}."]
        missed = [text for text in (t.format(a=a, p=p) for t, a, p in
                  itertools.product(templates, AMOUNTS[:8], PERIODS[1:]))
                  if normalize._cv_strip_pay_from_summary([text]) != []]
        self.assertEqual(missed[:10], [])

    def test_pay_for_explicit_employee_recipients_stays(self):
        templates = ["Managed payroll with salary of {a} for each employee.",
                     "Processed payroll with a salary of {a} per employee.",
                     "Administered payroll with salary of {a} for a worker.",
                     "Reviewed payroll with salary of {a} for every employee."]
        dropped = [text for text in (t.format(a=a) for t, a in itertools.product(templates, AMOUNTS[:8]))
                   if normalize._cv_strip_pay_from_summary([text]) != [text]]
        self.assertEqual(dropped[:10], [])

    def test_explicit_business_earnings_and_receipts_stay(self):
        templates = ["Company earnings of {a} monthly.", "Business earnings of {a} monthly.",
                     "The candidate receives {a} per month in client fees.",
                     "She receives {a} monthly in revenue."]
        dropped = [text for text in (t.format(a=a) for t, a in itertools.product(templates, AMOUNTS[:8]))
                   if normalize._cv_strip_pay_from_summary([text]) != [text]]
        self.assertEqual(dropped[:10], [])

    def test_employee_role_pay_is_removed_but_real_recipients_stay(self):
        roles = ["employee relations manager role", "employee engagement role",
                 "worker support manager position", "employee-relations manager role",
                 "employee's liaison role", "employee health and safety manager role"]
        missed = [text for text in (
            f"{verb} HR with salary of {amount} for the {role}."
            for verb, amount, role in itertools.product(WORK_VERBS[:6], AMOUNTS[:8], roles)
        ) if normalize._cv_strip_pay_from_summary([text]) != []]
        self.assertEqual(missed[:10], [])
        recipients = ["each employee", "every worker", "each employee working on a client project",
                      "every worker assigned to a construction job", "each employee who works in a support role"]
        dropped = [text for text in (
            f"{verb} payroll with salary of {amount} for {recipient}."
            for verb, amount, recipient in itertools.product(WORK_VERBS[:6], AMOUNTS[:8], recipients)
        ) if normalize._cv_strip_pay_from_summary([text]) != [text]]
        self.assertEqual(dropped[:10], [])

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
