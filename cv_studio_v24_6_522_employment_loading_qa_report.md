# v24.6.522 employment loading - local QA

Base: local v521 1941e58 (including local v520 a076a07), from merged v519
37e9461 / PR266. Branch codex/v24.6.522-employment-loading. The owner subsequently
authorizes publication and merge of the v520-522 stack. Issue35 records final
PR/merge identity. PR257 remains held/excluded.

The owner reports that all employment dates still appear unavailable.
Read-only inspection confirms the normal local installation is still v519.
The retained v521 preview uses a separate older snapshot of job ads, including
blank dates; opening it cannot establish a successful new employment lookup.
A recently affected exact-company live profile did not contain Experience until
scrolling. The same profile's clean dedicated Experience page displayed a
company-linked month/year range immediately. No real person, company identity,
private page content or IDs are retained in this report, fixtures or code.

The date worker now opens only the exact observed profile's canonical dedicated
Experience route. The reader accepts a single recognized Experience details
scope and exact company links, while retaining existing bounded caption parsing,
current/former and grouped-continuity logic. Sidebar, About and Activity dates
cannot supply evidence. General Sourcer profile behavior is unchanged. Profile
and company identity, access restrictions, bounded polling, operation-bound Stop,
concurrent-module isolation, ownership/viewed protection and suspension validation
remain. Query or identity redirects are rejected. A new capability requires the
updated companion for batch and individual checks. Old pending base-profile
sessions are readable without replaying navigation.

Blank legacy/interrupted results now say Not checked. An observed but ambiguous
range is Not confirmed. Optional evidence status survives the existing JSON
store, reopen and backup without a SQL migration. Single validated date updates
mark observed and preserve original scan metadata. Saved scan and bulk queue
summaries report confirmed-date counts separately from saved people. Existing
blank results still need Check employment or an explicit fresh HR scan; there
is no invented backfill. Updating the app alone cannot update the extension.

Verification:
- The new real-worker plus real-Chromium-DOM pipeline fails against the exact
  v521 worker/reader with profile_experience loading; it passes on v522 without
  a fake date reply. Covers batch/single reads, worker suspension, owned cleanup,
  direct current/former dates, unrelated-sidebar exclusion and query rejection.
- Existing native modern/legacy Experience range reader fixtures pass.
- Actual isolated app native fixture passes HR table/search/tabs, date save/reopen
  and original-card refresh, fictional explicit Apollo action, candidate notes,
  paging, filters, Excel and mobile layout. Its RPC mock is not evidence of live
  production extension acceptance; the separate actual pipeline closes that gap.
- Full isolated Windows Python:2192 passed,4 skipped,8418 subtests.
- All80 JavaScript files checked. Two bulk/resume fixtures initially lacked the
  new capability; corrected fixtures and rerun bulk/resume/HR checks pass. All
  remaining77 files passed the full run. No production workaround was added.
- After final unknown-label wording, the23 relevant Python tests were rerun and
  pass. Persistent evidence validation rejects malformed/inconsistent states
  atomically; legacy records remain readable and dates retain precision.
- Tracked-language syntax, version/repository consistency, source/protected asset
  inventory, genuine Windows Antiword/Tesseract preflight and24 source-smoke
  assertions pass. No protected colleague build or macOS testing is claimed.

Ignored evidence: runtime/final522_python.log, runtime/final522_js.log,
runtime/final522_static.log, runtime/baseline521_employment_failure.log and native
fictional screenshots under runtime/people521-native.

Limits: the newly installed production companion has not been run against a live
owner scan. Read-only live DOM evidence plus automated reproduction supports the
specific loading repair; it does not guarantee all LinkedIn layouts/accounts.
Owner app5000, its data and installed companion remain unchanged. Preview5095
is restarted on v522 using the same isolated job-ad snapshot, with no credential
or unlocked-email vault copies. No live paid request, unlock, contact creation,
external message, SQL migration or automatic rescan is performed.


PR267 review correction (before merge):
- The review reproduced an older-ad employment refresh being hidden by a newer
  blank duplicate. A new regression fails on the reviewed commit with Not checked
  instead of the freshly confirmed range.
- Confirmed ranges now carry server-generated microsecond observation timestamps
  independent of the preserved scan timestamp. Deduplication retains the latest
  confirmed evidence, plus its exact ad/revision/company URL for subsequent date
  actions; original title/scan/source and Apollo action sources are independent.
  Legacy confirmed observations fall back to their scan timestamp. Invalid or
  inconsistent timestamp inputs cannot overwrite saved records.
- Native actual-app duplicate fixture passes: older confirmed evidence appears
  despite a newer blank ad, refresh posts to the exact older source, and the
  resulting range survives dashboard and original-card refresh. Backend coverage
  verifies Excel, reopen, backup, later former-employment replacement and atomic
  invalid timestamp rejection. Full CI is rerun on the correction before merge.
