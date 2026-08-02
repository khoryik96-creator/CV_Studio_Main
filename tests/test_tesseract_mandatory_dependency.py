import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import cvstudio_tesseract as tesseract


ROOT = Path(__file__).resolve().parents[1]


class _Result:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class TesseractMandatoryDependencyTests(unittest.TestCase):
    def test_functional_version_and_english_language_are_required(self):
        with tempfile.TemporaryDirectory(prefix="cvstudio-tesseract-") as td:
            executable = Path(td) / ("tesseract.exe" if os.name == "nt" else "tesseract")
            executable.write_bytes(b"fixture")
            with mock.patch.object(tesseract, "tesseract_candidates", return_value=[executable]), mock.patch.object(
                tesseract.subprocess,
                "run",
                side_effect=[
                    _Result(stderr="tesseract v5.5.1\n"),
                    _Result(stdout="List of available languages in x (1):\neng\n"),
                ],
            ):
                found, health = tesseract.resolve_tesseract(ROOT)
            self.assertEqual(found, executable.resolve())
            self.assertTrue(health["available"])
            self.assertTrue(health["functional"])
            self.assertTrue(health["english_language_data"])

    def test_missing_english_data_fails_closed(self):
        with tempfile.TemporaryDirectory(prefix="cvstudio-tesseract-no-eng-") as td:
            executable = Path(td) / ("tesseract.exe" if os.name == "nt" else "tesseract")
            executable.write_bytes(b"fixture")
            with mock.patch.object(tesseract, "tesseract_candidates", return_value=[executable]), mock.patch.object(
                tesseract.subprocess,
                "run",
                side_effect=[_Result(stdout="tesseract 5.5.1\n"), _Result(stdout="deu\n")],
            ):
                found, health = tesseract.resolve_tesseract(ROOT)
            self.assertIsNone(found)
            self.assertFalse(health["available"])
            self.assertEqual(health["reason"], "english-language-data-missing")

    def test_installers_gate_tesseract_and_macos_antiword(self):
        windows = (ROOT / "INSTALL_CORE.ps1").read_text(encoding="utf-8-sig")
        macos = (ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertIn("if ($ok -and -not (Check-Tesseract)) { $ok = $false }", windows)
        self.assertNotIn("Tesseract is optional", windows)
        self.assertIn("UB-Mannheim.TesseractOCR", windows)
        self.assertIn("Installing mandatory Tesseract through Homebrew", macos)
        self.assertIn("Verifying mandatory Antiword", macos)
        self.assertIn("shasum -a 256 -c SHA256SUMS", macos)

    def test_runtime_diagnostics_and_protected_smoke_require_tesseract(self):
        app_source = (ROOT / "app.py").read_text(encoding="utf-8-sig")
        protected = (ROOT / "owner_build_tools" / "build_protected.py").read_text(
            encoding="utf-8-sig"
        )
        self.assertIn('status["tesseract_health"] = tesseract_health', app_source)
        self.assertIn('dependencies.get("tesseract")', protected)
        self.assertIn('tesseract_dependency.get("english_language_data")', protected)


if __name__ == "__main__":
    unittest.main()
