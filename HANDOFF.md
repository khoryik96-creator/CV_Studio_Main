# CV Studio — Collaboration / Handoff Notes

Read this before making changes. CV Studio is a Flask **modular monolith**
(single `app.py`, ~22k lines, currently **v24.6.246**). The owner runs a **local
source build** at `localhost:5000` and uses **DeepSeek** for all AI providers.
Several conventions below are non-obvious traps that the code alone won't warn
you about.

## 1. Sealed route contract — the most important invariant

`app.py` ends with `_finalize_modular_monolith_app(...)`, which hard-asserts at
import time:

- `expected_route_count = 116`
- `expected_route_contract_sha256 = "855e04d56c550c35739c70d2dc8d35fc9d2b37d35f76453b7f3d472cf702d18e"`
- 5 before-request guards, in this exact order:
  `_assign_cvstudio_request_id`, `_reject_declared_oversize_request`,
  `_reject_non_local_host_header`, `_require_ai_spend_browser_session`,
  `_reject_cross_site_unsafe_request`
- `MAX_CONTENT_LENGTH = 80 MiB`

If you add, remove, or rename **any** route, the app refuses to boot until you
recompute the SHA and bump the count in `app.py` **and** in the ~12 test files
that pin `116` / the SHA (`tests/test_phase7a_*`, `tests/test_phase5b_*`, etc.).
If you are not touching routes, leave all of this alone.

## 2. Architecture and module extractions

`cvstudio_architecture.py` owns application construction and the module
registry. Extracted modules (`cvstudio_*.py`, `salary_comparison/`) **must never
`import app`** — this is enforced by
`tests/test_phase7a_modular_monolith_foundation.py`. When you add a module,
register it there and in `owner_build_tools/build_protected.py` (the `required`
tuple **and** the `py_compile` preflight). Extractions should be
behavior-preserving and hold the route SHA constant.

## 3. CI is currently unavailable — verify locally

GitHub Actions runners fail at provisioning (the owner hit their billing/quota);
jobs die in under 20s with `runner_id: 0`. Do **not** wait on CI — verify
locally:

```bash
python -m venv .venv_test
.venv_test/bin/pip install flask pytest python-docx olefile reportlab beautifulsoup4 pypdf requests
SALARY_COMPARISON_DATA_DIR=/tmp/sal/data .venv_test/bin/python -m pytest tests/ -q
```

Expected result: **1 known failure** —
`test_legacy_doc_requires_and_uses_verified_antiword` (the Antiword binary is
not functional on Linux; it is a Windows-only runtime). Everything else must
pass (~388 tests). **Do not commit `.venv_test/`** — it is not gitignored, so
stage files explicitly and never `git add .`.

## 4. Git workflow

- Develop on your designated branch; commit and push there.
- **Only open a pull request when the owner explicitly asks.**
- End commit messages with the `Co-Authored-By: Claude ...` and
  `Claude-Session:` trailers.
- After a PR merges (squash), that branch is finished — restart it from
  `origin/master`; do not stack new commits on already-merged history.
- The squash-merge commit shows as "Unverified" because GitHub authors it. That
  is normal — never amend or rebase merged `master` history to "fix" it.

## 5. Install-receipt version trap

`app.py` enforces an install receipt at import
(`_enforce_install_receipt_or_exit`). If you bump the version, it must change
**consistently** across `app.py`, `INSTALL_CORE.ps1`, `INSTALL_RECEIPT.ps1`,
`install.sh` / `start.sh`, and the on-disk receipt — otherwise the app
`SystemExit`s at startup. A past bump was reverted for exactly this. Windows
batch/VBS files are CRLF-only with no BOM (the build validates this); write them
in binary mode preserving CRLF.

## 6. AI specifics

- DeepSeek V4 defaults to "thinking" mode, which causes 30–160s latency. CV
  Studio disables it via `thinking: {"type": "disabled"}` in `_call_deepseek`.
- AI keys live in a machine-bound secret store (`_ai_secret_store`, slots such
  as `main_deepseek`, `main_anthropic`). Resolve them **server-side** with
  `_resolve_request_api_key(...)` — **never send provider keys to the browser.**
- Paid AI routes must be listed in `_AI_SPEND_EXACT_PATHS` so they require the
  AI-spend browser-session token.

## 7. Recently completed (already on `master`)

