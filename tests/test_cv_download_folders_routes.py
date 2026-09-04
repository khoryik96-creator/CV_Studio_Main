import io
import os
from pathlib import Path
import tempfile
import unittest
import zipfile

from pypdf import PdfWriter

from owner_build_tools.build_protected import write_test_receipt


ROOT = Path(__file__).resolve().parents[1]
_MODULE_TEMPORARY = tempfile.TemporaryDirectory(prefix="cvstudio-download-routes-")
_ORIGINAL_DATABASE_OVERRIDE = os.environ.get("CVSTUDIO_DB_PATH")
os.environ["CVSTUDIO_DB_PATH"] = str(
    Path(_MODULE_TEMPORARY.name) / "state" / "cv_studio.sqlite3"
)
write_test_receipt(ROOT)
try:
    import app
finally:
    if _ORIGINAL_DATABASE_OVERRIDE is None:
        os.environ.pop("CVSTUDIO_DB_PATH", None)
    else:
        os.environ["CVSTUDIO_DB_PATH"] = _ORIGINAL_DATABASE_OVERRIDE

from cvstudio_downloads import LocalDownloadService


def _docx_bytes():
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", zipfile.ZIP_STORED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<document/>")
    return payload.getvalue()


def _pdf_bytes():
    payload = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.write(payload)
    return payload.getvalue()


class CvDownloadFolderRouteTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="cvstudio-download-route-case-")
        self.root = Path(self.temporary.name)
        self.folder = self.root / "CV Output"
        self.folder.mkdir()
        self.service = LocalDownloadService(self.root / "download_folders.json")
        self.previous = app._cvstudio_download_service
        app._cvstudio_download_service = self.service
        self.client = app.app.test_client()

    def tearDown(self):
        app._cvstudio_download_service = self.previous
        self.temporary.cleanup()

    @staticmethod
    def _headers(request_id):
        return {
            "X-CV-Studio-Request": "1",
            "X-CV-Studio-Request-ID": request_id,
        }

    def test_routes_are_guarded_and_have_the_rebaselined_contract(self):
        rules = {rule.rule: rule for rule in app.app.url_map.iter_rules()}
        self.assertEqual(len(rules), 118)
        self.assertEqual(
            rules["/downloads/folders"].methods & {"GET", "POST", "DELETE"},
            {"GET", "POST", "DELETE"},
        )
        self.assertEqual(rules["/downloads/folders"].endpoint, "cvstudio_download_folders")
        self.assertEqual(
            rules["/downloads/save"].methods & {"POST"}, {"POST"}
        )
        self.assertEqual(rules["/downloads/save"].endpoint, "cvstudio_download_save")

        blocked = self.client.post(
            "/downloads/folders", json={"kind": "formatted", "action": "check"}
        )
        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(blocked.get_json()["code"], "UNSAFE_LOCAL_REQUEST")

    def test_non_object_folder_request_is_rejected_without_http_500(self):
        response = self.client.post(
            "/downloads/folders",
            json=[{"kind": "formatted"}],
            headers=self._headers("download-route-non-object"),
        )
        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["code"], "DOWNLOAD_FOLDER_REQUEST_INVALID")
        self.assertEqual(payload["request_id"], "download-route-non-object")

    def test_select_status_check_save_and_clear_round_trip(self):
        self.service._choose_folder_native = lambda _initial: str(self.folder)
        selected = self.client.post(
            "/downloads/folders",
            json={"kind": "formatted", "action": "select"},
            headers=self._headers("download-route-select"),
        )
        self.assertEqual(selected.status_code, 200)
        self.assertEqual(selected.get_json()["folder"]["path"], str(self.folder))

        status = self.client.get(
            "/downloads/folders", headers=self._headers("download-route-status")
        )
        self.assertEqual(status.status_code, 200)
        self.assertTrue(status.get_json()["folders"]["formatted"]["configured"])

        checked = self.client.post(
            "/downloads/folders",
            json={"kind": "formatted", "action": "check"},
            headers=self._headers("download-route-check"),
        )
        self.assertEqual(checked.status_code, 200)
        self.assertTrue(checked.get_json()["folder"]["writable"])

        generated = _docx_bytes()
        saved = self.client.post(
            "/downloads/save",
            data={
                "kind": "formatted",
                "filename": "Hyppies CV.docx",
                "file": (io.BytesIO(generated), "Hyppies CV.docx"),
            },
            headers=self._headers("download-route-save"),
            content_type="multipart/form-data",
        )
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.get_json()["path"], str(self.folder / "Hyppies CV.docx"))
        self.assertEqual(
            (self.folder / "Hyppies CV.docx").read_bytes(),
            generated,
        )

        cleared = self.client.delete(
            "/downloads/folders",
            json={"kind": "formatted"},
            headers=self._headers("download-route-clear"),
        )
        self.assertEqual(cleared.status_code, 200)
        self.assertFalse(cleared.get_json()["folder"]["configured"])
        self.assertTrue((self.folder / "Hyppies CV.docx").exists())

    def test_configured_folder_failure_is_structured_and_does_not_write_elsewhere(self):
        self.service._write_state_unlocked({"blind": str(self.root / "missing")})
        response = self.client.post(
            "/downloads/save",
            data={
                "kind": "blind",
                "filename": "Blind.docx",
                "file": (io.BytesIO(b"data"), "Blind.docx"),
            },
            headers=self._headers("download-route-missing"),
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 409)
        payload = response.get_json()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["code"], "DOWNLOAD_FOLDER_UNAVAILABLE")
        self.assertEqual(payload["request_id"], "download-route-missing")

    def test_invalid_zip_signature_imitation_is_rejected_and_removed(self):
        self.service._write_state_unlocked({"formatted": str(self.folder)})
        response = self.client.post(
            "/downloads/save",
            data={
                "kind": "formatted",
                "filename": "Fake.docx",
                "file": (io.BytesIO(b"PK\x03\x04not-a-real-zip"), "Fake.docx"),
            },
            headers=self._headers("download-route-invalid-docx"),
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["code"], "DOWNLOAD_FILE_INVALID")
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_company_profile_pdf_uses_its_own_configured_destination(self):
        self.service._write_state_unlocked({"company_profile": str(self.folder)})
        generated = _pdf_bytes()

        saved = self.client.post(
            "/downloads/save",
            data={
                "kind": "company_profile",
                "filename": "Company Profile.pdf",
                "file": (io.BytesIO(generated), "Company Profile.pdf"),
            },
            headers=self._headers("download-route-company-pdf"),
            content_type="multipart/form-data",
        )

        self.assertEqual(saved.status_code, 200)
        self.assertEqual(
            saved.get_json()["path"], str(self.folder / "Company Profile.pdf")
        )
        self.assertEqual((self.folder / "Company Profile.pdf").read_bytes(), generated)


if __name__ == "__main__":
    unittest.main()
