# Historical QA record — CV Studio v24.6.482

Use root `VERSION` for the current release. This corrects PR #239's P1 finding
against v481: predictable DOM markers could let another loopback website acquire
automatic companion authority.

## Correction

Initial trust requires the real extension toolbar action on the intended CV
Studio installation/address. A derived installation/origin key is pinned in
extension-local storage restricted to trusted extension contexts. The backend
root key uses the existing protected vault under a separate companion service;
it is not an AI key and does not change existing integration credentials.

Fresh random challenges and origin-bound HMAC verification authenticate new
documents and restored workers before granting authority. Copied markers,
unpaired origins, rotated keys, replayed responses and stale/navigating documents
fail closed. Keys never enter page messages, session snapshots, SQLite or logs.
Backend verification requires the live app-session cookie and disables caching;
failed protected writes produce a redacted, structured failure. The existing
GET route handles verification without adding routes/guards or CORS exceptions.

After that one pairing, normal refresh, browser restart and extension reload
reconnect automatically. A changed installation/address needs a new explicit
pairing. Update & Restart plus Apply companion update remains the update flow;
page refresh is left to the user so unsaved drafts survive. Developer mode and
the browser extension must remain enabled.

## Verification

- New hostile-page/wrong-key/pairing tests failed on v481 before the correction.
  New backend session/proof tests likewise failed on v481.
- Isolated Windows Python: **1,779 passed, four skipped, 8,392 subtests**, 185.76s.
- All **47 JavaScript suites** passed on the final production code, preserving
  existing ownership, budgets, ad capture, search, HR and folder assertions.
- Tracked/untracked language syntax, repository consistency, whitespace checks,
  owner-source preflight and all **24 source smoke assertions** passed. The
  actual Windows Antiword/Tesseract checks passed; no protected compilation ran.
- Worker regressions cover unpaired marker imitations, idle-binding takeover,
  wrong/replayed proofs, persistent trust across worker suspension, rejection of
  legacy unpaired session state, navigation during pairing and storage failure.
  Existing sender/frame/document/pending-URL, cold-load, cancellation and local
  update races remain covered. Fixture pairing keys are synthetic.
- Actual isolated persistent Chromium + isolated Flask: marker-only hostile
  loopback pages rejected before and after pairing; the production toolbar
  callback was explicitly invoked in the disposable worker to simulate that
  gesture. No owner browser profile/settings were changed.
- Three native document-idle-before-load cycles recovered automatically only
  after completion and authenticated backend verification. A real production
  controller with simulated held paid planning retained ownership against a
  second app tab, and Stop released the run without replaying planning.
- Native local-file update into a synthetic next manifest preserved an unsaved
  draft and reconnected after explicit page refresh. Trust also survived a full
  browser restart without another pairing gesture.
- LinkedIn traffic was intercepted offline and provider replies simulated. No
  live LinkedIn scan, paid call, outreach, owner data mutation or protected build
  was performed. These checks do not claim native macOS application testing.

Runtime logs are ignored local evidence: `runtime/pytest_482_full.log`,
`runtime/js482_*.log`, `runtime/native482.log`, `runtime/preflight_482.log`.
The sealed 120-route contract, five guards, 80 MiB limit, main schema 10,
journal schema 1, Job Leads schema 2 and companion permissions remain unchanged.
Hosted exact-head checks/review and merge status are recorded on PR #239.
