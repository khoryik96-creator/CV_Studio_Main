"""Exercise real protected frontend bytes with fictional, in-browser API replies.

No CV Studio instance, user storage or provider connection is used. --zip checks
an already built colleague archive; otherwise build fresh protected web assets.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile
from urllib.parse import urlparse
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def check(assets: Path, executable: str | None = None) -> None:
    from playwright.sync_api import sync_playwright

    configured: dict[str, bool] = {}
    settings: dict[str, str] = {}
    requests: list[tuple[str, dict]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=executable)
        page = browser.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def respond(route):
            request = route.request
            path = urlparse(request.url).path
            relative = "index.html" if path == "/" else path.lstrip("/")
            candidate = (assets / relative).resolve()
            if candidate.is_relative_to(assets.resolve()) and candidate.is_file():
                route.fulfill(path=str(candidate))
                return
            if path.startswith("/vendor/"):
                route.fulfill(status=404, body="Missing fixture asset")
                return
            payload = json.loads(request.post_data or "{}")
            requests.append((path, payload))
            result = {}
            if path == "/secure-secrets/save":
                for slot, value in payload.get("secrets", {}).items():
                    configured[slot] = bool(value)
                result = {"configured": configured}
            elif path == "/secure-secrets/info":
                result = {"configured": configured}
            elif path == "/test":
                result = {"ok": True, "provider": payload["provider"], "model": "deepseek-v4-flash" if payload["provider"] == "deepseek" else "claude-sonnet-4-6", "cost_usd": 0}
            elif path == "/parse":
                # Stop before DOCX generation: this check verifies the paid
                # boundary receives the saved slot, without doing any AI work.
                result = {"error": "Fictional parse boundary reached"}
            elif path.startswith("/storage/browser-settings/"):
                settings.update(payload.get("settings", {}))
                for key in payload.get("keys", []):
                    settings.pop(key, None)
                result = {"ok": True, "settings": settings}
            elif path == "/job-leads/list":
                result = {"ads": [], "total": 0}
            elif path == "/ping":
                route.fulfill(status=204)
                return
            route.fulfill(json=result)

        # Every request is fulfilled locally. No external request is permitted.
        page.route("**/*", respond)
        page.goto("http://127.0.0.1:58382/", wait_until="networkidle")
        page.evaluate("toggleSettings()")
        assert page.locator('[id^="routeSel_"]').count() == 14
        page.evaluate("showSettingsTab('api')")
        for provider in ("anthropic", "deepseek"):
            page.select_option("#mainProviderSel", provider)
            page.fill("#keyInput", "fictional-protected-fixture-key")
            page.locator('button[onclick="saveKey()"]').click()
            page.wait_for_function("getKey() === '__BACKEND_SECURE__' && document.getElementById('keyInput').value === ''")
            with page.expect_response("**/test"):
                page.locator("#btnTest").click()
            page.wait_for_function("!document.getElementById('btnTest').disabled")
            assert "Key is valid" in page.locator("#toast").inner_text()
            assert any(path == "/test" and body.get("api_key_slot") == "main_" + provider for path, body in requests)
        page.evaluate("showSettingsTab('routing')")
        page.select_option("#routeSel_cv_single", "deepseek")
        page.evaluate("saveAiRoutes()")
        page.wait_for_function("localStorage.getItem('hy_ai_route_cv_single') === 'deepseek'")
        # A new page load must recover the backend-held key, not depend on the
        # plaintext key that was in memory while the Save button ran.
        page.evaluate("_phase2bSettingsWriteQueue")
        page.evaluate("localStorage.clear()")
        page.reload(wait_until="networkidle")
        page.wait_for_function("getKey() === '__BACKEND_SECURE__'")
        route = page.evaluate("aiRoutePayload('cv_single')")
        assert route["provider"] == "deepseek" and route["api_key_slot"] == "main_deepseek"
        assert route["api_key"] == "__BACKEND_SECURE__"
        assert page.evaluate("getFeatureRouteSource('cv_single')") == "deepseek"
        page.evaluate("_activeInputTab='paste';document.getElementById('cvInput').value='Fictional Candidate\\nInfrastructure Engineer';document.getElementById('singleSummaryToggle').checked=false")
        page.evaluate("startFormat(false)")
        assert any(path == "/parse" and body.get("api_key_slot") == "main_deepseek" and body.get("api_key") == "__BACKEND_SECURE__" for path, body in requests)
        page.evaluate("cvDoctor.open()")
        # Doctor report is a textarea; find it by its diagnostic header below.
        diagnostic = page.evaluate("Array.from(document.querySelectorAll('textarea')).map(x=>x.value).find(x=>x.includes('AI routes (provider / model / key)')) || ''")
        assert "cv_single = deepseek / deepseek-v4-flash / key:SET" in diagnostic
        assert not errors, errors
        assert "fictional-protected-fixture-key" not in diagnostic
        browser.close()
    print("Protected frontend passed: routing, key save/reload/Test, Format payload and Doctor; no live API calls.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets", type=Path)
    parser.add_argument("--zip", type=Path)
    parser.add_argument("--chromium")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="cvstudio-protected-ui-") as folder:
        temporary = Path(folder)
        if args.zip:
            # Read only known UI assets; never execute or unpack the native app.
            with zipfile.ZipFile(args.zip) as archive:
                for entry in archive.namelist():
                    marker = "/runtime/native/"
                    if marker not in entry:
                        continue
                    relative = entry.split(marker, 1)[1]
                    destination = (temporary / relative).resolve()
                    if not destination.is_relative_to(temporary.resolve()):
                        raise ValueError("Unsafe archive path")
                    if relative == "index.html" or relative.startswith("vendor/") and not entry.endswith("/"):
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        destination.write_bytes(archive.read(entry))
            assets = temporary
        elif args.assets:
            assets = args.assets.resolve()
        else:
            from owner_build_tools.build_protected import protect_javascript
            protect_javascript(ROOT, temporary, False)
            assets = temporary
        check(assets, args.chromium)


if __name__ == "__main__":
    main()
