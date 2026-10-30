# Apollo sign-in service — owner setup

One service serves every colleague. Each signs into their own Apollo account;
their access, credits and email results stay separate. They do not create API
keys or hosting accounts. CV Studio remains a local application.

## Activation prerequisites

Use **Cloudflare Workers Free** and a free D1 database, with the supplied
`workers.dev` address. Do not upgrade the account or attach paid resources.
Free quotas stop requests when exhausted; this implementation does not enable
automatic upgrades. Apollo's own account eligibility, permissions and credits
still apply. Current [Workers pricing](https://developers.cloudflare.com/workers/platform/pricing/)
and [D1 pricing](https://developers.cloudflare.com/d1/platform/pricing/) describe
those limits. A custom domain is not required.

The owner must register CV Studio as an Apollo OAuth application and obtain
approval. See [Apollo's partner OAuth setup](https://docs.apollo.io/docs/use-oauth-20-authorization-flow-to-access-apollo-user-information-partners).
Use only `people_match` and `read_user_profile` (plus Apollo's default
`app_scopes`). Set the redirect to the exact deployed Worker origin followed
by `/callback`. The existing `cv_studio_logo.png` can be used as the app logo.
Do not use another application's client ID, including Apollo CLI's identity.

## Deploy once, then distribute the public address

1. Sign into a free Cloudflare account. Create a Worker named `cvstudio-apollo`
   and note its HTTPS `workers.dev` origin.
2. Create a D1 database named `cvstudio-apollo`. Execute `schema.sql` on the
   **new, empty** database. Bind it to the Worker with the binding name `DB`.
   Never execute this schema on a CV Studio or unrelated existing database.
3. Deploy `worker.mjs`. Set `PUBLIC_ORIGIN` to its exact HTTPS origin, without
   a trailing slash. Disable Worker observability/request logs as in
   `wrangler.jsonc`. Do not add request-body, authorization or callback logging.
4. Register the Apollo app with that `/callback` address and the scopes above.
   The public GET/HEAD callback probe works before app credentials exist, so
   Apollo can verify the HTTPS URL. It returns no account or authorization data.
   When approved, set Worker **secret** variables `APOLLO_CLIENT_ID` and
   `APOLLO_CLIENT_SECRET`. Do not put them in a file, Git, chat or a screenshot.
5. Generate a random 32-byte encryption key and save its 64-character hex form
   as the Worker secret `TOKEN_KEY`. Keep an offline protected copy. Losing or
   rotating it requires reconnecting users; existing encrypted records cannot
   be recovered with a different key. Do not print it into QA logs.
6. Enable the daily cleanup trigger from `wrangler.jsonc`. It removes expired
   login attempts, old lookup outcomes and expired connections.
7. Put only the public HTTPS origin into repository-root
   `apollo_connection.json` as `broker_url`. This file ships to colleagues.
   An owner-only `CVSTUDIO_APOLLO_BROKER_URL` environment override is available
   for development. Client secrets and account tokens never belong here.
   CV Studio calls the Worker with the `CVStudio-Apollo/1.0` User-Agent.
   Cloudflare refuses Python's default `Python-urllib` agent with error 1010,
   which CV Studio reports as an Apollo permission (403) message.
8. Run the account/credit acceptance checks below before distributing a release.

`wrangler.jsonc` also supports a CLI deployment after the owner fills in the
public origin and the newly created D1 database ID. It contains no secrets and
has deliberately unusable placeholders. Local QA must not run a remote deploy.

## User flow

Open a saved ad with saved HR people. **Connect Apollo** opens Apollo's own
sign-in and consent page; the original CV Studio tab waits for completion.
Click **Unlock email** on one saved HR card and confirm credit use. Only a
business email is requested; no personal email, phone, waterfall enrichment or
outreach is requested. Apollo may charge for returned demographic data even
when no business email is found. The displayed status is Apollo's assessment,
separate from CV Studio Email Verifier's SMTP observations.

**Check lookup** retrieves an uncertain operation's existing outcome; it does
not repeat the paid request. A new account never sees the previous connection's
cache. **Disconnect** removes the local protected credential/cache and asks the
broker to delete that connection and its temporary outcomes. It does not claim
to revoke the Apollo-wide app grant; users can revoke that in Apollo's connected
integrations. If broker deletion cannot be confirmed, the UI says so explicitly.

### Unlocked contacts (v24.6.515)

Job Leads → **Unlocked contacts** is a separate device-local history of business
emails returned successfully by Apollo. It remains after sign-out/disconnect;
the confirmation says so. This intentional history is separate from the account
lookup cache, which is still cleared. It is not a shared team database.
The archive uses Windows DPAPI or the existing authenticated machine-bound file
vault on other platforms. It deliberately avoids macOS Keychain command-size
limits for a larger contact list. Credentials retain their existing storage.
No email/token mirror is added to browser storage or Job Leads SQLite/backups.

Successful unlocks and read-only recovery save name, position, company, observed
location, scan country, email, Apollo status and source URLs. Deduplication uses
person + employer ID + email; the first saved context is retained. Country is
labelled **Country (scan)**; it is not an independently verified person/company
country. Previous successful lookups import locally where their saved HR source
still exists. No provider lookup occurs for import, refresh, search or export.
If archival fails, the paid result stays on its HR card with explicit guidance;
refresh recovers from that cache without spending again. Disconnect preserves
its existing cache-clearing contract and remains available if ad/contact storage
is unavailable; its confirmation says to copy any unarchived email first. View
older successful lookups before disconnecting if they have not been archived.
The archive is bounded at
5,000 contacts/8 MB, never silently evicts, and reports storage/capacity failures.
An import failure does not block viewing/exporting the contacts already saved;
the dashboard and download show that some HR-card emails remain unarchived.

Excel export is a genuine `.xlsx` file of the matching contacts, with all source
values written as literal text (including leading formula characters). Exports
include profile/company/ad URLs and the archive-save time. Exported files are
ordinary user-managed files; the plain Job Leads ad backup does not include this
protected contact history.

### Applying the supplied activation fixes

The shipped public `apollo_connection.json` points to the owner's Worker; no
secret is distributed. The Python client sends `CVStudio-Apollo/1.0`. Provider
profile/company links compare their LinkedIn handles across HTTP/HTTPS and host
forms. Company names may ignore legal affixes, but their remaining full names
must agree; a partial brand overlap or conflicting numeric company ID fails.
Unicode company names retain their letters. Low/no-confidence matches remain
rejected. The protocol fix is code-supported; no live unlock is claimed here.

Pushing/merging Git does not deploy Cloudflare. Redeploy the final **worker.mjs**
in the existing Worker, then disconnect/reconnect once to clear terminal cached
mismatches. The next explicitly authorized unlock is the live credit-consuming
acceptance check. Do not silently replay previous operations or credits.

## Boundaries and retention

- Desktop: opaque connection secret, account label and up to 500 lookup outcomes
  use the existing protected vault. No token or email mirror in localStorage,
  browser IndexedDB, Job Leads SQLite, JSON backup or source tree. Account
  changes clear the cache; plain ad/HR records are never rewritten by unlocks.
- Broker: per-connection AES-256-GCM protects Apollo credentials and temporary
  outcomes in D1. Record identities are authenticated as associated data.
  Proof secrets are stored only as SHA-256 hashes; each connection is isolated.
- Login attempts expire after 10 minutes, lookup outcomes after 24 hours and
  connections after 30 days. Daily cleanup enforces removal; expired records
  cannot authorize a request while awaiting cleanup. There is no automatic
  reconnect or paid work after restart.
- OAuth exchanges, refresh-token rotations and paid lookups are claimed before
  transport and never replayed after ambiguous failure. Failed token rotation
  requires reconnect. Duplicate operation IDs return only the original result.
- Strict fixed Apollo endpoints, no redirects, bounded bodies/timeouts and
  fixed errors prevent redirect-based credential leakage and provider error
  content entering diagnostics. Browser CORS is disabled on authenticated APIs;
  only the public, static callback-verification probe permits cross-origin reads.
- Use a fresh connection after an interrupted worker has retained its busy
  marker. That marker is intentionally not reset by guessing whether paid work
  completed. Existing confirmed results remain readable.

## Acceptance and tests

Local tests use fictional accounts and intercept all provider traffic:
`tests/test_apollo.py`, `tests/test_apollo_routes.py`,
`tests/test_apollo_frontend.js`, `tests/test_apollo_broker.js`.
Contact archive, guarded download and UI tests are in `tests/test_apollo_contacts.py`
and `tests/test_apollo_contacts_frontend.js`.
The Worker test executes the real SQL against Node's in-memory SQLite and uses
real WebCrypto. This is not a Cloudflare-hosted or live Apollo authorization test.

After deployment, verify owner-approved sign-in, permission denial, cancellation,
disconnect/reconnect, and two distinct Apollo accounts. Check that no raw token
appears in browser responses/logs or plaintext D1 fields. A live credit-consuming
unlock needs separate explicit owner authorization; do not silently spend credits
as a connection test. Confirm returned profile/company and provider status, then
simulate a lost response and confirm **Check lookup** does not issue another
People Match request. This live acceptance remains pending until setup.


## Business email response handling (v24.6.523)

The broker first checks the exact matched person's primary business email. If
it is empty/withheld, an embedded saved contact can supply its business email
only when its person ID or LinkedIn profile positively binds to that same
person, positively bound employer evidence agrees, and no supplied metadata
contradicts either identity. An unrelated contact,
freemail address or locked placeholder cannot become a business email. Parent
and person-level low/none match confidence are rejected. No extra contact-read
OAuth scope, phone/personal/waterfall request or second enrichment call is added.

A bounded reason distinguishes no profile match, omitted email, personal-only,
redacted/invalid email and an unconfirmed nested contact. Unknown diagnostics are
ignored locally and raw responses never enter messages/logs. Already-completed
operations and local negative results are still kept to prevent credit replay.
Updating/reconnecting must not be advertised as recovering an old missing result.
The hosted Worker needs this code independently of the desktop update. Proving
an exact live response requires separately authorized provider credit use; a
parser fixture proves the code gap, not what a previous live response contained.

## Corporate-domain classification and hosted acceptance (v24.6.524)

Proton Mail public account domains are matched exactly: `proton.me`,
`protonmail.com`, `protonmail.ch` and `pm.me`. A corporate domain such as
`proton.com` is not excluded merely because its brand resembles the provider.
See [Proton's address documentation](https://proton.me/support/addresses-and-aliases).
Existing same-profile/employer validation and all other email rules remain.

The owner separately approved two new single-operation acceptance lookups:
first after deploying523, then one after fixing the domain collision exposed by
that first outcome. The second returned a business email with Apollo status
verified. This proves that example, not universal email availability, delivery
or every colleague's account. Both task outcomes remain encrypted separately;
the original owner cache/ad data were not overwritten and the acceptance result
was not imported into the owner's cards/contact archive. Updating hosted code
will not clear completed negative outcomes or spend another credit for them.

The524 Worker was deployed with the official Wrangler tool after explicit owner
permission. Existing database binding/secrets and production settings were
preserved, including the runtime date, disabled logs/traces/previews and the
absence of scheduled triggers. No database schema was executed. The original
setup's daily cleanup recommendation remains unconfigured on this deployment;
request-time expiry guards still apply. Wrangler authentication was held in the
Windows credential store and signed out after deployment. See the524 QA report
for exact deployed version and validation bounds. Git publication/merge is a
separate step and has not been performed for523/524.
