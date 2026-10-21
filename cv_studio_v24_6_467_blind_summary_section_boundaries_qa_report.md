# CV Studio v24.6.467 — Shared Blind summary section boundaries

Historical QA record; root `VERSION` is authoritative.

PR #235's automatic review identified an additional source-summary boundary
defect in v466: headings already supported by DOCX summary replacement, such as
Experience, Employment, Work History and Professional Skills, could enter the
recovered Blind CV summary together with the following section's bullets.

The established 71-key `_SUMMARY_DOCX_SECTION_HEADING_KEYS` set now lives in the
pure `cvstudio_blind_mask.py` module and is imported under the same app-level
compatibility name. Both summary replacement and source recovery use this one
authority. Its values are unchanged. The source reader retains all its extra
aliases and existing whole-heading, numbered/strong-heading, ordinary marked
content, candidate-header and size-limit decisions. No route, schema, provider
retry/paid-call boundary or renderer changed in this corrective.

Thirteen new anonymized B1 fixtures failed against v466 before correction,
including a supported section after a template footer. All 1,019 pre-existing
fixture cases and expectations remain unchanged. Generated coverage exercises
all 71 shared keys in ten layouts, including numbered, uppercase, colon-marked
and letter-spaced headings; ordinary marked title-case items and sentences
beginning with Experience remain content. A mocked actual `/parse` regression
checks the four reported headings, a clean summary and unchanged work bullets.
The same test verifies the app and pure helper share the exact set object.

Validation:

- Full isolated Windows Python: **1,750 passed, four skipped, 8,392 subtests**,
  146.62 seconds. Temporary receipt, SQLite, job journal, salary and credential
  state were isolated before collection. Focused guardrail/Word-summary checks:
  **56 passed, 2,223 subtests**. All **42 JavaScript suites passed**.
- Original master registry replay: all **985 cases** pass against exact merged
  master `02af520` and current blind helpers. All **1,019** prior fixture
  expectations remain unchanged; old source-reader/correction cases produce
  identical results against v466. AST comparison confirms all **71** shared
  heading values moved unchanged.
- Old/new comparison on **226,532 repository code/test/documentation lines**
  finds no changed legacy summary promotions or standalone false recoveries.
  Existing generated list, language-correction, numeric-anchor and hostile-input
  cases pass along with 710 generated shared-heading layouts.
- Eight deliberate in-memory reader/recovery mutations are detected, including
  removal of the shared heading vocabulary. Three actual-route mutations also
  fail their regressions when Word numbering preservation, language-correction
  retention or the new shared boundary union is disabled. All mutations stay in
  ignored test helpers and do not modify production files.

- Tracked Python, JavaScript, PowerShell and shell syntax, whitespace and
  repository consistency checks passed. Windows owner-source native preflight
  verified Antiword and Tesseract/English; **24 live source smoke assertions
  passed**. No protected compilation or local native macOS testing occurred.

Final PR checks follow this local gate; the coordination log records the final
tested checkpoint and merge identity.

Provider calls use synthetic mocks. Owner installation, receipt, private input
documents and the already-delivered corrected document remain untouched. No
live provider call, candidate write, protected build or new release ZIP occurred.
