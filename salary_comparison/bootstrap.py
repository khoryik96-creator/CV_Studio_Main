from __future__ import annotations

import json
import shutil
from copy import deepcopy
from pathlib import Path

DATA_FILES = ("country_currency.json", "tax_rules.json", "fx_cache.json")

_ADDITIVE_RULE_FIELDS = (
    "personal_reliefs_allowed",
)


def _rule_identity(rule):
    if not isinstance(rule, dict):
        return None
    try:
        year = int(rule.get("tax_year"))
    except (TypeError, ValueError):
        return None
    country = str(rule.get("country") or "").strip().casefold()
    residency = str(rule.get("residency") or "").strip().casefold()
    return (country, year, residency) if country and residency else None


def _merge_packaged_tax_rules(destination: Path, packaged: Path) -> None:
    """Add newly packaged rules without replacing user-approved tax values.

    Persistent salary data predates some built-in rule identities. Simply
    shipping a newer ``tax_rules.json`` does not update an existing install,
    because the normal bootstrap intentionally never overwrites user data.
    Merge only missing country/year/residency rules and newly introduced
    additive UI fields. Existing brackets, rates, notes, sources and any
    user-edited values remain authoritative.
    """
    try:
        current = json.loads(destination.read_text(encoding="utf-8"))
        defaults = json.loads(packaged.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return
    if not (
        isinstance(current, dict)
        and isinstance(current.get("rules"), list)
        and isinstance(defaults, dict)
        and isinstance(defaults.get("rules"), list)
    ):
        return

    current_by_identity = {}
    for rule in current["rules"]:
        identity = _rule_identity(rule)
        if identity is None:
            # Preserve an unrecognized user file byte-for-byte. The repository
            # will surface its normal validation error instead of bootstrap
            # attempting a partial repair that could hide custom data.
            return
        current_by_identity[identity] = rule
    changed = False
    for packaged_rule in defaults["rules"]:
        identity = _rule_identity(packaged_rule)
        if identity is None:
            continue
        existing = current_by_identity.get(identity)
        if existing is None:
            added = deepcopy(packaged_rule)
            current["rules"].append(added)
            current_by_identity[identity] = added
            changed = True
            continue
        packaged_profiles = packaged_rule.get("contribution_profiles")
        existing_profiles = existing.get("contribution_profiles")
        packaged_default = str(
            packaged_rule.get("default_contribution_profile") or ""
        ).strip()
        existing_default = str(
            existing.get("default_contribution_profile") or ""
        ).strip()
        if (
            isinstance(packaged_profiles, list)
            and packaged_profiles
            and not existing_profiles
            and (not existing_default or existing_default == packaged_default)
        ):
            # Older normalized/AI-published rules may contain an explicit empty
            # list. Treat that as the pre-profile shape for a matching packaged
            # identity. The original migration added the packaged default name
            # without its list, creating a rule the repository could not load.
            existing["contribution_profiles"] = deepcopy(packaged_profiles)
            existing_profiles = existing["contribution_profiles"]
            changed = True

        profile_ids = {
            str(profile.get("id") or "").strip()
            for profile in (existing_profiles or [])
            if isinstance(profile, dict)
        }
        if (
            packaged_default
            and packaged_default in profile_ids
            and not existing_default
        ):
            existing["default_contribution_profile"] = packaged_default
            existing_default = packaged_default
            changed = True
        for field in _ADDITIVE_RULE_FIELDS:
            if field not in existing and field in packaged_rule:
                existing[field] = deepcopy(packaged_rule[field])
                changed = True

    if not changed:
        return
    temp = destination.with_suffix(destination.suffix + ".merge.tmp")
    try:
        temp.write_text(
            json.dumps(current, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temp.replace(destination)
    except OSError:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass


def ensure_data_dir(target: Path) -> Path:
    """Seed persistent data and add new built-ins without overwriting user data."""
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    defaults = Path(__file__).resolve().parent / "data"
    for filename in DATA_FILES:
        destination = target / filename
        if not destination.exists():
            shutil.copy2(defaults / filename, destination)
        elif filename == "tax_rules.json":
            _merge_packaged_tax_rules(destination, defaults / filename)
    return target
