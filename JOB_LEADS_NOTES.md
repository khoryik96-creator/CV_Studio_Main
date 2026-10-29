# Job Leads module

## HR employment ranges (v24.6.518)

HR cards show **Employment: Oct 2026 to Present**, or an observed completed
range such as **Jun 2020 to Mar 2024**. Year-only source dates stay year-only;
duration text is never used to calculate dates. Old records display only their
saved start date, without assuming Present. Update the companion, refresh CV
Studio and LinkedIn, then rescan to collect evidence absent from a saved scan.

Exact-company modern/legacy Experience metadata is the only date source.
Company logos/role links can arrive before date paragraphs; the reader now
reports loading during that stage within the existing 20 polls / four scrolls.
Present stints take precedence over separate old ones. Continuous visible
promotions retain their start; ambiguous gaps, concurrent stints, collapsed
groups and unorderable year-only endpoints remain unknown. No full-profile,
About, education or role-description date fallback is added. Worker and UI
validate profile identity and optional `left`/`current` fields; the existing
revision-guarded JSON save/backup keeps them without changing the DB schema.
`hr_employment_revision:1` prevents a new scan using an older companion.

The reported historical scan snapshot is unavailable. Read-only inspection
confirmed that the current visible modern entry is readable once hydrated;
the newly reproduced loading path explains a possible missing-date outcome,
not a claim that the exact old snapshot was recovered.

The JobAdder pre-publication correction also binds protected non-replay state
to the account/email rather than account/email/company. Changing the company
cannot bypass an uncertain or completed create. Recovery checks the original
POST company; fresh reviews still bind all selected fields and the account.

## Create company contacts in JobAdder (v24.6.517)

Unlocked contacts offers **Create in JobAdder**. The owner explicitly chooses
an existing JobAdder company; this workflow cannot create companies. Search,
select the company, check first/last name and position, then Review contact and
Create contact. The unlocked email is authoritative and the observed LinkedIn
URL is sent as `social.linkedin`. The scan-country label is never sent as an
address. Existing JobAdder sign-in/permissions apply; no Apollo lookup is made.

The official public v2 OpenAPI was read without credentials: GET companies
supports Name; GET contacts supports Email; POST contacts accepts the reviewed
AddContactCommand fields and reports email duplicates with409. No duplicate
override is used. Exact-email duplicate checks happen during review and again
immediately before creation. Existing contacts under another company are shown
without updating/moving them. Failed/truncated duplicate reads block creation.

The review nonce binds the payload, selected company and current connection,
expires after10 minutes, and becomes unusable when fields/account change.
Protected operation metadata is persisted before POST; timeout/uncertainty can
only be reconciled with a safe lookup, never an automatic POST replay. The POST
sets `safe_to_retry=False`, `retries=0`, `refresh_on_401=False`. A lost result
save leaves the pending marker intact. Duplicate clicks are serialized. The
critical-write guard prevents sign-out/account replacement during the request.
All business data/markers stay protected; no provider response content enters
errors/logs. History is bounded at5,000 operations. No candidate, ad, HR evidence
or email-verifier state is rewritten. One additive local POST route preserves
the122 previous routes exactly and the five global request guards.

Local tests and the actual native app use synthetic JobAdder transport. No real
JobAdder contact was created; account-specific required/custom-field validation
still requires owner-driven acceptance. The installed owner app is separate
from the isolated preview. Held PR #257 is not included.

## Contact view visibility (v24.6.516)

The Contacts panel has the shared `card` class, whose explicit flex display
overrides the browser's default hidden style. A scoped panel `[hidden]` rule
now hides its contents and layout when Job ads is selected. Controller state,
contact data, filtering, export, drafts and ongoing scan behavior are unchanged.
`tests/browser/apollo_contacts_visibility.js` verifies computed visibility with
the real HTML/CSS/controller in Chromium, synthetic responses and blocked
network. It reproduces v515 and passes the corrected initial/selected/returned/
fresh desktop and mobile views. It needs optional Playwright/Chromium, not a
running application or account; the standard JS fixtures still need no browser.

## Apollo activation and contact history (v24.6.515)

The owner's two local Apollo activation commits are applied on merged v514,
excluding held JobAdder PR #257. The configured public broker and named HTTP
client fix the supplied Cloudflare case. Worker identity uses LinkedIn handles;
legal-affix-only name equality and numeric-ID conflict rejection keep different
employers separate. Redeploy the final Worker separately; local/Git validation
does not establish live Apollo account eligibility or delivery quality.

Job Leads has Job ads / Unlocked contacts views. The latter auto-archives
successful Apollo emails in a separate protected device vault, deduplicates
person/company/email, retains history on disconnect, and offers search, 40-row
paging and real XLSX export of matching contacts. It preserves ad/HR records,
drafts and running scans. Country is explicitly the scan filter; observed
location remains separate in export. No browser/SQLite email mirror, shared
team data, new route, storage-schema migration or automatic paid lookup/replay
is introduced. Known old successful lookups can import read-only when their HR
source remains. Storage failure retains the paid outcome with visible recovery
guidance. See the Apollo README and v515 QA report for bounds and verification.

## Native Show results transition (v24.6.513)

Shiseido's retained search and exact ad employer confirmed the correct company;
the saved ad had no previous HR identity. The inspected native Show results
anchor retained the HR keywords/origin but omitted `currentCompany`, while the
settled search had the correct single company. The v511 resolver rejected that
intermediate link as a company change because only bare filterless URLs and
known multi-ID subsets were allowed to wait.

Only in `company_wait`, after the native Apply was confirmed, a URL with no
`currentCompany` may now wait when every other canonical filter matches the
original expected search. The original search key remains authoritative.
No profiles are read, allowed links granted, filters clicked again or limits
reset. The final search still needs one observed group member, the saved ID
when present and the same other filters before country selection and results.
Empty/duplicate company parameters, foreign IDs, different keywords/countries,
other paths, access checks, deadline and Stop still reject. Committed and
pending transitions survive worker suspension without replay.

`hr_apply_transition_revision:1` is required before individual/bulk HR work,
with update guidance for older companions. No storage field, HTTP route,
permission, provider call, record edit or schema change is needed. The fix is
general to the native transition; no company name or ID is hard-coded.

## Concurrent Sourcer scans and rich ad repair (v24.6.511)

Job discovery, direct captures and HR scans use the `leads` companion scope;
Sourcer uses `profiles`. Both can run together in the same authenticated
CV Studio document, with independent run/source/Stop/ownership/counters and
snapshots. Job Leads still runs one of its own workflows at a time. No scan may
adopt another session's reserved source/profile. Viewed tabs remain protected;
updates wait for both sessions. Old companions fail before starting discovery
or paid planning. See Sourcer notes for migration and authentication details.

During native grouped-company selection, a reordered group or a still-known
multi-ID subset can remain visible while Apply finishes. Wait passively under
the existing deadline without reading people, replaying a click or resetting
the scan. Foreign/duplicate IDs and changed other filters still fail; only a
singleton from the observed group (and saved ID when present) authorizes HR
results. The Shiseido screenshot did not retain its transient URL, so no claim
is made that every instance of that message had this exact cause.

