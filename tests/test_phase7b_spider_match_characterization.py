"""Characterization coverage for the pure Spider (AI Crawler) field-parsing
helpers before they move from the legacy web shell into
``cvstudio_spider_boolean.py`` (the spider pure-matching module).

Imports through ``app`` so it passes identically before the extraction
(functions in app.py) and after it (app.py re-exports them).
"""

import os
from pathlib import Path
import tempfile
import unittest

from owner_build_tools.build_protected import write_test_receipt


ROOT = Path(__file__).resolve().parents[1]

_MODULE_TEMPORARY = tempfile.TemporaryDirectory(prefix="cvstudio-spider-match-")
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


_CANDIDATE = {
    "candidateId": 12345,
    "firstName": "Jane",
    "lastName": "Doe",
    "email": "jane@acme.com",
    "summary": "Senior SAP FICO consultant, Malaysian citizen, open to remote.",
    "employment": [{"start": "2018-01", "end": "2023-06", "title": "SAP Consultant"}],
    "customFields": [{"name": "Residential Status", "value": "Malaysian Citizen"}],
}


class SpiderMatchCharacterizationTests(unittest.TestCase):
    def test_years_helpers(self):
        self.assertEqual(app._spider_min_years_value("5+ years"), 0)
        self.assertEqual(app._spider_min_years_value(5), 5)
        self.assertEqual(app._spider_min_years_value("3-7"), 0)
        self.assertEqual(app._spider_min_years_value(None), 0)
        self.assertIsNone(app._spider_max_years_value("3-7"))
        self.assertIsNone(app._spider_max_years_value("up to 10"))
        self.assertEqual(app._spider_years_bounds({"min_years": 3, "max_years": 8}), (0, None))
        self.assertEqual(app._spider_years_bounds({}), (0, None))

    def test_parse_employment_month(self):
        self.assertEqual(app._spider_parse_employment_month("2020-03", False), 24242)
        self.assertEqual(app._spider_parse_employment_month("Jan 2019", True), 24239)
        self.assertIsNone(app._spider_parse_employment_month("", False))

    def test_flatten_stringifies(self):
        self.assertEqual(app._spider_flatten([[1, [2]], 3, "x"]), ["1", "2", "3", "x"])

    def test_has_any(self):
        self.assertIs(app._spider_has_any("senior sap consultant", ["sap", "oracle"]), True)
        self.assertIs(app._spider_has_any("nurse", ["sap"]), False)

    def test_status_and_residential_aliases(self):
        self.assertEqual(
            app._spider_status_aliases("citizen"),
            ["citizen", "citizenship", "local citizen", "malaysian citizen", "singapore citizen"],
        )
        self.assertEqual(
            app._spider_status_aliases("PR"),
            ["permanent resident", "permanent residency", "pr status", "pr holder"],
        )
        self.assertEqual(app._spider_status_target("Permanent Resident"), "permanent_resident")
        self.assertEqual(app._spider_residential_classes("Malaysian citizen"), {"citizen"})
        self.assertEqual(app._spider_residential_classes("work permit holder"), {"work_visa"})

    def test_work_setup_aliases(self):
        self.assertEqual(app._spider_work_setup_aliases("remote"), ["remote", "work from home", "wfh"])
        self.assertEqual(app._spider_work_setup_aliases("hybrid"), ["hybrid"])

    def test_candidate_field_helpers(self):
        self.assertEqual(app._spider_candidate_id(_CANDIDATE), "12345")
        self.assertEqual(app._spider_pick_field_text(_CANDIDATE, ["email"]), "jane@acme.com")
        self.assertEqual(app._spider_residential_status_text(_CANDIDATE), "Malaysian Citizen")
        blob = app._spider_candidate_blob(_CANDIDATE)
        self.assertIsInstance(blob, str)
        for token in ("jane@acme.com", "SAP Consultant", "Malaysian Citizen"):
            self.assertIn(token, blob)

    def test_country_aliases(self):
        my = app._spider_country_aliases("Malaysia")
        self.assertEqual(my[0], "malaysia")
        self.assertIn("kuala lumpur", my)
        self.assertIn("penang", my)
        # ISO code resolves to the same canonical alias list.
        self.assertEqual(app._spider_country_aliases("MY"), my)
        # An unknown country falls back to the raw term.
        self.assertEqual(app._spider_country_aliases("Narnia"), ["Narnia"])

    def test_country_profile(self):
        my = app._spider_country_profile("Malaysia")
        self.assertEqual(my["canonical"], "malaysia")
        self.assertEqual(my["names"], ["malaysia"])
        self.assertEqual(my["codes"], {"MYS", "MY"})
        self.assertIn("kuala lumpur", my["places"])
        sg = app._spider_country_profile("Singapore")
        self.assertEqual(sg["canonical"], "singapore")
        self.assertEqual(sg["codes"], {"SG", "SGP"})
        narnia = app._spider_country_profile("Narnia")
        self.assertEqual(narnia["canonical"], "narnia")
        self.assertEqual(narnia["codes"], set())
        self.assertEqual(narnia["places"], [])

    def test_location_identity_and_country_match(self):
        cand = {
            "summary": "Based in Kuala Lumpur, Malaysia. Malaysian citizen.",
            "address": {"country": "Malaysia"},
        }
        self.assertEqual(
            app._spider_location_identity(cand), (set(), "Malaysia", "country Malaysia")
        )
        self.assertEqual(app._spider_country_match(cand, "Malaysia"), ("match", "Malaysia"))
        self.assertEqual(
            app._spider_country_match(cand, "Singapore"), ("mismatch", "Malaysia")
        )

    def test_country_constants_reexported(self):
        for name in (
            "_SPIDER_COUNTRY_DEFINITIONS",
            "_SPIDER_COUNTRY_NAME_LOOKUP",
            "_SPIDER_COUNTRY_CODE_LOOKUP",
        ):
            self.assertIsInstance(getattr(app, name), dict)
        # Lookups are populated from the definitions build loop.
        self.assertIn("malaysia", app._SPIDER_COUNTRY_NAME_LOOKUP)
        self.assertIn("MY", app._SPIDER_COUNTRY_CODE_LOOKUP)

    def test_all_helpers_reexported(self):
        for name in (
            "_spider_min_years_value", "_spider_max_years_value", "_spider_years_bounds",
            "_spider_parse_employment_month", "_spider_structured_employment_years",
            "_spider_visible_years", "_spider_flatten", "_spider_candidate_blob",
            "_spider_pick_field_text", "_spider_has_any", "_spider_status_aliases",
            "_spider_status_target", "_spider_residential_status_text",
            "_spider_residential_classes", "_spider_work_setup_aliases", "_spider_candidate_id",
            "_spider_country_profile", "_spider_country_aliases",
            "_spider_location_identity", "_spider_country_match",
        ):
            self.assertTrue(callable(getattr(app, name)), name)


if __name__ == "__main__":
    unittest.main()
