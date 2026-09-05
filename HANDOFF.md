# CV Studio — Collaboration / Handoff Notes

**Read this first, before making any change — this file is the front door for
every contributor (human or AI).** CV Studio is a Flask **modular monolith**
(single `app.py`, ~13k lines; current release is in the repo-root `VERSION`
file). The owner runs a **local source build** at `localhost:5000` and uses
**DeepSeek** for all AI providers. Several conventions below are non-obvious
traps that the code alone won't warn you about.

**Reading order:**
1. **This file (`HANDOFF.md`)** — the durable rules: the sealed route contract,
   the version-bump trap, the local test recipe, and the work-split (who owns
   what). Everyone reads it first, every time.
2. **Your domain's deep-dive** — for CV formatting work, `FORMATTING_NOTES.md`.
3. **GitHub issue #35** (🤝 Multi-Agent Coordination Log) — the *live* log of
   who is touching what *right now*. Post your claim there before editing code.

## 1. Sealed route contract — the most important invariant

`app.py` ends with `_finalize_modular_monolith_app(...)`, which hard-asserts at
import time:

- `expected_route_count = 118`
- `expected_route_contract_sha256 = "42768445b8fe97e48688238c02bebf5abce0251befc3d212c2d2b029911f7862"`
- 5 before-request guards, in this exact order:
  `_assign_cvstudio_request_id`, `_reject_declared_oversize_request`,
  `_reject_non_local_host_header`, `_require_ai_spend_browser_session`,
  `_reject_cross_site_unsafe_request`
- `MAX_CONTENT_LENGTH = 80 MiB`

If you add, remove, or rename **any** route, the app refuses to boot until you
recompute the SHA and bump the count in `app.py` **and** in the ~12 test files
that pin `118` / the SHA (`tests/test_phase7a_*`, `tests/test_phase5b_*`, etc.).
If you are not touching routes, leave all of this alone.

## 2. Architecture and module extractions

`cvstudio_architecture.py` owns application construction and the module
registry. Extracted modules (`cvstudio_*.py`, `salary_comparison/`) **must never
`import app`** — this is enforced by
`tests/test_phase7a_modular_monolith_foundation.py`. When you add a module,
register it there and in `owner_build_tools/build_protected.py` (the `required`
tuple **and** the `py_compile` preflight). Extractions should be
behavior-preserving and hold the route SHA constant.

## 3. CI and local verification

Regression CI is configured for pull requests and the exact commit pushed to
`master`; runner provisioning can still fail when the account's Actions
spending limit is exhausted, so the complete local gate remains mandatory. The
expensive protected-package workflow is deliberately **manual-only** and runs
only when the owner chooses **Run workflow**; pull requests never start it
automatically. Continue to verify locally before pushing so CI is a second,
independent gate rather than the first place a regression is discovered:

```bash
python -m venv .venv_test
.venv_test/bin/pip install flask pytest python-docx olefile reportlab beautifulsoup4 pypdf requests openpyxl
npm install   # generate.js needs adm-zip; without node_modules the /generate-docx
              # DOCX-render tests (test_bullet_nesting, test_long_cv_output_corrective,
              # the phase2a support-bundle regression) all 500 and look like breakage.
SALARY_COMPARISON_DATA_DIR=/tmp/sal/data .venv_test/bin/python -m pytest tests/ -q
```

Expected Linux result: **1 known failure** —
`test_legacy_doc_requires_and_uses_verified_antiword` (the Antiword binary is
not functional on Linux; it is a Windows-only runtime — the app correctly
returns 424 rather than trusting an unverified extraction). A verified Windows
x64 environment currently passes **982 tests, 4 skipped, 96 subtests**.
**Do not commit `.venv_test/`** (or
`node_modules/`). Both paths are gitignored, but keep generated dependency
trees out of commits and continue staging source files explicitly rather than
using `git add .`.

**Previewing CV formatting without a browser/Word.** Most formatting work is
deterministic (reconcile + normalize + `generate.js`), so you rarely need to
install and open a `.docx`. Two loops:
- **Logic/structure bugs:** reproduce directly against the pure functions in a
  pytest (e.g. feed a bullet list to `_normalize_cv_bullet_items`) — seconds, no
  AI, no Word. This is how the "Key responsibilities" orphan-label bug was found
  and fixed.
- **Eyeball the rendered output:** `python preview_format.py parsed.json` renders
  the CV through the real `/generate-docx` pipeline and prints it as text, with
  `•` marking real bullets and no marker for headings — so a stray-bullet-vs-
  heading issue is visible in the terminal. Pass a second arg to also write the
  `.docx`. Feed it the `data` object from a real `/parse` response (captured
  once) to iterate offline with no repeated AI cost.

## 4. Git workflow

- **Branch naming: `<party>/v<version>`** — encode who owns it and the version
  it targets, e.g. `einstein/v24.6.275`, `chatgpt/v24.6.276`, `king/v24.6.277`.
  Einstein's branches say `einstein`, ChatGPT's say `chatgpt`, king's say `king`,
  each with the version. A short suffix is fine (`einstein/v24.6.275-ja-activity`).
- Develop on your own branch; commit and push there. One party per branch.
- **Only open a pull request when the owner explicitly asks.**
- End commit messages with the `Co-Authored-By: Claude ...` and
  `Claude-Session:` trailers.
- After a PR merges (squash), that branch is finished — restart it from
  `origin/master`; do not stack new commits on already-merged history.
- The squash-merge commit shows as "Unverified" because GitHub authors it. That
  is normal — never amend or rebase merged `master` history to "fix" it.

## 5. Install-receipt version trap — bump via `VERSION`, never by hand

**The repository-root `VERSION` file is the single source of truth** for the
current release (bare `M.N.P`, e.g. `24.6.270`). To change the version, run:

```bash
python bump_version.py 24.6.271   # writes VERSION and stamps every code surface
python bump_version.py            # re-stamp current VERSION (idempotent; repairs drift)
```

`bump_version.py` regenerates every version surface from `VERSION` using explicit
*anchors* (never a blanket find/replace — `app.py` and `index.html` also contain
*historical* version mentions in comments that must survive). It edits bytes so
the CRLF/BOM of the Windows `*.ps1`/`*.vbs`/`*.bat` files is preserved (the build
validates this). `tests/test_version_single_source.py` fails the suite if any
surface drifts from `VERSION`, sharing the one anchor table with the generator.

