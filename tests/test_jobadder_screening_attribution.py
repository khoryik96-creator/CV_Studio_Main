"""A JobAdder Screening Call is recorded under the connected token's user.

JobAdder attributes a Candidate Screening Call to whoever owns the OAuth token
that created it -- there is no author/onBehalfOf field on the write. So when
several consultants each run their own CV Studio, a note must never be filed
silently under the wrong person's name. These tests pin the two guarantees that
make attribution safe and visible:

  1. CV Studio resolves and exposes the connected JobAdder user's identity.
  2. Logging a Screening Call is refused when the connected account is not the
     consultant the browser expected.
"""

import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


_MODULE_TEMPORARY = None
if "app" in sys.modules:
    import app
else:
    _MODULE_TEMPORARY = tempfile.TemporaryDirectory(
        prefix="cvstudio-jobadder-attribution-"
    )
    _ORIGINAL_DATABASE_OVERRIDE = os.environ.get("CVSTUDIO_DB_PATH")
    _ORIGINAL_LOCAL_STATE = os.environ.get("LOCALAPPDATA")
    os.environ["CVSTUDIO_DB_PATH"] = str(
        Path(_MODULE_TEMPORARY.name) / "state" / "cv_studio.sqlite3"
    )
    os.environ["LOCALAPPDATA"] = str(Path(_MODULE_TEMPORARY.name) / "local-state")
    from owner_build_tools.build_protected import write_test_receipt

    write_test_receipt(Path(__file__).resolve().parents[1])
    try:
        import app
    finally:
        if _ORIGINAL_DATABASE_OVERRIDE is None:
            os.environ.pop("CVSTUDIO_DB_PATH", None)
        else:
            os.environ["CVSTUDIO_DB_PATH"] = _ORIGINAL_DATABASE_OVERRIDE
        if _ORIGINAL_LOCAL_STATE is None:
            os.environ.pop("LOCALAPPDATA", None)
        else:
            os.environ["LOCALAPPDATA"] = _ORIGINAL_LOCAL_STATE


class JobAdderIdentityResolutionTests(unittest.TestCase):
    def test_identity_parsed_from_users_current_shape(self):
        identity = app._ja_identity_from_payload(
            {
                "userId": 4321,
                "firstName": "Jane",
                "lastName": "Smith",
                "email": "jane@example.com",
            }
        )
        self.assertEqual(
            identity,
            {"user_id": "4321", "name": "Jane Smith", "email": "jane@example.com"},
        )

    def test_identity_ignores_empty_payload(self):
        self.assertIsNone(app._ja_identity_from_payload({}))
        self.assertIsNone(app._ja_identity_from_payload(None))

    def test_ensure_identity_populates_and_public_info_exposes_it(self):
        original = dict(app._ja_creds_store)
        original_attempt = app._ja_identity_last_attempt
        try:
            app._ja_creds_store.clear()
            app._ja_creds_store.update(
                {
                    "access_token": "tok",
                    "refresh_token": "ref",
                    "client_id": "cid",
                    "client_secret": "sec",
                    "expires_at": 9999999999,
                    "api_url": "https://api.jobadder.com/v2",
                    "cache_namespace": "n",
                }
            )
            app._ja_identity_last_attempt = 0.0
            payload = {
                "userId": 77,
                "firstName": "Jane",
                "lastName": "Smith",
                "email": "jane@example.com",
            }
            with mock.patch.object(
                app, "_ja_refresh_access_token", return_value="tok"
            ), mock.patch.object(
                app, "_ja_get_json", return_value=(200, payload)
            ) as get_json, mock.patch.object(app, "_ja_save_store"):
                app._ja_ensure_account_identity(force=True)
            # First identity endpoint tried is the documented users/current.
            self.assertEqual(get_json.call_args_list[0].args[0], "users/current")
            info = app._ja_public_info()
            self.assertEqual(info["account_user_name"], "Jane Smith")
            self.assertEqual(info["account_user_email"], "jane@example.com")
            self.assertEqual(info["account_user_id"], "77")
        finally:
            app._ja_creds_store.clear()
            app._ja_creds_store.update(original)
            app._ja_identity_last_attempt = original_attempt

    def _connected_store_without_identity(self):
        app._ja_creds_store.clear()
        app._ja_creds_store.update({
            "access_token": "tok", "refresh_token": "ref", "client_id": "cid",
            "client_secret": "sec", "expires_at": 9999999999,
            "api_url": "https://api.jobadder.com/v2", "cache_namespace": "n",
        })
        app._ja_identity_last_attempt = 0.0

    def test_identity_fetch_falls_through_to_alternate_on_http_error(self):
        import urllib.error
        original = dict(app._ja_creds_store)
        original_attempt = app._ja_identity_last_attempt
        try:
            self._connected_store_without_identity()
            payload = {"userId": 9, "firstName": "Amy", "lastName": "Lee", "email": "amy@x.io"}
            calls = []

            def fake_get(path, timeout=8):
                calls.append(path)
                if path == "users/current":
                    raise urllib.error.HTTPError(path, 404, "Not Found", {}, None)
                return (200, payload)

            with mock.patch.object(app, "_ja_refresh_access_token", return_value="tok"), \
                    mock.patch.object(app, "_ja_get_json", side_effect=fake_get), \
                    mock.patch.object(app, "_ja_save_store"):
                app._ja_ensure_account_identity(force=True)
            self.assertEqual(calls, ["users/current", "users/me"])
            self.assertEqual(app._ja_current_identity()["email"], "amy@x.io")
        finally:
            app._ja_creds_store.clear(); app._ja_creds_store.update(original)
            app._ja_identity_last_attempt = original_attempt

    def test_identity_fetch_stops_after_network_error_without_chaining(self):
        import urllib.error
        original = dict(app._ja_creds_store)
        original_attempt = app._ja_identity_last_attempt
        try:
            self._connected_store_without_identity()
            calls = []

            def fake_get(path, timeout=8):
                calls.append(path)
                raise urllib.error.URLError("timed out")

            with mock.patch.object(app, "_ja_refresh_access_token", return_value="tok"), \
                    mock.patch.object(app, "_ja_get_json", side_effect=fake_get), \
                    mock.patch.object(app, "_ja_save_store"):
                app._ja_ensure_account_identity(force=True)
            # A network timeout must not chain a second endpoint attempt.
            self.assertEqual(calls, ["users/current"])
            self.assertEqual(app._ja_current_identity()["email"], "")
        finally:
            app._ja_creds_store.clear(); app._ja_creds_store.update(original)
            app._ja_identity_last_attempt = original_attempt

    def test_disconnected_public_info_hides_identity(self):
        original = dict(app._ja_creds_store)
        try:
            app._ja_creds_store.clear()
            app._ja_creds_store.update(
                {"account_user_name": "Leftover", "account_user_email": "x@y.z"}
            )
            info = app._ja_public_info()
            self.assertFalse(info["connected"])
            self.assertEqual(info["account_user_name"], "")
            self.assertEqual(info["account_user_email"], "")
        finally:
            app._ja_creds_store.clear()
            app._ja_creds_store.update(original)