Some saved descriptions contain literal HTML rather than plain text. The
existing `format_content` route can now produce a read-only presentation of
that markup using bounded server-side HTML parsing and the established semantic
tag allowlist. No raw HTML is inserted into the page. Empty list items and
same-kind orphan list wrappers are removed; genuine nested/numbered items stay.
Scripts, attributes, links, images and remote resource loading are absent.
Stored records, drafts, notes, dates and backup/export content are untouched.
A bounded per-tab cache deduplicates presentation requests; stale responses
cannot overwrite a newer preview. No provider or new route/schema is involved.

## Browsing during HR scans (v24.6.509)

The owner can switch LinkedIn tabs while a scan continues. Viewing a temporary
joining-date profile retains exact-page read authority, but permanently releases
automatic navigation/closure. If Experience is still missing, its joining date
remains unknown; the companion never scrolls a viewed tab. A second page-side
visibility check protects the scroll boundary. Completed reads release their
reference while leaving viewed pages open. Other user tabs are never adopted.

The shared worker persists bounded read-only protection across suspension,
keeps it separate from owned action authority and rechecks real URL changes.
Existing company/search/native country, snapshot, document, run/page/profile,
Stop/save-revision guards remain. `profile_browsing_revision:1` requires the
updated companion before individual/bulk HR discovery. No provider call,
permission, route, record/storage schema or paid replay changes. See Sourcer
notes and the v509 QA report; actual scan-page/filter edits still stop.

## Minimal discovery and form UI (v24.6.503)

Discovery starts with labelled keywords/location/source/pages fields and Search.
Companion setup/update instructions live inside one collapsed Companion menu;
both helpers keep their status element in the button's parent as required by
the shared helper. Folder selection stays visible for direct LinkedIn saves.
Stop/Clear/Add/selection controls appear when relevant. Actual errors/progress
remain visible; empty live status regions retain accessible presence without
occupying layout space.

Empty previews and curation containers are hidden. Closing a real preview leaves
results at full width, keeps selections/drafts/folder choices, and does not
reopen a saved ad silently. Real captured content and excerpt labels remain;
empty content boxes and generic creation/content guidance are absent. Created
dates appear only for saved records. The form removes repetitive descriptions
and uses shorter fields/notes. No backend/reader/record contract changes.

## Compact controls and observed header recovery (v24.6.502)

Folder selection/buttons share a toolbar; selected count/move controls share
one row; HR action, country/name and pages use a compact panel. Labels remain
accessible, country/pages keep existing preferences, and mobile controls wrap.
At the same 1440px viewport the controls measure 339px instead of 666px (49%
shorter). Record, selection and persistence contracts are unchanged.

Live DKSH/cbs headers contain an icon-only verification link inside the title.
The paragraph detector accepts it only for the exact current job, containing
the named Verified job image and no other text except the known annotation.
Other links/buttons, foreign jobs and ambiguous employers remain rejected.
This corrects the v499 all-anchor rejection.

A completed company document with no heading and an empty body can receive
one reload after twelve passive polls, only while its exact unchanged source
is inactive. Bounded count/marker survive suspension and persist before reload.
Failed writes, different/pending navigation, active tabs, sign-in/checks and
nonblank unknown layouts cannot authorise it. Interrupted reloads allow only
passive confirmation, never another reload. Exact company/native filters still
precede profile reads and saves. Stop invalidates the run at existing await
boundaries. `hr_layout_revision:1` requires the updated companion.

## Review corrections (v24.6.501)

One title paragraph exposed as both a semantic heading and an employer/title/
metadata row now counts once by DOM identity. Distinct headings remain
ambiguous, and employer/job/description/sidebar boundaries remain. Optional HR
email checks retain their verifier-provided recheck reference for the unchanged
address only; input edits and cleared account suggestions discard it together
with previous/pending results. No saved HR/ad fields or paid calls change.

## First-party email verification on HR cards (v24.6.500, unmerged)

Each HR card has an optional Email to verify field and explicit Verify email
button. It uses the existing first-party `/email-verifier` route in Deep mode;
displaying a card or revealing an Apollo email does not probe mail servers.
Existing revealed Apollo emails can prefill the field; edits remain manual,
and disconnect/account changes clear any unchanged suggested address, result
and late response. Verification does not unlock an email, connect Apollo,
spend credits, send mail or save email fields with ads/HR scans. Manual checks
work while Apollo activation is deferred. Checks report mailbox evidence,
catch-all behaviour, qualitative recommendation and time in the card only.
See EMAIL_VERIFIER_NOTES.md for limits and the v500 QA report for validation.

## HR resilience and bounded recovery (v24.6.499)

Every automatic/repeat scan rereads its exact ad's employer. A manually changed
company-page URL keeps the strict manual path. If a previously scanned ad is
unavailable, missing its employer link, times out or uses an unknown layout,
only its valid saved source/company-ID binding may be reused. Access failures,
disconnection and changed source tabs do not enter that fallback. The live
company header must reconfirm the saved numeric ID; native group selection must
also commit that same ID. It may then adopt the current canonical name/URL.
An unrelated company's ID always stops before profile reads.

Company People tracking parameters are normalized only for the old company
page during the exact requested search transition. Actual search filters keep
their existing binding. A fresh ad whose company link redirects without prior
numeric evidence receives one source-link reread, following confirmed run
cleanup and before any filter/profile/save work. The reread employer URL must
equal the observed redirect target. No confirmed link, Stop or unconfirmed
cleanup means no restart. No page click, paid action or ambiguous mutation is
automatically replayed.

Standalone headers use employer/job-scoped semantic headings or one unambiguous
employer/title/metadata group before the description. Navigation, related-job
cards, other job IDs, company-name headings, description headings and ambiguous
employers cannot supply the title. Leading notices do not shift global field
positions. Unrecognized/localized controls still fail visibly; no location or
company filter is dropped to produce results.

Company-only metadata gets at most 48 passive polls (full-ad reads retain 16),
within a 55-second frontend request allowance; initial page loading remains
bounded. `jobReadCancel` requires the exact active operation ID and verified
app document, and only cancels metadata capture. Stop/pagehide request it; the
worker exits its next readiness boundary and cleans only its unchanged inactive
owned tab. This cannot interrupt another request, native filter mutation or
paid operation.

HR readiness has bounded company, company-filter, country-filter, navigation
and result stages. The frontend uses at most 120 polls per page/paging wait.
Systemic filter/access failures stop the remaining queue. Results changing
under unchanged filters cause at most two passive same-page rereads per scan,
with existing person deduplication, 100-person/look-up and total page/time limits;
no Next click or budget is consumed by a refresh request. Continuous churn fails
visibly and retains previous saved results. Structured `HR_*` reasons are
additive beside the legacy error string and contain no private page content.
`hr_resilience_revision:1` requires the current companion before single/bulk HR.

## Saved labels and verified employer identity (v24.6.498)

