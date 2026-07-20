# CV Studio native protected builds — owner guide

This folder belongs only in the private-source package.

## What this build protects

- Compiles the Python/Flask backend into a native Nuitka standalone executable.
- Excludes readable backend source, owner Authy enrollment material, private handover/reference notes, build tools and compiler output from colleague packages.
- Conservatively transforms the browser JavaScript to make casual copying harder.
- Keeps a minimal `app.py` launcher only so the existing Windows/macOS installer and receipt checks continue to work.

## What it cannot make secret

CV Studio is a browser-based local application. Any JavaScript delivered to a colleague's browser can ultimately be inspected through browser developer tools. The protected build raises the effort required to copy the application, but it is not unbreakable DRM. Truly hiding all logic requires moving that logic to an owner-controlled server.

## Safe release rule

Never distribute a protected package unless its platform build finishes with:

1. source preflight passed;
2. native compilation passed;
3. source-leak scan passed;
4. `/ping`, `/status`, `/`, vendor asset and DOCX-generation smoke tests passed;
5. a protected smoke JSON file showing `"ok": true`.

A failed smoke test deletes the colleague ZIP automatically. The original private-source ZIP remains the only patch base.

## Windows

Run:

```text
owner_build_tools\BUILD_PROTECTED_WINDOWS.bat
```

The artifact is written to `protected-output`.

## macOS

Run:

```text
owner_build_tools/BUILD_PROTECTED_MAC.command
```

The script detects Apple Silicon (`arm64`) or Intel (`x86_64`) and produces the matching package.

## Building all three packages without owning every Mac architecture

Use the private GitHub Actions workflow in `.github/workflows/build-protected.yml` inside a private repository. It builds and smoke-tests:

- Windows x64;
- macOS Apple Silicon;
- macOS Intel.

Only repository users with access can download workflow artifacts. Keep the repository private and never invite colleagues who should not receive source access. The included `.gitignore` excludes `OWNER_ONLY_AUTHY_SETUP/`, build output, dependencies and runtime logs because the QR/manual setup files are not needed by CI.

## Future patches

1. Keep the latest private-source ZIP.
2. Patch and test that readable source.
3. Run the protected builders.
4. Distribute only the platform-matching protected artifacts whose smoke JSON says `ok: true`.
5. Keep the new private-source ZIP for the next patch.

The private-source ZIP remains the only patch base. Never patch from a colleague package.

## macOS signing note

The builder applies an ad-hoc code signature and the Authy-protected installer clears quarantine only from CV Studio's own `runtime/native` directory. This is not Apple notarisation. Organisations with strict Gatekeeper/MDM policy may still require an Apple Developer ID-signed and notarised build.

## Authy limitation

The installer TOTP remains an offline installation deterrent. Because offline verification material must exist on the colleague computer, a determined reverse engineer can reconstruct it. Native compilation protects the application logic more meaningfully; it does not turn the Authy gate into server-backed licensing.


## v24.6.184 Windows smoke-test hardening

- Windows native runtime uses Nuitka console mode `hide` rather than `disable`, preserving diagnostic streams while keeping the console hidden.
- Native startup waits up to four minutes by default and prints progress every 15 seconds.
- Early process exits are detected immediately.
- Runtime and startup logs are preserved in `protected-output` when smoke testing fails.
- A failed smoke test still deletes the colleague ZIP so it cannot be distributed accidentally.


## v24.6.185 `/ping` smoke-test correction

CV Studio's `/ping` endpoint intentionally returns HTTP `204 No Content`. The protected builder now treats either 200 or 204 as a healthy readiness response and does not require a response body for `/ping`. All other smoke-test pages continue to require HTTP 200 and non-empty content.


## v24.6.186 security and reliability hardening

- All Flask routes reject non-local Host headers to block DNS rebinding.
- Generated DOCX temporary files are deleted after each response.
- Protected `/status` reports the process serving the request rather than counting `pythonw.exe`.
- OCR dependencies are installer-managed; request handlers never run `pip`.
- Windows installers stop early with a clear instruction when the extraction path is too long.
- Protected smoke tests use the production CV schema and verify rendered Word XML content.

## v24.6.187 Windows hidden runtime

