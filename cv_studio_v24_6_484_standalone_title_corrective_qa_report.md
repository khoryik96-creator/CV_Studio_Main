# Historical QA record — CV Studio v24.6.484

Use repository-root `VERSION` for the current release. This is the bounded
correction for PR #240's P2 finding against tested v483 head `9249ae0`.

## Defect and remedy

If a standalone ad began with a notice paragraph, the recognized header tuple
had no company links. v483 could then retain its generic fallback title. A job
type such as `Hybrid`, linked to the same ad inside another paragraph, could be
returned as the role after the ancestor walk found the real company.

Standalone ads now clear the fallback unconditionally and restore a title only
after recognizing the visible company/title/location tuple. Unknown or incomplete
standalone headers fail visibly for both full ad and HR company-only reads.
The correction does not add guesses for unknown layouts. Recognized plain or
linked standalone titles and search-detail layouts remain supported. All v483
company-only readiness, loading-gap and error-guidance corrections remain.

No change to canonical job/company identity checks, rich-content capture, paid
calls, pairing, permissions, run budgets, cancellation, routes, guards, schemas
or durable-record writes. No owner installation/browser/data changes, completed
live HR scan, paid call, outreach or protected build were performed.

## Validation

The added leading-notice/paragraph-wrapped-job-type fixture failed against v483
with a missing expected exception. It passes after the correction for literal
`companyOnly` false and true, preserving all earlier fixture assertions.

Final-code checks passed: **1,779 Python tests, four skipped, 8,392 subtests**
(194.92s), all **47 JavaScript suites**, repository and tracked-language
validation, owner-source/native preflight and all **24 source smoke assertions**.
Merge evidence is recorded on PR #240 and coordination issue #35. Hosted
checks/review must refer to the final commit, not the earlier v483 head.

Actual isolated Chromium with outbound networking blocked verified the same
leading-notice arrangement for both full and company-only requests. Neither can
import a job-type fallback. The same browser run retained successful linked and
plain title/company/location/rich-list captures, company-only success with an
unloaded body, and full-read loading guidance. There were no live credentials or
provider requests in the disposable browser. Native macOS application testing
is not claimed; hosted Mac checks cover dependency setup only.

Ignored local evidence: `runtime/standalone484_before.log`,
`runtime/job484_final.log`, `runtime/pytest_484_full.log`,
`runtime/js484_*.log` and `runtime/preflight_484.log`.
