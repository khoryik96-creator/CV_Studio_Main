"""Static web-asset serving for CV Studio.

The application remains responsible for registering the ``/vendor/<path>``,
``/cv_studio_logo.png``, ``/cv_studio.ico`` and ``/favicon.ico`` routes.  This
module receives the source directory through an explicit callback and never
imports the application or any shared mutable state.  The path-traversal
rejection and fallbacks are a verbatim move of the legacy web-shell handlers so
the served bytes, status codes and security checks are unchanged.
"""

from __future__ import annotations

import os
import re
from typing import Any, Callable


class WebAssetsService:
    """Explicitly wired handlers behind the static web-asset endpoints."""

    def __init__(
        self,
        *,
        jsonify: Callable[[Any], Any],
        send_from_directory: Callable[..., Any],
        source_dir: Callable[[], str],
    ):
        self._jsonify = jsonify
        self._send_from_directory = send_from_directory
        self._source_dir = source_dir

    def vendor_asset(self, filename):
        """Serve bundled offline browser dependencies used by index.html."""
        vendor_dir = os.path.realpath(os.path.join(self._source_dir(), "vendor"))
        raw_name = str(filename or "").replace("\\", "/")
        safe_name = os.path.normpath(raw_name).replace("\\", "/")
        if (not safe_name or safe_name.startswith("../") or safe_name.startswith("/")
                or safe_name != raw_name or not re.fullmatch(r"[A-Za-z0-9._/-]+", safe_name)):
            return self._jsonify({"error": "Not found"}), 404
        asset_path = os.path.realpath(os.path.join(vendor_dir, safe_name))
        if not asset_path.startswith(vendor_dir + os.sep) or not os.path.isfile(asset_path):
            return self._jsonify({"error": "Not found"}), 404
        return self._send_from_directory(vendor_dir, safe_name)

    def app_logo_png(self):
        """Serve the app logo explicitly without exposing the full source folder."""
        base_dir = self._source_dir()
        return self._send_from_directory(base_dir, "cv_studio_logo.png")

    def app_icon_ico(self):
        """Serve the bundled Windows/icon asset explicitly."""
        base_dir = self._source_dir()
        return self._send_from_directory(base_dir, "cv_studio.ico")

    def favicon(self):
        base_dir = self._source_dir()
        ico_path = os.path.join(base_dir, "cv_studio.ico")
        if os.path.isfile(ico_path):
            return self._send_from_directory(base_dir, "cv_studio.ico")
        return self._send_from_directory(base_dir, "cv_studio_logo.png")
