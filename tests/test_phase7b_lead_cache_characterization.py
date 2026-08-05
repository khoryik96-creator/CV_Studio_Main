"""Characterization tests for the Lead Finder title/contact cache.

Locks the behaviour of the title-angle cache and contact-email cache before
and after the logic is moved out of the legacy web shell into
``cvstudio_lead_cache.LeadCacheService`` (Phase 7B). This is a verbatim move,
so the assertions equally describe the legacy web-shell behaviour.

Exercised through the ``app._lead_*`` delegators against a temp-backed store so
the same test verifies both the extracted logic and the injection wiring.
``load``/``save`` legacy-JSON dual-write and SQLite-first reads are covered by
``test_phase2a_app_cache_integration``; this file covers ``find``/``store``/
``touch``/``key`` and the contact miss/eviction semantics.
"""

import os
from pathlib import Path
import tempfile
import unittest


_MODULE_TEMPORARY = tempfile.TemporaryDirectory(prefix="cvstudio-lead-cache-")
_MODULE_ROOT = Path(_MODULE_TEMPORARY.name)
_ORIGINAL_LOCAL_STATE = os.environ.get("LOCALAPPDATA")
_ORIGINAL_DATABASE_OVERRIDE = os.environ.get("CVSTUDIO_DB_PATH")
os.environ["LOCALAPPDATA"] = str(_MODULE_ROOT / "local-state")
os.environ["CVSTUDIO_DB_PATH"] = str(_MODULE_ROOT / "local-state" / "cv_studio.sqlite3")

from owner_build_tools.build_protected import write_test_receipt

write_test_receipt(Path(__file__).resolve().parents[1])

import app


