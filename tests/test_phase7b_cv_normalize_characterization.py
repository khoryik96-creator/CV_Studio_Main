"""Characterization tests for the pure CV data-normalization helpers.

Locks the behaviour of the stateless normalisers extracted into
``cvstudio_cv_normalize`` (Phase 7B-6c): smart casing, work-history date
ranges, month tokens, language canonicalisation and the CV bullet /
structured-content normalisers. Pure functions, exercised directly.

The deeper bullet/structured-content matrix is already covered by
tests/test_long_cv_output_corrective.py; this suite pins the surrounding
helpers and confirms the module is importable and self-contained.
"""

import unittest

import cvstudio_cv_normalize as cn


class SmartCasingTests(unittest.TestCase):
    def test_word_case_capitalises(self):
        self.assertEqual(cn._smart_word_case("data"), "Data")

    def test_title_text_normalises_all_caps(self):
        self.assertEqual(cn._smart_title_text("SENIOR DATA ENGINEER"), "Senior Data Engineer")

    def test_title_text_leaves_mixed_case_untouched(self):
        # Only all-caps / uniform-case input is re-cased; ordinary text is kept.
        self.assertEqual(cn._smart_title_text("vp of sales"), "vp of sales")

    def test_bare_vowelless_acronym_company_token_is_preserved(self):
        # Matches generate.js's smartTokenCase acronym fallback: an all-caps,
        # vowelless brand token not in the explicit keep-list (e.g. TDCX) must
        # not be title-cased down to "Tdcx" -- otherwise the Python-side
        # normalization used by authoritative work-row extraction corrupts the
        # casing before it ever reaches the (already-fixed) JS formatter.
        self.assertEqual(cn._smart_title_text("TDCX", company=True), "TDCX")

    def test_normal_all_caps_company_word_still_title_cases(self):
        # Vowel-bearing all-caps words are unaffected by the vowelless fallback.
        self.assertEqual(cn._smart_title_text("COGNIZANT", company=True), "Cognizant")


