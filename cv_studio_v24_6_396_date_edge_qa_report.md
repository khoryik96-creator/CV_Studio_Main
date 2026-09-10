# v24.6.396 date-edge corrective

Branch: `codex/pr204-v24.6.396-date-edge-fixes` (PR number provisional).
Base: merged master `42dcb78`, v24.6.395. No PR or merge requested.

## Fixes

- Day-bearing shared-year spans check month order before copying the ending
  year to the start. `1 Dec - 31 Jan 2026` becomes `Dec to Jan 2026`;
  the omitted start year is not guessed. Explicit 2025-to-2026 dates survive.
  The same guard applies to already-normalized month spans on every pass.
- Unicode horizontal/non-breaking spaces normalize before date parsing in
  Python, browser and Word generator. The raw-source ISO guard accepts those
  spaces while still rejecting matches across LF, CRLF and Unicode line breaks.
- Existing short-year preservation, ordinary shared-year spans, skills and
  bullet behavior remain unchanged. No route/schema/dependency changes.

## Verification

- Full isolated Windows suite: 1223 passed, 4 skipped, 2803 subtests passed.
- Shared parity tests: 1556 cases, including all 144 month pairs, both
  day/month orders, eight Unicode spaces, explicit years and repeated passes.
- Additional adversarial sweep: 2160 full-date variants passed in all three
  handlers (commas, dotted/full months, ordinals, separators and spacing).
- Real DOCX tests cover both direct Node and HTTP generation of work/education
  headers with cross-year and non-breaking-space dates; duty text is preserved.
- All 24 frontend groups and 24 live source-smoke assertions passed.
- Protected-source preflight passed: syntax, verified Antiword 1.3.5,
  Tesseract 5.5 English and adm-zip 0.6.0. Repository consistency and whitespace
  checks passed.

No native protected compilation, live provider calls, credential changes or
external candidate writes were performed. The separate existing adm-zip
security alert is outside this two-finding corrective and remains unchanged.
