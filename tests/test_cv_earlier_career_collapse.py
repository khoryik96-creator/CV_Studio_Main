"""Tests for the Earlier Career grouping in cvstudio_cv_reconcile.

A real CV exposed two defects. A 2025 role that the source gave no dates was filed
under "Earlier Career" beside 2015 roles, losing its place in the timeline; and when the
model had already produced its own Earlier Career grouping, that grouping was collapsed
a second time, printing the heading three times and leaving the literal words "Earlier
Career" as a bullet.
"""

import copy
import unittest

from cvstudio_cv_reconcile import _collapse_incomplete_earlier_career as collapse


def _entry(company, date_range="", title="", bullets=()):
    roles = []
    if title or bullets:
        roles = [{
            "title": title,
            "date_range": date_range,
            "reason_for_leaving": "",
            "bullets": list(bullets),
        }]
    return {"company": company, "date_range": date_range, "roles": roles}


def _collapsed(parsed):
    return collapse(copy.deepcopy(parsed))["work_experiences"]


class DescribedRoleTests(unittest.TestCase):
    def test_an_undated_but_described_role_keeps_its_own_entry(self):
        parsed = {"work_experiences": [
            _entry("A&W Malaysia Sdn Bhd", "Feb 2025 to Aug 2025", "Head of Operations",
                   ["Led the nationwide rollout."]),
            _entry("PM Brands Sdn Bhd (Halo Dim Sum)", "", "",
                   ["Developed the business proposal and rollout plan.",
                    "Conducted market research and feasibility studies."]),
            _entry("Earlier Career", "", "",
                   ["Outlet Assistant Chef - BBQ Chicken Malaysia (2017)",
                    "Commis - FIQ Gastronomy (2015)"]),
        ]}
        companies = [entry["company"] for entry in _collapsed(parsed)]
        self.assertEqual(
            companies,
            ["A&W Malaysia Sdn Bhd", "PM Brands Sdn Bhd (Halo Dim Sum)", "Earlier Career"],
        )

    def test_the_described_role_keeps_its_bullets(self):
        parsed = {"work_experiences": [
            _entry("A&W Malaysia Sdn Bhd", "Feb 2025 to Aug 2025", "Head of Operations", ["Led it."]),
            _entry("PM Brands Sdn Bhd (Halo Dim Sum)", "", "",
                   ["Developed the business proposal.", "Conducted market research."]),
            _entry("Earlier Career", "", "", ["Commis - FIQ Gastronomy (2015)", "Chef - Cafe (2016)"]),
        ]}
        entry = _collapsed(parsed)[1]
        self.assertEqual(
            entry["roles"][0]["bullets"],
            ["Developed the business proposal.", "Conducted market research."],
        )

    def test_a_bare_early_career_listing_is_still_collapsed(self):
        parsed = {"work_experiences": [
            _entry("KGB Holdings Sdn Bhd", "Oct 2018 to Feb 2025", "Head of Operations", ["Ran ops."]),
            _entry("Tiny Boutique Cafe", "", "Business Development Executive"),
            _entry("BBQ Chicken Malaysia", "", "Outlet Assistant Chef"),
            _entry("FIQ Gastronomy", "", "Commis"),
        ]}
        collapsed = _collapsed(parsed)
        self.assertEqual(len(collapsed), 2)
        self.assertEqual(collapsed[1]["company"], "Earlier Career")
        self.assertEqual(len(collapsed[1]["roles"][0]["bullets"]), 3)

    def test_one_stray_bullet_is_not_enough_to_protect_an_entry(self):
        # A listing with a single trailing note is still a listing.
        parsed = {"work_experiences": [
            _entry("KGB Holdings Sdn Bhd", "Oct 2018 to Feb 2025", "Head of Operations", ["Ran ops."]),
            _entry("Tiny Boutique Cafe", "", "Business Development Executive", ["Opened the site."]),
            _entry("BBQ Chicken Malaysia", "", "Outlet Assistant Chef"),
        ]}
        collapsed = _collapsed(parsed)
        self.assertEqual([entry["company"] for entry in collapsed],
                         ["KGB Holdings Sdn Bhd", "Earlier Career"])


class ExistingBlockTests(unittest.TestCase):
    def test_an_existing_block_is_not_collapsed_into_itself(self):
        parsed = {"work_experiences": [
            _entry("KGB Holdings Sdn Bhd", "Oct 2018 to Feb 2025", "Head of Operations", ["Ran ops."]),
            _entry("Earlier Career", "", "", ["Commis - FIQ Gastronomy (2015)"]),
            _entry("BBQ Chicken Malaysia", "", "Outlet Assistant Chef"),
        ]}
        collapsed = _collapsed(parsed)
        block = collapsed[-1]
        self.assertEqual(block["company"], "Earlier Career")
        bullets = block["roles"][0]["bullets"]
        # The grouping's own name must never appear as one of its bullets.
        self.assertNotIn("Earlier Career", bullets)

    def test_the_heading_is_not_repeated_as_a_role_title(self):
        parsed = {"work_experiences": [
            _entry("KGB Holdings Sdn Bhd", "Oct 2018 to Feb 2025", "Head of Operations", ["Ran ops."]),
            _entry("BBQ Chicken Malaysia", "", "", ["Outlet Assistant Chef"]),
            _entry("FIQ Gastronomy", "", "", ["Commis"]),
        ]}
        block = _collapsed(parsed)[-1]
        self.assertEqual(block["company"], "Earlier Career")
        self.assertNotEqual(block["roles"][0]["title"], "Earlier Career")

    def test_matching_the_heading_is_not_case_sensitive(self):
        parsed = {"work_experiences": [
            _entry("KGB Holdings Sdn Bhd", "Oct 2018 to Feb 2025", "Head of Operations", ["Ran ops."]),
            _entry("EARLIER CAREER", "", "", ["Commis - FIQ Gastronomy (2015)"]),
            _entry("BBQ Chicken Malaysia", "", "Outlet Assistant Chef"),
        ]}
        bullets = _collapsed(parsed)[-1]["roles"][0]["bullets"]
        self.assertFalse(
            any(bullet.strip().casefold() == "earlier career" for bullet in bullets),
            bullets,
        )


class UnchangedBehaviourTests(unittest.TestCase):
    def test_a_fully_dated_history_is_untouched(self):
        parsed = {"work_experiences": [
            _entry("A", "2020 to 2022", "Role A", ["Did A."]),
            _entry("B", "2018 to 2020", "Role B", ["Did B."]),
        ]}
        self.assertEqual(_collapsed(parsed), parsed["work_experiences"])

    def test_an_all_undated_history_is_left_alone(self):
        parsed = {"work_experiences": [
            _entry("A", "", "Role A"),
            _entry("B", "", "Role B"),
        ]}
        self.assertEqual(_collapsed(parsed), parsed["work_experiences"])

    def test_a_single_trailing_undated_entry_is_left_alone(self):
        parsed = {"work_experiences": [
            _entry("A", "2020 to 2022", "Role A", ["Did A."]),
            _entry("B", "", "Role B"),
        ]}
        self.assertEqual(_collapsed(parsed), parsed["work_experiences"])


if __name__ == "__main__":
    unittest.main()
