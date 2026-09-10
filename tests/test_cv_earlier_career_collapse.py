"""Tests for the Earlier Career grouping in cvstudio_cv_reconcile.

A real CV exposed two defects. A 2025 role that the source gave no dates was filed
under "Earlier Career" beside 2015 roles, losing its place in the timeline; and when the
model had already produced its own Earlier Career grouping, that grouping was collapsed
a second time, printing the heading three times and leaving the literal words "Earlier
Career" as a bullet.
"""

import copy
from pathlib import Path
import unittest

from cvstudio_cv_reconcile import (
    _attach_untitled_subsidiary_entries as attach,
    _collapse_incomplete_earlier_career as collapse,
)


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


_SOURCE = """
A&W MALAYSIA SDN BHD
Head of Operations, Special Projects
(February 2025 - August 2025)
- Led the nationwide rollout of the SPMH framework.
PM BRANDS SDN BHD (HALO DIM SUM)
- Developed the business proposal and rollout plan.
- Conducted market research and feasibility studies.
KGB HOLDINGS SDN BHD
Head of Operations - Business Partner
(October 2018 - February 2025)
- Led multi-site operations.
YBS AGRO PREMIERE SDN BHD
Business Development Executive/ Junior Chef
(October 2017 - August 2018)
- Created the signature product.
EARLIER CAREER
- Outlet Assistant Chef - BBQ Chicken Malaysia (2017)
- Commis - FIQ Gastronomy (2015)
"""


def _pipeline(parsed, source=_SOURCE):
    return collapse(attach(copy.deepcopy(parsed), source))["work_experiences"]


