#!/usr/bin/env python3
"""Single-source version stamping for CV Studio.

The file ``VERSION`` at the repository root is the ONE authoritative source of
truth for the current release. Every version surface in the shipped code
(``app.py``, ``index.html``, the Windows/macOS installers and launchers, the
protected-build scripts and the install-receipt trap) is *generated* from it by
this script, and ``tests/test_version_single_source.py`` fails the suite if any
surface drifts away from ``VERSION``.

Why generate rather than blanket search-and-replace: several code files also
contain *historical* version mentions (changelog comments such as ``v24.6.137``
in ``index.html`` / ``app.py``). A naive ``sed s/old/new/`` would rewrite those
too. Each surface below is therefore pinned by an explicit anchor pattern that
brackets exactly the *current*-version token and nothing else. If a surface is
moved or renamed so its anchor no longer matches, stamping raises rather than
silently skipping it.

Usage::

    python bump_version.py 24.6.271   # set a new version and stamp every file
    python bump_version.py            # re-stamp the current VERSION (idempotent;
                                      # also repairs any existing drift)

Version tokens exist in two shapes, both derived from ``VERSION``:
  * dotted, ``v``-prefixed  -> ``v24.6.271`` (human-facing surfaces, receipt)
  * underscore slug         -> ``v24_6_271`` (protected-build artifact names)

Windows scripts (``*.ps1``/``*.vbs``/``*.bat``) are CRLF-encoded and the
protected build validates that; all edits here are byte-level so line endings
and any BOM are preserved exactly.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VERSION_FILE = ROOT / "VERSION"

# Semantic version, e.g. "24.6.271" (no leading "v").
_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


def read_version() -> str:
    """Return the canonical bare version string, e.g. ``24.6.271``."""
    raw = VERSION_FILE.read_text(encoding="utf-8").strip()
    if not _VERSION_RE.match(raw):
        raise ValueError(
            f"VERSION file must contain a bare M.N.P version; found {raw!r}."
        )
    return raw


def dotted(version: str) -> str:
    """``24.6.271`` -> ``v24.6.271`` (human-facing / receipt token)."""
    return "v" + version


def slug(version: str) -> str:
    """``24.6.271`` -> ``v24_6_271`` (protected-build artifact-name token)."""
    return "v" + version.replace(".", "_")


# Each anchor is a byte regex with a named group ``ver`` capturing exactly the
# current-version token, wrapped in just enough literal context to be unique and
# to never touch a historical mention. ``DOTTED`` anchors carry the ``vM.N.P``
# shape; ``SLUG`` anchors carry the ``vM_N_P`` shape. Only the ``ver`` group is
# rewritten within each match, so surrounding text is preserved verbatim.
_D = rb"(?P<ver>v\d+\.\d+\.\d+)"
_S = rb"(?P<ver>v\d+_\d+_\d+)"

ANCHORS: dict[str, list[bytes]] = {
    "app.py": [
        rb'_INSTALL_RECEIPT_VERSION = "' + _D + rb'"',
        rb'_CVSTUDIO_VERSION = "' + _D + rb'"',
    ],
    "cvstudio_ja_screening.py": [
        # Version literal embedded in the OneNote CREATE-ONLY browser helper JS
        # (served as a string, so it cannot reference _CVSTUDIO_VERSION at
        # runtime); keep it stamped from VERSION like every other surface.
        rb"const helperVersion = '" + _D + rb"'",
    ],
    "index.html": [
        _D + rb" \(Offline\) by",
        # Cache-bust query on every extracted vendor asset (JS + CSS). One
        # generic anchor covers them all, so newly extracted modules are stamped
        # automatically — no per-slice hand-editing of the ?v= tag. The token
        # carries the dotted vM.N.P shape (e.g. ?v=v24.6.294) so the standard
        # _D machinery applies with no bare-version special case.
        rb"/vendor/cvstudio/[A-Za-z0-9._-]+\?v=" + _D,
    ],
    "vendor/cvstudio/appearance.js": [
        # Version literals extracted from index.html into the appearance
        # controller: the local-data export payload stamp and the wallpaper
        # lock/unlock schema version. Both are served as JS string/object
        # literals, so keep them stamped from VERSION like every other surface.
        rb"version:'" + _D + rb"',schema:1",
        rb"LOCK_UNLOCK_VERSION = '" + _D + rb"'",
    ],
    "INSTALL_CORE.ps1": [
        rb"\$InstallVersion = '" + _D + rb"'",
        rb"'" + _D + rb"-bundled-pdfium-ocr-antiword'",
    ],
    "INSTALL_RECEIPT.ps1": [
        rb"\$Version = '" + _D + rb"'",
    ],
    "START_HIDDEN.vbs": [
        rb'Const EXPECTED_VERSION = "' + _D + rb'"',
    ],
    "WATCHDOG.vbs": [
        rb'Const EXPECTED_VERSION = "' + _D + rb'"',
    ],
    "install.sh": [
        rb"installer " + _D + rb"\b",
        rb'VERSION="' + _D + rb'"',
    ],
    "start.sh": [
        rb"launcher " + _D + rb"\b",
        rb'VERSION="' + _D + rb'"',
    ],
    "owner_build_tools/BUILD_PROTECTED_WINDOWS.bat": [
        rb"CV Studio " + _D + rb" Protected Windows Build",
    ],
    "owner_build_tools/build_protected.py": [
        rb'VERSION = "' + _D + rb'"',
        rb'VERSION_SLUG = "' + _S + rb'"',
    ],
    "tests/test_phase2a_app_cache_integration.py": [
        rb'payload\["version"\], "' + _D + rb'"',
    ],
}


def stamp(version: str) -> list[str]:
    """Rewrite every anchored surface to ``version``. Returns files changed."""
    want_dotted = dotted(version).encode("ascii")
    want_slug = slug(version).encode("ascii")
    changed: list[str] = []
    for rel, patterns in ANCHORS.items():
        path = ROOT / rel
        data = path.read_bytes()
        original = data
        for pattern in patterns:
            token = want_slug if rb"_\d+_" in pattern else want_dotted
            new_data, count = re.subn(
                pattern,
                lambda m, _t=token: m.group(0).replace(m.group("ver"), _t),
                data,
            )
            if count == 0:
                raise RuntimeError(
                    f"Version anchor not found in {rel}: {pattern!r}. "
                    "The line was moved or renamed; update ANCHORS in bump_version.py."
                )
            data = new_data
        if data != original:
            path.write_bytes(data)
            changed.append(rel)
    return changed


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        new_version = argv[1].lstrip("v").strip()
        if not _VERSION_RE.match(new_version):
            print(f"error: expected a bare M.N.P version, got {argv[1]!r}", file=sys.stderr)
            return 2
        VERSION_FILE.write_text(new_version + "\n", encoding="utf-8")
    version = read_version()
    changed = stamp(version)
    print(f"VERSION = {version} ({dotted(version)}, slug {slug(version)})")
    if changed:
        print("stamped:", ", ".join(changed))
    else:
        print("all surfaces already consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
