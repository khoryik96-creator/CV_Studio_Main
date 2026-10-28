# v24.6.515 — Apollo activation and unlocked contacts

## Scope and baseline

From merged master `336ba15` / v24.6.514. Applied the owner's two supplied
patch commits with `git am`, retaining authorship. The public Worker URL ships
without secrets, and Python requests identify CV Studio. Worker profile identity
compares LinkedIn handles across HTTP/HTTPS, country/WWW hosts, slash and case.
Legal-affix-only full company-name equality replaces the patch's overly broad
word-subset fallback; conflicting numeric company IDs and unrelated/Unicode-distinct
names fail. Existing confidence, connection, paid confirmation, idempotency and
no-replay boundaries remain. No external endpoint or OAuth scope changes.

Job Leads adds **Job ads / Unlocked contacts**. Every new successful Apollo
business-email result is copied into separate protected device history. Refresh
also imports previous known successful cached outcomes whose saved HR source
still exists, without broker/provider requests. Person/company/email identities
deduplicate across ads. First saved source context is retained; rescan/removal of
an ad or disconnecting Apollo does not delete the archive. Country is the scan
filter, explicitly labelled, with observed location separate in exports.

The archive uses Windows DPAPI or the established authenticated machine-bound
file vault on other systems, avoiding macOS Keychain command-size limits.
Credentials retain their existing stores. Malformed/decryption failures are
visible; no email mirror is added to plain SQLite, browser storage or ad backups.
5,000 contacts/8 MB limits fail visibly without evicting records. The paid result
and non-replay marker are saved before archival; archive failure leaves the email
on its HR card with guidance to refresh contacts. Disconnect remains available
independently of ad/archive health, preserving its confirmed cache-clearing
contract. Its confirmation warns to copy any unarchived email first.
An import/capacity failure still permits export of existing history, with an
explicit incomplete-archive message/header rather than silently omitting it.

The dashboard provides text search, 40-row paging and real `.xlsx` export of
matching contacts. Export includes name, position, company, scan country,
observed location, email, Apollo status, profile/company/ad URLs and archive-save
time. Source cells are literal strings, never Excel formulas. Search uses the
same lowercase matching in UI/export; Unicode casefold expansion cannot cause
extra exported matches. Only the existing guarded `/apollo` route gains local
actions; no HTTP route/storage-schema/permission/dependency migration is added.

## Verification

- Supplied User-Agent regression; broker tests execute real SQL/WebCrypto with
  synthetic transports. HTTP/HTTPS/host/case/ID/name acceptance and unrelated
  identity/confidence rejections pass; no paid replay or new OAuth scope.
- Domain/guarded-route tests cover automatic archive, restart, intentional
  disconnect retention, fresh-account cache separation, duplicate ads, different
  employers, failed/no-result states, capacity/storage/corruption, recovery from
  cached results, invalid queries, Unicode search, formula-safe real XLSX and
  authenticated no-store downloads. Protected file tampering fails visibly.
- UI tests cover private read-only access while disconnected, search/paging,
  safe source text, filtered export, failures and draft/ad/paid isolation. Existing
  Apollo consent, double-click, account-transition and HR frontend suites pass.
- Native isolated Chromium runs the actual app/guards/UI with a synthetic broker
  and separate protected storage: a button unlock auto-archives; 45 entries page
  and filter; the downloaded real XLSX opens with only the matching contact;
  disconnect and page reload retain history. Desktop/390px mobile views were
  inspected, with no document overflow or browser errors. The temporary synthetic
  server was stopped. No real account/credit or owner data was involved.

Final local regression: **2,099 Python tests passed, four skipped, 8,418
subtests passed**. All **75 JavaScript fixture files** passed.
Tracked-language syntax, repository consistency,
generated-version checks, genuine Windows Antiword/Tesseract dependency preflight
and 24 source-smoke assertions passed. No protected package or genuine macOS app
execution is claimed. The isolated retained preview uses port5095/v24.6.515;
owner installation/5000, credentials, receipt and records remain untouched.

## Publication and live acceptance

The owner authorized pushing, not merging. JobAdder PR #257 remains on hold and
excluded. Git publication does not deploy Cloudflare: deploy the final
`integrations/apollo-broker/worker.mjs` in the existing Worker, then disconnect/
reconnect to clear terminal cached mismatches. One explicitly approved live unlock
and an Apollo credit check remain the live acceptance step. Neither the HTTP-link
diagnosis nor synthetic tests are claimed as proof of a live successful unlock.
