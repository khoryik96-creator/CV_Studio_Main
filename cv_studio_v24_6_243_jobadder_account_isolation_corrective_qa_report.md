> **Historical — do not use as the current release reference.** This document is a point-in-time record. The authoritative current version is the repository-root `VERSION` file; see `HANDOFF.md` for current state.

# CV Studio v24.6.243 JobAdder account-isolation corrective QA report

## Release decision

CV Studio v24.6.243 is the bounded corrective successor to immutable
v24.6.242. It addresses all four concrete findings from the one independent
review requested for:

- exact master baseline:
  `21408d0457c9e4c5db5018c39333c32420d54339`;
- exact v24.6.242 review head:
  `e7c86bc0020302723ea845cd046d6592f67263d2`;
- branch: `codex/jobadder-account-settings-signout`.

No second reviewer, repeated review-and-fix loop, live credential, provider
request, paid action, handoff or merge was used. Phase 6 remains inactive.
v24.6.243 remains Windows-x64-only; macOS users remain on v24.6.239.

## Corrected findings

1. OAuth callback completion is now conditional on the original session still
   existing in `exchanging` state. A successful or failed token exchange that
   returns after sign-out cannot recreate an OAuth session or reactivate
   access/refresh tokens.
2. Backend PPC detail cache keys include the protected random account cache
   namespace. A late detail read can populate that cache only if the captured
   namespace and a current access token still exist.
3. Browser PPC records use a one-way server-derived connection namespace.
   Memory, fallback localStorage and IndexedDB cache state are cleared after
   sign-out/account replacement, and in-flight cache reads/writes are rejected
   when the account sequence or namespace changes.
4. Successful sign-out and direct account replacement invalidate AI Crawler
   search results, active search sequence, preview/prefetch caches and visible
   output. OneNote candidate matches and in-flight lookup results are
   invalidated without deleting the user's source notes.

## Preserved account-management behavior

- `POST /jobadder/sign_out` remains POST-only, authenticated by the established
  local guard and protected by the established same-origin/CSRF guard.
- Protected Client ID and Client Secret remain after successful sign-out.
  Access token, refresh token, expiry, API/tenant state, reconnect state and
  protected cache namespace are absent from the reduced durable record.
- Protected-store failure remains visible and restores the in-memory credential
  record rather than reporting false success.
- Pending/completed OAuth sessions and durable AI Crawler prefetch work are
  cancelled/cleared in the established account transition.
- Six existing critical JobAdder write/upload routes remain tracked. Sign-out
  returns the established visible conflict while an unsafe write is active;
  ambiguous unsafe writes are never replayed.
- Same-Client-ID saved-secret reuse and changed-Client-ID replacement-secret
  enforcement remain unchanged.
- `POST /jobadder/disconnect` retains its exact disconnect-and-forget response
  and protected-registration deletion behavior.
- Settings remains the authoritative credential surface; Format CV contains no
  duplicate Client ID/Secret fields. The shared status renderer still covers
  all JobAdder surfaces and missing setup still focuses Settings.

## Recorded read-only lookup

The reviewed evidence records one request:

`GET /jobadder/lists?name=worktype`

It was a read-only GET. It performed no remote write, candidate upload, OAuth
login or paid action and did not alter the protected credential store. No live
response payload, account identifier, tenant information, token, secret,
private URL or candidate data appears in Git history, QA evidence, logs or
release artifacts. No temporary diagnostic output remained in the reviewed
tree or release evidence.

The retained evidence is not sufficient to prove zero application-state
mutation: the existing browser handler can set or refresh localStorage key
`ja_perm_work_type_id` after a successful response. The v24.6.242 QA and
handover records have been narrowed to this accurate statement.

## Focused validation

- Selected Python contract set: 30 passed. It includes 11 account-management
  cases plus targeted Phase 1/2 storage/security, Phase 3 client/PPC/upload/
  redaction, Phase 4 route/cache/Antiword, Phase 5A journal/signature/startup,
  Phase 5B guard/non-replay and Windows/macOS boundary cases.
- All six frontend fixture files passed. The JobAdder account-management
  fixture contains seven cases, including sign-out ordering, all three browser
  invalidators, transition-aware PPC cache schema and authoritative status
  surfaces. Blind JD, JobAdder escaping, frontend storage and AI-cost fixtures
  also remained green.
- One initial combined targeted-run command did not qualify: several requested
  class names were incorrect, and sharing one process let the first module
  remove its temporary database before later storage cases. All 16 tests that
  actually ran passed. The intended cases were then selected correctly and
  run in isolated processes; no production change followed.
- Local source smoke passed 24 assertions without a browser or provider
  request.
- Tracked syntax passed for 30 Python, 24 JavaScript, five Bash/command and five
  PowerShell files. Both inline browser scripts passed owner preflight.
- Owner Windows-x64 source preflight, genuine Antiword extraction, exact
  `adm-zip` 0.5.17 verification, repository consistency and `git diff --check`
  passed.
- No complete regression-suite rerun was performed, as explicitly required by
  the owner after the independent-review pass.

## Protected package

The isolated Windows-x64 native build and package-only smoke passed. Smoke
verified `/ping`, `/status`, the protected browser asset, instance identity,
runtime diagnostics, genuine bundled Antiword extraction and DOCX generation.
The colleague archive is:

`the_guo_lab_v24_6_243_native_protected_windows-x64_colleague.zip`

SHA-256:
`d876c604e8f9121a1314a84f0940d981e5fc910714f5d1fa63098d6280406b6c`.

The build used a temporary state root and did not read the normal protected
credential store. Smoke/runtime evidence contains no token, secret, account,
tenant, private URL or candidate data. The five v24.6.242 protected-output
files rehashed byte-for-byte unchanged after the build.

## Preserved contracts

- Exact route inventory: 108. Removing `/jobadder/sign_out` yields the unchanged
  v24.6.241 107-route contract and hash.
- Five ordered global guards, 18 compatibility signatures, SQLite schema 10
  and Phase 5A journal schema 1 remain.
- Phase 1–5B storage, external-client, persistent-job and AI-cost contracts;
  Antiword; Blind JD; request IDs; redaction; protected-package boundaries and
  unsafe-operation non-replay remain unchanged. This source baseline defines
  no separate Phase 5C milestone.
- v24.6.240, v24.6.241 and v24.6.242 artifacts remain immutable.
- No v24.6.243 Intel or Apple Silicon macOS support claim or artifact is
  authorized.

Stop before handoff or merge. Do not begin Phase 6.
