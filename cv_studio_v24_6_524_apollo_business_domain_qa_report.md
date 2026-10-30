# v24.6.524 Apollo business-domain correction and hosted acceptance

Date: 2026-10-30. Base: local523 `696da66`, on merged522 `deccf7f` / PR267.
Branch: `codex/v24.6.524-apollo-business-domain`. The owner now explicitly
authorizes publication and merge of the523/524 source stack; issue35 records
the resulting PR and merge identity. HeldPR257 is excluded.

## Defect and correction

After the owner's first explicit credit authorization, the deployed523 broker
completed one new lookup with the bounded reason personal_email_only. This
exposed a second, exact defect: the existing provider-brand wildcard excluded
all Proton-branded domain suffixes, including the corporate domain proton.com.
A new fictional parser regression fails on523 before this correction.

The broker now excludes Proton Mail's exact public domains: proton.me,
protonmail.com, protonmail.ch and pm.me. It accepts a positively matched business
email at proton.com (including uppercase spelling), in the primary or strictly
bound saved-contact field. All other existing provider-domain rules, exact
person/company checks, protected persistence, OAuth scopes, provider endpoints
and explicit one-operation credit/non-replay boundaries remain unchanged.
Primary domain reference: https://proton.me/support/addresses-and-aliases .
This correction does not claim exhaustive freemail classification.

## Deployment and live acceptance

The owner explicitly approved deploying the tested523 code and one new lookup,
then separately approved the official Wrangler tool when the Cloudflare editor
failed to load. The first lookup was journaled before transport and completed
not_found/personal_email_only. After the domain fix was deployed, the owner
separately approved one additional new lookup. It completed found with a
business email and provider email_status verified. There were exactly two new
acceptance operations, each explicitly approved. No third lookup, automated
paid retry or uncertain-operation reset was performed. Status/integrity checks
after completion read local protected journals only.

Each attempt used the existing account credential through an isolated DPAPI-
protected task vault and durable non-replay marker. The original selected owner
cache outcome was independently compared equal afterward; account fingerprint
also remained equal. The first task result was independently confirmed retained.
No owner ad/cache/contact-archive write occurred. The found result is stored in
the second protected task journal, not displayed in the owner's original cached
card. Updating the service cannot reconstruct or replace old terminal outcomes.
No real name, email, LinkedIn profile, account ID, token, provider body or other
live private record is copied into source, fixtures, QA or coordination comments.

Production Worker versions:
- prior active version: 4cbb986a (unchanged version retained for rollback);
-523 deployment: a42ee132-a391-461f-92c1-dece9bf1ea65;
-524 deployment: 29e8155b-bcd7-41f8-ba98-fee4f78b6038.

The dashboard confirms524 active at100% and Ready. The public callback probe
returns200. Existing D1 binding, secret values, PUBLIC_ORIGIN, compatibility date
2026-10-28, disabled preview URLs/logs/traces, default placement and no scheduled
triggers were retained. No schema execution, secret rotation, new resource,
paid hosting plan or new scheduled work. The initial setup's daily cleanup
recommendation remains unconfigured; this repair does not silently add it.

Official Wrangler4.156.0 used user-approved Workers script deployment access.
OAuth authentication was stored encrypted via Windows Credential Manager,
then logged out; whoami verified unauthenticated afterward. Browser diagnostic
and authorization tabs were closed. No live secret value was inspected.

## Tests and limits

- New parser tests fail on523 and pass on524: corporate domain primary/nested,
  uppercase and continued rejection of all four real Proton Mail domains.
- Real Worker SQLite/WebCrypto fixture verifies fictional corporate-domain
  selection, encrypted result persistence, lookup-status recovery and one paid
  upstream request despite repeated same-operation reveal/status requests.
-59 focused isolated Python tests pass (Apollo service, routes, contacts and
  single-source version). Final all81 JavaScript fixture files pass.
- Tracked-language and MJS syntax, version/repository consistency,
  owner-source/protected-asset preflight and genuine Windows Antiword/Tesseract
  functional checks pass;24 source-smoke assertions pass. git diff --check clean.
- Full isolated Python2210 passed/4 skipped/8418 subtests on523. This524 change
  affects only the broker's JS domain policy plus version/docs; focused Python
  and all JS/static gates were run on the final correction.
- No genuine macOS test, protected colleague build, second-account live test,
  live lost-response simulation, mailbox delivery or universal result claim.
  Existing fictional tests cover account isolation and ambiguous non-replay.

Ignored evidence: runtime/final524_js.log, runtime/final524_static.log and
runtime/apollo524_deployed.jpg. The two acceptance journals are DPAPI encrypted;
never delete/reset them to force another paid call. Successful live acceptance
applies to this one person/company under this account. Other missing/withheld
provider emails remain possible; old completed negative cache results remain.