Why this matters: `app.py` enforces an install receipt at import
(`_enforce_install_receipt_or_exit`). The version must match **consistently**
across `app.py`, `index.html`, `INSTALL_CORE.ps1`, `INSTALL_RECEIPT.ps1`,
`START_HIDDEN.vbs`, `WATCHDOG.vbs`, `install.sh` / `start.sh`,
`owner_build_tools/BUILD_PROTECTED_WINDOWS.bat`, `build_protected.py` (its
`VERSION` **and** the underscore `VERSION_SLUG` used in shipped artifact names),
and `tests/test_phase2a_app_cache_integration.py`, or the app `SystemExit`s at
startup / ships a mislabeled build. A past hand-bump was reverted for exactly
this, and the slug silently drifted once (`v24_6_268` vs app `v24.6.270`); the
`VERSION`-file workflow exists to make that impossible.

Historical handover / QA-report docs (filename `..._v24_6_NNN_...`) carry a
"Historical — do not use as the current release reference" banner; the living
process docs (`PHASE_STATUS.md`, `ROADMAP.md`, `AGENTS.md`, etc.) point at
`VERSION`. Do not resurrect a hard-coded "current version: vX" line in any doc.

## 6. AI specifics

- DeepSeek V4 defaults to "thinking" mode, which causes 30–160s latency. CV
  Studio disables it via `thinking: {"type": "disabled"}` in `_call_deepseek`.
- AI keys live in a machine-bound secret store (`_ai_secret_store`, slots such
  as `main_deepseek`, `main_anthropic`). Resolve them **server-side** with
  `_resolve_request_api_key(...)` — **never send provider keys to the browser.**
- Paid AI routes must be listed in `_AI_SPEND_EXACT_PATHS` so they require the
  AI-spend browser-session token.

## 7. Recently completed (already on `master`)

- **Current merged baseline, checked 2026-09-05: v24.6.378, `a5bf89d`.**
  PR #189 merged as `2c216c6` on 2026-08-29; PR #185 merged as `b84c36f` on
  2026-09-04. PR #191 merged as `a5bf89d` on 2026-09-05 after all hosted
  checks passed. Their old branches are not active claims.

- **Anonymization edge-case corrective — v24.6.370 / PR #188, MERGED.**
  PR #188 merged to `master` as `b52b5b0`; all three hosted Windows/macOS jobs
  passed. It covers compact Malaysian `A/P` and `A/L` names, short `M:` / `T:`
  phone labels, source-derived personal domains with newer top-level domains,
  parenthesized single-year employer rows, `Level`-style addresses and
  dot-grouped achievement metrics while protecting dotted technology/file
  names. PR #185 was separate then and has since merged.

- **Summary anonymization safety follow-up — v24.6.369 / PR #187, MERGED.**
  PR #187 merged to `master` as `2f345b7`. The deterministic summary safety
  pass handles Unicode and initialled candidate names, bare personal domains,
  Malaysian unit-style addresses, international/contact-context phone numbers,
  employers written on the same line as their dates, and education acronyms in
  an Education section. Phone detection preserves grouped achievement metrics,
  Blind CV retains every populated source summary bullet, and every successful
  `/generate-ai` fallback passes through the same deterministic anonymization
  finalizer. PR #185 was separate then and has since merged.

- **v24.6.362 Blind CV bullet and native-download corrective:** PR #183 was
  squash-merged to `master` as `809da3e`. Blind CV preserves real Word list
  structure without converting role subheadings into bullets; native
  Formatted/Blind CV destination folders work for single and batch downloads;
  stale product-owned Windows startup registrations can be repaired safely;
  and the final review corrections cover macOS state paths, explicit Word list
  suppression and malformed nested Blind-CV AI output. The route contract is
  intentionally 118. Final validation passed 1017 tests, 4 skipped and 96
  subtests; all 20 frontend fixtures; live source smoke; repository consistency;
  and the Windows protected-source preflight.
- **v24.6.361 CV download folders:** PR #182 was squash-merged to `master` as
  `67defbc`. Settings → Downloads provides separate browser-authorized
  destinations for Formatted CV and Blind CV, covering both single and batch
  downloads. Existing files are safely numbered and unsupported, expired or
  denied folder access visibly falls back to the browser Downloads behavior.
  No route, schema, dependency, credential, AI/external-call, CV-content or
  protected-build-trigger boundary changed.
- **v24.6.360 Blind CV candidate-gender neutralization:** PR #181 was
  squash-merged to `master` as `541cbf3`. General Settings now has an
  off-by-default toggle used only by single and batch Blind CV. Enabled runs
  rewrite candidate-only pronouns to `the candidate` / `the candidate's`
  forms without changing references to other people. Normal Format CV and the
  default Blind CV prompt remain unchanged. No route, schema, dependency,
  credential, paid-call-count or protected-build-trigger boundary changed.
- **v24.6.353 Windows source updater hardening:** PR #171 was squash-merged to
  `master` as `af322db`. `UPDATE.bat` now prevents Git branch names from being
  parsed as `cmd.exe` syntax, refuses to relaunch when the deliberate
  force-stop helper is missing or fails, and propagates the established
  `CV Studio.bat` startup result instead of always reporting success. The
  source-only updater joins the repository's no-BOM/CRLF batch validation,
  with real Windows regressions for branch-name safety and both failure paths.
  It remains a Git-clone convenience and is not added to the protected
  colleague package. No route, schema, dependency, credential, external-call,
  user-data or protected-package-content boundary changed.
- **v24.6.350 salary profile-migration safety corrective:** the startup repair
  now applies only to the exact packaged-default plus empty-list pair created
  by the earlier migration. A valid explicit empty profile list with no
  default remains authoritative and continues using the rule's legacy
  contribution settings. Malformed profile values are left untouched for the
  repository's established handled validation error instead of causing an
  unexpected bootstrap `TypeError`/HTTP 500. No route, schema, dependency or
  protected-package boundary changed.
- **v24.6.349 salary contribution-profile repair:** startup repairs the known
  incomplete packaged-profile shape where a Malaysia Resident rule has the
  packaged default profile name but an empty profile list. The repair copies
  only the matching packaged profile set and leaves brackets, rates, sources,
  notes and other user-approved values unchanged. Same-year one-click AI tax
  updates now preserve the stored contribution/pass profiles, preventing the
  invalid shape from being published again. A mismatched custom default is not
  rewritten. No route, schema, dependency or protected-package boundary
  changed.
- **v24.6.348 KWSP source-access corrective:** the one-click Malaysia tax
  updater uses KWSP's current Mandatory Contribution page instead of the
  obsolete Third Schedule alias. Public KWSP requests carry ordinary
  browser-compatible metadata required by its Cloudflare gate; no challenge,
  cookie, login or private endpoint is used. Resident fallback uses the
  official October-2025 Third Schedule, while Non-Resident fallback uses the
  official non-Malaysian contribution flyer, preventing a fallback from
  suggesting the wrong EPF profile. The actual successful URL is recorded.
  No route, schema, dependency or protected-package boundary changed.
