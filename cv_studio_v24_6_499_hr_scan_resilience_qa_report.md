# v24.6.499 — bounded Job Leads HR recovery

Local, unmerged `codex/v24.6.499-hr-scan-resilience`, stacked on tested v498
`ac22175`. Merged master remains v497 `ff722b3`. The v498 source-identity
correction is included; its QA report remains an immutable checkpoint.

## Failure paths hardened

1. Repeat scans refresh the exact ad's employer rather than trusting a stale
   display name/URL. When the ad cannot be reread, valid previously saved
   numeric company evidence can be reused only after live reconfirmation.
   Company renames/redirects can update the canonical HR label/URL without
   rewriting the ad; different IDs remain blocked before profile reads.
2. A fresh source redirect has one bounded recheck of the ad employer link,
   before filters/profiles/saves and after confirmed cleanup. The new native
   employer URL must equal the redirect target. An unchanged old link or
   failed cleanup cannot restart. Manual company pages remain strict.
3. Headers are employer/job scoped, using a semantic title or unambiguous field
   group instead of the first three global paragraphs. Leading notices do not
   shift fields. Related-job links/headings, navigation, company-name headings,
   description headings, conflicting employers and incomplete titles cannot
   silently become the current job. Unambiguous location metadata remains.
4. Metadata-only reads wait up to 48 passive polls with a 55-second frontend
   allowance. Full-ad reads retain 16 polls. Stop/pagehide can cancel the exact
   active metadata operation; no new extension permission or server route is
   needed. Its next readiness boundary closes only a safe owned tab.
5. Fixed error reasons distinguish access checks, unavailable ads, missing
   employer links, changed pages, redirect/identity mismatch and timeouts.
   HR loading identifies company, company-filter, country-filter, navigation
   or results. Systemic filter/access failures pause the remaining queue.
6. Same-filter result changes during joining-date work can trigger at most two
   passive rereads, without repeated Next clicks or duplicate lookups. Churn
   beyond the bound fails visibly. Actual source/filter changes remain fatal.

## Regression evidence

- The first repeat-source assertion failed against v498 before implementation.
  New controller tests cover refreshed names, verified cached-ID fallback,
  access refusal, metadata Stop, stage timeouts, one redirect recheck, stale
  redirect/cleanup refusal, result refresh/deduplication and churn limits.
- Worker tests exercise slow metadata after the old limit, exact/mismatched
  cancellation IDs, safe cleanup, restoration, numeric-ID rename/redirect
  acceptance, conflicting identity refusal, tracking-parameter transitions and
  no page-click/budget consumption for result refreshes.
- Reader tests cover leading notices, semantic headers, unrelated job IDs,
  duplicate/description headings, native company-ID reconfirmation and existing
  country/company limits. The header-location path retains visible location.
- Native Chromium runs the actual companion worker/reader with fictional,
  intercepted pages. Both Any country and Malaysia retain all eleven terms in
  three keyword groups, six result pages per case, six joining-date reads and
  twelve controlled source-loading races. A further cached-company case follows
  a renamed/tracked People URL and selects the exact native company ID before
  reading profiles. This exposed and corrected a company-transition tracking
  comparison missed by the initial mocked case.
- The same native fixture with the unmodified v498 reader/worker fails at the
  leading-notice header before any search navigation. The corrected fixture
  completes on v499, independently reproducing and verifying that parser case.
- Actual isolated-app browser checks exercise fresh repeat identity, unreadable
  ad fallback, numeric-ID arguments, metadata cancellation, orange indicator
  completion, repeated saves and unchanged ad labels. Existing three-ad bulk
  progress, Stop, saved results, unsaved draft and preference checks pass.
  Screenshots `company499_metadata_stop.png` and the other ignored runtime QA
  images contain fictional data only.
- Isolated Python regression: **1,894 passed, 4 skipped; 8,416 subtests**.
  All **67 JavaScript fixture files pass**; final runs cover the sealed code.
  Source/native preflight, tracked syntax, repository consistency and
  **24 live source-smoke assertions pass**. Native Windows x64 Antiword and
  Tesseract are functional. No protected colleague package was produced.

## Authority, limits and delivery

No route count/contract, ordered guards, request limit, database/journal schema,
provider/credit/consent or protected credential change. Company/country/native
source authority, revisioned saves, 100-person/lookup, 15-page/ten-minute limits,
owned-tab safety and mutation non-replay remain. No automatic worker/resume,
outreach, paid call, extra browser permission or Apollo activation.

Owner port 5000, source installation, receipts, saved ads/HR records and active
companion were not modified. Preview 5093 is isolated. These tests demonstrate
the covered recovery paths, not universal compatibility with future LinkedIn
layouts. Sign-in/security/access checks require user action; unconfirmable
identity remains an explicit failure with prior saved evidence preserved.

Apply the latest companion update and refresh both pages when using v499. This
checkpoint is local and includes the unmerged v498 correction; no push/PR/merge.