- **Salary Comparison** fully integrated (PRs #33, #34): self-contained
  `salary_comparison/` blueprint at `/salary-comparison/`, reuses saved AI keys
  server-side, dedicated "Salary Comparison — Tax rules" AI route, and a
  "Salary" nav tab. Route contract re-baselined 108 → 116.
- **AI Crawler** fixes (#30–#32): DeepSeek thinking-mode latency, undecodable
  legacy `.doc` per-candidate skip, per-query timeout raised to 420s.
- **Phase 7B** modularization stack (#23–#28).

## 8. Open / deferred work

- **AI Crawler ".doc: flag, don't decode"**: skip decoding an undecodable legacy
  `.doc` while still surfacing the candidate. Deferred pending measurement of
  whether `.doc` decode vs. PDF OCR is the real bottleneck; a naive attempt
  broke a ~900-line characterization test and was reverted.
- **Phase 7B modularization** can continue: extract pure clusters, keep it
  behavior-preserving, hold the route SHA constant.

## Coordinating two accounts

- Only one account should hold a given feature branch at a time — agree who owns
  which branch before starting, and always `git fetch` + rebase onto the latest
  `origin/master` before new work so you don't diverge.
- Keep this file current: when a deferred item is finished or a new trap is
  found, update section 7/8.

### Current work split (two concurrent accounts)

Every modularization extraction touches `app.py`, `cvstudio_architecture.py`,
and `tests/test_phase7a_modular_monolith_foundation.py`, so the two accounts
take domains in **non-overlapping `app.py` regions** and never share a branch.

| Account | Domain | New module | app.py region | Branch prefix |
|---------|--------|-----------|---------------|---------------|
| **Einstein** | PPC (Post Placement Care) — pure `_ppc_*` helpers + `/ppc/outlook/*` pure logic | `cvstudio_ppc.py` | ~3,980–4,300 and ~21,660–21,850 | `einstein/*` |
| **Claude** | Lead Finder enrichment — pure `_lead_*` URL/company/email/verification helpers | `cvstudio_lead_enrich.py` | ~16,200–19,300 | `claude/*` |

Rules while both are active:
1. Separate branches — never commit to the other account's branch.
2. `git fetch` + rebase onto `origin/master` before starting and before every push.
3. One domain each until merged; do not both edit the same `app.py` region.
4. Whoever merges second rebases and resolves the small conflict in
   `cvstudio_architecture.py` (the `DEFAULT_MODULES` tuple + `legacy_web_shell`
   deps) and the phase7a names tuple. The route SHA does **not** move for pure
   extractions, so the route-contract test files stay untouched.
5. Update this table when a domain lands or a new one is picked up.

### Backlog and claim protocol (what to do next)

When you finish your current domain, **claim the next unclaimed item below**
(edit its row to `CLAIMED by <account> <date>`), branch, rebase on
`origin/master`, and go. Do not start a domain already claimed by the other
account, and do not both work the same `app.py` region at once. Every item
follows the same recipe (HANDOFF §2): characterization tests first, move the
cluster, register in `cvstudio_architecture.py` + `build_protected.py`, keep the
route SHA `855e04d5…` constant, verify locally.

Two shapes of extraction:
- **Pure-helper closure** (easiest): a set of functions using only stdlib/other
  helpers, no Flask/app/network. Move them to `cvstudio_*.py`; `app.py`
  re-exports. Use an AST dependency-closure pass to find an exact self-contained
  set (see how `cvstudio_lead_enrich.py` was scoped).
- **Service module** (Graph/stateful): keep the Flask routes in `app.py`, move
  the handler bodies into a service class that receives its dependencies through
  explicit callbacks (see `cvstudio_secrets.py`, `cvstudio_jobadder_*.py`). Used
  when the code touches MS Graph, the secret store, or request state.

Prioritized backlog:

| Domain | Region | Shape | Suggested owner | Status |
|--------|--------|-------|-----------------|--------|
| PPC (Post Placement Care) | ~3,980–4,300 + ~21,660–21,850 | pure + service | Einstein | in progress |
| Lead Finder enrichment (URL/company) | ~15,750–19,600 | pure closure | Claude | slice 1 merged/queued; more `_lead_*` slices remain |
| **OneNote domain** (Graph + desktop-COM handlers) | ~4,270–4,900 | service module | **Einstein (next)** | unclaimed — same MS-Graph shape as PPC's Outlook work |
| Spider / AI Crawler enrichment (`_spider_*`) | ~9,880–11,600 | pure closure | Claude (later) | ⚠️ has the .doc/OCR characterization-test minefield; tests-first is mandatory |
| Core CV/AI pipeline pure helpers (`/parse`, `/generate-ai`, DOCX mapping) | ~15,300–21,600 | pure closure | either (last) | most sensitive; scope carefully, extract last |

Notes:
- Lead Finder still has ~74 `_lead_*` helpers beyond the first URL/company
  slice (search-provider result parsing, title-angle logic, contact/email
  helpers). Claude keeps taking those slices, so Einstein should stay out of the
  ~15,750–19,600 region.
- OneNote's `_onenote_*` helpers hit MS Graph / the OneNote desktop app, so they
  are a service-module extraction, not a pure closure — the same pattern PPC's
  `/ppc/outlook/*` handlers use.