A saved public/search-card label can be shorter than the employer link in the
same job's full header. Do not compare the saved label to LinkedIn text as the
identity boundary. `jobFromLink(company_only:true)` must confirm the exact job
URL and a single native employer link in two consecutive observations. The
worker keeps only bounded job/company URL/name/time metadata, scoped to the
verified app document and expiring after two minutes. `hrBegin(job_url:...)`
requires that exact observation; another ad, URL, name, expired proof or app
document cannot reuse it. It is consumed when the scan begins.

Only this source-confirmed path may read the heading of the exact linked
company page as the native filter name. Company URL, observed singleton/group,
country, keywords, joining-date checks and save revision remain enforced.
There is no fuzzy alias or name-only company search. Manually entered company
pages keep strict name matching. Saved `hr.company` continues to equal the ad's
unchanged display label; optional bounded `hr.company_name` records the verified
LinkedIn name and is shown in the HR panel/reused on later scans. Legacy records
without it remain readable, including backup/restore; no schema bump or
migration occurs.

Metadata-only reads need the identity-confirmed employer header, not About
content. A company-name container's Follow controls do not become its label;
multiple labels sharing one exact company URL are one identity, while
conflicting/foreign links remain unconfirmed. Same-ad loading and document
replacement receive bounded passive waits/reinjection without re-navigation.
Missing employer links use the full existing sixteen-poll bound and report a
specific error. `hr_company_source_revision:1` gates older companions before
single/bulk scans. Apply the companion update and refresh both pages.

## Scan activity and grouped-company selection (v24.6.497)

Single HR, bulk HR and job-ad searches now hold one token in the existing
sidebar activity system: orange during the scan and cleanup, then the normal
completion/error state. A bulk queue holds that token across all ads; any
failure leaves an error indication even when later ads save. Stop settles it
after cleanup. Loading the module and invalid inputs create no run indicator.

Some company People headers contain only a related-company employee group,
without the singleton link used by v496. The reader returns those observed
IDs as candidates only. The worker may open that group as a setup step, but
does not read profiles. In the native Current companies popup it requires one
checked label matching the exact saved-ad company, unique checked names and
the expected group count, then unchecks the other native labels. Each click
uses a fresh DOM query. Show results must commit a singleton from the observed
group while preserving keywords and other filter identity; normal visible
company/country checks still precede profile reads. Bare faceted-search and
unchanged group URLs may wait during navigation, never authorize results.

Each native mutation persists an interrupted marker before clicking; a partial
failure or suspended worker cannot silently replay it. A missing/ambiguous
company remains unconfirmed. `hr_company_filter_revision:1` is required before
single/bulk HR starts. Apply the companion update and refresh both pages.
No new permission, external API, paid call or persisted ad/HR format is added.

## Grouped company headers (v24.6.496)

The three owner-reported batch failures stopped on their company People pages,
before a search opened. LinkedIn's employee link listed several related IDs;
the separate exact-company connection link used an HTTP-valued URL. The old
reader discarded both and repeatedly returned loading. A singleton HTTP ID is
now usable only inside the matching company header, on the recognized native
connections route/query and corroborated by its HTTPS employee group. The
reader never navigates that HTTP link. Conflicts, unrelated recommendations,
foreign URLs and missing evidence remain unconfirmed. Existing HTTPS singleton
headers are unchanged. `hr_company_identity_revision:1` is required before any
single/bulk scan so an older companion gives update guidance immediately.

## Apollo connection (v24.6.495, local; activation pending)

Saved HR cards can explicitly unlock a business email through the user's own
Apollo account. Setup is shared once; colleagues sign in individually. The
hosted broker source and owner setup are in `integrations/apollo-broker/`.
The blank root `apollo_connection.json` makes setup unavailable until a real
approved deployment is configured. No provider password/token is returned to
the browser. The protected local `apollo` vault keeps account-scoped outcomes;
ad/HR SQLite and JSON backups receive no email or credential fields.

Credit confirmation precedes the durable operation marker and paid transport.
Uncertain lookups offer Check lookup, which reads the original operation only.
Disconnect overwrites the protected local record and clears visible results;
changing accounts cannot reuse an earlier account's cache. The email label is
Apollo's assessment, separate from first-party SMTP verification. No live
service, registration, credit-consuming request or outreach was performed.

Current version is the repository-root `VERSION`. This owner-requested module
tracks LinkedIn job ads for business development, separately from the candidate
sourcer and the locked historical Lead Finder.

## Bulk HR scans (v24.6.494)

Use the existing saved-ad checkboxes (or Select ads on this page), set the
shared country and pages in **Find HR people for selected ads**, then click
**Scan selected ads**. Country/page choices are prefilled from the same
validated preference as individual HR scans and changes update that preference.
The collapsed HR keyword field applies one title query to every selected ad.
Country may be Any country; pages remain 1–15 per ad. A queue is capped at 40
ads, matching one board page; selection across pages still works within that
cap. Ordinary folder moves are not limited by the HR queue cap.

The native progress bar counts processed ads. Current company/role, page or
joining-date stage and a per-ad result list stay visible; errors and limited
scans are distinguished from complete saves. Each ad uses its own original
revision, fresh companion run and exact company scope, with awaited cleanup
before the next starts. A single reusable scanning function backs both bulk
and individual scans. Unsaved form text and selection stay intact.

Completed results save independently using the existing `save_hr` operation.
A per-ad missing company/layout or revision conflict is reported without
overwriting prior results; other ads can continue. Disconnected/busy/old
companions, LinkedIn access restrictions and unconfirmed cleanup stop the
remaining queue. Stop waits for the current bounded read, retains completed
saves and does not start another ad. An unavailable or unconfirmed save also
halts the queue and requires a refresh, without replay or a claim that an
ambiguous write definitely failed. An atomic save already sent may finish
and is counted honestly. Pagehide stops and ends the exact active run; reload
does not resume a queue. Keep the CV Studio tab open. This is browser-driven,
not a durable worker, and uses no AI/provider call or outreach.

The established source-tab retention and 100-person/15-page/per-run limits in
the companion remain unchanged; no new companion permission/action or server
route/schema was introduced. The user can inspect completed HR people through
each ad's existing HR people button.

## HR joining-date loading and remembered controls (v24.6.492)

Joining-date checks now distinguish an unchanged source reloading from an actual
company/country/keyword change at every verification boundary. Same-filter
loading waits without opening a duplicate profile or spending another profile
budget. Cleanup may release an exact inactive owned profile during that loading;
the next lookup cannot inherit a false interrupted state. Actual filter or
pending-navigation changes still stop, retaining previous saved HR evidence.
The UI requires the additive joining-loading companion capability.

Explicit country mode/name and pages are remembered in the browser's bounded,
validated `cvstudio_job_leads_hr_preferences` setting, across ads and reloads.
Absent a preference, the saved scan country/default page count are retained.
Any country remembers its mode without discarding the last typed country.
Invalid storage is ignored; blocked storage retains the choices for the current
tab. These controls never rewrite the country/provenance of saved HR matches.

