"""Characterization tests for the MS-Graph / Outlook pure helpers.

Locks the behaviour of the stateless helpers extracted into
``cvstudio_msgraph`` (Phase 7B, first slice of the OneNote + Outlook / MS-Graph
domain): tenant sanitisation, account projection, the device-login/draft
error-payload translator, and Outlook draft-input validation. Verbatim move, so
these assertions equally describe the legacy web-shell behaviour.
"""

import os
import unittest

import cvstudio_msgraph as mg


class SafeTenantTests(unittest.TestCase):
    def test_defaults_to_common(self):
        self.assertEqual(mg._ms_safe_tenant(""), "common")
        self.assertEqual(mg._ms_safe_tenant(None), "common")

    def test_strips_disallowed_characters(self):
        self.assertEqual(mg._ms_safe_tenant("contoso.onmicrosoft.com"), "contoso.onmicrosoft.com")
        self.assertEqual(mg._ms_safe_tenant("bad/tenant name!"), "badtenantname")
        # A GUID tenant survives unchanged.
        self.assertEqual(
            mg._ms_safe_tenant("72f988bf-86f1-41af-91ab-2d7cd011db47"),
            "72f988bf-86f1-41af-91ab-2d7cd011db47",
        )

    def test_all_disallowed_falls_back_to_common(self):
        self.assertEqual(mg._ms_safe_tenant("///"), "common")


class AccountNormalizeTests(unittest.TestCase):
    def test_projects_id_name_email(self):
        out = mg._ms_outlook_account_normalize({"id": "1", "displayName": " Ada ", "mail": "ada@x.com"})
        self.assertEqual(out, {"id": "1", "displayName": "Ada", "email": "ada@x.com"})

    def test_email_falls_back_to_upn_then_email(self):
        self.assertEqual(mg._ms_outlook_account_normalize({"userPrincipalName": "u@x.com"})["email"], "u@x.com")
        self.assertEqual(mg._ms_outlook_account_normalize({"email": "e@x.com"})["email"], "e@x.com")

    def test_non_dict_returns_empty_shape(self):
        self.assertEqual(mg._ms_outlook_account_normalize(None), {"id": "", "displayName": "", "email": ""})


class ErrorPayloadTests(unittest.TestCase):
    def test_authorization_pending_is_pending(self):
        out = mg._ms_outlook_error_payload('{"error": "authorization_pending"}', 400)
        self.assertTrue(out["pending"])
        self.assertEqual(out["error_code"], "authorization_pending")
        self.assertIn("waiting for approval", out["error"])

    def test_slow_down_is_pending(self):
        out = mg._ms_outlook_error_payload('{"error": "slow_down"}', 400)
        self.assertTrue(out["pending"])

    def test_graph_error_object_code_and_message(self):
        body = '{"error": {"code": "ErrorAccessDenied", "message": "no perms"}}'
        out = mg._ms_outlook_error_payload(body, 403)
        self.assertEqual(out["error_code"], "ErrorAccessDenied")
        self.assertIn("permission", out["error"].lower())

    def test_invalid_grant_maps_to_reconnect(self):
        out = mg._ms_outlook_error_payload('{"error": "invalid_grant"}', 400)
        self.assertFalse(out["pending"])
        self.assertIn("expired or was revoked", out["error"])

    def test_status_only_401(self):
        out = mg._ms_outlook_error_payload("plain text", 401)
        self.assertIn("connection expired", out["error"])
        self.assertEqual(out["error_code"], "HTTP_401")

    def test_unparseable_body_gets_generic_code_and_truncates(self):
        out = mg._ms_outlook_error_payload("not json " * 500, 0)
        self.assertEqual(out["error_code"], "MICROSOFT_ERROR")
        self.assertLessEqual(len(out["technical_details"]), 2400)

    def test_bytes_body_is_decoded(self):
        out = mg._ms_outlook_error_payload(b'{"error": "slow_down"}', 400)
        self.assertTrue(out["pending"])