class SubsidiaryBlockTests(unittest.TestCase):
    """A sub-brand listed under a dated role belongs inside that role.

    The parent comes from the source CV, never from the model's ordering: the model
    moves such a block freely, and trusting its position filed a 2025 special project
    under a 2017 employer.
    """

    _A_AND_W = _entry("A&W Malaysia Sdn Bhd", "Feb 2025 to Aug 2025",
                      "Head of Operations, Special Projects",
                      ["Led the nationwide rollout of the SPMH framework."])
    _KGB = _entry("KGB Holdings Sdn Bhd", "Oct 2018 to Feb 2025",
                  "Head of Operations - Business Partner", ["Led multi-site operations."])
    _YBS = _entry("YBS Agro Premiere Sdn Bhd", "Oct 2017 to Aug 2018",
                  "Business Development Executive/ Junior Chef", ["Created the signature product."])
    _PM = _entry("PM Brands Sdn Bhd (Halo Dim Sum)", "", "",
                 ["Developed the business proposal and rollout plan.",
                  "Conducted market research and feasibility studies."])

    def _subsidiary_of(self, entries):
        for entry in _pipeline({"work_experiences": copy.deepcopy(entries)}):
            for role in entry.get("roles", []):
                for bullet in role.get("bullets", []):
                    if isinstance(bullet, dict):
                        return entry["company"], bullet
        return None, None

    def test_the_source_decides_the_parent_when_the_model_moves_the_block(self):
        # The model emitted the block last, after a 2017 employer. The source puts it
        # under A&W, and the source is what counts.
        parent, group = self._subsidiary_of(
            [self._A_AND_W, self._KGB, self._YBS, self._PM]
        )
        self.assertEqual(parent, "A&W Malaysia Sdn Bhd")
        self.assertEqual(group["heading"], "PM Brands Sdn Bhd (Halo Dim Sum)")

    def test_the_same_parent_when_the_model_keeps_it_in_place(self):
        parent, _group = self._subsidiary_of(
            [self._A_AND_W, self._PM, self._KGB, self._YBS]
        )
        self.assertEqual(parent, "A&W Malaysia Sdn Bhd")

    def test_it_is_not_promoted_to_its_own_employer_row(self):
        companies = [e["company"] for e in _pipeline(
            {"work_experiences": [self._A_AND_W, self._KGB, self._YBS, self._PM]})]
        self.assertNotIn("PM Brands Sdn Bhd (Halo Dim Sum)", companies)

    def test_the_host_role_keeps_its_own_bullets_first(self):
        entry = _pipeline({"work_experiences": [self._A_AND_W, self._PM, self._KGB]})[0]
        self.assertEqual(entry["roles"][0]["bullets"][0],
                         "Led the nationwide rollout of the SPMH framework.")

    def test_nothing_is_attached_without_source_text(self):
        # No source means no evidence. Leaving the block alone is the safe outcome;
        # guessing from list position is what caused the misattribution.
        companies = [e["company"] for e in _pipeline(
            {"work_experiences": [self._A_AND_W, self._KGB, self._YBS, self._PM]}, source="")]
        self.assertIn("PM Brands Sdn Bhd (Halo Dim Sum)", companies)

    def test_a_title_company_listing_line_is_not_absorbed(self):
        # "Outlet Assistant Chef - BBQ Chicken Malaysia" is one entry of a listing, not
        # a heading with bullets of its own.
        parent, group = self._subsidiary_of([
            self._A_AND_W, self._KGB, self._YBS,
            _entry("BBQ Chicken Malaysia", "", "", ["Ran the line.", "Trained staff."]),
        ])
        self.assertIsNone(parent)
        self.assertIsNone(group)

    def test_an_undated_entry_that_has_a_title_is_left_alone(self):
        companies = [e["company"] for e in _pipeline({"work_experiences": [
            self._A_AND_W,
            _entry("PM Brands Sdn Bhd (Halo Dim Sum)", "", "Head of Something",
                   ["Did A.", "Did B."]),
            self._KGB,
        ]})]
        self.assertIn("PM Brands Sdn Bhd (Halo Dim Sum)", companies)

    def test_an_earlier_career_grouping_is_never_absorbed(self):
        companies = [e["company"] for e in _pipeline({"work_experiences": [
            self._A_AND_W,
            _entry("Earlier Career", "", "",
                   ["Outlet Assistant Chef - BBQ Chicken Malaysia (2017)",
                    "Commis - FIQ Gastronomy (2015)"]),
        ]})]
        self.assertIn("Earlier Career", companies)

    def test_a_suffixed_earlier_career_grouping_is_also_recognised(self):
        companies = [e["company"] for e in _pipeline({"work_experiences": [
            self._A_AND_W,
            _entry("Earlier Career (Pre-2015)", "", "",
                   ["Commis - FIQ Gastronomy (2015)", "Trainee - Hotel (2014)"]),
        ]})]
        self.assertIn("Earlier Career (Pre-2015)", companies)

    def test_a_nested_group_inside_the_block_keeps_its_structure(self):
        block = _entry("PM Brands Sdn Bhd (Halo Dim Sum)", "", "", [])
        block["roles"] = [{"title": "", "date_range": "", "reason_for_leaving": "",
                           "bullets": [{"heading": "Key achievements",
                                        "bullets": ["Built the kiosk concept."]}]}]
        _parent, group = self._subsidiary_of([self._A_AND_W, self._KGB, block])
        self.assertIsInstance(group["bullets"][0], dict)
        self.assertEqual(group["bullets"][0]["heading"], "Key achievements")

    def test_a_host_role_whose_bullets_are_a_bare_string_keeps_them(self):
        host = _entry("A&W Malaysia Sdn Bhd", "Feb 2025 to Aug 2025", "Head of Operations")
        host["roles"] = [{"title": "Head of Operations", "date_range": "Feb 2025 to Aug 2025",
                          "reason_for_leaving": "", "bullets": "Led the nationwide rollout."}]
        entry = _pipeline({"work_experiences": [host, self._PM, self._KGB]})[0]
        self.assertIn("Led the nationwide rollout.", entry["roles"][0]["bullets"])


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


