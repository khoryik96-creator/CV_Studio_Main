# CV Studio v24.6.223 — Phase 3 Shared External-Service Clients QA Report

Date: 22 July 2026

Phase 3 source baseline: private owner/source v24.6.222 at
`1be9da48d8307c418d82807cbdaedc9f876a1b15`

Completed private owner/source release: v24.6.223

## Release intent

This owner-only release completes the explicitly authorized Phase 3 boundary:
shared JobAdder, Microsoft Graph and AI-provider client foundations behind the
existing Flask routes and helper contracts. It does not change schema version
10, remove or rename a route or legacy response field, migrate credentials,
begin Phase 4 or implement roadmap item 4, 7 or 8.

## Baseline and authorization evidence

- Both the owner `master` worktree and the Phase 3 worktree were clean and at
  the owner-specified baseline commit before implementation.
- The v24.6.222 owner/source release under
  `C:\CV-Studio-Codex\releases\v24.6.222` was freshly extracted and compared
  byte-for-byte against Git: 91 files, zero missing, extra or mismatched files.
- Its independently computed SHA-256,
  `b3caa1e1d32be21f2ea32a9d9eb0a7fe06fdc6c9f687b8abe0bcb8e95fae09dc`,
  matched both adjacent sidecars.
- Entry QA passed 26 Python tests, both frontend fixtures, 24 live-source-smoke
  assertions, all tracked-language parsers, owner-source preflight and
  repository consistency before production calls were moved.

## Implemented client foundations

### Shared transport and errors

- `cvstudio_clients.py` provides bounded timeouts, HTTPS service-host
  restrictions, explicit safe/unsafe retry policy, bounded `Retry-After`,
  redacted response/header handling and `HTTPError`-compatible structured
  upstream failures.
- Unhandled client failures use the established request-ID error contract with
  additive service, code, retry, action and redacted upstream metadata. Mature
  route handlers can continue reading HTTP status/body fields without losing
  their existing response shape.
- Redaction covers bearer/API/OAuth credentials, authorization/cookie headers,
  hyphenated secret names, email addresses and candidate-ID-labelled values.

### JobAdderClient

- All JobAdder OAuth, candidate read/write, attachment, Screening Call,
  diagnostic, list/custom-field, AI Crawler and PPC network calls pass through
  `JobAdderClient`; no JobAdder-specific raw `urlopen` remains in `app.py`.
- Safe reads retry one bounded transient failure. An HTTP 401 receives one
  forced token refresh and retry, after which a repeated rejection marks the
  existing reconnect state.
- Candidate/activity mutations and attachment uploads do not replay after an
  ambiguous network, throttle or 5xx failure. The existing authorization
  refresh path remains available after a definitive 401.
- AI Crawler and PPC retain their offset/limit semantics, caps, count queries,
  duplicate/no-progress detection and all established completeness fields.

### MicrosoftGraphClient

- OneNote and Outlook keep separate protected token stores, delegated scopes,
  device sessions and reconnect state while sharing Graph/OAuth request,
  timeout, token-refresh and parsing foundations.
- Safe Graph reads retry one bounded transient failure. A rejected access token
  receives one forced refresh and retry; repeated rejection clears the rejected
  access token and preserves reconnect guidance.
- Graph `@odata.nextLink` traversal accepts only HTTPS
  `graph.microsoft.com`, detects repeats and is capped at 5,000 items/100 pages
  plus each route's lower `$top` bound.
- Outlook draft and other unsafe Graph writes do not replay after ambiguous
  transient failure. Microsoft device-code creation/polling also remains
  non-replaying; only an explicit refresh-token grant receives one transient
  token-endpoint retry.
- Post-refresh account lookup uses the freshly issued token directly, avoiding
  refresh-lock re-entry.

### AIProviderClient