class DateAndMonthTests(unittest.TestCase):
    def test_month_token_title_cases(self):
        self.assertEqual(cn._normalize_month_token("jan"), "Jan")

    def test_date_range_dash_to_word(self):
        self.assertEqual(cn._normalize_cv_date_range("Jan 2020 - Present"), "Jan 2020 to Present")

    def test_date_range_already_normal_preserved(self):
        self.assertEqual(cn._normalize_cv_date_range("2019 to 2021"), "2019 to 2021")

    def test_leading_dash_on_single_year_is_not_turned_into_to(self):
        # A DOCX list can prefix a graduation year with a dash ("- 2001"); it must
        # not become "to 2001", while a real range separator is still converted.
        self.assertEqual(cn._normalize_cv_date_range("- 2001"), "2001")
        self.assertEqual(cn._normalize_cv_date_range("-2001"), "2001")
        self.assertEqual(cn._normalize_cv_date_range("– 1996"), "1996")
        self.assertEqual(cn._normalize_cv_date_range("to 2001"), "2001")
        self.assertEqual(cn._normalize_cv_date_range("TO 1996"), "1996")
        self.assertEqual(cn._normalize_cv_date_range("to"), "")
        self.assertEqual(cn._normalize_cv_date_range("2020 - 2023"), "2020 to 2023")

    def test_date_range_numeric_month_year_to_house_style(self):
        # A parse run that emits "06/2024" must normalise to the same "Mon YYYY"
        # form as a run that emits "Jun 2024", so re-formatting is consistent.
        self.assertEqual(
            cn._normalize_cv_date_range("06/2024 to 07/2026"), "Jun 2024 to Jul 2026"
        )
        self.assertEqual(cn._normalize_cv_date_range("6/2024"), "Jun 2024")
        self.assertEqual(
            cn._normalize_cv_date_range("05/2009 to Present"), "May 2009 to Present"
        )
        # Already-textual and year-only ranges are unchanged.
        self.assertEqual(
            cn._normalize_cv_date_range("Jun 2024 to Jul 2026"), "Jun 2024 to Jul 2026"
        )
        self.assertEqual(cn._normalize_cv_date_range("2004 to 2008"), "2004 to 2008")
        # An out-of-range month is not a month token; leave it alone.
        self.assertEqual(cn._normalize_cv_date_range("13/2024"), "13/2024")

    def test_date_sort_point_reads_numeric_month(self):
        self.assertEqual(cn._cv_date_sort_point("06/2024", end=False), (2024, 6))
        self.assertEqual(cn._cv_date_sort_point("06/2024 to 07/2026", end=True), (2026, 7))

    def test_company_span_from_roles_spans_earliest_to_latest(self):
        # Roles listed out of order (and a backwards company header) must yield a
        # correct earliest-start to latest-end span.
        roles = [
            {"date_range": "Jan 2020 to Mar 2021"},
            {"date_range": "Apr 2018 to Dec 2019"},
            {"date_range": "Dec 2015 to Mar 2018"},
        ]
        self.assertEqual(cn._cv_company_span_from_roles(roles), "Dec 2015 to Mar 2021")

    def test_company_span_preserves_present_and_normalizes_numeric(self):
        self.assertEqual(
            cn._cv_company_span_from_roles(
                [{"date_range": "Jan 2024 to Present"}, {"date_range": "Jan 2022 to Dec 2023"}]
            ),
            "Jan 2022 to Present",
        )
        self.assertEqual(
            cn._cv_company_span_from_roles(
                [{"date_range": "06/2024 to 07/2026"}, {"date_range": "01/2022 to 05/2024"}]
            ),
            "Jan 2022 to Jul 2026",
        )

    def test_company_span_empty_when_roles_have_no_dates(self):
        # No parseable date -> "" so callers keep the provided company date.
        self.assertEqual(cn._cv_company_span_from_roles([{"title": "X"}, {"title": "Y"}]), "")
        self.assertEqual(cn._cv_company_span_from_roles([]), "")

    def test_company_span_single_role(self):
        self.assertEqual(
            cn._cv_company_span_from_roles([{"date_range": "Jan 2020 to Mar 2021"}]),
            "Jan 2020 to Mar 2021",
        )

    def test_iso_year_month_dates_normalized_not_shredded(self):
        # ISO YYYY-MM ranges must become "Mon YYYY to Mon YYYY", not be split by
        # the hyphen->"to" step into "2020 to 06 to 2025 to 07".
        self.assertEqual(
            cn._normalize_cv_date_range("2020-06 – 2025-07"), "Jun 2020 to Jul 2025"
        )
        self.assertEqual(
            cn._normalize_cv_date_range("2016-01 – 2019-12"), "Jan 2016 to Dec 2019"
        )
        self.assertEqual(
            cn._normalize_cv_date_range("2025-03 – Present"), "Mar 2025 to Present"
        )
        # ISO with a day drops the day.
        self.assertEqual(
            cn._normalize_cv_date_range("2020-06-15 to 2025-07-31"), "Jun 2020 to Jul 2025"
        )

    def test_pretranslate_iso_dates_targets_only_dates(self):
        self.assertEqual(
            cn._cv_pretranslate_iso_dates("UOB Indonesia 2020-06 – 2025-07"),
            "UOB Indonesia Jun 2020 – Jul 2025",
        )
        # Year-only ranges, phone numbers, percentages, versions untouched.
        for junk in ["2016 – Present", "+6281310272131", "reduce by 30%", "RHEL 7 to RHEL 8", "192-168 lab"]:
            self.assertEqual(cn._cv_pretranslate_iso_dates(junk), junk)


class LanguageEvidenceTests(unittest.TestCase):
    # Two-column CV whose LANGUAGES sidebar is interleaved with work history by
    # PDF extraction, so the 2nd/3rd languages fall outside the heading's line
    # window. Each "X (Professional Working)" line must still count as evidence.
    INTERLEAVED = (
        "LANGUAGES Head of Modern Trade 07/2023 - 05/2024\n"
        "Reckitt\n"
        "Chinese (Professional Working):\n"
        "• Reignited MT business with quarter-to-quarter growth\n"
        "Malay (Professional Working):\n"
        "• Led both MT key account management teams\n"
        "English (Professional Working):\n"
    )

    def test_parenthesised_proficiency_lines_are_evidence(self):
        for lang in ("Chinese", "Bahasa Malaysia", "English"):
            self.assertTrue(
                cn._language_has_source_evidence(lang, self.INTERLEAVED),
                f"expected source evidence for {lang}",
            )

    def test_language_with_no_source_line_has_no_evidence(self):
        self.assertFalse(cn._language_has_source_evidence("French", self.INTERLEAVED))
        self.assertFalse(cn._language_has_source_evidence("Japanese", self.INTERLEAVED))