- **v24.6.347 LHDN source reliability corrective:** the one-click Malaysia
  tax updater no longer uses the removed English LHDN tax-rate page. Its
  primary source is the live official `Navigasi HASiL 2026` PDF containing the
  YA2025 resident schedule, with the official 2025 `Sepintas` booklet as a
  registered fallback. Automatic source selection records whichever approved
  URL was actually read, retries only registered official alternatives, and
  still fails clearly when every approved source is unavailable. The stored
  YA2025 resident rule now points to the live LHDN source. No route, schema,
  dependency or protected-package boundary changed.
- **Deeper audit pass (Einstein, 2026-08-08):** found and fixed a real bug
  left over from the "Company – Title | dates" formatting fix (#87):
  `cvstudio_cv_normalize._smart_word_case` never got the vowelless-acronym
  fallback that was added to `generate.js`'s `smartTokenCase`, so a bare
  all-caps brand token not in the explicit keep-list (e.g. `TDCX`) still got
  corrupted to `Tdcx` at the **Python** normalization layer used by
  `_extract_authoritative_work_rows` — before it ever reached the
  already-fixed JS formatter. Mirrored the JS condition in Python; added
  regression coverage in `test_phase7b_cv_normalize_characterization.py`.
  Also fixed a **high-severity salary bug** in
  `cvstudio_ja_salary_notice._ja_calc_fixed_salary_detailed`: the exclusion
  filter (`token["value"] < 1000 and _JA_SALARY_EXCLUDED_COMPONENT_RE...`)
  only rejected excluded components (bonus/commission/EPF/claims/RSU/...)
  **under** 1000, so a large excluded figure like `RM8000 commission` could
  be chosen as the base salary and PUT to JobAdder as the candidate's current
  salary. Now excluded components are rejected regardless of size unless the
  same component carries an explicit base/current/basic/last-drawn label.
  Regression tests in `test_phase7b_ja_salary_notice_characterization.py`.
  v24.6.270.

- **JobAdder `_ja_*` extractions (Einstein, took over from Claude):**
  `cvstudio_salary_parse.py` — pure salary currency/amount parse + format + LLM
  usage/cost helpers (#79). `cvstudio_ja_answers.py` — JobAdder screening-question
  answer builders (presentability/rating payload bundles), pure closure. Both are
  behaviour-preserving verbatim moves; `app.py` re-exports; route SHA held.
  ⚠️ #79 originally shipped **without** registering `cvstudio_salary_parse.py` in
  `cvstudio_architecture.py` / `build_protected.py` / the phase7a names tuple —
  fixed in the `ja_answers` slice. **Lesson: every new module must be added to all
  three (registry, build manifest, phase7a `registry.names`) or the protected
  build silently omits it.**

- **Salary Comparison** fully integrated (PRs #33, #34): self-contained
  `salary_comparison/` blueprint at `/salary-comparison/`, reuses saved AI keys
  server-side, dedicated "Salary Comparison — Tax rules" AI route, and a
  "Salary" nav tab. Route contract re-baselined 108 → 116.
- **AI Crawler** fixes (#30–#32): DeepSeek thinking-mode latency, undecodable
  legacy `.doc` per-candidate skip, per-query timeout raised to 420s.
- **Phase 7B** modularization stack (#23–#28).
- **Install authorization and PDF fallback (v24.6.327–v24.6.330, PRs
  #148–#151):** an existing signed receipt remains valid across in-place
  version updates while staying bound to the machine and extracted folder.
  `/extract-text` recognizes `(cid:N)`/control-code layers and visually sparse
  image/vector PDFs, and every timed browser caller shares one OCR-aware request
  budget. These releases introduced aggregate/document-wide OCR decisions; the
  merged page-aware corrective below supersedes those details.

## 8. Open / deferred work

- **Skill-casing corrective — v24.6.379, ACTIVE AND UNMERGED.** Branch
  `codex/pr192-v24.6.379-preserve-corrected-casing` (PR #192 is provisional;
  no PR opened yet). Source skill separator recovery retains matched provider
  ASCII letter casing instead of restoring the source's lowercase spelling.
  Original separators/symbols and existing content-match guards remain intact.
  Tests reproduce the enabled case through `/parse` and real DOCX generation,
  verify OFF output and protect internal commas, symbols, metrics and dates.
  No route, schema, dependency, credentials or paid-call changes. Await owner
  instructions before PR creation or merge.

- **PR #191 — v24.6.378, MERGED as `a5bf89d`.** Historical PR source branch:
  `claude/pr157-chatgpt-fix-zke4cy`; Codex local review branch:
  `codex/pr191-v24.6.378-review-fixes`. Includes Claude's off-by-default
  language auto-correction (single/batch formatting AND JobAdder Create Profile)
  and Open Folder buttons for all six download destinations. Corrections keep
  the preference on during existing parse retries, reject browser fallback for
  invalid files/requests, and make single/batch download messages accurately
  distinguish folder saves, browser fallback and uncertainty. No extra paid
  calls, schema/route changes, credential changes or native protected build.
  Merged with owner approval. See issue #35 for the completed claim and test results.

- **Anonymization final edge corrective — v24.6.371 / PR #189, MERGED
  as `2c216c6`.** Historical branch
  `chatgpt/pr189-v24.6.371-anonymization-final-edge-fixes` protects dotted
  degree abbreviations from link redaction, records both the complete source
  website path and its hostname, recognizes compact/spaced/lowercase Malaysian
  `A/P` / `A/L` name forms, and masks employers in unparenthesized or
  role-bearing single-year rows. No route, storage schema, dependency,
  credential, paid-call-count, CV-formatting or protected-package boundary
  change. PR #185 was separate at that time. Local validation: 1060 tests
  passed, 4 skipped and 128 subtests; all 20 frontend fixture groups; 24 live
  source-smoke assertions; tracked Python, JavaScript, PowerShell and POSIX-shell
  syntax; repository consistency; Git whitespace; and the Windows
  protected-source/Antiword/Tesseract/adm-zip preflight. Merged 2026-08-29.
- **CV Summary and Blind CV summary anonymization — v24.6.368 / PR
  #186, MERGED.** PR #186 merged to `master` as `fbdf0e7`. Its branch
  `chatgpt/pr186-v24.6.367-summary-anonymization-final-review-fixes` added an off-by-default
  anonymized-output option directly to CV Summary. Its prompt retains supported
  role, technology, qualification, date, metric and achievement detail while
  excluding candidate identity/contact details and named employers, clients,
  products and education institutions. A server-side final safety pass scrubs
  source identifiers and rejects a still-identifying response before the UI can
  label, copy or export it as anonymized. Single and batch Blind CV now promote a
  parsed Summary/Profile/About Him / Her skill section back into
  `summary_bullets`; linked CV Summary bullets are no longer discarded merely
  because Blind CV was selected. DOCX extraction preserves each numbered
  summary textbox paragraph, removes AlternateContent duplicates and orders the
  ABOUT HIM / HER label before its bullets. `/blind` requires the provider to preserve the
  exact populated summary-bullet count, deterministically scrubs direct
  candidate PII plus contextual unknown client/product names, and then runs the
  established organisation safety sweep. Whole-identifier/case-safe matching
  protects ordinary text such as `may` and `commitment`, and provider-returned
  list markers are removed before Word numbering. A
  final corrective makes identifier matching Markdown-aware, redacts labeled
  physical addresses, selects employers rather than roles from dated
  multi-column rows, preserves camel-case technologies such as PowerBI,
  JavaScript and NodeJS, and trims prose before company legal suffixes. The
  PR-review corrective also reads candidate names from mixed name/contact
  headers, masks standalone employers beside vertical work-history date rows,
  redacts unlabeled numbered street addresses, and preserves long uninterrupted
  achievement metrics that do not carry phone context. A
  provider that drops or corrupts the populated summary fails visibly instead
  of publishing a blank About Him / Her box. No route, storage schema,
  dependency, credential, AI-call-count or protected-package boundary change.
  PR #185 was a separate branch at the time and was not included there. Local
  validation: 1045 tests passed, 4 skipped and 96 subtests; all 20 frontend
  fixture groups; 24 live source-smoke assertions; repository consistency,
  Git whitespace and Windows protected-source/dependency preflight.
- **Feature download destinations — PR #185, MERGED as `b84c36f`.**
  Historical branch `chatgpt/pr185-v24.6.364-feature-download-folders` adds
  separate configured destinations for Company Profile, Summary Output, Blind
  JD and The Owl. Merged 2026-09-04; both PR #185 and #189 are now in master.
- **Post-merge review corrective — v24.6.363 / PR #184, MERGED.** PR #184
  merged to `master` as `1912d48`. Its branch
  `chatgpt/pr184-v24.6.363-post-merge-review-fixes` closes
  four findings from the v24.6.362 review. Native saves validate a temporary
  same-folder staging file before atomically publishing the final DOCX name, so
  a crash cannot expose a partial official-looking CV. A lost browser response
  is reported as uncertain and tells the user to check the selected folder
  before retrying, rather than claiming the save failed. Non-object JSON sent
  to `/downloads/folders` receives a handled 400 response instead of a generic
  500. This handoff and `PHASE_STATUS.md` now identify PR #183 as merged. No
  route, schema, dependency, credential, paid-call-count or protected-package
  boundary changes. Final local validation: 1020 tests passed, 4 skipped and 96
  subtests; all 20 frontend fixtures; 24-assertion live source smoke; tracked
  Python/JavaScript/PowerShell syntax; repository consistency; and the Windows
  Antiword/Tesseract/adm-zip protected-source preflight.
- **Updater preflight-output corrective — v24.6.359 / PR #179, MERGED.** PR
  #179 merged to `master` as `a20b7f9`. It keeps the
  downloaded preflight's visible diagnostic output out of the PowerShell
  function return pipeline. `Invoke-Preflight` now returns only the numeric exit
  code, so a real success/error message cannot become a `System.Object[]` and
  crash `Stop-Update` with a disappearing red conversion error. The Windows
  launcher fixture now always emits a realistic preflight diagnostic and seals
  the failure path at exit code 8 with the running server untouched. No route,
  schema, dependency, CV-formatting, credential, external-call or user-data
  boundary changes. Final local validation passed 982 tests, 4 skips and 96
  subtests; hosted jobs did not start because the Actions spending limit was
  exhausted.
- **Updater runtime consistency — v24.6.358 / PR #177, MERGED.** PR #177 merged
  to `master` as `2c06bc5`. It makes update preflight
  and source startup use one shared Python resolver. It accepts only an
  interpreter that has every exact `requirements.txt` version and can import
  the complete runtime set, then startup launches that same resolved
  executable. This prevents a stale first Python from taking the app down after
  a later Python passed preflight, and prevents manual pulls or one-time updater
  transitions from restarting with stale packages. The downloaded preflight is
  self-contained for the one-time v24.6.357 upgrade, before the new runtime
  helper exists in the old checkout, and future updater runs verify that the
  candidate contains the helper before changing source. Focused Windows
  regressions cover exact-version acceptance, rejection and that transition.
  No route, schema, CV
  formatting, credential, external-call or user-data boundary changes. Final
  local validation passed 982 tests, 4 skips and 96 subtests; hosted jobs did
  not start because the Actions spending limit was exhausted.
- **Audit hardening — v24.6.357 / PR #176, MERGED.** PR #176 merged to
  `master` as `d94554c`. It hardens source updates so only a
  clean `master` can update and both the current and downloaded preflight run
  before Git changes local source. The PowerShell update transaction is loaded
  before the merge, so replacing `UPDATE.bat` during a real fast-forward cannot
  corrupt the running update. It also broadens compatible Python discovery,
  adds a behavior-compatible CSP, emits a distributable ZIP checksum, removes
  owner paths from copied Nuitka diagnostics and validates four dependency
  upgrades in an isolated Python 3.14 environment. Routes, schemas,
  credentials, CV formatting and manual-only protected-build behavior remain
  unchanged. Final local validation passed 979 tests, 4 skips and 96 subtests;
  the final hosted jobs did not start because the Actions spending limit was
  exhausted.
- **Manual-only protected builds — v24.6.355 / PR #174, MERGED.** PR #174
  removed the expensive protected workflow's automatic pull-request trigger
  and left its explicit **Run workflow** action enabled. Do not restore
  automatic PR builds. The local
  `owner_build_tools/BUILD_PROTECTED_WINDOWS.bat` remains authoritative, and
  the owner will report any local build failure. Ordinary regression CI and
  Dependabot remain enabled. No application route, schema, runtime,
  dependency, credential, external-call, user-data or protected-package
  content changes. Validation: 973 passed, 4 skipped, 96 subtests; all 19
  frontend fixtures; 24 source-smoke assertions; tracked syntax; repository
  consistency; and Windows Antiword/Tesseract/adm-zip protected preflight.
- **Windows source update and CI reliability — v24.6.354 / PR #173,
  MERGED.** Branch `chatgpt/pr173-v24.6.354-update-ci-reliability` adds a
  dependency and authorization preflight before the current server is stopped,
  waits for the existing bounded startup health check, and records a small
  rotating local update log plus the previous/current Git commits for safe
  recovery guidance. It does not install dependencies automatically and does
  not reset local edits. Regression CI now runs on merged `master`, maintained
  GitHub action runtimes replace warning-producing versions and are pinned to
  immutable commit SHAs. PR #174 supersedes its automatic protected-build
  trigger with a manual-only action. The low-memory single-worker Nuitka
  compile has a bounded 120-minute allowance inside a 150-minute workflow
  budget. Batch-file validation uses one shared inventory. Weekly Dependabot
  version-update PRs cover exact-pinned Python
  packages and GitHub Actions; npm is intentionally excluded because the sole
  `adm-zip` dependency uses an owner-vetted tree and pinned aggregate hash.
  GitHub Dependabot alerts, malware alerts, automatic security updates and
  grouped security updates are enabled. No route, schema, dependency-set,
  credential, external-call, user-data or protected colleague-package-content
  boundary changes.
- **Windows watchdog recovery corrective — v24.6.352 / PR #169, MERGED.**
  Branch `chatgpt/pr169-v24.6.352-watchdog-recovery` corrects a
  long-standing Windows recovery dead-end. When the listener still existed but
  stopped answering after sleep or a hang, `WATCHDOG.vbs` asked
  `INSTANCE_PORT.ps1` to stop it; the helper terminated the calling watchdog
  before that watchdog could launch the replacement, leaving port 5000 down
  until a manual launch. Watchdog-initiated recovery now preserves only its own
  supervisor, while deliberate Stop, upgrade and package-replacement callers
  retain the established old-watchdog-first shutdown contract. Focused source
  contracts and both protected-build validation stages reject either side of
  that distinction regressing. No route, schema, dependency, credential,
  external-call, user-data or protected-package-boundary change. Validation:
  959 passed, 4 skipped, 96 subtests; all 20 JavaScript source/fixture scripts;
  24-assertion source smoke; repository byte consistency; PowerShell parsing;
  Windows protected-source/Antiword/Tesseract/adm-zip/launcher preflight.
- **JobAdder original-CV upload corrective — v24.6.351 / PR #167, MERGED.**
  PR #167 was squash-merged to `master` as `85dc896`. The corrective preserves
  the original browser File and sends PDF/DOCX/DOC MIME metadata in
  JobAdder's `fileData` multipart part rather than generic
  `application/octet-stream`. If a candidate exists but its latest CV upload is
  rejected, the UI keeps the profile link, shows the readable JobAdder
  validation reason and offers a résumé-only retry without repeating
  extraction, paid parsing or candidate creation. Newly created candidates no
  longer hide a failed original-CV attachment, empty files stop before the
  remote write, and remote error text is escaped. Multipart boundaries are
  unique and collision-checked. A follow-up owner diagnostic showed that AI
  contact fields could still reach JobAdder as invalid email prose or a phone
  string longer than 50 characters; Create Profile and the backend now reduce
  these to one valid contact or omit the invalid optional phone, and candidate
  validation failures expose JobAdder's readable reason. PDF OCR also records
  only near-uniform rendered pages as intentionally blank, so blank trailing
  pages no longer stop Create Profile while unreadable scans remain
  failure-visible. The owner-supplied DOCX/PDFs and diagnostic were inspected
  read-only and remain outside Git. No live JobAdder write, paid AI call, route,
  schema, dependency or protected-package boundary change. Validation: 956
  passed, 4 skipped, 96 subtests; all 19 JavaScript fixtures; 24-assertion
  source smoke; real extraction of both supplied PDFs; Windows protected-source/
  Antiword/Tesseract/adm-zip preflight; route, architecture and version gates.
- **Persistent salary-rule migration — v24.6.346 / planned PR #161, NOT
  MERGED.** Branch `chatgpt/pr161-v24.6.346-salary-rule-migration` fixes an
  upgrade gap found after PR #159: an existing installation retained its old
  persistent `tax_rules.json`, so the packaged Malaysia YA2025 Non-Resident
  rule was never copied and calculations still returned “No rules”. Startup now
  appends missing packaged country/year/residency identities and missing
  additive contribution-profile fields atomically, while preserving all
  existing user-approved brackets, rates, notes, sources and custom values.
  Invalid or unrecognized user files remain untouched, and the migration is
  idempotent.
- **Crawler/JobAdder/Malaysia tax reliability corrective — v24.6.344 / PR
  #159, MERGED.** AI Crawler now stops optional
  enrichment at a 330-second internal deadline and returns safe partial results
  rather than reaching the 420-second browser timeout. JobAdder refreshes near
  expiry, preserves the connection on transient failures and requires reconnect
  only for permanent refresh rejection. Malaysia YA2025 includes a separate
  30% non-resident tax rule and independent EPF/pass profiles for citizen, PR,
  EP, RP-T and spousal/long-term-visit pass. The updater can draft the next year
  from registered official sources in one click, refuses unsupported years and
  never bypasses human approval. Windows receipt/Antiword installer checks were
  also hardened against mismatched local-state roots and user-controlled HOME
  module loading. Validation: 922 passed, 4 skipped, 93 subtests; all JavaScript
  fixtures; protected Windows source/dependency preflight; route/version gates.

- **Lee Lin Yuan CV source-order/fidelity corrective — v24.6.345 / planned PR
  #160, NOT MERGED.** Branch
  `chatgpt/pr160-v24.6.345-cv-source-order-fidelity` builds on the merged
  v24.6.344 reliability/tax corrective. It preserves an explicit source
  Professional Experience → Independent Consulting → Earlier Experience order
  into Preview, and `/generate-docx` keeps that already-reviewed order; carries safe subsection
  headings into preview/Word; restores explicit source glyph bullets only when
  the source list is fuller than the provider role; recognizes title-first
  single-year work headers and compact same-year Earlier Experience dates;
  compacts `2018 to 2018` to `2018`; and restores source middle-dot skill
  separators only after exact content matching. The owner-supplied real PDF
  extracts seven source roles and all five TrustDecision bullets with the new
  pass. Recovery also stops at later CV sections, rejects ungrounded bare-year
  prose, and treats a subsection heading as a hard employer-merge boundary. No
  route shape, storage schema, native dependency or package boundary changes.
- **OCR partial-failure corrective — v24.6.341 / PR #156.** The owner
  authorized the corrective and its merge after validation. If OCR is
  unavailable for selected pages in a mixed PDF, `/extract-text` preserves
  independently readable pages but returns an explicit partial-extraction
  warning and affected page numbers. A name/contact fragment on an OCR-routed
  cover cannot make a mostly scanned CV look complete: at least one
  independently usable page must survive. All interactive browser consumers
  surface the warning, while Batch Format and JobAdder Create Profile stop
  before generating or uploading incomplete data. The focused PDF test now
  isolates its installation receipt instead of overwriting the user's real
  authorization. Validation: 903 passed, 4 skipped, 2 known unrelated Windows
  tests deselected, 93 subtests; all 16 JavaScript fixtures; protected Windows
  source/dependency preflight; repository consistency; and the 24-assertion
  live source smoke. No route, schema, dependency, document-trust or package
  boundary changes.
- **HTML Boolean-highlight review corrective — v24.6.340.** The owner
  authorized PR #155 and its merge after validation. Converted-DOC/DOCX HTML
  matching now groups text by visual paragraph or table cell and maps matches
  back across bold, italic and other Word run nodes. A multi-word phrase is
  therefore highlighted even when formatting changes mid-phrase. The existing
  60,000-character / 8,000-node browser budget is enforced before accepting
  each text node, so one oversized Word run cannot bypass the total limit.
  Focused coverage includes both the cross-run phrase and a 70,000-character
  single run. No route, schema, backend document-trust boundary, dependency or
  package boundary changes. Validation: 899 passed, 4 skipped, 1 known
  unrelated Windows receipt-isolation test deselected, 93 subtests; all 15
  JavaScript fixtures; protected Windows source/dependency preflight;
  repository consistency; and the 24-assertion live source smoke.
- **Legacy-DOC visual preview and Boolean-highlight corrective — PR #154
  MERGED.** PR #154 was merged to `master` as `5e4da48` at v24.6.339. It makes
  AI Crawler and `/preview-file` honor the existing verified-Antiword-first
  conversion exception. If Antiword safely completes and rejects only that
  document, the validated Microsoft Word/LibreOffice DOCX conversion is reused
  for a visual HTML fallback and searchable text; runtime/trust failures still
  never reach a converter. Converted Office HTML is highlighted directly,
  and literal Boolean matching tolerates NBSP, ligatures, soft hyphens and
  line-wrap hyphenation. Foreground scanned PDFs can build bounded word boxes
  with the already-mandatory Tesseract dependency (three pages / 28 seconds);
  background prefetch does not OCR. The owner-observed Yan Yen Fen JobAdder
  `.doc` returns HTTP 200 as a Microsoft-Word-converted visual HTML preview in
  genuine local testing. No new dependency, route, schema or trust exception
  is introduced. Validation: 899 Python tests passed, 4 skipped, 1 unrelated
  Windows receipt-isolation test deselected, and 93 subtests passed; all 15
  JavaScript fixtures, route/version gates, Windows protected-source preflight,
  repository consistency and the 24-assertion live smoke passed.
- **Page-aware PDF/OCR + receipt hardening — MERGED.** PR #152 was
  squash-merged to `master` as `f1934b7` at v24.6.331. The corrective
  preserves usable text and bullet geometry page-by-page, OCRs only pages with
  unmapped glyphs or corroborating image/vector evidence, protects exact short
  contact/skills PDFs, and keeps mixed-language pages in source order. Selected
  OCR pages share one semaphore/deadline; the browser budget covers the 180s
  ceiling plus the maximum 45s render and 35s Tesseract operation already in
  flight. Receipt schema coercion now fails closed, and receipt tests use an
  isolated temporary path rather than the user's real authorization file.
- **Legacy `.doc` conversion fallback and CV formatting — MERGED.** PR #98 was
  squash-merged to `master` as `a18cda4` at v24.6.279. It keeps verified
  Antiword mandatory and first, then accepts a validated temporary DOCX
  conversion only after that exact document is rejected. It prefers installed
  Microsoft Word on Windows and otherwise uses LibreOffice when available. The
  resulting DOCX reuses the existing table and nested-list extraction.
  Execution-time Antiword trust
  failures remain fatal, Word disables automatic link updates before opening
  the untrusted input, and failed/timed-out converters terminate their wrapper
  and recorded native process trees. The owner-supplied incompatible
  DOC passed a genuine Windows `/extract-text` test through Microsoft Word.
  The same branch removes `No Degree`/`Not specified`/`N/A` education
  placeholders, including placeholder suffixes after `No Degree:`, while
  protecting real `Non-Degree Certificate` wording. It also
  covers the owner's exact Isaac/Faizal formatting regressions: continuous
  Unilever/DKSH promotion paths are grouped without merging gapped returns,
  employer blocks and their dated roles are sorted newest-first, source
  education months are restored only for matching two-endpoint year ranges,
  a provider-leading `to` is removed from a lone education year (`to 2001`
  becomes `2001`) while an absent date remains absent,
  Core Expertise is a real bullet list, and bare `a.`/`i.`/`1-`/`a-`
  source labels are removed before Word supplies the visible list marker. The
  Kwong regression follow-up removes JobStreet/SiVA retrieval metadata, rejects
  GitHub URLs not grounded in the source, and deterministically restores the
  source Project Involvement History and Participated Training Programme lists.
  Its review corrective also removes the known GitHub placeholder at the
  source-free export boundary, accepts sentence punctuation after grounded
  source URLs, removes inline retrieval metadata after an item separator, and
  renders recovered multi-item sections as bullets in both preview and Word.
  The v24.6.280 post-merge corrective stops Project/Training source recovery at
  recognized ordinary CV headings so it cannot absorb later sections, and
  records the owner-authorized Antiword-rejection conversion exception in
  `AGENTS.md`. The separate Summary-format work is published only on
  `chatgpt/v24.6.282-summary-table-options`; it is not part of these changes and
  must remain unmerged unless the owner later approves it explicitly.
  The v24.6.281 follow-up also recognizes common combined boundaries such as
  Education & Certification, Professional Qualifications, Courses & Training,
  and Professional Affiliations.
  The v24.6.283 review corrective preserves explicitly marked project/training
  items even when their wording resembles a section heading, treats literal
  `AND` like `&` in combined headings, and keeps undated current employers and
  roles in their source positions. Continuous-employer grouping now requires
  month-precise touching dates and only strips known broad location suffixes;
  year-only dates and business-unit suffixes remain separate. Existing Core
  Expertise list items also keep internal commas while still rendering as
  bullets.
  The v24.6.284 audit corrective closes the remaining marked-boundary and
  partial-date gaps: numbered or emphasized marked headings terminate
  Project/Training recovery, and same-employer grouping requires month precision
  at every bounded endpoint. A three-or-more-item expertise paragraph wrapped in
  a one-element provider list is restored to bullets while genuine comma-bearing
  expertise phrases stay intact. The same release upgrades Pillow and adm-zip,
  validates real image formats and every salary-source redirect before contact,
  makes CI run the full pytest/JavaScript matrix, and removes the known Windows
  platform-test, live-smoke header-case and Antiword release-lock flakes.
- **AI Crawler ".doc: flag, don't decode"**: skip decoding an undecodable legacy
  `.doc` while still surfacing the candidate. Deferred pending measurement of
  whether `.doc` decode vs. PDF OCR is the real bottleneck; a naive attempt
  broke a ~900-line characterization test and was reverted.
- **Phase 7B modularization** can continue: extract pure clusters, keep it
  behavior-preserving, hold the route SHA constant.
- **Waitress server swap (backburner #4) — MERGED AND PROTECTED-BUILD VERIFIED.**
  `app._run_cvstudio_server()` prefers Waitress and falls back to Werkzeug
  `app.run` if Waitress is unavailable or `CVSTUDIO_SERVER=werkzeug` is set, so
  it degrades safely. Loopback-only bind; `threads=16`; and critically
  `channel_timeout` is *derived* from `_cv_parse_backend_timeout_seconds`
  (300s ceiling × 3 chained parse attempts + 120s = 1020s) so a long/truncated
  `/parse` connection is never cut mid-flight — do not hardcode this or the
  timeout bug returns. Covered by `tests/test_server_runtime.py`; route SHA and
  version surfaces unchanged. The owner's v24.6.356 protected Windows build
  report confirms Waitress 3.0.2 is frozen into the native runtime. Future
  protected builds must retain that explicit inclusion and smoke coverage.
  `waitress==3.0.2` is in `requirements.txt`; it is a pip dep, not a repo source
  file, so it is not in the `build_protected.py` `required` tuple.

## Coordinating the work — slicing + formatting (three parties)

Two kinds of work run in parallel, and the split is drawn **by file/function, not
just by theme**, because both touch `app.py`:

- **CV formatting** — owned by **ChatGPT** (relayed by the owner; ChatGPT can't
  push). Files: `cvstudio_cv_normalize.py`, `cvstudio_cv_reconcile.py`,
  `generate.js`, `template.docx`, and **inside `app.py`**: `parse_cv`,
  `/generate-docx`, `SYSTEM_PROMPT`, and the CV post-processing chain. Tests:
  `test_long_cv_output_corrective.py`, `test_phase7b_cv_normalize_characterization.py`.
  See `FORMATTING_NOTES.md`.
- **Slicing (modularization)** — owned by the **Einstein** and **Claude/kingg**
  accounts: pulling *other* clusters out of `app.py` into `cvstudio_*.py`
  modules.

**The rule that keeps them from colliding: slicing must NOT touch the CV
formatting files or functions above — leave them in `app.py` for ChatGPT to keep
editing.** There is plenty else to slice. Likewise ChatGPT's formatting fixes
must never add or remove a route (that would move the route-contract SHA); flag
any such need to a slicing account.

- Only one account holds a given feature branch at a time — agree who owns which
  branch, and always `git fetch` + rebase onto the latest `origin/master` before
  new work.
- **Version:** every code change bumps the version via `python bump_version.py
  X.Y.Z` (§5). Whoever merges second rebases and re-bumps — a one-command,
  conflict-free fix thanks to the single-source `VERSION` file.
- Keep this file current: when a deferred item lands or a new trap is found,
  update section 7/8 and the table below.
- **Live status log:** GitHub issue #35 ("🤝 Multi-Agent Coordination Log") is
  the append-only record of who is doing what *right now*. Post there when
  starting, pausing, or finishing so others see in-flight state without reading
  commits.

### Current work split

> **STATUS (v24.6.315).** A separate **frontend modularization is complete**:
> `index.html` was sliced into a 2,196-line thin shell + 30 `vendor/cvstudio/*.js`
> modules + `app.css` (F1–F4, PRs #112–#134), including the Lead Finder **frontend**
> (`lead-finder.js`). This is distinct from the backend `_lead_*` app.py-region
> slicing in the table below — treat the frontend as done and see
> `FRONTEND_ROADMAP.md`. The backend split table below is unchanged; confirm
> current backend claims in issue #35 before starting.

Every modularization extraction touches `app.py`, `cvstudio_architecture.py`,
and `tests/test_phase7a_modular_monolith_foundation.py`, so the slicing accounts
take domains in **non-overlapping `app.py` regions** and never share a branch.

| Party | Domain | New module | app.py region | Branch name |
|---------|--------|-----------|---------------|---------------|
| **ChatGPT** | CV **formatting** (bullets/markers/dates/casing/reconcile). Files listed above; see `FORMATTING_NOTES.md`. Changes relayed by the owner. | edits `cvstudio_cv_normalize.py` / `cvstudio_cv_reconcile.py` / `generate.js` — no new modules, no new routes | `parse_cv` / `/generate-docx` / `SYSTEM_PROMPT` / CV post-processing | `chatgpt/v<version>` |
| **Einstein** *(slicing)* | No current JobAdder claim. The activity network service, official/SPA screening helpers, provider adapters and low-level request layer were completed in PRs #104–#108. Remaining token/account/cache globals are deliberate shell state, not an advertised pure slice. | — | — | claim the next task in #35 first |
| **king** *(slicing, suggested — confirm in #35)* | Remaining **Lead Finder** `_lead_*` helpers (pure closures; self-contained, good re-onboarding domain). Keeps a clean `_lead_*` vs `_ja_*` region split from Einstein. | `cvstudio_lead_*` | `_lead_*` cluster | `king/v<version>` |

_Historical rows (completed domains) below for context:_

| Account | Domain | New module | app.py region | Branch prefix |
|---------|--------|-----------|---------------|---------------|
| **Einstein** | OneNote + Outlook / MS-Graph — **domain done.** Slice 1 = pure helpers (#41). Slice 2 = `OutlookService` (#43). Slice 3a = `OneNoteGraphService` connection layer (#47). Desktop-COM → `cvstudio_onenote_desktop.py` (#53). Content handlers (notebooks/sections/pages/import + list helpers) now in `OneNoteGraphService`. Only the 3 `/onenote/desktop_*`+`manual_pages` route bodies remain in the shell (thin delegators to the desktop module + service-owned page-list helpers via aliases). `_onenote_*` screening/clean helpers stay (shared with candidate-import). | `cvstudio_msgraph.py`, `cvstudio_onenote_desktop.py` | — | `einstein/*` |
| **Claude** | Spider / AI Crawler pure closures (`cvstudio_spider_summary`, `cvstudio_spider_score`) + JobAdder typo-correction (`cvstudio_ja_typos`) — **core closures done (#54).** Lead Finder domain **reassigned to Einstein 2026-08-05**, and the **remaining Spider `_spider_*` + JobAdder `_ja_*` domain reassigned to Einstein 2026-08-07** (Claude out of quota). | `cvstudio_spider_summary.py`, `cvstudio_spider_score.py`, `cvstudio_ja_typos.py` | done | `claude/*` |
| **Einstein / Kingg (took over `_ja_*`/`_spider_*`)** | JobAdder/Spider modularisation through v24.6.290 is complete: salary parse/notice/AI, screening answers and payloads, activity helpers plus network service, SPA bridge, request layer, provider adapters and safe Spider document helpers are extracted. The small app-level activity functions are compatibility delegates. Stateful token/account/cache and native `.doc`/OCR/PDFium boundaries stay in the shell unless a separately characterized service slice is claimed. | `cvstudio_salary_parse.py`, `cvstudio_ja_answers.py`, `cvstudio_ja_salary_notice.py`, `cvstudio_ja_salary_ai.py`, `cvstudio_ja_activity.py`, `cvstudio_ja_screening.py`, `cvstudio_jobadder_request.py`, `cvstudio_ai_providers.py`, `cvstudio_spider_documents.py` | completed service/pure closures | `einstein/*`, `claude/*` |

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
| PPC (Post Placement Care) — `_ppc_*` placements only | ~21,660–21,850 | pure closure | Einstein | ✅ merged (#40); `/ppc/outlook/*` deferred to the OneNote + Outlook row |
| Lead Finder enrichment (URL/company) | ~15,750–19,600 | pure closure | **Einstein** (reassigned 2026-08-05; Claude ran out of quota mid-handoff) | CLAIMED by Einstein 2026-08-05; slice 1 merged (#39/#42), ~29 `_lead_*` helpers still in `app.py` |
| OneNote desktop-COM cluster → **`cvstudio_onenote_desktop.py`** (done) | ~3,585–4,251 | pure module (Windows COM, lazy-imported) | **Einstein** | Done — the 17 `_onenote_desktop_*` / `_onenote_com_error_label` / `_onenote_match_desktop_section_from_manual` helpers moved byte-for-byte into `cvstudio_onenote_desktop.py`; the `/onenote/desktop_*` + `manual_pages` route handlers stay in the shell and import them back (same pattern as `cvstudio_onenote_text`). Windows-only, so verified by compile + import + route contract only (no Linux behavioral coverage). |
| OneNote Graph **content** handlers → `OneNoteGraphService` (done) | — | service methods | **Einstein** | Done — notebooks/sections/section_pages/pages/page_content/import_recent/import_selected + the `_onenote_list_*` / `_get_all_notebooks_and_sections` helpers and `_onenote_parse_date_bound` moved into `OneNoteGraphService` (`request_args` injected). The 3 desktop route bodies remain in the shell and reach the page-list helpers + `_onenote_parse_date_bound` via app-level aliases. `_ms_graph_json`/`_ms_graph_store` aliases still kept for the external MS-status/diagnostics probes. |
| Spider / AI Crawler enrichment (`_spider_*`) | ~4,900–7,700 | pure closure | Kingg | ✅ **pure closures exhausted (Kingg, 2026-08-09).** slice 1 = candidate data-shaping (`cvstudio_spider_summary.py`); slice 2 = JD-scoring/fit-term matching (`cvstudio_spider_score.py`); slice 3 = the small leftovers (`_spider_preview_name`, preview-text, download identity/fingerprint, disposition filename, attachment/candidate parsers, keyword marking) folded into `cvstudio_spider_summary` / `cvstudio_spider_boolean`; slice 4 = **new `cvstudio_spider_documents.py`** (byte-signature classifiers + visual-preview shaping). What remains is NOT pure: the preview/resume **cache cluster** (tests pin the module-global int byte-counter — can't encapsulate without breaking behaviour), network fetch, and ⚠️ the .doc/OCR/PDFium minefield (`_spider_*_legacy_doc_*`, tesseract/poppler/pdfium; native `.doc` recovery is Einstein's) — leave in the shell; tests-first mandatory |
| JobAdder `_ja_activity` diagnostics → **`cvstudio_ja_activity.py`** | ~4,350–4,660 | pure helpers + injected service | Kingg | ✅ completed: five pure helpers merged in #103; the OAuth GET/POST network probes moved into `JaActivityDiagnosticService` in #104. Flask routes retain only compatibility delegates. |
| `_ja_*` screening-call **payload builders** (regular + SPA) → **`cvstudio_ja_screening.py`** | ~3,240–3,810 | pure but interconnected | Kingg | ✅ **done (Kingg, 2026-08-09).** 11 items moved verbatim: `_ja_candidate_screening_call_payload` (the exhaustive answers-shape sweep), `_ja_spa_screening_call_*`, `_ja_screening_call_answers`, `_ja_browser/precise/activity_payload_variants`, plus the shared `_onenote_clean_field_value` / `_onenote_screening_remarks_value` / `_onenote_presentability_rating_int` + `_ONENOTE_JA_SCREENING_QUESTIONS_BASE`. app.py re-exports all 11, so the 28 in-shell `_onenote_clean_field_value` callers and the lazy injection into `cvstudio_ja_salary_ai` are unaffected. Verified byte-for-byte via a **golden differential** across 138 shape×mode combos + new characterization tests. Depends only on `cvstudio_ja_answers`. |
| Core CV/AI pipeline pure helpers (`/parse`, `/generate-ai`, DOCX mapping) | ~15,300–21,600 | pure closure | either (last) | most sensitive; scope carefully, extract last |
| Remaining `_ja_*` service slices | ~3,830–4,560 | injected services | Einstein/Kingg | ✅ activity network probes completed in #104; official screening payload in #105; SPA bridge in #106; provider adapters in #107; request layer in #108. No `_ja_candidate` service cluster remains identified. Re-scope from current code and claim in #35 before any further extraction. |

Notes:
- Lead Finder still has ~29 `_lead_*` helpers beyond the first URL/company
  slice (search-provider result parsing, title-angle logic, contact/email
  helpers). Reassigned to Einstein 2026-08-05 (Claude ran out of quota before
  posting the handoff) — Claude should now stay out of the ~15,750–19,600
  region.
- OneNote's `_onenote_*` helpers hit MS Graph / the OneNote desktop app, so they
  are a service-module extraction, not a pure closure. This domain now also
  folds in the `/ppc/outlook/*` `_ms_outlook_*` cluster (deferred out of PPC),
  since it is the same MS-Graph service-module shape.