class SourceAnchorHardeningTests(unittest.TestCase):
    """Cases a review of the source-anchored attachment found."""

    _PM = _entry("PM Brands Sdn Bhd (Halo Dim Sum)", "", "",
                 ["Developed the business proposal.", "Conducted market research."])

    @staticmethod
    def _run(entries, source):
        return attach({"work_experiences": copy.deepcopy(entries)}, source)["work_experiences"]

    @staticmethod
    def _subsidiaries(entries):
        found = {}
        for entry in entries:
            for role in entry.get("roles", []):
                if not isinstance(role.get("bullets"), list):
                    continue
                for bullet in role["bullets"]:
                    if isinstance(bullet, dict):
                        found[bullet["heading"]] = entry["company"]
        return found

    def test_a_block_is_never_deleted_when_the_parent_has_no_role(self):
        # Dropping the child while refusing to attach it removed a company and all its
        # bullets from the CV outright.
        source = ("A&W MALAYSIA SDN BHD\nHead\n(Feb 2025 - Aug 2025)\n"
                  "PM BRANDS SDN BHD (HALO DIM SUM)\n- a\n- b\n")
        entries = self._run([
            {"company": "A&W Malaysia Sdn Bhd", "date_range": "Feb 2025 to Aug 2025", "roles": []},
            self._PM,
        ], source)
        self.assertIn("PM Brands Sdn Bhd (Halo Dim Sum)", [e["company"] for e in entries])
        self.assertIn("Developed the business proposal.", str(entries))

    def test_an_employer_named_in_a_profile_paragraph_is_not_the_parent(self):
        source = ("PROFILE Experienced leader at KGB Holdings Sdn Bhd and others.\n"
                  "A&W MALAYSIA SDN BHD\nHead\n(Feb 2025 - Aug 2025)\n- x\n"
                  "PM BRANDS SDN BHD (HALO DIM SUM)\n- a\n- b\n"
                  "KGB HOLDINGS SDN BHD\nHead\n(Oct 2018 - Feb 2025)\n- y\n")
        entries = self._run([
            _entry("A&W Malaysia Sdn Bhd", "Feb 2025 to Aug 2025", "Head", ["x"]),
            _entry("KGB Holdings Sdn Bhd", "Oct 2018 to Feb 2025", "Head", ["y"]),
            self._PM,
        ], source)
        self.assertEqual(
            self._subsidiaries(entries).get("PM Brands Sdn Bhd (Halo Dim Sum)"),
            "A&W Malaysia Sdn Bhd",
        )

    def test_a_heading_glued_to_the_previous_sentence_still_counts(self):
        # Extracted PDF text loses line breaks: "...new business concept.KGB HOLDINGS".
        source = ("A&W MALAYSIA SDN BHD\nHead\n(Feb 2025 - Aug 2025)\n"
                  "- Improved SOP enhancements.PM BRANDS SDN BHD (HALO DIM SUM)\n- a\n- b\n")
        entries = self._run([
            _entry("A&W Malaysia Sdn Bhd", "Feb 2025 to Aug 2025", "Head", ["x"]),
            self._PM,
        ], source)
        self.assertIn("PM Brands Sdn Bhd (Halo Dim Sum)", self._subsidiaries(entries))

    def test_punctuation_drift_in_the_company_name_still_matches(self):
        source = ("A&W MALAYSIA SDN BHD\nHead\n(Feb 2025 - Aug 2025)\n- x\n"
                  "PM BRANDS SDN BHD\n- a\n- b\n")
        entries = self._run([
            _entry("A&W Malaysia Sdn. Bhd.", "Feb 2025 to Aug 2025", "Head", ["x"]),
            _entry("PM Brands Sdn. Bhd.", "", "", ["a", "b"]),
        ], source)
        self.assertIn("PM Brands Sdn. Bhd.", self._subsidiaries(entries))

    def test_offsets_survive_a_length_changing_casefold(self):
        # casefold("\u00df") is "ss", so offsets taken from a casefolded copy no longer
        # line up with the text they index.
        source = ("STRA\u00dfE GMBH\nHead\n(2020 - 2022)\n- x\n"
                  "PM BRANDS SDN BHD\n- a\n- b\n")
        entries = self._run([
            _entry("Stra\u00dfe GmbH", "2020 to 2022", "Head", ["x"]),
            _entry("PM Brands Sdn Bhd", "", "", ["a", "b"]),
        ], source)
        self.assertEqual(
            self._subsidiaries(entries).get("PM Brands Sdn Bhd"), "Stra\u00dfe GmbH"
        )


