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
    the real document.

    This fixture interleaves the sidebar to the RIGHT of the block heading, which still
    leaves the heading opening its line. ``SidebarLeftTwoColumnTests`` below carries the
    other half -- the sidebar to its LEFT, so the heading lands mid-line -- because a
    later rule that only checked the line after the heading passed here and rejected the
    real CV.
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

    def test_unlocatable_or_duplicate_role_titles_fall_back_to_the_newest_role(self):
        # The source cannot say which promotion owns the block: one title it never
        # prints as a heading, or two roles sharing one heading. The employer is still
        # known, so the block goes to the newest role there. Declining would put the
        # sub-brand back on its own dateless row, which is the defect this pass exists
        # to remove and which shipped twice before.
        for other in ("Missing Role", "Director"):
            with self.subTest(other=other):
                parent = copy.deepcopy(self.alpha)
                parent["roles"].append({"title": other, "date_range": "2020 to 2023", "bullets": []})
                result = self.run_attach([parent, self.beta, self.child], self.source)
                self.assertNotIn("Project Delta", [entry["company"] for entry in result])
                host = next(entry for entry in result if entry["company"] == "Beta Systems")
                self.assertEqual(host["roles"][0]["bullets"][-1]["heading"], "Project Delta")
                self.assertEqual(
                    host["roles"][0]["bullets"][-1]["bullets"],
                    self.child["roles"][0]["bullets"],
                )

    def test_a_single_role_parent_is_unaffected_by_the_role_lookup(self):
        result = self.run_attach([self.alpha, self.beta, self.child], self.source)
        host = next(entry for entry in result if entry["company"] == "Beta Systems")
        self.assertEqual(len(host["roles"]), 1)
        self.assertEqual(host["roles"][0]["bullets"][-1]["heading"], "Project Delta")

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


