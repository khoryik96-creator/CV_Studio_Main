"""JobAdder candidate-write service for CV Studio.

The application keeps ownership of the JobAdder OAuth token lifecycle, the
critical-write concurrency guard (the ``_ja_critical_write_route`` decorator
stays on the delegating routes) and the ``JobAdderClient`` transport.  This
module holds only the JSON candidate-write handlers behind
``/jobadder/create_candidate`` and ``/jobadder/update_candidate``.  It reaches
the token refresh, request body and transport through injected callbacks and
never imports the application.  Both writes stay non-retryable
(``safe_to_retry=False``); the logic is a verbatim move of the legacy web-shell
handlers.
"""

from __future__ import annotations

import json
import re
import sys
import hashlib
import secrets
import threading
import time
import urllib.error
from typing import Any, Callable


class JobAdderContactError(Exception):
    def __init__(self, message, code="JOBADDER_CONTACT_INPUT", status=400):
        super().__init__(message)
        self.code, self.status = code, status


class JobAdderContactService:
    """Reviewed company-contact creation; protected markers precede POST.

    No candidate writes, duplicate overrides, outreach or ambiguous replay.
    All account/transport/storage dependencies resolve through injected callbacks.
    """
    def __init__(self, *, client, account, contact, load, save, clock=time.time):
        self.client, self.account, self.contact = client, account, contact
        self.load, self.save, self.clock = load, save, clock
        self.lock = threading.Lock()

    def _store(self):
        try:
            data = self.load()
            if not data:
                return {"version":1, "operations":{}}
            if data.get("version") != 1 or not isinstance(data.get("operations"), dict):
                raise ValueError()
            if len(data["operations"]) > 5000:
                raise ValueError()
            for key, entry in data["operations"].items():
                if not re.fullmatch(r"[a-f0-9]{64}", key) or not isinstance(entry, dict) or entry.get("state") not in {"review", "pending", "unconfirmed", "rejected", "created", "exists"}:
                    raise ValueError()
            return data
        except Exception:
            raise JobAdderContactError("JobAdder contact history could not be read securely. No contact was created.", "JOBADDER_CONTACT_STORAGE", 503) from None

    def _write(self, value):
        try:
            self.save(value)
        except Exception:
            raise JobAdderContactError("The contact result could not be saved securely. Check JobAdder before trying again.", "JOBADDER_CONTACT_STORAGE", 503) from None

    @staticmethod
    def _text(value, name, limit, required=False):
        if not isinstance(value, str) or len(value) > limit or any(ord(c)<32 or ord(c)==127 for c in value) or (required and not value.strip()):
            raise JobAdderContactError("Check the " + name + ".")
        return value.strip()

    @staticmethod
    def _id(value):
        if type(value) is not int or not 0 < value <= 2147483647:
            raise JobAdderContactError("Choose a JobAdder company from the search results.")
        return value

    def _request(self, path, token, **kwargs):
        try:
            return self.client().request_json(path, token=token, timeout=15, fallback=None, **kwargs)
        except urllib.error.HTTPError as exc:
            status = exc.code
            exc.close()
            if status in {401,403}:
                raise JobAdderContactError("Your JobAdder connection cannot access company contacts. Check its permissions or reconnect.", "JOBADDER_CONTACT_AUTH", 403) from None
            raise JobAdderContactError("JobAdder could not complete this check. Try again later.", "JOBADDER_CONTACT_SERVICE", 502) from None
        except Exception:
            raise JobAdderContactError("JobAdder did not confirm this check. No contact was created.", "JOBADDER_CONTACT_NETWORK", 502) from None

    def _duplicates(self, email, token):
        _, data = self._request("contacts", token, params={"Email":email,"Limit":100})
        if not isinstance(data, dict) or not isinstance(data.get("items"), list) or type(data.get("totalCount")) is not int or data["totalCount"] < len(data["items"]):
            raise JobAdderContactError("JobAdder did not confirm the duplicate check. No contact was created.", "JOBADDER_CONTACT_CHECK", 502)
        if data["totalCount"] > len(data["items"]):
            raise JobAdderContactError("Too many matching contacts were returned. Check this email in JobAdder before creating a contact.", "JOBADDER_CONTACT_CHECK", 409)
        matches = []
        for row in data["items"]:
            if not isinstance(row, dict) or not isinstance(row.get("email"),str) or not row["email"].strip():
                raise JobAdderContactError("JobAdder returned an incomplete duplicate check.", "JOBADDER_CONTACT_CHECK", 502)
            if str(row.get("email") or "").strip().lower() == email.lower():
                identity = row.get("contactId")
                if type(identity) is not int or identity <= 0:
                    raise JobAdderContactError("JobAdder returned an incomplete contact.", "JOBADDER_CONTACT_CHECK", 502)
                company = row.get("company") or {}
                if not isinstance(company,dict):
                    raise JobAdderContactError("JobAdder returned an incomplete company.", "JOBADDER_CONTACT_CHECK", 502)
                matches.append({"contact_id":identity, "company":str(company.get("name") or "")[:200], "company_id":company.get("companyId")})
        return matches

    def perform(self, body, token):
        if not self.lock.acquire(blocking=False):
            raise JobAdderContactError("Finish the current JobAdder contact action first.", "JOBADDER_CONTACT_BUSY", 409)
        try:
            info = self.account()
            scope = info.get("account_cache_namespace", "")
            if not token or not info.get("connected") or not scope:
                raise JobAdderContactError("Connect JobAdder in Settings first.", "JOBADDER_CONTACT_AUTH", 401)
            action = body.get("action")
            if action not in {"companies", "review", "create", "check"}:
                raise JobAdderContactError("Choose a supported contact action.")
            if action == "companies":
                query = self._text(body.get("query"), "company name", 200, True)
                _, data = self._request("companies", token, params={"Name":query,"Limit":50})
                if not isinstance(data, dict) or not isinstance(data.get("items"), list) or type(data.get("totalCount")) is not int or data["totalCount"] < len(data["items"]):
                    raise JobAdderContactError("JobAdder did not return company results.", "JOBADDER_CONTACT_SERVICE", 502)
                rows = []
                for row in data["items"][:50]:
                    if isinstance(row, dict) and type(row.get("companyId")) is int and row["companyId"]>0 and isinstance(row.get("name"), str):
                        rows.append({"id":row["companyId"], "name":row["name"][:200]})
                return {"account":scope, "companies":rows, "more":data.get("totalCount",0)>len(rows)}
            if body.get("account") != scope:
                raise JobAdderContactError("The JobAdder account changed. Search for the company again.", "JOBADDER_CONTACT_ACCOUNT", 409)
            source = self.contact(body.get("contact_key"))
            company_id = self._id(body.get("company_id"))
            email = self._text(source.get("email"), "email address", 100, True)
            if not _JOBADDER_EMAIL_RE.fullmatch(email):
                raise JobAdderContactError("Check the unlocked email address.")
            first = self._text(body.get("first_name", ""), "first name", 50)
            last = self._text(body.get("last_name", ""), "last name", 50)
            if not first and not last:
                raise JobAdderContactError("Enter the contact's name.")
            position = self._text(body.get("position", ""), "position", 500)
            payload = {"firstName":first,"lastName":last,"email":email,"position":position,"companyId":company_id}
            profile = source.get("profile_url", "")
            if re.fullmatch(r"https://www\.linkedin\.com/in/[A-Za-z0-9_%~-]+/?", profile):
                payload["social"] = {"linkedin":profile}
            encoded = json.dumps(payload,sort_keys=True,separators=(",",":")).encode()
            fingerprint = hashlib.sha256(encoded).hexdigest()
            key = hashlib.sha256(json.dumps([scope,email.lower(),company_id]).encode()).hexdigest()
            store = self._store()
            previous = store["operations"].get(key)
            if previous and previous["state"] in {"created","exists"}:
                return {"state":previous["state"],"contact_id":previous.get("contact_id"),"message":"This contact is already in JobAdder."}
            if previous and previous["state"] in {"pending","unconfirmed"}:
                matches = self._duplicates(email,token)
                exact = next((row for row in matches if row["company_id"]==company_id),None)
                if exact:
                    previous.update(state="created",contact_id=exact["contact_id"]);self._write(store)
                    return {"state":"created",**exact,"message":"Contact confirmed in JobAdder. No request was repeated."}
                return {"state":"unconfirmed","message":"JobAdder has not confirmed the previous create request. Check JobAdder; this request will not be repeated."}
            if action == "check":
                return {"state":"not_started","message":"No previous create request exists. Review the details first."}
            if action == "review":
                _, company = self._request("companies/"+str(company_id),token)
                if not isinstance(company, dict) or type(company.get("companyId")) is not int or company["companyId"] != company_id or not isinstance(company.get("name"),str) or not company["name"].strip():
                    raise JobAdderContactError("This company could not be confirmed. Search again.", "JOBADDER_CONTACT_COMPANY", 409)
                matches = self._duplicates(email,token)
                if matches:
                    return {"state":"exists","matches":matches,"message":"A JobAdder contact already uses this email. No new record was created."}
                if key not in store["operations"] and len(store["operations"]) >= 5000:
                    raise JobAdderContactError("Local contact-create history is full. No contact was created.", "JOBADDER_CONTACT_LIMIT", 409)
                nonce = secrets.token_hex(32)
                store["operations"][key] = {"state":"review","payload":fingerprint,"proof":hashlib.sha256(nonce.encode()).hexdigest(),"expires":self.clock()+600}
                self._write(store)
                return {"state":"review","review_token":nonce,"company":str(company["name"])[:200],"message":"Review these details, then choose Create contact."}
            if body.get("confirmed") is not True or not previous or previous["state"] != "review" or previous.get("payload") != fingerprint or previous.get("expires",0) <= self.clock() or not secrets.compare_digest(previous.get("proof", ""),hashlib.sha256(str(body.get("review_token", "")).encode()).hexdigest()):
                raise JobAdderContactError("The review changed or expired. Review the details again before creating.", "JOBADDER_CONTACT_REVIEW", 409)
            # Repeat only the safe read immediately before the one unsafe write.
            matches = self._duplicates(email,token)
            if matches:
                previous.update(state="exists",contact_id=matches[0]["contact_id"]);self._write(store)
                return {"state":"exists","matches":matches,"message":"This email already exists in JobAdder. No new record was created."}
            previous.update(state="pending");self._write(store)
            try:
                status, result = self.client().request_json("contacts",method="POST",body=encoded,
                    headers={"Content-Type":"application/json"},token=token,timeout=20,
                    safe_to_retry=False,retries=0,refresh_on_401=False,fallback=None)
                identity = result.get("contactId") if isinstance(result,dict) else None
                if status==201 and type(identity) is int and identity>0:
                    previous.update(state="created",contact_id=identity)
                else:
                    previous.update(state="unconfirmed")
            except urllib.error.HTTPError as exc:
                status=exc.code;exc.close()
                previous.update(state="rejected" if status in {400,401,403,422} else "unconfirmed")
            except Exception:
                previous.update(state="unconfirmed")
            self._write(store)
            state=previous["state"]
            return {"state":state,"contact_id":previous.get("contact_id"),"message":{
                "created":"Contact created in JobAdder.",
                "rejected":"JobAdder rejected the details or permissions. Check the required contact fields and connection before reviewing again.",
                "unconfirmed":"JobAdder did not confirm the result. Check the previous request; it will not be repeated."}[state]}
        finally:
            self.lock.release()


