import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import urllib.error
from unittest import mock


_MODULE_TEMPORARY = None
if "app" in sys.modules:
    import app
else:
    _MODULE_TEMPORARY = tempfile.TemporaryDirectory(
        prefix="cvstudio-jobadder-account-settings-"
    )
    _ORIGINAL_DATABASE_OVERRIDE = os.environ.get("CVSTUDIO_DB_PATH")
    _ORIGINAL_LOCAL_STATE = os.environ.get("LOCALAPPDATA")
    os.environ["CVSTUDIO_DB_PATH"] = str(
        Path(_MODULE_TEMPORARY.name) / "state" / "cv_studio.sqlite3"
    )
    os.environ["LOCALAPPDATA"] = str(
        Path(_MODULE_TEMPORARY.name) / "local-state"
    )
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


_V246241_ROUTE_CONTRACT_SHA256 = (
    "3d415072b4fa555f17dfc9d81c2d21dc6f6bff73af13f519c90f11085113a9ea"
)


class JobAdderAccountSettingsSignOutTests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()
        self.original_store = dict(app._ja_creds_store)
        self.original_sessions = {
            key: dict(value) for key, value in app._ja_oauth_sessions.items()
        }
        self.original_write_count = getattr(app, "_ja_critical_writes_active", 0)
        self.original_transition = getattr(
            app, "_ja_account_transition_in_progress", False
        )
        self.original_ppc_detail_cache = dict(app._ppc_detail_cache)
        app._ja_creds_store.clear()
        app._ja_oauth_sessions.clear()
        app._spider_resume_text_cache_clear()
        app._ppc_detail_cache.clear()
        if hasattr(app, "_ja_critical_writes_active"):
            app._ja_critical_writes_active = 0
        if hasattr(app, "_ja_account_transition_in_progress"):
            app._ja_account_transition_in_progress = False

    def tearDown(self):
        app._ja_creds_store.clear()
        app._ja_creds_store.update(self.original_store)
        app._ja_oauth_sessions.clear()
        app._ja_oauth_sessions.update(self.original_sessions)
        app._spider_resume_text_cache_clear()
        app._ppc_detail_cache.clear()
        app._ppc_detail_cache.update(self.original_ppc_detail_cache)
        if hasattr(app, "_ja_critical_writes_active"):
            app._ja_critical_writes_active = self.original_write_count
        if hasattr(app, "_ja_account_transition_in_progress"):
            app._ja_account_transition_in_progress = self.original_transition

    @staticmethod
    def _headers(request_id):
        return {
            "X-CV-Studio-Request": "1",
            "X-CV-Studio-Request-ID": request_id,
        }

    @staticmethod
    def _route_contract(exclude=()):
        excluded = set(exclude)
        rows = sorted(
            (
                rule.rule,
                rule.endpoint,
                sorted(set(rule.methods) - {"HEAD", "OPTIONS"}),
            )
            for rule in app.app.url_map.iter_rules()
            if rule.rule not in excluded
        )
        raw = json.dumps(rows, separators=(",", ":"))
        return len(rows), hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def test_route_inventory_adds_only_sign_out_to_exact_v246241_contract(self):
        routes = {rule.rule: rule for rule in app.app.url_map.iter_rules()}
        self.assertEqual(len(routes), 116)
        self.assertIn("/jobadder/sign_out", routes)
        sign_out = routes["/jobadder/sign_out"]
        self.assertEqual(sign_out.endpoint, "jobadder_sign_out")
        self.assertEqual(
            set(sign_out.methods) - {"HEAD", "OPTIONS"},
            {"POST"},
        )
        # The Salary Comparison feature module adds its own namespaced routes;
        # exclude them (and sign-out) so this check stays focused on proving the
        # sign-out delta against the exact v24.6.241 base contract.
        _salary_routes = {
            rule.rule
            for rule in app.app.url_map.iter_rules()
            if rule.rule.startswith("/salary-comparison")
        }
        self.assertEqual(
            self._route_contract(exclude={"/jobadder/sign_out"} | _salary_routes),
            (107, _V246241_ROUTE_CONTRACT_SHA256),
        )

    def test_sign_out_is_csrf_protected_post(self):
        response = self.client.get("/jobadder/sign_out")
        self.assertEqual(response.status_code, 405)

        response = self.client.post("/jobadder/sign_out", json={})
        self.assertEqual(response.status_code, 403)
        payload = response.get_json()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["code"], "UNSAFE_LOCAL_REQUEST")
        self.assertTrue(payload["request_id"])

    def test_sign_out_persists_only_registration_and_clears_account_state(self):
        app._ja_creds_store.update(
            {
                "client_id": "fixture-client-id",
                "client_secret": "fixture-client-secret",
                "access_token": "fixture-access-token",
                "refresh_token": "fixture-refresh-token",
                "expires_at": 1234567890,
                "api_url": "https://api.eu.jobadder.com/v2",
                "cache_namespace": "fixture-old-account-namespace",
                "_needs_reconnect": True,
                "_storage": "fixture-protected-store",
                "account_id": "fixture-account-state",
            }
        )
        app._ja_oauth_sessions["fixture-session"] = {
            "state": "fixture-oauth-state",
            "status": "pending",
        }
        app._SPIDER_RESUME_TEXT_CACHE["fixture-resume"] = {
            "text": "fixture tenant resume"
        }
        app._SPIDER_PREVIEW_PAYLOAD_CACHE["fixture-preview"] = {
            "payload": {"fixture": True}
        }
        app._SPIDER_PREVIEW_PAYLOAD_CACHE_BYTES = 123
        app._ppc_detail_cache[
            ("fixture-old-account-namespace", "fixture-placement", "fixture-updated")
        ] = {"candidate_name": "Fixture Tenant Candidate"}
        saved = []

        def secure_save(name, record):
            saved.append((name, dict(record)))
            return "fixture-protected-store"

        with mock.patch.object(
            app, "_cv_secure_save", side_effect=secure_save
        ), mock.patch.object(
            app, "_spider_preview_cancel_persistent_work", return_value=7
        ) as cancelled:
            response = self.client.post(
                "/jobadder/sign_out",
                json={},
                headers=self._headers("jobadder-sign-out-success"),
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {
                "ok": True,
                "connected": False,
                "client_id": "fixture-client-id",
                "client_secret_configured": True,
            },
        )
        self.assertEqual(
            saved,
            [
                (
                    "jobadder",
                    {
                        "client_id": "fixture-client-id",
                        "client_secret": "fixture-client-secret",
                    },
                )
            ],
        )
        self.assertEqual(
            app._ja_creds_store,
            {
                "client_id": "fixture-client-id",
                "client_secret": "fixture-client-secret",
                "_storage": "fixture-protected-store",
            },
        )
        self.assertEqual(app._ja_oauth_sessions, {})
        self.assertEqual(len(app._SPIDER_RESUME_TEXT_CACHE), 0)
        self.assertEqual(len(app._SPIDER_PREVIEW_PAYLOAD_CACHE), 0)
        self.assertEqual(app._SPIDER_PREVIEW_PAYLOAD_CACHE_BYTES, 0)
        self.assertEqual(app._ppc_detail_cache, {})
        cancelled.assert_called_once_with()
        payload_text = response.get_data(as_text=True)
        for forbidden in (
            "fixture-client-secret",
            "fixture-access-token",
            "fixture-refresh-token",
            "fixture-oauth-state",
            "fixture-protected-store",
        ):
            self.assertNotIn(forbidden, payload_text)

        info = self.client.get(
            "/jobadder/api_info",
            headers={"X-CV-Studio-Request-ID": "jobadder-after-sign-out"},
        )
        self.assertEqual(info.status_code, 200)
        info_payload = info.get_json()
        self.assertFalse(info_payload["connected"])
        self.assertEqual(info_payload["client_id"], "fixture-client-id")
        self.assertTrue(info_payload["client_secret_configured"])
        for forbidden_key in (
            "client_secret",
            "access_token",
            "refresh_token",
            "oauth_state",
        ):
            self.assertNotIn(forbidden_key, info_payload)

    def test_late_oauth_callback_cannot_recreate_session_after_sign_out(self):
        app._ja_creds_store.update(
            {
                "client_id": "fixture-client-id",
                "client_secret": "fixture-client-secret",
            }
        )
        app._ja_oauth_sessions["fixture-late-session"] = {
            "state": "fixture-late-state",
            "client_id": "fixture-client-id",
            "client_secret": "fixture-client-secret",
            "created_at": app.time.time(),
            "expires_at": app.time.time() + 600,
            "status": "pending",
        }
        exchange_started = threading.Event()
        release_exchange = threading.Event()
        callback_result = {}

        def exchange_token(_params):
            exchange_started.set()
            self.assertTrue(release_exchange.wait(5))
            return {
                "access_token": "fixture-late-access",
                "refresh_token": "fixture-late-refresh",
                "api": "https://api.eu.jobadder.com/v2",
                "expires_in": 3300,
            }

        def run_callback():
            with app.app.test_client() as callback_client:
                callback_result["response"] = callback_client.get(
                    "/jobadder/callback"
                    "?code=fixture-late-code&state=fixture-late-state"
                )

        with mock.patch.object(
            app, "_ja_exchange_token", side_effect=exchange_token
        ), mock.patch.object(
            app, "_cv_secure_save", return_value="fixture-protected-store"
        ), mock.patch.object(
            app, "_spider_preview_cancel_persistent_work", return_value=17
        ):
            callback_thread = threading.Thread(target=run_callback)
            callback_thread.start()
            self.assertTrue(exchange_started.wait(5))
            signed_out = self.client.post(
                "/jobadder/sign_out",
                json={},
                headers=self._headers("jobadder-late-callback-sign-out"),
            )
            self.assertEqual(signed_out.status_code, 200)
            release_exchange.set()
            callback_thread.join(5)

        self.assertFalse(callback_thread.is_alive())
        self.assertIn(callback_result["response"].status_code, {400, 409})
        self.assertEqual(app._ja_oauth_sessions, {})
        self.assertNotIn("access_token", app._ja_creds_store)
        self.assertNotIn("refresh_token", app._ja_creds_store)
        poll = self.client.post(
            "/jobadder/poll_token",
            json={"login_session_id": "fixture-late-session"},
            headers=self._headers("jobadder-late-callback-poll"),
        )
        self.assertEqual(poll.status_code, 404)

    def test_ppc_detail_cache_is_account_namespaced(self):
        app._ja_creds_store.update(
            {
                "client_id": "fixture-client-id",
                "client_secret": "fixture-client-secret",
                "access_token": "fixture-access-token",
                "api_url": "https://api.eu.jobadder.com/v2",
                "cache_namespace": "fixture-account-a",
            }
        )

        def collection(_token, placement_type, _params, _max_records):
            rows = (
                [
                    {
                        "placementId": "fixture-placement",
                        "type": "Permanent",
                        "startDate": "2026-01-01",
                        "updatedAt": "2026-01-02T00:00:00Z",
                    }
                ]
                if placement_type == "Permanent"
                else []
            )
            return rows, {
                "type": placement_type,
                "expected": len(rows),
                "observed_total": len(rows),
                "returned": len(rows),
                "pages": 1,
                "complete": True,
                "truncated": False,
                "repeated_page": False,
                "empty_before_total": False,
            }

        detail_calls = []

        def detail(_token, path, **_kwargs):
            self.assertEqual(path, "placements/fixture-placement")
            namespace = app._ja_creds_store["cache_namespace"]
            detail_calls.append(namespace)
            suffix = "A" if namespace == "fixture-account-a" else "B"
            return {
                "placementId": "fixture-placement",
                "type": "Permanent",
                "startDate": "2026-01-01",
                "updatedAt": "2026-01-02T00:00:00Z",
                "candidate": {
                    "candidateId": "fixture-candidate-" + suffix.lower(),
                    "firstName": "Tenant",
                    "lastName": suffix,
                },
            }

        with mock.patch.object(
            app, "_ppc_fetch_type_collection", side_effect=collection
        ), mock.patch.object(app, "_ppc_get_json", side_effect=detail):
            first = self.client.post(
                "/jobadder/ppc/placements",
                json={"approved_only": False},
                headers=self._headers("jobadder-ppc-account-a"),
            )
            self.assertEqual(first.status_code, 200)
            self.assertEqual(first.get_json()["items"][0]["candidate_name"], "Tenant A")

            app._ja_creds_store["cache_namespace"] = "fixture-account-b"
            second = self.client.post(
                "/jobadder/ppc/placements",
                json={"approved_only": False},
                headers=self._headers("jobadder-ppc-account-b"),
            )
            self.assertEqual(second.status_code, 200)
            self.assertEqual(
                second.get_json()["items"][0]["candidate_name"], "Tenant B"
            )

        self.assertEqual(
            detail_calls,
            ["fixture-account-a", "fixture-account-b"],
        )

    def test_sign_out_vault_failure_is_visible_and_rolls_back_credentials(self):
        original = {
            "client_id": "fixture-client-id",
            "client_secret": "fixture-client-secret",
            "access_token": "fixture-access-token",
            "refresh_token": "fixture-refresh-token",
            "expires_at": 123,
            "api_url": "https://api.jobadder.com/v2",
            "cache_namespace": "fixture-namespace",
            "_storage": "fixture-protected-store",
        }
        app._ja_creds_store.update(original)
        app._ja_oauth_sessions["fixture-session"] = {
            "state": "fixture-state",
            "status": "pending",
        }
        app._SPIDER_RESUME_TEXT_CACHE["fixture-cache"] = {"text": "fixture"}

        with mock.patch.object(
            app, "_cv_secure_save", side_effect=OSError("fixture vault unavailable")
        ), mock.patch.object(
            app, "_spider_preview_cancel_persistent_work", return_value=9
        ):
            response = self.client.post(
                "/jobadder/sign_out",
                json={},
                headers=self._headers("jobadder-sign-out-vault-failure"),
            )

        self.assertEqual(response.status_code, 500)
        payload = response.get_json()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["request_id"], "jobadder-sign-out-vault-failure")
        self.assertEqual(app._ja_creds_store, original)
        self.assertIn("fixture-session", app._ja_oauth_sessions)
        self.assertIn("fixture-cache", app._SPIDER_RESUME_TEXT_CACHE)

    def test_active_critical_write_returns_conflict_without_signing_out(self):
        app._ja_creds_store.update(
            {
                "client_id": "fixture-client-id",
                "client_secret": "fixture-client-secret",
                "access_token": "fixture-access-token",
            }
        )
        app._ja_critical_writes_active = 1
        with mock.patch.object(app, "_cv_secure_save") as secure_save, mock.patch.object(
            app, "_spider_preview_cancel_persistent_work"
        ) as cancelled:
            response = self.client.post(
                "/jobadder/sign_out",
                json={},
                headers=self._headers("jobadder-sign-out-write-conflict"),
            )
        self.assertEqual(response.status_code, 409)
        payload = response.get_json()
        self.assertEqual(payload["code"], "JOBADDER_WRITE_IN_PROGRESS")
        self.assertTrue(payload["retryable"])
        self.assertEqual(
            app._ja_creds_store["access_token"], "fixture-access-token"
        )
        secure_save.assert_not_called()
        cancelled.assert_not_called()

        app._ja_critical_writes_active = 0
        app._ja_account_transition_in_progress = True
        with mock.patch.object(
            app._JOBADDER_CLIENT, "request_json"
        ) as external_write:
            blocked_write = self.client.post(
                "/jobadder/create_candidate",
                json={"firstName": "Fixture"},
                headers=self._headers("jobadder-write-transition-conflict"),
            )
        self.assertEqual(blocked_write.status_code, 409)
        self.assertEqual(
            blocked_write.get_json()["code"], "JOBADDER_ACCOUNT_TRANSITION"
        )
        external_write.assert_not_called()

        blocked_login = self.client.post(
            "/jobadder/store_creds",
            json={
                "client_id": "fixture-client-id",
                "client_secret": "fixture-client-secret",
            },
            headers=self._headers("jobadder-login-transition-conflict"),
        )
        self.assertEqual(blocked_login.status_code, 409)
        self.assertEqual(
            blocked_login.get_json()["code"], "JOBADDER_ACCOUNT_TRANSITION"
        )
        self.assertEqual(app._ja_oauth_sessions, {})

        blocked_restore = self.client.post(
            "/jobadder/restore_token",
            json={
                "access_token": "fixture-late-access",
                "refresh_token": "fixture-late-refresh",
            },
            headers=self._headers("jobadder-restore-transition-conflict"),
        )
        self.assertEqual(blocked_restore.status_code, 409)
        self.assertEqual(
            blocked_restore.get_json()["code"], "JOBADDER_ACCOUNT_TRANSITION"
        )
        self.assertNotEqual(
            app._ja_creds_store.get("access_token"), "fixture-late-access"
        )

    def test_saved_registration_reuse_change_rejection_and_oauth_state_binding(self):
        app._ja_creds_store.update(
            {
                "client_id": "fixture-client-id",
                "client_secret": "fixture-client-secret",
            }
        )
        response = self.client.post(
            "/jobadder/store_creds",
            json={"client_id": "fixture-client-id", "client_secret": ""},
            headers=self._headers("jobadder-reconnect-saved-secret"),
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["login_session_id"])
        self.assertTrue(payload["state"])
        self.assertNotIn("client_secret", payload)
        session = app._ja_oauth_sessions[payload["login_session_id"]]
        self.assertEqual(session["client_id"], "fixture-client-id")
        self.assertEqual(session["client_secret"], "fixture-client-secret")

        changed = self.client.post(
            "/jobadder/store_creds",
            json={"client_id": "fixture-other-client", "client_secret": ""},
            headers=self._headers("jobadder-change-needs-secret"),
        )
        self.assertEqual(changed.status_code, 400)
        self.assertIn("saved secret", changed.get_json()["error"].lower())

        with mock.patch.object(app, "_ja_exchange_token") as exchange:
            invalid_callback = self.client.get(
                "/jobadder/callback?code=fixture-code&state=wrong-state"
            )
        self.assertEqual(invalid_callback.status_code, 400)
        exchange.assert_not_called()

    def test_save_settings_uses_protected_workflow_and_requires_new_pair(self):
        saved = []

        def secure_save(name, record):
            saved.append((name, dict(record)))
            return "fixture-protected-store"

        with mock.patch.object(
            app, "_cv_secure_save", side_effect=secure_save
        ), mock.patch.object(
            app, "_spider_preview_cancel_persistent_work", return_value=11
        ):
            response = self.client.post(
                "/jobadder/store_creds",
                json={
                    "client_id": "fixture-client-id",
                    "client_secret": "fixture-client-secret",
                    "save_only": True,
                },
                headers=self._headers("jobadder-save-settings"),
            )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["connected"])
        self.assertEqual(payload["client_id"], "fixture-client-id")
        self.assertTrue(payload["client_secret_configured"])
        self.assertEqual(
            saved[-1][1],
            {
                "client_id": "fixture-client-id",
                "client_secret": "fixture-client-secret",
            },
        )

        saved.clear()
        with mock.patch.object(app, "_cv_secure_save", side_effect=secure_save):
            reused = self.client.post(
                "/jobadder/store_creds",
                json={
                    "client_id": "fixture-client-id",
                    "client_secret": "",
                    "save_only": True,
                },
                headers=self._headers("jobadder-save-settings-reuse"),
            )
        self.assertEqual(reused.status_code, 200)
        self.assertTrue(reused.get_json()["client_secret_configured"])
        self.assertEqual(saved[-1][1]["client_secret"], "fixture-client-secret")

        rejected = self.client.post(
            "/jobadder/store_creds",
            json={
                "client_id": "fixture-new-client",
                "client_secret": "",
                "save_only": True,
            },
            headers=self._headers("jobadder-save-settings-new-id"),
        )
        self.assertEqual(rejected.status_code, 400)

    def test_new_connection_gets_fresh_namespace_after_sign_out(self):
        app._ja_creds_store.update(
            {
                "client_id": "fixture-client-id",
                "client_secret": "fixture-client-secret",
                "access_token": "fixture-old-access",
                "refresh_token": "fixture-old-refresh",
                "api_url": "https://api.eu.jobadder.com/v2",
                "expires_at": 123,
                "cache_namespace": "fixture-old-namespace",
            }
        )
        app._SPIDER_RESUME_TEXT_CACHE["fixture-old-cache"] = {"text": "fixture"}
        with mock.patch.object(
            app, "_cv_secure_save", return_value="fixture-protected-store"
        ), mock.patch.object(
            app, "_spider_preview_cancel_persistent_work", return_value=13
        ):
            signed_out = self.client.post(
                "/jobadder/sign_out",
                json={},
                headers=self._headers("jobadder-namespace-sign-out"),
            )
            self.assertEqual(signed_out.status_code, 200)
            app._ja_apply_token(
                {
                    "access_token": "fixture-new-access",
                    "refresh_token": "fixture-new-refresh",
                    "api": "https://api.us.jobadder.com/v2",
                    "expires_in": 3300,
                },
                "fixture-client-id",
                "fixture-client-secret",
                clear_spider_cache=True,
            )
        self.assertNotEqual(
            app._ja_creds_store["cache_namespace"], "fixture-old-namespace"
        )
        new_public_namespace = app._ja_public_info()["account_cache_namespace"]
        app._ja_creds_store["cache_namespace"] = "fixture-other-namespace"
        other_public_namespace = app._ja_public_info()["account_cache_namespace"]
        self.assertNotEqual(new_public_namespace, other_public_namespace)
        self.assertNotEqual(
            other_public_namespace,
            app._ja_creds_store["cache_namespace"],
        )
        self.assertEqual(len(app._SPIDER_RESUME_TEXT_CACHE), 0)

    def test_malformed_oauth_expiry_never_escapes_as_http_500(self):
        malformed_values = (
            "3300abc",
            {"seconds": 3300},
            [3300],
            float("nan"),
            float("inf"),
            10 ** 400,
        )
        for value in malformed_values:
            with self.subTest(expires_in=repr(value)), mock.patch.object(
                app, "_cv_secure_save", return_value="fixture-protected-store"
            ):
                started = int(app.time.time())
                app._ja_apply_token({
                    "access_token": "fixture-access",
                    "refresh_token": "fixture-refresh",
                    "expires_in": value,
                })
                self.assertGreaterEqual(
                    app._ja_creds_store["expires_at"], started + 3299
                )
                self.assertLessEqual(
                    app._ja_creds_store["expires_at"], started + 3301
                )

        app._ja_creds_store.clear()
        app._ja_creds_store.update({
            "access_token": "fixture-old-access",
            "refresh_token": "fixture-refresh",
            "client_id": "fixture-client-id",
            "client_secret": "fixture-client-secret",
            "expires_at": 0,
        })
        refreshed = {
            "access_token": "fixture-new-access",
            "refresh_token": "fixture-new-refresh",
            "expires_in": "3300abc",
        }
        with mock.patch.object(
            app, "_ja_exchange_token", return_value=refreshed
        ), mock.patch.object(
            app, "_cv_secure_save", return_value="fixture-protected-store"
        ):
            self.assertEqual(
                app._ja_refresh_access_token(force=True),
                "fixture-new-access",
            )
        self.assertFalse(app._ja_creds_store.get("_needs_reconnect"))

        session_id = "fixture-malformed-expiry-session"
        app._ja_oauth_sessions[session_id] = {
            "status": "complete",
            "token": dict(refreshed, expires_in={"seconds": 3300}),
            "activated": False,
            "client_id": "fixture-client-id",
            "client_secret": "fixture-client-secret",
            "expires_at": app.time.time() + 300,
        }
        with mock.patch.object(
            app, "_cv_secure_save", return_value="fixture-protected-store"
        ), mock.patch.object(
            app, "_spider_preview_cancel_persistent_work", return_value=0
        ):
            response = self.client.post(
                "/jobadder/poll_token",
                json={"login_session_id": session_id},
                headers=self._headers("jobadder-malformed-expiry"),
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "complete")
        self.assertEqual(
            app._ja_creds_store["access_token"], "fixture-new-access"
        )

    def test_transient_refresh_failure_preserves_protected_connection(self):
        app._ja_creds_store.clear()
        app._ja_creds_store.update({
            "access_token": "fixture-still-protected-access",
            "refresh_token": "fixture-refresh",
            "client_id": "fixture-client-id",
            "client_secret": "fixture-client-secret",
            "expires_at": 0,
        })
        transient = app.ExternalServiceError(
            "jobadder",
            "JobAdder token service is temporarily unavailable",
            status=503,
            retryable=True,
            action="retry",
        )
        with mock.patch.object(app, "_ja_exchange_token", side_effect=transient):
            with self.assertRaises(app.ExternalServiceError):
                app._ja_refresh_access_token(force=True)
        self.assertEqual(
            app._ja_creds_store["access_token"],
            "fixture-still-protected-access",
        )
        self.assertFalse(app._ja_creds_store.get("_needs_reconnect"))

    def test_confirmed_refresh_rejection_requires_reconnect(self):
        app._ja_creds_store.clear()
        app._ja_creds_store.update({
            "access_token": "fixture-rejected-access",
            "refresh_token": "fixture-rejected-refresh",
            "client_id": "fixture-client-id",
            "client_secret": "fixture-client-secret",
            "expires_at": 0,
        })
        rejected = urllib.error.HTTPError(
            "https://id.jobadder.com/connect/token",
            400,
            "invalid_grant",
            {},
            io.BytesIO(b'{"error":"invalid_grant"}'),
        )
        with mock.patch.object(app, "_ja_exchange_token", side_effect=rejected), mock.patch.object(
            app, "_cv_secure_save", return_value="fixture-protected-store"
        ):
            self.assertEqual(app._ja_refresh_access_token(force=True), "")
        self.assertEqual(app._ja_creds_store.get("access_token"), "")
        self.assertTrue(app._ja_creds_store.get("_needs_reconnect"))

    def test_browser_refresh_route_is_expiry_aware_not_forced(self):
        app._ja_creds_store.clear()
        app._ja_creds_store.update({
            "access_token": "fixture-valid-access",
            "expires_at": int(app.time.time()) + 3000,
        })
        forces = []

        def refresh(force=False):
            forces.append(force)
            return "fixture-valid-access"

        with mock.patch.object(app, "_ja_refresh_access_token", side_effect=refresh):
            response = self.client.post(
                "/jobadder/refresh_token",
                json={},
                headers=self._headers("jobadder-expiry-aware-refresh"),
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(forces, [False])
        self.assertTrue(response.get_json()["connected"])

    def test_jobadder_client_does_not_mark_reconnect_on_transient_refresh(self):
        reconnects = []
        calls = []
        transient = app.ExternalServiceError(
            "jobadder",
            "temporary token transport failure",
            status=503,
            retryable=True,
            action="retry",
        )

        def token_provider(force=False):
            if force:
                raise transient
            return "fixture-expired-access"

        class Transport:
            def request(self, *args, **kwargs):
                calls.append(kwargs.get("headers", {}).get("Authorization"))
                raise app.ExternalServiceHTTPError(
                    "jobadder", "https://api.jobadder.com/v2/candidates", 401,
                    "Unauthorized", {}, b"rejected"
                )

        client = app.JobAdderClient(
            api_base_provider=lambda: "https://api.jobadder.com/v2",
            token_provider=token_provider,
            reconnect_handler=lambda: reconnects.append(True),
            transport=Transport(),
        )
        with self.assertRaises(app.ExternalServiceError):
            client.request_raw("candidates", method="GET")
        self.assertEqual(calls, ["Bearer fixture-expired-access"])
        self.assertEqual(reconnects, [])

    def test_disconnect_and_forget_response_and_state_remain_compatible(self):
        app._ja_creds_store.update(
            {
                "client_id": "fixture-client-id",
                "client_secret": "fixture-client-secret",
                "access_token": "fixture-access-token",
            }
        )
        app._ja_oauth_sessions["fixture-session"] = {"status": "pending"}
        with mock.patch.object(app, "_cv_secure_delete") as secure_delete:
            response = self.client.post(
                "/jobadder/disconnect",
                json={},
                headers=self._headers("jobadder-disconnect-compatibility"),
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"ok": True, "connected": False})
        self.assertEqual(app._ja_creds_store, {})
        self.assertEqual(app._ja_oauth_sessions, {})
        secure_delete.assert_called_once_with("jobadder")


def tearDownModule():
    if _MODULE_TEMPORARY is not None:
        _MODULE_TEMPORARY.cleanup()


if __name__ == "__main__":
    unittest.main()
