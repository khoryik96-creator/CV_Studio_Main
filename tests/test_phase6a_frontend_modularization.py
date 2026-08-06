import inspect
import os
from pathlib import Path
import sys
import tempfile
import unittest

from owner_build_tools import build_protected


_MODULE_TEMPORARY = None
if "app" in sys.modules:
    import app
else:
    _MODULE_TEMPORARY = tempfile.TemporaryDirectory(
        prefix="cvstudio-phase6a-app-"
    )
    _temporary_root = Path(_MODULE_TEMPORARY.name)
    _original_database_override = os.environ.get("CVSTUDIO_DB_PATH")
    _original_local_state = os.environ.get("LOCALAPPDATA")
    os.environ["CVSTUDIO_DB_PATH"] = str(
        _temporary_root / "state" / "cv_studio.sqlite3"
    )
    os.environ["LOCALAPPDATA"] = str(_temporary_root / "local-state")
    build_protected.write_test_receipt(Path(__file__).resolve().parents[1])
    try:
        import app
    finally:
        if _original_database_override is None:
            os.environ.pop("CVSTUDIO_DB_PATH", None)
        else:
            os.environ["CVSTUDIO_DB_PATH"] = _original_database_override
        if _original_local_state is None:
            os.environ.pop("LOCALAPPDATA", None)
        else:
            os.environ["LOCALAPPDATA"] = _original_local_state


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_MODULES = (
    "lazy-loader.js",
    "api-transport.js",
    "page-nav.js",
    "server-heartbeat.js",
)


class Phase6AFrontendModularizationTests(unittest.TestCase):
    def test_existing_route_and_vendor_asset_boundary(self):
        rules = list(app.app.url_map.iter_rules())
        self.assertEqual(len(rules), 116)
        vendor_rules = [rule for rule in rules if rule.rule == "/vendor/<path:filename>"]
        self.assertEqual(len(vendor_rules), 1)
        self.assertEqual(vendor_rules[0].methods - {"HEAD", "OPTIONS"}, {"GET"})

        module_root = ROOT / "vendor" / "cvstudio"
        if not module_root.is_dir():
            return
        client = app.app.test_client()
        present_modules = tuple(
            filename
            for filename in FRONTEND_MODULES
            if (module_root / filename).is_file()
        )
        self.assertEqual(
            present_modules,
            FRONTEND_MODULES[: len(present_modules)],
        )
        for filename in present_modules:
            response = client.get("/vendor/cvstudio/" + filename)
            try:
                self.assertEqual(response.status_code, 200, filename)
                self.assertGreater(len(response.data), 100, filename)
                self.assertIn(b"function", response.data, filename)
            finally:
                response.close()
        rejected = client.get("/vendor/../app.py")
        try:
            self.assertEqual(rejected.status_code, 404)
        finally:
            rejected.close()

    def test_owner_protection_and_package_asset_seam(self):
        module_root = ROOT / "vendor" / "cvstudio"
        if not all((module_root / filename).is_file() for filename in FRONTEND_MODULES):
            return

        self.assertEqual(build_protected.FRONTEND_MODULES, FRONTEND_MODULES)
        build_protected.validate_source(ROOT)
        with tempfile.TemporaryDirectory(prefix="cvstudio-phase6a-protection-") as temporary:
            result = build_protected.protect_javascript(
                ROOT, Path(temporary), True
            )
            self.assertEqual(len(result), 4)
            protected_index, protected_generate, protected_modules, report = result
            self.assertTrue(protected_index.is_file())
            self.assertTrue(protected_generate.is_file())
            self.assertEqual(
                sorted(path.name for path in protected_modules.iterdir()),
                sorted(FRONTEND_MODULES),
            )
            self.assertEqual(
                sorted(report["frontend_modules"]["source_sha256"]),
                sorted(FRONTEND_MODULES),
            )
            self.assertEqual(
                sorted(report["frontend_modules"]["protected_sha256"]),
                sorted(FRONTEND_MODULES),
            )

        build_package_source = inspect.getsource(build_protected.build_package)
        self.assertIn("protected_modules", build_package_source)
        self.assertIn("vendor/cvstudio", inspect.getsource(build_protected.smoke_test))

        # The protected build must bundle the salary_comparison package data
        # (seed JSON, Jinja templates, static assets); Nuitka standalone omits
        # package data unless explicitly included, and their absence 500s the
        # module at runtime.
        compile_source = inspect.getsource(build_protected.compile_native)
        self.assertIn("--include-package-data=salary_comparison", compile_source)


def tearDownModule():
    if _MODULE_TEMPORARY is not None:
        _MODULE_TEMPORARY.cleanup()


if __name__ == "__main__":
    unittest.main()
