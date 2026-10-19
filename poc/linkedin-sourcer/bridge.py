"""Standalone loopback bridge. Does not start, import or alter CV Studio."""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import hmac
from pathlib import Path
import re
import secrets
import threading
import time
import uuid

from flask import Flask, jsonify, render_template, request

from provider import (DeepSeek, PLAN_SCHEMA, REVIEW_SCHEMA, SourcerError, clean_profiles,
                      validate_plan, validate_reviews)

MODES = {"standard", "lite", "recruiter"}


@dataclass
class Run:
    brief: str
    mode: str
    max_pages: int
    max_calls: int
    model: str
    id: str = field(default_factory=lambda: secrets.token_hex(16))
    calls: int = 0
    tokens: int = 0
    usage_complete: bool = True
    stopped: bool = False
    expires: float = field(default_factory=lambda: time.monotonic() + 3600)
    busy: threading.Lock = field(default_factory=threading.Lock)

    def summary(self):
        return {"id": self.id, "calls": self.calls, "max_calls": self.max_calls,
                "tokens": self.tokens, "usage_complete": self.usage_complete,
                "stopped": self.stopped, "max_pages": self.max_pages}


def create_app(provider=None, pair_code=None):
    app = Flask(__name__, template_folder=str(Path(__file__).parent))
    app.config.update(MAX_CONTENT_LENGTH=650000)
    provider = provider or DeepSeek()
    pair_code = pair_code or secrets.token_urlsafe(32)
    state = {"run": None}
    lock = threading.Lock()
    app.extensions["sourcer"] = {"pair_code": pair_code, "state": state}

    @app.before_request
    def guard():
        # Exact loopback host prevents DNS rebinding. Origin is checked as well
        # as the unguessable pairing token; a public page cannot use this bridge.
        if request.host.split(":")[0] != "127.0.0.1":
            return jsonify(error="Use the local POC address."), 403
        origin = request.headers.get("Origin", "")
        if origin and not re.fullmatch(r"chrome-extension://[a-p]{32}", origin):
            return jsonify(error="Only the paired browser extension can use this bridge."), 403
        if request.path.startswith("/api/"):
            supplied = request.headers.get("Authorization", "")
            if not supplied.isascii() or not hmac.compare_digest(supplied, "Bearer " + pair_code):
                return jsonify(error="Pair the extension with the code on the local welcome page."), 401
            if request.method == "POST" and not request.is_json:
                return jsonify(error="A JSON request is required."), 415

    @app.after_request
    def headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'unsafe-inline'; frame-ancestors 'none'"
        return response

    @app.errorhandler(SourcerError)
    def problem(error):
        return jsonify(error=str(error), request_id=uuid.uuid4().hex), 400

    @app.errorhandler(413)
    def oversized(_):
        return jsonify(error="This page is too large for the POC. Nothing was sent to DeepSeek."), 413

    def body():
        value = request.get_json(silent=True)
        if not isinstance(value, dict):
            raise SourcerError("The request is invalid.")
        return value

    def current(data):
        run = state["run"]
        if run is None or data.get("run_id") != run.id:
            raise SourcerError("This run is no longer available. Start a new search.")
        if run.stopped or time.monotonic() >= run.expires:
            raise SourcerError("The run has stopped or expired.")
        return run

    def paid(run, task, schema, data):
        if not run.busy.acquire(blocking=False):
            raise SourcerError("A DeepSeek request is already in progress. Wait for it to finish.")
        try:
            with lock:
                if run.stopped or run.calls >= run.max_calls or time.monotonic() >= run.expires:
                    raise SourcerError("The run stopped or reached its request/time limit.")
                run.calls += 1  # Reserve before transport; ambiguous calls consume the budget.
            try:
                value, tokens = provider.call(run.model, run.brief, task, schema, data)
            except Exception:
                run.usage_complete = False
                raise
            if tokens is None:
                run.usage_complete = False
            else:
                run.tokens += tokens
            if run.stopped:
                raise SourcerError("Stopped. The in-flight request finished, and no next action was taken.")
            return value
        finally:
            run.busy.release()

    @app.get("/")
    def welcome():
        return render_template("welcome.html", pair_code=pair_code,
                               extension_path=str(Path(__file__).parent / "extension"))

    @app.get("/health")
    def health():
        return jsonify(product="CVStudioSourcerPOC")

    @app.get("/api/status")
    def status():
        return jsonify(configured=bool(provider.key_loader()), model="deepseek-flash",
                       run=state["run"].summary() if state["run"] else None)

    @app.post("/api/start")
    def start():
        data = body()
        brief = data.get("brief")
        mode = data.get("mode")
        pages, calls = data.get("max_pages"), data.get("max_calls")
        if data.get("confirm_paid") is not True:
            raise SourcerError("Confirm the DeepSeek API use and profile-data sharing before starting.")
        if (not isinstance(brief, str) or not 5 <= len(brief.strip()) <= 4000
                or not isinstance(mode, str) or mode not in MODES):
            raise SourcerError("Enter a profile brief and select a supported LinkedIn mode.")
        if (type(pages) is not int or not 1 <= pages <= 15
                or type(calls) is not int or not 1 <= calls <= 80):
            raise SourcerError("Use 1–15 pages and 1–80 API requests.")
        if not provider.key_loader():
            raise SourcerError("Save your DeepSeek key in CV Studio Settings first.")
        with lock:
            previous = state["run"]
            if previous and (previous.busy.locked() or (not previous.stopped and time.monotonic() < previous.expires)):
                raise SourcerError("Stop the current run before starting another.")
            run = Run(brief.strip(), mode, pages, calls, "deepseek-flash")
            state["run"] = run
        return jsonify(run=run.summary())

    @app.post("/api/plan")
    def plan():
        data = body()
        run = current(data)
        value = paid(run, "search_plan", PLAN_SCHEMA, {"mode": run.mode})
        return jsonify(plan=validate_plan(value), run=run.summary())

    @app.post("/api/review")
    def review():
        data = body()
        run = current(data)
        profiles = clean_profiles(data.get("profiles"))
        stage = data.get("stage")
        page = data.get("page")
        if (not isinstance(stage, str) or stage not in {"screen", "detail"}
                or type(page) is not int or not 1 <= page <= run.max_pages):
            raise SourcerError("The page or review stage is invalid.")
        maximum = 5 if stage == "screen" else len(profiles)
        value = paid(run, "profile_review", REVIEW_SCHEMA,
                     {"stage": stage, "maximum_candidates": maximum, "profiles": profiles,
                      "instruction": "Select up to five most promising profiles to inspect." if stage == "screen"
                                     else "Assess only the observed profile detail. List missing requirements explicitly."})
        return jsonify(candidates=validate_reviews(value, profiles, maximum), run=run.summary())

    @app.post("/api/stop")
    def stop():
        data = body()
        with lock:
            run = state["run"]
            if run is None or data.get("run_id") != run.id:
                raise SourcerError("This run is no longer available.")
            run.stopped = True
        return jsonify(run=run.summary())

    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LinkedIn Sourcer POC loopback bridge")
    parser.add_argument("--port", type=int, default=5073)
    options = parser.parse_args()
    if not 1024 <= options.port <= 65535:
        parser.error("Choose a port between 1024 and 65535.")
    import logging
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    print(f"LinkedIn Sourcer POC: http://127.0.0.1:{options.port}/", flush=True)
    create_app().run(host="127.0.0.1", port=options.port, debug=False, use_reloader=False)
