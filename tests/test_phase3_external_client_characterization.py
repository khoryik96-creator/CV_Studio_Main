import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import urllib.error
from unittest import mock


_MODULE_TEMPORARY = tempfile.TemporaryDirectory(prefix="cvstudio-phase3-characterization-")
_ORIGINAL_DATABASE_OVERRIDE = os.environ.get("CVSTUDIO_DB_PATH")
os.environ["CVSTUDIO_DB_PATH"] = str(
    Path(_MODULE_TEMPORARY.name) / "state" / "cv_studio.sqlite3"
)
from owner_build_tools.build_protected import write_test_receipt

write_test_receipt(Path(__file__).resolve().parents[1])
try:
    import app
finally:
    if _ORIGINAL_DATABASE_OVERRIDE is None:
        os.environ.pop("CVSTUDIO_DB_PATH", None)
    else:
        os.environ["CVSTUDIO_DB_PATH"] = _ORIGINAL_DATABASE_OVERRIDE


class _FakeResponse:
    def __init__(self, payload=b"", *, status=200, headers=None):
        if isinstance(payload, (dict, list)):
            payload = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        elif isinstance(payload, str):
            payload = payload.encode("utf-8")
        self._payload = bytes(payload)
        self.status = int(status)
        self.headers = dict(headers or {})

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


def _http_error(url, status, payload, headers=None):
    if isinstance(payload, (dict, list)):
        payload = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    elif isinstance(payload, str):
        payload = payload.encode("utf-8")
    return urllib.error.HTTPError(
        url,
        int(status),
        "fixture upstream failure",
        dict(headers or {}),
        io.BytesIO(payload),
    )


