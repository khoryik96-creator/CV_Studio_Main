# v24.6.383 — isolated unused-helper cleanup

Base: master `a5fa125` (v24.6.381). Branch:
`codex/pr195-v24.6.383-unused-helper-cleanup` (PR number provisional).

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

Validation on isolated Windows state:

- Full suite: **1117 passed, 4 skipped, 128 subtests**.
- All **22 existing frontend fixture groups** passed.
- Live source smoke: **24 assertions** passed.
- Protected-source preflight passed, including verified Antiword 1.3.5,
  Tesseract 5.5 English, adm-zip 0.6.0, source syntax and frontend inventory.
- Repository byte consistency, version anchors, 118-route seal and Git
  whitespace checks passed. No package lock was generated.

This branch does not include v24.6.382's async-handler behavioral changes.
They are separately pushed on `codex/pr194-v24.6.382-async-handler-safety`.
Rebase and reconcile the version/handoff if this cleanup merges second.
No schemas, dependency set, credentials, paid calls or protected packaging
boundaries changed. No native protected compilation, PR, merge or release.
