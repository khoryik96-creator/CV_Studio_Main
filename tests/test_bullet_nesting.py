"""Tests for multi-level bullet nesting (DOCX w:ilvl / PDF geometry / outline
labels) and its rendering through /generate-docx.

Levels are recovered server-side (docx metadata, pdf x-geometry, or the outline
label ladder), merged, and rendered by generate.js as stepped w:ilvl + per-level
w:leftChars. Non-nested bullets stay at level 0, so ordinary CVs are unchanged.
"""

import io
import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import zipfile

from owner_build_tools import build_protected

_TEMP = tempfile.TemporaryDirectory(prefix="cvstudio-nesting-")
_ROOT = Path(__file__).resolve().parents[1]
os.environ["CVSTUDIO_DB_PATH"] = str(Path(_TEMP.name) / "state.sqlite3")
os.environ["LOCALAPPDATA"] = str(Path(_TEMP.name) / "local")
build_protected.write_test_receipt(_ROOT)

import app


class OutlineLabelInferenceTests(unittest.TestCase):
    def test_infer_levels_from_label_sequence(self):
        seq = ["Responsible for all IP services:", "(a) Operating System", "(b) Physical Server",
               "(c) Virtual Machines", "Ensure OLAs are met"]
        self.assertEqual(app._infer_outline_levels(seq), [0, 1, 1, 1, 0])

    def test_nested_ladder(self):
        # Parenthesised alpha then multi-char parenthesised roman nests one level
        # deeper. (A single-char "(i)" is ambiguous with alpha and is treated as
        # alpha -- an accepted limitation; real sub-lists use (a)-(e) siblings.)
        seq = ["Intro:", "(a) First", "(b) Second", "(iii) deep", "(iv) deep2", "(c) Third", "Outro"]
        self.assertEqual(app._infer_outline_levels(seq), [0, 1, 1, 2, 2, 1, 0])

    def test_plain_glyphs_are_not_labels(self):
        self.assertEqual(app._infer_outline_levels(["- one", "- two", "* three"]), [0, 0, 0])

    def test_label_style_only_covers_stripped_forms(self):
        # Classification is restricted to what _CV_LEADING_BULLET_MARKER_RE strips
        # (parenthesised + numeric), so a label is never counted without being
        # stripped. Bare "a." is not a recognised style here.
        self.assertIsNotNone(app._bullet_label_style("(a) x"))
        self.assertIsNotNone(app._bullet_label_style("1. x"))
        self.assertNotEqual(app._bullet_label_style("(a) x"), app._bullet_label_style("(vi) x"))
        self.assertIsNone(app._bullet_label_style("a. x"))
        self.assertIsNone(app._bullet_label_style("plain text"))

    def test_match_key_aligns_with_display_strip(self):
        # The map key from the raw label must equal the lowercased rendered text.
        self.assertEqual(app._cv_bullet_match_key("(a) Operating System"), "operating system")
        self.assertEqual(app._cv_bullet_match_key("1. Increased sales"), "increased sales")


class PdfGeometryLevelTests(unittest.TestCase):
    def test_levels_from_x_positions(self):
        # Base column 204 (level 0); deeper columns step by their indent. Keys use
        # parenthesised labels (stripped by _cv_bullet_match_key), and the ~6pt
        # jitter on the last row must still resolve to level 2.
        lines = [(204, "- p1"), (204, "- p2"), (204, "- p3"), (204, "- p4"),
                 (240, "(a) child one"), (240, "(b) child two"),
                 (276, "(i) grand one"), (282, "(ii) grand two")]
        self.assertEqual(app._pdf_bullet_levels_from_lines(lines), [
            {"text": "child one", "level": 1},
            {"text": "child two", "level": 1},
            {"text": "grand one", "level": 2},
            {"text": "grand two", "level": 2},
        ])

    def test_flat_and_guards(self):
        self.assertEqual(app._pdf_bullet_levels_from_lines(
            [(204, "- a"), (204, "- b"), (204, "- c"), (204, "- d")]), [])
        self.assertEqual(app._pdf_bullet_levels_from_lines([(204, "- a"), (240, "b. deep")]), [])


