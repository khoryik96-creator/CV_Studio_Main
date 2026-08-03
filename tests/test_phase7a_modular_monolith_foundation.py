import ast
import os
from pathlib import Path
import tempfile
import unittest

from cvstudio_architecture import (
    ARCHITECTURE_EXTENSION_KEY,
    DEFAULT_MAX_CONTENT_LENGTH,
    DEFAULT_MODULES,
    ArchitectureContractError,
    ArchitectureState,
    ModuleDefinition,
    ModuleRegistry,
    create_modular_monolith_app,
    finalize_modular_monolith_app,
    route_contract_sha256,
)
from owner_build_tools.build_protected import write_test_receipt


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_ROUTE_CONTRACT_SHA256 = (
    "f8378b6f3424476eb0683af8e0bbb06ed430675abfe11b74ebed5ab361a20bc9"
)
EXPECTED_GUARDS = (
    "_assign_cvstudio_request_id",
    "_reject_declared_oversize_request",
    "_reject_non_local_host_header",
    "_require_ai_spend_browser_session",
    "_reject_cross_site_unsafe_request",
)


_MODULE_TEMPORARY = tempfile.TemporaryDirectory(
    prefix="cvstudio-phase7a-foundation-"
)
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


class Phase7AModularMonolithFoundationTests(unittest.TestCase):
    def test_current_module_graph_is_explicit_unique_and_acyclic(self):
        registry = ModuleRegistry(DEFAULT_MODULES)
        self.assertEqual(
            registry.names,
            (
                "composition_root",
                "platform_dependencies",
                "storage",
                "background_jobs",
                "ai_costs",
                "external_clients",
                "documents",
                "diagnostics",
                "startup",
                "runtime",
                "web_assets",
                "secrets",
                "jobadder_read",
                "jobadder_write",
                "onenote_text",
                "outlook_crypto",
                "cv_normalize",
                "lead_match",
                "spider_boolean",
                "storage_http",
                "legacy_web_shell",
            ),
        )
        ownership = {}
        for module in registry.modules:
            for source_file in module.source_files:
                self.assertTrue((ROOT / source_file).is_file(), source_file)
                self.assertNotIn(source_file, ownership)
                ownership[source_file] = module.name
        self.assertEqual(ownership["app.py"], "legacy_web_shell")
        self.assertEqual(
            ownership["cvstudio_architecture.py"], "composition_root"
        )
        self.assertEqual(ownership["cvstudio_storage.py"], "storage")

    def test_invalid_module_graphs_fail_before_application_construction(self):
        with self.assertRaisesRegex(ArchitectureContractError, "unknown"):
            ModuleRegistry(
                (
                    ModuleDefinition(
                        "web", "interface", ("web.py",), ("missing",)
                    ),
                )
            )
        with self.assertRaisesRegex(ArchitectureContractError, "cycle"):
            ModuleRegistry(
                (
                    ModuleDefinition("one", "domain", ("one.py",), ("two",)),
                    ModuleDefinition("two", "domain", ("two.py",), ("one",)),
                )
            )
        with self.assertRaisesRegex(ArchitectureContractError, "owned by both"):
            ModuleRegistry(
                (
                    ModuleDefinition("one", "domain", ("shared.py",)),
                    ModuleDefinition("two", "domain", ("shared.py",)),
                )
            )

    def test_composition_root_constructs_an_independent_flask_application(self):
        isolated = create_modular_monolith_app(
            "phase7a-fixture",
            static_folder=None,
            config={"TESTING": True},
        )
        self.assertTrue(isolated.testing)
        self.assertEqual(
            isolated.config["MAX_CONTENT_LENGTH"], DEFAULT_MAX_CONTENT_LENGTH
        )
        state = isolated.extensions[ARCHITECTURE_EXTENSION_KEY]
        self.assertIsInstance(state, ArchitectureState)
        self.assertFalse(state.finalized)
        self.assertEqual(state.registry.names[-1], "legacy_web_shell")

    def test_live_application_is_sealed_to_the_exact_baseline_contract(self):
        state = app.app.extensions[ARCHITECTURE_EXTENSION_KEY]
        self.assertIs(state, app._CVSTUDIO_ARCHITECTURE)
        self.assertTrue(state.finalized)
        self.assertEqual(state.route_count, 108)
        self.assertEqual(
            state.route_contract_sha256, EXPECTED_ROUTE_CONTRACT_SHA256
        )
        self.assertEqual(
            route_contract_sha256(app.app), EXPECTED_ROUTE_CONTRACT_SHA256
        )
        self.assertEqual(state.before_request_handlers, EXPECTED_GUARDS)
        self.assertEqual(
            app.app.config["MAX_CONTENT_LENGTH"], DEFAULT_MAX_CONTENT_LENGTH
        )

    def test_contract_drift_is_failure_visible(self):
        isolated = create_modular_monolith_app(
            "phase7a-contract-drift", static_folder=None
        )

        @isolated.get("/fixture")
        def fixture():
            return "ok"

        with self.assertRaisesRegex(ArchitectureContractError, "route count"):
            finalize_modular_monolith_app(
                isolated,
                expected_route_count=0,
                expected_route_contract_sha256="not-used",
                expected_before_request_handlers=(),
            )
        with self.assertRaisesRegex(ArchitectureContractError, "URL/method"):
            finalize_modular_monolith_app(
                isolated,
                expected_route_count=1,
                expected_route_contract_sha256="wrong",
                expected_before_request_handlers=(),
            )

    def test_extracted_backend_modules_do_not_import_the_legacy_web_shell(self):
        for module in DEFAULT_MODULES:
            if module.name == "legacy_web_shell":
                continue
            for source_file in module.source_files:
                tree = ast.parse(
                    (ROOT / source_file).read_text(encoding="utf-8-sig"),
                    filename=source_file,
                )
                imported = set()
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        imported.update(alias.name for alias in node.names)
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        imported.add(node.module)
                self.assertNotIn("app", imported, source_file)


if __name__ == "__main__":
    unittest.main()
