# CV Studio v24.6.513 — native company Apply transition

Local branch `codex/v24.6.513-company-apply-transition`, from merged v511
`44f188751c663749e455e20fee947997d06a0c7f` / PR #261. Not published/merged.
Separate JobAdder PR #257 reserves v512 and is excluded.

## Report and evidence

The owner reported the same grouped-company error for Shiseido's logistics ad.
Read-only inspection of the retained search confirmed a selected Shiseido
filter and settled singleton included in its company-header group. The exact
ad links to that same company page. A filtered, read-only local record lookup
confirmed no previous saved HR identity, ruling out a stale saved company ID.
No unrelated record/profile/contact contents were retained in fixtures or QA.

The inspected native company popover's Show results link retains the HR
keywords/origin but omits `currentCompany`. That shape reproduces the reported
error on merged v511 before the change. v511 accepted reordered group IDs and
bare People URLs, but this keyword-preserving filterless address falls into
the invalid-company branch. The exact transient browser-event timing of the
old attempt was not recorded; the native link and deterministic rejection are
directly observed. The popover was restored and the temporary company tab closed.
The original ad/search and saved records were retained.

## Correction and preserved guards

After native Apply, `company_wait` passively permits a URL lacking the company
parameter only when every other canonical search filter equals the original
expected search with that parameter removed. It never adopts that URL as the
expected result, reads profiles or repeats a click. The existing deadline and
frontend wait budget are unchanged. Final results still require one original
group member, any pinned saved ID, matching other filters and native country
confirmation. No company-specific rule or guessed ID is introduced.

HR preflight requires additive `hr_apply_transition_revision:1`, so a stale
companion gives update guidance before individual/bulk discovery. No new
permission, route, persisted field, schema, provider request/retry, credential,
record/note write, owner-install/extension update or protected build occurs.
Concurrent-session isolation and viewed-tab protection are unchanged.

## Verification

- The new worker regression fails on v511 with the exact reported error before
  implementation. Corrected committed, pending and old-group-plus-pending
  transitions wait across repeated suspension/restarts for worldwide/Malaysia
  modes, without profile reads or repeated Apply; the final singleton/country
  then succeeds.
- Wrong keywords, added country filters, empty/duplicate company parameters,
  foreign IDs and wrong paths fail. Existing deadline, pinned-ID mismatch and
  Stop remain authoritative. Existing group, concurrency, source/identity,
  joining-date and frontend old-companion negatives remain.
- Native isolated Chromium loads the actual unpacked companion/content bridge
  and reader against local HTTPS fixtures with external DNS blocked. Its real
  native-style Show results anchor publishes the same filterless keyword URL.
  Five reads stay loading, no allowed profile links are granted and Apply is
  clicked once. Publishing the confirmed singleton yields the observed HR
  result without another click. No real account scan or paid provider call.

Final validation: **2,059 Python tests passed, four skipped, 8,418 subtests**;
all **74 JavaScript fixture files** passed. Syntax/repository consistency,
generated version surfaces, genuine Windows Antiword/Tesseract dependency
preflight and all **24 source-smoke assertions** passed. The isolated preview
on port 5095 serves v24.6.513 with retained separate development state.

The live native inspection was limited to public company/filter/ad evidence
and the relevant record's company metadata; no real HR scan or paid AI request
was started. No native macOS application execution or protected build is claimed.