class GenerateDocxNestingTests(unittest.TestCase):
    def _ilvl(self, xml, target):
        for p in re.findall(r"<w:p\b.*?</w:p>", xml, re.S):
            if target in "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", p)):
                m = re.search(r'<w:ilvl w:val="(\d+)"', p)
                return m.group(1) if m else None
        return "MISSING"

    def _leftchars(self, xml, target):
        for p in re.findall(r"<w:p\b.*?</w:p>", xml, re.S):
            if target in "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", p)):
                m = re.search(r'w:leftChars="(\d+)"', p)
                return m.group(1) if m else None
        return "MISSING"

    def _generate(self, data, bullet_levels=None):
        client = app.app.test_client()
        client.set_cookie(app._AI_SPEND_SESSION_COOKIE, app._AI_SPEND_SESSION_TOKEN)
        body = {"data": data}
        if bullet_levels is not None:
            body["bullet_levels"] = bullet_levels
        r = client.post("/generate-docx", json=body, headers={"Origin": "http://127.0.0.1:5000"})
        self.assertEqual(r.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(r.data)) as z:
            return z.read("word/document.xml").decode("utf-8")

    def test_infers_and_renders_nesting_from_labels(self):
        data = {"candidate": {"name": "T"}, "work_experiences": [{"company": "Co", "date_range": "2020 to 2021",
                "roles": [{"title": "Eng", "bullets": [
                    "Responsible for all IP services:", "(a) Operating System", "(b) Physical Server", "Ensure OLAs are met"]}]}]}
        xml = self._generate(data)  # no map: server infers from labels
        self.assertEqual(self._ilvl(xml, "Operating System"), "1")
        self.assertEqual(self._ilvl(xml, "Physical Server"), "1")
        self.assertEqual(self._leftchars(xml, "Physical Server"), "500")
        self.assertEqual(self._ilvl(xml, "Ensure OLAs are met"), "0")
        self.assertNotIn("(a) Operating", xml)

    def test_no_levels_keeps_flat_output(self):
        data = {"candidate": {"name": "T"}, "work_experiences": [{"company": "Co", "date_range": "2020 to 2021",
                "roles": [{"title": "Eng", "bullets": ["Did a thing", "Did another thing"]}]}]}
        xml = self._generate(data)
        self.assertEqual(self._ilvl(xml, "Did a thing"), "0")
        self.assertEqual(self._leftchars(xml, "Did a thing"), None)

    def test_explicit_map_levels_render(self):
        data = {"candidate": {"name": "T"}, "work_experiences": [{"company": "Co", "date_range": "2020 to 2021",
                "roles": [{"title": "Eng", "bullets": ["Parent", "Manchester united", "Wonderful world"]}]}]}
        levels = [{"text": "manchester united", "level": 1}, {"text": "wonderful world", "level": 2}]
        xml = self._generate(data, bullet_levels=levels)
        self.assertEqual(self._ilvl(xml, "Manchester united"), "1")
        self.assertEqual(self._ilvl(xml, "Wonderful world"), "2")
        self.assertEqual(self._leftchars(xml, "Wonderful world"), "800")


class ParseReturnsLevelsTests(unittest.TestCase):
    def test_parse_returns_outline_levels_before_stripping(self):
        parsed_json = {"candidate": {"name": "T"}, "work_experiences": [{"company": "Co", "date_range": "2020 to 2021",
                "roles": [{"title": "Eng", "bullets": [
                    "Responsible for all IP services:", "(a) Operating System", "(b) Physical Server", "Ensure OLAs"]}]}]}

        def fake_call_llm(provider, api_key, payload):
            return {"content": [{"text": json.dumps(parsed_json)}], "usage": {}}

        client = app.app.test_client()
        client.set_cookie(app._AI_SPEND_SESSION_COOKIE, app._AI_SPEND_SESSION_TOKEN)
        with mock.patch.object(app, "call_llm", side_effect=fake_call_llm):
            r = client.post("/parse", json={"api_key": "sk-test", "cv_text": "x", "model": "m", "provider": "anthropic"},
                            headers={"Origin": "http://127.0.0.1:5000"})
        self.assertEqual(r.status_code, 200)
        payload = r.get_json()
        levels = {e["text"]: e["level"] for e in payload.get("bullet_levels", [])}
        self.assertEqual(levels.get("operating system"), 1)
        self.assertEqual(levels.get("physical server"), 1)
        bullets = payload["data"]["work_experiences"][0]["roles"][0]["bullets"]
        self.assertIn("Operating System", bullets)
        self.assertNotIn("(a) Operating System", bullets)


if __name__ == "__main__":
    unittest.main()