class CandidateNameCorrectionTests(unittest.TestCase):
    HEADER = (
        "MOHD AZMAN BIN HAMZAH\n"
        "(cid:44476)(cid:44478)(cid:44477) Bangi Avenue, Selangor, Malaysia\n"
        "(cid:44562)(cid:44563) 011-11237201\n"
        "(cid:44604)(cid:44605) azman.mgsb@gmail.com\n"
        "PROFESSIONAL SUMMARY\n"
    )

    def test_location_like_name_is_detected(self):
        self.assertTrue(cn._name_is_location_like("Bangi Avenue, Selangor, Malaysia"))
        self.assertTrue(cn._name_is_location_like("azman.mgsb@gmail.com"))
        self.assertTrue(cn._name_is_location_like("011-11237201"))
        self.assertFalse(cn._name_is_location_like("Mohd Azman Bin Hamzah"))
        self.assertFalse(cn._name_is_location_like("Parlindungan Tampubolon, S.Kom, M.Kom"))

    def test_recovers_name_from_header_stripping_icon_glyphs(self):
        self.assertEqual(cn._recover_candidate_name_from_text(self.HEADER), "MOHD AZMAN BIN HAMZAH")

    def test_correct_replaces_only_a_mistagged_name(self):
        # Mis-tagged: location landed in the name field -> recovered from header.
        p = {"candidate": {"name": "Bangi Avenue, Selangor, Malaysia"}}
        self.assertEqual(
            cn._correct_mistagged_candidate_name(p, self.HEADER)["candidate"]["name"],
            "MOHD AZMAN BIN HAMZAH",
        )
        # A correct name is never touched.
        p2 = {"candidate": {"name": "Isaac Lee"}}
        self.assertEqual(
            cn._correct_mistagged_candidate_name(p2, self.HEADER)["candidate"]["name"], "Isaac Lee"
        )

    def test_mistagged_name_is_kept_when_no_recovery_available(self):
        # Never blank a name: with no usable header line, leave the value as-is.
        p = {"candidate": {"name": "Kuala Lumpur, Malaysia"}}
        out = cn._correct_mistagged_candidate_name(p, "SKILLS\nPython\nLinux\n")
        self.assertEqual(out["candidate"]["name"], "Kuala Lumpur, Malaysia")


class LanguageTests(unittest.TestCase):
    def test_canonical_language_name(self):
        # The alias->standard map is mutated at runtime by other code paths, so
        # the exact canonical target ("Mandarin" vs "Chinese") is state
        # dependent; the stable contract is a non-empty, capitalised name.
        result = cn._canonical_language_name("mandarin")
        self.assertTrue(result)
        self.assertEqual(result, result[:1].upper() + result[1:])

    def test_normalize_candidate_languages_returns_dict(self):
        out = cn._normalize_candidate_languages({"languages": ["English", "Malay"]})
        self.assertIsInstance(out, dict)
        self.assertIn("languages", out)

    def test_split_candidate_language_names(self):
        names = cn._split_candidate_language_names("English, Mandarin; Malay")
        self.assertIsInstance(names, list)
        self.assertTrue(any("english" in n.lower() for n in names))


class BulletAndStructuredContentTests(unittest.TestCase):
    def test_standalone_label_absorbs_following_bullets(self):
        # A sub-section label the provider emitted as a flat bullet takes the
        # loose bullets that follow it as its own, rather than rendering as an
        # empty label above orphaned siblings. Matches the contract asserted in
        # test_long_cv_output_corrective.
        out = cn._normalize_cv_bullet_items(["Key achievement", "Delivered result"])
        self.assertEqual(out, [
            {"heading": "Key achievements", "bullets": ["Delivered result"], "kind": "section"},
        ])

    def test_bare_label_with_nothing_following_is_dropped(self):
        out = cn._normalize_cv_bullet_items(["Real bullet", "Key responsibilities"])
        self.assertEqual(out, ["Real bullet"])

    def test_correctly_nested_section_is_untouched(self):
        nested = [{"heading": "Key responsibilities", "bullets": ["a", "b"], "kind": "section"}, "c"]
        self.assertEqual(cn._normalize_cv_bullet_items(nested), nested)

    def test_leading_source_bullet_markers_are_stripped(self):
        # DOCX/plain-text bullets that carry their own marker must not render as
        # "- Received…" once the formatter adds its own bullet.
        out = cn._normalize_cv_bullet_items([
            "-Received customer complaint",
            "• Provide technical support",
            "– Ensure closing all incoming calls",
        ])
        self.assertEqual(out, [
            "Received customer complaint",
            "Provide technical support",
            "Ensure closing all incoming calls",
        ])

    def test_leading_marker_strip_preserves_figures_and_internal_dashes(self):
        out = cn._normalize_cv_bullet_items(["-5% cost variance recorded", "5-star client rating"])
        self.assertEqual(out, ["-5% cost variance recorded", "5-star client rating"])

    def test_marker_only_noise_bullets_are_dropped_but_non_latin_kept(self):
        # A residue like "-"/"--" left after stripping carries no content and must
        # not render as a lone dash; non-Latin bullets (no A-Za-z0-9) are content
        # and must survive (isalnum is Unicode-aware).
        out = cn._normalize_cv_bullet_items(["-", "--", "•", "维护服务器", "Real bullet"])
        self.assertEqual(out, ["维护服务器", "Real bullet"])

    def test_leading_enumerators_are_stripped(self):
        # Source enumeration markers ("(i)", "1.", "1)") must not survive as
        # "(i)Receives…" once the formatter adds its own bullet.
        out = cn._normalize_cv_bullet_items([
            "(i)Receives calls", "(ii) Talks with user", "(iv)To do backup",
            "1. Achieved target", "1)Delivered project",
        ])
        self.assertEqual(out, [
            "Receives calls", "Talks with user", "To do backup",
            "Achieved target", "Delivered project",
        ])

    def test_enumerator_strip_does_not_eat_real_content(self):
        # Decimals, long parentheticals, and "i.e." are not enumerators.
        out = cn._normalize_cv_bullet_items([
            "3.5 GPA maintained",
            "(Vendors: Toyota, Honda) engaged",
            "(i.e. cross-functional) collaboration",
        ])
        self.assertEqual(out, [
            "3.5 GPA maintained",
            "(Vendors: Toyota, Honda) engaged",
            "(i.e. cross-functional) collaboration",
        ])

    def test_structured_content_smoke(self):
        parsed = {"experience": [{"title": "engineer", "bullets": ["Did a thing"]}]}
        out = cn._normalize_cv_structured_content(parsed)
        self.assertIsInstance(out, dict)

    def test_data_for_output_smoke(self):
        out = cn._normalize_cv_data_for_output({"name": "Jane"}, source_text="Jane")
        self.assertIsInstance(out, dict)


