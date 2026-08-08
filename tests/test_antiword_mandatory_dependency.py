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


class FakeAntiwordProcess:
    def __init__(self, outcome):
        self.outcome = outcome
        self.returncode = 0
        self.killed = False
        self.timeouts = []

    def communicate(self, timeout=None):
        self.timeouts.append(timeout)
        if self.killed:
            return b"", b""
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome

    def kill(self):
        self.killed = True
        self.returncode = -9


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
            "packages/antiword_1.3.5_macos_x86_64_r46.tgz":
                "0416f1389dc01398cb820ec014e976a5c2198bb103a725f290efce1598f0fced",
            "packages/antiword_1.3.5_macos_arm64_r46.tgz":
                "1536939cca2c1b9cfcab7721c8982933bf8093eda0460f0e38055e7c826eae9a",
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

    def test_macos_payloads_are_pinned_and_native_specific(self):
        self.assertEqual(set(antiword._PLATFORMS), {"windows-x64", "macos-intel", "macos-arm64"})
        for tag, executable_hash in {
            "macos-intel": "afeec28ba1bc3f89e9552f26402312c84d072b91f301200710f113afed36dea7",
            "macos-arm64": "dd4be2c485c589cd4ac8495c9de77510b7496d2acc44deadebab80ec88d6769d",
        }.items():
            self.assertEqual(sha256(VENDOR / tag / "bin" / "antiword"), executable_hash)
            runtime_files = [
                path
                for folder in ("bin", "share")
                for path in (VENDOR / tag / folder).rglob("*")
                if path.is_file()
            ]
            self.assertEqual(len(runtime_files), antiword.ANTIWORD_RUNTIME_FILE_COUNT)

    def test_native_macos_runtime_is_trusted_and_functional(self):
        if __import__("platform").system().lower() != "darwin":
            self.skipTest("Genuine macOS Antiword execution is macOS-only")
        health = antiword.antiword_health(ROOT)
        self.assertTrue(health["available"])
        self.assertTrue(health["trusted"])
        self.assertTrue(health["functional"])
        self.assertIn(health["platform"], {"macos-intel", "macos-arm64"})

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
        with tempfile.TemporaryDirectory(
            prefix="cvstudio-antiword-timeout-"
        ) as td:
            package = Path(td)
            copied_vendor = package / "vendor" / "antiword"
            shutil.copytree(VENDOR, copied_vendor)
            executable = (
                copied_vendor
                / "windows-x64"
                / "bin"
                / "antiword.exe"
            )
            mapping = (
                copied_vendor
                / "windows-x64"
                / "share"
                / "antiword"
                / "UTF-8.txt"
            )
            timed_out = FakeAntiwordProcess(
                subprocess.TimeoutExpired("antiword", 12)
            )
            with mock.patch.dict(
                os.environ,
                {
                    "LOCALAPPDATA": str(package / "empty-state"),
                    "CVSTUDIO_ANTIWORD_PACKAGE_ONLY": "1",
                },
                clear=False,
            ), mock.patch.object(
                antiword.subprocess,
                "Popen",
                return_value=timed_out,
            ) as popen:
                health = antiword.antiword_health(package)
            self.assertFalse(health["available"])
            self.assertEqual(
                health["reason"], "functional-execution-timeout"
            )
            for protected_path in (executable, mapping):
                with protected_path.open("r+b"):
                    pass
                moved = protected_path.with_name(
                    protected_path.name + ".released"
                )
                protected_path.rename(moved)
                moved.rename(protected_path)
        self.assertEqual(timed_out.timeouts, [12, None])
        self.assertTrue(timed_out.killed)
        self.assertEqual(
            popen.call_args.kwargs["stdout"],
            subprocess.PIPE,
        )
        self.assertEqual(
            popen.call_args.kwargs["stderr"],
            subprocess.PIPE,
        )
        self.assertNotIn(
            "ANTIWORDHOME",
            popen.call_args.kwargs["env"],
        )
        self.assertEqual(
            Path(popen.call_args.kwargs["env"]["HOME"]),
            executable.resolve(),
        )

    def test_verified_execution_blocks_runtime_substitution_until_exit(self):
        if os.name != "nt":
            self.skipTest("Windows sharing enforcement is Windows-only")
        with tempfile.TemporaryDirectory(
            prefix="cvstudio-antiword-locked-execution-"
        ) as td:
            package = Path(td)
            copied_vendor = package / "vendor" / "antiword"
            shutil.copytree(VENDOR, copied_vendor)
            runtime = copied_vendor / "windows-x64"
            executable = runtime / "bin" / "antiword.exe"
            mapping = runtime / "share" / "antiword" / "UTF-8.txt"
            fixture = copied_vendor / "fixtures" / "UDHR-english.doc"
            replacements = package / "replacement-attempts"
            replacements.mkdir()
            exe_replacement = replacements / "antiword.exe"
            mapping_replacement = replacements / "UTF-8.txt"
            shutil.copy2(executable, exe_replacement)
            shutil.copy2(mapping, mapping_replacement)
            original_popen = subprocess.Popen
            attempts = []

            def assert_locked(target, replacement):
                for operation in (
                    lambda: target.write_bytes(target.read_bytes()),
                    target.unlink,
                    lambda: target.rename(
                        target.with_name(target.name + ".renamed")
                    ),
                    lambda: os.replace(replacement, target),
                ):
                    with self.assertRaises(OSError):
                        operation()
                    attempts.append(target)

            def attempt_replacement_then_start(*args, **kwargs):
                assert_locked(executable, exe_replacement)
                assert_locked(mapping, mapping_replacement)
                return original_popen(*args, **kwargs)

            environment = {
                "LOCALAPPDATA": str(package / "empty-state"),
                "CVSTUDIO_ANTIWORD_PACKAGE_ONLY": "1",
            }
            with mock.patch.dict(
                os.environ, environment, clear=False
            ), mock.patch.object(
                antiword.subprocess,
                "Popen",
                side_effect=attempt_replacement_then_start,
            ) as popen:
                result = antiword.run_verified_antiword(
                    package,
                    (fixture,),
                    timeout=20,
                )
            self.assertEqual(result.returncode, 0)
            self.assertEqual(popen.call_count, 2)
            self.assertEqual(len(attempts), 16)
            for call in popen.call_args_list:
                self.assertEqual(
                    Path(call.kwargs["env"]["HOME"]),
                    executable.resolve(),
                )

            for protected_path in (executable, mapping):
                with protected_path.open("r+b"):
                    pass
                moved = protected_path.with_name(
                    protected_path.name + ".released"
                )
                protected_path.rename(moved)
                moved.rename(protected_path)
            post_replacement = replacements / "post-execution.exe"
            shutil.copy2(executable, post_replacement)
            os.replace(post_replacement, executable)
            with mock.patch.dict(
                os.environ, environment, clear=False
            ):
                self.assertTrue(
                    antiword.antiword_health(package)["functional"]
                )

    def test_public_fixture_markers_cannot_bypass_executable_identity(self):
        if os.name != "nt":
            self.skipTest("Windows runtime identity is Windows-only")
        with tempfile.TemporaryDirectory(
            prefix="cvstudio-antiword-marker-spoof-"
        ) as td:
            package = Path(td)
            copied_vendor = package / "vendor" / "antiword"
            shutil.copytree(VENDOR, copied_vendor)
            executable = (
                copied_vendor
                / "windows-x64"
                / "bin"
                / "antiword.exe"
            )
            executable.write_bytes(b"malicious executable")
            marker_output = "\n".join(antiword._FUNCTIONAL_MARKERS).encode()
            with mock.patch.dict(
                os.environ,
                {
                    "LOCALAPPDATA": str(package / "empty-state"),
                    "CVSTUDIO_ANTIWORD_PACKAGE_ONLY": "1",
                },
                clear=False,
            ), mock.patch.object(
                antiword.subprocess,
                "Popen",
                return_value=FakeAntiwordProcess((marker_output, b"")),
            ) as popen:
                health = antiword.antiword_health(package)
            self.assertFalse(health["trusted"])
            self.assertFalse(health["functional"])
            self.assertEqual(health["reason"], "runtime-integrity-failed")
            popen.assert_not_called()

    def test_actual_execution_abort_paths_release_runtime_locks(self):
        if os.name != "nt":
            self.skipTest("Windows sharing enforcement is Windows-only")
        marker_output = "\n".join(antiword._FUNCTIONAL_MARKERS).encode()
        for label, failure in (
            (
                "timeout",
                subprocess.TimeoutExpired("antiword", 20),
            ),
            ("failure", OSError("process start failed")),
            ("cancellation", KeyboardInterrupt()),
        ):
            with self.subTest(label=label), tempfile.TemporaryDirectory(
                prefix=f"cvstudio-antiword-{label}-release-"
            ) as td:
                package = Path(td)
                copied_vendor = package / "vendor" / "antiword"
                shutil.copytree(VENDOR, copied_vendor)
                runtime = copied_vendor / "windows-x64"
                executable = runtime / "bin" / "antiword.exe"
                mapping = runtime / "share" / "antiword" / "UTF-8.txt"
                successful_functional = FakeAntiwordProcess(
                    (marker_output, b"")
                )
                aborted_process = (
                    failure
                    if isinstance(failure, OSError)
                    else FakeAntiwordProcess(failure)
                )
                with mock.patch.dict(
                    os.environ,
                    {
                        "LOCALAPPDATA": str(package / "empty-state"),
                        "CVSTUDIO_ANTIWORD_PACKAGE_ONLY": "1",
                    },
                    clear=False,
                ), mock.patch.object(
                    antiword.subprocess,
                    "Popen",
                    side_effect=[
                        successful_functional,
                        aborted_process,
                    ],
                ):
                    with self.assertRaises(type(failure)):
                        antiword.run_verified_antiword(
                            package,
                            (copied_vendor / "fixtures" / "UDHR-english.doc",),
                            timeout=20,
                        )
                if isinstance(aborted_process, FakeAntiwordProcess):
                    self.assertTrue(aborted_process.killed)
                    self.assertEqual(
                        aborted_process.timeouts,
                        [20, None],
                    )
                for protected_path in (executable, mapping):
                    with protected_path.open("r+b"):
                        pass
                    moved = protected_path.with_name(
                        protected_path.name + ".released"
                    )
                    protected_path.rename(moved)
                    moved.rename(protected_path)

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
            "$startInfo.EnvironmentVariables['HOME'] = $Executable",
            windows,
        )
        self.assertIn("[CVStudioAntiwordRuntimeLock]::Open", windows)
        self.assertIn("FILE_SHARE_READ", windows)
        self.assertIn("FILE_FLAG_OPEN_REPARSE_POINT", windows)
        self.assertIn("WaitForExit($TimeoutMilliseconds)", windows)
        self.assertIn("[int]$TimeoutMilliseconds = 12000", windows)
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
        self.assertIn("Assert-AntiwordPathProtected", windows)
        self.assertIn("Assert-AntiwordPathReleased", windows)
        self.assertIn("$lockHandles[$index].Dispose()", windows)
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
        self.assertIn("blocked replacement", result.stdout)
        self.assertIn("released timeout/failure locks", result.stdout)

    def test_native_parser_alone_cannot_satisfy_success_but_validated_docx_conversion_can(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("def _extract_word_binary_piece_table", source)
        self.assertIn(
            "if not (_verified_antiword_text or legacy_doc_converter):\n"
            "                raise AntiwordDependencyError(",
            source,
        )
        route_start = source.index("elif filename.endswith('.doc')")
        self.assertLess(
            source.index("_require_verified_antiword()", route_start),
            source.index("_convert_legacy_doc_to_docx_bytes(file_bytes)", route_start),
        )
        self.assertEqual(source.count("_run_verified_antiword("), 3)
        self.assertNotIn("_sp.run([antiword, doc_path]", source)
        self.assertNotIn("_sp2.run(", source)
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

    def test_macos_build_targets_require_matching_native_hosts(self):
        workflow = (
            ROOT / ".github" / "workflows" / "build-protected.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("macos-arm64", workflow)
        self.assertIn("macos-intel", workflow)
        with mock.patch.object(
            protected_build.platform, "system", return_value="Darwin"
        ), mock.patch.object(
            protected_build.platform, "machine", return_value="arm64"
        ):
            self.assertEqual(protected_build.detect_target("auto"), "macos-arm64")
            protected_build.validate_target_host("macos-arm64")
            with self.assertRaisesRegex(RuntimeError, "Intel"):
                protected_build.validate_target_host("macos-intel")


if __name__ == "__main__":
    unittest.main()
