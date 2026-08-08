#!/usr/bin/env python3
"""Render a parsed-CV JSON to the formatted DOCX and print it as plain text.

A fast local loop for CV-formatting work: it runs the *real* deterministic
pipeline (reconcile + normalize + the ``generate.js`` DOCX renderer) via the
app's own ``/generate-docx`` route -- no browser, no install, no Word, and no AI
call (the parse step is skipped; you supply the already-parsed data).

Usage::

    python preview_format.py parsed.json          # print the formatted text
    python preview_format.py parsed.json out.docx  # also write the .docx

``parsed.json`` is the object CV Studio sends to ``/generate-docx``. It is either
``{"data": {...}}`` or the bare parsed CV ``{"candidate": {...},
"work_experiences": [...], ...}`` -- both are accepted. To capture a real one,
copy the ``/parse`` response's ``data`` field from the app once and reuse it
offline as many times as you like.
"""

import io
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _load_app():
    tmp = tempfile.mkdtemp(prefix="cvstudio-preview-")
    os.environ.setdefault("CVSTUDIO_DB_PATH", str(Path(tmp) / "state.sqlite3"))
    os.environ.setdefault("LOCALAPPDATA", str(Path(tmp) / "local"))
    from owner_build_tools import build_protected
    build_protected.write_test_receipt(ROOT)
    import app
    return app


def _docx_to_text(docx_bytes):
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as archive:
        xml = archive.read("word/document.xml").decode("utf-8")
    # Cheap, dependency-free paragraph/text extraction.
    import re
    lines = []
    for para in re.findall(r"<w:p\b.*?</w:p>", xml, re.S):
        texts = re.findall(r"<w:t[^>]*>(.*?)</w:t>", para, re.S)
        line = "".join(texts)
        line = (line.replace("&amp;", "&").replace("&lt;", "<")
                    .replace("&gt;", ">").replace("&quot;", '"').replace("&apos;", "'"))
        if line.strip():
            # "  • " marks a real list bullet; headings/plain lines have no marker,
            # so a sub-section label like "Key responsibilities" is visibly a
            # heading rather than a stray bullet.
            marker = "  • " if "<w:numPr>" in para else "    "
            lines.append(marker + line)
    return lines


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    payload = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    if "data" not in payload:
        payload = {"data": payload}

    app = _load_app()
    resp = app.app.test_client().post(
        "/generate-docx", json=payload,
        headers={"Origin": "http://127.0.0.1:5000"},
    )
    if resp.status_code != 200:
        print(f"generate-docx failed: {resp.status_code} {resp.get_data(as_text=True)[:400]}", file=sys.stderr)
        return 1
    for line in _docx_to_text(resp.data):
        print(line)
    if len(argv) >= 3:
        Path(argv[2]).write_bytes(resp.data)
        print(f"\n[wrote {argv[2]}]", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
