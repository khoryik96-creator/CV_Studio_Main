# v24.6.497 — Job Leads activity and grouped-company fallback

Unmerged branch `codex/v24.6.497-hr-scan-activity`, based on merged v496
`e13727d3e7275b4abbd10affd23ac8f7a123ea52`. Apollo activation remains deferred.

## Cause and correction

Job Leads never called the existing sidebar run-status helpers. Single HR,
bulk HR and job-ad searches now hold a run token until their cleanup finishes.
A bulk queue holds one token across all ads; partial failures report failure,
Stop settles after cleanup, and module loading/invalid input creates no run.

The remaining Cargill failure stopped on its company page. Unlike the layouts
fixed in v496, this header has no singleton connection-search ID. It exposes
only a group of related employee IDs. Read-only header inspection confirmed
the difference. In a separate diagnostic search tab, the native Current
companies popup successfully narrowed that group to Cargill alone. No original
owner tab or saved ad/HR record was changed.

The reader now returns an unambiguous observed group as candidate evidence.
The worker opens that group solely to operate the native company filter: it
requires the exact saved-ad company among uniquely named checked entries,
unchecks the other labels and applies Show results. It reads no grouped
profiles. The resulting singleton must belong to the observed group and keep
all other search identity unchanged; existing visible company/country checks
remain authoritative before profile reads. No first-ID guess or name-only
search fallback is introduced. Interrupted mutations remain non-replayable.
New capability negotiation rejects an older companion before a scan begins.

## Validation

- New reader fixture covers candidate-only group evidence, a non-first exact
  company, fresh native label queries, loading, ambiguous/missing names and
  validation before any click. It failed on the missing fallback before the fix.
- New worker fixture covers Any country/Malaysia, restoration at every setup
  stage, confirmed singleton membership, changed keyword/ID rejection,
  transient faceted navigation and no interrupted-mutation replay.
- Native Chromium runs the actual companion worker and reader against fully
  intercepted fictional pages with a grouped header and no singleton link.
  Any country and Malaysia both pass all three keyword groups, all 11 terms,
  six result pages, six joining-date reads and twelve source-loading races.
  The same fixture using unchanged merged v496 fails before search navigation
  with zero updates, independently reproducing the remaining loading stall.
- Actual isolated-app browser QA shows the orange Job Leads outline/dot while
  the second ad is held, clears running status after Stop and completion,
  preserves the first completed save/draft, starts no third ad after Stop,
  remembers settings and subsequently completes three ads serially. Screenshots
  `job497_running_indicator.png` and `bulk497_progress.png` use fictional data.
- All 62 JavaScript fixture files pass, including activity lifecycle, bulk HR,
  old-companion refusal, ordinary ad searches, company/country binding,
  pagination, joining dates and deferred Apollo flows.
- Source/native preflight and 24 live source-smoke assertions pass, including
  verified Windows x64 Antiword and Tesseract. No protected build was made.

Isolated full regression: **1,888 passed, 4 skipped; 8,416 subtests**.
The single independent read-only review agent returned **No findings** after
reviewing the complete local diff, untracked files and version surfaces against
the verified merge base. It independently ran ten relevant JavaScript suites
and four version checks. It did not repeat the full Python/native browser runs.
Synthetic coverage cannot establish compatibility with every live LinkedIn
layout; the live diagnostic confirmed the native Cargill filter mechanism,
not an installed-extension end-to-end HR rescan.

## Boundaries

The 122-route seal, five ordered guards, 80 MiB limit, SQLite schema 10 and job
journal schema 1 are unchanged. No permissions, paid calls, outreach, hosting,
Apollo activation or email-verdict changes. Tests isolate receipts/databases;
preview 5093 is separate from installed port 5000. The owner's installation,
receipt, extension and saved records were not updated. Existing singleton
company behavior is retained. LinkedIn layouts that cannot be confirmed still
fail visibly without replacing previous evidence.

After delivery, Apply companion update and refresh CV Studio and LinkedIn to
use the new company-filter capability. This checkpoint is not pushed or merged.