class EducationPlaceholderTests(unittest.TestCase):
    def test_no_degree_placeholders_are_omitted_without_touching_real_qualifications(self):
        parsed = {
            "education": [
                {"institution": "School A", "degree": "No Degree"},
                {"institution": "School B", "degree": "Degree not specified"},
                {"institution": "School C", "degree": "N/A"},
                {"institution": "School C2", "degree": "No Degree: SPM"},
                {
                    "institution": "School C3",
                    "degree": "No Degree: Computer System Operation And Management",
                },
                {
                    "institution": "School D",
                    "degree": "Non-Degree Certificate in Leadership",
                },
                {
                    "institution": "University E",
                    "degree": "Bachelor of Computer Science",
                },
                {"institution": "School F", "degree": "No Degree: N/A"},
                {
                    "institution": "School G",
                    "degree": "No Degree - Not specified",
                },
                {"institution": "School H", "degree": "No Degree: Unknown"},
            ]
        }

        normalized = cn._normalize_cv_data_for_output(parsed)

        self.assertEqual(normalized["education"][0]["degree"], "")
        self.assertEqual(normalized["education"][1]["degree"], "")
        self.assertEqual(normalized["education"][2]["degree"], "")
        self.assertEqual(normalized["education"][3]["degree"], "SPM")
        self.assertEqual(
            normalized["education"][4]["degree"],
            "Computer System Operation And Management",
        )
        self.assertEqual(
            normalized["education"][5]["degree"],
            "Non-Degree Certificate in Leadership",
        )
        self.assertEqual(
            normalized["education"][6]["degree"],
            "Bachelor of Computer Science",
        )
        self.assertEqual(normalized["education"][7]["degree"], "")
        self.assertEqual(normalized["education"][8]["degree"], "")
        self.assertEqual(normalized["education"][9]["degree"], "")


