"""Install-receipt authorization is per machine + folder, not per version.

Once a user authorizes CV Studio on a computer, routine version updates must not
re-trigger the "not fully installed or authorized" prompt. These tests lock that
in: a correctly-signed receipt authorizes regardless of the version it names,
while machine, folder, or signature tampering is still rejected.

The install receipt lives at a single per-user path, so this module snapshots
whatever receipt is present and restores it after every test — leaving the shared
authorized state exactly as it found it for other test modules in the process.
"""

import hashlib
import hmac
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

from owner_build_tools import build_protected


ROOT = Path(__file__).resolve().parents[1]

_MODULE_TEMPORARY = None
if "app" not in sys.modules:
    _MODULE_TEMPORARY = tempfile.TemporaryDirectory(prefix="cvstudio-receipt-auth-")
    _temporary_root = Path(_MODULE_TEMPORARY.name)
    _original_database_override = os.environ.get("CVSTUDIO_DB_PATH")
    os.environ["CVSTUDIO_DB_PATH"] = str(_temporary_root / "state" / "cv_studio.sqlite3")
    build_protected.write_test_receipt(ROOT)
    try:
        import app
    finally:
        if _original_database_override is None:
            os.environ.pop("CVSTUDIO_DB_PATH", None)
        else:
            os.environ["CVSTUDIO_DB_PATH"] = _original_database_override
else:
    import app


def _write_receipt(version, *, machine=None, root_hash=None, break_signature=False):
    """Write a receipt naming `version`, correctly signed unless asked otherwise."""
    machine = app._install_receipt_machine_hash() if machine is None else machine
    root_hash = app._install_package_root_hash() if root_hash is None else root_hash
    data = {
        "schema": app._INSTALL_RECEIPT_SCHEMA,
        "product": app._INSTALL_RECEIPT_PRODUCT,
        "machine": machine,
        "version": version,
        "rootHash": root_hash,
        "issuedAt": "2020-01-01T00:00:00Z",
    }
    signature = hmac.new(
        app._install_receipt_signing_key(),
        app._install_receipt_message(data).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    data["signature"] = "0" * len(signature) if break_signature else signature
    path = Path(app._install_receipt_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


class InstallReceiptAuthorizationTests(unittest.TestCase):
    def setUp(self):
        # Snapshot the shared receipt so tamper cases never leak past this module.
        self._path = Path(app._install_receipt_path())
        self._prior = self._path.read_bytes() if self._path.exists() else None

    def tearDown(self):
        if self._prior is None:
            if self._path.exists():
                self._path.unlink()
        else:
            self._path.write_bytes(self._prior)

    def test_receipt_from_an_older_version_still_authorizes(self):
        _write_receipt("v0.0.1")
        ok, reason, _ = app._install_receipt_status()
        self.assertTrue(ok, reason)

    def test_receipt_from_a_newer_version_still_authorizes(self):
        _write_receipt("v99.99.999")
        ok, reason, _ = app._install_receipt_status()
        self.assertTrue(ok, reason)

    def test_receipt_matching_the_current_version_authorizes(self):
        _write_receipt(app._INSTALL_RECEIPT_VERSION)
        ok, reason, _ = app._install_receipt_status()
        self.assertTrue(ok, reason)

    def test_receipt_from_another_computer_is_rejected(self):
        _write_receipt(app._INSTALL_RECEIPT_VERSION, machine="0" * 64)
        ok, reason, _ = app._install_receipt_status()
        self.assertFalse(ok)
        self.assertIn("another computer", reason)

    def test_receipt_from_another_folder_is_rejected(self):
        _write_receipt(app._INSTALL_RECEIPT_VERSION, root_hash="0" * 64)
        ok, reason, _ = app._install_receipt_status()
        self.assertFalse(ok)
        self.assertIn("another extracted folder", reason)

    def test_tampered_signature_is_rejected(self):
        # A different-version receipt whose signature does not cover that version
        # must not slip through — the signature still gates forgery.
        _write_receipt("v0.0.1", break_signature=True)
        ok, reason, _ = app._install_receipt_status()
        self.assertFalse(ok)
        self.assertIn("signature", reason)


def tearDownModule():
    if _MODULE_TEMPORARY is not None:
        _MODULE_TEMPORARY.cleanup()


if __name__ == "__main__":
    unittest.main()
