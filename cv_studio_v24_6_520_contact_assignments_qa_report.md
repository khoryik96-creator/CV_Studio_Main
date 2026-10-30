# v24.6.520 contact assignments — local QA

Base: merged51937e9461, PR266. Local branch codex/v24.6.520-contact-assignments.
Not published/merged. PR257 remains held. Owner installation/data untouched.

Public api.jobadder.com/v2/openapi.json confirms one nullable ownerUserId and
nullable recruiterUserId int32 array, and GET users default active roster.
Only fictional transports were used; no credentialed read/contact/paid action.

Choices load with existing company search. One owner and searchable recruiter
checkboxes/Select all/Clear. Optional protected connection-bound defaults save
only on successful creation or safe confirmation, including original pending
assignments on uncertain recovery. No SQL/browser mirror or migration. Roster
is complete, active and <=1000, with safe provider-default fallback on failure.
Review binds selections; changed or unavailable users block create. Existing
source-email, duplicate, account and unsafe-write non-replay checks remain.

Validation: Windows2169 passed,4 skipped,8418 subtests; all79 standard JS files.
Actual isolated Flask/native Chromium fictional contact creation confirmed exact
owner7/recruiter[7,8] POST, single create, regional link, duplicate recovery,
remembered defaults on reopening and desktop/mobile layout. Screenshots are
ignored runtime evidence with fictional identities. Syntax/version/repository,
genuine Windows Antiword/Tesseract, owner-source preflight and24 source-smoke
assertions pass. No protected native compilation or macOS test is claimed.