## Companion connection and updates (v24.6.480)

The v489 saved-ad HR correction reads modern list items nested one wrapper below
the results list. Only the first wrapper carries a SearchResults component key;
the old selector consequently saw just one of ten cards. Reading remains scoped
to the primary results region and retains exact company/country badge checks.
Native pagination's `spellCorrectionEnabled` and `prioritizeMessage` URL options
are excluded from the identity key, alongside the existing page/tracking fields;
company, geography, keyword text and other filters remain identity-bearing.
If the location button has not hydrated, no click occurs and the existing bounded
poll loop can wait. An invoked/ambiguous action still never replays. Reader
exceptions use fixed, step-specific messages and never expose arbitrary page text.

Trust the normal CV Studio installation/address once using the companion toolbar
icon. The enabled companion then reconnects automatically when its verified tab
loads or is revisited. Fresh backend challenges authenticate the paired identity;
another local page with copied markers cannot connect. The toolbar remains a manual recovery option. Active
worker runs/captures and document ownership remain protected; automatic connection
does not start searches, writes, profile reads or paid requests.

Find job ads includes **Apply companion update** and a collapsed **Set up
companion once**. Load the bundled folder copied from the normal installation
once, with Developer mode kept on. Update & Restart then updates those files;
the in-app action reloads the matching local bundle while idle. Old downloaded
copies require this one-time migration or continued manual ZIP updates. The
action leaves page refresh to the user, preserving unsaved drafts.

## Standalone ad / HR company-read correction (v24.6.483)

Modern standalone LinkedIn ads can render their title as a plain paragraph while
job-type buttons still point to the same ad. Only a recognized visible
company/title/location header establishes that plain title; incomplete or
ambiguous headers stay loading instead of importing a job-type label as a role.
Existing linked-title and search-detail layouts remain supported.
The v484 review correction clears standalone fallback selection unconditionally:
a leading notice before the recognized tuple cannot retain a paragraph-wrapped
job-type link, including during company-only HR reads. Unknown header layouts
fail with the existing specific guidance rather than importing a guessed role.

HR's `jobFromLink` call sets `company_only: true`. It validates the same canonical
job/header/company identity but does not wait for or collect the description.
Only literal boolean true enables this mode. Normal ad imports, preview reads
and direct-add controls keep the existing full-content behavior. No metadata-only
result overwrites saved ad content: HR uses only its confirmed company link.

A newly created extension-owned job tab may briefly lack both committed and
pending URLs. Its existing bounded load poll can wait through that exact loading
state; another pending target fails before reading. Page access/layout/injection
errors receive fixed, redacted guidance rather than a generic disconnect claim.
After a companion reload, refresh the open CV Studio and LinkedIn pages to
replace invalidated content scripts. Timeout guidance supports Chrome and Brave.

## HR search transition and modern filter correction (v24.6.485)

After the company employee link is confirmed, the companion persists a
`search_wait` stage. Chrome can still report the old company document as complete
after accepting the navigation. That exact old page may wait for the requested
People search; it cannot supply results, trigger a second navigation or authorize
a different pending company/search. Once ready, the full company/keyword/country
search identity remains pinned. Worker suspension retains this waiting state.

A same-search load beginning during reader injection also waits before invoking
any filter/page action. Only this worker-generated pre-action sentinel permits
retrying an action; missing/invalid results after invocation remain interrupted
and never replay. Deferred next-page attempts do not consume the page budget.
The controller polls explicit paging-loading responses within its existing
90-attempt ceiling, preserving Stop and avoiding false completion/saving on timeout.

Modern selected company/country inputs can get their names from associated
visible labels. Country controls also support role-based Locations buttons,
exact option rows with native buttons and the location popover outside the filter
toolbar. Unchecked/different company or country labels cannot authorize results;
partial country suggestions cannot be selected. Result reads prefer the primary
content region, including its current semantic-section layout.

No route/schema/permission, pairing, scan limit, paid call, saved-ad data or
joining-date ownership change. Development and QA do not update the normal
installation. After adoption, apply its companion update and refresh the open
CV Studio and LinkedIn pages to replace older page scripts.

## Bounded HR keyword searches (v24.6.486)

The default eleven-term Boolean returned no results on the owner's normal
LinkedIn People search, while the same current-company filter returned people
with short queries. The companion now groups up to five distinct comma-separated
terms per query; it does not discard the remaining terms or remove the company
or country. Five is a conservatively tested group size, not a claim about a
universal LinkedIn account limit.

All groups share the original page, profile and ten-minute budgets. Empty
nonterminal groups advance rather than ending the scan. Repeated people across
queries are deduplicated, and query-aware page signatures distinguish identical
result cards from a stuck page. Company/country filters and all original matching
keywords remain pinned. Interrupted query navigation never repeats after worker
suspension. Older in-flight sessions remain readable; new UI requires the
corrected companion capability before starting HR scans.

The shared page budget reserves a first result page for each remaining group
when possible. Skipping further pages in an earlier group keeps the final scan
limited, including when the last group has no next page. A small limit can still
leave groups unreviewed; it never silently increases the selected page count.

Saved evidence keeps the full original keyword list and the final confirmed
company/country source URL, within the existing record and backup format. A scan
that reaches its shared limits remains limited even if some keyword groups or
result pages were not reviewed. No paid request, new permission, route, database
migration, owner installation update or external write is introduced.

## HR completeness at the result ceiling (v24.6.479)

The 100-person cap applies to unique canonical profile links. If a final-page
snapshot contains additional unique matches after the cap, the saved scan and
completion message remain limited even when LinkedIn shows no next page.
Exactly 100 retained matches, or duplicates after the ceiling, do not falsely
mark an otherwise complete final page as incomplete. No extra profile lookups
or pages are requested; the saved limited label survives reopening the ad.

## HR unload cleanup (v24.6.478)

Reloading/closing the app ends its HR run on pagehide and prevents a late read
from saving. If that final message is lost, the worker also clears the run and
closes unchanged inactive owned tabs on app navigation/removal or failed
exact-document restoration. Matching pending profile loads are cleaned too,
including a tab whose creation completes after the app disconnects. User-taken-
over/redirected tabs and the retained company search remain untouched. No scan
or paid operation is restarted during cleanup.

## Complex-ad plain-text fallback (v24.6.477)

If the optional rich serializer reaches its 4,000-node / 32-level limit, the
ad still imports its company, role and a readable plain description. A separate
iterative walk keeps the same hidden/control/active-content exclusions, stops
after 16,000 nodes or a 20,000-character excerpt, and drops optional markup.
Truncation or a visible More control is labelled as an excerpt. Normal captures
retain the original rich formatting; identity/access/layout failures still stop
instead of being swallowed by this size-only fallback.

## HR company joining dates (v24.6.476)

Each HR result card shows **Joined company**, using a month/year or year-only
date explicitly visible in that profile's current company Experience. Missing,
hidden, unrecognized or ambiguous evidence shows **Not available**. The scan
does not subtract tenure durations or infer a date from headlines. Promotions
within one fully visible company group use the earliest explicitly dated,
continuous role; a separate former stint cannot replace the rejoining date.

