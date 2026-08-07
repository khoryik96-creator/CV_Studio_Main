"""CV Studio modular-monolith composition and architecture contracts.

This module is deliberately independent of ``app.py``.  It owns application
construction and the explicit inventory of the current backend modules while
the legacy web shell continues to register its established routes in place.
Future extractions can move one bounded domain at a time without changing the
process, deployment unit, route surface, or shared SQLite authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import PurePosixPath
from typing import Iterable, Mapping, Sequence

from flask import Flask


ARCHITECTURE_EXTENSION_KEY = "cvstudio_modular_monolith"
DEFAULT_MAX_CONTENT_LENGTH = 80 * 1024 * 1024


class ArchitectureContractError(RuntimeError):
    """Raised when the declared module graph or Flask contract drifts."""


@dataclass(frozen=True)
class ModuleDefinition:
    """One current modular-monolith boundary and its allowed dependencies."""

    name: str
    layer: str
    source_files: tuple[str, ...]
    dependencies: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "layer": self.layer,
            "source_files": list(self.source_files),
            "dependencies": list(self.dependencies),
        }


DEFAULT_MODULES = (
    ModuleDefinition(
        "composition_root",
        "foundation",
        ("cvstudio_architecture.py",),
    ),
    ModuleDefinition(
        "platform_dependencies",
        "foundation",
        ("cvstudio_antiword.py", "cvstudio_tesseract.py"),
    ),
    ModuleDefinition(
        "storage",
        "foundation",
        ("cvstudio_storage.py",),
    ),
    ModuleDefinition(
        "background_jobs",
        "foundation",
        ("cvstudio_jobs.py",),
    ),
    ModuleDefinition(
        "ai_costs",
        "domain",
        ("cvstudio_ai_costs.py",),
    ),
    ModuleDefinition(
        "external_clients",
        "domain",
        ("cvstudio_clients.py",),
    ),
    ModuleDefinition(
        "documents",
        "domain",
        ("cvstudio_document_safety.py",),
        ("platform_dependencies",),
    ),
    ModuleDefinition(
        "diagnostics",
        "domain",
        ("cvstudio_diagnostics.py",),
        ("platform_dependencies", "storage"),
    ),
    ModuleDefinition(
        "startup",
        "domain",
        ("cvstudio_startup.py",),
    ),
    ModuleDefinition(
        "runtime",
        "domain",
        ("cvstudio_runtime.py",),
    ),
    ModuleDefinition(
        "web_assets",
        "domain",
        ("cvstudio_web_assets.py",),
    ),
    ModuleDefinition(
        "secrets",
        "domain",
        ("cvstudio_secrets.py",),
    ),
    ModuleDefinition(
        "jobadder_read",
        "domain",
        ("cvstudio_jobadder_read.py",),
        ("external_clients",),
    ),
    ModuleDefinition(
        "jobadder_write",
        "domain",
        ("cvstudio_jobadder_write.py",),
        ("external_clients",),
    ),
    ModuleDefinition(
        "onenote_text",
        "domain",
        ("cvstudio_onenote_text.py",),
    ),
    ModuleDefinition(
        "outlook_crypto",
        "domain",
        ("cvstudio_outlook_crypto.py",),
    ),
    ModuleDefinition(
        "cv_normalize",
        "domain",
        ("cvstudio_cv_normalize.py",),
    ),
    ModuleDefinition(
        "lead_match",
        "domain",
        ("cvstudio_lead_match.py",),
    ),
    ModuleDefinition(
        "lead_enrich",
        "domain",
        ("cvstudio_lead_enrich.py",),
        ("lead_match",),
    ),
    ModuleDefinition(
        "lead_cache",
        "domain",
        ("cvstudio_lead_cache.py",),
        ("lead_enrich",),
    ),
    ModuleDefinition(
        "lead_search",
        "domain",
        ("cvstudio_lead_search.py",),
        ("lead_enrich",),
    ),
    ModuleDefinition(
        "spider_boolean",
        "domain",
        ("cvstudio_spider_boolean.py",),
    ),
    ModuleDefinition(
        "spider_summary",
        "domain",
        ("cvstudio_spider_summary.py",),
        ("spider_boolean",),
    ),
    ModuleDefinition(
        "spider_score",
        "domain",
        ("cvstudio_spider_score.py",),
        ("spider_boolean",),
    ),
    ModuleDefinition(
        "ja_typos",
        "domain",
        ("cvstudio_ja_typos.py",),
    ),
    ModuleDefinition(
        "salary_parse",
        "domain",
        ("cvstudio_salary_parse.py",),
        ("ja_typos",),
    ),
    ModuleDefinition(
        "ja_answers",
        "domain",
        ("cvstudio_ja_answers.py",),
    ),
    ModuleDefinition(
        "ja_salary_notice",
        "domain",
        ("cvstudio_ja_salary_notice.py",),
        ("salary_parse", "ja_typos"),
    ),
    ModuleDefinition(
        "blind_mask",
        "domain",
        ("cvstudio_blind_mask.py",),
    ),
    ModuleDefinition(
        "ppc",
        "domain",
        ("cvstudio_ppc.py",),
    ),
    ModuleDefinition(
        "msgraph",
        "domain",
        ("cvstudio_msgraph.py",),
    ),
    ModuleDefinition(
        "onenote_desktop",
        "domain",
        ("cvstudio_onenote_desktop.py",),
    ),
    ModuleDefinition(
        "salary_comparison",
        "interface",
        (
            "salary_comparison/__init__.py",
            "salary_comparison/routes.py",
            "salary_comparison/calculator.py",
            "salary_comparison/fx_service.py",
            "salary_comparison/repository.py",
            "salary_comparison/validators.py",
            "salary_comparison/exporter.py",
            "salary_comparison/ai_rule_updater.py",
            "salary_comparison/bootstrap.py",
        ),
    ),
    ModuleDefinition(
        "storage_http",
        "interface",
        ("cvstudio_storage_bridge.py",),
        ("storage",),
    ),
    ModuleDefinition(
        "legacy_web_shell",
        "interface",
        (
            "app.py",
            "index.html",
            "generate.js",
            "vendor/cvstudio/api-transport.js",
            "vendor/cvstudio/lazy-loader.js",
            "vendor/cvstudio/page-nav.js",
            "vendor/cvstudio/server-heartbeat.js",
        ),
        (
            "composition_root",
            "ai_costs",
            "background_jobs",
            "blind_mask",
            "diagnostics",
            "documents",
            "external_clients",
            "jobadder_read",
            "jobadder_write",
            "cv_normalize",
            "lead_match",
            "lead_enrich",
            "lead_cache",
            "lead_search",
            "msgraph",
            "onenote_desktop",
            "onenote_text",
            "outlook_crypto",
            "platform_dependencies",
            "ppc",
            "runtime",
            "salary_comparison",
            "secrets",
            "spider_boolean",
            "spider_summary",
            "spider_score",
            "ja_typos",
            "salary_parse",
            "ja_answers",
            "ja_salary_notice",
            "startup",
            "storage",
            "storage_http",
            "web_assets",
        ),
    ),
)


class ModuleRegistry:
    """Validated immutable inventory of the modules composed into one app."""

    def __init__(self, modules: Iterable[ModuleDefinition]):
        self._modules = tuple(modules)
        self._by_name = self._validate(self._modules)

    @staticmethod
    def _validate(
        modules: tuple[ModuleDefinition, ...],
    ) -> Mapping[str, ModuleDefinition]:
        by_name: dict[str, ModuleDefinition] = {}
        source_owner: dict[str, str] = {}
        allowed_layers = {"foundation", "domain", "interface"}

        for module in modules:
            if not module.name or module.name in by_name:
                raise ArchitectureContractError(
                    "Module names must be non-empty and unique: {!r}".format(
                        module.name
                    )
                )
            if module.layer not in allowed_layers:
                raise ArchitectureContractError(
                    "Module {!r} has an unsupported layer {!r}".format(
                        module.name, module.layer
                    )
                )
            if not module.source_files:
                raise ArchitectureContractError(
                    "Module {!r} has no owned source files".format(module.name)
                )
            by_name[module.name] = module
            for raw_path in module.source_files:
                path = PurePosixPath(str(raw_path).replace("\\", "/"))
                if path.is_absolute() or ".." in path.parts or str(path) in {"", "."}:
                    raise ArchitectureContractError(
                        "Module {!r} owns an invalid source path {!r}".format(
                            module.name, raw_path
                        )
                    )
                normalized = path.as_posix()
                previous = source_owner.get(normalized)
                if previous:
                    raise ArchitectureContractError(
                        "Source file {!r} is owned by both {!r} and {!r}".format(
                            normalized, previous, module.name
                        )
                    )
                source_owner[normalized] = module.name

        for module in modules:
            for dependency in module.dependencies:
                if dependency == module.name:
                    raise ArchitectureContractError(
                        "Module {!r} cannot depend on itself".format(module.name)
                    )
                if dependency not in by_name:
                    raise ArchitectureContractError(
                        "Module {!r} has unknown dependency {!r}".format(
                            module.name, dependency
                        )
                    )

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(name: str) -> None:
            if name in visited:
                return
            if name in visiting:
                raise ArchitectureContractError(
                    "Module dependency cycle includes {!r}".format(name)
                )
            visiting.add(name)
            for dependency in by_name[name].dependencies:
                visit(dependency)
            visiting.remove(name)
            visited.add(name)

        for name in by_name:
            visit(name)
        return by_name

    @property
    def modules(self) -> tuple[ModuleDefinition, ...]:
        return self._modules

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(module.name for module in self._modules)

    def manifest(self) -> tuple[dict[str, object], ...]:
        return tuple(module.as_dict() for module in self._modules)


@dataclass
class ArchitectureState:
    registry: ModuleRegistry
    finalized: bool = False
    route_count: int = 0
    route_contract_sha256: str = ""
    before_request_handlers: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "finalized": self.finalized,
            "route_count": self.route_count,
            "route_contract_sha256": self.route_contract_sha256,
            "before_request_handlers": list(self.before_request_handlers),
            "modules": list(self.registry.manifest()),
        }


def create_modular_monolith_app(
    import_name: str,
    *,
    static_folder: str | None = None,
    config: Mapping[str, object] | None = None,
    modules: Sequence[ModuleDefinition] = DEFAULT_MODULES,
) -> Flask:
    """Create the single Flask process and attach its validated module graph."""

    app = Flask(import_name, static_folder=static_folder)
    app.config["MAX_CONTENT_LENGTH"] = DEFAULT_MAX_CONTENT_LENGTH
    if config:
        app.config.update(dict(config))
    app.extensions[ARCHITECTURE_EXTENSION_KEY] = ArchitectureState(
        ModuleRegistry(modules)
    )
    return app


def _route_contract(app: Flask) -> tuple[dict[str, object], ...]:
    rows = []
    for rule in app.url_map.iter_rules():
        methods = set(rule.methods or ())
        if "GET" in methods:
            methods.discard("HEAD")
        if getattr(rule, "provide_automatic_options", False):
            methods.discard("OPTIONS")
        rows.append(
            {
                "rule": rule.rule,
                "methods": sorted(methods),
                "endpoint": rule.endpoint,
            }
        )
    return tuple(
        sorted(
            rows,
            key=lambda row: (
                str(row["rule"]),
                str(row["endpoint"]),
                tuple(row["methods"]),
            ),
        )
    )


def route_contract_sha256(app: Flask) -> str:
    """Return a deterministic digest of URLs, methods, and endpoint names."""

    payload = json.dumps(
        _route_contract(app),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def finalize_modular_monolith_app(
    app: Flask,
    *,
    expected_route_count: int,
    expected_route_contract_sha256: str,
    expected_before_request_handlers: Sequence[str],
    expected_max_content_length: int = DEFAULT_MAX_CONTENT_LENGTH,
) -> ArchitectureState:
    """Seal the composition only when the preserved Flask contract is exact."""

    state = app.extensions.get(ARCHITECTURE_EXTENSION_KEY)
    if not isinstance(state, ArchitectureState):
        raise ArchitectureContractError(
            "CV Studio application was not created through the composition root"
        )

    route_count = len(tuple(app.url_map.iter_rules()))
    route_digest = route_contract_sha256(app)
    before_handlers = tuple(
        callback.__name__
        for callback in app.before_request_funcs.get(None, ())
    )
    actual_limit = int(app.config.get("MAX_CONTENT_LENGTH") or 0)

    if route_count != int(expected_route_count):
        raise ArchitectureContractError(
            "Flask route count drifted: expected {}, found {}".format(
                expected_route_count, route_count
            )
        )
    if route_digest != str(expected_route_contract_sha256):
        raise ArchitectureContractError(
            "Flask route URL/method/endpoint contract drifted"
        )
    if before_handlers != tuple(expected_before_request_handlers):
        raise ArchitectureContractError(
            "Flask before-request guard order drifted: {!r}".format(
                before_handlers
            )
        )
    if actual_limit != int(expected_max_content_length):
        raise ArchitectureContractError(
            "Flask request-size limit drifted: expected {}, found {}".format(
                expected_max_content_length, actual_limit
            )
        )

    state.finalized = True
    state.route_count = route_count
    state.route_contract_sha256 = route_digest
    state.before_request_handlers = before_handlers
    return state
