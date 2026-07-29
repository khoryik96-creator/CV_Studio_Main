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
import owner_build_tools.build_protected as protected_build
from cvstudio_diagnostics import dependency_status
from cvstudio_jobs import PersistentJobStore, default_job_state_path
from cvstudio_storage import CVStudioStorage, default_database_path
from owner_build_tools.build_protected import (
    protected_smoke_environment,
    receipt_path,
    validate_antiword_runtime,
    write_test_receipt,
)


ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor" / "antiword"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class AntiwordMandatoryDependencyTests(unittest.TestCase):
    def test_protected_smoke_redirects_every_supported_state_override(self):
        with tempfile.TemporaryDirectory(
            prefix="cvstudio-antiword-smoke-override-"
        ) as td:
            root = Path(td)
            sentinels = root / "owner-sentinels"
            sentinel_home = sentinels / "home"
            sentinel_local = sentinels / "localappdata"
            sentinel_state = sentinels / "state"
            for directory in (
                sentinel_home,
                sentinel_local,
                sentinel_state,
            ):
                directory.mkdir(parents=True)
                (directory / "sentinel.txt").write_bytes(b"owner-state")
            sentinel_db = sentinels / "owner.sqlite3"
            sentinel_jobs = sentinels / "owner-jobs.json"
            sentinel_db.write_bytes(b"owner-database")
            sentinel_jobs.write_bytes(b"owner-journal")
            seeded = {
                "HOME": str(sentinel_home),
                "LOCALAPPDATA": str(sentinel_local),
                "CVSTUDIO_STATE_DIR": str(sentinel_state),
                "CVSTUDIO_DB_PATH": str(sentinel_db),
                "CVSTUDIO_JOB_STATE_PATH": str(sentinel_jobs),
            }
            smoke_root = root / "isolated-smoke"
            with mock.patch.dict(os.environ, seeded, clear=False):
                environment = protected_smoke_environment(smoke_root)
            for name in (
                "HOME",
                "LOCALAPPDATA",
                "CVSTUDIO_STATE_DIR",
                "CVSTUDIO_DB_PATH",
                "CVSTUDIO_JOB_STATE_PATH",
            ):
                self.assertTrue(
                    Path(environment[name]).resolve().is_relative_to(
                        smoke_root.resolve()
                    ),
                    name,
                )
            with mock.patch.dict(
                os.environ,
                environment,
                clear=True,
            ):
                database_path = default_database_path()
                jobs_path = default_job_state_path()
                storage = CVStudioStorage()
                storage.initialize()
                job_store = PersistentJobStore()
                job_store.initialize()
                receipt, prior = write_test_receipt(ROOT, environment)
            self.assertIsNone(prior)
            for path in (database_path, jobs_path, receipt_path(environment)):
                self.assertTrue(
                    path.resolve().is_relative_to(smoke_root.resolve())
                )
            self.assertTrue(database_path.exists())
            self.assertEqual(sentinel_db.read_bytes(), b"owner-database")
            self.assertEqual(sentinel_jobs.read_bytes(), b"owner-journal")
            for directory in (
                sentinel_home,
                sentinel_local,
                sentinel_state,
            ):
                self.assertEqual(
                    (directory / "sentinel.txt").read_bytes(),
                    b"owner-state",
                )

    def test_pinned_windows_runtime_is_complete_trusted_and_functional(self):
        if os.name != "nt":
            self.skipTest("Genuine Windows Antiword execution is Windows-only")
        with tempfile.TemporaryDirectory(
            prefix="cvstudio-antiword-source-state-"
        ) as state:
            ambient_home = Path(state) / "ambient-home"
            ambient_resources = ambient_home / ".antiword"
            ambient_resources.mkdir(parents=True)
            (ambient_resources / "UTF-8.txt").write_text(
                "untrusted mapping",
                encoding="utf-8",
            )
            (ambient_resources / "fontnames").write_text(
                "untrusted font mapping",
                encoding="utf-8",
            )
            with mock.patch.dict(
                os.environ,
                {
                    "LOCALAPPDATA": state,
                    "HOME": str(ambient_home),
                    "ANTIWORDHOME": str(ambient_resources),
                },
                clear=False,
            ):
                health = antiword.antiword_health(ROOT)
                executable = Path(
                    antiword.require_verified_antiword(ROOT)
                )
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
        self.assertEqual(
            sha256(executable),
            "2cbab2831854ccd5141ea328824a77cb889586db2e97129873d543a52cf3e15c",
        )

    def test_package_only_smoke_rejects_ambient_managed_fallback(self):
        if os.name != "nt":
            self.skipTest("Windows package-only runtime fixture is Windows-only")
        with tempfile.TemporaryDirectory(
            prefix="cvstudio-antiword-package-only-"
        ) as td:
            root = Path(td)
            local_state = root / "ambient-state"
            managed = (
                local_state
                / "TheGuoLab"
                / "CVStudio"
                / "dependencies"
                / "antiword"
                / antiword.ANTIWORD_PACKAGE_VERSION
                / "windows-x64"
            )
            shutil.copytree(VENDOR / "windows-x64", managed)
            shutil.copytree(VENDOR / "fixtures", managed / "fixtures")

            package = root / "package"
            runtime = package / "runtime" / "native"
            packaged_vendor = runtime / "vendor" / "antiword"
            shutil.copytree(VENDOR, packaged_vendor)
            environment = {
                "LOCALAPPDATA": str(local_state),
                "CVSTUDIO_ANTIWORD_PACKAGE_ONLY": "1",
            }
            receipt, prior = write_test_receipt(
                package,
                environment,
            )
            self.assertIsNone(prior)
            self.assertTrue(
                receipt.is_relative_to(local_state)
            )
            receipt.unlink()
            with mock.patch.dict(
                os.environ,
                environment,
                clear=False,
            ):
                bundled = antiword.antiword_health(package, runtime)
            self.assertTrue(bundled["available"])
            self.assertEqual(bundled["source"], "bundled")
            packaged_health = validate_antiword_runtime(
                ROOT,
                "windows-x64",
                packaged_vendor,
            )
            self.assertEqual(packaged_health["source"], "bundled")

            mapping = (
                packaged_vendor
                / "windows-x64"
                / "share"
                / "antiword"
                / "UTF-8.txt"
            )
            mapping.write_bytes(mapping.read_bytes() + b"\ncorrupt")
            with mock.patch.dict(
                os.environ,
                environment,
                clear=False,
            ):
                package_only = antiword.antiword_health(package, runtime)
            self.assertFalse(package_only["available"])
            self.assertEqual(
                package_only["reason"],
                "runtime-integrity-failed",
            )
            with self.assertRaises(RuntimeError):
                validate_antiword_runtime(
                    ROOT,
                    "windows-x64",
                    packaged_vendor,
                )

            with mock.patch.dict(
                os.environ,
                {
                    "LOCALAPPDATA": str(local_state),
                    "CVSTUDIO_ANTIWORD_PACKAGE_ONLY": "0",
                },
                clear=False,
            ):
                ambient = antiword.antiword_health(package, runtime)
            self.assertTrue(ambient["available"])
            self.assertEqual(ambient["source"], "managed")

        builder = (
            ROOT / "owner_build_tools" / "build_protected.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            'env["CVSTUDIO_ANTIWORD_PACKAGE_ONLY"]="1"',
            builder,
        )
        self.assertIn(
            'dependency.get("source")=="bundled"',
            builder,
        )
        self.assertIn(
            'native / "vendor" / "antiword"',
            builder,
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

    def test_macos_payloads_are_deferred_and_not_shipped(self):
        for relative in (
            "macos-x86_64",
            "macos-arm64",
            "packages/antiword_1.3.5_macos_x86_64_r46.tgz",
            "packages/antiword_1.3.5_macos_arm64_r46.tgz",
        ):
            self.assertFalse((VENDOR / relative).exists(), relative)
        self.assertEqual(set(antiword._PLATFORMS), {"windows-x64"})
        self.assertEqual(
            set(antiword.ANTIWORD_DISTRIBUTION_HASHES),
            {
                "packages/antiword_1.3.5_windows_x64_r46.zip",
                "source/antiword_1.3.5.tar.gz",
                "GPL-2.0.txt",
                "fixtures/UDHR-english.doc",
            },
        )

    def test_linux_proof_target_statically_verifies_but_never_claims_support(self):
        health = validate_antiword_runtime(ROOT, "linux-x64-test")
        self.assertFalse(health["available"])
        self.assertTrue(health["trusted"])
        self.assertFalse(health["functional"])
        self.assertTrue(health["test_only"])
        self.assertEqual(health["static_platform_manifests_verified"], 1)

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
        self.assertEqual(
            {
                relative: sha256(VENDOR / "windows-x64" / relative)
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
        self.assertNotIn(
            "ANTIWORDHOME",
            run.call_args.kwargs["env"],
        )
        self.assertEqual(
            Path(run.call_args.kwargs["env"]["HOME"]),
            executable.parent.resolve(),
        )

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
        self.assertIn(
            "if ($ok -and -not (Check-Antiword)) { $ok = $false }",
            windows,
        )
        self.assertIn("Test-AntiwordRuntime", windows)
        self.assertIn("Invoke-AntiwordFunctionalCheck", windows)
        self.assertIn(
            "$startInfo.EnvironmentVariables['HOME'] = Split-Path -Parent $Executable",
            windows,
        )
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

    def test_windows_installer_rejects_nested_runtime_junction(self):
        if os.name != "nt":
            self.skipTest("Windows junction validation is Windows-only")
        state = Path(tempfile.gettempdir()) / (
            "cvstudio-antiword-installer-self-test-"
            + os.urandom(8).hex()
        )
        ambient_home = Path(tempfile.gettempdir()) / (
            "cvstudio-antiword-ambient-home-"
            + os.urandom(8).hex()
        )
        try:
            ambient_resources = ambient_home / ".antiword"
            ambient_resources.mkdir(parents=True)
            (ambient_resources / "UTF-8.txt").write_text(
                "untrusted mapping",
                encoding="utf-8",
            )
            (ambient_resources / "fontnames").write_text(
                "untrusted font mapping",
                encoding="utf-8",
            )
            environment = os.environ.copy()
            environment["HOME"] = str(ambient_home)
            environment["ANTIWORDHOME"] = str(ambient_resources)
            result = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(ROOT / "INSTALL_CORE.ps1"),
                    "-AntiwordSelfTestOnly",
                    "-AntiwordSelfTestStateRoot",
                    str(state),
                ],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
            )
        finally:
            if state.exists():
                shutil.rmtree(state)
            if ambient_home.exists():
                shutil.rmtree(ambient_home)
        self.assertEqual(
            result.returncode,
            0,
            (result.stdout or "") + (result.stderr or ""),
        )
        self.assertIn("nested reparse rejection", result.stdout)

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
        self.assertIn(
            '/diagnostics/runtime" -f $port) -Headers $headers -Method Get -TimeoutSec 15',
            windows,
        )

    def test_macos_production_files_are_exact_v239_baseline_and_v240_builds_blocked(self):
        expected_hashes = {
            "install.sh":
                "1e28c62ab82692dc0388024cbe5fe5da32d59ec04ecec6e95f5b06d17ea7b47d",
            "start.sh":
                "9a74ebe8153df059c7d210bcf1fc8cd4dd0e74a6a8ee790066559ad468ee195e",
            "restore_previous.sh":
                "fcda709bd9b5c14c608e770b284320d7cb8439ad71d8c705fda2a9efb9acd217",
            "owner_build_tools/BUILD_PROTECTED_MAC.command":
                "e7079c8067d8133e86ef8cad22211b26a22caad2d325dd3614a9bcffd865c432",
        }
        self.assertEqual(
            {relative: sha256(ROOT / relative) for relative in expected_hashes},
            expected_hashes,
        )
        workflow = (
            ROOT / ".github" / "workflows" / "build-protected.yml"
        ).read_text(encoding="utf-8")
        self.assertNotIn("macos-arm64", workflow)
        self.assertNotIn("macos-intel", workflow)
        with mock.patch.object(
            protected_build.platform, "system", return_value="Darwin"
        ), mock.patch.object(
            protected_build.platform, "machine", return_value="arm64"
        ):
            with self.assertRaisesRegex(RuntimeError, "Windows-x64-only"):
                protected_build.detect_target("auto")
        for target in ("macos-arm64", "macos-intel"):
            with self.assertRaisesRegex(RuntimeError, "only a Windows-x64"):
                protected_build.validate_target_host(target)


if __name__ == "__main__":
    unittest.main()
