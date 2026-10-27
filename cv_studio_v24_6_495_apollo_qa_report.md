# v24.6.495 — per-account Apollo OAuth preparation

Base: merged master `a323ad5` (v494). Branch:
`codex/v24.6.495-apollo-hr-emails`. Local checkpoint; not published or merged.

## Implemented

- One shared free-tier Cloudflare Worker/D1 OAuth broker with encrypted
  per-account tokens and outcomes, single-use login/exchange authority,
  serialized token rotation, account isolation, expiry/cleanup and fixed errors.
- The desktop stores an opaque connection and up to 500 email outcomes in its
  existing protected vault. Neither account tokens nor revealed emails enter
  browser storage, Job Leads SQLite or JSON ad backups.
- Compact Connect/Disconnect controls and per-person Unlock email / Copy email.
  Credit confirmation names the data sent and possible charge. Apollo status
  is displayed explicitly; catch-all is never relabelled as our verified result.
- A persisted operation precedes every paid call. Lost replies offer a read-only
  Check lookup. No OAuth exchange, refresh or paid ambiguity is replayed.
- Only `/apollo` GET/POST is new. Its POST requires the current browser session,
  local/CSRF gates and bounded input. Exact previous 121-route digest remains
  independently tested. New contract: 122 routes,
  `4cb6b3f8e64b3421c9b9fae819c7fe64e6b05d98db193bb1eb42f8da07aaf600`.
  Five guards, 80 MiB global limit, existing routes, schemas and journal remain.

## Validation

- Pre-change focused baseline: 101 passed.
- New tests cover protected persistence before spending, permission/session and
  saved-profile/revision gates, no paid retry, restart recovery, blocked/invalid
  destinations and redirects, malformed responses, account changes, cache
  isolation, visible storage failures and login expiry/cancellation.
- Worker tests execute real SQLite statements and WebCrypto using fictional
  Apollo HTTP. They exercise ciphertext binding, callback replay/cancellation,
  wrong-account proofs, concurrent requests, duplicate operation IDs, strict
  profile/company identity, business-email-only requests and refresh ambiguity.
- All 58 JavaScript fixture files pass. Source/native preflight, repository and
  tracked syntax checks, and 24 live source-smoke assertions pass.
- Isolated actual-app Chromium QA confirms setup disabled until configured,
  an explicit unlock and provider status, disconnect/reconnect with a distinct
  fictional account, previous emails disappearing, unsaved draft retention,
  no ad/HR rewrite and no page errors. Screenshots inspected:
  `apollo495_setup.png`, `apollo495_revealed.png`, `apollo495_account_two.png`.
  All screenshots contain fictional intercepted data; none prove live login.
- Final isolated full regression: **1,888 passed, 4 skipped; 8,416 subtests**.
  Earlier failed runs caught additional route-inventory
  declarations and an intentional redirect-cleanup handler annotation; those
  corrections preserve all old contract digests.

## Activation remains required

The broker is not deployed and no Apollo app has been registered. The shipped
broker address is blank, and the UI accurately says owner setup is required.
The owner needs a free Cloudflare account and Apollo app approval; app secrets
must be entered only as hosted secrets. See `integrations/apollo-broker/README.md`.
Live two-account acceptance and a separately authorized credit-consuming lookup
remain pending. No genuine Cloudflare hosting, live provider login, API charge,
owner receipt/installation/data change, protected colleague build, PR or merge
is claimed. Existing installed CV Studio remains separate from preview 5093.
