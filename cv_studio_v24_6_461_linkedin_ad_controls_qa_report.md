# CV Studio v24.6.461 — LinkedIn folders and reversible Added controls

Historical QA record; root `VERSION` remains the release reference.

The owner confirmed the missing search results were caused by the wrong installed
companion version; discovery worked after updating/reloading. A subsequent
screenshot showed controls competing with native card content as a horizontal
flex item. Reload cleared the changed-page error. No source-identity guard was
relaxed on the basis of that transient error.

The owner then requested clicking Added to un-add, plus folder selection and
creation on LinkedIn. Controls now mount inside a recognized native text column,
without changing native styles. Injected control labels are excluded from saved
summaries even before native footer text.

Explicit removal uses recoverable Trash. Adding again restores the existing
record and preserves contact, notes, status and dates. Folder selection/creation
uses the existing guarded APIs through the exact bound app document. Creating a
folder alone saves no ad. Restoring followed by a failing folder move returns the
actual Added state/folder plus a warning without replaying writes. An existing
lead open for editing blocks these changes, preserving its draft.

Search readiness rejects older companions before clearing results or opening
tabs. Reader-start/read errors receive fixed redacted guidance. An old local app
page rejects management commands rather than treating them as legacy adds; both
updated app and companion are needed for the new controls.

## Verification

- Full isolated unfiltered Windows Python suite: **1,737 passed, four skipped,
  7,599 subtests passed**, 188.08 seconds.
- Focused VM tests verify trusted interactions, native flex-row/text-column
  placement, Add/remove/restore, folder list/create/selection, duplicate and
  partial-failure preservation, editing-draft guards, old-page capability checks,
  exact document/channel/source authority, invalid operations and timeout
  non-replay. Search-readiness tests fail against the old gate, then pass.
- **All 41 JavaScript suites passed.** Source syntax/repository/whitespace checks,
  owner-source native-dependency preflight and **24 source smoke assertions
  passed**. Genuine bundled Windows Antiword and Tesseract/English functional
  checks passed; no local native Mac or protected-build claim.
- An actual isolated browser fixture with sample data and actual content-button
  code verified readable card text, selecting SAP, Add, clicking Added to remove,
  and creating/selecting Priority Finance. Extension transport was simulated;
  this is not a live installed-companion claim.
- A second isolated sample fixture used the actual controller and backend APIs
  through a simulated companion transport. Add increased active leads from one
  to two in Priority Finance; remove returned to one; creating SAP Shortlist
  changed no lead count; Add restored the same ad into SAP Shortlist. The manual
  note `Keep this unsaved draft` remained intact throughout. Test pages closed
  and fixture servers stopped; no owner data was used.
- Additional browser layout fixtures inherited nowrap styles and exercised
  flex (450 px), narrow (280 px) and grid (350 px) cards. Text widths before and
  after successful Add or a long error were exactly 330.3125, 196 and 266 px,
  respectively. None overflowed. Controls isolate their inline size and explicitly
  wrap text, so status messages cannot become a competing card column.

A fresh source preview on 5077 uses a verified SQLite snapshot of the
older preview's two lead rows. Read-only backup comparison and integrity checking
verified the copy; the original 5074 preview and installed owner app remain
untouched. A four-file companion ZIP is verified against current source bytes.
Its SHA-256 is
`0b45cc0ac66f603a3d64a37298927e4928c944fdd576eea2d8a2ee59c3955043`.

The normal browser disconnected during diagnosis. Its Extensions page was blocked
by browser URL policy; the owner supplied the version diagnosis instead. No live
LinkedIn write, paid call, owner-record mutation or installed-app update was made.
Routes (120), guards (five), schemas, the four companion assets and permissions
remain unchanged. No protected build, PR or merge is part of this checkpoint.
