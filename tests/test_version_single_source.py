"""Enforce the single authoritative version source.

``VERSION`` at the repository root is the one source of truth for the current
release. Every shipped code surface must equal it. Before this guard, the
version was hand-copied into ~11 files (plus a separate underscore *slug* in the
protected-build script), and drift crept in silently -- e.g. the build slug
lagged the app version, so a shipped protected build could be named after one
version while the app inside reported another.

This test makes that drift un-mergeable: it re-derives every version token from
``VERSION`` and asserts each anchored surface carries exactly that token. The
anchor table lives once, in ``bump_version.py`` (which generates the surfaces);
this test consumes the same table so the generator and the guard can never
disagree.
"""

import re
import unittest
from pathlib import Path

import bump_version


ROOT = Path(__file__).resolve().parents[1]


class VersionSingleSourceTests(unittest.TestCase):
    def setUp(self):
        self.version = bump_version.read_version()
        self.dotted = bump_version.dotted(self.version).encode("ascii")
        self.slug = bump_version.slug(self.version).encode("ascii")

    def test_version_file_is_a_bare_semver(self):
        self.assertRegex(self.version, r"^\d+\.\d+\.\d+$")

    def test_every_anchored_surface_matches_VERSION(self):
        for rel, patterns in bump_version.ANCHORS.items():
            path = ROOT / rel
            self.assertTrue(path.is_file(), rel)
            data = path.read_bytes()
            for pattern in patterns:
                is_slug = rb"_\d+_" in pattern
                expected = self.slug if is_slug else self.dotted
                matches = list(re.finditer(pattern, data))
                self.assertTrue(
                    matches,
                    f"{rel}: anchor {pattern!r} not found (line moved/renamed?)",
                )
                for match in matches:
                    self.assertEqual(
                        match.group("ver"),
                        expected,
                        f"{rel}: version surface {match.group('ver')!r} "
                        f"drifted from VERSION ({expected!r}).",
                    )

    def test_install_receipt_and_display_version_agree(self):
        # The two app.py constants gate the boot-time receipt trap and the
        # /health-style surfaces respectively; both must equal VERSION.
        app_text = (ROOT / "app.py").read_text(encoding="utf-8-sig")
        want = self.dotted.decode("ascii")
        self.assertIn(f'_INSTALL_RECEIPT_VERSION = "{want}"', app_text)
        self.assertIn(f'_CVSTUDIO_VERSION = "{want}"', app_text)

    def test_stamp_is_idempotent(self):
        # Re-stamping the current VERSION must not want to change anything, i.e.
        # the committed tree is already fully consistent with VERSION.
        changed = bump_version.stamp(self.version)
        self.assertEqual(changed, [], f"surfaces out of sync with VERSION: {changed}")


if __name__ == "__main__":
    unittest.main()
