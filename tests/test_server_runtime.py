"""Runtime server-selection coverage for the Waitress swap.

The HTTP server is chosen in ``app._run_cvstudio_server`` (Waitress when
available, Werkzeug's ``app.run`` as a fallback). None of this touches the sealed
route contract -- it lives entirely in the ``__main__`` serve path -- but it does
carry one correctness-critical value: ``channel_timeout`` must cover the
worst-case ``/parse`` hold, or long CV parses get their connection cut mid-flight
(the exact timeout failure class the parse pipeline was hardened against).

These tests pin: the derived timeout, that Waitress is chosen by default with
loopback-only binding, and that ``CVSTUDIO_SERVER=werkzeug`` forces the legacy
server. The app is imported the same way the other suites do (write a test
install receipt first so the boot-time receipt trap is satisfied).
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from owner_build_tools.build_protected import write_test_receipt


ROOT = Path(__file__).resolve().parents[1]

_TMP = tempfile.TemporaryDirectory(prefix="cvstudio-server-runtime-")
_PRIOR_DB = os.environ.get("CVSTUDIO_DB_PATH")
os.environ["CVSTUDIO_DB_PATH"] = str(Path(_TMP.name) / "state" / "cv_studio.sqlite3")
write_test_receipt(ROOT)
try:
    import app
finally:
    if _PRIOR_DB is None:
        os.environ.pop("CVSTUDIO_DB_PATH", None)
    else:
        os.environ["CVSTUDIO_DB_PATH"] = _PRIOR_DB


class ChannelTimeoutTests(unittest.TestCase):
    def test_channel_timeout_covers_worst_case_chained_parse(self):
        # Long-CV per-call ceiling is 300s; a single /parse can chain up to three
        # sequential DeepSeek calls, so the inactivity timeout must clear 900s.
        timeout = app._cvstudio_http_channel_timeout()
        self.assertGreaterEqual(timeout, 900)
        # Derived from the real parse budget (300 * 3 + 120 margin).
        self.assertEqual(timeout, 300 * 3 + 120)

    def test_channel_timeout_tracks_the_parse_budget_function(self):
        # If the per-call parse budget is raised, the channel timeout follows it,
        # so the two can never silently drift apart.
        with mock.patch.object(
            app, "_cv_parse_backend_timeout_seconds", return_value=600
        ):
            self.assertEqual(app._cvstudio_http_channel_timeout(), 600 * 3 + 120)


class ServerSelectionTests(unittest.TestCase):
    def setUp(self):
        self._prior = os.environ.get("CVSTUDIO_SERVER")

    def tearDown(self):
        if self._prior is None:
            os.environ.pop("CVSTUDIO_SERVER", None)
        else:
            os.environ["CVSTUDIO_SERVER"] = self._prior

    def test_default_prefers_waitress_bound_to_loopback(self):
        waitress = __import__("importlib").import_module("waitress")
        os.environ.pop("CVSTUDIO_SERVER", None)
        with mock.patch.object(waitress, "serve") as served, \
                mock.patch.object(app.app, "run") as legacy:
            app._run_cvstudio_server()
        legacy.assert_not_called()
        served.assert_called_once()
        args, kwargs = served.call_args
        self.assertIs(args[0], app.app)
        self.assertEqual(kwargs["host"], "127.0.0.1")  # never a public interface
        self.assertEqual(kwargs["port"], app._CVSTUDIO_PORT)
        self.assertEqual(kwargs["channel_timeout"], app._cvstudio_http_channel_timeout())
        self.assertGreaterEqual(kwargs["threads"], 8)

    def test_env_override_forces_legacy_server(self):
        waitress = __import__("importlib").import_module("waitress")
        os.environ["CVSTUDIO_SERVER"] = "werkzeug"
        with mock.patch.object(waitress, "serve") as served, \
                mock.patch.object(app.app, "run") as legacy:
            app._run_cvstudio_server()
        served.assert_not_called()
        legacy.assert_called_once()

    def test_falls_back_to_legacy_when_waitress_missing(self):
        # Simulate waitress being unavailable in the runtime: the import inside
        # the serve path fails, and the app must still start via app.run.
        os.environ.pop("CVSTUDIO_SERVER", None)
        real_import = __import__

        def no_waitress(name, *args, **kwargs):
            if name == "waitress":
                raise ImportError("simulated missing waitress")
            return real_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=no_waitress), \
                mock.patch.object(app.app, "run") as legacy:
            app._run_cvstudio_server()
        legacy.assert_called_once()


if __name__ == "__main__":
    unittest.main()
