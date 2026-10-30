# v24.6.521 people dashboards and employment — local QA

Base: local520a076a07 on merged51937e9461/PR266. Local branch
codex/v24.6.521-people-dashboards. No push/PR/merge requested. Held PR257 excluded.

Owner requests all crawled HR people with per-person Apollo unlock, a Sourcer
candidate table following a spreadsheet reference, and actual employment dates.
Reference sheet inspected read-only; no source names/rows are copied to QA/code.
All retained automated fixtures contain fictional identities and accounts.

Implementation and limits are in JOB_LEADS_NOTES.md. New cvstudio_people domain
has no app/transport/credential dependency, is inventoried with explicit acyclic
imports, and uses the existing protected vault for a bounded candidate archive.
No production URL/method,123-route seal,5 guards,80MiB global limit or SQL schema
changes. Additive actions use the existing paired/CSRF/non-replay boundaries.
Source/protected packaging includes the dashboard and contact dialog assets;
no colleague build or protected compilation is produced/claimed.

Read-only owner inspection confirmed saved HR observations with empty dates
while an exact-company profile later displayed month/year metadata. It cannot
prove the historical timing of the earlier scan. Reproduced hydration cases
now wait instead of confirming absence; direct heading scrolling and bounded
caption spans cover the observed modern/legacy structure. A separate explicit
Check employment action refreshes existing blanks without an HR search and
preserves existing dates on missing, stopped or invalid evidence. Authenticated
production companion acceptance still needs the owner to update/reload it.

Validation (final log paths are ignored runtime evidence):
- Isolated Windows complete Python regression:2180 passed,4 skipped,8418 subtests.
- All80 standard JavaScript regression files pass.
- Native Chromium actual isolated app: HR table/tab/search, date-only persistence
  back to original card, one explicitly confirmed fictional Apollo reveal;
  candidate40-row paging, note/filter draft retention, reload persistence,
  filtered genuine Excel and compact desktop/mobile width all pass.
- Native modern Experience fixtures: delayed metadata, current/former month-year,
  grouped continuity, exact company, collapsed/unknown evidence pass.
- Worker synthetic checks cover exact document/scope/profile/company, busy runs,
  owned/viewed tabs, operation-bound Stop and invalid ranges.
- Protected archive tests cover restart, corruption/tamper failure, capacity,
  note conflicts, retained detail/notes, provider accounting on archive failure,
  observed metadata, duplicate HR lookups and literal spreadsheet cells.
- Static/version/repository, source/protected-asset seam, genuine Windows
  Antiword/Tesseract preflight and24 source-smoke assertions pass.

No live paid provider request, email unlock, JobAdder mutation or outgoing
message was used for QA. Owner app5000 and data remain unchanged. Preview5095
uses a consistent read-only snapshot of job ads in an isolated runtime directory,
without credentials/unlocked-email vaults. No genuine macOS run is claimed.
