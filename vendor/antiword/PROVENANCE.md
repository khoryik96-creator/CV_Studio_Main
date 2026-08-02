# Antiword 1.3.5 provenance and redistribution record

This directory contains the mandatory native legacy `.doc` runtimes authorized
for the CV Studio v24.6.246 candidate. They are isolated from CV Studio
application source and used only for legacy Microsoft Word decoding. The last
completed release remains v24.6.243 until every native candidate gate passes.

## Upstream identity

- Package: `antiword` 1.3.5; embedded Antiword engine: 0.37.
- Publisher/build service: rOpenSci R-universe.
- Upstream repository: <https://github.com/ropensci/antiword>
- Upstream commit: `51441d45283512081c08010835b8002af79fe5e6`.
- Package/API record:
  <https://ropensci.r-universe.dev/api/packages/antiword>
- Package page: <https://ropensci.r-universe.dev/antiword>
- License declared upstream: GPL-2.

The R-universe package API records the source archive and platform binaries
against the same upstream commit. The v24.6.246 candidate authorizes the current
R 4.6.1 Intel and Apple Silicon rebuilds for native validation alongside the
existing Windows runtime.

## Exact official artifacts

| Purpose | Official URL | SHA-256 |
| --- | --- | --- |
| Corresponding source | `https://ropensci.r-universe.dev/src/contrib/antiword_1.3.5.tar.gz` | `72e84b33b54c11101cb70d63304ca0283f57a6d0ef518ca6329ff5e6490ad630` |
| Windows x64, R 4.6 package | `https://ropensci.r-universe.dev/bin/windows/contrib/4.6/antiword_1.3.5.zip` | `9a99f67680475605de009cb85ba94c7dc546eb261a4256d743597fbb24b0ddf8` |
| macOS Intel R 4.6.1 | `https://r2.ropensci.org/0416f1389dc01398cb820ec014e976a5c2198bb103a725f290efce1598f0fced` | `0416f1389dc01398cb820ec014e976a5c2198bb103a725f290efce1598f0fced` |
| macOS Apple Silicon R 4.6.1 | `https://r2.ropensci.org/1536939cca2c1b9cfcab7721c8982933bf8093eda0460f0e38055e7c826eae9a` | `1536939cca2c1b9cfcab7721c8982933bf8093eda0460f0e38055e7c826eae9a` |

R-universe redirects each URL to content-addressed storage whose identifier is
the same SHA-256. All three authorized archives are retained under `packages/`,
their extracted platform runtimes are retained under platform-specific
directories, and the exact corresponding source remains under `source/`.

## Runtime extraction

Each platform directory contains only the official package's `bin/` and
`share/` runtime trees plus a generated `SHA256SUMS` file. Each runtime has
exactly 37 files. CV Studio separately pins every checksum-manifest and
executable hash:

| Platform | Executable SHA-256 | SHA256SUMS SHA-256 |
| --- | --- | --- |
| Windows x64 | `2cbab2831854ccd5141ea328824a77cb889586db2e97129873d543a52cf3e15c` | `7d365a89f268a2fc34f815b369474124bc6a1aac02e9b0b57e6dfd5eb5368da0` |
| macOS Intel | `afeec28ba1bc3f89e9552f26402312c84d072b91f301200710f113afed36dea7` | `7e403a00b2acd1186c714bc55fe382f2b8a03fb5c430edd16e4d447e3f9f4ee8` |
| macOS Apple Silicon | `dd4be2c485c589cd4ac8495c9de77510b7496d2acc44deadebab80ec88d6769d` | `6c59492af62df5d342c16b3126e588a4bbe855f3ba37f1f9120dc3e5352f6ce3` |

File inspection identifies the executables as PE32+ Windows x64, Mach-O x86_64
and Mach-O arm64 respectively. Runtime trust is based on the exact official
archives, complete-file manifests, executable hashes and matching native
architecture checks, not on publisher-signature claims. A future macOS release
still requires successful execution on both native Mac architectures.

## Verification-to-execution identity

CV Studio v24.6.241 corrected the v24.6.240 Windows
verification-to-execution race. On Windows, verification opens the runtime
root, pinned manifest, genuine
fixture, every manifest parent directory and all 37 manifest-listed files
with read-only handles that allow only read sharing. These handles deny
write, delete and rename replacement while hashes are computed and remain
open through functional or document process creation and completion.

Antiword's child environment removes `ANTIWORDHOME` and binds `HOME` to the
locked executable file, not a writable directory. The upstream
`$HOME/.antiword` lookup therefore cannot be populated to shadow the pinned,
locked global mapping resources. Timeouts, process-start failures and
cancellation terminate/reap the process where applicable and release every
handle in deterministic cleanup. On macOS, the candidate copies the
manifest-bound runtime and fixture to a private temporary tree, verifies every
byte, applies user-immutable flags and restrictive modes, and executes from
that snapshot before removing it. Fixture output markers supplement the pinned
executable/runtime identity; they cannot establish trust on their own.

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
The v24.6.246 candidate requires matching native Intel and Apple Silicon GitHub
runners to verify installer selection, immutable execution, diagnostics,
functional extraction and protected-package smoke. No v24.6.246 release or
macOS support claim exists until both gates pass.