After each results page the companion checks the observed HR public profile
links sequentially in temporary inactive tabs, up to 100 per run within the
existing ten-minute ceiling. Exact profile/company identities and current
employment dates are required. Activation relinquishes navigation/closure
ownership (v509 retains exact read access); navigation relinquishes all authority;
user tabs remain untouched. Each lookup is polled briefly, and a slow/missing
Experience section leaves its optional date unavailable. Up to four persisted
scroll attempts load LinkedIn's lazy Experience content within that owned tab;
an empty loading skeleton is polled instead of being treated as final evidence.
Restrictions, identity
changes and interrupted browser actions stop visibly and preserve saved results.
The attempt count is persisted before opening; suspension during creation cannot
silently open another tab. No captured Experience text/date enters worker
session state. The existing saved-ad JSON evidence/backup retains the bounded
optional date; older records remain readable and show Not available until a
new HR scan. No route, database schema, extension permission, AI call or outreach
is added. Update/reload the companion and reconnect for joining-date scans.

## Rich-content capture corrective (v24.6.475)

Modern LinkedIn can put an aria-hidden **“… more”** button inside the About
section, before benefit text. The previous reader retained that label in plain
text but the passive HTML sanitizer removed it. The exact-text consistency
check then rejected the whole rich tree, losing otherwise valid bold and lists.

Both companion job readers now derive plain text and passive markup from the
same bounded DOM traversal, excluding controls, hidden/active elements and all
source attributes/URLs. Semantic lists/headings/emphasis remain; computed bold,
italic and block layout are converted to passive tags, and explicit ARIA list
roles remain lists. No styling rules or source code are executed/stored.
Visible expansion controls still mark captured excerpts. Existing size/depth
limits, job/source identity and companion ownership checks remain.

At the established 20,000-character capture limit, a matching semantic prefix
is clipped to the retained text instead of discarding all formatting. The final
exact-text gate still applies; short/manual mismatches remain rejected. Public
reads can use one canonical visible description's richer formatting when its
words exactly match the retained metadata text; metadata fields/text are kept.
Oversized optional markup cannot break a valid metadata-only result.

The shared preview/form/saved-ad renderer already supports these passive tags;
no display-only guess of bold or bullet meaning is needed. Older saved plain
captures cannot recover their original typography locally. After updating and
reloading the companion, use **Edit / view details → Refresh ad content → Save**.
Public reads use the corrected backend directly. Existing duplicates, drafts,
folders, HR results and manual contact/status/notes remain unchanged; no
automatic record rewrite, paid call, route/schema or permission change occurs.

## Phase 2: company HR people (v24.6.474)

Saved active ads have **HR people** beside Preview. Preview also shows a
Phase 2 column beside the ad. Choose **Any country** (default) or enter a country
name, then **Find HR people**. Search options retain comma-separated title
keywords, a 1–15-page ceiling (default 3), and an optional company-page override.
Defaults include HR, human resources, CHRO, chief people officer, talent
acquisition, TA, recruitment, hiring, recruiter, HRBP and end to end recruitment.

The connected current Chrome companion reads the exact ad's company link when
needed, opens that company's People page, verifies its heading against the saved
company, and reads the header's observed single-company employee-search ID.
It opens a standard People search with that Current company filter and the HR
keywords. For a named country it uses LinkedIn's visible location chooser and
one exact suggestion, then verifies the settled geo filter and visible checked
company/country labels before reading. No guessed company/geo IDs, private API,
paid provider, contact enrichment, messages or LinkedIn writes are involved.
The source tab remains open; existing user tabs are never navigated or closed.

Only observed public profile links and visible name/title/location are retained.
Title keywords use word boundaries (TA cannot match “data”); matched terms are
shown. Company association comes from LinkedIn's Current company search, not a
claim that employment or hiring authority has independently been verified.
Unknown/collapsed profile details are not inferred. Results cover the requested
pages, up to 100 unique matches, not an exhaustive employee directory.

Normal completion saves results, country, keywords, source and local scan time
with that ad. Opening it again displays the saved results without a new scan.
Notes, manual contact, folder, status and creation time remain. Ordinary ad saves
preserve current HR evidence; changing the company or job identity clears it.
Trash/folder moves and the existing JSON backup/import retain HR evidence.
A dedicated revision-checked `save_hr` action on the existing guarded
`/job-leads` route updates only evidence; concurrent edits/Trash reject stale
results atomically. New bounded JSON payload fields require no database schema
change (Job Leads remains schema 2; main DB 10 and journal 1 remain).

Stop, failed reads, unrecognized layouts, restrictions and storage failures keep
previous saved results. Partial matches may remain visibly unsaved until another
scan/navigation. HR browser work is isolated from Jobs/profile/capture runs, has
a ten-minute ceiling and persists its page budget in extension session memory.
Pending mutations are marked before native clicks/navigation; an interrupted
mutation cannot replay after worker suspension. Exact app-document/source/filter
checks remain, including checks around reader injection. No automatic resume,
new route, extension permission or packaged asset is added.

Existing installations need the updated companion files, Reload, refreshed
CV Studio/LinkedIn pages and a reconnected app tab. Automated reader/worker/UI
fixtures and an isolated browser demo do not prove a real installed-extension
end-to-end scan; live company/location controls were inspected read-only.

## Workflow

- Open **Job Leads** and paste a LinkedIn job link. Public company, role,
  location and description load directly, including in the in-app browser.
  **Fill from link** starts a new read. On a recognized public-unavailable or
  public-rate-limit failure, a connected, idle Chrome companion is tried once
  automatically (v24.6.456). A short read-only bound-status probe avoids a long
  capture timeout when disconnected; an active profile/Jobs/capture run is left
  alone. No public request or browser capture is automatically repeated.
  Setup expands when the companion is unavailable or a capture fails.
  Existing manual entries are preserved.
  Review the details before saving; manual entry remains available.
  Replacing an unsaved draft's job link asks before clearing its job-specific
  fields. The folder is retained; a cancelled or failed read keeps the old URL
  and details. Same-job manual corrections remain. Save independently rejects
  a different URL that has not been loaded into this draft; saved leads require
  New lead before switching to another job.
- Optional fields: contact person, location, posting date, notes, status,
  follow-up date and retained job-description text. Contact is always manual and optional;
  status starts as New and follow-up dates are never inferred from the ad.
  Follow-ups due are shown in the module;
  this is not a scheduled notification or outreach service.
- **Create folder** creates a saved folder even before it contains an ad.
  Choose a named folder in the Folder menu to enable **Delete folder**.
  Deleting it moves its ads to Unfiled without deleting them; trashed ads stay
  in Trash. The confirmation includes every ad in that folder, and concurrent
  changes reject the operation atomically. **Save to folder** still accepts an
  existing or new name when saving an individual ad.
