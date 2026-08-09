"""Lead Finder title/contact cache (Phase 7B).

Behaviour-preserving extraction of the file-backed title-angle cache and
contact-email cache from the legacy web shell. Storage (the SQLite-backed
repository, the legacy-JSON dual-write path, and ``StorageError``) stays
owned by the application; this module receives those as explicit
dependencies at construction, so it never imports ``app``. The repositories
and path constants are injected as zero-argument callables (not the bound
objects/strings) because tests reassign those app-level globals after import
-- e.g. to a corrupt-storage repository -- and expect the cache to read the
current value on every call, not a value captured at construction.
"""

from __future__ import annotations

from datetime import datetime, timezone


class LeadCacheService:
    def __init__(
        self,
        *,
        title_repository,
        contact_repository,
        title_path,
        contact_path,
        legacy_json_read,
        legacy_json_write,
        storage_error,
        title_max_entries,
        contact_max_entries,
        title_sim_threshold,
        normalize_linkedin_url,
        is_company_domain_email,
    ):
        # ``title_repository``/``contact_repository`` are zero-arg callables that
        # resolve the current app-level repository global at call time (see the
        # module docstring: tests rebind these to a corrupt-storage repository).
        self._title_repository = title_repository
        self._contact_repository = contact_repository
        self._title_path = title_path
        self._contact_path = contact_path
        self._legacy_json_read = legacy_json_read
        self._legacy_json_write = legacy_json_write
        self._storage_error = storage_error
        self._title_max_entries = title_max_entries
        self._contact_max_entries = contact_max_entries
        self._title_sim_threshold = title_sim_threshold
        self._normalize_linkedin_url = normalize_linkedin_url
        self._is_company_domain_email = is_company_domain_email

    # ── title cache ─────────────────────────────────────────────────────
    def title_cache_load(self):
        repository = self._title_repository()
        legacy, fingerprint = self._legacy_json_read(self._title_path(), dict)
        try:
            if isinstance(legacy, dict) and isinstance(legacy.get("entries"), list):
                repository.import_legacy(legacy, fingerprint)
            return repository.load()
        except self._storage_error:
            raise
        except Exception:
            if isinstance(legacy, dict) and isinstance(legacy.get("entries"), list):
                return legacy
            return {"entries": []}

    def title_cache_save(self, data):
        try:
            self._title_repository().save(data)
            try:
                self._legacy_json_write(self._title_path(), data)
            except Exception:
                pass
        except self._storage_error:
            raise
        except Exception:
            pass

    def title_cache_find(self, family, evidence, threshold=None):
        if threshold is None:
            threshold = self._title_sim_threshold
        data = self.title_cache_load()
        best, best_score = None, 0.0
        for entry in data.get("entries", []):
            if entry.get("family") != family:
                continue
            ev = set(entry.get("evidence") or [])
            if not ev or not evidence:
                continue
            inter = len(ev & evidence)
            union = len(ev | evidence)
            score = (inter / union) if union else 0.0
            if score > best_score:
                best_score, best = score, entry
        if best and best_score >= threshold:
            return best, best_score
        return None, 0.0

    def title_cache_store(self, family, evidence, titles):
        data = self.title_cache_load()
        entries = data.get("entries", [])
        entries.append({
            "family": family,
            "evidence": sorted(evidence),
            "titles": titles,
            "created_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
            "hits": 0,
        })
        if len(entries) > self._title_max_entries:
            entries = entries[-self._title_max_entries:]
        data["entries"] = entries
        self.title_cache_save(data)

    def title_cache_touch(self, matched_entry):
        """Best-effort hit counter. Not critical if a concurrent write races it."""
        try:
            data = self.title_cache_load()
            for e in data.get("entries", []):
                if e.get("family") == matched_entry.get("family") and e.get("evidence") == matched_entry.get("evidence"):
                    e["hits"] = int(e.get("hits") or 0) + 1
                    break
            self.title_cache_save(data)
        except Exception:
            pass

    # ── contact cache ───────────────────────────────────────────────────
    def contact_cache_load(self):
        repository = self._contact_repository()
        legacy, fingerprint = self._legacy_json_read(self._contact_path(), dict)
        try:
            if isinstance(legacy, dict) and isinstance(legacy.get("entries"), dict):
                repository.import_legacy(legacy, fingerprint)
            return repository.load()
        except self._storage_error:
            raise
        except Exception:
            if isinstance(legacy, dict) and isinstance(legacy.get("entries"), dict):
                return legacy
            return {"entries": {}}

    def contact_cache_save(self, data):
        try:
            self._contact_repository().save(data)
            try:
                self._legacy_json_write(self._contact_path(), data)
            except Exception:
                pass
        except self._storage_error:
            raise
        except Exception:
            pass

    def contact_cache_key(self, person):
        """A LinkedIn profile URL is the most reliable identity anchor when present
        (two different people are essentially never the same profile URL). Falling
        back to name+company is a reasonable second choice, but is more prone to
        collisions (common names, similarly-named companies) so is only used when
        no profile URL is available at all.
        """
        import re

        person = person or {}
        li = self._normalize_linkedin_url(person.get("profile_url") or person.get("linkedin_url"))
        if li:
            return "li:" + li
        name = re.sub(r"\s+", " ", str(person.get("name") or "").strip().lower())
        company = re.sub(r"\s+", " ", str(person.get("company") or "").strip().lower())
        if name and company:
            return "nc:" + name + "|" + company
        return ""

    def contact_cache_find(self, person):
        key = self.contact_cache_key(person)
        if not key:
            return None
        data = self.contact_cache_load()
        cached = data.get("entries", {}).get(key)
        if not isinstance(cached, dict):
            return None
        # Do not let previous misses become permanent. A cached "Not found" with
        # no email is retry-eligible, so Apollo/AI can try again on a later run.
        if not str(cached.get("email") or "").strip() and str(cached.get("verification_status") or "").strip().lower() == "not found":
            return None
        return cached

    def contact_cache_store(self, person, email_data):
        key = self.contact_cache_key(person)
        if not key:
            return
        email_data = dict(email_data or {})
        email = str(email_data.get("email") or "").strip()
        if not email or not self._is_company_domain_email(email, (person or {}).get("company") or email_data.get("company") or ""):
            # Failed/Not-found/personal-email results should not poison the cache.
            # If an older version cached a miss, remove it so the person can be retried.
            data = self.contact_cache_load()
            entries = data.get("entries", {})
            if key in entries:
                entries.pop(key, None)
                data["entries"] = entries
                self.contact_cache_save(data)
            return
        data = self.contact_cache_load()
        entries = data.get("entries", {})
        existing = entries.get(key) or {}
        entries[key] = {
            "email": email,
            "email_confidence": email_data.get("email_confidence", ""),
            "email_source": email_data.get("email_source", ""),
            "verification_status": email_data.get("verification_status", ""),
            "cached_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
            "hits": int(existing.get("hits") or 0),
        }
        if len(entries) > self._contact_max_entries:
            # Drop the least-reused entries first, matching the merge tool's logic.
            ordered = sorted(entries.items(), key=lambda kv: int(kv[1].get("hits") or 0))
            for k, _ in ordered[: len(entries) - self._contact_max_entries]:
                entries.pop(k, None)
        data["entries"] = entries
        self.contact_cache_save(data)

    def contact_cache_touch(self, person):
        try:
            key = self.contact_cache_key(person)
            if not key:
                return
            data = self.contact_cache_load()
            entries = data.get("entries", {})
            if key in entries:
                entries[key]["hits"] = int(entries[key].get("hits") or 0) + 1
                self.contact_cache_save(data)
        except Exception:
            pass