class SidebarLeftTwoColumnTests(unittest.TestCase):
    """The shape pdfplumber really produces: the sidebar lands to the LEFT.

    ``POS & HRIS) PM BRANDS SDN BHD (HALO DIM SUM)`` -- so the block heading is
    mid-line, its first duty is two lines further down with a sidebar fragment
    wedged in between, and a referees block at the foot of the CV repeats the
    employer names. A rule that corroborated the heading from the single following
    line passed every other test in this file and still dropped this block.
    """

    @classmethod
    def setUpClass(cls):
        cls.source = (
            Path(__file__).resolve().parent / "fixtures" / "cv_two_column_sidebar_left.txt"
        ).read_text(encoding="utf-8")

    def _run(self, entries, source=None):
        return attach(
            {"work_experiences": copy.deepcopy(entries)},
            self.source if source is None else source,
        )["work_experiences"]

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

    def _pm(self):
        return _entry("PM Brands Sdn Bhd (Halo Dim Sum)", "", "", [
            "Developed the business proposal and rollout plan for the Halo Dim Sum kiosk concept.",
            "Conducted market research and feasibility studies to evaluate the commercial viability of the new business concept.",
        ])

    def _employers(self):
        return [
            _entry("A&W Malaysia Sdn Bhd", "Feb 2025 to Aug 2025",
                   "Head of Operations, Special Projects", [
                       "Led the nationwide rollout of the SPMH framework, including scheduling tools and KPI tracking across all A&W outlets.",
                       "Involved directly in cost-saving initiatives by analysing cost leakages and implementing operational improvements and SOP enhancements.",
                   ]),
            _entry("KGB Holdings Sdn Bhd", "Oct 2018 to Feb 2025",
                   "Head of Operations - Business Partner", [
                       "Promoted from Area Manager to Operations Manager and subsequently Head of Operations (Business Partner)",
                   ]),
            _entry("YBS Agro Premiere Sdn Bhd", "Oct 2017 to Aug 2018",
                   "Business Development Executive/ Junior Chef", [
                       "Created and launched the signature Nasi Lemak Sambal Strawberry.",
                   ]),
        ]

    def _entries(self, pm_last=True):
        base = self._employers()
        pm = self._pm()
        return base + [pm] if pm_last else base[:1] + [pm] + base[1:]

    def test_the_block_attaches_to_the_employer_above_it(self):
        for pm_last in (True, False):
            with self.subTest(pm_last=pm_last):
                found = self._subsidiaries(self._run(self._entries(pm_last)))
                self.assertEqual(
                    found.get("PM Brands Sdn Bhd (Halo Dim Sum)"), "A&W Malaysia Sdn Bhd"
                )

    def test_it_is_not_left_as_its_own_dateless_employer_row(self):
        companies = [entry["company"] for entry in self._run(self._entries())]
        self.assertNotIn("PM Brands Sdn Bhd (Halo Dim Sum)", companies)

    def test_the_blocks_own_bullets_survive_the_move(self):
        found = None
        for entry in self._run(self._entries()):
            for role in entry.get("roles", []):
                for bullet in role.get("bullets") or []:
                    if isinstance(bullet, dict) and "PM Brands" in bullet["heading"]:
                        found = bullet
        self.assertIsNotNone(found)
        self.assertEqual(found["bullets"], self._pm()["roles"][0]["bullets"])

    def test_a_wrapped_sidebar_word_to_the_right_does_not_refuse_the_heading(self):
        # The sidebar wraps mid-phrase, so the text beside a heading is a bare word
        # with no bullet glyph of its own.
        source = self.source.replace(
            "POS & HRIS) PM BRANDS SDN BHD (HALO DIM SUM)\n",
            "POS & HRIS) PM BRANDS SDN BHD (HALO DIM SUM) Management\n",
        )
        found = self._subsidiaries(self._run(self._entries(), source))
        self.assertEqual(
            found.get("PM Brands Sdn Bhd (Halo Dim Sum)"), "A&W Malaysia Sdn Bhd"
        )

    def test_a_name_inside_a_sentence_is_still_only_a_mention(self):
        # The tail carries on the same sentence, which is what prose looks like.
        source = self.source.replace(
            "POS & HRIS) PM BRANDS SDN BHD (HALO DIM SUM)\n",
            "POS & HRIS) PM BRANDS SDN BHD (HALO DIM SUM) on supplier onboarding.\n",
        )
        companies = [entry["company"] for entry in self._run(self._entries(), source)]
        self.assertIn("PM Brands Sdn Bhd (Halo Dim Sum)", companies)

    def test_the_referees_block_is_not_a_section_a_company_can_sit_in(self):
        # The foot of the CV lists employers as referee contacts, each one reading as a
        # clean heading. A sub-brand named there outranks the real mid-line heading on
        # looks alone, and the employer above it in the referees list is not the employer
        # the CV filed the block under.
        source = self.source + (
            "KGB HOLDINGS SDN BHD\n"
            "• Director - Someone Else (+6012 000 0002)\n"
            "PM BRANDS SDN BHD (HALO DIM SUM)\n"
            "• Director - A Third Person (+6012 000 0003)\n"
        )
        found = self._subsidiaries(self._run(self._entries(), source))
        self.assertEqual(
            found.get("PM Brands Sdn Bhd (Halo Dim Sum)"), "A&W Malaysia Sdn Bhd"
        )

    def test_an_accented_referees_heading_is_still_a_referees_block(self):
        # The heading reads "RÉFÉRENCES". Screening lines by an ASCII word match before
        # the accent-folding predicate would miss it, and the sub-brand repeated in the
        # referee list would then anchor to whichever employer sits above it there.
        for heading in ("RÉFÉRENCES", "Références", "Referee’s Details", "REFEREES"):
            with self.subTest(heading=heading):
                source = self.source.replace("REFERENCES\n", heading + "\n", 1) + (
                    "KGB HOLDINGS SDN BHD\n"
                    "• Director - Someone Else (+6012 000 0002)\n"
                    "PM BRANDS SDN BHD (HALO DIM SUM)\n"
                    "• Director - A Third Person (+6012 000 0003)\n"
                )
                found = self._subsidiaries(self._run(self._entries(), source))
                self.assertEqual(
                    found.get("PM Brands Sdn Bhd (Halo Dim Sum)"), "A&W Malaysia Sdn Bhd"
                )

    def test_a_block_cannot_borrow_a_later_employers_duty_as_evidence(self):
        # The model's duty text for the block appears only under KGB, after the next
        # employer heading. The span stops there, so the mention stays a mention.
        block = _entry("PM Brands Sdn Bhd (Halo Dim Sum)", "", "", [
            "Promoted from Area Manager to Operations Manager and subsequently Head of Operations (Business Partner)",
            "Ran the kiosk rollout.",
        ])
        entries = self._employers() + [block]
        companies = [entry["company"] for entry in self._run(entries)]
        self.assertIn("PM Brands Sdn Bhd (Halo Dim Sum)", companies)

    def test_a_parent_with_a_promotion_still_receives_the_block(self):
        # The source prints only the final title as a heading, so it cannot say which
        # promotion ran the project. The employer is still known.
        entries = self._employers() + [self._pm()]
        entries[0]["roles"].append({
            "title": "Senior Operations Manager",
            "date_range": "Jan 2024 to Jan 2025",
            "reason_for_leaving": "",
            "bullets": ["Ran the central region."],
        })
        result = self._run(entries)
        self.assertNotIn(
            "PM Brands Sdn Bhd (Halo Dim Sum)", [entry["company"] for entry in result]
        )
        self.assertEqual(
            self._subsidiaries(result).get("PM Brands Sdn Bhd (Halo Dim Sum)"),
            "A&W Malaysia Sdn Bhd",
        )

    def test_an_early_career_listing_line_is_still_refused(self):
        entries = self._entries() + [
            _entry("BBQ Chicken Malaysia", "", "", ["Ran the line.", "Trained staff."])
        ]
        self.assertNotIn("BBQ Chicken Malaysia", self._subsidiaries(self._run(entries)))

    def test_the_pass_is_idempotent_on_this_source(self):
        once = self._run(self._entries())
        self.assertEqual(self._run(once), once)

