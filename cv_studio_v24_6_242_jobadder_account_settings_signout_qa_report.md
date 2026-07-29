# CV Studio v24.6.242 JobAdder account-management and settings QA report

## Release decision

CV Studio v24.6.242 is the separately authorized, bounded pre-Phase-6
JobAdder account-management and settings successor to immutable v24.6.241.
It remains Windows-x64-only. macOS users remain on v24.6.239.

Exact source baseline:
`21408d0457c9e4c5db5018c39333c32420d54339`.

Entry verification passed from a clean exact-master worktree. The v24.6.241
owner/source ZIP recomputed to
`f4c27b897d478b4629ccfe8011d6e9019d8f5c5a7f7b0309941afd4fc8b10e76`;
both v24.6.241 verification sidecars named the exact baseline commit; fresh
owner/source and protected Windows-x64 extractions verified; and a 24-file
v24.6.240/v24.6.241 release snapshot was taken and rechecked unchanged after
validation.

## Authorized behavior

- Adds the only authorized route, authenticated/CSRF-protected
  `POST /jobadder/sign_out`, for an exact total of 108 routes.
- Normal sign-out atomically persists only the protected Client ID and Client
  Secret. It removes access/refresh tokens, expiry, API/tenant state, cache
  namespace and reconnect state; clears pending/completed OAuth login sessions;
  durably requests AI Crawler preview-prefetch cancellation; and clears backend
  resume/preview caches.
- A six-route critical-write tracker prevents sign-out from silently
  cancelling or racing candidate/activity writes and CV uploads. Unsafe
  requests retain their no-replay behavior.
- OAuth start and legacy token restore are serialized with account transition
  state so a late request cannot reconnect after sign-out.
- Existing `POST /jobadder/disconnect` remains the compatibility
  disconnect-and-forget operation with its existing response.
- Existing `POST /jobadder/store_creds` gains an opt-in `save_only` request
  mode for the Settings form without adding another route. An unchanged Client
  ID can reuse the protected saved secret; a changed Client ID requires its
  corresponding replacement secret and cannot inherit tenant-bound state.

## Browser behavior

- Settings → Integrations & Data now owns the one JobAdder setup form, with
  authoritative connection/reconnect status, Client ID, write-only Client
  Secret, secure-saved placeholder, read-only callback URI, developer link,
  Save, Connect, Reconnect, Refresh and Sign out actions.
- Format CV retains Connect, connection status and upload controls. Its
  duplicate Client ID/Secret fields and settings gear are removed.
- Missing setup opens Settings, selects Integrations & Data, scrolls to and
  focuses the JobAdder card, and explains the required application setup.
- One shared renderer updates Format CV, Batch, OneNote, PPC, AI Crawler,
  upload/create queues and Settings after connect, refresh and sign-out.
- Frontend sign-out confirms first, uses the established same-origin request
  wrapper, changes `window._jaToken` only after backend success, clears obsolete
  token/expiry/API/tenant localStorage keys while retaining `ja_client_id`,
  invalidates browser preview-prefetch state, refreshes diagnostics and emits
  exactly one success toast.
- No Client Secret or OAuth token is written to localStorage or returned by
  `/jobadder/api_info`.

## Controlled regression coverage

The new backend and browser fixtures prove:

- the exact v24.6.241 route-contract hash remains unchanged after subtracting
  the one new route;
- CSRF/POST enforcement, reduced protected-vault persistence, rollback on
  durable-save failure, safe response fields and post-sign-out API status;
- OAuth-state/session binding, saved-secret reconnect, Client-ID change
  rejection, account-transition races and fresh tenant cache namespaces;
- critical-write conflict behavior and unchanged disconnect semantics;
- complete Settings markup, Format cleanup, missing-setup focus, shared status
  updates, success/failure ordering and localStorage cleanup.

Existing JobAdder client, OAuth, upload, OneNote, PPC, AI Crawler/cache,
Antiword, Blind JD, storage, persistent-job and AI-cost fixtures remain green.

## Validation results

- Focused JobAdder/backend/cache compatibility: 54 passed.
- New JobAdder frontend fixture: six cases passed.
- One focused self-review found and corrected exactly two concrete issues:
  a late OAuth/legacy-restore account-state race and loss of a newly typed
  Client ID before missing-secret rejection. No repeated review loop or
  independent reviewer was started.
- The first discovery attempt did not qualify as the complete run because a
  new fixture lacked the standard temporary receipt bootstrap, three
  historical tests still expected 107 routes, and the pinned local
  `adm-zip` working dependency was absent. Those test/environment issues were
  corrected without another production-code change and the affected cases
  passed before the qualifying run.
- Qualifying complete Python discovery ran once after the final production-code
  change: 149 passed, 0 failed. Three existing `datetime.utcnow()`
  deprecation warnings remained informational.
- All six frontend fixture files passed.
- Live source smoke passed all 24 assertions.
- Static validation passed for 29 Python, 23 JavaScript, five Bash/command and
  five PowerShell files.
- Owner Windows-x64 source preflight passed, including both inline scripts,
  genuine Antiword extraction and pinned `adm-zip` 0.5.17 verification.
- Repository consistency, byte-stability and whitespace checks passed.
- Final contracts: 108 routes, five ordered guards, 18 compatibility
  signatures, SQLite schema 10 and Phase 5A journal schema 1.

## Live-read transparency note

Automated tests used controlled fixtures and no live JobAdder transport. During
the one local visual DOM check, the source server discovered an already
configured protected JobAdder connection on this Windows account; its existing
startup behavior issued one read-only work-type list request. No JobAdder
write, upload, OAuth login, paid call, cache product change, secret display or
credential export occurred. This is recorded because the milestone requested
no live JobAdder contact.

## Preserved boundaries

- All previous 107 route methods, endpoints and response fields remain.
- Five guards, 18 signatures, schema 10, journal schema 1, single-use OAuth
  state, `compare_digest`, backend-only tokens, protected secret storage,
  request IDs, Host/Origin enforcement and unsafe non-replay remain.
- Mandatory Windows Antiword, Phase 5B cost controls, v24.6.239 macOS status,
  Phase 6 and backburner boundaries remain unchanged.
- All v24.6.240 and v24.6.241 release artifacts remain immutable.

Stop before handoff or merge. Do not begin Phase 6.