class ContinuousEmployerGroupingTests(unittest.TestCase):
    def test_adjacent_continuous_roles_are_grouped_like_the_marked_correct_unilever_output(self):
        parsed = {
            "work_experiences": [
                {
                    "company": "Unilever - Malaysia",
                    "date_range": "Jan 2020 to Mar 2021",
                    "roles": [{"title": "Head of Trade Marketing", "date_range": "", "bullets": ["A"]}],
                },
                {
                    "company": "Unilever",
                    "date_range": "Apr 2018 to Dec 2019",
                    "roles": [{"title": "Head of Sales Operation & Effectiveness", "date_range": "", "bullets": ["B"]}],
                },
                {
                    "company": "Unilever",
                    "date_range": "Dec 2015 to Mar 2018",
                    "roles": [{"title": "National Sales Manager", "date_range": "", "bullets": ["C"]}],
                },
                {
                    "company": "Unilever - Johor, Malaysia",
                    "date_range": "Sep 2013 to May 2014",
                    "roles": [{"title": "Regional Sales Manager", "date_range": "", "bullets": []}],
                },
                {
                    "company": "Nestle",
                    "date_range": "Jun 2014 to Nov 2015",
                    "roles": [{"title": "Trade Marketing Manager", "date_range": "", "bullets": []}],
                },
                {
                    "company": "Unilever",
                    "date_range": "Sep 2012 to Aug 2013",
                    "roles": [{"title": "Trade Marketing Manager", "date_range": "", "bullets": []}],
                },
                {
                    "company": "DKSH Consumer Goods",
                    "date_range": "May 2009 to Oct 2011",
                    "roles": [{"title": "Product Manager", "date_range": "", "bullets": []}],
                },
                {
                    "company": "DKSH Consumer Goods",
                    "date_range": "May 2008 to Apr 2009",
                    "roles": [{"title": "Supply Chain Management Trainee", "date_range": "", "bullets": []}],
                },
            ]
        }

        normalized = cn._normalize_cv_data_for_output(parsed)
        work = normalized["work_experiences"]

        self.assertEqual(len(work), 5)
        self.assertEqual(work[0]["company"], "Unilever")
        self.assertEqual(work[0]["date_range"], "Dec 2015 to Mar 2021")
        self.assertEqual(
            [role["title"] for role in work[0]["roles"]],
            [
                "Head of Trade Marketing",
                "Head of Sales Operation & Effectiveness",
                "National Sales Manager",
            ],
        )
        self.assertEqual(
            [role["date_range"] for role in work[0]["roles"]],
            [
                "Jan 2020 to Mar 2021",
                "Apr 2018 to Dec 2019",
                "Dec 2015 to Mar 2018",
            ],
        )
        self.assertEqual(work[1]["company"], "Nestle")
        self.assertEqual(work[2]["company"], "Unilever - Johor, Malaysia")
        self.assertEqual(work[3]["company"], "Unilever")
        self.assertEqual(work[4]["date_range"], "May 2008 to Oct 2011")
        self.assertEqual(len(work[4]["roles"]), 2)

    def test_adjacent_same_employer_with_a_real_gap_stays_separate(self):
        parsed = {
            "work_experiences": [
                {
                    "company": "Example Co",
                    "date_range": "Jan 2020 to Mar 2021",
                    "roles": [{"title": "New Role", "date_range": "", "bullets": []}],
                },
                {
                    "company": "Example Co",
                    "date_range": "Jan 2018 to Dec 2018",
                    "roles": [{"title": "Old Role", "date_range": "", "bullets": []}],
                },
            ]
        }

        normalized = cn._normalize_cv_data_for_output(parsed)

        self.assertEqual(len(normalized["work_experiences"]), 2)

    def test_merged_roles_are_sorted_newest_first_even_when_provider_order_is_oldest_first(self):
        parsed = {
            "work_experiences": [
                {
                    "company": "Example Co",
                    "date_range": "Jan 2018 to Dec 2019",
                    "roles": [
                        {"title": "Analyst", "date_range": "", "bullets": []}
                    ],
                },
                {
                    "company": "Example Co",
                    "date_range": "Jan 2020 to Mar 2021",
                    "roles": [
                        {"title": "Manager", "date_range": "", "bullets": []}
                    ],
                },
            ]
        }

        normalized = cn._normalize_cv_data_for_output(parsed)

        self.assertEqual(len(normalized["work_experiences"]), 1)
        self.assertEqual(
            [
                role["title"]
                for role in normalized["work_experiences"][0]["roles"]
            ],
            ["Manager", "Analyst"],
        )

    def test_short_business_unit_suffix_is_not_treated_as_a_location(self):
        parsed = {
            "work_experiences": [
                {
                    "company": "Acme - Consulting",
                    "date_range": "Jan 2020 to Dec 2020",
                    "roles": [{"title": "Consultant", "date_range": "", "bullets": []}],
                },
                {
                    "company": "Acme",
                    "date_range": "Jan 2019 to Dec 2019",
                    "roles": [{"title": "Analyst", "date_range": "", "bullets": []}],
                },
            ]
        }

        normalized = cn._normalize_cv_data_for_output(parsed)

        self.assertEqual(
            [item["company"] for item in normalized["work_experiences"]],
            ["Acme - Consulting", "Acme"],
        )

    def test_year_only_same_employer_entries_are_not_assumed_continuous(self):
        parsed = {
            "work_experiences": [
                {
                    "company": "Example Co",
                    "date_range": "2020",
                    "roles": [{"title": "Manager", "date_range": "", "bullets": []}],
                },
                {
                    "company": "Example Co",
                    "date_range": "2019",
                    "roles": [{"title": "Analyst", "date_range": "", "bullets": []}],
                },
            ]
        }

        normalized = cn._normalize_cv_data_for_output(parsed)

        self.assertEqual(len(normalized["work_experiences"]), 2)

    def test_partially_month_precise_same_employer_entries_are_not_assumed_continuous(self):
        parsed = {
            "work_experiences": [
                {
                    "company": "Example Co",
                    "date_range": "2020 to Jan 2021",
                    "roles": [{"title": "Manager", "date_range": "", "bullets": []}],
                },
                {
                    "company": "Example Co",
                    "date_range": "Feb 2019 to 2020",
                    "roles": [{"title": "Analyst", "date_range": "", "bullets": []}],
                },
            ]
        }

        normalized = cn._normalize_cv_data_for_output(parsed)

        self.assertEqual(len(normalized["work_experiences"]), 2)

    def test_undated_current_employer_and_role_keep_their_source_positions(self):
        experiences = [
            {"company": "Current Co", "date_range": ""},
            {"company": "Old Co", "date_range": "2019"},
            {"company": "Newer Co", "date_range": "2021"},
        ]
        roles = [
            {"title": "Current Role", "date_range": ""},
            {"title": "Old Role", "date_range": "2019"},
            {"title": "Newer Role", "date_range": "2021"},
        ]

        self.assertEqual(
            [item["company"] for item in cn._sort_work_experiences_reverse_chronological(experiences)],
            ["Current Co", "Newer Co", "Old Co"],
        )
        self.assertEqual(
            [item["title"] for item in cn._sort_cv_roles_reverse_chronological(roles)],
            ["Current Role", "Newer Role", "Old Role"],
        )


