import tempfile
import unittest
from pathlib import Path

from cvstudio_storage import (
    CVStudioStorage,
    LeadContactCacheRepository,
    LeadTitleCacheRepository,
    PPCMetadataRepository,
    SalaryComponentCacheRepository,
    UsageHistoryRepository,
)


class Phase2ARepositoryTests(unittest.TestCase):
    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory(prefix="cvstudio-repositories-")
        root = Path(self._temporary.name)
        self.storage = CVStudioStorage(root / "state" / "cv_studio.sqlite3")
        self.storage.initialize()

    def tearDown(self):
        self._temporary.cleanup()

    def test_usage_import_is_idempotent_and_preserves_legacy_detail_cutoff(self):
        repository = UsageHistoryRepository(self.storage)
        legacy = [
            {
                "ts": "2026-07-01T01:02:03Z",
                "name": "Legacy fixture",
                "mode": "format",
                "cost": 0.25,
                "model": "legacy-model",
            },
            {
                "id": "stat_fixture_current",
                "ts": "2026-07-02T01:02:03Z",
                "name": "Current fixture",
                "mode": "lead",
                "cost": 0.5,
                "input_tokens": 12,
                "output_tokens": 8,
                "api_calls": 1,
            },
        ]

        self.assertEqual(repository.import_legacy(legacy), 2)
        self.assertEqual(repository.import_legacy(legacy), 0)
        loaded = repository.list()
        self.assertEqual(len(loaded), 2)
        self.assertNotIn("input_tokens", loaded[0])
        self.assertNotIn("api_calls", loaded[0])
        self.assertEqual(loaded[1]["input_tokens"], 12)

        updated = dict(legacy[1], outcome="success", cost_note="fixture")
        self.assertEqual(repository.upsert([updated]), 1)
        self.assertEqual(len(repository.list()), 2)
        self.assertEqual(repository.list()[1]["cost_note"], "fixture")

        stale = dict(legacy[1], outcome="stale-mirror")
        self.assertEqual(repository.import_legacy([stale]), 0)
        self.assertEqual(repository.list()[1]["cost_note"], "fixture")
        self.assertEqual(repository.list()[1]["outcome"], "success")

        repository.clear()
        self.assertEqual(repository.list(), [])

    def test_lead_title_import_deduplicates_signatures_and_save_replaces(self):
        repository = LeadTitleCacheRepository(self.storage)
        legacy = {
            "entries": [
                {
                    "family": "data",
                    "evidence": ["python", "sql"],
                    "titles": ["Data Engineer"],
                    "created_at": "2026-07-01T00:00:00",
                    "hits": 1,
                },
                {
                    "family": "data",
                    "evidence": ["sql", "python"],
                    "titles": ["Senior Data Engineer"],
                    "created_at": "2026-07-02T00:00:00",
                    "hits": 2,
                },
            ]
        }

        self.assertEqual(repository.import_legacy(legacy), 2)
        self.assertEqual(repository.import_legacy(legacy), 0)
        loaded = repository.load()
        self.assertEqual(len(loaded["entries"]), 1)
        self.assertEqual(loaded["entries"][0]["hits"], 2)

        replacement = {
            "entries": [
                {
                    "family": "finance",
                    "evidence": ["audit"],
                    "titles": ["Finance Manager"],
                    "hits": 0,
                }
            ]
        }
        self.assertEqual(repository.save(replacement), 1)
        self.assertEqual(repository.load(), replacement)

    def test_contact_and_salary_documents_round_trip_without_duplicates(self):
        contacts = LeadContactCacheRepository(self.storage)
        contact_document = {
            "entries": {
                "profile:fixture": {
                    "verification_status": "Verified fixture",
                    "cached_at": "2026-07-01T00:00:00",
                    "hits": 3,
                }
            }
        }
        self.assertEqual(contacts.import_legacy(contact_document), 1)
        self.assertEqual(contacts.import_legacy(contact_document), 0)
        self.assertEqual(contacts.load(), contact_document)

        salary = SalaryComponentCacheRepository(self.storage)
        salary_document = {
            "salary-fixture": {
                "components": {"current": {"baseMonthly": 1}},
                "provider": "fixture",
                "model": "fixture-model",
                "savedAt": "2026-07-01T00:00:00Z",
            }
        }
        self.assertEqual(salary.import_legacy(salary_document), 1)
        self.assertEqual(salary.import_legacy(salary_document), 0)
        self.assertEqual(salary.load(), salary_document)

        contacts.clear()
        salary.clear()
        self.assertEqual(contacts.load(), {"entries": {}})
        self.assertEqual(salary.load(), {})

    def test_ppc_metadata_and_diagnostic_state_are_idempotent_and_bounded(self):
        repository = PPCMetadataRepository(self.storage)
        legacy = {
            "placement-fixture": {
                "payment": "Invoiced",
                "guaranteeMonths": "3",
                "updatedAt": "2026-07-01T00:00:00Z",
            }
        }
        self.assertEqual(repository.import_legacy(legacy), 1)
        self.assertEqual(repository.import_legacy(legacy), 0)
        self.assertEqual(repository.load(), legacy)

        changed = {
            "placement-fixture": {
                "payment": "Paid",
                "guaranteeMonths": "3",
                "updatedAt": "2026-07-02T00:00:00Z",
            }
        }
        self.assertEqual(repository.upsert(changed), 1)
        self.assertEqual(repository.load(), changed)

        stale = {
            "placement-fixture": {
                "payment": "Unpaid",
                "guaranteeMonths": "3",
                "updatedAt": "2026-07-01T12:00:00Z",
            }
        }
        self.assertEqual(repository.import_legacy(stale), 0)
        self.assertEqual(repository.load(), changed)

        timestamp_free = {
            "placement-fixture": {
                "payment": "Unpaid",
                "guaranteeMonths": "3",
            }
        }
        self.assertEqual(repository.import_legacy(timestamp_free), 0)
        self.assertEqual(repository.load(), changed)

        newer = {
            "placement-fixture": {
                "payment": "Invoiced",
                "guaranteeMonths": "3",
                "updatedAt": "2026-07-03T00:00:00Z",
            }
        }
        self.assertEqual(repository.import_legacy(newer), 1)
        self.assertEqual(repository.load(), newer)

        self.storage.diagnostic_state_set(
            "last_migration",
            {
                "version": 7,
                "name": "diagnostic_state_repository",
                "applied_at": "2026-07-01T00:00:00Z",
                "ignored_field": "not persisted",
            },
        )
        diagnostic = self.storage.diagnostic_state_get("last_migration")
        self.assertEqual(diagnostic["version"], 7)
        self.assertNotIn("ignored_field", diagnostic)
        self.assertIsNone(self.storage.diagnostic_state_get("unsupported"))

        repository.clear()
        self.assertEqual(repository.load(), {})


if __name__ == "__main__":
    unittest.main()