class TrailingScanTests(unittest.TestCase):
    def test_bare_rows_above_a_described_entry_are_still_collapsed(self):
        # A described role keeps its own row, but must not halt the scan, or the bare
        # "| Company" rows above it stop being grouped.
        parsed = {"work_experiences": [
            _entry("KGB Holdings Sdn Bhd", "Oct 2018 to Feb 2025", "Head", ["Ran ops."]),
            _entry("Bare One", "", "Chef"),
            _entry("Bare Two", "", "Cook"),
            _entry("Described Role", "", "", ["Lots of detail here.", "And more detail."]),
        ]}
        companies = [e["company"] for e in collapse(copy.deepcopy(parsed))["work_experiences"]]
        self.assertEqual(companies, ["KGB Holdings Sdn Bhd", "Described Role", "Earlier Career"])


class TwoColumnExtractionTests(unittest.TestCase):
    """The app extracts PDFs with pdfplumber, which interleaves a sidebar column.

    Every earlier test in this file used clean synthetic text, so a rule that needed the
    block's heading to open a line or follow a sentence looked correct here and failed on
    the real document, where the heading lands mid-line behind sidebar text
    ("... (ERP, POS & HRIS) PM BRANDS SDN BHD"). This fixture is that shape.
    """

    @classmethod
    def setUpClass(cls):
        cls.source = (
            Path(__file__).resolve().parent / "fixtures" / "cv_two_column_pdfplumber.txt"
        ).read_text(encoding="utf-8")

    def _run(self, entries):
        return attach({"work_experiences": copy.deepcopy(entries)}, self.source)["work_experiences"]

    @staticmethod
    def _subsidiaries(entries):
        return {
            bullet["heading"]: entry["company"]
            for entry in entries
            for role in entry.get("roles", [])
            if isinstance(role.get("bullets"), list)
            for bullet in role["bullets"]
            if isinstance(bullet, dict)
        }

    def _entries(self, pm_last=True):
        base = [
            _entry("A&W Malaysia Sdn Bhd", "Feb 2025 to Aug 2025",
                   "Head of Operations, Special Projects", ["Led the nationwide rollout."]),
            _entry("KGB Holdings Sdn Bhd", "Oct 2018 to Feb 2025",
                   "Head of Operations - Business Partner", ["Led multi-site operations."]),
            _entry("YBS Agro Premiere Sdn Bhd", "Oct 2017 to Aug 2018",
                   "Business Development Executive/ Junior Chef", ["Created the product."]),
        ]
        pm = _entry("PM Brands Sdn Bhd (Halo Dim Sum)", "", "",
                    ["Developed the business proposal.", "Conducted market research."])
        return base + [pm] if pm_last else base[:1] + [pm] + base[1:]

    def test_the_block_attaches_to_the_employer_above_it_in_the_source(self):
        found = self._subsidiaries(self._run(self._entries(pm_last=True)))
        self.assertEqual(found.get("PM Brands Sdn Bhd (Halo Dim Sum)"), "A&W Malaysia Sdn Bhd")

    def test_the_same_parent_when_the_model_keeps_it_in_place(self):
        found = self._subsidiaries(self._run(self._entries(pm_last=False)))
        self.assertEqual(found.get("PM Brands Sdn Bhd (Halo Dim Sum)"), "A&W Malaysia Sdn Bhd")

    def test_it_is_not_left_as_its_own_employer_row(self):
        companies = [e["company"] for e in self._run(self._entries())]
        self.assertNotIn("PM Brands Sdn Bhd (Halo Dim Sum)", companies)

    def test_an_early_career_listing_line_is_still_refused(self):
        # "Outlet Assistant Chef - BBQ Chicken Malaysia" follows a dash in the source.
        entries = self._entries() + [
            _entry("BBQ Chicken Malaysia", "", "", ["Ran the line.", "Trained staff."])
        ]
        self.assertNotIn("BBQ Chicken Malaysia", self._subsidiaries(self._run(entries)))