class Phase7BLeadCacheCharacterizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.legacy_root = _MODULE_ROOT / "legacy"
        cls.legacy_root.mkdir(parents=True, exist_ok=True)
        app._LEAD_TITLE_CACHE_PATH = str(cls.legacy_root / "lead_title_cache.json")
        app._LEAD_CONTACT_CACHE_PATH = str(cls.legacy_root / "lead_contact_cache.json")

    @classmethod
    def tearDownClass(cls):
        if _ORIGINAL_LOCAL_STATE is None:
            os.environ.pop("LOCALAPPDATA", None)
        else:
            os.environ["LOCALAPPDATA"] = _ORIGINAL_LOCAL_STATE
        if _ORIGINAL_DATABASE_OVERRIDE is None:
            os.environ.pop("CVSTUDIO_DB_PATH", None)
        else:
            os.environ["CVSTUDIO_DB_PATH"] = _ORIGINAL_DATABASE_OVERRIDE
        _MODULE_TEMPORARY.cleanup()

    def setUp(self):
        app._CVSTUDIO_LEAD_TITLE_REPOSITORY.clear()
        app._CVSTUDIO_LEAD_CONTACT_REPOSITORY.clear()
        for path in (
            Path(app._LEAD_TITLE_CACHE_PATH),
            Path(app._LEAD_CONTACT_CACHE_PATH),
        ):
            path.unlink(missing_ok=True)

    # ── path-callable seam ──────────────────────────────────────────────
    def test_service_reads_current_path_globals_not_construction_time(self):
        # The service must read app._LEAD_TITLE_CACHE_PATH on each call (the
        # setUpClass reassignment above only works because of this seam).
        app._lead_title_cache_store("data", {"python", "sql"}, ["Data Engineer"])
        self.assertTrue(Path(app._LEAD_TITLE_CACHE_PATH).is_file())

    # ── title cache: find / store / touch ───────────────────────────────
    def test_title_store_then_find_by_jaccard_similarity(self):
        app._lead_title_cache_store("data", {"python", "sql", "etl"}, ["Data Engineer", "ETL Developer"])
        entry, score = app._lead_title_cache_find("data", {"python", "sql", "etl"})
        self.assertIsNotNone(entry)
        self.assertEqual(entry["titles"], ["Data Engineer", "ETL Developer"])
        self.assertEqual(score, 1.0)

    def test_title_find_respects_family_and_threshold(self):
        app._lead_title_cache_store("data", {"python", "sql", "etl", "spark"}, ["Data Engineer"])
        # Different family never matches.
        self.assertEqual(app._lead_title_cache_find("finance", {"python", "sql", "etl", "spark"}), (None, 0.0))
        # One shared token of four-token evidence => jaccard 1/4 = 0.25 < 0.45.
        self.assertEqual(app._lead_title_cache_find("data", {"python"}), (None, 0.0))
        # Three shared of four => 3/4 = 0.75 >= 0.45.
        entry, score = app._lead_title_cache_find("data", {"python", "sql", "etl"})
        self.assertIsNotNone(entry)
        self.assertAlmostEqual(score, 0.75)

    def test_title_find_empty_evidence_never_matches(self):
        app._lead_title_cache_store("data", {"python"}, ["Data Engineer"])
        self.assertEqual(app._lead_title_cache_find("data", set()), (None, 0.0))

    def test_title_store_sorts_evidence_and_seeds_hits(self):
        app._lead_title_cache_store("data", {"sql", "python", "etl"}, ["Data Engineer"])
        data = app._lead_title_cache_load()
        entry = data["entries"][0]
        self.assertEqual(entry["evidence"], ["etl", "python", "sql"])
        self.assertEqual(entry["hits"], 0)

    def test_title_touch_increments_matching_entry_only(self):
        app._lead_title_cache_store("data", {"python", "sql"}, ["Data Engineer"])
        app._lead_title_cache_store("finance", {"audit"}, ["Finance Manager"])
        matched, _ = app._lead_title_cache_find("data", {"python", "sql"})
        app._lead_title_cache_touch(matched)
        data = app._lead_title_cache_load()
        by_family = {e["family"]: e["hits"] for e in data["entries"]}
        self.assertEqual(by_family["data"], 1)
        self.assertEqual(by_family["finance"], 0)

    # ── contact cache: key / find / store / touch ───────────────────────
    def test_contact_key_prefers_linkedin_then_name_company(self):
        li = app._lead_contact_cache_key({"profile_url": "https://www.linkedin.com/in/ada-lovelace/"})
        self.assertTrue(li.startswith("li:"))
        nc = app._lead_contact_cache_key({"name": "Ada Lovelace", "company": "Acme"})
        self.assertEqual(nc, "nc:ada lovelace|acme")
        self.assertEqual(app._lead_contact_cache_key({"name": "Ada"}), "")

    def test_contact_store_and_find_business_email(self):
        person = {"name": "Ada Lovelace", "company": "Acme"}
        app._lead_contact_cache_store(person, {"email": "ada@acme.io", "verification_status": "Verified business email"})
        cached = app._lead_contact_cache_find(person)
        self.assertIsNotNone(cached)
        self.assertEqual(cached["email"], "ada@acme.io")

    def test_contact_store_rejects_personal_email(self):
        person = {"name": "Ada Lovelace", "company": "Acme"}
        app._lead_contact_cache_store(person, {"email": "ada@gmail.com"})
        self.assertIsNone(app._lead_contact_cache_find(person))

    def test_contact_find_treats_cached_not_found_as_retry_eligible(self):
        # Directly seed a "Not found" miss and confirm find() returns None so a
        # later run can retry it, rather than the miss becoming permanent.
        person = {"name": "Ada Lovelace", "company": "Acme"}
        key = app._lead_contact_cache_key(person)
        app._lead_contact_cache_save({"entries": {key: {"email": "", "verification_status": "Not found"}}})
        self.assertIsNone(app._lead_contact_cache_find(person))

    def test_contact_store_evicts_prior_miss(self):
        person = {"name": "Ada Lovelace", "company": "Acme"}
        key = app._lead_contact_cache_key(person)
        app._lead_contact_cache_save({"entries": {key: {"email": "", "verification_status": "Not found"}}})
        # Storing another miss should remove the stale key entirely.
        app._lead_contact_cache_store(person, {"email": ""})
        self.assertNotIn(key, app._lead_contact_cache_load().get("entries", {}))

    def test_contact_touch_increments_hits(self):
        person = {"name": "Ada Lovelace", "company": "Acme"}
        app._lead_contact_cache_store(person, {"email": "ada@acme.io"})
        app._lead_contact_cache_touch(person)
        key = app._lead_contact_cache_key(person)
        self.assertEqual(app._lead_contact_cache_load()["entries"][key]["hits"], 1)


if __name__ == "__main__":
    unittest.main()