class ValidateDraftInputTests(unittest.TestCase):
    def test_valid_input_returns_tuple_and_collapses_subject_whitespace(self):
        recipient, subject, html = mg._ms_outlook_validate_draft_input(
            {"to": " a@b.com ", "subject": "hi\r\nthere", "html": "<p>x</p>"}
        )
        self.assertEqual(recipient, "a@b.com")
        self.assertEqual(subject, "hi there")
        self.assertEqual(html, "<p>x</p>")

    def test_invalid_recipient_raises_value_error(self):
        with self.assertRaises(ValueError):
            mg._ms_outlook_validate_draft_input({"to": "not-an-email", "subject": "s", "html": "<p>x</p>"})

    def test_missing_subject_and_body_raise_value_error(self):
        with self.assertRaises(ValueError):
            mg._ms_outlook_validate_draft_input({"to": "a@b.com", "subject": "", "html": "<p>x</p>"})
        with self.assertRaises(ValueError):
            mg._ms_outlook_validate_draft_input({"to": "a@b.com", "subject": "s", "html": ""})

    def test_oversized_content_raises_overflow_error(self):
        with self.assertRaises(OverflowError):
            mg._ms_outlook_validate_draft_input({"to": "a@b.com", "subject": "s", "html": "x" * 250001})


class _FakeGraphClient:
    """Records token_request calls; request_json is unused in these tests."""

    def __init__(self, token_provider=None, reconnect_handler=None):
        self.token_provider = token_provider
        self.reconnect_handler = reconnect_handler
        self.token_request_result = {}

    def token_request(self, *args, **kwargs):
        return self.token_request_result

    def request_json(self, *args, **kwargs):
        raise AssertionError("network not expected in these tests")


def _make_service(tmpdir, token_response=None):
    """Build an OutlookService with offline fakes and a temp receipt dir."""
    receipt = os.path.join(tmpdir, "install_receipt.json")
    return mg.OutlookService(
        jsonify=lambda payload: payload,
        request_json=lambda: _make_service._next_request or {},
        token_response=token_response or (lambda req, tenant="common": {}),
        graph_client_factory=lambda token_provider, reconnect_handler: _FakeGraphClient(token_provider, reconnect_handler),
        receipt_path=lambda: receipt,
        machine_hash=lambda: "fixture-machine-hash-000000000000",
        signing_key=lambda: b"fixture-signing-key-32-bytes-long!!",
    )


_make_service._next_request = None


class OutlookServiceStorageTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._tmp = tempfile.mkdtemp(prefix="outlook-svc-")

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_empty_store_reports_not_connected(self):
        svc = _make_service(self._tmp)
        info = svc.public_info()
        self.assertFalse(info["connected"])
        self.assertEqual(info["account"], {"id": "", "displayName": "", "email": ""})

    def test_machine_bound_round_trip_persists_tokens(self):
        # On Linux the primary vault is unavailable, so save writes the
        # authenticated machine-bound fallback file; a fresh instance must load
        # it back and report connected.
        svc = _make_service(self._tmp)
        with svc._store_lock:
            svc._store.update({
                "access_token": "fixture-access",
                "refresh_token": "fixture-refresh",
                "client_id": "00000000-0000-0000-0000-000000000000",
                "tenant": "common",
                "expires_at": 4102444800,
                "account": {"id": "1", "displayName": "Ada", "email": "ada@example.invalid"},
            })
            svc._save_store()
        reopened = _make_service(self._tmp)
        info = reopened.public_info()
        self.assertTrue(info["connected"])
        self.assertEqual(info["account"]["email"], "ada@example.invalid")
        self.assertEqual(info["storage"], "machine_bound_file")

    def test_disconnect_clears_store_and_reports_disconnected(self):
        svc = _make_service(self._tmp)
        with svc._store_lock:
            svc._store.update({"access_token": "x", "refresh_token": "y", "client_id": "c"})
            svc._save_store()
        result = svc.disconnect()
        self.assertFalse(result["connected"])
        self.assertFalse(svc.public_info()["connected"])
        # A fresh instance sees no persisted secret either.
        self.assertFalse(_make_service(self._tmp).public_info()["connected"])

    def test_device_start_rejects_invalid_client_id(self):
        svc = _make_service(self._tmp)
        _make_service._next_request = {"client_id": "not-a-guid", "tenant": "common"}
        try:
            payload, status = svc.device_start()
        finally:
            _make_service._next_request = None
        self.assertEqual(status, 400)
        self.assertIn("Client ID", payload["error"])

    def test_token_refresh_uses_injected_token_response(self):
        calls = []

        def fake_token_response(req, tenant="common"):
            calls.append((req, tenant))
            return {"access_token": "fresh-access", "refresh_token": "fresh-refresh", "expires_in": 3600}

        svc = _make_service(self._tmp, token_response=fake_token_response)
        with svc._store_lock:
            svc._store.update({
                "refresh_token": "old-refresh",
                "client_id": "00000000-0000-0000-0000-000000000000",
                "tenant": "common",
                "expires_at": 0,
            })
        token = svc._refresh_access_token(force=True)
        self.assertEqual(token, "fresh-access")
        self.assertEqual(calls[0][0]["grant_type"], "refresh_token")

    def test_refresh_without_credentials_raises_permission_error(self):
        svc = _make_service(self._tmp)
        with self.assertRaises(PermissionError):
            svc._refresh_access_token(force=True)


