"""Combined frontend source for tests.

The frontend JS was extracted from the old monolithic ``index.html`` into
``vendor/cvstudio/*.js`` modules. Tests that assert on the frontend source must
look in ``index.html`` (still holds the markup + a small inline init) PLUS the
modules it loads.

The modules are read in the SAME ORDER as ``index.html``'s ``<script src>``
tags, and ONLY the files actually referenced there -- not an alphabetical
directory listing. Following the real load order means an assertion can only
find a symbol if the browser actually loads the file that defines it; an
orphaned or unused module file can never produce a false pass.
"""

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_MODULE_TAG = re.compile(
    r"""<script[^>]+src=["']/vendor/cvstudio/([A-Za-z0-9._-]+\.js)(?:\?[^"']*)?["']"""
)


def frontend_source() -> str:
    index_html = (_ROOT / "index.html").read_text(encoding="utf-8-sig")
    source = index_html
    seen: set[str] = set()
    for match in _MODULE_TAG.finditer(index_html):
        name = match.group(1)
        if name in seen:
            continue
        seen.add(name)
        module = _ROOT / "vendor" / "cvstudio" / name
        if module.is_file():
            source += "\n" + module.read_text(encoding="utf-8")
    return source