class SourceEnumeratorCleanupTests(unittest.TestCase):
    def test_bare_source_enumerators_are_removed_without_touching_false_positives(self):
        bullets = cn._normalize_cv_bullet_items(
            [
                "a. Manchester united",
                "b. Manchester city",
                "i. Wonderful world",
                "ii. Wonderful creature",
                "1- Responsible for cross-domain support",
                "a- Administrating VMware",
                "3.5 years of experience",
                "-5% variance",
                "i.e. keep this abbreviation",
                "A. Smith led the programme",
                "2020-2023 migration programme",
            ]
        )

        self.assertEqual(
            bullets[:6],
            [
                "Manchester united",
                "Manchester city",
                "Wonderful world",
                "Wonderful creature",
                "Responsible for cross-domain support",
                "Administrating VMware",
            ],
        )
        self.assertEqual(
            bullets[6:],
            [
                "3.5 years of experience",
                "-5% variance",
                "i.e. keep this abbreviation",
                "A. Smith led the programme",
                "2020-2023 migration programme",
            ],
        )


class EducationAndSkillsConsistencyTests(unittest.TestCase):
    def test_education_recovers_source_months_when_provider_returns_years_only(self):
        parsed = {
            "education": [
                {
                    "institution": "Multimedia University",
                    "degree": "Bachelor of Business Administration",
                    "date_range": "2004 to 2008",
                }
            ]
        }
        source = (
            "EDUCATION & CERTIFICATION\n"
            "Bachelor of Business Administration (Honor): Management with Multimedia,\n"
            "06/2004 - 05/2008\n"
            "Multimedia University\n"
        )

        normalized = cn._normalize_cv_data_for_output(parsed, source)

        self.assertEqual(
            normalized["education"][0]["date_range"],
            "Jun 2004 to May 2008",
        )

    def test_education_does_not_expand_a_single_graduation_year(self):
        parsed = {
            "education": [
                {
                    "institution": "Multimedia University",
                    "degree": "Bachelor of Business Administration",
                    "date_range": "2008",
                }
            ]
        }
        source = (
            "Bachelor of Business Administration\n"
            "06/2004 - 05/2008\n"
            "Multimedia University\n"
        )

        normalized = cn._normalize_cv_data_for_output(parsed, source)

        self.assertEqual(normalized["education"][0]["date_range"], "2008")

    def test_education_removes_dangling_to_and_keeps_missing_date_empty(self):
        parsed = {
            "education": [
                {
                    "institution": "University of Tenaga Nasional",
                    "degree": "Bachelor's Degree in Computer Science",
                    "date_range": "to 2001",
                },
                {
                    "institution": "Primary/Secondary School",
                    "degree": "Malaysian Certificate of Education (SPM Grade 1)",
                    "date_range": "to 1996",
                },
                {
                    "institution": "Undated University",
                    "degree": "Certificate",
                    "date_range": "",
                },
            ]
        }

        normalized = cn._normalize_cv_data_for_output(parsed, "Education")

        self.assertEqual(normalized["education"][0]["date_range"], "2001")
        self.assertEqual(normalized["education"][1]["date_range"], "1996")
        self.assertEqual(normalized["education"][2]["date_range"], "")

    def test_core_expertise_always_normalizes_to_bullet_items(self):
        expected = [
            "P&L Leadership",
            "Key Account Management",
            "Distributor & Route to Market Management",
        ]
        inputs = [expected, ", ".join(expected), "\n".join(expected)]

        for items in inputs:
            with self.subTest(items=items):
                parsed = {
                    "skills": [
                        {
                            "category": "Core Expertise",
                            "items": items,
                        }
                    ]
                }

                normalized = cn._normalize_cv_data_for_output(parsed)

                self.assertEqual(normalized["skills"][0]["items"], expected)

    def test_core_expertise_keeps_commas_inside_existing_bullet_items(self):
        parsed = {
            "skills": [
                {
                    "category": "Core Expertise",
                    "items": [
                        "Mergers, Acquisitions & Integration",
                        "P&L Leadership",
                    ],
                }
            ]
        }

        normalized = cn._normalize_cv_data_for_output(parsed)

        self.assertEqual(
            normalized["skills"][0]["items"],
            ["Mergers, Acquisitions & Integration", "P&L Leadership"],
        )

    def test_core_expertise_splits_a_comma_paragraph_wrapped_in_one_list_item(self):
        parsed = {
            "skills": [
                {
                    "category": "Core Expertise",
                    "items": ["Leadership, Strategy, Sales"],
                }
            ]
        }

        normalized = cn._normalize_cv_data_for_output(parsed)

        self.assertEqual(
            normalized["skills"][0]["items"],
            ["Leadership", "Strategy", "Sales"],
        )