class SourceSafetyCorrectiveTests(unittest.TestCase):
    def setUp(self):
        self.alpha = _entry("Alpha Operations", "2024 to Present", "Director",
                            ["Partnered with Project Delta on supplier onboarding."])
        self.beta = _entry("Beta Systems", "2020 to 2023", "Manager", ["Managed delivery."])
        self.child = _entry("Project Delta", "", "", ["Built the tool.", "Led implementation."])
        self.source = (
            "Alpha Operations\nDirector\n2024 - Present\n"
            "Partnered with Project Delta on supplier onboarding.\n"
            "Beta Systems\nManager\n2020 - 2023\n"
            "Project Delta\nBuilt the tool.\nLed implementation."
        )

    def run_attach(self, entries, source):
        return attach({"work_experiences": copy.deepcopy(entries)}, source)["work_experiences"]

    def test_actual_child_heading_wins_over_an_earlier_prose_mention(self):
        for entries in ([self.alpha, self.beta, self.child],
                        [self.child, self.beta, self.alpha]):
            with self.subTest(order=[entry["company"] for entry in entries]):
                result = self.run_attach(entries, self.source)
                parent = next(entry for entry in result if entry["company"] == "Beta Systems")
                self.assertEqual(parent["roles"][0]["bullets"][-1]["heading"], "Project Delta")
                alpha = next(entry for entry in result if entry["company"] == "Alpha Operations")
                self.assertEqual(alpha["roles"][0]["bullets"], self.alpha["roles"][0]["bullets"])

    def test_a_midline_mention_without_its_own_duties_is_not_an_attachment(self):
        source = ("Alpha Operations\nDirector\n2024 - Present\n"
                  "Partnered with Project Delta\n- Managed suppliers.\n- Supported operations.")
        result = self.run_attach([self.alpha, self.child], source)
        self.assertEqual(result, [self.alpha, self.child])

    def test_actual_duties_allow_a_genuine_midline_two_column_heading(self):
        source = ("Alpha Operations\nDirector\n2024 - Present\n- Managed suppliers.\n"
                  "Sidebar system skills Project Delta • Procurement\n"
                  "• Built the tool.\n• Led implementation.")
        result = self.run_attach([self.alpha, self.child], source)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["roles"][0]["bullets"][-1]["heading"], "Project Delta")

    def test_source_older_promotion_gets_the_project_not_the_newest_role(self):
        parent = copy.deepcopy(self.alpha)
        parent["roles"].append({"title": "Analyst", "date_range": "2020 to 2023",
                                "bullets": ["Analyst work."]})
        source = ("Alpha Operations\nDirector\n2024 - Present\nDirector work.\n"
                  "Analyst\n2020 - 2023\nProject Delta\nBuilt the tool.\nLed implementation.")
        for roles in (parent["roles"], list(reversed(parent["roles"]))):
            with self.subTest(titles=[role["title"] for role in roles]):
                parent["roles"] = roles
                result = self.run_attach([parent, self.child], source)[0]
                analyst = next(role for role in result["roles"] if role["title"] == "Analyst")
                director = next(role for role in result["roles"] if role["title"] == "Director")
                self.assertEqual(analyst["bullets"][-1]["heading"], "Project Delta")
                self.assertTrue(all(isinstance(item, str) for item in director["bullets"]))

    def test_unlocatable_or_duplicate_role_titles_leave_the_block_separate(self):
        for other in ("Missing Role", "Director"):
            with self.subTest(other=other):
                parent = copy.deepcopy(self.alpha)
                parent["roles"].append({"title": other, "date_range": "2020 to 2023", "bullets": []})
                result = self.run_attach([parent, self.child], self.source)
                self.assertEqual(len(result), 2)

    def test_source_job_metadata_overrides_missing_model_dates_and_title(self):
        for metadata in ("Consultant\n2020 - 2023\n", "(2020 - 2023)\n", "Consultant\n"):
            with self.subTest(metadata=metadata):
                source = ("Alpha Operations\nDirector\n2024 - Present\n- Led the team.\n"
                          "Project Delta\n" + metadata + "Built the tool.\nLed implementation.")
                self.assertEqual(self.run_attach([self.alpha, self.child], source),
                                 [self.alpha, self.child])

    def test_repeated_possible_blocks_do_not_pick_the_first_arbitrarily(self):
        source = self.source + "\nProject Delta\nBuilt the tool.\nLed implementation."
        self.assertEqual(self.run_attach([self.alpha, self.beta, self.child], source),
                         [self.alpha, self.beta, self.child])

    def test_attachment_is_idempotent(self):
        first = self.run_attach([self.alpha, self.beta, self.child], self.source)
        self.assertEqual(self.run_attach(first, self.source), first)


if __name__ == "__main__":
    unittest.main()
