# CV Studio v24.6.242 Phase 6 handover

## Owner gate

Phase 6 remains inactive. This handover records only the separately authorized
pre-Phase-6 JobAdder account-management and settings milestone. It does not
authorize Phase 6, unrelated AI Crawler product changes, backburner work,
handoff or merge.

## Release identity and platform boundary

- Release: CV Studio v24.6.242.
- Exact source baseline:
  `21408d0457c9e4c5db5018c39333c32420d54339`.
- Supported platform: Windows x64 only.
- Mandatory dependency: bundled, hash-pinned and functionally verified
  Antiword 1.3.5 (engine 0.37).
- No v24.6.242 Intel or Apple Silicon macOS claim or artifact is authorized.
  macOS users remain on v24.6.239.

## JobAdder account boundary

`POST /jobadder/sign_out` is the sole route addition. It retains the protected
application Client ID/Secret while atomically removing local OAuth and
tenant/account state. OAuth sessions, AI Crawler durable prefetch work and
tenant-bound resume/preview caches are invalidated. A critical remote write or
upload produces a visible 409 conflict and is never fake-cancelled or replayed.

The legacy `/jobadder/disconnect` route still deletes the entire protected
JobAdder registration. `/jobadder/store_creds` keeps its OAuth-start response
and gains only the opt-in Settings `save_only` request mode. A saved secret is
reusable only for the identical Client ID.

## Browser boundary

Complete JobAdder setup now lives in Settings → Integrations & Data. The
Format CV surface contains connect/status/upload only. One authoritative state
renderer covers Format CV, Batch, OneNote, PPC, AI Crawler, upload/create
queues and Settings.

Successful local sign-out clears obsolete browser account keys but preserves
`ja_client_id`; Client Secret and OAuth tokens are never written to
localStorage. The user-facing success text is exactly:
`Signed out from JobAdder in CV Studio`.

## Validation record

- Focused backend/cache compatibility: 54 passed.
- One self-review; two concrete race/Client-ID findings fixed; no repeated loop
  or independent reviewer.
- Qualifying complete Python discovery: 149 passed.
- All six frontend fixture files passed.
- Source smoke: 24 assertions passed.
- Tracked Python, JavaScript, Bash/command and PowerShell validation passed.
- Owner Windows-x64 preflight, repository consistency, byte-stability and
  whitespace checks passed.
- Exact final contracts: 108 routes, five guards, 18 compatibility signatures,
  SQLite schema 10 and journal schema 1.
- The QA report records one read-only live JobAdder work-type request that
  occurred during local visual inspection; no remote write, upload, OAuth
  login, paid call or credential exposure occurred.

## Preserved release history

All v24.6.240/v24.6.241 artifacts rehashed unchanged. Mandatory Windows
Antiword and its protected execution interval remain exact. The v24.6.239
macOS baseline remains the newest supported Mac release.

Stop before handoff or merge. Do not begin Phase 6 without a new explicit owner
authorization.