class JobAdderScreeningAttributionGuardTests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()
        self.client.set_cookie(
            app._AI_SPEND_SESSION_COOKIE, app._AI_SPEND_SESSION_TOKEN
        )
        self.original_store = dict(app._ja_creds_store)
        app._ja_creds_store.clear()
        app._ja_creds_store.update(
            {
                "access_token": "tok",
                "refresh_token": "ref",
                "client_id": "cid",
                "client_secret": "sec",
                "expires_at": 9999999999,
                "api_url": "https://api.jobadder.com/v2",
                "cache_namespace": "n",
                "account_user_id": "100",
                "account_user_name": "Jane Smith",
                "account_user_email": "jane@example.com",
            }
        )

    def tearDown(self):
        app._ja_creds_store.clear()
        app._ja_creds_store.update(self.original_store)

    def _post(self, body):
        # Identity is already cached, so the guard reads the store without a
        # network lookup; still stub the token refresh to stay offline.
        headers = {
            "X-CV-Studio-Request": "1",
            "X-CV-Studio-Request-ID": "attribution-test",
        }
        with mock.patch.object(app, "_ja_refresh_access_token", return_value="tok"):
            return self.client.post(
                "/jobadder/onenote_log_screening", json=body, headers=headers
            )

    def test_mismatched_consultant_is_refused_before_writing(self):
        response = self._post(
            {
                "candidate_id": "555",
                "note_text": "Great candidate",
                "expected_user_email": "john@example.com",
            }
        )
        self.assertEqual(response.status_code, 409)
        payload = response.get_json()
        self.assertEqual(payload["code"], "JOBADDER_ACCOUNT_MISMATCH")
        self.assertEqual(payload["logged_as"]["email"], "jane@example.com")
        self.assertIn("Jane Smith", payload["why"])

    def test_matching_consultant_passes_the_attribution_guard(self):
        # A matching identity must NOT trip the mismatch guard. With no
        # candidate_id supplied the request then fails validation instead --
        # proving the guard let it through rather than blocking on identity.
        response = self._post(
            {"expected_user_email": "jane@example.com"}
        )
        self.assertNotEqual(response.status_code, 409)
        self.assertEqual(response.status_code, 400)
        self.assertIn("candidate_id", response.get_json()["error"])

    def test_missing_expectation_does_not_block_logging(self):
        # Back-compatibility: a browser that sends no expectation is not blocked
        # by the guard (it still fails later on the missing candidate_id).
        response = self._post({})
        self.assertNotEqual(response.status_code, 409)
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
