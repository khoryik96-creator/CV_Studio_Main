"""Microsoft Graph / Outlook pure helpers (Phase 7B).

First slice of the OneNote + Outlook / MS-Graph domain extraction: the
stateless helpers that touch neither Flask, the application, the credential
stores, nor the network — tenant sanitisation, account projection, the
device-login/draft error-payload translator, and Outlook draft-input
validation. These are a verbatim move of the legacy web-shell helpers.

The stateful service handlers (token lifecycle, credential storage, Graph
calls, the OneNote/Outlook route bodies) stay in ``app.py`` for now and move in
later slices as an explicitly wired service class. This module never imports
``app``.
"""

from __future__ import annotations

import json
import re


def _safe_json_object(text):
    """Parse a JSON string, returning ``{}`` on empty or invalid input.

    Mirrors the web shell's ``safe_json(text, {})`` for the already-decoded
    string inputs this module passes it, without depending on ``app``.
    """
    if not text or not str(text).strip():
        return {}
    try:
        return json.loads(text)
    except Exception:
        return {}


def _ms_safe_tenant(value):
    tenant = re.sub(r"[^A-Za-z0-9_.-]", "", str(value or "common").strip())
    return tenant or "common"


def _ms_outlook_account_normalize(raw):
    raw = raw if isinstance(raw, dict) else {}
    return {
        "id": str(raw.get("id") or ""),
        "displayName": str(raw.get("displayName") or "").strip(),
        "email": str(raw.get("mail") or raw.get("userPrincipalName") or raw.get("email") or "").strip(),
    }


def _ms_outlook_error_payload(raw_body, status=0, context="Microsoft Outlook"):
    text = raw_body.decode(errors="replace") if isinstance(raw_body, bytes) else str(raw_body or "")
    data = _safe_json_object(text)
    err = data.get("error") if isinstance(data, dict) else None
    code = ""
    description = ""
    if isinstance(err, dict):
        code = str(err.get("code") or "")
        description = str(err.get("message") or "")
        inner = err.get("innerError") if isinstance(err.get("innerError"), dict) else {}
        if not code:
            code = str(inner.get("code") or "")
    elif isinstance(err, str):
        code = err
        description = str(data.get("error_description") or data.get("error_uri") or "")
    if not code and isinstance(data, dict):
        code = str(data.get("code") or "")
    combined = (code + " " + description + " " + text).lower()
    friendly = "{} request failed".format(context)
    action = "Review Technical details and try again."
    pending = False
    if "authorization_pending" in combined:
        friendly = "Microsoft Outlook login is still waiting for approval."
        action = "Finish the Microsoft device login, then click Finish Outlook Login again."
        pending = True
    elif "slow_down" in combined:
        friendly = "Microsoft asked CV Studio to slow down the login check."
        action = "Wait a few seconds, then click Finish Outlook Login again."
        pending = True
    elif "unauthorized_client" in combined or "aadsts700016" in combined or "invalid_client" in combined:
        friendly = "The Microsoft Outlook app Client ID is invalid or not enabled for this tenant."
        action = "Check the Client ID and tenant, then enable public-client/device-code authentication in the Microsoft app registration."
    elif "consent_required" in combined or "interaction_required" in combined:
        friendly = "Microsoft needs the Outlook permissions to be approved again."
        action = "Reconnect Outlook and approve User.Read and Mail.ReadWrite. An administrator may need to grant consent."
    elif "insufficient" in combined or "erroraccessdenied" in combined or "authorization_requestdenied" in combined:
        friendly = "The connected Microsoft account does not have permission to create Outlook drafts."
        action = "Add delegated Mail.ReadWrite to the app registration, grant consent, then reconnect Outlook."
    elif "access_denied" in combined or "authorization_declined" in combined:
        friendly = "Microsoft Outlook login was cancelled or denied."
        action = "Start the Outlook connection again and approve the requested permissions."
    elif "expired_token" in combined or "code_expired" in combined:
        friendly = "The Microsoft Outlook login code expired."
        action = "Start Outlook login again to get a fresh device code."
    elif "invalid_grant" in combined:
        friendly = "The Microsoft Outlook session expired or was revoked."
        action = "Disconnect and reconnect Outlook."
    elif status == 401:
        friendly = "The Microsoft Outlook connection expired."
        action = "Reconnect Outlook."
    elif status == 403:
        friendly = "Microsoft refused permission to create the Outlook draft."
        action = "Confirm delegated Mail.ReadWrite is granted, then reconnect Outlook."
    return {
        "error": friendly,
        "error_code": code or ("HTTP_{}".format(status) if status else "MICROSOFT_ERROR"),
        "action": action,
        "pending": pending,
        "technical_details": text[:2400],
        "status": int(status or 0),
    }


def _ms_outlook_validate_draft_input(data):
    recipient = str(data.get("to") or "").strip()
    subject = re.sub(r"[\r\n\t]+", " ", str(data.get("subject") or "")).strip()
    html_body = str(data.get("html") or "").strip()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", recipient):
        raise ValueError("Invalid Outlook draft recipient")
    if not subject:
        raise ValueError("Missing Outlook draft subject")
    if not html_body:
        raise ValueError("Missing Outlook draft HTML body")
    if len(subject) > 998 or len(html_body) > 250000:
        raise OverflowError("Outlook draft content is too large")
    return recipient, subject, html_body