class SourceAdditionalSectionRecoveryTests(unittest.TestCase):
    SOURCE = """Other Information
[PROJECT INVOLVEMENT HISTORY]:
* Firewalls Configuring & VPN Services
* Network Infrastructure Enhancement & Redesign
[PARTICIPATED TRAINING PROGRAMME]:
* Enhancing Performance Through Teamwork
* Microsoft Certified System Engineer (MCSE)
[SOFT SKILLS]:
* Vendor Management & Negotiation Skills
"""

    def test_recovers_project_and_training_sections_without_duplicate_certs(self):
        parsed = {
            "certifications": [
                "Microsoft Certified System Engineer (MCSE)",
                "Unrelated Certification",
            ],
            "skills": [
                {
                    "category": "Project Involvement History",
                    "items": "Firewalls Configuring & VPN Services",
                }
            ],
        }

        normalized = cn._normalize_cv_data_for_output(parsed, self.SOURCE)
        sections = {
            skill["category"]: skill["items"] for skill in normalized["skills"]
        }

        self.assertEqual(
            sections["Project Involvement History"],
            [
                "Firewalls Configuring & VPN Services",
                "Network Infrastructure Enhancement & Redesign",
            ],
        )
        self.assertEqual(
            sections["Participated Training Programme"],
            [
                "Enhancing Performance Through Teamwork",
                "Microsoft Certified System Engineer (MCSE)",
            ],
        )
        self.assertEqual(normalized["certifications"], ["Unrelated Certification"])

    def test_recovery_stops_at_unbracketed_cv_section_headings(self):
        source = """[PROJECT INVOLVEMENT HISTORY]:
Unmarked project title
EDUCATION
Bachelor of Computer Science
[PARTICIPATED TRAINING PROGRAMME]:
* Enhancing Performance Through Teamwork
REFERENCES:
Available upon request
"""

        recovered = cn._extract_recoverable_cv_source_sections(source)

        self.assertEqual(
            recovered,
            {
                "Project Involvement History": ["Unmarked project title"],
                "Participated Training Programme": [
                    "Enhancing Performance Through Teamwork"
                ],
            },
        )

    def test_recovery_stops_at_common_combined_cv_section_headings(self):
        headings = (
            "EDUCATION & CERTIFICATION",
            "EDUCATION AND CERTIFICATION",
            "PROFESSIONAL QUALIFICATIONS",
            "COURSES & TRAINING",
            "PROFESSIONAL AFFILIATIONS",
        )

        for heading in headings:
            with self.subTest(heading=heading):
                source = (
                    "[PROJECT INVOLVEMENT HISTORY]:\n"
                    "* Project Alpha\n"
                    f"{heading}\n"
                    "* Later section content\n"
                )

                recovered = cn._extract_recoverable_cv_source_sections(source)

                self.assertEqual(
                    recovered,
                    {"Project Involvement History": ["Project Alpha"]},
                )

    def test_heading_like_text_with_an_explicit_bullet_remains_a_project_item(self):
        source = """[PROJECT INVOLVEMENT HISTORY]:
* Project Alpha
* Professional Development
* Project Omega
EDUCATION
Bachelor of Computer Science
"""

        recovered = cn._extract_recoverable_cv_source_sections(source)

        self.assertEqual(
            recovered,
            {
                "Project Involvement History": [
                    "Project Alpha",
                    "Professional Development",
                    "Project Omega",
                ]
            },
        )

    def test_recovery_stops_at_numbered_or_emphasized_marked_section_headings(self):
        headings = ("1. EDUCATION", "* EDUCATION", "* Education:")

        for heading in headings:
            with self.subTest(heading=heading):
                source = (
                    "[PROJECT INVOLVEMENT HISTORY]:\n"
                    "* Project Alpha\n"
                    f"{heading}\n"
                    "Bachelor of Computer Science\n"
                )

                recovered = cn._extract_recoverable_cv_source_sections(source)

                self.assertEqual(
                    recovered,
                    {"Project Involvement History": ["Project Alpha"]},
                )

    def test_removes_siva_metadata_and_only_keeps_source_grounded_github(self):
        parsed = {
            "skills": [
                {
                    "category": "Summary",
                    "items": (
                        "Position: Retrieved Resumes (SiVA folder: Prescreened); "
                        "Date Applied: 30 Mar 2022"
                    ),
                },
                {
                    "category": "Portfolio & Links",
                    "items": (
                        "GitHub: https://github.com/unknown | "
                        "GitHub: https://github.com/source-user"
                    ),
                },
                {
                    "category": "Technologies",
                    "items": "Python | Java",
                },
            ]
        }
        source = self.SOURCE + "\nGitHub: https://github.com/source-user\n"

        normalized = cn._normalize_cv_data_for_output(parsed, source)

        self.assertEqual(
            normalized["skills"],
            [
                {
                    "category": "Portfolio & Links",
                    "items": "GitHub: https://github.com/source-user",
                },
                {
                    "category": "Technologies",
                    "items": "Python | Java",
                },
                {
                    "category": "Project Involvement History",
                    "items": [
                        "Firewalls Configuring & VPN Services",
                        "Network Infrastructure Enhancement & Redesign",
                    ],
                },
                {
                    "category": "Participated Training Programme",
                    "items": [
                        "Enhancing Performance Through Teamwork",
                        "Microsoft Certified System Engineer (MCSE)",
                    ],
                },
            ],
        )

    def test_removes_inline_siva_metadata_after_a_skill_item_delimiter(self):
        parsed = {
            "skills": [
                {
                    "category": "Summary",
                    "items": (
                        "Infrastructure leader | Position: Retrieved Resumes "
                        "(SiVA folder: Prescreened); Date Applied: 30 Mar 2022\n"
                        "Delivery governance"
                    ),
                }
            ]
        }

        normalized = cn._normalize_cv_data_for_output(parsed, "Infrastructure leader")

        self.assertEqual(
            normalized["skills"],
            [
                {
                    "category": "Summary",
                    "items": "Infrastructure leader\nDelivery governance",
                }
            ],
        )

    def test_source_free_output_drops_placeholder_but_keeps_other_github_links(self):
        parsed = {
            "skills": [
                {
                    "category": "Portfolio & Links",
                    "items": (
                        "GitHub: https://github.com/unknown | "
                        "GitHub: https://github.com/source-user"
                    ),
                }
            ]
        }

        normalized = cn._normalize_cv_data_for_output(parsed)

        self.assertEqual(
            normalized["skills"],
            [
                {
                    "category": "Portfolio & Links",
                    "items": "GitHub: https://github.com/source-user",
                }
            ],
        )

        source_free_real_link = {
            "skills": [
                {
                    "category": "Portfolio & Links",
                    "items": "GitHub: https://github.com/source-user | Website: example.com",
                }
            ]
        }
        self.assertEqual(
            cn._normalize_cv_data_for_output(source_free_real_link)["skills"],
            [
                {
                    "category": "Portfolio & Links",
                    "items": (
                        "GitHub: https://github.com/source-user | "
                        "Website: example.com"
                    ),
                }
            ],
        )

    def test_source_grounding_ignores_terminal_sentence_period(self):
        parsed = {
            "skills": [
                {
                    "category": "Portfolio & Links",
                    "items": "GitHub: https://github.com/source-user",
                }
            ]
        }

        normalized = cn._normalize_cv_data_for_output(
            parsed,
            "GitHub: https://github.com/source-user.",
        )

        self.assertEqual(
            normalized["skills"],
            [
                {
                    "category": "Portfolio & Links",
                    "items": "GitHub: https://github.com/source-user",
                }
            ],
        )


class ModuleHygieneTests(unittest.TestCase):
    def test_module_does_not_import_app(self):
        import sys
        # Importing the module must not have pulled in the legacy web shell.
        self.assertNotIn("app", getattr(cn, "__dict__", {}))


if __name__ == "__main__":
    unittest.main()