class Phase3ExternalClientCharacterizationTests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()

    @staticmethod
    def _headers(request_id):
        return {"X-CV-Studio-Request-ID": request_id}

    def test_service_route_inventory_preserves_v246222_baseline(self):
        routes = {rule.rule for rule in app.app.url_map.iter_rules()}
        self.assertEqual(len(routes), 107)
        self.assertTrue(
            {
                "/jobadder/search_candidate",
                "/jobadder/create_candidate",
                "/jobadder/update_candidate",
                "/jobadder/upload_original_cv",
                "/jobadder/upload_cv",
                "/jobadder/spider_search",
                "/jobadder/ppc/placements",
                "/onenote/device_start",
                "/onenote/device_poll",
                "/onenote/notebooks",
                "/onenote/sections",
                "/onenote/pages",
                "/onenote/page_content",
                "/ppc/outlook/device_start",
                "/ppc/outlook/device_poll",
                "/ppc/outlook/create_draft",
                "/test",
                "/parse",
                "/generate-ai",
            }.issubset(routes)
        )

    def test_jobadder_search_success_and_error_response_shapes(self):
        success = {"items": [{"fixture": "candidate-summary"}], "totalCount": 1}
        with mock.patch.object(app, "_ja_refresh_access_token", return_value="<fixture-credential>"), mock.patch.object(
            app, "_ja_api", side_effect=lambda path: "https://api.jobadder.com/v2/" + path
        ), mock.patch.object(
            app.urllib.request, "urlopen", return_value=_FakeResponse(success)
        ) as opened:
            response = self.client.get(
                "/jobadder/search_candidate?email=",
                headers=self._headers("phase3-ja-success"),
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), success)
        request_object = opened.call_args.args[0]
        self.assertEqual(request_object.full_url, "https://api.jobadder.com/v2/candidates?email=")
        self.assertEqual(request_object.get_header("Authorization"), "Bearer <fixture-credential>")
        self.assertEqual(opened.call_args.kwargs["timeout"], 15)

        error_url = "https://api.jobadder.com/v2/candidates?email="
        upstream = {"message": "fixture upstream unavailable"}
        search_error = _http_error(error_url, 503, upstream)
        with mock.patch.object(app, "_ja_refresh_access_token", return_value="<fixture-credential>"), mock.patch.object(
            app, "_ja_api", side_effect=lambda path: "https://api.jobadder.com/v2/" + path
        ), mock.patch.object(
            app.urllib.request,
            "urlopen",
            side_effect=search_error,
        ):
            response = self.client.get(
                "/jobadder/search_candidate?email=",
                headers=self._headers("phase3-ja-error"),
            )
        search_error.close()
        payload = response.get_json()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(payload["error"], "JobAdder error: 503")
        self.assertEqual(payload["detail"], json.dumps(upstream, separators=(",", ":")))
        self.assertEqual(payload["message"], "JobAdder error: 503")
        self.assertEqual(payload["code"], "JOBADDER_REQUEST_FAILED")
        self.assertTrue(payload["retryable"])
        self.assertEqual(payload["action"], "retry")
        self.assertEqual(payload["request_id"], "phase3-ja-error")
        self.assertFalse(payload["ok"])

    def test_jobadder_raw_get_refreshes_once_and_pagination_shape_is_stable(self):
        expired_url = "https://api.jobadder.com/v2/candidates/fixture"
        requests_seen = []
        expired_error = _http_error(expired_url, 401, {"error": "expired"})

        def open_with_refresh(request_object, timeout):
            requests_seen.append((request_object, timeout))
            if len(requests_seen) == 1:
                raise expired_error
            return _FakeResponse(
                b"fixture-bytes",
                headers={"Content-Type": "application/octet-stream", "Content-Disposition": "fixture.bin"},
            )

        with mock.patch.object(
            app,
            "_ja_refresh_access_token",
            side_effect=["<fixture-credential-a>", "<fixture-credential-b>"],
        ), mock.patch.object(
            app, "_ja_api", side_effect=lambda path: "https://api.jobadder.com/v2/" + path
        ), mock.patch.object(app.urllib.request, "urlopen", side_effect=open_with_refresh):
            raw, content_type, disposition = app._spider_get_ja_raw(
                "<fixture-credential-a>", "candidates/fixture", timeout=12
            )
        expired_error.close()
        self.assertEqual((raw, content_type, disposition), (b"fixture-bytes", "application/octet-stream", "fixture.bin"))
        self.assertEqual(len(requests_seen), 2)
        self.assertEqual(requests_seen[0][0].get_header("Authorization"), "Bearer <fixture-credential-a>")
        self.assertEqual(requests_seen[1][0].get_header("Authorization"), "Bearer <fixture-credential-b>")
        self.assertEqual([item[1] for item in requests_seen], [12, 12])

        page_payloads = [
            {"items": [{"fixture_key": "a"}, {"fixture_key": "b"}], "totalCount": 3},
            {"items": [{"fixture_key": "c"}], "totalCount": 3},
        ]
        with mock.patch.object(
            app,
            "_spider_get_ja_raw",
            side_effect=[
                (json.dumps(page_payloads[0]).encode("utf-8"), "application/json", ""),
                (json.dumps(page_payloads[1]).encode("utf-8"), "application/json", ""),
            ],
        ) as page_get:
            items, metadata = app._spider_jobadder_keyword_items(
                "<fixture-credential>",
                "fixture query",
                max_items=3,
                page_size=2,
                location="Fixture City",
                embed=False,
            )
        self.assertEqual(items, page_payloads[0]["items"] + page_payloads[1]["items"])
        self.assertEqual(
            metadata,
            {
                "keyword": "fixture query",
                "location": "Fixture City",
                "scanned": 3,
                "reported_total": 3,
                "pages": 2,
                "truncated": False,
                "incomplete": False,
                "warnings": [],
                "embed_applied": False,
                "embed_rejected": False,
            },
        )
        self.assertIn("Limit=2", page_get.call_args_list[0].args[1])
        self.assertIn("Offset=0", page_get.call_args_list[0].args[1])
        self.assertIn("Limit=1", page_get.call_args_list[1].args[1])
        self.assertIn("Offset=2", page_get.call_args_list[1].args[1])

    def test_microsoft_graph_helpers_and_onenote_route_shapes(self):
        calls = []

        def open_graph(request_object, timeout, context=None):
            calls.append((request_object, timeout, context))
            if request_object.full_url.endswith("/content"):
                return _FakeResponse(
                    "<html><body><p>Fixture page</p></body></html>",
                    headers={"Content-Type": "text/html; charset=utf-8"},
                )
            return _FakeResponse({"value": [{"title": "Fixture page"}]})

        with mock.patch.object(app, "_ms_graph_token", return_value="<fixture-credential>"), mock.patch.object(
            app.urllib.request, "urlopen", side_effect=open_graph
        ):
            listing = app._ms_graph_json(
                "me/onenote/pages",
                params={"$top": "1", "$select": "id,title"},
                timeout=23,
            )
            body, content_type = app._ms_graph_bytes(
                "me/onenote/pages/fixture/content", timeout=24
            )
        self.assertEqual(listing, {"value": [{"title": "Fixture page"}]})
        self.assertEqual(body, b"<html><body><p>Fixture page</p></body></html>")
        self.assertEqual(content_type, "text/html; charset=utf-8")
        self.assertEqual([item[1] for item in calls], [23, 24])
        self.assertIn("%24top=1", calls[0][0].full_url)
        self.assertEqual(calls[0][0].get_header("Authorization"), "Bearer <fixture-credential>")

        with mock.patch.object(
            app,
            "_ms_graph_json",
            return_value={"value": [{"id": "fixture-page", "title": "Fixture page"}]},
        ):
            response = self.client.get(
                "/onenote/pages?top=1",
                headers=self._headers("phase3-ms-success"),
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {"items": [{"id": "fixture-page", "title": "Fixture page"}], "raw_count": 1},
        )

        graph_url = "https://graph.microsoft.com/v1.0/me/onenote/pages"
        graph_error = _http_error(graph_url, 503, {"error": {"code": "serviceUnavailable"}})
        with mock.patch.object(
            app,
            "_ms_graph_json",
            side_effect=graph_error,
        ):
            response = self.client.get(
                "/onenote/pages?top=1",
                headers=self._headers("phase3-ms-error"),
            )
        graph_error.close()
        payload = response.get_json()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(payload["error"], "Microsoft OneNote pages failed")
        self.assertEqual(payload["status"], 503)
        self.assertIn("serviceUnavailable", payload["detail"])
        self.assertEqual(payload["code"], "ONENOTE_REQUEST_FAILED")
        self.assertEqual(payload["request_id"], "phase3-ms-error")
        self.assertTrue(payload["retryable"])

    def test_ai_provider_dispatch_and_normalized_response_shapes(self):
        payload = {
            "model": "fixture-model",
            "max_tokens": 32,
            "messages": [{"role": "user", "content": "fixture prompt"}],
        }
        anthropic_response = {
            "content": [{"type": "text", "text": "fixture answer"}],
            "usage": {"input_tokens": 7, "output_tokens": 3},
        }
        with mock.patch.object(
            app.urllib.request,
            "urlopen",
            return_value=_FakeResponse(anthropic_response),
        ) as opened:
            result = app.call_llm("anthropic", "<fixture-credential>", payload)
        self.assertEqual(result["content"], anthropic_response["content"])
        self.assertEqual(
            result["usage"],
            {
                "input_tokens": 7,
                "output_tokens": 3,
                "prompt_cache_hit_tokens": 0,
                "prompt_cache_miss_tokens": 0,
                "api_calls": 1,
            },
        )
        request_object = opened.call_args.args[0]
        self.assertEqual(request_object.full_url, "https://api.anthropic.com/v1/messages")
        self.assertEqual(request_object.get_header("X-api-key"), "<fixture-credential>")
        self.assertEqual(opened.call_args.kwargs["timeout"], 180)

        openai_response = {
            "output": [
                {"type": "message", "content": [{"type": "output_text", "text": "fixture GPT answer"}]}
            ],
            "usage": {"input_tokens": 11, "output_tokens": 4},
        }
        with mock.patch.object(
            app.urllib.request,
            "urlopen",
            return_value=_FakeResponse(openai_response),
        ):
            result = app.call_llm("openai", "<fixture-credential>", payload)
        self.assertEqual(result["content"], [{"type": "text", "text": "fixture GPT answer"}])
        self.assertEqual(result["usage"]["input_tokens"], 11)
        self.assertEqual(result["usage"]["output_tokens"], 4)
        self.assertEqual(result["usage"]["api_calls"], 1)

        with self.assertRaises(app._LLMProviderNoWebSearch):
            app.call_llm(
                "deepseek",
                "<fixture-credential>",
                dict(payload, tools=[{"type": "web_search_20250305"}]),
            )

    def test_existing_error_redaction_masks_external_credentials(self):
        message = app._cvstudio_safe_error_message(
            "Authorization: Bearer <fixture-credential> "
            "access_token=<fixture-credential> client_secret=<fixture-credential>"
        )
        self.assertNotIn("<fixture-credential>", message)
        self.assertIn("Bearer [redacted]", message)
        self.assertIn("access_token=[redacted]", message)
        self.assertIn("client_secret=[redacted]", message)


def tearDownModule():
    _MODULE_TEMPORARY.cleanup()


if __name__ == "__main__":
    unittest.main()
