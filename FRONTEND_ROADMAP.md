> **Version source of truth.** The current release is whatever the repository-root [`VERSION`](VERSION) file says. Any version number below is historical context from when this doc was authored — see [`HANDOFF.md`](HANDOFF.md) for live state and GitHub issue #35 for who is touching what right now.

# CV Studio — Frontend Modularization Roadmap

The backend went from a ~22k-line `app.py` to ~12k by draining behaviour-preserving
helper clusters into `cvstudio_*.py` modules while the sealed route contract held
constant. This is the parallel plan for the **frontend**: `index.html` is one
19,834-line / 1.28 MB file, and **~82% of it (~16,270 lines) is a single inline
`<script>` block**. The same discipline applies — extract cohesive slices into
loadable modules while the *rendered app behaves identically*.

## 1. Current state (the anatomy)

`index.html` (19,834 lines) breaks down as:

| Region | Lines | What it is |
|--------|-------|------------|
| `<style>` (main) | 8–1419 (~1,411) | All app CSS |
| bootstrap `<script>` | 1421–1593 (~172) | Early JobAdder OAuth/upload glue |
| HTML body | 1594–3546 (~1,950) | Markup for every tab/panel |
| **monster `<script>`** | **3549–19818 (~16,270)** | **The entire app: ~40 feature sections** |
| final init `<script>` | 19820–19832 (~12) | Boot |

- **~7% CSS, ~10% HTML, ~82% JavaScript.**
- The monster block is already organized into **~40 clearly-commented feature
  sections** (`// ── The Owl ──`, `// ── AI Crawler ──`, `// ── Blind JD Tab ──`,
  …), which are the natural extraction seams.

## 2. The pattern already exists (the beachhead)

Two proofs that modular frontend works here today:

1. **Four `vendor/cvstudio/*.js` IIFE modules** are already extracted and shipped:
   `lazy-loader.js`, `api-transport.js`, `page-nav.js`, `server-heartbeat.js`.
   They are loaded with versioned `<script src="/vendor/cvstudio/NAME.js?v=…">`
   tags, registered in the **`FRONTEND_MODULES`** tuple in
   `owner_build_tools/build_protected.py`, and validated at build time with
   `node --check` (plus the QA harness at `build_protected.py` ~line 931).
2. **Salary Comparison is already fully decoupled** — the tab is an
   `<iframe id="salaryFrame">` pointing at the self-contained `/salary-comparison/`
   Flask blueprint. Isolation via iframe is a proven option for heavy, standalone
   features.

Each vendor module is an IIFE: `(function(){ 'use strict'; … window.X = …; })();`
It re-attaches its public functions to `window`, so existing callers keep working.
**That is the target shape for every slice below.**

## 3. Invariants to hold constant (the frontend "route contract")

Just as backend extractions hold the 116-route SHA constant, frontend slices must
hold these:

1. **The global-function surface.** There are **422 inline event handlers**
   (`onclick=` ×318, `onchange=` ×78, `oninput=` ×26, `onsubmit=`, `onload=`) in the
   HTML body plus **110 `window.X =` globals**. Every function named by an inline
   handler (`onclick="switchTab('owl')"`) **must remain a global** after extraction.
   An IIFE module preserves this by assigning `window.switchTab = switchTab;`.
2. **`index.html` version anchors.** `bump_version.py` stamps three anchors in
   `index.html` (`… (Offline) by`, `version:'…',schema:1`, `LOCK_UNLOCK_VERSION`).
   They live in the head/HTML, not in the JS being moved — keep them in place.
3. **Build registration.** Every new `vendor/cvstudio/*.js` must be added to
   `FRONTEND_MODULES` (so `node --check` and the packaged build include it), exactly
   as backend modules are added to `build_protected.py`'s required tuple.
4. **Load order.** Modules that publish globals used by inline handlers must load
   before the handlers can fire (i.e. before/at `DOMContentLoaded`). Preserve the
   current ordering: foundation first, then feature modules, then boot.
5. **CSP stays satisfiable.** Today CSP is permissive (`frame-ancestors` only, no
   `script-src`), so external scripts are safe to add. Extraction *enables* a
   stricter `script-src` later (Phase F5) — don't regress toward more inline JS.

## 4. The per-slice recipe (definition of done)

Mirrors the backend extraction recipe:

1. Pick one commented feature section from the monster block.
2. Move its JS **verbatim** into `vendor/cvstudio/<feature>.js` as an IIFE; end the
   IIFE by assigning every function referenced by an inline handler (and by other
   sections) onto `window`.
3. Replace the inline code with a versioned `<script src="/vendor/cvstudio/<feature>.js?v=…">`
   at the correct load position.
4. Register the file in `FRONTEND_MODULES`.
5. **Verify** (Section 6). Cache-bust version bump. Commit one slice per PR.

## 5. Phased plan (ordered by decoupling risk)

**Phase F0 — foundation (DONE).** `lazy-loader`, `api-transport`, `page-nav`,
`server-heartbeat`; Salary via iframe.

