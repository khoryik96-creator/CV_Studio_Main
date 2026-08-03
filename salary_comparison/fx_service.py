from __future__ import annotations

import json
import math
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


class FxServiceError(RuntimeError):
    pass


class FxService:
    _locks_guard = threading.Lock()
    _locks: dict[str, threading.RLock] = {}

    def __init__(
        self,
        cache_path: Path,
        endpoint: str = "https://api.frankfurter.dev/v2/rate/{base}/{quote}",
        max_age_hours: float = 24,
    ):
        self.cache_path = Path(cache_path)
        self.endpoint = endpoint
        self.max_age_hours = max(0.0, float(max_age_hours))
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        key = str(self.cache_path.resolve())
        with self._locks_guard:
            self._lock = self._locks.setdefault(key, threading.RLock())
        if not self.cache_path.exists():
            self._write({"rates": {}})

    def _read(self) -> dict[str, Any]:
        with self._lock:
            try:
                payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
                if not isinstance(payload, dict) or not isinstance(payload.get("rates", {}), dict):
                    raise ValueError("FX cache must contain a top-level rates object")
                return payload
            except FileNotFoundError:
                payload = {"rates": {}}
                self._write(payload)
                return payload
            except (json.JSONDecodeError, ValueError, OSError):
                # FX data is disposable cache data. Preserve a backup and recover automatically.
                try:
                    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                    backup = self.cache_path.with_name(f"{self.cache_path.name}.corrupt-{stamp}")
                    if self.cache_path.exists():
                        self.cache_path.replace(backup)
                except OSError:
                    pass
                payload = {"rates": {}}
                self._write(payload)
                return payload

    def _write(self, payload: dict[str, Any]) -> None:
        with self._lock:
            temp = self.cache_path.with_suffix(self.cache_path.suffix + ".tmp")
            try:
                temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
                temp.replace(self.cache_path)
            except OSError as exc:
                try:
                    temp.unlink(missing_ok=True)
                except OSError:
                    pass
                raise FxServiceError(f"Unable to save FX cache: {exc}") from exc

    @staticmethod
    def _pair(base: str, quote: str) -> tuple[str, str, str]:
        base = str(base or "").strip().upper()
        quote = str(quote or "").strip().upper()
        if len(base) != 3 or len(quote) != 3 or not base.isalpha() or not quote.isalpha():
            raise FxServiceError("Currencies must be three-letter codes.")
        return base, quote, f"{base}/{quote}"

    @staticmethod
    def _valid_cached(item: Any, base: str, quote: str) -> dict[str, Any] | None:
        if not isinstance(item, dict):
            return None
        try:
            rate = float(item.get("rate"))
        except (TypeError, ValueError):
            return None
        if not math.isfinite(rate) or rate <= 0:
            return None
        returned_base = str(item.get("base") or base).strip().upper()
        returned_quote = str(item.get("quote") or quote).strip().upper()
        if returned_base != base or returned_quote != quote:
            return None
        clean = dict(item)
        clean.update({"base": base, "quote": quote, "rate": rate})
        return clean

    def get_cached(self, base: str, quote: str) -> dict[str, Any] | None:
        base, quote, key = self._pair(base, quote)
        if base == quote:
            return {"base": base, "quote": quote, "rate": 1.0, "date": None, "source": "identity", "cached": True}

        rates = self._read().get("rates", {})
        direct = self._valid_cached(rates.get(key), base, quote)
        if direct:
            return direct

        reverse_key = f"{quote}/{base}"
        reverse = self._valid_cached(rates.get(reverse_key), quote, base)
        if reverse:
            reciprocal = dict(reverse)
            reciprocal.update({
                "base": base,
                "quote": quote,
                "rate": 1.0 / float(reverse["rate"]),
                "source": f"reciprocal of cached {reverse_key}",
                "derived": True,
            })
            return reciprocal
        return None

    def _is_fresh(self, cached: dict[str, Any]) -> bool:
        refreshed_at = cached.get("refreshed_at")
        if not refreshed_at:
            return False
        try:
            stamp = datetime.fromisoformat(str(refreshed_at).replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            age_hours = (datetime.now(timezone.utc) - stamp).total_seconds() / 3600
            return 0 <= age_hours <= self.max_age_hours
        except Exception:
            return False

    def get_rate(self, base: str, quote: str, *, refresh: bool = False) -> dict[str, Any]:
        base, quote, key = self._pair(base, quote)
        if base == quote:
            return {"base": base, "quote": quote, "rate": 1.0, "date": None, "source": "identity", "cached": True}

        cached = self.get_cached(base, quote)
        if cached and not refresh and self._is_fresh(cached):
            fresh = dict(cached)
            fresh["cached"] = True
            return fresh

        url = self.endpoint.format(base=base, quote=quote)
        try:
            response = requests.get(
                url,
                headers={"Accept": "application/json", "User-Agent": "CVStudio-SalaryComparison/1.4"},
                timeout=20,
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError("FX service returned an invalid JSON object")
            returned_base = str(data.get("base") or base).strip().upper()
            returned_quote = str(data.get("quote") or quote).strip().upper()
            if returned_base != base or returned_quote != quote:
                raise ValueError(f"FX service returned {returned_base}/{returned_quote}, expected {key}")
            rate = float(data["rate"])
            if not math.isfinite(rate) or rate <= 0:
                raise ValueError("non-positive or non-finite rate")
            result = {
                "base": base,
                "quote": quote,
                "rate": rate,
                "date": data.get("date"),
                "source": url,
                "cached": False,
                "refreshed_at": datetime.now(timezone.utc).isoformat(),
            }
            with self._lock:
                payload = self._read()
                payload.setdefault("rates", {})[key] = result
                self._write(payload)
            return result
        except Exception as exc:
            if cached:
                stale = dict(cached)
                stale["cached"] = True
                stale["stale"] = True
                stale["warning"] = str(exc)
                return stale
            raise FxServiceError(f"Unable to retrieve FX rate for {key}: {exc}") from exc
