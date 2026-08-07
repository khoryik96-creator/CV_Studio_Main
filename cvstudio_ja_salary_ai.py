"""JobAdder salary-AI storage service for CV Studio.

Behaviour-preserving extraction of the salary-AI component cache from the app
shell. The SQLite repository and legacy-JSON cache path are injected as
zero-argument callables (not bound objects) so the service always reads the
current app-level globals at call time -- the Phase 2A storage-corruption route
tests rebind ``_CVSTUDIO_SALARY_REPOSITORY`` / ``_SALARY_AI_CACHE_PATH`` and the
code must observe the rebind. This module never imports ``app``.
"""

from datetime import datetime


class SalaryAiCacheService:
    """Row-level SQLite cache for AI-extracted salary components.

    Mirrors the established cache-service shape (see ``LeadCacheService``):
    dependencies come in through the constructor, storage handles are resolved
    late through callables, and the legacy JSON mirror is kept consistent while
    SQLite stays authoritative.
    """

    def __init__(
        self,
        *,
        repository,
        cache_path,
        lock,
        legacy_json_read,
        legacy_json_write,
        storage_error,
    ):
        # ``repository``/``cache_path`` are zero-arg callables returning the
        # current app globals; ``lock`` is the shared threading lock object.
        self._repository = repository
        self._cache_path = cache_path
        self._lock = lock
        self._legacy_json_read = legacy_json_read
        self._legacy_json_write = legacy_json_write
        self._storage_error = storage_error

    def load(self):
        legacy, fingerprint = self._legacy_json_read(self._cache_path(), dict)
        try:
            if legacy is not None:
                self._repository().import_legacy(legacy, fingerprint)
            return self._repository().load()
        except self._storage_error:
            raise
        except Exception:
            return legacy if isinstance(legacy, dict) else {}

    def import_legacy_locked(self):
        """Import any legacy JSON once (fingerprint-guarded in the repository)."""
        legacy, fingerprint = self._legacy_json_read(self._cache_path(), dict)
        if legacy is not None:
            self._repository().import_legacy(legacy, fingerprint)
        return legacy

    def get(self, cache_key):
        key = str(cache_key or "")
        with self._lock:
            try:
                self.import_legacy_locked()
                item = self._repository().get(key)  # single-row read, no whole-map load
            except self._storage_error:
                raise
            except Exception:
                item = None
        return item if isinstance(item, dict) else None

    def put(self, cache_key, components, provider, model):
        if not cache_key or not isinstance(components, dict):
            return
        entry = {
            "components": components,
            "provider": provider,
            "model": model,
            "savedAt": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        }
        with self._lock:
            try:
                self.import_legacy_locked()
                # Row-level upsert + newest-500 trim in one transaction, instead
                # of loading, mutating and rewriting the entire map.
                self._repository().put(str(cache_key), entry, cap=500)
            except self._storage_error:
                raise
            except Exception:
                return
            try:
                # Keep the legacy JSON mirror consistent with SQLite
                # (compatibility contract). SQLite is authoritative if the mirror
                # cannot be updated.
                self._legacy_json_write(self._cache_path(), self._repository().load(), indent=2)
            except Exception:
                pass
