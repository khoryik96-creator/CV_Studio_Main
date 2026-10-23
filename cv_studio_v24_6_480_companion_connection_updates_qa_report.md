# Companion automatic connection and easier updates — v24.6.480

Owner requested persistent companion availability and removal of repeat ZIP
downloads. Branch `codex/v24.6.480-companion-easy-updates` starts at merged
master `065e75e8890e9f126196f811ef809eab237f39e4` (v479). This is a local source
checkpoint, not a merged release or an update of the owner's browser/installation.

## Behavior

- The enabled companion binds verified local CV Studio documents automatically
  on load, tab return, and before forwarded requests. Its ON badge describes a
  connection, not a switch the user has to keep clicking. Explicit toolbar
  connection remains available as a recovery/selection action.
- Binding is serialized; repeated connection to the same document retains its
  active run. Replacement documents receive no old run authority. Background
  app tabs cannot replace an idle binding; active worker runs/captures reject
  another document. Document IDs, current/pending URLs, app markers, extension
  sender identity, top-level frame and durable session writes are checked.
- Setup copies the companion folder bundled inside the currently served app.
  Users must copy this from their normal installation, not a temporary preview.
  Load unpacked from that folder once, keeping Developer mode on. Normal app
  Update & Restart updates these files in place.
- Apply companion update checks a capability marker and reads the extension's
  own local manifest with no cache. Its version must match the app. It refuses
  active work and rechecks after the asynchronous read. Only then can runtime
  reload apply existing local files. No download, remote code, browser-profile
  write, new permission, policy setting, forced page refresh or action replay.
- Old downloaded copies receive one-time setup guidance; their manual ZIP path
  remains available. Clipboard denial leaves a selectable folder path. Explicit
  searches, LinkedIn writes and DeepSeek consent remain unchanged.

## Verification

- New worker tests failed on v479 before implementation. Passing cases cover
  automatic connection, document replacement, concurrent/idempotent binding,
  fake pages/foreign senders/subframes/stale documents/pending navigation,
  active and background-tab protection, session write failure, own-file reload,
  old downloaded files and a search starting during update validation.
- Controller/content tests cover automatic load/return connection, copy fallback,
  already-current/reloading messages, legacy capability guidance, and no paid
  operation from setup. Existing ad import, folder, duplicate, HR, sourcing,
  ownership, suspension and cancellation suites remain passing.
- Full isolated Windows Python: **1,777 passed, 4 skipped, 8,392 subtests**,
  140.59 seconds. **All 47 JavaScript suites passed**. Native/source preflight,
  repository consistency, tracked-language syntax, whitespace and **24 source
  smoke assertions passed**. Owner receipt/state paths remained isolated.
- An isolated persistent Chromium profile loaded the actual companion. Its actual
  content script/worker connected without toolbar clicks and recovered after
  page reload. Changing only the disposable bundle's manifest from v480 to a
  synthetic next version proved uncached local-file observation, real runtime
  reload to the new version, and connection after an explicit page refresh.
  The draft textarea was retained before that user-controlled refresh. All test
  extension files/profiles were disposable; the owner's browser was untouched.
  Closing and reopening the entire isolated browser with its persisted profile
  also reconnected without reinstalling or clicking the toolbar. The actual
  Flask preview rendered both setup/update controls and returned its bundled
  folder through the new read-only action; clipboard denial remains covered.
- An initial browser test incorrectly initialized Developer mode by pref seeding;
  Chromium disabled the unpacked extension on reload. Repeating the documented
  setup through the isolated browser's real Developer mode control resolved it.
  The product setup instructions explicitly say to keep Developer mode on. No
  production browser flag or permission was added.

The route count/hash, five guards, request limit, main SQLite schema 10, journal
schema 1, Job Leads schema 2 and companion permissions remain unchanged. No live
LinkedIn scan, paid AI request, outreach, owner record mutation, protected build,
PR or merge was performed. Browser-installed-off extensions cannot reconnect
until enabled by the user.

Reference: Chrome documents [runtime reload and unpacked updates](https://developer.chrome.com/docs/extensions/reference/api/runtime#unpacked-extension-behavior)
and [one-time unpacked extension loading](https://developer.chrome.com/docs/extensions/get-started/tutorial/hello-world#load-unpacked).
