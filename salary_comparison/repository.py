from __future__ import annotations

import json
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any

from .validators import RuleValidationError, validate_rule


class RuleNotFoundError(LookupError):
    pass


class RuleRepositoryError(RuntimeError):
    pass


class JsonRuleRepository:
    _locks_guard = threading.Lock()
    _locks: dict[str, threading.RLock] = {}

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        key = str(self.path.resolve())
        with self._locks_guard:
            self._lock = self._locks.setdefault(key, threading.RLock())
        if not self.path.exists():
            self._write({"rules": []})

    def _read(self) -> dict[str, Any]:
        with self._lock:
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
            except FileNotFoundError:
                payload = {"rules": []}
                self._write(payload)
            except json.JSONDecodeError as exc:
                raise RuleRepositoryError(
                    f"Tax-rule data is not valid JSON: {self.path.name}. Restore the file or replace it with a backup."
                ) from exc
            except OSError as exc:
                raise RuleRepositoryError(f"Unable to read tax-rule data: {exc}") from exc
            if not isinstance(payload, dict) or not isinstance(payload.get("rules", []), list):
                raise RuleRepositoryError("Tax-rule data must contain a top-level rules list.")
            return payload

    def _write(self, payload: dict[str, Any]) -> None:
        with self._lock:
            temp = self.path.with_suffix(self.path.suffix + ".tmp")
            try:
                temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
                temp.replace(self.path)
            except OSError as exc:
                try:
                    temp.unlink(missing_ok=True)
                except OSError:
                    pass
                raise RuleRepositoryError(f"Unable to save tax-rule data: {exc}") from exc

    def list_rules(self) -> list[dict[str, Any]]:
        rules: list[dict[str, Any]] = []
        for index, rule in enumerate(self._read().get("rules") or []):
            try:
                rules.append(validate_rule(rule))
            except RuleValidationError as exc:
                raise RuleRepositoryError(f"Stored tax rule {index + 1} is invalid: {exc}") from exc
        return deepcopy(rules)

    def get_rule(self, country: str, tax_year: int, residency: str) -> dict[str, Any]:
        country_key = str(country or "").strip().casefold()
        residency_key = str(residency or "").strip().casefold()
        try:
            year_key = int(tax_year)
        except (TypeError, ValueError) as exc:
            raise RuleNotFoundError("Tax year must be a whole number.") from exc

        for rule in self._read().get("rules") or []:
            if (
                str(rule.get("country", "")).strip().casefold() == country_key
                and int(rule.get("tax_year")) == year_key
                and str(rule.get("residency", "")).strip().casefold() == residency_key
            ):
                try:
                    return deepcopy(validate_rule(rule))
                except RuleValidationError as exc:
                    raise RuleRepositoryError(f"Stored tax rule is invalid: {exc}") from exc
        raise RuleNotFoundError(f"No rules for {str(country).strip()}, {year_key}, {str(residency).strip()}.")

    def publish(self, rule: dict[str, Any]) -> dict[str, Any]:
        normalized = validate_rule(rule)
        with self._lock:
            payload = self._read()
            rules = list(payload.get("rules") or [])
            rules = [
                existing
                for existing in rules
                if not (
                    str(existing.get("country", "")).strip().casefold() == normalized["country"].casefold()
                    and int(existing.get("tax_year")) == normalized["tax_year"]
                    and str(existing.get("residency", "")).strip().casefold() == normalized["residency"].casefold()
                )
            ]
            rules.append(normalized)
            rules.sort(key=lambda item: (str(item["country"]).casefold(), int(item["tax_year"]), str(item["residency"]).casefold()))
            payload["rules"] = rules
            self._write(payload)
        return deepcopy(normalized)