- Anthropic Messages, DeepSeek's Anthropic-compatible endpoint and OpenAI
  Responses now share endpoint/header construction, HTTPS host restrictions,
  15–300 second timeout bounds, JSON request/response handling and redacted
  structured failures.
- Existing provider selection, DeepSeek web-tool refusal, OpenAI request/
  response translation and provider-neutral `{content,usage}` normalization
  remain in compatibility adapters.
- Chargeable AI POSTs have an explicit zero-retry policy for every timeout,
  network, throttle and upstream HTTP failure. The owner-only paid DeepSeek
  probe still requires the exact confirmation string and was not run.

## Characterization and targeted QA

- The exact 107-route baseline is asserted before and after extraction.
- The final focused client/route-characterization gate passed 19 no-network
  tests covering JobAdder route shapes, offset pagination, refresh/reconnect,
  uploads, Graph JSON/bytes, continuation links, OneNote/Outlook device-start
  secrecy, draft response shape, explicit-token refresh safety, AI endpoint/
  header/translation behavior, timeout caps, zero-retry chargeable calls,
  structured metadata and credential/private-data redaction.
- Every external response was a controlled in-memory fixture. No live
  credential, candidate record, email address or paid provider call was used.

Stable milestone checkpoints:

- `c952e5b` — activate Phase 3 and characterize external-service contracts;
- `8b5f6da` — extract the shared JobAdder client foundation;
- `551307a` — extract the shared Microsoft Graph client foundation;
- `aacbddd` — extract the shared AI-provider client foundation.

## Complete regression and release QA

- `python -W error::ResourceWarning -m unittest discover -s tests -p
  "test_*.py"`: 45 tests passed with no implicit resource warning.
- Both Phase 2A and Phase 2B Node frontend fixtures passed.
- `python tests/run_phase2a_source_smoke.py`: 24 live loopback assertions
  passed on Windows source mode with temporary local state.
- Python syntax passed for all 15 tracked Python files.
- JavaScript syntax passed for all 20 tracked JavaScript files and both complete
  inline scripts in `index.html`.
- Git Bash syntax passed for all 5 tracked shell/command entry points.
- PowerShell parser validation passed for all 5 tracked `.ps1` files.
- Owner-source validation, exact `adm-zip` 0.5.17 dependency preflight,
  repository consistency and Git whitespace validation passed.

## Final compatibility and scope review against master

- All 107 v24.6.222 Flask route URLs remain present and every successful/
  failure compatibility fixture retains its legacy fields.
- `cvstudio_storage.py` remains at schema version 10 with no migration,
  repository or persistence change.
- Protected credential stores, browser mirrors, tombstones, schema-1 local-data
  backup/restore and the v24.6.215 DeepSeek detailed-cost cutoff are unchanged.
- The only raw `urlopen` sites left in `app.py` are the inventoried local
  watchdog, Tavily/SerpAPI search and Apollo enrichment paths, which are outside
  the three authorized client boundaries.
- No Flask server replacement, saved scoring profile, candidate decision
  workflow, persistent background job, broad backend/frontend modularisation,
  lazy loading, credential migration or unrelated user workflow was added.

## Private owner/source archive

The authoritative archive is
`cv_studio_v24_6_223_phase3_shared_external_clients_owner_source.zip`. It has
one `cv_formatter/` root and is generated from the final clean Git commit. A
fresh extraction is compared byte-for-byte with every tracked source file. Its
final SHA-256, source commit, byte size and extraction counts are recorded in
the adjacent `.sha256` and `.verification.json` sidecars under the private
release directory.

## Not genuinely tested

- Native protected Windows/macOS compilation or protected-binary smoke launch;
- physical Windows or macOS installer/restore execution;
- live JobAdder, Microsoft/Outlook/OneNote or paid AI calls.

No protected colleague package was created or claimed.

## Stop boundary

Phases 1, 2A, 2B and 3 are complete. Phase 4 remains inactive and must not
begin without a new explicit owner instruction.