_JOBADDER_EMAIL_RE = re.compile(
    r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,63}", re.IGNORECASE
)
_JOBADDER_PHONE_RE = re.compile(r"\+?\d[\d\s().\-]{6,22}\d")
_JOBADDER_PHONE_LABEL_RE = re.compile(
    r"^(?:phone|mobile|contact|tel|telephone|handphone)\s*[:\-]?\s*",
    re.IGNORECASE,
)


def _jobadder_email_value(value: Any) -> str:
    """Return one valid JobAdder email from common AI/API field shapes."""
    if isinstance(value, list):
        value = value[0] if value else ""
    if isinstance(value, dict):
        value = value.get("address") or value.get("email") or ""
    match = _JOBADDER_EMAIL_RE.search(str(value or "").strip())
    if not match:
        return ""
    email = match.group(0).lower()
    return email if len(email) <= 254 else ""


def _jobadder_phone_value(value: Any) -> str:
    """Keep one plausible optional phone and discard AI-concatenated prose."""
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    if isinstance(value, dict):
        value = value.get("number") or value.get("value") or ""
    raw = " ".join(str(value or "").split()).strip()
    candidates = [raw] + _JOBADDER_PHONE_RE.findall(raw)
    for candidate in candidates:
        cleaned = _JOBADDER_PHONE_LABEL_RE.sub("", candidate).strip()
        if not re.fullmatch(r"\+?[\d().\-\s]+", cleaned):
            continue
        digits = re.sub(r"\D", "", cleaned)
        if not 8 <= len(digits) <= 15:
            continue
        if re.fullmatch(r"(?:19|20)\d{6,}", digits):
            continue
        if len(cleaned) <= 50:
            return cleaned
    return ""


