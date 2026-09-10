# v24.6.395 — PR #202 date-parity corrective

Branch: `codex/pr202-v24.6.395-date-parity-fixes`.
Based on PR #202 head `317e320` (v24.6.394), including master `787e815`
(v24.6.393). Claude's PR branch is untouched; this corrective is unmerged.

## Corrections

- Preserve ambiguous two-digit years, including mixed-precision endpoints.
  `Jan 20 - Dec 21` becomes `Jan 20 to Dec 21`, not `Jan to Dec`.
  `Jan 20 to Dec 2021` stays intact rather than changing the start to 2021.
- Strip days only from complete dates or a complete day-bearing shared-year
  range. `Apr 2022-11 Jul 2026` becomes `Apr 2022 to Jul 2026`;
  `Jul 1 - Aug 31, 2026` becomes `Jul 2026 to Aug 2026`.
- Mirror those rules in Python, browser preview and direct `generate.js` input.
  Browser numeric/ISO dates and leading date-list markers now match the other
  two normalizers too. The same-line ISO lookahead remains in all three paths.
- Do not consume an ISO month as the day of a month on the next line.
- Retain PR #202's empty-Skills fix and all previous bullet/education safeguards.

## Verification

- Full isolated Windows suite: **1223 passed, 4 skipped, 2161 subtests passed**.
- All **24 frontend fixture groups** passed.
- **919 date cases** compare Python, browser and generator, including checking
  that normalizing a second time makes no further change.
- Real DOCX tests run through both `/generate-docx` and direct Node generation;
  work and education headers retain expected dates and duty wording survives.
- Pre-fix comparison reproduces both short-year losses on the reviewed PR head.
- Live source smoke: **24 assertions** passed.
- Protected-source preflight passed with verified Antiword 1.3.5, Tesseract 5.5
  English and adm-zip 0.6.0; source/JavaScript/PowerShell syntax, repository byte
  consistency, version anchors and whitespace checks passed.

No production credentials or paid AI/Microsoft/JobAdder writes were used.
No route, schema, dependency or protected-package boundary was changed.
PR #203 supersedes #202; the owner subsequently authorized merge after validation.
Review added optional commas in complete day-first dates and shared-year spans.
The expanded parity tests (919 cases) and all 24 frontend groups pass.
No native protected compilation or release was requested.
