# CV Studio v24.6.241 Windows-x64 Antiword TOCTOU corrective QA report

## Release decision

CV Studio v24.6.241 is the narrow corrective successor to the immutable
Windows-x64-only v24.6.240 mandatory Antiword release. It fixes only the
confirmed verification-to-execution race in the application and Windows
installer.

Antiword 1.3.5 (engine 0.37) remains mandatory, bundled, hash-pinned,
unsigned with exact-hash trust, GPL-2 accompanied, corresponding-source
complete and genuinely function-tested on Windows x64. No Intel or Apple
Silicon macOS support claim or v24.6.241 macOS artifact is authorized. macOS
users remain on v24.6.239.

Exact master baseline:
`a5762488f7d90fe58f00870b2c0b2944be084e71`.

Exact v24.6.240 corrective baseline:
`0a8179a1d580d5db923a521e20f2693a24d651c4`.

## Confirmed issue and correction

v24.6.240 hashed and function-tested `antiword.exe` and its runtime tree, then
released those handles before later pathname-based process creation. The
managed runtime is user-writable, so a write/delete/rename replacement in that
gap could substitute another executable or mapping resource. Public fixture
markers did not establish executable identity.

v24.6.241 makes these bounded corrections:

1. `cvstudio_antiword.py` opens the runtime root, pinned manifest, genuine
   fixture, every runtime parent directory and all 37 manifest-listed files
   with Windows `CreateFileW` handles that allow only read sharing.
2. Hashes, exact-file-set checks, reparse/link checks and the pinned executable
   identity are evaluated while those handles deny write/delete/rename.
3. The same handles remain open through functional process creation and
   completion and through actual legacy-`.doc` process creation and completion.
4. Both application legacy-`.doc` launch paths use one
   `run_verified_antiword()` primitive; no application Antiword launch retains
   the old verify-release-execute sequence.
5. The child environment removes `ANTIWORDHOME` and sets `HOME` to the locked
   executable file. `$HOME/.antiword` cannot be created to shadow the pinned,
   locked global mapping resources.
6. Python process timeout and cancellation kill/reap the process before the
   lock context exits. Process-start and validation failures also release every
   handle.
7. `INSTALL_CORE.ps1` uses the equivalent read-only, read-share-only
   `SafeFileHandle` set around its mandatory functional process and disposes
   every handle in `finally`.

The correction does not replace the existing hashes, manifest, unsigned-binary
check, fixture, timeouts, repair behavior, mandatory-install boundary,
diagnostic shape, paths, junction/reparse rules or provenance.

## Adversarial regression coverage

- In-place write, delete, rename and atomic replacement of `antiword.exe` are
  denied immediately before both functional and actual process creation.
- The same four replacement classes are denied for the critical
  `share/antiword/UTF-8.txt` mapping resource.
- A modified executable cannot become trusted or functional even when a mocked
  process would print both expected public fixture markers; process creation is
  never reached.
- Genuine bundled fixture extraction succeeds through the protected interval.
- Success, functional timeout, actual timeout, process-start failure,
  cancellation and integrity-failure paths prove that executable/resource
  locks are released afterward.
- The real Windows installer self-test proves protected execution, blocked
  executable/resource replacement, timeout/failure cleanup, genuine
  extraction, initial install, repeated-install idempotency, corruption
  repair, nested-junction rejection and missing-bundle failure.
- Source coverage requires both application launch paths to call the secured
  primitive and rejects the former direct Antiword subprocess patterns.

## Validation results

- Final focused Antiword and Phase 4 document/route characterization:
  30 passed, 0 failed.
- Complete Python discovery was run exactly once after the final application
  and installer correction: 140 tests executed; 138 passed and two unrelated
  pre-existing `datetime.utcnow()` deprecation warnings were promoted to
  errors by `PYTHONWARNINGS=error`.
  - `test_contact_and_salary_caches_import_and_keep_legacy_json_readable`
    reached the existing salary-cache `datetime.utcnow()` call.
  - `test_jobadder_diagnostics_preserve_network_error_response_shapes`
    reached the existing JobAdder diagnostic `datetime.utcnow()` call.
  Neither location or behavior changed in this milestone. They were not fixed
  and the complete suite was not rerun, per the owner’s exact-once and
  no-unrelated-work instructions.
- All five frontend fixtures passed.
- Live source smoke passed all 24 assertions.
- Tracked syntax passed for 29 Python, 23 JavaScript, five Bash/command and five
  PowerShell files; both inline browser scripts passed owner preflight.
- Owner Windows-x64 source preflight passed, including genuine Antiword
  extraction and exact `adm-zip` verification.
- Repository consistency and whitespace checks passed after deterministic CRLF
  normalization of the edited Windows batch/VBS version surfaces.

## Focused self-review

One focused self-review was performed, limited to this TOCTOU correction.
It traced every application and installer Antiword process launch, checked
lock acquisition order and cleanup, verified no direct application Antiword
launch remained, confirmed no route/guard/schema drift, rechecked the exact
v24.6.239 macOS production hashes and rehashed the immutable v24.6.240 release
artifacts. The pass found no remaining concrete, actionable issue in scope.

No repeated self-review loop or independent reviewer was started.

## Preserved boundaries

- All 107 Flask routes, five ordered guards, 18 compatibility signatures,
  SQLite schema 10 and Phase 5A journal schema 1 remain.
- No JobAdder behavior, Phase 6 work, backburner item, credential behavior,
  provider behavior or unrelated workflow changed.
- v24.6.240 artifacts remain unchanged.
- v24.6.241 remains Windows-x64-only; no macOS artifact or support claim is
  produced.

Stop before handoff or merge. Do not begin JobAdder work or Phase 6.