- Tick **Select** on saved cards (or **Select ads on this page**), choose
  **Move to folder**, then **Move selected**. This files ads after reviewing
  them; it does not change their notes, content, status or creation date.
  Search/folder/status changes clear selections. Trash must be restored before
  it can be selected. Unsaved edits on a selected ad require discard confirmation.
- **Date created** shows the original local save timestamp on each card and in
  the edit form. It is separate from LinkedIn's posting date, remains stable
  through edits/Trash/restore, and is retained when restoring a current backup.
  Legacy backups without a creation timestamp use the time they are imported.
- For login-only ads, the optional Chrome fallback can fill a draft. Install/reload the latest bundled companion,
  arm it from the CV Studio toolbar icon, open a job ad and use **Refresh job
  tabs → Read job ad**. Review the fields before saving. Manual entry works
  without the companion. Public reads need no extension; neither path uses AI
  or incurs provider charges.
- **Date posted** fills only when the same job supplies valid exact date
  metadata. Source calendar dates are preserved across time zones; relative
  ages are not converted into guessed dates. It can also be entered manually.
  Older leads and ads without exact metadata show **Posted: Not available**.
- Expand **View more — job ad content** on a saved lead to read its captured
  description without reopening LinkedIn or making a network call. The draft
  has the same expandable section with editable text. Captured excerpts are
  labelled, and missing descriptions explain how to add one. Headings, paragraphs,
  bold/italic text and lists are retained as a bounded semantic tree, with no
  source attributes, styles, media, scripts or executable HTML. Plain text is
  retained for editing/CSV and remains bounded to 20,000 characters.
  **Edit or paste job content** accepts formatted clipboard content into an empty
  or fully selected field; ordinary text edits replace its rich formatting.
  For older plain-text captures, use **Refresh ad content**, review and save.
  Failed or empty refreshes preserve the existing draft. The LinkedIn link stays available.
- Search saved leads, filter by status or due date, and edit/view details.
  Re-saving the same LinkedIn job preserves the existing record and notes.
  **Delete**, **Clear shown ads** and **Clear all ads** move records into
  recoverable Trash. Clear shown ads affects the current folder/search/status
  selection across all its pages; Clear all ads affects every active folder.
  Bulk actions confirm the count. Select Trash and **Restore** to return a lead
  to its original folder. There is no permanent purge; Trash still counts toward
  storage limits and is retained in JSON backups. Stale selections fail atomically.
- **More options** keeps CSV export, backup/import and bulk clearing collapsed
  until needed. **Back up saved ads** exports all records as Job Leads JSON.
  **Import backup** validates the entire file before
  adding missing job IDs in one transaction; existing records are never replaced.
  Current version-2 backups include empty folders; version-1 backups remain
  readable. This dedicated backup is separate from Settings' legacy local-data backup.
  Posting dates are included in CSV, and JSON backup/restore also retains the
  description excerpt marker, rich content, folders and Trash state. CSV also
  includes folder and creation date. Existing records retain all their data.
- Job Leads inputs use visible labels without placeholder text, including search.

## Boundaries

`cvstudio_job_leads.py` owns a dedicated `job_leads.sqlite3` in the existing
per-user state directory. It opens lazily, checks integrity/application/schema
identity, creates and verifies a consistent backup before initial schema creation,
and serializes writes using SQLite transactions. This store has its own schema 2;
the existing application database remains schema 10 and the job journal schema 1.
An integrity-verified database backup precedes initial creation or the additive
v1-to-v2 folder-table migration. Migration imports existing folder names without
rewriting lead rows, is transactional and can retry after failure. Earlier source
versions reject the newer database rather than silently dropping folder metadata.
Initialization is restart-safe, failed writes roll back and errors are visible.
Revisions prevent an older browser draft overwriting a newer saved edit.
Unknown fields are discarded rather than persisted; links retain only canonical
LinkedIn job IDs. No credentials, AI/provider calls,
LinkedIn messages, applications, JobAdder writes or background worker are added.

`cvstudio_job_ads.py` reads public job HTML only, through the existing guarded
`/job-leads` lookup action. The server constructs a canonical LinkedIn URL;
each redirect must remain on an approved LinkedIn job host and the same job ID.
No request cookies, auth headers, .netrc credentials or tracking queries are
forwarded. The reader limits size to 4 MiB, caps redirects/concurrent reads and
uses network/deadline bounds. It performs no automatic retry or login bypass.
JSON-LD JobPosting identities or a canonical public top card supply the fields;
search headers, recommended jobs and ambiguous identity mismatches are rejected.
No public content is stored until the owner clicks Save lead. Request failures
leave manual entries intact and offer the explicit Chrome/manual fallback.
LinkedIn HTTP 429 is reported separately as temporary public-read limiting;
there is no automatic retry or login/rate-limit bypass. The Chrome fallback
requires this CV Studio address and the connected companion in Chrome; it
cannot operate from the in-app browser. Saved job content remains available
locally through Edit / view details and View more.

The store is bounded to 5,000 leads and 8 MiB of field payload. Individual text
fields and a 12 MiB route/import limit are enforced. Backup/import limits cover
the bounded store. Contacts/notes are local user content, excluded from logs,
tests and diagnostic evidence except synthetic fixtures.

`app.py` owns only the guarded GET/POST `/job-leads` adapter and constructs the
store. All five existing guards remain. This non-AI route is deliberately not a
paid route. The new seal is 120 routes:
`ee8d33baeb48b961a2f50723faacbeb7fed86b55454b3518ab4a07bcd1e90033`.
Excluding `job_leads` exactly reproduces the v446 119-route contract; excluding
both new modules still reproduces the merged v445 118-route contract.

The companion supports `jobTabs`, `jobRead` and `jobFromLink` after its bound app
document check. Link fill reuses a matching job tab or opens only the explicitly
pasted canonical LinkedIn job URL in one temporary inactive tab. It never
navigates or closes a pre-existing tab. Cleanup closes only an unchanged inactive
tab created for that read; navigated/activated tabs are retained. One capture runs
at a time and a sourcing run cannot start midway through it.
Job capture requires a matching canonical job ID,
completed loading and a recognized visible detail panel. Search-panel title
links must confirm the selected job ID to reject stale SPA content. It stops
on unknown layouts, access challenges, navigation or an active sourcing run.
Capture performs no LinkedIn click, application, message or remote save;
it only fills an unsaved CV Studio draft. Its four-file packaging,
permissions and provider/key isolation remain unchanged.

## LinkedIn job discovery and content (v24.6.455)

Job Leads has a collapsed **Find job ads on LinkedIn** panel. The connected
Chrome companion opens a keyword/location Jobs search, or reads an explicitly
chosen already-open Jobs search while retaining its filters. It reads visible
cards, scrolls the recognized results list and uses recognized job pagination.
Limits are 1–15 pages, eight scrolls per page, ten minutes and 600 unique ads.
No AI provider or public per-link lookup is used for discovery. Search summaries
are explicitly labelled; Read full ad optionally captures the selected ad.
Selecting results and Add selected to list uses the established save route.
Existing duplicates, including Trash, are never overwritten. A partial storage
failure leaves the remaining selections available; existing manual drafts are
not replaced. Stop prevents further reads/paging and retains collected results.
New search tabs remain open for the user; existing tabs are not repurposed.

