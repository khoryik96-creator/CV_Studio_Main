import copy
import io
import json
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock
import zipfile

from owner_build_tools import build_protected


_TEMP = tempfile.TemporaryDirectory(prefix="cvstudio-long-cv-")
_ROOT = Path(__file__).resolve().parents[1]
os.environ["CVSTUDIO_DB_PATH"] = str(Path(_TEMP.name) / "state.sqlite3")
os.environ["LOCALAPPDATA"] = str(Path(_TEMP.name) / "local")
build_protected.write_test_receipt(_ROOT)

import app


class LongCvOutputCorrectiveTests(unittest.TestCase):
    def fixture(self):
        return {
            "candidate": {
                "name": "Saik Eng Joo",
                "current_position": "Insurance Agent/Financial Advisor (assumed from duties)",
                "current_company": "MANULIFE",
            },
            "work_experiences": [{
                "date_range": "2023 to Present",
                "company": "Example Sdn Bhd",
                "roles": [{
                    "title": "Insurance Agent/Financial Advisor (likely based on responsibilities)",
                    "date_range": "",
                    "reason_for_leaving": "",
                    "bullets": [
                        "Key responsibilities",
                        '{"heading":"Responsibilities","bullets":["Achievement"]}',
                        '{"bullets":["Successfully achieved over 100% of the annual sales target.","Honored with Best Performing Business Development Manager for year 2024."],"heading":"Business Set up"}',
                        '{"bullets":["Successfully achieved 120% of the annual sales target."],"heading":"Manpower"}',
                        '{"heading":"malformed","bullets":[}',
                    ],
                }],
            }],
            "education": [],
            "certifications": ["", "  "],
            "skills": [{"category": "Skills", "items": "Leadership"}, {"category": "", "items": ""}],
        }

    def test_long_cv_timeout_is_bounded_and_role_dense(self):
        self.assertEqual(app._cv_parse_backend_timeout_seconds("x" * 17999), 180)
        self.assertEqual(app._cv_parse_backend_timeout_seconds("x" * 18000), 300)
        dense = "\n".join(["Key responsibilities"] * 7)
        self.assertEqual(app._cv_parse_backend_timeout_seconds(dense), 180)
        dense += "\nKey achievement"
        self.assertEqual(app._cv_parse_backend_timeout_seconds(dense), 300)

    def test_parse_route_passes_long_timeout_to_provider(self):
        provider_result = {
            "content": [{"type": "text", "text": json.dumps({
                "candidate": {}, "work_experiences": [], "education": [],
                "certifications": [], "skills": [],
            })}],
            "usage": {},
        }
        with (
            mock.patch.object(app, "call_llm", return_value=provider_result) as call,
            mock.patch.object(app, "_ai_spend_session_allowed", return_value=True),
        ):
            response = app.app.test_client().post(
                "/parse",
                json={"api_key": "fixture-key", "cv_text": "x" * 18000},
                headers={"Origin": "http://127.0.0.1:5000", "X-CV-Studio-Request": "1"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(call.call_args.args[2]["_timeout_seconds"], 300)

    def test_structured_normalization_is_idempotent_and_factual(self):
        normalized = app._normalize_cv_structured_content(self.fixture())
        role = normalized["work_experiences"][0]["roles"][0]
        self.assertEqual(normalized["candidate"]["current_position"], "")
        self.assertEqual(role["title"], "")
        self.assertEqual(role["bullets"][0], {
            "heading": "Key responsibilities",
            "bullets": [],
            "kind": "section",
        })
        self.assertEqual(role["bullets"][1], {
            "heading": "Key responsibilities",
            "bullets": ["Achievement"],
            "kind": "section",
        })
        self.assertEqual(role["bullets"][2]["heading"], "Business Set up")
        self.assertEqual(role["bullets"][4], '{"heading":"malformed","bullets":[}')
        self.assertEqual(normalized["certifications"], [])
        self.assertEqual(normalized["skills"], [{"category": "Skills", "items": "Leadership"}])
        self.assertEqual(app._normalize_cv_structured_content(copy.deepcopy(normalized)), normalized)

    def test_standalone_sections_and_bounded_inference_variants_are_normalized(self):
        self.assertEqual(app._normalize_cv_bullet_items(["Key achievement", "Delivered result"]), [
            {"heading": "Key achievements", "bullets": [], "kind": "section"},
            "Delivered result",
        ])
        for title in (
            "Advisor (inferred from duties)",
            "Advisor (implied from responsibilities)",
            "Advisor (assumed from duties)",
            "Advisor (guessed from context)",
            "Advisor (likely based on responsibilities)",
        ):
            self.assertEqual(app._strip_cv_inferred_title(title), "")
        self.assertEqual(app._strip_cv_inferred_title("Advisor"), "Advisor")
        self.assertEqual(app._strip_cv_inferred_title("Advisor (likely to succeed)"), "Advisor (likely to succeed)")

    def test_docx_xml_never_serializes_structured_bullets_or_inferred_title(self):
        response = app.app.test_client().post(
            "/generate-docx",
            json={"data": self.fixture()},
            headers={"Origin": "http://127.0.0.1:5000"},
        )
        self.assertEqual(response.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            document_xml = archive.read("word/document.xml").decode("utf-8")
        self.assertNotIn('&quot;heading&quot;:&quot;Business Set up&quot;', document_xml)
        self.assertNotIn('&quot;heading&quot;:&quot;Responsibilities&quot;', document_xml)
        self.assertNotIn("assumed from duties", document_xml)
        self.assertNotIn("likely based on responsibilities", document_xml)
        self.assertIn("Key responsibilities", document_xml)
        heading_paragraphs = [
            paragraph for paragraph in re.findall(r"<w:p\b.*?</w:p>", document_xml, re.S)
            if "Key responsibilities" in paragraph
        ]
        self.assertTrue(heading_paragraphs)
        self.assertTrue(all("<w:numPr>" not in paragraph for paragraph in heading_paragraphs))
        self.assertIn("Business Set up", document_xml)
        self.assertIn("Successfully achieved over 100%", document_xml)
        self.assertEqual(document_xml.count("<w:t>Skills:</w:t>"), 1)
        self.assertNotIn("E D U C A T I O N S  &amp;  T R A I N I N G", document_xml)
        self.assertNotIn("<w:t>Example Sdn Bhd</w:t></w:r></w:p></w:tc>\n    <w:tc", document_xml)

    def test_prompt_forbids_inferred_titles_and_serialized_groups(self):
        self.assertIn("Never invent, infer, imply, annotate, or explain a title", app.SYSTEM_PROMPT)
        self.assertIn("never as JSON serialized inside a string", app.SYSTEM_PROMPT)

    def test_ai_crawler_backend_no_longer_requires_password(self):
        with app.app.test_request_context("/jobadder/spider_options"):
            self.assertTrue(app._ai_crawler_lock_allowed({}))


if __name__ == "__main__":
    unittest.main()