def _make_onenote_service(store_backend, token_response=None, request=None):
    """Build a OneNoteGraphService with in-memory secure store + fake client."""
    return mg.OneNoteGraphService(
        jsonify=lambda payload: payload,
        request_json=lambda: request or {},
        token_response=token_response or (lambda req, tenant="common": {}),
        secure_save=lambda service, record: (store_backend.__setitem__(service, dict(record)) or "backend_secure_store"),
        secure_load=lambda service: dict(store_backend.get(service) or {}),
        secure_delete=lambda service: store_backend.pop(service, None),
        graph_client_factory=lambda token_provider, reconnect_handler: _FakeGraphClient(token_provider, reconnect_handler),
    )


class OneNoteGraphServiceTests(unittest.TestCase):
    def test_empty_store_api_info_not_connected(self):
        svc = _make_onenote_service({})
        info = svc.api_info()
        self.assertFalse(info["connected"])
        self.assertEqual(info["storage"], "backend_secure_store")

    def test_store_token_persists_to_secure_store(self):
        backend = {}
        svc = _make_onenote_service(backend, request={"access_token": "tok", "refresh_token": "ref", "client_id": "cid"})
        result = svc.store_token()
        self.assertTrue(result["connected"])
        self.assertEqual(backend["onenote"]["access_token"], "tok")
        self.assertTrue(svc.api_info()["connected"])

    def test_disconnect_clears_store_and_secure_delete(self):
        backend = {"onenote": {"access_token": "tok"}}
        svc = _make_onenote_service(backend)
        self.assertTrue(svc.api_info()["connected"])
        result = svc.disconnect()
        self.assertFalse(result["connected"])
        self.assertNotIn("onenote", backend)
        self.assertFalse(svc.api_info()["connected"])

    def test_device_start_requires_client_id(self):
        svc = _make_onenote_service({}, request={"client_id": "", "tenant": "common"})
        payload, status = svc.device_start()
        self.assertEqual(status, 400)
        self.assertIn("client ID", payload["error"])

    def test_refresh_without_credentials_is_noop(self):
        # No refresh_token/client_id → returns the (empty) current token, no call.
        svc = _make_onenote_service({})
        self.assertEqual(svc._refresh_access_token(force=True), "")

    def test_loads_existing_secure_store_on_construction(self):
        backend = {"onenote": {"access_token": "persisted", "client_id": "cid"}}
        svc = _make_onenote_service(backend)
        self.assertTrue(svc.api_info()["connected"])
        self.assertEqual(svc._store["access_token"], "persisted")


class ModuleHygieneTests(unittest.TestCase):
    def test_module_does_not_import_app(self):
        self.assertNotIn("app", getattr(mg, "__dict__", {}))

    def test_services_exposed(self):
        self.assertTrue(hasattr(mg, "OutlookService"))
        self.assertTrue(hasattr(mg, "OneNoteGraphService"))

    def test_expected_symbols_present(self):
        for name in [
            "_ms_safe_tenant", "_ms_outlook_account_normalize",
            "_ms_outlook_error_payload", "_ms_outlook_validate_draft_input",
        ]:
            self.assertTrue(callable(getattr(mg, name)), name)


if __name__ == "__main__":
    unittest.main()
