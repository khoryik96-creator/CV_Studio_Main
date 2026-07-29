# CV Studio v24.6.243 Phase 6 handover

## Owner gate

Phase 6 remains inactive. This handover records only the four-finding
JobAdder account-isolation corrective to v24.6.242. It does not authorize
Phase 6, unrelated AI Crawler product behavior, backburner work, handoff or
merge.

## Release identity and platform boundary

- Release: CV Studio v24.6.243.
- Reviewed baseline:
  `21408d0457c9e4c5db5018c39333c32420d54339`.
- Reviewed v24.6.242 head:
  `e7c86bc0020302723ea845cd046d6592f67263d2`.
- Supported platform: Windows x64 only.
- Mandatory dependency: bundled, hash-pinned and functionally verified
  Antiword 1.3.5 (engine 0.37).
- No Intel or Apple Silicon macOS claim or artifact is authorized. macOS users
  remain on v24.6.239.

## Corrective boundary

Late OAuth callback completion cannot recreate a session cleared by sign-out.
Backend and browser PPC caches are connection-scoped and reject in-flight
repopulation across an account transition. Sign-out/direct account replacement
invalidates AI Crawler results and preview/prefetch state, OneNote candidate
matches and PPC rows/cache state.

The protected Client ID/Secret, same-ID secret reuse, changed-ID
replacement-secret rule, durable failure behavior, six critical write/upload
boundaries, unsafe non-replay and exact `/jobadder/disconnect` behavior remain.
The route inventory remains exactly 108.

## Lookup disclosure

The earlier diagnostic was one read-only
`GET /jobadder/lists?name=worktype`. It caused no remote write, upload, OAuth
login or paid action and did not alter protected credentials. No live response,
account/tenant identifier, token, secret, private URL or candidate data entered
Git, QA evidence, logs or release artifacts; no temporary diagnostic output
remained.

The evidence cannot prove that the browser's local
`ja_perm_work_type_id` key was unchanged. The v24.6.242 QA/handover text and
the v24.6.243 QA report disclose that limitation explicitly.

## Validation record

- Selected Python contract set: 30 passed.
- All six frontend fixtures passed; the account-management fixture contains
  seven cases.
- Local source smoke: 24 assertions passed.
- Tracked syntax: 30 Python, 24 JavaScript, five Bash/command and five
  PowerShell files passed.
- Owner Windows-x64 source preflight, genuine Antiword extraction, vetted
  `adm-zip`, repository consistency and whitespace validation passed.
- Native protected Windows-x64 build and package-only smoke passed. Colleague
  archive SHA-256:
  `d876c604e8f9121a1314a84f0940d981e5fc910714f5d1fa63098d6280406b6c`.
- All five pre-existing v24.6.242 protected-output files rehashed unchanged.
- Per the owner's instruction, the complete regression suite was not rerun.
- Exact preserved contracts: 108 routes, five guards, 18 compatibility
  signatures, SQLite schema 10 and journal schema 1.

Phase 1–5B, Antiword, Blind JD, AI-cost, packaging/redaction and provider
non-replay contracts remain unchanged. This baseline contains no separately
defined Phase 5C milestone.

Stop before handoff or merge. Do not begin Phase 6 without a new explicit
owner authorization.
