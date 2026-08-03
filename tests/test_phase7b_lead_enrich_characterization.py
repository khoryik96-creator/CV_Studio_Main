"""Characterization coverage for the pure Lead Finder URL/company helpers.

These lock the observable behavior of the URL/link classification and
company-guess helpers before they move out of the legacy web shell into
``cvstudio_lead_enrich.py``. The suite imports through ``app`` so it passes
identically before the extraction (functions defined in app.py) and after it
(app.py re-exports them from the new module).
"""

import os
from pathlib import Path
import tempfile
import unittest

from owner_build_tools.build_protected import write_test_receipt


ROOT = Path(__file__).resolve().parents[1]

_MODULE_TEMPORARY = tempfile.TemporaryDirectory(prefix="cvstudio-lead-enrich-")
_ORIGINAL_DATABASE_OVERRIDE = os.environ.get("CVSTUDIO_DB_PATH")
os.environ["CVSTUDIO_DB_PATH"] = str(
    Path(_MODULE_TEMPORARY.name) / "state" / "cv_studio.sqlite3"
)
write_test_receipt(ROOT)
try:
    import app
finally:
    if _ORIGINAL_DATABASE_OVERRIDE is None:
        os.environ.pop("CVSTUDIO_DB_PATH", None)
    else:
        os.environ["CVSTUDIO_DB_PATH"] = _ORIGINAL_DATABASE_OVERRIDE


