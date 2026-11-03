# v24.6.547 — Rich client email composer

Local branch: `codex/job-leads-email-composer`, from master v24.6.546 / `ea046fa`.

## Behavior

Email actions prefill known recipient addresses. Multiple To, CC and BCC fields
accept comma/semicolon/newline separated email addresses, capped at 100 total.
Explicit Send confirmation shows all recipients, subject, files and image count.
Cancelling never posts an email request. Completed/uncertain messages stay locked;
definitive rejections retain editable contents and require a new confirmation.

The formatting toolbar and paste preserve approved text formatting, hyperlinks,
fonts, sizes and colors. Templates persist the subject and rich signature/body,
including valid embedded PNG/JPEG/GIF images. They exclude recipient fields and
ordinary file attachments. The local template store supports create/edit/delete,
case-insensitive unique names, bounds and revision checks. Refresh does not mask
a concurrent edit; Use selected template reloads with replacement confirmation.

Uploaded/pasted banners use data images only in the local editor/template. Before
calling Graph, the server validates raster image bytes/dimensions and converts
images into CID-linked inline attachments. No script, arbitrary image URL, local
file URL, SVG or active HTML reaches the email. Files and inline images share a
10-item/2.5 MiB limit; serialized Graph JSON is conservatively capped at 3.8 MB.
The send/draft identity covers all recipients, formatting and attachment content.
Existing PPC draft requests retain their old path and payload semantics.

## Independent review

One P2 finding: pasting a clipboard containing HTML/text and an image file kept
only the image. The handler now preserves sanitized rich content and incorporates
file images not already embedded in that content. It validates clipboard file
bounds, locks editing during reads, restores the selection, and inserts only when
all data is ready. The Chromium fixture reproduces mixed HTML plus PNG paste.

The reviewer independently verified the correction in Chromium and reran the
39 email backend tests and Job Leads frontend fixture. No actionable findings
remained after follow-up review.

## Evidence

- 234 relevant backend, architecture, version and Outlook crypto tests passed.
- All 92 frontend fixtures passed, including explicit group-send cancellation,
  recipient autofill and confirmation of every recipient field.
- Actual Chromium: autofill; formatting controls; banner/file upload; template
  create/edit/refresh/apply/delete; stale-template conflict/reload; template image
  persistence; recipient/file separation; draft creation; cancelled/confirmed send;
  duplicate action lock. No JavaScript page errors.
- Syntax, whitespace and repository byte/line-ending consistency passed.
- Reproducible isolated browser fixture and workflow are under
  `tests/browser/job_leads_email_composer_server.py` and
  `tests/browser/job_leads_email_composer.py` (optional Playwright/Chromium).

All Outlook calls used fictional transport and all fixture state/receipts used
temporary paths. No real email, paid/provider action, Microsoft login/consent,
installed-app update, publication or merge was performed. Native Windows/macOS
or live Outlook rendering/delivery is not claimed. The user's original banner
file is not included; the image in the browser fixture is a sample PNG.
