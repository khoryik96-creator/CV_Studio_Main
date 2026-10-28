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
The Worker test executes the real SQL against Node's in-memory SQLite and uses
real WebCrypto. This is not a Cloudflare-hosted or live Apollo authorization test.

After deployment, verify owner-approved sign-in, permission denial, cancellation,
disconnect/reconnect, and two distinct Apollo accounts. Check that no raw token
appears in browser responses/logs or plaintext D1 fields. A live credit-consuming
unlock needs separate explicit owner authorization; do not silently spend credits
as a connection test. Confirm returned profile/company and provider status, then
simulate a lost response and confirm **Check lookup** does not issue another
People Match request. This live acceptance remains pending until setup.
