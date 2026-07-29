# CV Studio v24.6.241 Phase 6 handover

## Owner gate

Phase 6 remains inactive. This document records the narrow Windows Antiword
verification-to-execution TOCTOU correction and does not authorize Phase 6,
JobAdder settings/sign-out, AI Crawler changes, backburner work, handoff or
merge.

## Release identity and platform boundary

- Release: CV Studio v24.6.241.
- Corrective baseline: v24.6.240 commit
  `0a8179a1d580d5db923a521e20f2693a24d651c4`.
- Exact master baseline:
  `a5762488f7d90fe58f00870b2c0b2944be084e71`.
- Supported platform: Windows x64 only.
- Mandatory dependency: bundled, hash-pinned and functionally verified
  Antiword 1.3.5 (engine 0.37).
- No v24.6.241 Intel or Apple Silicon macOS support claim or artifact was
  produced. macOS users remain on v24.6.239.

## Corrected Windows execution boundary

Application and installer verification now retain Windows file/directory
handles that deny write/delete/rename from before hashing through process
creation and completion. The protected set includes the runtime root, manifest,
genuine fixture, runtime directories, executable and every manifest-listed
mapping/resource file.

Both application legacy-`.doc` launch paths use the shared secured execution
primitive. The Windows installer applies the same protected interval to its
mandatory functional check. Fixture markers supplement the locked pinned
identity and cannot establish trust by themselves.

Timeout, process-start failure and cancellation cleanup terminate/reap the
child where applicable, and every handle is released in deterministic cleanup.
Repair, repeated installation, diagnostics, mandatory-install failure, exact
hashes, unsigned-binary trust and reparse/link rejection remain unchanged.

## Preserved release history

All v24.6.240 artifacts were rehashed during focused review and remain
unchanged. The exact v24.6.239 macOS installer, launcher, rollback and
historical owner-builder command hashes remain unchanged. No newer Mac payload,
mandatory behavior, protected target or artifact exists.

## Validation record

- Focused Windows Antiword/installer and document-boundary tests: 30 passed.
- Complete Python discovery: run exactly once; 140 executed, 138 passed, with
  two unrelated existing `datetime.utcnow()` deprecation warnings promoted to
  errors by strict warning handling. No unrelated correction or rerun was
  performed.
- All five frontend fixtures: passed.
- Live source smoke: 24 assertions passed.
- Tracked Python/JavaScript/Bash/PowerShell and inline-script validation:
  passed.
- Owner Windows-x64 source preflight, repository consistency and whitespace:
  passed.
- One focused TOCTOU self-review: clean.
- No repeated review loop or independent reviewer was started.

## Preserved contracts

The corrective release preserves all 107 routes, five guards, 18 compatibility
signatures, SQLite schema 10, Phase 5A journal schema 1, prior Phase 1-5B
contracts, mandatory Windows Antiword behavior and the Phase 6 stop boundary.

Stop before handoff or merge. Do not begin JobAdder work or Phase 6 without a
new explicit owner authorization.
