import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import shutil
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from owner_build_tools.build_protected import VERSION, write_test_receipt


def choose_port():
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])
    finally:
        probe.close()


def request_json(base, path, *, method="GET", payload=None, request_id="phase2a-source-smoke"):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"X-CV-Studio-Request-ID": request_id}
    if data is not None:
        headers.update({"Content-Type": "application/json", "X-CV-Studio-Request": "1"})
    request = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, dict(response.headers), json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), json.loads(error.read())


def main():
    checks = 0

    def check(condition, message):
        nonlocal checks
        if not condition:
            raise AssertionError(message)
        checks += 1

    timing_path = ROOT / "startup_timing.log"
    timing_existed = timing_path.exists()
    timing_bytes = timing_path.read_bytes() if timing_existed else None
    original_local_state = os.environ.get("LOCALAPPDATA")
    original_database_override = os.environ.get("CVSTUDIO_DB_PATH")
    process = None
    output = None
    state_root = None

    try:
        with tempfile.TemporaryDirectory(
            prefix="cvstudio-source-smoke-",
            ignore_cleanup_errors=True,
        ) as temporary:
            state_root = Path(temporary)
            local_state = state_root / "local-state"
            database = local_state / "cv_studio.sqlite3"
            port = choose_port()
            base = "http://127.0.0.1:{}".format(port)

            os.environ["LOCALAPPDATA"] = str(local_state)
            os.environ["CVSTUDIO_DB_PATH"] = str(database)
            write_test_receipt(ROOT)

            environment = os.environ.copy()
            environment["CVSTUDIO_OWNER_BUILD_SMOKE"] = "1"
            environment["CVSTUDIO_OWNER_BUILD_SMOKE_PORT"] = str(port)
            environment["CVSTUDIO_RUNTIME_LOG_PATH"] = str(state_root / "runtime.log")
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            output = open(state_root / "server-output.log", "w", encoding="utf-8")
            process = subprocess.Popen(
                [sys.executable, str(ROOT / "app.py")],
                cwd=str(ROOT),
                env=environment,
                stdout=output,
                stderr=subprocess.STDOUT,
                creationflags=creation_flags,
            )

            deadline = time.time() + 45
            while time.time() < deadline:
                if process.poll() is not None:
                    raise RuntimeError("Source server exited before smoke checks")
                try:
                    with urllib.request.urlopen(base + "/ping", timeout=1) as response:
                        if 200 <= response.status < 300:
                            break
                except Exception:
                    time.sleep(0.2)
            else:
                raise RuntimeError("Source server did not become ready")

            status_code, headers, status = request_json(base, "/status")
            check(status_code == 200 and status["healthy"], "status route")
            check(status["version"] == VERSION, "version surface")
            check(bool(headers.get("X-CV-Studio-Request-ID")), "response request ID")

            status_code, _, instance = request_json(base, "/instance")
            check(status_code == 200 and instance["version"] == VERSION, "instance identity")

            status_code, _, diagnostics = request_json(base, "/diagnostics/runtime")
            storage = diagnostics["durable_storage"]
            check(status_code == 200 and storage["healthy"], "durable storage health")
            check(storage["journal_mode"] == "wal", "WAL diagnostics")
            check(storage["integrity_check"] == "ok", "integrity diagnostics")
            check("database_path" not in storage, "path-free diagnostics")

            status_code, _, missing = request_json(
                base,
                "/missing-source-smoke",
                request_id="phase2a-source-caller",
            )
            check(status_code == 404 and missing["code"] == "NOT_FOUND", "structured 404")
            check(missing["request_id"] == "phase2a-source-caller", "caller request ID")

            legacy_usage = [{
                "ts": "2026-07-01T00:00:00Z",
                "name": "Legacy fixture",
                "mode": "format",
                "cost": 0.125,
                "model": "legacy-model",
            }]
            status_code, _, usage = request_json(
                base,
                "/storage/usage-history/import",
                method="POST",
                payload={"records": legacy_usage},
            )
            check(status_code == 200 and usage["records"] == legacy_usage, "usage import")
            check("input_tokens" not in usage["records"][0], "legacy detail cutoff")

            ppc = {
                "placement-fixture": {
                    "payment": "Invoiced",
                    "guaranteeMonths": "3",
                    "updatedAt": "2026-07-01T00:00:00Z",
                }
            }
            status_code, _, metadata = request_json(
                base,
                "/storage/ppc-metadata/import",
                method="POST",
                payload={"metadata": ppc},
            )
            check(status_code == 200 and metadata["metadata"] == ppc, "PPC import")

            status_code, _, owner_status = request_json(base, "/owner/integration/status")
            check(status_code == 200 and owner_status["enabled"], "owner status")
            request = urllib.request.Request(
                base + "/owner/integration/run",
                data=json.dumps({"tests": ["local_health", "docx_generation"]}).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "X-CV-Studio-Request": "1",
                    "X-CV-Studio-Owner-Test": "1",
                    "X-CV-Studio-Request-ID": "phase2a-source-owner",
                },
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=90) as response:
                owner_report = json.loads(response.read())
            check(owner_report["summary"]["passed"] == 2, "owner local integration")

            process.terminate()
            process.wait(timeout=15)
            process = None
            output.close()

            connection = sqlite3.connect(str(database))
            try:
                version = connection.execute("PRAGMA user_version").fetchone()[0]
                integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
                history = connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
            finally:
                connection.close()
            check(version == 7, "schema version")
            check(integrity == "ok", "post-run integrity")
            check(history == 7, "migration history")

        print("Phase 2A live source smoke passed: {} assertions".format(checks))
        return 0
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        if output is not None:
            output.close()
        if state_root is not None:
            resolved_state = state_root.resolve()
            resolved_temp = Path(tempfile.gettempdir()).resolve()
            if (
                resolved_state.parent == resolved_temp
                and resolved_state.name.startswith("cvstudio-source-smoke-")
            ):
                shutil.rmtree(resolved_state, ignore_errors=True)
        if original_local_state is None:
            os.environ.pop("LOCALAPPDATA", None)
        else:
            os.environ["LOCALAPPDATA"] = original_local_state
        if original_database_override is None:
            os.environ.pop("CVSTUDIO_DB_PATH", None)
        else:
            os.environ["CVSTUDIO_DB_PATH"] = original_database_override
        if timing_existed:
            timing_path.write_bytes(timing_bytes)
        else:
            timing_path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
