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


if __name__ == "__main__":
    unittest.main()
