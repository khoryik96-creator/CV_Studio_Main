# CV Studio v24.6.240 Windows-x64 mandatory Antiword QA report

## Release decision

CV Studio v24.6.240 is a Windows-x64-only pre-Phase-6 dependency release.
Antiword 1.3.5 (engine 0.37) is mandatory, bundled, hash-pinned and
functionally verified for Windows x64. No Intel or Apple Silicon macOS support
claim or v24.6.240 macOS artifact was produced. macOS users remain on the last
verified release, v24.6.239.

Exact master/source baseline:
`a5762488f7d90fe58f00870b2c0b2944be084e71` (v24.6.239).

The milestone does not authorize JobAdder settings/sign-out, Phase 6, AI
Crawler behavior changes, a backburner item, handoff or merge.

## Final implementation

- `cvstudio_antiword.py` trusts only the pinned Windows-x64 managed or bundled
  runtime. It verifies the distribution archive, corresponding source,
  GPL-2 text, genuine fixture, manifest hash, exact 37-file runtime set,
  every runtime hash and executable hash before a bounded functional
  extraction.
- The Windows installer performs the same trust and functional checks before
  completing setup or issuing a receipt. Missing, altered, linked/reparse or
  non-functional runtime state fails closed and remains repairable.
- Every genuine legacy Word OLE payload reaches the verified Antiword boundary
  before weak filename/content-type dispatch, including JobAdder preview,
  prefetch, resume caches, shared extraction, visual preview and OCR.
- The subprocess environment removes `ANTIWORDHOME` and binds `HOME` to the
  verified executable directory, preventing user-controlled
  `HOME\.antiword` mappings from influencing the pinned executable.
- Candidate-text and preview cache entries record downloaded-content identity,
  strong content kind and verified-Antiword provenance. Metadata-only `.doc`
  hints cannot create or satisfy verified legacy-DOC cache provenance.
- Diagnostics preserve the legacy `dependencies.antiword` boolean and add
  bounded, redacted trust/function evidence.
- The protected build preflight and compiled smoke validate the copied bundled
  Windows runtime, require `source: bundled`, and perform genuine multipart
  `/extract-text` extraction of the pinned fixture.

## Owner scope adjustment corrections and regression coverage

1. Restored `install.sh`, `start.sh`, `restore_previous.sh` and
   `owner_build_tools/BUILD_PROTECTED_MAC.command` to the exact v24.6.239
   baseline bytes. Regression coverage pins the SHA-256 of all four files.
2. Removed the unvalidated Intel/Apple Silicon Antiword archives and extracted
   runtimes from the production/vendor tree. The Windows archive, complete
   Windows runtime, corresponding source, GPL-2 text and genuine fixture
   remain. Regression coverage requires the Mac payload paths to be absent and
   repository consistency fails if they return.
3. Restricted `cvstudio_antiword` production platform metadata to
   `windows-x64`. Regression coverage requires exactly one runtime platform and
   the exact approved distribution set.
4. Restricted the v24.6.240 protected builder CLI, host validation, compilation,
   packaging and smoke entry points to Windows x64. The private CI workflow
   contains only the Windows-x64 target. Regression coverage proves Darwin
   auto-detection and explicit Mac targets fail and the workflow contains no
   Mac target.
5. Updated phase status, owner rules, protected-build guide, Antiword
   provenance/readme and Phase 6 handover to state the Windows-only boundary,
   mandatory Windows installation, deferred native Mac validation and absence
   of a v24.6.240 Mac artifact/support claim.
6. Preserved earlier unvalidated Mac research only as provenance and future
   work: exact URLs/hashes and inspection notes remain documented, but no Mac
   archive, runtime, installer delta or protected target ships.

## Focused validation

Run on genuine Windows x64:

- `python -m unittest tests.test_antiword_mandatory_dependency -v`:
  18 passed.
- `python -m unittest tests.test_phase4_backend_modularization_characterization -v`:
  9 passed.
- Combined focused result: 27 passed, 0 failed.
- The focused suite includes genuine bundled Antiword extraction, installer
  self-test/repair/idempotency, nested-junction rejection, corrupted and extra
  runtime rejection, untrusted ambient path rejection, protected package-only
  validation, cache provenance, every legacy-DOC route boundary, exact
  v24.6.239 Mac file hashes and v24.6.240 Mac-build rejection.

## Complete regression and static validation

- Complete Python discovery: 137 passed once after the final scope adjustment,
  with `ResourceWarning` treated as an error.
- All five frontend fixtures: passed once after the final scope adjustment.
- Live source smoke: all 24 assertions passed once after the final scope
  adjustment.
- Tracked syntax: 29 Python, 23 JavaScript, five Bash/command and five
  PowerShell files passed; both full inline browser scripts also passed.
- Owner protected-source preflight, repository consistency, exact `adm-zip`
  validation and `git diff --check`: passed.

## Focused scope-adjustment self-review

One focused review was performed against exact master
`a5762488f7d90fe58f00870b2c0b2944be084e71`. It checked:

- Windows mandatory Antiword behavior and tests were not weakened;
- Mac installer/launcher/rollback bytes equal v24.6.239;
- no Mac Antiword payload remains in the shippable tree;
- no v24.6.240 Mac protected target or CI target remains;
- documentation makes no v24.6.240 Mac claim;
- routes, five ordered guards, 18 compatibility signatures, SQLite schema 10,
  Phase 5A journal schema 1 and prior Phase 1-5B contracts remain preserved.

The pass reported no remaining concrete, actionable finding. Per owner
instruction, no repeated review loop or independent reviewer was started.

## Release packaging

Only these v24.6.240 release classes are authorized:

- Windows-x64 owner/source ZIP;
- Windows-x64 native protected colleague ZIP plus genuine native smoke evidence.

Both archives are freshly extracted and byte/integrity verified. Adjacent
SHA-256 and JSON verification sidecars are authoritative for archive hashes,
byte counts and the final `source_commit`; each sidecar's `source_commit`
equals final HEAD. No v24.6.240 macOS archive exists.

Stop before handoff or merge. Do not begin JobAdder work or Phase 6.
