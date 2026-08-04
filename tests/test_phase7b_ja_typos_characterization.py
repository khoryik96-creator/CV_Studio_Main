"""Characterization tests for the JobAdder typo-correction helpers.

Locks the behaviour of the pure helpers extracted into ``cvstudio_ja_typos``
(Phase 7B): bounded edit distance, casing preservation, the recruitment/salary
typo tables, and the field-level corrections applied to screening notes,
notice-period text and salary strings. These are a verbatim move from the legacy
web shell, so every assertion equally describes the pre-extraction behaviour.
"""

import unittest

import cvstudio_ja_typos as typos


class EditDistanceTests(unittest.TestCase):
    def test_close_words_report_true_distance(self):
        self.assertEqual(typos._ja_edit_distance_limited("recruter", "recruiter", 3), 1)

    def test_distance_is_capped_at_the_limit(self):
        self.assertEqual(typos._ja_edit_distance_limited("abc", "xyz", 2), 3)


class CaseLikeTests(unittest.TestCase):
    def test_upper_case_source_is_preserved(self):
        self.assertEqual(typos._ja_case_like("permanent", "PERMENANT"), "PERMENANT")

    def test_title_case_source_is_preserved(self):
        self.assertEqual(typos._ja_case_like("permanent", "Permenant"), "Permenant")


class TypoTargetTests(unittest.TestCase):
    def test_known_aliases_map_to_canonical(self):
        self.assertEqual(typos._ja_recruitment_typo_target("permenant"), "permanent")
        self.assertEqual(typos._ja_recruitment_typo_target("allowence"), "allowance")

    def test_clean_word_has_no_target(self):
        self.assertEqual(typos._ja_recruitment_typo_target("engineer"), "")


class CorrectRecruitmentTypoTests(unittest.TestCase):
    def test_corrects_multiple_typos_in_text(self):
        self.assertEqual(
            typos._ja_correct_recruitment_typos("permenant contrct with allowence"),
            "permanent contract with allowance",
        )

    def test_disabled_returns_text_unchanged(self):
        self.assertEqual(
            typos._ja_correct_recruitment_typos("permenant role", enabled=False), "permenant role"
        )


class ScreeningFieldTypoTests(unittest.TestCase):
    def test_known_field_value_is_corrected(self):
        result = typos._ja_correct_screening_field_typos({"role": "permenant contrct"})
        self.assertEqual(result["role"], "permanent contract")

    def test_disabled_leaves_field_value_unchanged(self):
        result = typos._ja_correct_screening_field_typos({"role": "permenant"}, enabled=False)
        self.assertEqual(result["role"], "permenant")


class NoticeAndSalaryTypoTests(unittest.TestCase):
    def test_notice_month_typo_is_corrected(self):
        self.assertEqual(typos._ja_correct_notice_typos("available in 2 moth"), "available in 2 month")

    def test_salary_ordinal_month_typo_is_corrected(self):
        self.assertEqual(
            typos._ja_salary_normalize_recruiter_typos("5th moth salary"), "5th month salary"
        )


class ReExportTests(unittest.TestCase):
    def test_app_reexports_are_the_module_objects(self):
        import app  # noqa: PLC0415 - importing the shell is the point of this check

        for name in (
            "_JA_RECRUITMENT_FUZZY_TERMS",
            "_JA_RECRUITMENT_PROTECTED_WORDS",
            "_JA_RECRUITMENT_TYPO_ALIASES",
            "_JA_SALARY_TYPO_RULES",
            "_ja_case_like",
            "_ja_correct_notice_typos",
            "_ja_correct_recruitment_typos",
            "_ja_correct_screening_field_typos",
            "_ja_edit_distance_limited",
            "_ja_recruitment_typo_target",
            "_ja_salary_normalize_recruiter_typos",
        ):
            self.assertIs(getattr(app, name), getattr(typos, name), name)


if __name__ == "__main__":
    unittest.main()
