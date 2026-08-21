"""Pytest fixtures for the Salary Comparison module inside CV Studio.

Adapted from the module's standalone fixtures: the data directory is resolved
against the vendored ``salary_comparison`` package at the repository root, and
the ``app`` fixture builds a bare Flask app with only this blueprint registered
(via the module's own ``init_app``), so these tests exercise the feature in
isolation from the CV Studio web shell.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def data_dir(tmp_path: Path) -> Path:
    source = _REPO_ROOT / "salary_comparison" / "data"
    target = tmp_path / "data"
    shutil.copytree(source, target)
    return target


@pytest.fixture()
def malaysia_rule(data_dir: Path):
    data = json.loads((data_dir / "tax_rules.json").read_text(encoding="utf-8"))
    return next(
        rule for rule in data["rules"]
        if rule["country"] == "Malaysia" and rule["residency"] == "Resident"
    )


@pytest.fixture()
def malaysia_nonresident_rule(data_dir: Path):
    data = json.loads((data_dir / "tax_rules.json").read_text(encoding="utf-8"))
    return next(
        rule for rule in data["rules"]
        if rule["country"] == "Malaysia" and rule["residency"] == "Non-Resident"
    )


@pytest.fixture()
def app(data_dir: Path):
    if importlib.util.find_spec("flask") is None:
        pytest.skip("Flask is not installed in this offline test container.")
    from flask import Flask

    import salary_comparison

    application = Flask(__name__)
    application.config.update(
        TESTING=True,
        SALARY_COMPARISON_DATA_DIR=str(data_dir),
    )
    salary_comparison.init_app(application, url_prefix="/salary-comparison")
    return application


@pytest.fixture()
def client(app):
    return app.test_client()
