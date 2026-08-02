Mandatory Antiword runtime for legacy .doc files on Windows and macOS

The v24.6.246 candidate pins rOpenSci Antiword package 1.3.5 (Antiword engine
0.37) separately for Windows x64, Intel macOS and Apple Silicon macOS. Each
installer selects and verifies only its matching native runtime before setup
can complete.

Runtime acceptance requires all of the following:

- the platform SHA256SUMS file matches the hash compiled into CV Studio;
- the exact 37-file bin/share set matches every listed SHA-256;
- the executable matches its separately pinned SHA-256 and architecture;
- native platform trust checks have the expected result;
- the bundled genuine legacy Word fixture matches its pinned SHA-256;
- Antiword extracts the expected fixture text within the bounded timeout.
- the verified runtime remains protected from replacement through process
  creation and completion (Windows deny-replacement handles; macOS private
  immutable snapshot).

CV Studio never discovers Antiword through PATH, Program Files,
ANTIWORDHOME or other arbitrary executable locations. An existing local
Antiword installation is comparison evidence only and cannot satisfy runtime
trust.

If verification fails, CV Studio may still start so diagnostics and repair
guidance remain available. Every feature that needs legacy .doc decoding
returns ANTIWORD_DEPENDENCY_UNAVAILABLE until the installer repairs the
managed runtime. LibreOffice and the native OLE parser remain defense in
depth, but their output is never presented as a verified .doc success.
A verified runtime that cannot decode a corrupt/incompatible document returns
LEGACY_DOC_EXTRACTION_FAILED with convert-to-DOCX/PDF guidance.

The v24.6.246 candidate adds separately pinned Intel and Apple Silicon runtimes.
Each macOS architecture must pass native installer, immutable-snapshot runtime,
functional fixture and protected-package smoke checks before release.

See PROVENANCE.md for upstream URLs, immutable hashes, license/source
compliance, security evidence and native release gates.
