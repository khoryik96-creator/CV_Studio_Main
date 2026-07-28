# Antiword 1.3.5 provenance and redistribution record

This directory contains the mandatory legacy `.doc` runtime authorized for
CV Studio v24.6.240. It is isolated from CV Studio application source and used
only for legacy Microsoft Word decoding.

## Upstream identity

- Package: `antiword` 1.3.5; embedded Antiword engine: 0.37.
- Publisher/build service: rOpenSci R-universe.
- Upstream repository: <https://github.com/ropensci/antiword>
- Upstream commit: `51441d45283512081c08010835b8002af79fe5e6`.
- Package/API record:
  <https://ropensci.r-universe.dev/api/packages/antiword>
- Package page: <https://ropensci.r-universe.dev/antiword>
- License declared upstream: GPL-2.

The R-universe package API records the source archive and all three binaries
below against the same upstream commit and reports successful native checks
for Windows x64, macOS x86_64 and macOS arm64.

## Exact official artifacts

| Purpose | Official URL | SHA-256 |
| --- | --- | --- |
| Corresponding source | `https://ropensci.r-universe.dev/src/contrib/antiword_1.3.5.tar.gz` | `72e84b33b54c11101cb70d63304ca0283f57a6d0ef518ca6329ff5e6490ad630` |
| Windows x64, R 4.6 package | `https://ropensci.r-universe.dev/bin/windows/contrib/4.6/antiword_1.3.5.zip` | `9a99f67680475605de009cb85ba94c7dc546eb261a4256d743597fbb24b0ddf8` |
| macOS Intel, R 4.6 package | `https://ropensci.r-universe.dev/bin/macosx/big-sur-x86_64/contrib/4.6/antiword_1.3.5.tgz` | `501f2cf83b050fd4a56ab1ecff6fe21295c168eb4a9876d46c259e7ca21cb923` |
| macOS Apple Silicon, R 4.6 package | `https://ropensci.r-universe.dev/bin/macosx/sonoma-arm64/contrib/4.6/antiword_1.3.5.tgz` | `17cd193eb8ed3b27d092c60fec181e6a7b6d82eda9741dbec03578396d659e25` |

R-universe redirects each URL to content-addressed storage whose identifier is
the same SHA-256. The original archives are retained under `packages/`, and
the exact corresponding source is retained under `source/`.

## Runtime extraction

Each platform directory contains only the official package's `bin/` and
`share/` runtime trees plus a generated `SHA256SUMS` file. Each runtime has
exactly 37 files. CV Studio separately pins the checksum-manifest hash and
executable hash:

| Platform | Executable SHA-256 | SHA256SUMS SHA-256 |
| --- | --- | --- |
| Windows x64 | `2cbab2831854ccd5141ea328824a77cb889586db2e97129873d543a52cf3e15c` | `7d365a89f268a2fc34f815b369474124bc6a1aac02e9b0b57e6dfd5eb5368da0` |
| macOS Intel | `867f9688d851ec85cb6dd5e70f14abcf53e2c77bf55da20ec6e8b94399904d5f` | `e616a696828ce938ad90594ce635ee4889d464787cdfd110f5e42efd12418729` |
| macOS Apple Silicon | `d4ad0924e195f5dc6a898d5bdcb734a532446ed927af7e3c49865b11ef5e250d` | `f07264b33fefd3b12ce0af40f312ea8abd290a71e3d04f2c63a2bb16135cbe9e` |

Cross-platform file inspection identifies the binaries as PE32+ Windows x64,
Mach-O x86_64 and Mach-O arm64 respectively. Both macOS executables link only
to `/usr/lib/libSystem.B.dylib`. The Intel binary has no embedded code
signature; the Apple Silicon binary has an embedded code-signature load
command. Runtime trust is therefore based on the exact official archive,
complete-file manifest, executable hash and native architecture/signature
checks, not on publisher-signature claims.

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
R-universe reports successful native package checks for both exact macOS
artifacts, whose upstream example executes this fixture. CV Studio's own
protected macOS packages must additionally pass the existing native build
smoke and installer/diagnostics checks on the matching real Mac architecture
before a macOS protected artifact or completed cross-platform release may be
claimed.
