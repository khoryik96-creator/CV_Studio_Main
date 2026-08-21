"""Hermetic regressions for JobAdder original-CV multipart uploads.

No real JobAdder credential or network call is used.  The transport is replaced
with an in-memory fake so these tests can inspect the exact outbound request.
"""

import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import urllib.error


_MODULE_TEMPORARY = tempfile.TemporaryDirectory(
    prefix="cvstudio-jobadder-resume-upload-"
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


class _Response:
    status = 201
    body = b'{"attachmentId":1}'


class _FakeJobAdderClient:
    def __init__(self):
        self.raw_calls = []
        self.error = None

    def request_raw(self, endpoint, **kwargs):
        self.raw_calls.append((endpoint, kwargs))
        if self.error is not None:
            raise self.error
        return _Response()


class JobAdderResumeUploadCorrectiveTests(unittest.TestCase):
    def setUp(self):
        self.original_refresh = app._ja_refresh_access_token
        self.original_client = app._JOBADDER_CLIENT
        app._ja_refresh_access_token = lambda force=False: "fixture-token"
        self.client_double = _FakeJobAdderClient()
        app._JOBADDER_CLIENT = self.client_double
        self.http = app.app.test_client()

    def tearDown(self):
        app._ja_refresh_access_token = self.original_refresh
        app._JOBADDER_CLIENT = self.original_client

    @staticmethod
    def _headers(request_id):
        return {
            "X-CV-Studio-Request": "1",
            "X-CV-Studio-Request-ID": request_id,
        }

    def _upload(self, filename, data=b"fixture-cv-bytes"):
        return self.http.post(
            "/jobadder/upload_original_cv",
            data={
                "candidate_id": "123",
                "file": (io.BytesIO(data), filename),
            },
            content_type="multipart/form-data",
            headers=self._headers("jobadder-resume-upload"),
        )

    def test_cv_multipart_uses_file_type_metadata_jobadder_accepts(self):
        cases = {
            "candidate.pdf": b"Content-Type: application/pdf\r\n",
            "candidate.docx": (
                b"Content-Type: application/vnd.openxmlformats-officedocument."
                b"wordprocessingml.document\r\n"
            ),
            "candidate.doc": b"Content-Type: application/msword\r\n",
        }
        for filename, expected_content_type in cases.items():
            with self.subTest(filename=filename):
                self.client_double.raw_calls.clear()
                response = self._upload(filename)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(self.client_double.raw_calls), 1)
                endpoint, kwargs = self.client_double.raw_calls[0]
                self.assertEqual(endpoint, "candidates/123/attachments/Resume")
                self.assertEqual(kwargs["method"], "POST")
                self.assertFalse(kwargs["safe_to_retry"])
                self.assertEqual(kwargs["retries"], 0)
                self.assertIn(expected_content_type, kwargs["body"])
                self.assertNotIn(
                    b"Content-Type: application/octet-stream\r\n",
                    kwargs["body"],
                )
                content_type = kwargs["headers"]["Content-Type"]
                self.assertRegex(
                    content_type,
                    r"^multipart/form-data; boundary=----CVStudioBoundary[0-9a-f]{36}$",
                )
                boundary = content_type.split("boundary=", 1)[1].encode("ascii")
                self.assertTrue(kwargs["body"].endswith(b"--" + boundary + b"--\r\n"))

    def test_422_keeps_jobadder_validation_detail_and_readable_message(self):
        raw_detail = json.dumps(
            {
                "message": "Attachment validation failed",
                "errors": {"fileData": ["The uploaded CV could not be accepted"]},
            }
        ).encode("utf-8")
        self.client_double.error = urllib.error.HTTPError(
            "https://api.jobadder.invalid/candidates/123/attachments/Resume",
            422,
            "Unprocessable Entity",
            {},
            io.BytesIO(raw_detail),
        )
        response = self._upload("candidate.docx")
        self.assertEqual(response.status_code, 422)
        payload = response.get_json()
        self.assertEqual(payload["error"], "JobAdder error: 422")
        self.assertEqual(payload["code"], "JOBADDER_ATTACHMENT_VALIDATION_FAILED")
        self.assertEqual(payload["detail"], raw_detail.decode("utf-8"))
        self.assertEqual(
            payload["jobadder_message"],
            "Attachment validation failed The uploaded CV could not be accepted",
        )

    def test_empty_upload_is_rejected_before_jobadder_write(self):
        response = self._upload("candidate.pdf", b"")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "The selected CV file is empty")
        self.assertEqual(self.client_double.raw_calls, [])


if __name__ == "__main__":
    unittest.main()
