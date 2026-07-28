import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

import cvstudio_antiword as antiword
from cvstudio_diagnostics import dependency_status
from owner_build_tools.build_protected import validate_antiword_runtime


ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor" / "antiword"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class AntiwordMandatoryDependencyTests(unittest.TestCase):
    def test_pinned_windows_runtime_is_complete_trusted_and_functional(self):
        if os.name != "nt":
            self.skipTest("Genuine Windows Antiword execution is Windows-only")
        health = antiword.antiword_health(ROOT)
        self.assertEqual(
            {
                "available": health["available"],
                "trusted": health["trusted"],
                "functional": health["functional"],
                "version": health["version"],
                "engine_version": health["engine_version"],
                "platform": health["platform"],
                "source": health["source"],
                "manifest_verified": health["manifest_verified"],
                "functional_fixture_verified": health[
                    "functional_fixture_verified"
                ],
                "runtime_file_count": health["runtime_file_count"],
            },
            {
                "available": True,
                "trusted": True,
                "functional": True,
                "version": "1.3.5",
                "engine_version": "0.37",
                "platform": "windows-x64",
                "source": "bundled",
                "manifest_verified": True,
                "functional_fixture_verified": True,
                "runtime_file_count": 37,
            },
        )
        self.assertNotIn(str(ROOT), json.dumps(health))
        executable = Path(antiword.require_verified_antiword(ROOT))
        self.assertEqual(
            sha256(executable),
            "2cbab2831854ccd5141ea328824a77cb889586db2e97129873d543a52cf3e15c",
        )

    def test_corruption_and_extra_runtime_files_fail_closed(self):
        if os.name != "nt":
            self.skipTest("Windows runtime corruption fixture is Windows-only")
        with tempfile.TemporaryDirectory(prefix="cvstudio-antiword-corrupt-") as td:
            package = Path(td)
            copied_vendor = package / "vendor" / "antiword"
            shutil.copytree(VENDOR, copied_vendor)
            mapping = (
                copied_vendor
                / "windows-x64"
                / "share"
                / "antiword"
                / "UTF-8.txt"
            )
            mapping.write_bytes(mapping.read_bytes() + b"\ncorrupt")
            with mock.patch.dict(
                os.environ,
                {"LOCALAPPDATA": str(package / "empty-state")},
                clear=False,
            ):
                health = antiword.antiword_health(package)
            self.assertFalse(health["available"])
            self.assertEqual(health["reason"], "runtime-integrity-failed")

            shutil.rmtree(copied_vendor)
            shutil.copytree(VENDOR, copied_vendor)
            unexpected = copied_vendor / "windows-x64" / "bin" / "helper.exe"
            unexpected.write_bytes(b"not allowed")
            with mock.patch.dict(
                os.environ,
                {"LOCALAPPDATA": str(package / "empty-state-2")},
                clear=False,
            ):
                health = antiword.antiword_health(package)
            self.assertFalse(health["available"])
            self.assertEqual(health["reason"], "runtime-file-set-invalid")

    def test_arbitrary_path_and_unpinned_installs_are_never_candidates(self):
        with tempfile.TemporaryDirectory(prefix="cvstudio-antiword-path-") as td:
            root = Path(td)
            fake = root / ("antiword.exe" if os.name == "nt" else "antiword")
            fake.write_bytes(b"untrusted executable")
            with mock.patch.dict(
                os.environ,
                {
                    "PATH": str(root),
                    "ANTIWORDHOME": str(root),
                    "LOCALAPPDATA": str(root / "empty-state"),
                },
                clear=False,
            ):
                health = antiword.antiword_health(root / "empty-package")
                found = antiword.find_verified_antiword(
                    root / "empty-package"
                )
            self.assertIsNone(found)
            self.assertFalse(health["available"])
            source = Path(antiword.__file__).read_text(encoding="utf-8")
            self.assertNotIn("shutil.which", source)
            self.assertNotIn("Program Files", source)

    def test_junction_or_reparse_runtime_boundaries_fail_closed(self):
        class JunctionFixture:
            @staticmethod
            def is_symlink():
                return False

            @staticmethod
            def is_junction():
                return True

        self.assertTrue(antiword._is_link_or_reparse(JunctionFixture()))

    def test_every_official_artifact_and_corresponding_source_is_pinned(self):
        expected = {
            "packages/antiword_1.3.5_windows_x64_r46.zip":
                "9a99f67680475605de009cb85ba94c7dc546eb261a4256d743597fbb24b0ddf8",
            "packages/antiword_1.3.5_macos_x86_64_r46.tgz":
                "501f2cf83b050fd4a56ab1ecff6fe21295c168eb4a9876d46c259e7ca21cb923",
            "packages/antiword_1.3.5_macos_arm64_r46.tgz":
                "17cd193eb8ed3b27d092c60fec181e6a7b6d82eda9741dbec03578396d659e25",
            "source/antiword_1.3.5.tar.gz":
                "72e84b33b54c11101cb70d63304ca0283f57a6d0ef518ca6329ff5e6490ad630",
            "GPL-2.0.txt":
                "edaef632cbb643e4e7a221717a6c441a4c1a7c918e6e4d56debc3d8739b233f6",
            "fixtures/UDHR-english.doc":
                "f430cdfe9446c4b943074d4bf804232761c284f2caa3d4125006b158d8b14af8",
        }
        self.assertEqual(
            {relative: sha256(VENDOR / relative) for relative in expected},
            expected,
        )
        self.assertIn("GNU GENERAL PUBLIC LICENSE", (
            VENDOR / "GPL-2.0.txt"
        ).read_text(encoding="utf-8"))

    def test_macos_artifacts_are_exact_native_architectures(self):
        x86 = (VENDOR / "macos-x86_64" / "bin" / "antiword").read_bytes()
        arm = (VENDOR / "macos-arm64" / "bin" / "antiword").read_bytes()
        self.assertEqual(x86[:8].hex(), "cffaedfe07000001")
        self.assertEqual(arm[:8].hex(), "cffaedfe0c000001")
        self.assertEqual(
            sha256(VENDOR / "macos-x86_64" / "bin" / "antiword"),
            "867f9688d851ec85cb6dd5e70f14abcf53e2c77bf55da20ec6e8b94399904d5f",
        )
        self.assertEqual(
            sha256(VENDOR / "macos-arm64" / "bin" / "antiword"),
            "d4ad0924e195f5dc6a898d5bdcb734a532446ed927af7e3c49865b11ef5e250d",
        )

    def test_linux_proof_target_statically_verifies_but_never_claims_support(self):
        health = validate_antiword_runtime(ROOT, "linux-x64-test")
        self.assertFalse(health["available"])
        self.assertTrue(health["trusted"])
        self.assertFalse(health["functional"])
        self.assertTrue(health["test_only"])
        self.assertEqual(health["static_platform_manifests_verified"], 3)

    def test_critical_unicode_and_windows_mapping_resources_are_pinned(self):
        expected = {
            "share/antiword/UTF-8.txt":
                "2401ee812ff859a85f3b737be7daf32f19c11946ecaa5f5e66468abae4fe2d43",
            "share/antiword/cp1252.txt":
                "fca3ab5882f0a562794f05d7f15a39157c59d7c07fcbac79ab7cf3d12c979541",
            "share/antiword/Unicode01":
                "6fa1684cdf01960adf325cc60760d376f917c49d9a1edb4cf8b69893a8e434da",
            "share/antiword/Default":
                "b005fff466673f0a032610d5464302cfdf7ac67485cfb5608357ffb29b51dad4",
        }
        for platform_tag in (
            "windows-x64",
            "macos-x86_64",
            "macos-arm64",
        ):
            self.assertEqual(
                {
                    relative: sha256(VENDOR / platform_tag / relative)
                    for relative in expected
                },
                expected,
            )

    def test_functional_timeout_is_bounded_and_failure_visible(self):
        if os.name != "nt":
            self.skipTest("Windows executable timeout fixture is Windows-only")
        executable = VENDOR / "windows-x64" / "bin" / "antiword.exe"
        fixture = VENDOR / "fixtures" / "UDHR-english.doc"
        with mock.patch.object(
            antiword.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired("antiword", 12),
        ) as run:
            with self.assertRaises(antiword.AntiwordDependencyError) as caught:
                antiword._functional_check(executable, fixture)
        self.assertEqual(caught.exception.reason, "functional-execution-timeout")
        self.assertEqual(run.call_args.kwargs["timeout"], 12)
        self.assertFalse(run.call_args.kwargs["check"])

    def test_extraction_verifier_has_no_network_or_shell_discovery(self):
        source = Path(antiword.__file__).read_text(encoding="utf-8")
        for forbidden in (
            "urllib",
            "requests",
            "urlopen",
            "socket",
            "shell=True",
            "shutil.which",
            "Program Files",
        ):
            self.assertNotIn(forbidden, source)
        self.assertIn("TemporaryDirectory", (
            ROOT / "app.py"
        ).read_text(encoding="utf-8"))

    def test_installers_are_mandatory_fail_closed_and_idempotent(self):
        windows = (ROOT / "INSTALL_CORE.ps1").read_text(
            encoding="utf-8-sig"
        )
        macos = (ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertIn(
            "if ($ok -and -not (Check-Antiword)) { $ok = $false }",
            windows,
        )
        self.assertIn("Test-AntiwordRuntime", windows)
        self.assertIn("Invoke-AntiwordFunctionalCheck", windows)
        self.assertIn("WaitForExit(12000)", windows)
        self.assertIn("WaitForExit(2000)", windows)
        self.assertNotIn("$process.WaitForExit()", windows)
        self.assertIn("functional-execution-timeout", windows)
        self.assertIn("runtime-link-rejected", windows)
        self.assertIn("manifest-link-rejected", windows)
        self.assertIn("functional-fixture-link-rejected", windows)
        self.assertIn("$script:AntiwordFailure = 'verification-failed'", windows)
        self.assertIn(
            "$script:AntiwordFailure = 'install-or-repair-failed'",
            windows,
        )
        self.assertIn("[guid]::NewGuid().ToString('N')", windows)
        self.assertIn(
            "Remove-Item -LiteralPath $stage -Recurse -Force",
            windows,
        )
        self.assertIn("Managed Antiword 1.3.5 is hash-verified", windows)
        self.assertIn("AntiwordSelfTestOnly", windows)
        self.assertIn(
            "Antiword self-test requires a fresh, non-existent temporary state directory.",
            windows,
        )
        self.assertIn(
            "Antiword self-test state cannot be a reparse point.",
            windows,
        )
        self.assertIn(
            "Dependency QA cannot issue a receipt or reach the installer main block",
            windows,
        )
        self.assertNotIn("Native .doc extraction fallback remains active", windows)
        self.assertNotIn("Get-Command antiword", windows)
        self.assertIn("install_verified_antiword ||", macos)
        self.assertIn("verify_antiword_runtime", macos)
        self.assertIn("run_antiword_functional_check", macos)
        self.assertIn("/bin/sleep 12", macos)
        self.assertIn('"$check_dir/timed-out"', macos)
        self.assertIn("timed out after 12 seconds", macos)
        for trusted_tool in (
            "/usr/bin/shasum",
            "/usr/bin/mktemp",
            "/usr/bin/env",
            "/usr/bin/find",
            "/usr/bin/file",
            "/usr/bin/codesign",
            "/bin/chmod",
            "/bin/kill",
            "/bin/date",
            "/bin/cp",
            "/bin/mv",
            "/bin/rm",
        ):
            self.assertIn(trusted_tool, macos)
        self.assertIn('[ ! -L "$runtime_root" ]', macos)
        self.assertIn('[ ! -L "$runtime_root/SHA256SUMS" ]', macos)
        self.assertIn('[ ! -L "$executable" ]', macos)
        self.assertIn(
            '/usr/bin/mktemp -d "$dependency_base/$tag.stage.XXXXXX"',
            macos,
        )
        self.assertIn("remove_antiword_stage", macos)
        self.assertIn('.$$.$RANDOM', macos)
        self.assertIn("Managed Antiword 1.3.5 is hash-verified", macos)
        self.assertIn("ANTIWORD_OK", macos)

        protected_builder = (
            ROOT / "owner_build_tools" / "build_protected.py"
        ).read_text(encoding="utf-8")
        self.assertIn('base_url+"/extract-text"', protected_builder)
        self.assertIn(
            "Compiled legacy .doc extraction did not return verified Antiword text",
            protected_builder,
        )
        self.assertIn(
            'fixture_sha256":hashlib.sha256(fixture).hexdigest()',
            protected_builder,
        )

    def test_native_parser_is_retained_but_cannot_satisfy_success(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("def _extract_word_binary_piece_table", source)
        self.assertIn(
            "if not _verified_antiword_text:\n"
            "                raise AntiwordDependencyError(",
            source,
        )
        self.assertIn(
            "Native OLE parsing remains defense-in-depth and cannot satisfy success",
            source,
        )

    def test_diagnostics_preserve_boolean_and_add_health(self):
        legacy_finder = mock.Mock(return_value="must-not-run")
        health_finder = mock.Mock(
            return_value={
                "available": True,
                "trusted": True,
                "functional": True,
            }
        )
        status = dependency_status(
            lambda: None,
            legacy_finder,
            health_finder,
        )
        self.assertTrue(status["antiword"])
        legacy_finder.assert_not_called()
        health_finder.assert_called_once_with()
        self.assertEqual(
            status["antiword_health"],
            {"available": True, "trusted": True, "functional": True},
        )

        fallback_finder = mock.Mock(return_value="legacy-compatible")
        fallback = dependency_status(lambda: None, fallback_finder)
        self.assertTrue(fallback["antiword"])
        fallback_finder.assert_called_once_with()

    def test_installer_health_deadlines_cover_one_functional_timeout(self):
        windows = (ROOT / "INSTALL_CORE.ps1").read_text(
            encoding="utf-8-sig"
        )
        macos = (ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertIn(
            '/diagnostics/runtime" -f $port) -Headers $headers -Method Get -TimeoutSec 15',
            windows,
        )
        self.assertIn(
            "HEALTH_DEADLINE=$((SECONDS + 75))",
            macos,
        )
        self.assertIn(
            "remaining=$((HEALTH_DEADLINE - SECONDS))",
            macos,
        )
        self.assertIn(
            '[ "$remaining" -lt "$timeout" ] && timeout="$remaining"',
            macos,
        )
        self.assertIn(
            'DIAG_JSON="$(health_curl 15 '
            '"http://localhost:$SMOKE_PORT/diagnostics/runtime"',
            macos,
        )
        health_loop = macos.split(
            "for _i in $(seq 1 180); do",
            1,
        )[1].split("done", 1)[0]
        self.assertNotIn("curl -fsS", health_loop)


if __name__ == "__main__":
    unittest.main()
