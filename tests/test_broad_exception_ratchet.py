"""Ratchet test for silently-swallowed broad exceptions.

Audit finding P2 ("Broad exception swallowing weakens diagnostics and can hide
state failures") recommends: *"Add a lint/test rule that rejects a new
``except Exception: pass`` unless it contains an approved explanatory marker."*

This does exactly that without forcing an immediate rewrite of the existing
handlers. It counts ``pass``-only broad handlers (bare ``except:`` or
``except Exception``/``BaseException``) that carry no approved marker, and asserts
the per-file count never rises above a frozen baseline. So:

* existing handlers are grandfathered by the baseline;
* a NEW unmarked ``except ...: pass`` makes the count exceed the baseline and fails;
* a genuinely-necessary best-effort handler can be annotated with one of the
  approved markers (on the ``except`` line or anywhere in its body) to opt out;
* as handlers are classified/annotated the count drops below the baseline (still
  passing) and the baseline can be tightened over time.

The intent is a diagnostics ratchet, not a ban: fallbacks stay allowed, they just
have to be acknowledged.
"""

import ast
import pathlib
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# A pass-only broad handler is treated as acknowledged (and excluded from the
# count) when its source carries one of these case-insensitive markers.
_APPROVED_MARKERS = ("best-effort", "broad-except-ok", "cleanup-only")

# Frozen baseline of UNMARKED pass-only broad handlers per file. Numbers may only
# go DOWN. Any increase — or a new file appearing here — fails the ratchet.
_BASELINE = {
    "app.py": 88,
    "cvstudio_msgraph.py": 17,
    "cvstudio_clients.py": 6,
    "cvstudio_lead_cache.py": 6,
    "cvstudio_lead_enrich.py": 6,
    "cvstudio_document_safety.py": 4,
    "cvstudio_onenote_desktop.py": 4,
    "cvstudio_storage.py": 4,
    "cvstudio_onenote_text.py": 2,
    "cvstudio_antiword.py": 1,
    "cvstudio_jobadder_read.py": 1,
    "cvstudio_jobs.py": 1,
    "cvstudio_lead_search.py": 1,
}


def _scanned_files():
    files = sorted(_REPO_ROOT.glob("*.py"))
    files += sorted((_REPO_ROOT / "salary_comparison").glob("*.py"))
    return files


def _handler_is_broad(handler):
    exc_type = handler.type
    if exc_type is None:
        return True  # bare ``except:``
    if isinstance(exc_type, ast.Name) and exc_type.id in ("Exception", "BaseException"):
        return True
    if isinstance(exc_type, ast.Tuple):
        return any(
            isinstance(elt, ast.Name) and elt.id in ("Exception", "BaseException")
            for elt in exc_type.elts
        )
    return False


def _body_is_pass_only(handler):
    meaningful = [
        node
        for node in handler.body
        if not (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        )
    ]
    return len(meaningful) == 1 and isinstance(meaningful[0], ast.Pass)


def _is_marked(handler, source_lines):
    start = handler.lineno - 1
    end = getattr(handler, "end_lineno", handler.lineno)
    snippet = "\n".join(source_lines[start:end]).lower()
    return any(marker in snippet for marker in _APPROVED_MARKERS)


def _count_unmarked_pass_only(path):
    text = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return 0
    source_lines = text.splitlines()
    count = 0
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ExceptHandler)
            and _handler_is_broad(node)
            and _body_is_pass_only(node)
            and not _is_marked(node, source_lines)
        ):
            count += 1
    return count


class BroadExceptionRatchetTests(unittest.TestCase):
    def test_no_new_silent_broad_handlers(self):
        counts = {}
        for path in _scanned_files():
            rel = path.relative_to(_REPO_ROOT).as_posix()
            counts[rel] = _count_unmarked_pass_only(path)

        failures = []
        for rel, count in counts.items():
            allowed = _BASELINE.get(rel, 0)
            if count > allowed:
                failures.append(
                    f"{rel}: {count} unmarked pass-only broad handlers "
                    f"(baseline {allowed}). Add a structured diagnostic / typed "
                    f"error, or annotate the intentional handler with one of "
                    f"{_APPROVED_MARKERS}."
                )
        self.assertEqual(failures, [], "New silently-swallowed broad exception(s):\n" + "\n".join(failures))

    def test_baseline_is_not_stale(self):
        # If a file dropped below its baseline, tighten the baseline so the
        # ratchet keeps its grip. This keeps the numbers honest over time.
        stale = []
        for rel, allowed in _BASELINE.items():
            path = _REPO_ROOT / rel
            if not path.exists():
                continue
            actual = _count_unmarked_pass_only(path)
            if actual < allowed:
                stale.append(f"{rel}: baseline {allowed} but only {actual} remain — lower the baseline to {actual}.")
        self.assertEqual(stale, [], "Ratchet baseline is looser than reality:\n" + "\n".join(stale))


if __name__ == "__main__":
    unittest.main()