Job searches have their own companion run kind and source/filter identity,
with the existing binding, document revalidation, session-memory persistence
and fail-closed storage behavior. Page/scroll budgets survive worker suspension
and repeated Begin. Search filters/host changes, challenges and access limits
stop the run; no bypass, application, message, cookie access, provider call or
remote save is added. No new routes, schemas or extension permissions.

Single-ad capture now polls the same loaded DOM for up to 16 reads separated
by 350 ms when recognized detail fields are still loading. URL/pending URL and
binding are rechecked each time; this is not a network or navigation retry.
Missing description gets a shorter readiness allowance before metadata returns.

Rich formatting unwraps nested layout divs into proper sibling paragraphs,
headings and lists, retaining only the bounded passive semantic tree. Existing
nested paragraph captures flatten at display time, and explicit plain-text
bullet markers render as lists. Saved description text is not rewritten.
The manually selected Save to folder default is retained in origin-local browser
UI storage. New leads/captures use that choice; editing an existing ad uses its
own folder. Explicit Unfiled is remembered, deletion clears the matching default,
and reload discards a preference for a folder that no longer exists.

`test_linkedin_job_search.js`, `test_job_search_reader.js` and
`test_job_search_frontend.js` cover authority/budgets, scoped extraction and
the actual controller with synthetic companion messages. The existing Job Leads
and link-capture suites cover sticky folders, legacy/plain formatting, delayed
DOM readiness and fixed timeout behavior. Refresh/reload the downloaded v455
companion and reconnect the CV Studio Chrome tab to use the new actions.

The v456 `jobStatus` probe is behind the same exact app tab/document check and
returns only connected/capability/busy flags. It never arms the companion or
opens, reads, navigates or closes a LinkedIn tab. Automatic link fallback is
limited to `JOB_AD_UNAVAILABLE`/`JOB_AD_RATE_LIMITED`; storage, security, busy
and unrelated failures do not trigger it. The existing canonical URL checks,
single-capture lock, source-switch confirmation, optional manual contact/status,
rich formatting and empty-refresh protection apply to fallback results too.
`test_job_read_fallback_frontend.js` covers these flows and preservation on a
missing, busy, timed-out, failing or mismatched companion. Existing installations
need the v456 companion's updated files, Reload and app-tab reconnection.

## Current LinkedIn search layout (v24.6.457)

The current signed-in page inspected in Brave uses `/jobs/search-results/`
and a rendered `[componentkey="SearchResultsMainContent"]` result region.
Its job cards are buttons with `job-card-component-ref-<numeric job ID>`
component keys and ordered title/company/location paragraphs, with no job-view
anchors. The reader accepts this DOM layout alongside the existing linked-card
layout. It never reads hidden React state, tracking payloads, cookies or network
responses. Wrong/mixed card identities, missing title/company, duplicate cards
and oversized snapshots remain rejected/bounded. Modern Next is confined to
the results region and a parent containing numbered Page buttons.

`/jobs/search/` and `/jobs/search-results/` share one source identity; selected
job/paging/tracking fields (including `eBP`) are excluded, while actual search
filters remain pinned. Selected modern search links also canonicalize to the
same job-view ID in the backend, controller and worker. Modern ad capture uses
the same-job title link and exact `JobDetails_AboutTheJob_<ID>` region, requires
one company and substantive description, and rejects stale/ambiguous panels.
It retains passive source formatting and labels collapsed/truncated content.
Relative posting ages remain unconverted.

Search now probes `jobStatus` with a one-second bound before opening a source,
clearing old results or sending End. Disconnected, busy or older companions
leave the previous results intact and receive distinct guidance. Stop during
this readiness check sends no unrelated End. The `job_search` capability flag
identifies a current companion; update/reload/reconnect its v457 files.
The in-app Codex preview has no Chrome companion and cannot execute search.

Live read-only DOM inspection found 25 readable unique cards, zero normal
job-view links, and recognized paging/scrolling on the owner-opened page. This
verifies the observed selectors, not a complete installed-extension run.
Synthetic modern fixtures cover card identities/field order, scoped paging,
loading/stale description panels and bounds. Existing legacy fixtures remain.

## Preview and direct LinkedIn capture (v24.6.459)

Results have a Preview action and an in-app panel. Read full ad fills this
panel using the existing companion read, and Add this ad saves only that ad.
Other checkbox selections remain available for Add selected to list. Plain
summaries, captured content and excerpts stay explicitly labelled; no LinkedIn
iframe or remote HTML execution is used.

The updated companion's existing four-file package also runs its reader/content
scripts on `https://www.linkedin.com/jobs/*`. Existing host permissions are
unchanged. Recognized rendered cards and loaded job-view pages receive an Add
to CV Studio button. It acts only on a trusted user click, reads that visible
job identity again and never presses LinkedIn Save, Apply or messaging controls.
Injected control text is excluded from ad content. DOM updates do not duplicate
controls. It uses Save selected and LinkedIn ads to folder in the connected
Job Leads tab. Keep that tab open; refresh both pages after extension updates.

Direct captures require a top-frame LinkedIn sender, the same source document,
canonical observed job identity and an idle companion. They are forwarded to
the exact previously connected app document, correlated through its initialized
Job Leads channel and saved using the existing same-origin guarded API.
Busy/replaced/disconnected pages reject visibly; no ambiguous write is replayed.
Duplicate saves retain existing data, including Trash, and manual draft fields
are untouched. No new route, schema, provider call or remote LinkedIn write.

Live diagnosis of the v458 owner page found that LinkedIn removed `location`
from the opened search URL while its rendered location button still said
Malaysia. Exact URL comparison stopped discovery before results arrived. A
new-search-only initial handshake now checks unchanged keyword/filter identity,
reads the recognized location control and pins the resolved search identity.
Missing location UI waits within existing limits; a different location or
changed keywords rejects with readable guidance. Open-search mode and all
later reads retain strict filter identity, counters, deadlines and guards.

The v460 review corrective identifies the modern location control through its
visible Location accessibility label (on the control or its child). Other
expandable header filters and the promoted-jobs/AI-search help controls are
excluded. Read-only live inspection confirmed the nested label and both help
controls. Multiple conflicting recognized locations still reject; unrecognized
location UI remains loading within the existing budget.

## Verification (existing contracts)

### LinkedIn controls (v24.6.461)

The owner confirmed that updating/reloading the wrong companion version resolved
the missing-results report. Readiness now reports the manifest version and an
explicit current-search revision; older companions stop before results are cleared
or a source tab opens. Known reader-start/read failures return fixed guidance,
without exposing raw browser errors or document information.

LinkedIn cards place controls in an existing vertical text column. They never
add a competing flex-row column or change native card styles; unrecognized
horizontal/grid containers receive no inline controls. Summary extraction excludes
the injected controls even when a native footer follows them.

