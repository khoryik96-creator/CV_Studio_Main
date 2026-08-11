"""Combined frontend source for tests.

The frontend JS was extracted from the old monolithic ``index.html`` into
``vendor/cvstudio/*.js`` modules. Tests that assert on the frontend source must
therefore look in ``index.html`` (still holds the markup + a small inline init)
PLUS every module. ``frontend_source()`` returns that combined text so an
assertion finds each symbol wherever it was extracted to.
"""

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def frontend_source() -> str:
    source = (_ROOT / "index.html").read_text(encoding="utf-8-sig")
    module_dir = _ROOT / "vendor" / "cvstudio"
    if module_dir.is_dir():
        for module in sorted(module_dir.glob("*.js")):
            source += "\n" + module.read_text(encoding="utf-8")
    return source