class SourceOwnershipAuditTests(unittest.TestCase):
    """Four ways the source could be overruled, found by audit on v24.6.405.

    Each one is reproduced here first, so the guard that fixes it has something
    that fails without it.
    """

    def _run(self, entries, source):
        return attach({"work_experiences": copy.deepcopy(entries)}, source)["work_experiences"]

    @staticmethod
    def _groups(entries):
        """{group heading: (employer, role title)} for every nested bullet group."""
        found = {}
        for entry in entries:
            for role in entry.get("roles") or []:
                for item in role.get("bullets") or []:
                    if isinstance(item, dict):
                        found[item.get("heading")] = (entry.get("company"), role.get("title"))
        return found

    # ── the model already nested the block ────────────────────────────────────
    NESTED_SOURCE = (
        "A&W MALAYSIA SDN BHD\nHead of Operations, Special Projects\n(February 2025 - August 2025)\n"
        "• Led the nationwide rollout.\n"
        "PM BRANDS SDN BHD (HALO DIM SUM)\n• Developed the business proposal.\n"
        "KGB HOLDINGS SDN BHD\nHead of Operations\n(October 2018 - February 2025)\n"
        "• Led multi-site operations.\n"
    )

    def _nested_entries(self, host_is_kgb=True):
        aw = _entry("A&W Malaysia Sdn Bhd", "Feb 2025 to Aug 2025",
                    "Head of Operations, Special Projects", ["Led the nationwide rollout."])
        kgb = _entry("KGB Holdings Sdn Bhd", "Oct 2018 to Feb 2025", "Head of Operations",
                     ["Led multi-site operations."])
        group = {"heading": "PM Brands Sdn Bhd (Halo Dim Sum)",
                 "bullets": ["Developed the business proposal."]}
        (kgb if host_is_kgb else aw)["roles"][0]["bullets"].append(group)
        return [aw, kgb]

    def test_a_group_nested_under_the_wrong_employer_moves(self):
        # The block never appears as an entry of its own, so the top-level loop sees
        # nothing to correct and Word exported it under KGB.
        found = self._groups(self._run(self._nested_entries(), self.NESTED_SOURCE))
        self.assertEqual(
            found.get("PM Brands Sdn Bhd (Halo Dim Sum)"),
            ("A&W Malaysia Sdn Bhd", "Head of Operations, Special Projects"),
        )

    def test_a_group_the_source_agrees_with_is_left_alone(self):
        found = self._groups(self._run(self._nested_entries(host_is_kgb=False), self.NESTED_SOURCE))
        self.assertEqual(
            found.get("PM Brands Sdn Bhd (Halo Dim Sum)"),
            ("A&W Malaysia Sdn Bhd", "Head of Operations, Special Projects"),
        )

    def test_moving_a_group_keeps_its_bullets_and_loses_nothing(self):
        result = self._run(self._nested_entries(), self.NESTED_SOURCE)
        aw = next(entry for entry in result if entry["company"] == "A&W Malaysia Sdn Bhd")
        kgb = next(entry for entry in result if entry["company"] == "KGB Holdings Sdn Bhd")
        group = next(item for item in aw["roles"][0]["bullets"] if isinstance(item, dict))
        self.assertEqual(group["bullets"], ["Developed the business proposal."])
        self.assertEqual(aw["roles"][0]["bullets"][0], "Led the nationwide rollout.")
        self.assertEqual(kgb["roles"][0]["bullets"], ["Led multi-site operations."])

    def test_moving_a_group_is_idempotent(self):
        once = self._run(self._nested_entries(), self.NESTED_SOURCE)
        self.assertEqual(self._run(once, self.NESTED_SOURCE), once)

    def test_a_group_the_source_cannot_place_stays_put(self):
        entries = self._nested_entries()
        entries[1]["roles"][0]["bullets"].append(
            {"heading": "Key Achievements", "bullets": ["Won an award."]}
        )
        found = self._groups(self._run(entries, self.NESTED_SOURCE))
        self.assertEqual(found.get("Key Achievements"), ("KGB Holdings Sdn Bhd", "Head of Operations"))

    # ── a role heading printed with a place or qualifier ──────────────────────
    def _promotion_entries(self):
        parent = _entry("Alpha Operations", "2020 to Present", "Director", ["Ran the group."])
        parent["roles"].append({"title": "Analyst", "date_range": "2020 to 2023",
                                "reason_for_leaving": "", "bullets": ["Ran the desk."]})
        child = _entry("Project Delta", "", "", ["Built the tool.", "Led implementation."])
        return [parent, child]

    def test_a_role_heading_with_a_qualifier_is_still_found(self):
        # "Analyst - Kuala Lumpur" is the same role. Failing to place it sent an
        # older project to the newer Director role through the fallback.
        for qualifier in ("- Kuala Lumpur", "– Kuala Lumpur", ", Kuala Lumpur",
                          "| Group Office", "(Operations)", "/ Central Region"):
            with self.subTest(qualifier=qualifier):
                source = (
                    "ALPHA OPERATIONS\nDirector\n(2024 - Present)\n• Ran the group.\n"
                    "Analyst " + qualifier + "\n(2020 - 2023)\n• Ran the desk.\n"
                    "PROJECT DELTA\n• Built the tool.\n• Led implementation.\n"
                )
                found = self._groups(self._run(self._promotion_entries(), source))
                self.assertEqual(found.get("Project Delta"), ("Alpha Operations", "Analyst"))

    def test_a_bare_role_heading_still_works(self):
        source = (
            "ALPHA OPERATIONS\nDirector\n(2024 - Present)\n• Ran the group.\n"
            "Analyst\n(2020 - 2023)\n• Ran the desk.\n"
            "PROJECT DELTA\n• Built the tool.\n• Led implementation.\n"
        )
        found = self._groups(self._run(self._promotion_entries(), source))
        self.assertEqual(found.get("Project Delta"), ("Alpha Operations", "Analyst"))

    def test_prose_after_a_role_heading_still_blocks_it(self):
        # A sentence continuing past the title is not that role's heading, so the
        # source cannot say, and the newest role takes the project.
        source = (
            "ALPHA OPERATIONS\nDirector\n(2024 - Present)\n• Ran the group.\n"
            "Analyst work covered the regional desk and its reporting line\n"
            "(2020 - 2023)\n• Ran the desk.\n"
            "PROJECT DELTA\n• Built the tool.\n• Led implementation.\n"
        )
        found = self._groups(self._run(self._promotion_entries(), source))
        self.assertEqual(found.get("Project Delta"), ("Alpha Operations", "Director"))

    # ── an employer printing its title on the same line ───────────────────────
    def test_a_same_line_job_title_is_not_sidebar_text(self):
        # The model dropped the title, so the entry looks untitled. Absorbing it
        # would delete a whole job from the CV.
        for title in ("Senior Manager", "Head of Delivery", "Executive Chef",
                      "Business Development Executive", "Lead Engineer"):
            with self.subTest(title=title):
                source = (
                    "ALPHA OPERATIONS\nDirector\n(2024 - Present)\n• Ran the group.\n"
                    "BETA SYSTEMS SDN BHD " + title + "\n"
                    "• Ran the delivery team.\n• Owned the roadmap.\n"
                )
                entries = [
                    _entry("Alpha Operations", "2024 to Present", "Director", ["Ran the group."]),
                    _entry("Beta Systems Sdn Bhd", "", "",
                           ["Ran the delivery team.", "Owned the roadmap."]),
                ]
                companies = [entry["company"] for entry in self._run(entries, source)]
                self.assertIn("Beta Systems Sdn Bhd", companies)

    def test_a_wrapped_sidebar_word_is_still_not_a_job_title(self):
        for word in ("Management", "Development", "Compliance", "Analytics"):
            with self.subTest(word=word):
                source = (
                    "ALPHA OPERATIONS\nDirector\n(2024 - Present)\n• Ran the group.\n"
                    "BETA SYSTEMS SDN BHD " + word + "\n"
                    "• Ran the delivery team.\n• Owned the roadmap.\n"
                )
                entries = [
                    _entry("Alpha Operations", "2024 to Present", "Director", ["Ran the group."]),
                    _entry("Beta Systems Sdn Bhd", "", "",
                           ["Ran the delivery team.", "Owned the roadmap."]),
                ]
                found = self._groups(self._run(entries, source))
                self.assertEqual(found.get("Beta Systems Sdn Bhd"),
                                 ("Alpha Operations", "Director"))

    # ── a referees section part-way through the document ──────────────────────
    MID_REFEREES_SOURCE = (
        "REFERENCES\nAvailable on request from the employers listed below.\n"
        "WORK EXPERIENCE\n"
        "ALPHA OPERATIONS\nDirector\n(2024 - Present)\n• Ran the group.\n"
        "PROJECT DELTA\n• Built the tool.\n• Led implementation.\n"
    )

    def _mid_referees_entries(self):
        return [
            _entry("Alpha Operations", "2024 to Present", "Director", ["Ran the group."]),
            _entry("Project Delta", "", "", ["Built the tool.", "Led implementation."]),
        ]

    def test_work_experience_after_a_referees_section_is_still_reachable(self):
        # Treating the first referees heading as a cut to the end of the document
        # made every employer below it invisible.
        found = self._groups(self._run(self._mid_referees_entries(), self.MID_REFEREES_SOURCE))
        self.assertEqual(found.get("Project Delta"), ("Alpha Operations", "Director"))

    def test_a_company_inside_the_referees_section_is_still_skipped(self):
        source = (
            "ALPHA OPERATIONS\nDirector\n(2024 - Present)\n• Ran the group.\n"
            "PROJECT DELTA\n• Built the tool.\n• Led implementation.\n"
            "BETA SYSTEMS\nManager\n(2018 - 2020)\n• Ran delivery.\n"
            "REFERENCES\n"
            "BETA SYSTEMS\n• Director - A Person (+6012 000 0001)\n"
            "PROJECT DELTA\n• Director - Another Person (+6012 000 0002)\n"
        )
        entries = [
            _entry("Alpha Operations", "2024 to Present", "Director", ["Ran the group."]),
            _entry("Beta Systems", "2018 to 2020", "Manager", ["Ran delivery."]),
            _entry("Project Delta", "", "", ["Built the tool.", "Led implementation."]),
        ]
        found = self._groups(self._run(entries, source))
        self.assertEqual(found.get("Project Delta"), ("Alpha Operations", "Director"))

    def test_a_trailing_referees_section_still_runs_to_the_end(self):
        source = self.MID_REFEREES_SOURCE + (
            "REFEREES\nPROJECT DELTA\n• Director - A Person (+6012 000 0003)\n"
        )
        found = self._groups(self._run(self._mid_referees_entries(), source))
        self.assertEqual(found.get("Project Delta"), ("Alpha Operations", "Director"))

if __name__ == "__main__":
    unittest.main()