Added is a reversible toggle: removal calls the established revision-guarded
Trash operation, and explicit Add restores the same stored lead. Contact, notes,
status and follow-up details remain. A selected destination can move the restored
lead afterward through the existing guarded operation. If restore succeeds but a
subsequent move fails, the result stays Added in its actual folder with a visible
warning; no write is replayed. A lead currently open for editing in CV Studio
cannot be removed/moved through the companion, preserving that draft.

The LinkedIn folder selector loads from the exact connected Job Leads tab.
New folder creates a folder without saving an ad and selects it for subsequent
adds. Chosen folders carry across the page's controls. Ad writes and folder creation still require
an explicit trusted interaction, a visible canonical ad, exact source/destination
documents and an idle companion. Folder names are rendered as text. No new route,
schema, permission, LinkedIn write or provider call exists.

In v471 the folder catalog is separate read-only metadata. The page preloads it
once and shares it across current/new cards; concurrent refreshes are coalesced.
Opening a menu, returning to the LinkedIn tab or **Refresh folders** reads the
current catalog. Successful creation updates all menus. A valid chosen folder is
retained; a deleted folder falls back to Unfiled without recreating it. Initial
loading/failure is explicit; failed refreshes retain a usable cached list. Reads
time out after 12 seconds and late responses cannot overwrite a newer catalog.

Catalog reads no longer parse company/role or require the ad layout to finish
loading. They still verify the top Jobs frame, canonical URL and exact live source
and destination documents. These local reads may run during sourcing/discovery;
they never acquire/release a write lock, render the Job Leads panel, clear selected
ads or modify drafts/records. The content bridge permits bounded parallel reads
while serializing writes. Save/remove/create still use the full existing ad
validation, trusted click, busy/revision and non-replay gates. Updated app capability
is required; old app pages receive refresh/update guidance before metadata is sent.

The v472 review corrective checks the clicked ad's own saved state on every Add,
using the bounded read-only metadata request rather than the shared catalog's
unrelated first-card status. An already-active saved ad is labelled Added and
retains its folder without sending an Add/move/remove write. A genuinely new ad
still receives the chosen folder. Failed/unknown checks issue no write. Explicit
Added/removal and later Trash restoration retain their existing behavior; no
route, schema, worker contract or legacy duplicate/move behavior is changed.

The v473 timing correction also makes the actual companion Add handler idempotent
for every active duplicate, even if another window saves it after the preflight.
The selected destination is used for new ads, and for explicitly restoring a
trashed ad, but never moves an already-active duplicate. Use the established
Move to folder controls to refile saved ads. If a record appears during the final
store save, the existing immediate transaction returns the unchanged duplicate;
the frontend does not follow it with a move. Explicit moves and revision-guarded
Trash restoration keep their existing paths. No route or schema changes.

Both the v461 app and companion are needed for folders/removal. An older local
page rejects management commands visibly rather than treating them as legacy
adds. Existing ordinary direct-add messages remain compatible. Replace/reload
the companion files, refresh both pages and reconnect the intended app tab.

The v458 review corrective makes the numeric empty-result check match only a
standalone zero count. A header such as `10 jobs`, `100 jobs` or `1,000 jobs`
can appear before its cards; that remains a loading snapshot rather than ending
discovery with no ads. Both legacy and modern DOM fixtures cover positive
counts before cards, real zero/no-result messages and delayed card readiness.

`tests/test_job_leads.py` covers canonical identities, rejection of unsafe URLs,
durability, duplicate and stale-write protection, cross-process-style concurrent
connections, backup verification, corruption, atomic restore/rollback, route
guards, request IDs and the previous route digest. `test_job_leads_frontend.js`
covers bound job-only capture, source invalidation, sourcing isolation, draft
protection, DOM text safety and spreadsheet-safe CSV output. Native Chrome uses
synthetic intercepted LinkedIn pages and a simulated companion; actual extension
installation and current live LinkedIn layouts still need owner-driven checking.
`test_job_link_autofill_frontend.js` adds link/canonical URL constraints,
existing-tab reuse, owned-tab cleanup, timeout and concurrent-run/reload checks.
`test_job_ads.py` adds no-network public HTML extraction, same-job redirects,
identity/size/type/auth restrictions, timeouts, ambiguity and concurrency checks.
The owner-reported public ad was verified end-to-end in the real in-app browser
after v449; that does not establish all LinkedIn layouts or login-only access.

In v462 the preview reads both saved records and temporary search results.
Reloading without an active search shows the first active saved ad; Preview on
a saved card opens the search/preview panel, and direct LinkedIn additions select
the affected saved ad immediately. Search still selects its first result and
keeps its own counts and selection. Removed ads display In Trash without offering
a duplicate save. Empty previews hide unavailable actions and explain the sources.
Reading a full saved ad is temporary: it never updates the record or editing
draft. Refresh reverts to authoritative saved content. Persisting updated content
still requires Edit / view details, Refresh ad content, then Save changes.

The v462 companion folder controls have consistent sizing, borders and spacing.
Their inline-size isolation, recognized native column mount and explicit wrapping
remain essential. Added keeps its reversible action in its accessible label and
hover title. The four-file package and extension permissions are unchanged.

The current source preview on port 5077 uses a verified SQLite snapshot of the
earlier isolated preview state. The installed owner app on port 5000 is separate.
Preview paths and QA screenshots remain in ignored runtime configuration. All
interactive QA uses isolated fictional ads; no owner records were changed.

## Preview navigation and reversible removal (v24.6.468)

The preview identifies its source and position: Saved ads or Search results.
**Previous ad / Next ad** browse individual ads; saved navigation follows the
current folder/search/status filters. Search navigation follows the selected ad
across its 20-result pages. **Previous results page / Next results page** select
the first result on the requested page and appear only when multiple pages exist.
Without search results, the preview fills the available width.

**Close preview** dismisses its content without changing saved records, selected
results or an editing draft. Refreshing records or changing checkboxes does not
reopen it. An explicit Preview action or a new search opens it again. Clearing
search results also dismisses the preview instead of silently selecting a saved
ad. These are temporary page controls; a fresh page still starts with its first
matching saved ad as before.

Saved previews offer **Move to Trash**, or **Restore ad** when already trashed.
Both use the existing revision-guarded operations and draft-discard check. Saved
browsing advances to the next matching record after success, or clears the
preview when none remain. Failed or cancelled writes keep the current ad.
Search previews retain their result and show its current Trash/restore state.
No permanent deletion, implicit save, provider call, companion change or schema
change is introduced. Companion direct-add/removal keeps its existing behavior.

The v468 browser QA preview is isolated and contains fictional ads, with a
simulated companion for search. It does not change the installed app or owner
records. See the v468 QA report for the regression and live-browser checks.

The v469 corrective uses the same saved-filter synchronization after folder
creation as after a manual filter change. Selecting a newly created empty
folder clears the previous saved preview and its management actions. An
existing populated folder selects its first matching ad with the correct
count. Closed previews, search-result context/selections and unsaved drafts
remain intact. Folder selection does not move, remove or update saved ads.