**Phase F1 — CSS extraction (lowest risk, do first).** Move the 1,411-line
`<style>` (8–1419) into `vendor/cvstudio/app.css`, linked with
`<link rel="stylesheet" href="/vendor/cvstudio/app.css?v=…">`. No JS coupling; pure
win; validates the cache-bust story (Section 7) before any JS risk. *Leave the small
per-document `<style>` template strings inside the JS (they build exported .docx/PDF
HTML — they are data, not page CSS).*

**Phase F2 — leaf feature controllers (self-contained tabs).** Each is a bounded
section with its own render/export logic and a small global surface:
- `blind-jd.js` — Blind JD Tab + Export (~1,050 lines)
- `company-profile.js` — Company Profile Tab + Export (~510 lines)
- `cv-scoring.js` — JD vs CV Compatibility Scorer (~490 lines)
- `candidate-summary.js` — Candidate Summary Generator (~190 lines)
- `fcv-upload.js` — FCV Upload Tab (~160 lines)
- `appearance.js` — Wallpaper/background settings (~150 lines)

**Phase F3 — big cohesive features.**
- `the-owl.js` — The Owl + chat/memory + floating chat (~1,130 lines)
- `ai-crawler.js` — AI Crawler / JobAdder resume sourcing (~2,355 lines, the single
  biggest section; may itself split into `ai-crawler-*` sub-modules)

**Phase F4 — shared services (extract last, after consumers are modular).** These are
the cores many features call, so they move once their callers already live in
modules and the global surface is well-understood:
- `ai-proxy.js` — generic AI proxy + anonymisation safety helpers
- `net.js` — the global fetch helper ("available to ALL functions")
- `jobadder-upload.js` — OAuth popup + DOCX upload + batch/queue + candidate dialog
- `ai-routing.js` — per-feature AI provider routing
- `settings.js` — settings tabs/panel, locked-tab version-scoped persistence,
  integrations diagnostics + local backup, sidebar tab run-status indicators

**Phase F5 — hardening (optional, after the block is drained).**
- Split the HTML body (1594–3546) into server-rendered partials/templates.
- Migrate inline `onclick=`/`onchange=` to `addEventListener` (delegated), then set a
  strict `script-src` CSP that forbids inline scripts/handlers — a real security win
  the extraction unlocks.

## 6. Verification strategy (the frontend "golden diff")

No pytest for the browser, so the safety net is:

- **Global-surface diff.** Before a slice, enumerate the app's global functions/vars
  (`window.*` and top-level `function` names). After, assert the set is unchanged
  (moved functions still resolve as globals). This is the direct analog of the
  backend route-SHA check.
- **Handler-resolves check.** A grep/AST that every `on*="fn(…)"` target in the HTML
  resolves to a defined global after extraction — nothing silently becomes undefined.
- **`node --check`** on every module (already in the build).
- **Headless smoke test (Playwright — already available in this environment).** Load
  `/`, click through every tab, assert no console errors and that each panel's key
  element renders. This is the real behavioural gate; add it once and run per slice.
- **Byte-identity of moved JS.** Diff the extracted function bodies against the
  original inline text — the move must be verbatim (only the IIFE wrapper + `window.`
  exports are added).

## 7. Cross-cutting: fix cache-busting first

The existing vendor tags are pinned at `?v=24.6.268` while `VERSION` is well past that
— the `?v=` is **not** a `bump_version.py` anchor, so it has silently drifted. Before
adding more modules, pick one and apply it consistently:
- **(a)** Add each `vendor/cvstudio/*.js?v=…` to the `bump_version.py` `ANCHORS` table
  (like the backend surfaces), so cache-bust tracks `VERSION`; or
- **(b)** Switch to a content-hash query (`?v=<sha8>`) generated at build time.
  Option (a) is the smaller, in-convention change and matches how every other surface
  is managed.

## 8. Coordination

- This work is **`index.html` + `vendor/cvstudio/` + `FRONTEND_MODULES`** — largely
  disjoint from the Python `cvstudio_*.py` slicing, so it can proceed in parallel.
  Post slices to issue #35 like any other work.
- **Watch one overlap:** the CV parse/generate frontend controller touches the same
  formatting concern ChatGPT owns on the backend (`generate.js`, the CV pipeline).
  Extract that controller **near-last** and coordinate before moving it.
- One slice per PR, behaviour-preserving, `FRONTEND_MODULES` updated, verified per
  Section 6 — same cadence as the backend extractions.

## 9. Sequencing summary

| Phase | Slices | ~Lines drained | Risk |
|-------|--------|----------------|------|
| F0 | foundation (done) + Salary iframe | — | — |
| F1 | `app.css` | ~1,411 | very low |
| F2 | 6 leaf tab controllers | ~2,550 | low |
| F3 | The Owl, AI Crawler | ~3,485 | medium |
| F4 | 5 shared-service modules | ~4,500+ | medium-high (extract last) |
| F5 | HTML partials + strict CSP | — | opt-in hardening |

Draining F1–F4 takes `index.html` from ~19,800 lines to a thin shell of markup +
`<script src>` tags — the same outcome the backend achieved, reached the same way:
one bounded, behaviour-preserving, independently-verified slice at a time.
