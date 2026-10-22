# CV Studio v24.6.471 — Reliable LinkedIn folder catalogs

Historical QA record; root `VERSION` is authoritative. This checkpoint retains
the reviewed, unmerged v470 Sourcer startup fixes on a new local branch.

The owner reported that existing folders sometimes do not appear in LinkedIn
job-ad dropdowns. Two deterministic causes were found: each card loaded only on
its first focus and then never refreshed; the folder request also required a
successful company/role read from the current ad. A native select could open
before its first asynchronous response, and a failed request while focused had
no retry button. These paths are independent of the Sourcer null-read correction.

The companion now preloads one shared catalog before enabling the folder menus,
refreshes on menu opening/tab return, and provides a small Refresh folders button.
Current/new cards share successful updates; create/select continues across cards.
Valid choices survive refresh. Deleted folders are removed without recreation;
Unfiled remains available for an empty catalog. Failure retains a loaded catalog,
or shows explicit unavailable/retry guidance. Concurrent reads are coalesced;
12-second timeouts and settled promises prevent late responses replacing fresh
data. Initial failures do not trigger an observer-driven retry loop.

Folder metadata no longer parses an ad. Worker source URL/top-frame checks and
an exact-document probe remain, as does the exact bound destination. The app
accepts canonical identity-only input only for the folders action. It reads the
authoritative store without rendering/reloading the panel or changing locks,
selected ads, drafts or records. Read-only metadata may overlap a search; ordinary
add/remove/create requests remain validated, explicit, serialized and non-replayed.
The bridge bounds pending captures and still blocks overlapping writes. A new
capability marker rejects old app pages with actionable update guidance.

New regressions failed before correction for missing initial menu options and
folder reads blocked by unready ad details. Focused tests now cover preload,
reopening, shared/new cards, chosen-folder preservation, external creation/deletion,
empty catalogs, first/transient failure, explicit retry, coalescing, timeout and
late response rejection, tab return, legacy app guidance and bounded concurrency.
Worker checks cover stale/foreign source/destination documents, ongoing searches
and strict ad-save parsing. Actual app-controller checks retain selected ads,
previews, notes and active locks while returning freshly created folders with no
write request. Existing add/remove/restore/create and source identity tests pass.

Full isolated Windows Python: **1,750 passed, four skipped, 8,392 subtests**,
139.11 seconds. **All 42 JavaScript suites passed**; final targeted checks also
passed after catalog failure/status refinements. Static/syntax/repository checks,
Windows Antiword and Tesseract/English preflight, and **24 source smoke assertions**
passed. No protected compilation or genuine local macOS test occurred.

Actual browser verification uses the real companion controls on two fictional
cards in an isolated localhost fixture. Both menus initially contain Priority
and SAP. An externally simulated folder appeared after Refresh; a native-keyboard
selection of SAP survived refresh in both menus. Creating New shortlist added
and selected it across both cards. The native dropdown remained open normally
after refresh, with no distorted card layout. Fixture/screenshot stay ignored
under runtime. This is not a live LinkedIn or installed-extension test.

No owner records, credentials, receipt or installed app/companion is changed.
No route/schema/extension-permission/provider behavior changes or paid/external
writes occur. No PR/merge requested yet. Live use needs both updated app and
companion, refreshed/reconnected after installation.
