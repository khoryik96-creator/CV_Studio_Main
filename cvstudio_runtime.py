"""Runtime liveness and identity service for CV Studio.

The application remains responsible for registering the read-only ``/status``,
``/instance``, ``/instance-id`` and ``/ping`` routes.  This module receives the
running process identity (version, install root, root hash, instance id and
port) through explicit callbacks and never imports the application or any
shared mutable state.  The response payloads, status codes and headers are a
verbatim move of the legacy web-shell handlers.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Callable


class RuntimeService:
    """Explicitly wired handlers behind the runtime liveness/identity endpoints."""

    def __init__(
        self,
        *,
        jsonify: Callable[[Any], Any],
        version: Callable[[], str],
        root_path: Callable[[], str],
        root_hash: Callable[[], str],
        instance_id: Callable[[], str],
        port: Callable[[], Any],
    ):
        self._jsonify = jsonify
        self._version = version
        self._root_path = root_path
        self._root_hash = root_hash
        self._instance_id = instance_id
        self._port = port

    def status(self):
        """Report the health of the process that is serving this response.

        Older builds counted pythonw.exe/app.py processes, which is inaccurate for
        native CVStudio executables and can match unrelated Python applications.
        If this route is executing, the current server process is alive.
        """
        executable_name = os.path.basename(str(sys.executable or sys.argv[0] or "")).strip()
        argv0_name = os.path.basename(str(sys.argv[0] or "")).strip()
        native_compiled = bool(
            getattr(sys, "frozen", False)
            or executable_name.lower().startswith("cvstudio")
            or argv0_name.lower().startswith("cvstudio")
        )
        return self._jsonify({
            "status": "running",
            "version": self._version(),
            "healthy": True,
            "root": self._root_path(),
            "root_hash": self._root_hash(),
            "instance_id": self._instance_id(),
            "runtime_mode": "native" if native_compiled else "source",
            "runtime_process": executable_name or argv0_name or "unknown",
            # Retain the legacy field for older frontends, but make it represent the
            # one process that is demonstrably serving this request.
            "pythonw_instances": 1,
        })

    def instance_info(self):
        """Identify the exact version and extracted package serving this port."""
        return self._jsonify({
            "product": "CV Studio",
            "version": self._version(),
            "root": self._root_path(),
            "root_hash": self._root_hash(),
            "instance_id": self._instance_id(),
            "pid": os.getpid(),
            "port": self._port(),
        })

    def instance_id_text(self):
        # Plain text is intentionally easy for VBS/bash launchers to validate.
        return "{}|{}|{}".format(self._version(), self._instance_id(), self._root_path()), 200, {"Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store"}

    def ping(self):
        """Self-ping endpoint — keeps the process warm during idle periods."""
        return "", 204