The Windows binary is compiled with no-console mode. Normal launch uses `CV Studio.bat` → `START_HIDDEN.vbs`, which starts `runtime\native\CVStudio.exe` with hidden window style. The protected `app.py` launcher and in-app restart also use `CREATE_NO_WINDOW`. No persistent CMD window should be visible or own the server process. When console streams are unavailable, runtime output is written to `%LOCALAPPDATA%\TheGuoLab\CVStudio\runtime.log`.

## v24.6.193 protected release requirements

- The builder seals the two largest proprietary prompt constants in a temporary native compile source. The readable owner source remains the future patch base.
- The exact adm-zip 0.5.17 runtime folder is bundled and checked against a pinned aggregate SHA-256 tree hash. Native smoke tests deliberately remove `NODE_PATH` so they cannot borrow owner dependencies.
- Windows and macOS artifacts contain only their own platform launchers. The owner-only title-cache merge utility is not included in colleague packages.
- Launch and smoke validation require the exact version, package root and instance identity, not only a healthy `/ping` response.
- Colleague packages keep JobAdder, OneNote, Outlook and AI credentials in native/backend protected storage rather than browser localStorage.
- JobAdder reconnect can reuse a securely stored Client Secret only for the exact same Client ID. The frontend sees only whether a matching secret is configured and never receives the secret value.
- Runtime logs rotate continuously and redact common credentials and email addresses. Large/corrupt documents are bounded before preview, extraction or OCR.
- Windows installers finalize the package-bound receipt only after required setup succeeds; macOS does the same after Node/adm-zip validation.
- CI uploads colleague ZIP/smoke files separately from private compiler diagnostics.

### Remaining platform reality

Final Windows no-console, DPAPI, VBScript and PowerShell behavior must be checked on Windows. Apple Silicon/Intel binaries, Keychain, LaunchAgent, Gatekeeper and ad-hoc signing must be checked on their matching Macs. Native compilation and prompt sealing materially raise copying effort, but browser JavaScript and offline verifier material remain reversible to a determined specialist.


## v24.6.193 deterministic adm-zip packaging

The protected package now copies `adm-zip` from the immutable owner-vetted tree under
`owner_build_tools/vetted_node/adm-zip`. The normal npm working tree is checked only
for version and a functional ZIP round trip; harmless Windows/npm metadata can no
longer falsely fail the protected build, and mutable `node_modules` content can never
enter the colleague artifact.


## v24.6.193 private GitHub repository consistency

The protected build deliberately uses no npm lock file. The authoritative dependency controls are the exact `adm-zip` 0.5.17 pin plus the immutable vetted tree and pinned aggregate hash.

Before running private GitHub Actions, update the private repository with the complete current owner kit. On Windows you may run:

```text
owner_build_tools\APPLY_PRIVATE_REPO_FIX_WINDOWS.bat
```

On macOS:

```text
owner_build_tools/APPLY_PRIVATE_REPO_FIX_MAC.command
```

The helper removes/stages stale `package-lock.json` or `npm-shrinkwrap.json`, confirms the exact package pin, and verifies that the workflow uses `npm install --package-lock=false` rather than `npm ci`. Never mix the no-lock owner kit with an older lock-based workflow.


## v24.6.193 Git checkout byte stability

The private repository must preserve exact bytes on every runner. Keep the root `.gitattributes` file committed:

```text
* -text
```

The workflow additionally disables `core.autocrlf` before checkout. Do not remove or move that step below `actions/checkout`. All Windows `.bat` files are committed with CRLF line endings; because text conversion is disabled, those committed endings are preserved exactly.


## v24.6.194 owner script byte requirements

Owner-only Windows `.bat` builders must be UTF-8 without BOM and CRLF-only. Owner-only macOS `.command` builders must be UTF-8 without BOM, LF-only, and begin with `#!` at byte zero. `repo_consistency.py --repair` enforces these rules and a clean repair run must report no phantom changes.


## v24.6.195 runtime hardening

The protected source now enforces a per-process HttpOnly browser session for paid AI routes, validates Blind JD preview data URLs, prefers trusted Antiword locations, keeps `INSTANCE_PORT.ps1` BOM-free, and preserves the JobAdder regional API URL supplied by OAuth instead of forcing AU3.
