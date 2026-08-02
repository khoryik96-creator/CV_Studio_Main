"""AI secret-store management service for CV Studio.

The application remains responsible for registering the ``/secure-secrets/*``
routes and for owning the shared, machine-bound secret store and its secure
save/delete primitives (which other domains such as JobAdder and OneNote also
use).  This module receives that shared state and those primitives through
explicit callbacks and never imports the application.  The slot validation,
in-place mutation and storage bookkeeping are a verbatim move of the legacy
web-shell handlers so the observable behaviour and response payloads are
unchanged.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping


class SecretsService:
    """Explicitly wired handlers behind the AI secret-store endpoints."""

    def __init__(
        self,
        *,
        jsonify: Callable[[Any], Any],
        request_json: Callable[[], Any],
        secret_store: Callable[[], dict],
        secret_slots: Callable[[], Any],
        secure_save: Callable[[str, Mapping[str, Any]], str],
        secure_delete: Callable[[str], Any],
    ):
        self._jsonify = jsonify
        self._request_json = request_json
        self._secret_store = secret_store
        self._secret_slots = secret_slots
        self._secure_save = secure_save
        self._secure_delete = secure_delete

    def info(self):
        store = self._secret_store()
        slots = self._secret_slots()
        return self._jsonify({"configured": {slot: bool(str(store.get(slot) or "").strip()) for slot in sorted(slots)}, "storage": store.get("_storage", "backend_secure_store")})

    def save(self):
        store = self._secret_store()
        slots = self._secret_slots()
        data = self._request_json() or {}
        updates = data.get("secrets") if isinstance(data.get("secrets"), dict) else {}
        for slot, value in updates.items():
            slot = str(slot or "").strip().lower()
            if slot not in slots:
                continue
            value = str(value or "").strip()
            if value:
                store[slot] = value
            elif bool(data.get("clear_blank")):
                store.pop(slot, None)
        store["_storage"] = self._secure_save("ai", {k: v for k, v in store.items() if k in slots})
        return self.info()

    def clear(self):
        store = self._secret_store()
        slots = self._secret_slots()
        data = self._request_json() or {}
        requested = data.get("slots") if isinstance(data.get("slots"), list) else []
        for slot in requested:
            if slot in slots:
                store.pop(slot, None)
        if any(k in slots for k in store):
            store["_storage"] = self._secure_save("ai", {k: v for k, v in store.items() if k in slots})
        else:
            self._secure_delete("ai")
        return self.info()
