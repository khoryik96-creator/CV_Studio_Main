# CV Studio v24.6.511 — concurrent scans and ad presentation

Local branch `codex/v24.6.511-concurrent-companion` from merged v509
`7a2505161a3cf56dc7ae4675f0cb77648f7e66ff` / PR #260. v510 belongs to separate
JobAdder PR #257 and is excluded. No publication/merge or owner-install update.

## Changes and boundaries

- Instantiate the existing bounded worker separately for profiles and leads.
  Scoped app/content RPCs route to separate sources, allowed URLs, capture
  tokens, budgets, ownership/view protection and session write queues. Shared
  source/tab leases and script/tab API guards reject cross-session authority.
  Both sessions belong to one authenticated CV Studio document. Stop affects
  only its own run. Existing unscoped pages retain the single-run contract.
- Keep the profiles snapshot key and atomically move an untagged old HR/Jobs
  snapshot to the separate leads key. Startup validates exact documents and
  bounds without executing work. Tagged sessions are never reimported.
  Duplicate/corrupt/ambiguous state cannot grant authority. Shared update
  reservation blocks either scan during validation/reload; capability checks
  reject old companions before paid planning or discovery.
- Use fresh inactive tabs for next observed profiles rather than reusing a
  previously loaded tab. This eliminates late old-page events invalidating the
  next expected URL. Conservative cleanup/viewed-tab protection, observed-link
  checks, limits and paid non-replay remain. Gazy's pinned profile-fetch source
  supplied the fresh-tab comparison; no remote code was executed or copied as
  a replacement for CV Studio's guards. The old screenshot's exact transient
  event was not captured and is not asserted as proven.
- Passively await known intermediate grouped-company selections under the
  existing deadline. Never read multi-company results or repeat a filter click.
  Final singleton, saved-ID, foreign/duplicate-ID and other-filter checks stay.
  The Shiseido screenshot had no retained URL proving its precise transition.
- Render literal ad HTML safely through an additive mode of the existing
  read-only formatter. Preserve real headings/emphasis, genuine nested/numbered
  bullets and words; remove empty items/orphan same-kind wrappers. No raw HTML
  insertion, scripts/attributes/links/images, remote-resource load, record or
  draft write. Bounded presentation caching and stale-preview guards remain.

No new permission, HTTP route, SQLite/journal schema, credentials, provider
request/retry, paid replay or protected build is introduced. Tests use fictional
profiles/ad text; owner records/keys/install/companion and private LinkedIn
account scans are untouched. Read-only live tab/visible-link inspection found
an ongoing owner scan; it was left running and no paid action was triggered.

## Verification

- Concurrent worker cases cover overlap/restart, independent Stop, held profile
  reads during HR starts, cross-session source/read/navigation/close rejection,
  exact viewed-page protection, unrelated closure, shared update exclusion,
  one-document binding, legacy busy compatibility and atomic HR migration.
  Late events for a previous profile cannot invalidate its fresh replacement.
- Group selection tests cover reordered groups and known multi-ID subsets,
  suspension without click replay, singleton completion and foreign/duplicate
  rejection before profile reads. Existing identity/country/navigation gates stay.
- HTML/domain/route/frontend cases cover safe bold/bullets, real nested and
  numbered lists, hostile tags, bounds, exact text agreement, unchanged storage,
  deduplicated requests and late responses after another preview is selected.
- Native isolated Chromium runs the actual unpacked companion/content bridge/
  reader with enforced local HTTPS fixtures. Both sessions are active; profile
  reading, activation and replacement continue, and ending Sourcer preserves
  the HR session. No real browser profile/account or paid provider is used.
- Native actual Job Leads UI plus the actual isolated Flask formatter displays
  the fictional raw-HTML case with bold headings and exactly two clean bullets.
  Scripts/images/remote requests and record writes are absent. Visual screenshot
  checked in ignored `runtime/markup511_preview.png`.

Full validation: **2,059 Python tests passed, four skipped, 8,418 subtests**;
all **73 JavaScript fixture files** passed. Syntax/repository consistency,
generated version surfaces, genuine Windows Antiword/Tesseract dependency
preflight and all **24 source-smoke assertions** passed. Additional capability
negatives reject old companions in standard/Recruiter/Lite, Jobs and HR before
scan/paid work. The isolated preview on port 5095 serves v24.6.511 with retained
separate development state. No genuine native macOS app or live-account end-to-
end LinkedIn scan is claimed. Final checkpoint identity belongs in issue #35.
