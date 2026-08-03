from __future__ import annotations

import shutil
from pathlib import Path

DATA_FILES = ("country_currency.json", "tax_rules.json", "fx_cache.json")


def ensure_data_dir(target: Path) -> Path:
    """Seed a persistent data directory without overwriting existing user data."""
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    defaults = Path(__file__).resolve().parent / "data"
    for filename in DATA_FILES:
        destination = target / filename
        if not destination.exists():
            shutil.copy2(defaults / filename, destination)
    return target
