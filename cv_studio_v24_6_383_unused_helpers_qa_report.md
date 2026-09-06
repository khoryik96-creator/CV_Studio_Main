# v24.6.383 — isolated unused-helper cleanup

Original base: master `a5fa125` (v24.6.381); integrated base after PR #194:
master `75c43b6` (v24.6.382). Branch:
`codex/pr195-v24.6.383-unused-helper-cleanup` (planned PR #195).

Removed only four definitions with no remaining repository callers:

- `app._spider_fetch_candidate_bundle`
- `app._lead_provider_from_model`
- `app._lead_pricing_for_model`
- `cvstudio_blind_mask._blind_summary_vertical_org_identities`

An AST comparison against the base confirms these exact four deletions, no
added functions, and byte-equivalent ASTs for every remaining function in the
two changed modules. Live provider/pricing, candidate detail/resume and summary
identity implementations remain unchanged. No sealed compatibility signature
or decorated route was removed.

Repeated validation of the integrated code on isolated Windows state:

- Full suite: **1117 passed, 4 skipped, 128 subtests**.
- All **23 frontend fixture groups** passed, including async-handler safety.
- Live source smoke: **24 assertions** passed.
- Protected-source preflight passed, including verified Antiword 1.3.5,
  Tesseract 5.5 English, adm-zip 0.6.0, source syntax and frontend inventory.
- Repository byte consistency, version anchors, 118-route seal and Git
  whitespace checks passed. No package lock was generated.

The owner subsequently authorized both merges. This branch now integrates
v24.6.382's async-handler fixes and its OneNote loading-indicator corrective
from PR #194, while retaining version 24.6.383. Its own delta remains the four
deletions, generated version surfaces and documentation.
No schemas, dependency set, credentials, paid calls or protected packaging
boundaries changed. No native protected compilation or release is requested.
