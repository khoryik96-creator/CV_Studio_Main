import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from cvstudio_storage import (
    CVStudioStorage,
    LeadContactCacheRepository,
    LeadTitleCacheRepository,
    PPCMetadataRepository,
    SalaryComponentCacheRepository,
    UsageHistoryRepository,
)


class Phase2AV217FixtureTests(unittest.TestCase):
    def test_complete_v217_fixture_imported_twice_without_loss_or_legacy_changes(self):
        with tempfile.TemporaryDirectory(prefix="cvstudio-v217-fixture-") as temporary:
            root = Path(temporary)
            legacy_root = root / "legacy"
            legacy_root.mkdir()
            database = root / "state" / "cv_studio.sqlite3"

            usage = [
                {
                    "ts": "2026-07-01T00:00:00Z",
                    "name": "Legacy fixture",
                    "mode": "format",
                    "cost": 0.125,
                    "model": "legacy-model",
                }
            ]
            titles = {
                "entries": [
                    {
                        "family": "data",
                        "evidence": ["python", "sql"],
                        "titles": ["Data Engineer"],
                        "created_at": "2026-07-01T00:00:00",
                        "hits": 1,
                    }
                ]
            }
            contacts = {
                "entries": {
                    "profile:fixture": {
                        "verification_status": "Verified fixture",
                        "cached_at": "2026-07-01T00:00:00",
                        "hits": 1,
                    }
                }
            }
            salary = {
                "salary-fixture": {
                    "components": {"current": {"baseMonthly": 1}},
                    "provider": "fixture",
                    "model": "fixture-model",
                    "savedAt": "2026-07-01T00:00:00Z",
                }
            }
            ppc = {
                "placement-fixture": {
                    "payment": "Invoiced",
                    "guaranteeMonths": "3",
                    "updatedAt": "2026-07-01T00:00:00Z",
                }
            }
            fixture_documents = {
                "usage_history.json": usage,
                "lead_title_cache.json": titles,
                "lead_contact_cache.json": contacts,
                "salary_ai_component_cache.json": salary,
                "ppc_metadata.json": ppc,
            }
            original_bytes = {}
            for name, payload in fixture_documents.items():
                raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                path = legacy_root / name
                path.write_bytes(raw)
                original_bytes[name] = raw

            storage = CVStudioStorage(database)
            storage.initialize()
            usage_repository = UsageHistoryRepository(storage)
            title_repository = LeadTitleCacheRepository(storage)
            contact_repository = LeadContactCacheRepository(storage)
            salary_repository = SalaryComponentCacheRepository(storage)
            ppc_repository = PPCMetadataRepository(storage)

            imports = (
                (usage_repository, usage, "usage_history.json"),
                (title_repository, titles, "lead_title_cache.json"),
                (contact_repository, contacts, "lead_contact_cache.json"),
                (salary_repository, salary, "salary_ai_component_cache.json"),
                (ppc_repository, ppc, "ppc_metadata.json"),
            )
            first_counts = []
            second_counts = []
            for repository, payload, name in imports:
                fingerprint = hashlib.sha256(original_bytes[name]).hexdigest()
                first_counts.append(repository.import_legacy(payload, fingerprint))
                second_counts.append(repository.import_legacy(payload, fingerprint))

            self.assertEqual(first_counts, [1, 1, 1, 1, 1])
            self.assertEqual(second_counts, [0, 0, 0, 0, 0])
            self.assertEqual(usage_repository.list(), usage)
            self.assertEqual(title_repository.load(), titles)
            self.assertEqual(contact_repository.load(), contacts)
            self.assertEqual(salary_repository.load(), salary)
            self.assertEqual(ppc_repository.load(), ppc)
            self.assertNotIn("input_tokens", usage_repository.list()[0])
            self.assertNotIn("api_calls", usage_repository.list()[0])

            for name, raw in original_bytes.items():
                self.assertEqual((legacy_root / name).read_bytes(), raw)

            backup_names = [item["backup_name"] for item in storage.migration_history()]
            restarted = CVStudioStorage(database)
            restarted.initialize()
            self.assertEqual(
                [item["backup_name"] for item in restarted.migration_history()],
                backup_names,
            )
            self.assertEqual(restarted.recheck_integrity(), "ok")


if __name__ == "__main__":
    unittest.main()
