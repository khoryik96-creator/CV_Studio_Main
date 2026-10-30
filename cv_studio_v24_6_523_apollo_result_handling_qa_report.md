# v24.6.523 Apollo result handling - local QA

Base: merged v24.6.522 deccf7f / PR267. Branch:
codex/v24.6.523-apollo-email-results. No publication/merge requested for v523.
PR257 remains held/excluded. PR267 merge and final green checks were separately
confirmed before beginning this correction.

The owner reports no business email despite seeing one on Apollo's website.
Read-only comparison of the supplied profile confirms its exact LinkedIn handle,
employer and a business email labelled verified in the already-saved Apollo
contact, while the matching protected local outcome is not_found. No unlock was
clicked; no new paid request, contact write, cache clearing or deployment was
performed. Only aggregate protected-cache states were inspected. No real profile,
email, opaque identity, token, account details or private content is copied into
this report, code, fixtures or diagnostic logs.

The historical upstream response is unavailable. These observations establish a
website/cache discrepancy, not the precise reason Apollo's earlier API response
omitted an address. In particular, a team-saved website contact need not imply
that every enrichment response contains the same fields.

A new parser regression fails on merged522: a correctly bound embedded saved
contact business email is discarded when person.email is empty. The correction
keeps the primary business email authoritative, then accepts contact.email only
with a positive same-person ID/profile binding and same-employer evidence,
rejecting conflicting person/organization fields. Parent and person-level
low/none match confidence remain rejected. Personal email domains and Apollo's
locked placeholder cannot become business email output. Malformed successful
responses are unconfirmed instead of claiming that no email exists.

Bounded optional reason codes distinguish no profile match, omitted email,
personal-only data, locked/invalid email and an unconfirmed nested contact.
Only allowlisted reasons and a saved_contact provenance label cross the local
client boundary; arbitrary upstream text is ignored. The desktop also rejects
a locked placeholder even if an older hosted broker labels it found. Existing
terminal cache entries are retained. A local or hosted code update cannot
reconstruct their missing upstream fields, recover an omitted email, or silently
start another credit-consuming operation.

Preserved: existing provider endpoints/parameters and OAuth scopes; one explicit
paid request per operation; durable pre-transport marker; lookup-status recovery
without paid replay; encrypted accounts and selected results; no raw contact
response persistence; existing routes, request guards and SQL schemas. No phone,
personal-email, waterfall or extra contact-read scope is added.

Primary provider references inspected read-only:
- https://docs.apollo.io/reference/people-enrichment (person/contact response and
  match confidence; enrichment may charge for demographic/email output).
- https://docs.apollo.io/reference/get-complete-person-info (locked placeholder).
- https://docs.apollo.io/reference/view-a-contact (saved team contact is a
  distinct read endpoint; its contact_read scope is NOT added by this change).

Verification:
- 54 focused Apollo Python tests pass, including bounded/unknown diagnostics,
  protected-cache persistence/non-replay and desktop placeholder rejection.
- 81 standard JavaScript fixture files pass. New parser tests cover positively
  bound contacts, wrong/missing employer/person bindings, primary precedence,
  freemail/redaction/invalid values, malformed responses and nested confidence.
- Real Worker + SQLite/WebCrypto fixture additionally verifies one request only,
  encrypted selected-contact result, same-operation read recovery and exclusion
  of raw contact/person metadata. Rerun after final employer-binding tightening.
- Tracked-language syntax, explicit broker MJS syntax, version/repository
  consistency, owner-source/protected-asset preflight, genuine Windows native
  Antiword/Tesseract and24 source-smoke assertions pass. No protected colleague
  build or genuine macOS testing is claimed.
- Full isolated Windows Python:2210 passed,4 skipped,8418 subtests.

Ignored evidence: runtime/final523_python.log, runtime/final523_js.log and
runtime/final523_static.log. Full-sweep JS passed before the last focused
employer-binding assertions; the changed parser and real Worker fixture were
rerun successfully afterward. No additional unchanged fixture sweep is needed.

Acceptance still needed: deploy the reviewed hosted Worker and explicitly
approve one new lookup for the supplied example, which may use an Apollo credit.
Do not discard/replay an uncertain operation or clear the account cache to force
that test. If the provider still omits the email, use the bounded reason to
identify the next step rather than claiming that the website has no address.
