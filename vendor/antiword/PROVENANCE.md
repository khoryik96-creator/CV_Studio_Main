# Antiword 1.3.5 provenance and redistribution record

This directory contains the mandatory Windows-x64 legacy `.doc` runtime
authorized for CV Studio v24.6.240. It is isolated from CV Studio application
source and used only for legacy Microsoft Word decoding. v24.6.240 does not
ship or claim support for Intel or Apple Silicon macOS.

## Upstream identity

- Package: `antiword` 1.3.5; embedded Antiword engine: 0.37.
- Publisher/build service: rOpenSci R-universe.
- Upstream repository: <https://github.com/ropensci/antiword>
- Upstream commit: `51441d45283512081c08010835b8002af79fe5e6`.
- Package/API record:
  <https://ropensci.r-universe.dev/api/packages/antiword>
- Package page: <https://ropensci.r-universe.dev/antiword>
- License declared upstream: GPL-2.

The R-universe package API records the source archive and all three upstream
binaries below against the same upstream commit. Only the Windows x64 binary
is authorized, bundled, installed and verified by CV Studio v24.6.240. The two
macOS records are retained solely as documented inputs for a future,
separately authorized native-validation milestone.

## Exact official artifacts

| Purpose | Official URL | SHA-256 |
| --- | --- | --- |
| Corresponding source | `https://ropensci.r-universe.dev/src/contrib/antiword_1.3.5.tar.gz` | `72e84b33b54c11101cb70d63304ca0283f57a6d0ef518ca6329ff5e6490ad630` |
| Windows x64, R 4.6 package | `https://ropensci.r-universe.dev/bin/windows/contrib/4.6/antiword_1.3.5.zip` | `9a99f67680475605de009cb85ba94c7dc546eb261a4256d743597fbb24b0ddf8` |
| Deferred macOS Intel input (not shipped) | `https://ropensci.r-universe.dev/bin/macosx/big-sur-x86_64/contrib/4.6/antiword_1.3.5.tgz` | `501f2cf83b050fd4a56ab1ecff6fe21295c168eb4a9876d46c259e7ca21cb923` |
| Deferred macOS Apple Silicon input (not shipped) | `https://ropensci.r-universe.dev/bin/macosx/sonoma-arm64/contrib/4.6/antiword_1.3.5.tgz` | `17cd193eb8ed3b27d092c60fec181e6a7b6d82eda9741dbec03578396d659e25` |

R-universe redirects each URL to content-addressed storage whose identifier is
the same SHA-256. The authorized Windows archive is retained under `packages/`
and the exact corresponding source under `source/`. The deferred macOS
archives and extracted runtimes are intentionally absent from the v24.6.240
production and packaging tree.

## Runtime extraction

The Windows platform directory contains only the official package's `bin/`
and `share/` runtime trees plus a generated `SHA256SUMS` file. It has exactly
37 files. CV Studio separately pins the checksum-manifest hash and executable
hash:

| Platform | Executable SHA-256 | SHA256SUMS SHA-256 |
| --- | --- | --- |
| Windows x64 | `2cbab2831854ccd5141ea328824a77cb889586db2e97129873d543a52cf3e15c` | `7d365a89f268a2fc34f815b369474124bc6a1aac02e9b0b57e6dfd5eb5368da0` |

File inspection identifies the shipped executable as PE32+ Windows x64.
Runtime trust is based on the exact official archive, complete-file manifest,
executable hash and native Windows architecture checks, not on
publisher-signature claims. Prior source-level inspection of the deferred
macOS binaries is recorded as future-work evidence only; it is not native
validation and supports no v24.6.240 macOS claim.

## Local comparison and security evidence

The owner-provided local installation reported package 1.3.5, GPL-2, complete
`share/antiword` resources, an unsigned executable and executable SHA-256
`5f46d20310baf9e647b658a5a8be70fcc8da940a4c068a34b17e8676bce8ba84`.
It was an older rebuild of the same package version: 49 of 58 shared package
files, including the complete resource tree, matched the current official
artifact, while the executable and generated R metadata differed. It was
functionally tested but was not copied or redistributed. CV Studio bundles the
fresh content-addressed artifacts listed above.

On 2026-07-28, Microsoft Defender engine/platform
`4.18.26060.3008-0`, signature `1.455.390.0`, reported no threats for the
downloaded/extracted official artifacts and for the comparison installation.
The Windows executable is unsigned, consistent with the owner-supplied
evidence; its exact official SHA-256 is mandatory.

## License and corresponding source

Upstream declares GPL-2 and the embedded source headers state that Antiword is
released under the GNU GPL. `GPL-2.0.txt` contains the complete GPL version 2
text obtained from <https://www.gnu.org/licenses/old-licenses/gpl-2.0.txt>.
`source/antiword_1.3.5.tar.gz` is the exact corresponding source archive bound
by R-universe to the same commit as the packaged binaries. These materials
must remain with every owner/source and protected distribution containing the
runtime.

## Functional fixture and platform release gate

`fixtures/UDHR-english.doc` is the genuine OLE Word fixture used by the
upstream maintainer's documented example:
<https://jeroen.github.io/files/UDHR-english.doc>. It contains public,
non-candidate sample content and has SHA-256
`f430cdfe9446c4b943074d4bf804232761c284f2caa3d4125006b158d8b14af8`.
Installation and runtime diagnostics accept Antiword only when it extracts the
two pinned expected phrases from this file within the bounded timeout.

The current Windows x64 runtime was functionally verified on genuine Windows.
Windows installation is mandatory and fail-closed. Intel and Apple Silicon
CV Studio validation is deferred; no v24.6.240 macOS artifact was produced and
no macOS support claim is made. macOS users remain on v24.6.239 until a
separately authorized milestone completes native build, installer,
diagnostics, functional and release-artifact verification on each matching
architecture.
