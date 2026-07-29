Mandatory Antiword runtime for legacy .doc files

CV Studio v24.6.240 is a Windows-x64-only release. It pins rOpenSci Antiword
package 1.3.5 (Antiword engine 0.37) for Windows x64. The Windows installer
copies the exact bundled runtime into CV Studio's managed dependency directory
and verifies it before completing setup.

Runtime acceptance requires all of the following:

- the platform SHA256SUMS file matches the hash compiled into CV Studio;
- the exact 37-file bin/share set matches every listed SHA-256;
- the executable matches its separately pinned SHA-256 and architecture;
- native platform trust checks have the expected result;
- the bundled genuine legacy Word fixture matches its pinned SHA-256;
- Antiword extracts the expected fixture text within the bounded timeout.

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

No v24.6.240 macOS runtime or release artifact is shipped or supported. Intel
and Apple Silicon validation is deferred to a separately authorized native
validation milestone. macOS users remain on the last verified release,
v24.6.239.

See PROVENANCE.md for upstream URLs, immutable hashes, license/source
compliance, security evidence and the Windows release gate.