class LeadEnrichCharacterizationTests(unittest.TestCase):
    def test_is_direct_job_url(self):
        cases = {
            "https://www.linkedin.com/jobs/view/3812345678": True,
            "https://www.linkedin.com/jobs/": False,
            "https://www.indeed.com/viewjob?jk=abc123": True,
            "https://www.indeed.com/jobs?q=sap": False,
            "https://my.jobstreet.com/jobs?jobId=87401944&type=standard": True,
            "https://www.jobstreet.com.my/companies/acme": False,
            "https://www.jobstreet.com.my/sap-consultant-jobs/in-Kuala-Lumpur": False,
            "https://boards.greenhouse.io/acme/jobs/1234567": True,
            "https://example.com/": False,
            "https://acme.com/careers/sap-consultant/1024": True,
            "https://acme.com/careers": False,
            "not a url": False,
            "": False,
        }
        for url, expected in cases.items():
            self.assertIs(app._lead_is_direct_job_url(url), expected, url)

    def test_is_non_job_content_url(self):
        cases = {
            "https://www.jobstreet.com/career-advice/role/sap/salary": True,
            "https://www.jobstreet.com/job/12345": False,
            "https://acme.com/blog/hiring": True,
            "https://acme.com/jobs/1": False,
        }
        for url, expected in cases.items():
            self.assertIs(app._lead_is_non_job_content_url(url), expected, url)

    def test_is_generic_portal_category_url(self):
        self.assertIs(
            app._lead_is_generic_portal_category_url(
                "https://www.jobstreet.com.my/sap-consultant-jobs", ""
            ),
            True,
        )
        self.assertIs(
            app._lead_is_generic_portal_category_url(
                "https://boards.greenhouse.io/acme/jobs/1234567", "Acme"
            ),
            False,
        )
        self.assertIs(
            app._lead_is_generic_portal_category_url("https://example.com/", ""),
            False,
        )

    def test_canonical_direct_job_url_is_stable(self):
        for url in (
            "https://www.linkedin.com/jobs/view/3812345678?refId=xyz&trk=abc",
            "https://www.indeed.com/viewjob?jk=abc123&from=serp",
            "https://acme.com/careers/sap-consultant/1024",
        ):
            self.assertEqual(app._lead_canonical_direct_job_url(url), url)

    def test_url_portal_labels(self):
        self.assertEqual(
            app._lead_url_portal("https://www.linkedin.com/jobs/view/1"),
            "LinkedIn Jobs",
        )
        self.assertEqual(
            app._lead_url_portal("https://my.jobstreet.com/jobs?jobId=1"),
            "JobStreet",
        )
        self.assertEqual(
            app._lead_url_portal("https://www.indeed.com/viewjob?jk=1"), "Indeed"
        )
        self.assertEqual(
            app._lead_url_portal("https://boards.greenhouse.io/acme/jobs/1"),
            "Company Careers",
        )
        self.assertEqual(
            app._lead_url_portal("https://acme.com/careers/x"), "Company Careers"
        )

    def test_guess_portal_from_url_labels(self):
        self.assertEqual(
            app._lead_guess_portal_from_url("https://www.linkedin.com/jobs/view/1", ""),
            "LinkedIn Jobs",
        )
        self.assertEqual(
            app._lead_guess_portal_from_url("https://my.jobstreet.com/jobs?jobId=1", ""),
            "JobStreet",
        )
        self.assertEqual(
            app._lead_guess_portal_from_url("https://www.indeed.com/viewjob?jk=1", ""),
            "Indeed",
        )
        self.assertEqual(
            app._lead_guess_portal_from_url(
                "https://boards.greenhouse.io/acme/jobs/1", ""
            ),
            "Company Careers / ATS",
        )
        self.assertEqual(
            app._lead_guess_portal_from_url("https://acme.com/careers/x", ""),
            "Company Careers",
        )

    def test_guess_company_from_url(self):
        self.assertEqual(
            app._lead_guess_company_from_url(
                "https://acme.com/careers/sap-consultant/1024"
            ),
            "Acme",
        )
        self.assertEqual(
            app._lead_guess_company_from_url("https://www.linkedin.com/jobs/view/1"),
            "",
        )
        self.assertEqual(
            app._lead_guess_company_from_url("https://randomblog.com/post"),
            "Randomblog",
        )

    def test_clean_company_guess(self):
        cases = {
            "ACME Corporation Sdn Bhd": "ACME Corporation Sdn Bhd",
            "  the acme, inc. ": "the acme, inc.",
            "Careers": "",
            "SAP": "SAP",
            "": "",
        }
        for raw, expected in cases.items():
            self.assertEqual(app._lead_clean_company_guess(raw), expected, raw)

    def test_verification_company_text(self):
        cases = {
            "Acme Corp": "Acme Corp",
            "SAP": "SAP",
            "  ": "",
            "O'Brien & Sons": "O'Brien & Sons",
        }
        for raw, expected in cases.items():
            self.assertEqual(app._lead_verification_company_text(raw), expected, raw)

    def test_is_generated_verification_search(self):
        self.assertIs(
            app._lead_is_generated_verification_search(
                "https://www.google.com/search?q=acme+sap"
            ),
            True,
        )
        self.assertIs(
            app._lead_is_generated_verification_search("https://acme.com/careers/1"),
            False,
        )
        self.assertIs(
            app._lead_is_generated_verification_search(
                "https://www.bing.com/search?q=x"
            ),
            False,
        )

    def test_source_allowed_by_selection(self):
        self.assertIs(
            app._lead_source_allowed_by_selection(
                "https://www.linkedin.com/jobs/view/1", "linkedin", ["linkedin"]
            ),
            True,
        )
        self.assertIs(
            app._lead_source_allowed_by_selection(
                "https://www.linkedin.com/jobs/view/1", "linkedin", ["jobstreet"]
            ),
            False,
        )
        self.assertIs(
            app._lead_source_allowed_by_selection(
                "https://acme.com/careers/1", "company", ["linkedin"]
            ),
            False,
        )

    # --- job-filter / query-term helpers ---------------------------------

    def test_clean_csv_dedupes_and_limits(self):
        self.assertEqual(app._lead_clean_csv("a, b; a\nc", 12), ["a", "b", "c"])
        self.assertEqual(app._lead_clean_csv(["x", "x ", " y"], 2), ["x", "y"])
        self.assertEqual(app._lead_clean_csv("", 12), [])

    def test_clean_job_filters_normalizes_and_drops_empty(self):
        self.assertEqual(
            app._lead_clean_job_filters(
                {
                    "must_have": "sap, abap, sap",
                    "seniority": "  senior ",
                    "max_days_open": "30x9",
                    "company_include": "tech",
                    "exclude_keywords": "",
                }
            ),
            {
                "must_have": "sap, abap",
                "seniority": "senior",
                "max_days_open": "309",
                "company_include": "tech",
            },
        )
        self.assertEqual(app._lead_clean_job_filters("not a dict"), {})

    def test_job_filter_instruction(self):
        no_filters = (
            "No extra relevance filters supplied. Infer relevance from CV, "
            "target role, regions and selected portals."
        )
        self.assertEqual(app._lead_job_filter_instruction({}), no_filters)
        self.assertEqual(app._lead_job_filter_instruction(None), no_filters)
        out = app._lead_job_filter_instruction(
            {"must_have": "SAP", "exclude_keywords": "intern"}
        )
        self.assertIn("MUST-HAVE keywords/skills: SAP", out)
        self.assertIn("EXCLUDE keywords: intern", out)

    def test_filter_and_exclude_query_terms(self):
        self.assertEqual(
            app._lead_filter_query_terms(
                {
                    "must_have": "sap,abap",
                    "seniority": "senior",
                    "company_include": "tech,finance",
                }
            ),
            "sap abap senior tech finance",
        )
        self.assertEqual(app._lead_filter_query_terms({}), "")
        self.assertEqual(
            app._lead_exclude_query_terms(
                {"exclude_keywords": "intern, junior", "company_exclude": "acme corp"}
            ),
            "-intern -junior -acme-corp",
        )
        self.assertEqual(app._lead_exclude_query_terms(None), "")

    # --- email / linkedin helpers ----------------------------------------

    def test_email_domain(self):
        self.assertEqual(app._lead_email_domain("  John.Doe@Acme.COM "), "acme.com")
        self.assertEqual(app._lead_email_domain("<a@b.co>"), "b.co")
        self.assertEqual(app._lead_email_domain("not-an-email"), "")
        self.assertEqual(app._lead_email_domain(""), "")

    def test_is_company_domain_email(self):
        self.assertIs(app._lead_is_company_domain_email("a@acme.com", "Acme"), True)
        self.assertIs(app._lead_is_company_domain_email("a@gmail.com", "Acme"), False)
        self.assertIs(app._lead_is_company_domain_email("a@example.com", ""), False)
        self.assertIs(app._lead_is_company_domain_email("bad", ""), False)

    def test_normalize_linkedin_url(self):
        self.assertEqual(
            app._lead_normalize_linkedin_url("www.linkedin.com/in/jdoe/"),
            "https://linkedin.com/in/jdoe",
        )
        self.assertEqual(
            app._lead_normalize_linkedin_url("https://WWW.linkedin.com/in/jdoe?trk=x"),
            "https://linkedin.com/in/jdoe",
        )
        self.assertEqual(app._lead_normalize_linkedin_url("https://acme.com/in/x"), "")
        self.assertEqual(app._lead_normalize_linkedin_url(""), "")

    def test_sanitize_public_business_emails(self):
        out = app._lead_sanitize_public_business_emails(
            [
                {"email": "a@gmail.com", "company": "Acme"},
                {"email": "b@acme.com"},
                {"email": "", "notes": "hi"},
            ]
        )
        # Personal/free-mail email is cleared with a note + Not found status.
        self.assertEqual(out[0]["email"], "")
        self.assertEqual(out[0]["verification_status"], "Not found")
        self.assertIn("Removed personal/free-mail", out[0]["notes"])
        # Business-domain email is preserved untouched.
        self.assertEqual(out[1], {"email": "b@acme.com"})
        # Blank email gets a Not found status but keeps its note.
        self.assertEqual(out[2]["verification_status"], "Not found")
        self.assertEqual(out[2]["notes"], "hi")
        self.assertEqual(app._lead_sanitize_public_business_emails("nope"), [])

    # --- role-family / title-angle text analysis --------------------------

    _CV = (
        "Senior SAP FICO consultant with 10 years in S/4HANA finance "
        "implementations, ABAP debugging and controlling."
    )

    def test_has_any_and_contains_token(self):
        self.assertIs(app._lead_has_any("Senior SAP Consultant", ["sap", "oracle"]), True)
        self.assertIs(app._lead_has_any("Nurse practitioner", ["sap", "oracle"]), False)
        self.assertIs(app._lead_contains_any_token("sap fico consultant", ["fico", "mm"]), True)
        self.assertIs(app._lead_contains_any_token("sap mm consultant", ["fico", "sd"]), False)

    def test_family_scores_and_families(self):
        self.assertEqual(app._lead_family_scores(self._CV), {"sap_erp": 6})
        self.assertEqual(app._lead_families_from_text(self._CV, 3), ["sap_erp"])
        self.assertEqual(
            app._lead_primary_role_families("SAP FICO Consultant", self._CV, "", "ERP"),
            ["sap_erp"],
        )

    def test_resolve_search_target_role(self):
        self.assertEqual(
            app._lead_resolve_search_target_role("SAP FICO Consultant", self._CV, "", "ERP"),
            ("SAP FICO Consultant", ""),
        )
        # With no explicit role, it derives one from the CV family.
        self.assertEqual(
            app._lead_resolve_search_target_role("", self._CV, "", "ERP"),
            ("SAP Consultant", ""),
        )

    def test_cv_evidence_tokens_and_signature(self):
        self.assertEqual(
            sorted(app._lead_cv_evidence_tokens("sap_erp", self._CV)),
            ["s/4hana", "sap fico"],
        )
        family, evidence = app._lead_cv_content_signature(
            "SAP FICO Consultant", self._CV, "", "ERP"
        )
        self.assertEqual(family, "sap_erp")
        self.assertEqual(set(evidence), {"sap fico", "s/4hana"})

    def test_job_title_angles(self):
        angles = app._lead_job_title_angles("SAP FICO Consultant", self._CV, "", "ERP")
        self.assertEqual(angles[0], "SAP FICO Consultant")
        self.assertEqual(len(angles), 19)
        for title in ("SAP Consultant", "S/4HANA Consultant", "ERP Consultant"):
            self.assertIn(title, angles)

    def test_role_specific_title_bank(self):
        bank = app._lead_role_specific_title_bank(
            "SAP FICO Consultant", ["sap", "fico"], self._CV
        )
        self.assertIsInstance(bank, list)
        self.assertEqual(len(bank), 50)
        for title in ("Head of SAP", "SAP FICO Manager", "CFO"):
            self.assertIn(title, bank)


if __name__ == "__main__":
    unittest.main()
