# CV Studio v24.6.509 — browsing during companion scans

Local branch `codex/v24.6.509-companion-tab-browsing`, based on merged v508
`156980bbc4af97efdb4d4da15361f37fead4331f` / PR #259. Not published/merged.

## Root cause and authorized behavior

The old activation listener deleted profile ownership whenever its tab became
active. Subsequent exact-page reads failed, and the generic browser error said
to reconnect. This affected Sourcer detail reads and the shared Job Leads HR
joining-date lookups. The owner explicitly requested browsing LinkedIn while
these scans run, superseding the previous activation-stop policy.

Activation now moves profile URL/ID authority from `owned` into a separate
read-only `viewed` map. It survives worker suspension and inactivity but cannot
authorize navigation, scrolling or closure. Current/pending URL and run/source
checks still apply, including an additional post-profile-read check. Actual
page/filter/document changes stop; merely changing the active tab does not.

Sourcer leaves a viewed profile open and allocates a new inactive tab for the
next exact observed candidate. A validated replacement ID updates the existing
controller; counts do not reset. HR can finish reading an unchanged viewed page,
but missing Experience returns an unknown joining date instead of scrolling.
Cleanup releases read references and closes only unchanged inactive owned tabs.

The optional session field is strictly validated and disjoint from `owned`,
with a combined 76-entry bound. Old session snapshots remain readable; older
workers ignore the separate map, so downgrade cannot reclaim control of viewed
tabs. The additive capability rejects old companions before paid planning or
HR discovery. No new permission, route, storage schema, credential, provider
request/retry, automatic paid replay or owner-installation write.

## Verification

Focused regressions cover unrelated activation, viewed reads, new inactive
replacement, activation during injection/staged navigation, real navigation
during injection/after read, worker restart, loading pages, cleanup/reference
release, failed storage writes, malformed/duplicate/cross-map/over-limit state,
legacy snapshots, unchanged profile budgets and invalid replacement IDs. HR
tests cover successful dates and unknown Experience without scrolling. Frontend
tests reject old companions before paid work in standard/Recruiter/Lite and
before individual/bulk HR scanning. Existing actual navigation/filter/document,
Stop, cost/usage and non-replay tests remain.

Native isolated Chromium loads the actual unpacked extension, content bridge,
worker and reader. An authenticated fictional local app observes two fictional
profiles, opens a background profile, activates it, reads it, creates a fresh
inactive replacement, switches to another page, reads the replacement and ends.
The viewed profile and unrelated page remain; only the owned replacement closes;
session read references clear. The successful run maps LinkedIn's hostname to a
local HTTPS fixture and blocks other DNS resolution. An earlier exploratory
run discovered that extension-created tabs escaped Playwright interception and
reached a public LinkedIn authwall for a fictional profile URL; no account,
private profile, credential or paid provider was involved. The final native
test enforces local routing independently of Playwright interception.

Final validation: **2,055 Python tests passed, four skipped, 8,418 subtests**;
all **71 JavaScript fixture files** passed, including the 14 new focused case
groups. Tracked/untracked source syntax, repository consistency, exact generated
version surfaces, genuine Windows Antiword/Tesseract dependency preflight and
all **24 source-smoke assertions** passed. Static bytecode output uses its own
temporary cache to avoid Windows file-lock contention with concurrent pytest;
no product code was changed for that tooling issue. The isolated development
preview on port 5095 serves v24.6.509 using its retained separate state.
No genuine live-account LinkedIn scan, paid DeepSeek request, owner installation
update, protected compilation or macOS native execution is claimed. Separate
JobAdder PR #257 remains excluded. Companion publication/update is still needed
before the owner's installed app can use this behavior.