def _jobadder_error_summary(raw_detail: Any) -> str:
    """Extract JobAdder's readable validation reasons from an HTTP body."""
    detail = str(raw_detail or "").strip()
    if not detail:
        return "JobAdder rejected the candidate data without an explanation."
    try:
        payload = json.loads(detail)
    except (TypeError, ValueError):
        return detail[:1200]
    messages = []
    if isinstance(payload, dict):
        for key in ("message", "error", "detail", "title"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                messages.append(value.strip())
        errors = payload.get("errors")
        if isinstance(errors, list):
            for item in errors:
                if isinstance(item, dict):
                    message = str(item.get("message") or "").strip()
                    fields = item.get("fields")
                    if message and isinstance(fields, list) and fields:
                        message += " ({}).".format(", ".join(map(str, fields)))
                    if message:
                        messages.append(message)
                elif str(item or "").strip():
                    messages.append(str(item).strip())
        elif isinstance(errors, dict):
            for value in errors.values():
                if isinstance(value, list):
                    messages.extend(str(item).strip() for item in value if str(item).strip())
                elif str(value or "").strip():
                    messages.append(str(value).strip())
    if not messages:
        return detail[:1200]
    return " ".join(dict.fromkeys(messages))[:1200]


def _sanitize_jobadder_candidate_contacts(data: dict[str, Any]):
    """Normalize contacts before a create/update can reach JobAdder."""
    if "email" in data:
        email = _jobadder_email_value(data.get("email"))
        if not email and str(data.get("email") or "").strip():
            return "Email is not in a valid format. Enter one email address."
        data["email"] = email
    for key in ("phone", "mobile"):
        if key in data:
            phone = _jobadder_phone_value(data.get(key))
            if phone:
                data[key] = phone
            else:
                data.pop(key, None)
    return ""


class JobAdderWriteService:
    """Explicitly wired handlers behind the JSON candidate-write endpoints."""

    def __init__(
        self,
        *,
        jsonify: Callable[[Any], Any],
        request_json: Callable[[], Any],
        refresh_token: Callable[..., Any],
        client: Callable[[], Any],
    ):
        self._jsonify = jsonify
        self._request_json = request_json
        self._refresh_token = refresh_token
        self._client = client

    def create_candidate(self):
        """Server-side proxy: create a new candidate."""
        token = self._refresh_token(force=False)
        if not token:
            return self._jsonify({"error": "Not authenticated"}), 401
        data = self._request_json() or {}
        if not data:
            return self._jsonify({"error": "Invalid or empty JSON body"}), 400
        contact_error = _sanitize_jobadder_candidate_contacts(data)
        if contact_error:
            return self._jsonify({"error": contact_error}), 400
        try:
            # Build payload — keep non-empty values (dicts/lists are kept if non-empty)
            payload = {}
            for k, v in data.items():
                if v is None or v == "" or v == [] or v == {}: continue
                # For nested dicts, also strip if all values are empty
                if isinstance(v, dict) and all(not vv for vv in v.values()): continue
                payload[k] = v
            body = json.dumps(payload).encode()
            print(f"[JA Create] payload keys: {list(payload.keys())}", file=sys.stderr)
            _status, result = self._client().request_json(
                "candidates",
                method="POST",
                body=body,
                headers={"Content-Type": "application/json"},
                token=token,
                timeout=15,
                fallback={},
                safe_to_retry=False,
                retries=0,
            )
            return self._jsonify(result)
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            return self._jsonify({
                "error": f"JobAdder error: {e.code}",
                "detail": body,
                "jobadder_message": _jobadder_error_summary(body),
            }), e.code
        except Exception as e:
            return self._jsonify({"error": str(e)}), 500

    def update_candidate(self):
        """Update existing candidate profile fields via PUT /candidates/{id}."""
        token = self._refresh_token(force=False)
        if not token:
            return self._jsonify({"error": "Not authenticated"}), 401
        data = self._request_json() or {}
        if not data:
            return self._jsonify({"error": "Invalid or empty JSON body"}), 400
        candidate_id = data.pop("candidateId", "")
        if not candidate_id:
            return self._jsonify({"error": "Missing candidateId"}), 400
        contact_error = _sanitize_jobadder_candidate_contacts(data)
        if contact_error:
            return self._jsonify({"error": contact_error}), 400
        try:
            payload = {k: v for k, v in data.items() if v not in (None, "", [], {})}
            body = json.dumps(payload).encode()
            _status, result = self._client().request_json(
                "candidates/{}".format(candidate_id),
                method="PUT",
                body=body,
                headers={"Content-Type": "application/json"},
                token=token,
                timeout=15,
                fallback={},
                safe_to_retry=False,
                retries=0,
            )
            return self._jsonify(result)
        except urllib.error.HTTPError as e:
            body_err = e.read().decode()
            return self._jsonify({
                "error": "JobAdder error: {}".format(e.code),
                "detail": body_err,
                "jobadder_message": _jobadder_error_summary(body_err),
            }), e.code
        except Exception as e:
            return self._jsonify({"error": str(e)}), 500
