"""Non-secret AI review preference uses existing schema-10 durable settings."""
from pathlib import Path
import tempfile

from cvstudio_storage import BrowserSettingsRepository, CVStudioStorage, SCHEMA_VERSION

KEY = "cvstudio_formatting_review_v1"


def test_review_choice_survives_restart_without_changing_schema():
    with tempfile.TemporaryDirectory(prefix="cvstudio-review-setting-") as directory:
        path = Path(directory) / "state.sqlite3"
        store = CVStudioStorage(path)
        store.initialize()
        settings = BrowserSettingsRepository(store)
        assert KEY not in settings.load()
        assert settings.upsert({KEY: "true"}) == 1
        restarted = CVStudioStorage(path)
        restarted.initialize()
        assert BrowserSettingsRepository(restarted).load()[KEY] == "true"
        assert BrowserSettingsRepository(restarted).upsert({KEY: "false"}) == 1
        assert settings.load()[KEY] == "false"
        with restarted.connection() as connection:
            assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION == 10


def test_deleted_review_choice_cannot_be_resurrected_by_an_old_browser_mirror():
    with tempfile.TemporaryDirectory(prefix="cvstudio-review-setting-") as directory:
        store = CVStudioStorage(Path(directory) / "state.sqlite3")
        store.initialize()
        settings = BrowserSettingsRepository(store)
        assert settings.import_legacy({KEY: "true"}) == 1
        assert settings.delete([KEY]) == 1
        assert settings.import_legacy({KEY: "true"}, fingerprint="stale-second-browser") == 0
        assert KEY not in settings.load()
