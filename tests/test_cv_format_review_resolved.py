"""A grounded suggestion already satisfied by the final CV is not a warning."""
import copy
import json
import unittest

from cvstudio_cv_fidelity import apply_cv_format_review, seal_cv_format_review, validate_cv_format_review


SOURCE = """WORK EXPERIENCE
Contoso Systems | Analyst | January 2021 - Present
Built reporting dashboards.
Led regional operations.
EDUCATION
Fabrikam University | Bachelor of Science | 2017
Statistics
First Class Honors
"""


def cv():
    return {"candidate": {}, "work_experiences": [{"company": "Contoso Systems", "date_range": "Jan 2021 to Present",
        "roles": [{"title": "Analyst", "bullets": ["Built reporting dashboards."]}]}],
        "education": [{"institution": "Fabrikam University", "degree": "Bachelor of Science", "date_range": "2017", "major": "Statistics"}]}


def issue(operation, quote=SOURCE):
    return {"message": "Check this source detail.", "source_quote": quote, "operation": operation}


class ResolvedReviewTests(unittest.TestCase):
    def review(self, issues, data=None, source=SOURCE):
        original = data or cv()
        before = copy.deepcopy(original)
        result = validate_cv_format_review(json.dumps({"issues": issues}), source, original)
        self.assertEqual(original, before)
        return result

    def test_exact_or_house_style_replacements_already_present_are_omitted(self):
        for path, value in (("/work_experiences/0/company", "Contoso Systems"),
                            ("/work_experiences/0/roles/0/title", "Analyst"),
                            ("/work_experiences/0/date_range", "January 2021 - Present"),
                            ("/education/0/major", "Statistics")):
            with self.subTest(path=path):
                review = self.review([issue({"op": "replace", "path": path, "before": "Stale value", "value": value})])
                self.assertEqual(review["issues"], [])
                self.assertEqual(review["status"], "reviewed")

    def test_added_duty_already_present_after_marker_normalization_is_omitted(self):
        for marker in ("• ", "- ", "● ", "1. "):
            text = marker + "Built reporting dashboards."
            source = SOURCE + "\n" + text
            with self.subTest(marker=marker):
                review = self.review([issue({"op": "add", "path": "/work_experiences/0/roles/0/bullets/-", "value": text}, text)], source=source)
                self.assertEqual(review["issues"], [])

    def test_existing_job_and_qualification_are_omitted_when_all_proposed_details_exist(self):
        data = cv()
        for path, value in (("/work_experiences/-", data["work_experiences"][0]), ("/education/-", data["education"][0])):
            value = copy.deepcopy(value)
            if "company" in value:
                value["date_range"] = "January 2021 - Present"
            with self.subTest(path=path):
                self.assertEqual(self.review([issue({"op": "add", "path": path, "value": value})])["issues"], [])

    def test_matching_identity_does_not_hide_a_missing_duty_or_qualification_result(self):
        data = cv()
        job = copy.deepcopy(data["work_experiences"][0])
        job["date_range"] = "January 2021 - Present"
        job["roles"][0]["bullets"].append("Led regional operations.")
        qualification = dict(data["education"][0], honors="First Class Honors")
        for path, value in (("/work_experiences/-", job), ("/education/-", qualification)):
            with self.subTest(path=path):
                review = self.review([issue({"op": "add", "path": path, "value": value})])
                self.assertEqual(len(review["issues"]), 1)
                self.assertFalse(review["issues"][0]["can_apply"])

    def test_body_already_correct_does_not_hide_a_conflicting_current_header(self):
        data = cv()
        data["candidate"]["current_company"] = "Different employer"
        review = self.review([issue({"op": "replace", "path": "/work_experiences/0/company",
            "before": "Contoso Systems", "value": "Contoso Systems"})], data)
        self.assertEqual(len(review["issues"]), 1)
        self.assertFalse(review["issues"][0]["can_apply"])

    def test_matching_first_job_addition_keeps_conflicting_current_headers_manual(self):
        for headers in ({"current_company": "Different employer"}, {"current_position": "Different position"},
                        {"current_company": "Different employer", "current_position": "Different position"}):
            for path in ("/work_experiences/-", "/work_experiences/0", "/work_experiences/1"):
                data = cv()
                data["candidate"] = headers
                operation = {"op": "add", "path": path, "value": copy.deepcopy(data["work_experiences"][0])}
                operation["value"]["date_range"] = "January 2021 - Present"
                with self.subTest(headers=headers, path=path):
                    review = self.review([issue(operation)], data)
                    self.assertEqual(len(review["issues"]), 1)
                    self.assertFalse(review["issues"][0]["can_apply"])
                    self.assertNotEqual(review["message"], "No clear content mistake was found.")

    def test_matching_first_job_with_consistent_or_absent_headers_is_still_resolved(self):
        for headers in ({}, {"current_company": "", "current_position": ""},
                        {"current_company": "CONTOSO SYSTEMS", "current_position": "ANALYST"}):
            data = cv()
            data["candidate"] = headers
            value = copy.deepcopy(data["work_experiences"][0])
            value["date_range"] = "January 2021 - Present"
            with self.subTest(headers=headers):
                self.assertEqual(self.review([issue({"op": "add", "path": "/work_experiences/-",
                    "value": value})], data)["issues"], [])

    def test_header_check_uses_rendered_title_style_and_latest_role(self):
        data = cv()
        data["candidate"] = {"current_company": "CONTOSO SYSTEMS", "current_position": "SR Engineer"}
        data["work_experiences"][0]["roles"] = [
            {"title": "Analyst", "date_range": "2021 to 2022", "bullets": []},
            {"title": "SR Engineer", "date_range": "2023 to Present", "bullets": []}]
        source = SOURCE + "\nSR Engineer\n2021 to 2022\n2023 to Present"
        value = copy.deepcopy(data["work_experiences"][0])
        value["date_range"] = "January 2021 - Present"
        self.assertEqual(self.review([issue({"op": "add", "path": "/work_experiences/-", "value": value}, source)],
            data, source)["issues"], [])
        # A subset proposing an older role still checks the actual latest role.
        value["roles"] = value["roles"][:1]
        self.assertEqual(self.review([issue({"op": "add", "path": "/work_experiences/-", "value": value}, source)],
            data, source)["issues"], [])
        data["candidate"]["current_position"] = "Analyst"
        review = self.review([issue({"op": "add", "path": "/work_experiences/-", "value": value}, source)], data, source)
        self.assertEqual(len(review["issues"]), 1)
        self.assertFalse(review["issues"][0]["can_apply"])

    def test_older_job_and_education_duplicates_do_not_check_current_headers(self):
        data = cv()
        data["candidate"] = {"current_company": "Different employer", "current_position": "Different position"}
        older = {"company": "Northwind Systems", "date_range": "2017 to 2020", "roles": [{"title": "Engineer", "bullets": []}]}
        data["work_experiences"].append(older)
        source = SOURCE + "\nNorthwind Systems\n2017 to 2020\nEngineer"
        for path, value in (("/work_experiences/-", older), ("/education/-", data["education"][0])):
            with self.subTest(path=path):
                self.assertEqual(self.review([issue({"op": "add", "path": path, "value": value}, source)],
                    data, source)["issues"], [])

    def test_matching_job_does_not_hide_a_duty_missing_from_its_correct_role(self):
        data = cv()
        data["work_experiences"][0]["roles"].append({"title": "Manager", "bullets": []})
        value = copy.deepcopy(data["work_experiences"][0])
        value["date_range"] = "January 2021 - Present"
        value["roles"][1]["bullets"] = ["Built reporting dashboards."]
        source = SOURCE + "\nManager"
        review = self.review([issue({"op": "add", "path": "/work_experiences/-", "value": value}, source)], data, source)
        self.assertEqual(len(review["issues"]), 1)
        self.assertFalse(review["issues"][0]["can_apply"])

    def test_duty_case_is_equivalent_but_different_role_ownership_is_not(self):
        text = "BUILT REPORTING DASHBOARDS."
        source = SOURCE + "\n" + text
        operation = {"op": "add", "path": "/work_experiences/0/roles/0/bullets/-", "value": text}
        self.assertEqual(self.review([issue(operation, text)], source=source)["issues"], [])
        data = cv()
        data["work_experiences"][0]["roles"].append({"title": "Manager", "bullets": []})
        operation["path"] = "/work_experiences/0/roles/1/bullets/-"
        self.assertTrue(self.review([issue(operation, text)], data, source)["issues"][0]["can_apply"])

    def test_unverified_referee_and_unsupported_suggestions_are_not_silently_hidden(self):
        good = {"op": "replace", "path": "/work_experiences/0/company", "before": "Old", "value": "Contoso Systems"}
        for operation, quote, source in ((dict(good, _hidden=True), SOURCE, SOURCE),
                                        (good, SOURCE, SOURCE + SOURCE),
                                        (good, SOURCE, "REFERENCES\n" + SOURCE.replace("WORK EXPERIENCE\n", "")),
                                        (dict(good, path="/candidate/company"), SOURCE, SOURCE),
                                        (None, SOURCE, SOURCE)):
            with self.subTest(operation=operation):
                review = self.review([issue(operation, quote)], source=source)
                self.assertEqual(len(review["issues"]), 1)
                self.assertFalse(review["issues"][0]["can_apply"])

    def test_different_dates_or_words_are_still_reported(self):
        source = SOURCE + "\nContoso Systems | Analyst | January 2020 - Present\nBuilt reporting dashboards for the board."
        for path, value in (("/work_experiences/0/date_range", "January 2020 - Present"),
                            ("/work_experiences/0/roles/0/bullets/-", "Built reporting dashboards for the board.")):
            operation = {"op": "replace" if "date_range" in path else "add", "path": path,
                         "before": "Jan 2021 to Present", "value": value}
            with self.subTest(path=path):
                self.assertTrue(self.review([issue(operation, source)], source=source)["issues"][0]["can_apply"])

    def test_filtering_keeps_remaining_signed_issue_ids_usable(self):
        resolved = issue({"op": "replace", "path": "/work_experiences/0/date_range", "before": "Wrong", "value": "January 2021 - Present"})
        missing = issue({"op": "add", "path": "/work_experiences/0/roles/0/bullets/-", "value": "Led regional operations."})
        data = cv()
        review = self.review([resolved, missing], data)
        self.assertEqual([item["id"] for item in review["issues"]], ["2"])
        sealed = seal_cv_format_review(review, SOURCE, data, b"synthetic-key", now=100)
        fixed = apply_cv_format_review(SOURCE, data, sealed, "2", b"synthetic-key", now=101)
        self.assertEqual(fixed["work_experiences"][0]["roles"][0]["bullets"], ["Built reporting dashboards.", "Led regional operations."])
