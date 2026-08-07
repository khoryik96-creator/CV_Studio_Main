"""Characterization coverage for the extracted salary-AI cache service.

SalaryAiCacheService was lifted out of the app shell into cvstudio_ja_salary_ai.py.
These tests exercise the service in isolation with fakes (so no real storage is
touched) and confirm the late-binding seam the Phase 2A storage-corruption route
test depends on: the repository/cache-path are resolved through callables at call
time, not captured at construction.
"""

import threading
import unittest


class _FakeStorageError(Exception):
    pass


class _FakeRepo:
    def __init__(self):
        self.rows = {}
        self.imported = []

    def import_legacy(self, legacy, fingerprint):
        self.imported.append((legacy, fingerprint))

    def load(self):
        return dict(self.rows)

    def get(self, key):
        return self.rows.get(key)

    def put(self, key, entry, cap=None):
        self.rows[key] = entry


def _service(repo_box, writes, reads=(None, "")):
    from cvstudio_ja_salary_ai import SalaryAiCacheService

    return SalaryAiCacheService(
        repository=lambda: repo_box["repo"],
        cache_path=lambda: repo_box["path"],
        lock=threading.Lock(),
        legacy_json_read=lambda path, expected: reads,
        legacy_json_write=lambda path, data, indent=None: writes.append((path, data)),
        storage_error=_FakeStorageError,
    )


class SalaryAiCacheServiceTests(unittest.TestCase):
    def test_put_then_get_roundtrip_and_mirror_write(self):
        box = {"repo": _FakeRepo(), "path": "/tmp/x.json"}
        writes = []
        svc = _service(box, writes)
        svc.put("k1", {"base": 5000}, "deepseek", "v4")
        got = svc.get("k1")
        self.assertEqual(got["components"]["base"], 5000)
        self.assertEqual(got["provider"], "deepseek")
        self.assertIn("savedAt", got)
        self.assertTrue(writes, "legacy JSON mirror should be written on put")

    def test_put_ignores_invalid_input(self):
        box = {"repo": _FakeRepo(), "path": "/tmp/x.json"}
        svc = _service(box, [])
        svc.put("", {"base": 1}, "p", "m")
        svc.put("k", "not-a-dict", "p", "m")
        self.assertEqual(box["repo"].rows, {})

    def test_get_reads_the_current_repository_late_bound(self):
        box = {"repo": _FakeRepo(), "path": "/tmp/x.json"}
        svc = _service(box, [])
        svc.put("k", {"base": 1}, "p", "m")
        # Rebind the repository (as the Phase 2A corruption test does); the
        # service must observe the new object, not a captured reference.
        box["repo"] = _FakeRepo()
        self.assertIsNone(svc.get("k"))

    def test_service_is_wired_into_app_delegators(self):
        import app

        self.assertEqual(type(app._SALARY_AI_CACHE_SERVICE).__name__, "SalaryAiCacheService")
        for name in (
            "_ja_salary_ai_cache_load",
            "_ja_salary_ai_cache_get",
            "_ja_salary_ai_cache_put",
            "_ja_salary_ai_cache_import_legacy_locked",
        ):
            self.assertTrue(callable(getattr(app, name)), name)

    def test_module_never_imports_app(self):
        import inspect

        import cvstudio_ja_salary_ai

        self.assertNotIn("import app", inspect.getsource(cvstudio_ja_salary_ai))


if __name__ == "__main__":
    unittest.main()
