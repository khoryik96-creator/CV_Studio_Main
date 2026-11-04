# CV Studio v24.6.562 — browser tab grouping

Local source on `codex/browser-tab-grouping`, including unmerged v24.6.561.
The companion groups its authenticated app tab and created tabs under CV Studio
in blue. Central creation covers both scan sessions: Jobs/company/full-ad tabs,
Sourcer profile tabs, HR People sources and employment detail lookups. New scan
tabs explicitly use their app window. Existing user search tabs selected for a
read are not grouped/adopted by that selection.

Native opener and created-navigation-target events extend grouping to tabs
opened from the authenticated app or its created-tab lineage. This covers links,
noopener/noreferrer links and window.open destinations, including Outlook, without
new external host permissions or destination DOM access. Groups stay within each
window; popups that Chrome cannot group are left operational. Existing groups
chosen for the app keep their names, colors and collapsed state.

The new tabGroups and webNavigation permissions enable only grouping/provenance
logic. Only bounded numeric tab/root IDs are kept in Chrome session storage;
no destination URLs/content are stored. Group membership never authorizes reads,
navigation or tab cleanup. Cosmetic operations run independently of scan tab
ownership registration, so a failed/stalled group API or storage write cannot
block scans. Closing a tab removes its grouping metadata. No automatic scan replay.

Validation:

- New real-worker grouping fixture covers app/create paths, normal opener events,
  noopener navigation-target events, descendants, window separation, unchanged
  existing user groups/tabs, suspension, metadata deletion, no acquired scan
  authority, HR source/profile grouping and failed/hung cosmetic APIs/storage.
- Existing Jobs, HR, Sourcer, concurrent-scan, tab-browsing and companion lifecycle
  fixtures pass. Nineteen version/Sourcer Python tests, syntax, whitespace and
  repository consistency pass. All 97 JavaScript fixtures pass in the final serial
  run.
- Native Chromium extension loading could not be exercised: this managed browser
  ignores startup unpacked-extension loading and its supported CDP loadUnpacked
  API reports 'Loading of unpacked extensions is disabled by the administrator.'
  The policy was not changed. Actual native tab-strip behavior is unverified here;
  no claim is made of a successful live extension/browser integration test.

Requires applying/reloading the companion update and enabling its new permissions
if Chrome/Brave asks. Grouping needs the companion in the same browser. No live
LinkedIn/provider operation, email send, backend route/schema change, push, merge
or installed-app update was performed.
