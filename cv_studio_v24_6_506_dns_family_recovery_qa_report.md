# CV Studio v24.6.506 — DNS family recovery

Branch `codex/v24.6.506-dns-family-recovery`, stacked on pending project-bullet
v505 `3f9e340` from merged v504 `8d0e8dc`. The owner authorized fixing all review
findings and merging. The supplied review targeted the historical v490 branch;
the one identified DNS defect was confirmed still present in current source.
No historical branch history or later verifier improvements were reverted.

## Finding and correction

`MailDNS.addresses` queried A followed by AAAA without per-query failure
handling. An A failure skipped usable AAAA records; an AAAA failure discarded
already-successful public A records. Both paths could make a usable MX appear
unconfirmed in quick, full and deep verification.

The resolver now catches normalized `CheckUnavailable` separately for each
family and retains every successful answer for the existing public-IP guard.
Any restricted or malformed answer still rejects the entire host. Only after
that validation does the existing deduplication/two-address/family selection
run. With no successful addresses, a remembered lookup failure is raised rather
than interpreted as a definite empty implicit MX. Both queries use the same
caller-supplied deadline; no retry, extra SMTP session, background work or
external service was added.

## Regression evidence

- New synthetic cases failed 22 checks on the old code before implementation.
- All 106 verifier cases pass, including quick/full/deep recovery for either
  failed family, identical DNS/SMTP deadlines, missing answers with a failed
  family, both families failing, implicit MX, repeated checks releasing slots,
  private/loopback/mapped-private/malformed answers and definite empty results.
- Existing balanced IPv4/IPv6 selection, same-family ordering/caps, public-IP
  pinning, real loopback SMTP protocol fixtures, overall deadlines, evidence,
  conflicting servers, signed recheck references and route/UI checks remain.
- The v505 project-layout correction and its tests/docs are retained in this
  merge stack; its separate QA report records source replay and Word visuals.
- Final full regression: **2,034 Python tests passed, four skipped, 8,417
  subtests passed**. All **69 JavaScript fixture files** passed. Three deliberate
  in-memory breaks of family recovery, unknown-versus-empty handling and public
  address validation were caught by the new regressions.
- Tracked Python/JavaScript/PowerShell/shell syntax, repository consistency,
  exact version surfaces, genuine Windows Antiword/Tesseract dependency
  preflight and all 24 source-smoke assertions passed.

Final full regression and hosted-check results are recorded with the merge
identity in coordination issue #35. No live SMTP/DNS/provider call, real mailbox
or lead mutation, owner installation/receipt write, new route/schema, protected
build or unrelated JobAdder integration is part of this correction.
