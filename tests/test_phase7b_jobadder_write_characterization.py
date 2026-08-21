"""Phase 7B-5c JobAdder candidate-write characterization.

Locks the authenticated behaviour of the JSON candidate-write routes
(``/jobadder/create_candidate`` and ``/jobadder/update_candidate``) before they
are moved out of the legacy web shell.  Hermetic: the OAuth token refresh and
the ``JobAdderClient`` transport are replaced with in-memory fakes, so no real
OAuth exchange or network write happens.  The unauthenticated 401 contract for
these routes is already locked by the Phase 7B-5a coverage net; this module adds
the authenticated payload-construction and transport-call contracts (POST vs
PUT, endpoint, non-retryable write flags, email flattening, empty-value
stripping, candidateId handling).
"""

import json
import io
import os
from pathlib import Path
import tempfile
import unittest
import urllib.error

_MODULE_TEMPORARY = tempfile.TemporaryDirectory(
    prefix="cvstudio-phase7b-ja-write-"
)
_ORIGINAL_DATABASE_OVERRIDE = os.environ.get("CVSTUDIO_DB_PATH")
os.environ["CVSTUDIO_DB_PATH"] = str(
    Path(_MODULE_TEMPORARY.name) / "state" / "cv_studio.sqlite3"
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


class _FakeJobAdderClient:
    def __init__(self):
        self.json_calls = []
        self.json_response = (200, {"candidateId": 123, "fake": True})
        self.error = None

    def request_json(self, endpoint, **kwargs):
        self.json_calls.append((endpoint, kwargs))
        if self.error:
            raise self.error
        return self.json_response


class Phase7BJobAdderWriteTests(unittest.TestCase):
    def setUp(self):
        self._orig_refresh = app._ja_refresh_access_token
        self._orig_client = app._JOBADDER_CLIENT
        app._ja_refresh_access_token = lambda force=False: "fake-token"
        self.client_double = _FakeJobAdderClient()
        app._JOBADDER_CLIENT = self.client_double
        self.http = app.app.test_client()

    def tearDown(self):
        app._ja_refresh_access_token = self._orig_refresh
        app._JOBADDER_CLIENT = self._orig_client

    @staticmethod
    def _headers(request_id):
        return {
            "X-CV-Studio-Request": "1",
            "X-CV-Studio-Request-ID": request_id,
        }

    def test_create_candidate_posts_non_retryable_and_flattens_email(self):
        response = self.http.post(
            "/jobadder/create_candidate",
            json={
                "firstName": "Ada",
                "email": [{"address": "ada@example.com"}],
                "blank": "",
                "emptyList": [],
                "emptyDict": {},
            },
            headers=self._headers("phase7b-ja-create"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"candidateId": 123, "fake": True})

        self.assertEqual(len(self.client_double.json_calls), 1)
        endpoint, kwargs = self.client_double.json_calls[0]
        self.assertEqual(endpoint, "candidates")
        self.assertEqual(kwargs.get("method"), "POST")
        self.assertEqual(kwargs.get("token"), "fake-token")
        self.assertFalse(kwargs.get("safe_to_retry"))
        self.assertEqual(kwargs.get("retries"), 0)
        payload = json.loads(kwargs["body"])
        self.assertEqual(payload["firstName"], "Ada")
        self.assertEqual(payload["email"], "ada@example.com")  # flattened
        self.assertNotIn("blank", payload)
        self.assertNotIn("emptyList", payload)
        self.assertNotIn("emptyDict", payload)

    def test_create_candidate_rejects_empty_body(self):
        response = self.http.post(
            "/jobadder/create_candidate",
            json={},
            headers=self._headers("phase7b-ja-create-empty"),
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client_double.json_calls, [])

    def test_create_candidate_rejects_invalid_email_before_remote_write(self):
        response = self.http.post(
            "/jobadder/create_candidate",
            json={"firstName": "Ada", "email": "Email not available"},
            headers=self._headers("phase7b-ja-create-invalid-email"),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("valid format", response.get_json()["error"])
        self.assertEqual(self.client_double.json_calls, [])

    def test_create_candidate_extracts_one_phone_from_concatenated_ai_text(self):
        response = self.http.post(
            "/jobadder/create_candidate",
            json={
                "firstName": "Ada",
                "email": "Email: ADA@EXAMPLE.COM",
                "phone": "Mobile: +60 12-345 6789 Address and unrelated prose " * 3,
                "mobile": "Mobile: +60 12-345 6789 Address and unrelated prose " * 3,
            },
            headers=self._headers("phase7b-ja-create-contact-clean"),
        )
        self.assertEqual(response.status_code, 200)
        payload = json.loads(self.client_double.json_calls[0][1]["body"])
        self.assertEqual(payload["email"], "ada@example.com")
        self.assertEqual(payload["phone"], "+60 12-345 6789")
        self.assertEqual(payload["mobile"], "+60 12-345 6789")
        self.assertLessEqual(len(payload["phone"]), 50)

    def test_create_candidate_surfaces_readable_jobadder_validation_reason(self):
        detail = json.dumps({
            "message": "Validation failed",
            "errors": [{"message": "Email provided is not valid", "fields": ["email"]}],
        }).encode()
        self.client_double.error = urllib.error.HTTPError(
            "https://api.example.invalid/candidates",
            422,
            "Unprocessable Entity",
            {},
            io.BytesIO(detail),
        )
        response = self.http.post(
            "/jobadder/create_candidate",
            json={"firstName": "Ada", "email": "ada@example.com"},
            headers=self._headers("phase7b-ja-create-remote-validation"),
        )
        self.assertEqual(response.status_code, 422)
        payload = response.get_json()
        self.assertIn("Validation failed", payload["jobadder_message"])
        self.assertIn("Email provided is not valid", payload["jobadder_message"])

    def test_update_candidate_puts_to_candidate_id_and_strips_id_from_body(self):
        response = self.http.post(
            "/jobadder/update_candidate",
            json={"candidateId": "55", "firstName": "Grace", "blank": ""},
            headers=self._headers("phase7b-ja-update"),
        )
        self.assertEqual(response.status_code, 200)

        self.assertEqual(len(self.client_double.json_calls), 1)
        endpoint, kwargs = self.client_double.json_calls[0]
        self.assertEqual(endpoint, "candidates/55")
        self.assertEqual(kwargs.get("method"), "PUT")
        self.assertFalse(kwargs.get("safe_to_retry"))
        payload = json.loads(kwargs["body"])
        self.assertEqual(payload["firstName"], "Grace")
        self.assertNotIn("candidateId", payload)
        self.assertNotIn("blank", payload)

    def test_update_candidate_requires_candidate_id_and_nonempty_body(self):
        missing_id = self.http.post(
            "/jobadder/update_candidate",
            json={"firstName": "NoId"},
            headers=self._headers("phase7b-ja-update-noid"),
        )
        self.assertEqual(missing_id.status_code, 400)

        empty = self.http.post(
            "/jobadder/update_candidate",
            json={},
            headers=self._headers("phase7b-ja-update-empty"),
        )
        self.assertEqual(empty.status_code, 400)
        self.assertEqual(self.client_double.json_calls, [])


if __name__ == "__main__":
    unittest.main()
