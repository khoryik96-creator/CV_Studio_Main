# CV Studio v24.6.552 — company and full-ad read recovery

Branch `codex/company-jobs-button-resolution`, based on merged v24.6.551 / PR295.

## Company/group recovery

Lear's public company Jobs page links its own “See all jobs” action to
`/jobs/lear-corporation-jobs-worldwide?f_C=63345,44466,34111,3701` (plus tracking).
The resulting public search labels Lear and three affiliated employers. Earlier
code accepted only `/jobs/search/` links with one numeric ID. This is concrete
public evidence explaining why the prior numeric-header fix could still fail.
The signed-in DOM has not been reproduced.

The reader now preserves all IDs in the company-authored Jobs CTA, including
observed SEO-style links. It accepts up to 20 distinct numeric IDs, compares
multiple CTAs as complete sets, and rejects conflicting header evidence. A
People/associated-member group alone never authorizes a Jobs group. IDs are not
hardcoded or inferred from names. The client caches the complete group against
its exact saved page for the session. Pull and Open LinkedIn retain all members;
`jobSearchBegin` accepts a bounded `company_ids` array while preserving the old
single `company_id` contract. Search identity ignores group ordering but rejects
any dropped/replaced member. No backend storage/schema change is needed.

If no numeric filter is exposed, one native Jobs action may run in the owned
inactive company tab. Hidden, disabled, ambiguous, foreign-employer and unsafe
controls are rejected and rechecked before activation. The resulting search must
contain a valid complete numeric company filter. Actions are never replayed.
Capabilities `company_jobs_action_revision:1` and `company_jobs_group_revision:1`
prompt older companions to update before resolving unknown pages.

PR296 review found Chrome's onUpdated handler could discard ownership during
this authorized native navigation. The transition now retains exact destination
ownership and filter identity, including persistence/reaping across restart.
Actual onUpdated/onActivated regressions verify inactive cleanup and permanent
protection for user-viewed or differently navigated tabs. Cancellation mid-hop
also cleans up the owned destination. No existing user tab is driven or closed.

## Full-ad recovery

Manual and background full-ad reads use the existing public lookup once after a
recognized companion layout/empty-content/timeout failure. Successful content
must match the exact job URL and include company, role and a readable description.
Rich formatting and cached previews remain available; saved ads and drafts are
not overwritten. Access, cancellation, changed-ad and connection failures never
trigger this fallback. Public busy/rate-limit errors pause the queue without
replaying requests. Stop aborts the pending browser request and rejects late
results; the bounded server reader may still finish its own read.

## Validation and limits

- All 95 frontend fixtures pass, including grouped/SEO company evidence, all-ID
  pull/cache/open propagation, reordered/changed filters, restart/event ownership,
  client capability checks and the full-content fallback fixture.
- 192 relevant public-ad, Job Leads/folder/organization/HR, version and composition
  tests pass under isolated paths. One existing pytest deprecation warning.
- Chromium tests native and aria-labeled company Jobs buttons, rejected hidden /
  ambiguous / other-employer actions, and actual same-tab filter navigation on
  intercepted fictional pages. Reproduce with `tests/browser/company_jobs_button.py`.
- Chromium also verifies companion timeout → one exact-URL public lookup → rich
  cached preview, followed by Stop with preserved content, against the isolated
  existing fixture. No external browser requests or page errors occurred.
- JavaScript syntax, repository consistency and whitespace checks pass.

Reported URLs are `https://www.linkedin.com/company/lear-corporation/`,
`https://www.linkedin.com/jobs/view/4437968792/` and
`https://www.linkedin.com/jobs/view/4373530413/`. The user confirmed the second
description is visible in their browser. Public web views expose descriptions
for the two job URLs; one redirected to LinkedIn's Malaysian public site. This
does not reproduce the user's authenticated DOM. Direct requests through the
existing public reader in this cloud environment returned `JOB_AD_UNAVAILABLE`.
The grouped public Lear link is verified, but live signed-in success for Lear
or either ad on the owner's installation is not claimed. The implemented recovery paths are verified with controlled responses.

No routes, schemas, credentials or provider/paid-call boundaries change. No live
email, JobAdder write or paid provider action was made. Both app and companion
need updating to use grouped-company recovery.

[PR296](https://github.com/khoryik96-creator/CV_Studio_Main/pull/296) records current
CI, review and merge status.
