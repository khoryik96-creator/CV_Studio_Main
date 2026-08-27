from __future__ import annotations

import inspect
import tempfile
import unittest
from pathlib import Path

from owner_build_tools import build_protected


ROOT = Path(__file__).resolve().parents[1]


class NodeInstallerDependencyTests(unittest.TestCase):
    def test_successful_install_moves_an_existing_startup_entry_to_new_root(self):
        installer = (ROOT / "INSTALL_CORE.ps1").read_text(encoding="utf-8-sig")
        function = installer.split(
            "function Repair-CvStudioStartupRegistration {", 1
        )[1].split("function Get-DesktopCvStudioShortcutPath {", 1)[0]

        self.assertIn("$valueName = 'GUOLabCVStudio'", function)
        self.assertIn("START_HIDDEN\\.vbs", function)
        self.assertIn("Set-ItemProperty", function)
        self.assertIn("was left unchanged", function)
        self.assertIn("Repair-CvStudioStartupRegistration | Out-Null", installer)
        self.assertLess(
            installer.index("if ($ok) {\n    Create-Shortcut -Phase 'final'"),
            installer.index("Repair-CvStudioStartupRegistration | Out-Null"),
        )

    def test_fresh_source_does_not_run_noisy_require_probe_before_install(self):
        installer = (ROOT / "INSTALL_CORE.ps1").read_text(encoding="utf-8-sig")
        function = installer.split("function Install-NodePackages {", 1)[1].split(
            "function Refresh-IconCache {", 1
        )[0]

        package_guard = (
            "if (Test-Path -LiteralPath $script:ProtectedAdmZipPackage "
            "-PathType Leaf) {"
        )
        first_probe = (
            "$verifyRc = Run-Logged -FilePath 'node' -Arguments "
            "@('-e', \"const p=require('adm-zip/package.json')"
        )
        self.assertIn(package_guard, function)
        self.assertIn(first_probe, function)
        self.assertLess(function.index(package_guard), function.index(first_probe))
        self.assertIn("$verifyRc = 1", function)
        self.assertIn("Owner/source build dependency is missing", function)

    def test_protected_package_receives_shared_installer_and_vetted_adm_zip(self):
        self.assertIn("INSTALL_CORE.ps1", build_protected.ROOT_FILES)
        build_source = inspect.getsource(build_protected.build_package)
        self.assertIn(
            "for name in ROOT_FILES: copy_item(source/name,package/name)",
            build_source,
        )
        self.assertIn(
            "bundle_node_runtime_dependency(source, package)",
            build_source,
        )

        with tempfile.TemporaryDirectory(prefix="cvstudio-node-bundle-") as td:
            package = Path(td) / "package"
            build_protected.bundle_node_runtime_dependency(ROOT, package)
            bundled = package / "node_modules" / "adm-zip" / "package.json"
            self.assertTrue(bundled.is_file())
            self.assertEqual(
                build_protected.sha256_tree(bundled.parent),
                build_protected.ADM_ZIP_TREE_SHA256,
            )


if __name__ == "__main__":
    unittest.main()
