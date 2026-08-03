"""Characterization tests for the MS-Graph / Outlook pure helpers.

Locks the behaviour of the stateless helpers extracted into
``cvstudio_msgraph`` (Phase 7B, first slice of the OneNote + Outlook / MS-Graph
domain): tenant sanitisation, account projection, the device-login/draft
error-payload translator, and Outlook draft-input validation. Verbatim move, so
these assertions equally describe the legacy web-shell behaviour.
"""

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


class ModuleHygieneTests(unittest.TestCase):
    def test_module_does_not_import_app(self):
        self.assertNotIn("app", getattr(mg, "__dict__", {}))

    def test_expected_symbols_present(self):
        for name in [
            "_ms_safe_tenant", "_ms_outlook_account_normalize",
            "_ms_outlook_error_payload", "_ms_outlook_validate_draft_input",
        ]:
            self.assertTrue(callable(getattr(mg, name)), name)


if __name__ == "__main__":
    unittest.main()
