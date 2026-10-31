"""Signed JobAdder clients for Job Leads. JobAdder is read, never written.

The owner chooses which JobAdder company statuses mean "signed client" and
follows a few of those companies. Their LinkedIn company pages let Job Leads
pull the clients' public job ads for review. The status choice and the follow
list are kept per JobAdder user in a protected vault, so another account never
sees them and signing in again restores them. All transport, account and
storage dependencies resolve through injected callbacks; this module never
imports the application.
"""
from __future__ import annotations

import hashlib
import re
import threading
import time
import urllib.error
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit


MAX_ACCOUNTS = 20
MAX_CONNECTIONS = 100
ACTIONS = {"overview", "statuses", "set_statuses", "companies", "follow", "unfollow", "set_linkedin", "pulled"}
MAX_FOLLOWED = 200
MAX_STATUSES = 50
PAGE_SIZE = 50
MAX_OFFSET = 100_000
_SCOPE_RE = re.compile(r"[a-f0-9]{64}")
_LINKEDIN_ID_RE = re.compile(r"[0-9]{1,24}")
_STAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00")


class JobAdderClientsError(Exception):
    def __init__(self, message, code="JOBADDER_CLIENTS_INPUT", status=400):
        super().__init__(message)
        self.code, self.status = code, status


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _text(value, limit):
    return re.sub(r"\s+", " ", value).strip()[:limit] if isinstance(value, str) else ""


def _id(value, message="Choose a JobAdder company from the list."):
    if type(value) is not int or not 0 < value <= 2147483647:
        raise JobAdderClientsError(message)
    return value


def linkedin_link(value):
    """(company page, numeric company id) from a LinkedIn link, or ('', '').

    Accepts a company page (any sub-page, numeric or named) or a LinkedIn Jobs
    search that is filtered to exactly one company (``f_C``), which is what a
    company page's "See all jobs" link opens. Anything else is rejected.
    """
    if not isinstance(value, str) or len(value) > 2048:
        return "", ""
    try:
        parts = urlsplit(value.strip())
        host = (parts.hostname or "").lower()
        # A malformed port raises here; it is not a LinkedIn page either way.
        if (parts.scheme not in {"http", "https"} or parts.username or parts.password or parts.port is not None
                or not re.fullmatch(r"(?:www\.|[a-z]{2}\.)?linkedin\.com", host)):
            return "", ""
    except ValueError:
        return "", ""
    company = re.fullmatch(r"/company/([A-Za-z0-9_-]{1,100})(?:/[A-Za-z0-9_/-]*)?", parts.path)
    if company:
        handle = company.group(1)
        return "https://www.linkedin.com/company/" + handle + "/", handle if _LINKEDIN_ID_RE.fullmatch(handle) else ""
    if re.fullmatch(r"/jobs/search(?:-results)?/?", parts.path):
        ids = parse_qs(parts.query).get("f_C", [])
        if len(ids) == 1 and _LINKEDIN_ID_RE.fullmatch(ids[0]):
            return "", ids[0]
    return "", ""


class JobAdderClientsService:
    """Explicitly wired actions behind ``/jobadder/clients``."""

    def __init__(self, *, client, account, load, save, web_base, clock=time.time):
        self.client, self.account, self.load, self.save = client, account, load, save
        self.web_base, self.clock = web_base, clock
        self.lock = threading.Lock()

    # Storage ---------------------------------------------------------------

    def _store(self):
        try:
            data = self.load()
            if not data:
                return {"version": 1, "accounts": {}, "connections": {}}
            accounts = data.get("accounts")
            data.setdefault("connections", {})
            connections = data["connections"]
            if (data.get("version") != 1 or not isinstance(accounts, dict) or len(accounts) > MAX_ACCOUNTS or
                    not isinstance(connections, dict) or len(connections) > MAX_CONNECTIONS or
                    any(not isinstance(key, str) or not isinstance(value, str) or not _SCOPE_RE.fullmatch(key) or not _SCOPE_RE.fullmatch(value)
                        for key, value in connections.items())):
                raise ValueError()
            for scope, entry in accounts.items():
                if not _SCOPE_RE.fullmatch(scope) or not isinstance(entry, dict):
                    raise ValueError()
                statuses, followed = entry.get("statuses"), entry.get("followed")
                if (not isinstance(statuses, list) or len(statuses) > MAX_STATUSES or
                        any(type(value) is not int or value <= 0 for value in statuses) or
                        not isinstance(followed, dict) or len(followed) > MAX_FOLLOWED or
                        not isinstance(entry.get("updated"), (int, float))):
                    raise ValueError()
                for key, row in followed.items():
                    if (not re.fullmatch(r"[1-9][0-9]{0,9}", key) or not isinstance(row, dict) or
                            not isinstance(row.get("name"), str) or not row["name"] or len(row["name"]) > 200 or
                            not isinstance(row.get("linkedin_url"), str) or linkedin_link(row["linkedin_url"])[0] != row["linkedin_url"] or
                            not isinstance(row.get("linkedin_id"), str) or not (row["linkedin_id"] == "" or _LINKEDIN_ID_RE.fullmatch(row["linkedin_id"])) or
                            not _STAMP_RE.fullmatch(str(row.get("followed_at"))) or
                            not (row.get("pulled_at") == "" or _STAMP_RE.fullmatch(str(row.get("pulled_at"))))):
                        raise ValueError()
            return data
        except Exception:
            raise JobAdderClientsError("Saved client choices could not be read securely. Keep the existing files and check local storage.",
                                       "JOBADDER_CLIENTS_STORAGE", 503) from None

    def _write(self, data):
        try:
            self.save(data)
        except Exception:
            raise JobAdderClientsError("Your client choices could not be saved securely. Nothing was changed in JobAdder.",
                                       "JOBADDER_CLIENTS_STORAGE", 503) from None

    @staticmethod
    def _entry(data, identity):
        entry = data["accounts"].get(identity)
        return entry if entry else {"statuses": [], "followed": {}, "updated": 0}

    def _put(self, data, identity, entry):
        entry["updated"] = self.clock()
        data["accounts"][identity] = entry
        while len(data["accounts"]) > MAX_ACCOUNTS:
            oldest = min((key for key in data["accounts"] if key != identity), key=lambda key: data["accounts"][key]["updated"])
            del data["accounts"][oldest]
        self._write(data)

    def _identity(self, data, scope, api_url, token):
        """A stable key for the signed-in JobAdder user and account.

        Every completed JobAdder sign-in gets a new random connection scope, so
        choices cannot be keyed by it. The first request of a connection reads
        the current user once and remembers which key that connection maps to;
        later requests, including offline ones, use the remembered key.
        """
        known = data["connections"].get(scope)
        if known:
            return known
        who = self._request("users/current", self._token(token))
        user_id = who.get("userId") if isinstance(who, dict) else None
        if type(user_id) is not int or user_id <= 0:
            raise JobAdderClientsError("JobAdder did not confirm the signed-in user. Reconnect JobAdder and try again.",
                                       "JOBADDER_CLIENTS_SERVICE", 502)
        material = "|".join(["cvstudio-jobadder-clients-v1", str(api_url or "").strip().lower(),
                             _text(who.get("accountName"), 200).casefold(), str(user_id)])
        identity = hashlib.sha256(material.encode("utf-8")).hexdigest()
        connections = data["connections"]
        connections[scope] = identity
        while len(connections) > MAX_CONNECTIONS:
            del connections[next(iter(connections))]
        self._write(data)
        return identity

    # JobAdder reads --------------------------------------------------------

    def _request(self, path, token, params=None):
        try:
            _status, data = self.client().request_json(path, token=token, timeout=20, fallback=None, params=params)
            return data
        except urllib.error.HTTPError as exc:
            status = exc.code
            try:
                exc.close()
            except Exception:
                pass  # cleanup-only: a close failure must not hide the JobAdder status.
            if status in {401, 403}:
                raise JobAdderClientsError("Your JobAdder connection cannot read companies or the signed-in user. Reconnect JobAdder in Settings.",
                                           "JOBADDER_CLIENTS_AUTH", 403) from None
            if status == 404:
                raise JobAdderClientsError("This company is no longer in JobAdder. Refresh the client list.",
                                           "JOBADDER_CLIENTS_MISSING", 404) from None
            if status == 429:
                raise JobAdderClientsError("JobAdder is limiting requests. Wait a moment and try again.",
                                           "JOBADDER_CLIENTS_LIMITED", 429) from None
            raise JobAdderClientsError("JobAdder could not list companies (HTTP {}). Try again later.".format(status),
                                       "JOBADDER_CLIENTS_SERVICE", 502) from None
        except Exception:
            raise JobAdderClientsError("JobAdder could not be reached. Check the connection and try again.",
                                       "JOBADDER_CLIENTS_NETWORK", 502) from None

    def _statuses(self, token):
        data = self._request("companies/lists/status", token)
        items = data.get("items") if isinstance(data, dict) else data
        if not isinstance(items, list) or len(items) > 500:
            raise JobAdderClientsError("JobAdder did not return its company statuses.", "JOBADDER_CLIENTS_SERVICE", 502)
        rows, seen = [], set()
        for item in items:
            status_id = item.get("statusId") if isinstance(item, dict) else None
            name = _text(item.get("name"), 100) if isinstance(item, dict) else ""
            if type(status_id) is not int or status_id <= 0 or status_id in seen or not name:
                raise JobAdderClientsError("JobAdder returned an incomplete status list.", "JOBADDER_CLIENTS_SERVICE", 502)
            seen.add(status_id)
            rows.append({"id": status_id, "name": name, "active": item.get("active") is not False})
        return rows

    # Projection ------------------------------------------------------------

    def _followed(self, entry):
        base = self.web_base()
        rows = [{"company_id": int(key), "name": row["name"], "linkedin_url": row["linkedin_url"],
                 "linkedin_id": row["linkedin_id"], "followed_at": row["followed_at"], "pulled_at": row["pulled_at"],
                 "jobadder_url": base + "/companies/" + key}
                for key, row in entry["followed"].items()]
        return sorted(rows, key=lambda row: (row["name"].casefold(), row["company_id"]))

    # Actions ---------------------------------------------------------------

    def perform(self, body, token):
        if not isinstance(body, dict):
            raise JobAdderClientsError("Choose a valid client action.")
        info = self.account()
        scope = info.get("account_cache_namespace", "") if isinstance(info, dict) else ""
        if not isinstance(info, dict) or not info.get("connected") or not isinstance(scope, str) or not _SCOPE_RE.fullmatch(scope):
            raise JobAdderClientsError("Connect JobAdder in Settings first.", "JOBADDER_CLIENTS_AUTH", 401)
        action = body.get("action")
        if not isinstance(action, str) or action not in ACTIONS:
            raise JobAdderClientsError("Choose a supported client action.")
        if action not in {"overview", "statuses", "companies"} and body.get("account") != scope:
            # A page opened under an earlier JobAdder account must not change
            # this account's choices.
            raise JobAdderClientsError("The JobAdder account changed. Refresh the Signed clients view.", "JOBADDER_CLIENTS_ACCOUNT", 409)
        if not self.lock.acquire(timeout=10):
            raise JobAdderClientsError("Finish the current client action first.", "JOBADDER_CLIENTS_BUSY", 409)
        try:
            return self._perform(action, body, token, scope, str(info.get("api_url") or ""))
        finally:
            self.lock.release()

    def _token(self, token):
        try:
            value = token()
        except Exception:
            raise JobAdderClientsError("JobAdder could not be reached to refresh the sign-in. Check the internet connection.",
                                       "JOBADDER_CLIENTS_NETWORK", 503) from None
        if not value:
            raise JobAdderClientsError("Connect JobAdder in Settings first.", "JOBADDER_CLIENTS_AUTH", 401)
        return value

    def _perform(self, action, body, token, scope, api_url):
        data = self._store()
        identity = self._identity(data, scope, api_url, token)
        entry = self._entry(data, identity)
        if action == "overview":
            # Local once this connection's user is known: the follow list
            # stays usable while JobAdder is unreachable.
            return {"account": scope, "signed": list(entry["statuses"]), "followed": self._followed(entry)}
        if action == "statuses":
            return {"account": scope, "statuses": self._statuses(self._token(token)), "signed": list(entry["statuses"])}
        if action == "set_statuses":
            chosen = body.get("status_ids")
            if (not isinstance(chosen, list) or len(chosen) > MAX_STATUSES or
                    any(type(value) is not int or value <= 0 for value in chosen) or len(set(chosen)) != len(chosen)):
                raise JobAdderClientsError("Choose up to 50 JobAdder statuses.")
            known = {row["id"] for row in self._statuses(self._token(token))}
            if not set(chosen) <= known:
                raise JobAdderClientsError("A chosen status is no longer in JobAdder. Refresh the statuses and choose again.",
                                           "JOBADDER_CLIENTS_STALE", 409)
            entry = {**entry, "statuses": sorted(chosen)}
            self._put(data, identity, entry)
            return {"account": scope, "signed": entry["statuses"]}
        if action == "companies":
            return self._companies(body, self._token(token), scope, entry)
        if action == "follow":
            return self._follow(body, self._token(token), data, scope, identity, entry)
        company_id = _id(body.get("company_id"), "Choose a followed client.")
        key = str(company_id)
        if action == "unfollow":
            followed = dict(entry["followed"])
            if followed.pop(key, None) is not None:
                self._put(data, identity, {**entry, "followed": followed})
            return {"account": scope, "followed": self._followed({**entry, "followed": followed})}
        if key not in entry["followed"]:
            raise JobAdderClientsError("Follow this client first.", "JOBADDER_CLIENTS_MISSING", 404)
        row = dict(entry["followed"][key])
        if action == "set_linkedin":
            link = body.get("link", "")
            if not isinstance(link, str) or len(link) > 2048:
                raise JobAdderClientsError("Paste the client's LinkedIn company page.")
            if link.strip():
                url, number = linkedin_link(link)
                if not url and not number:
                    raise JobAdderClientsError("Paste the client's LinkedIn company page, or the link of its 'See all jobs' search.")
                if url:
                    row["linkedin_url"] = url
                    row["linkedin_id"] = number
                else:
                    row["linkedin_id"] = number
            else:
                row["linkedin_url"], row["linkedin_id"] = "", ""
        else:  # pulled
            row["pulled_at"] = _now()
        followed = {**entry["followed"], key: row}
        self._put(data, identity, {**entry, "followed": followed})
        return {"account": scope, "followed": self._followed({**entry, "followed": followed})}

    def _companies(self, body, token, scope, entry):
        if not entry["statuses"]:
            raise JobAdderClientsError("Choose which JobAdder statuses mean a signed client first.", "JOBADDER_CLIENTS_SETUP", 409)
        offset, query = body.get("offset", 0), body.get("query", "")
        if type(offset) is not int or not 0 <= offset <= MAX_OFFSET:
            raise JobAdderClientsError("The client list page is out of range.")
        if not isinstance(query, str) or len(query) > 200 or any(ord(c) < 32 for c in query):
            raise JobAdderClientsError("Use a shorter client search.")
        params = {"StatusId": list(entry["statuses"]), "Offset": offset, "Limit": PAGE_SIZE}
        if query.strip():
            params["Name"] = query.strip()
        data = self._request("companies", token, params)
        if not isinstance(data, dict) or not isinstance(data.get("items"), list) or len(data["items"]) > PAGE_SIZE:
            raise JobAdderClientsError("JobAdder returned an unexpected company list.", "JOBADDER_CLIENTS_SERVICE", 502)
        total = data.get("totalCount")
        total = total if type(total) is int and total >= 0 else None
        signed, base, rows = set(entry["statuses"]), self.web_base(), []
        for item in data["items"]:
            if not isinstance(item, dict) or type(item.get("companyId")) is not int or item["companyId"] <= 0:
                continue
            status = item.get("status") if isinstance(item.get("status"), dict) else {}
            # Never label a company signed unless JobAdder says its status is
            # one of the chosen ones, even if a filter were ignored upstream.
            if status.get("statusId") not in signed:
                continue
            name = _text(item.get("name"), 200)
            if not name:
                continue
            owner = item.get("owner") if isinstance(item.get("owner"), dict) else {}
            rows.append({"company_id": item["companyId"], "name": name, "status": _text(status.get("name"), 100),
                         "owner": " ".join(part for part in (_text(owner.get("firstName"), 60), _text(owner.get("lastName"), 60)) if part),
                         "followed": str(item["companyId"]) in entry["followed"],
                         "jobadder_url": base + "/companies/" + str(item["companyId"])})
        returned = len(data["items"])
        more = returned > 0 and (offset + returned < total if total is not None else returned >= PAGE_SIZE)
        return {"account": scope, "companies": rows, "offset": offset, "total": total,
                "next_offset": offset + returned if more and offset + returned <= MAX_OFFSET else None}

    def _follow(self, body, token, data, scope, identity, entry):
        company_id = _id(body.get("company_id"))
        key = str(company_id)
        if key not in entry["followed"] and len(entry["followed"]) >= MAX_FOLLOWED:
            raise JobAdderClientsError("You can follow up to 200 clients. Unfollow one first.", "JOBADDER_CLIENTS_LIMIT", 409)
        if not entry["statuses"]:
            raise JobAdderClientsError("Choose which JobAdder statuses mean a signed client first.", "JOBADDER_CLIENTS_SETUP", 409)
        company = self._request("companies/" + key, token)
        status = company.get("status") if isinstance(company, dict) and isinstance(company.get("status"), dict) else {}
        name = _text(company.get("name"), 200) if isinstance(company, dict) else ""
        if not isinstance(company, dict) or company.get("companyId") != company_id or not name:
            raise JobAdderClientsError("JobAdder returned an unexpected company.", "JOBADDER_CLIENTS_SERVICE", 502)
        if status.get("statusId") not in set(entry["statuses"]):
            raise JobAdderClientsError("This company's JobAdder status is no longer one of your signed statuses.",
                                       "JOBADDER_CLIENTS_STALE", 409)
        social = company.get("social") if isinstance(company.get("social"), dict) else {}
        url, number = linkedin_link(social.get("linkedin") or "")
        old = entry["followed"].get(key)
        if old:
            # Keep what the owner pasted unless JobAdder now gives something
            # better: a pasted company number survives while JobAdder's page
            # is the same named page (or absent), because LinkedIn needs the
            # number and a named page does not carry it.
            if not number and old["linkedin_id"] and (not url or not old["linkedin_url"] or old["linkedin_url"] == url):
                number = old["linkedin_id"]
            if not url:
                url = old["linkedin_url"]
        row = {"name": name, "linkedin_url": url, "linkedin_id": number,
               "followed_at": old["followed_at"] if old else _now(), "pulled_at": old["pulled_at"] if old else ""}
        followed = {**entry["followed"], key: row}
        self._put(data, identity, {**entry, "followed": followed})
        return {"account": scope, "followed": self._followed({**entry, "followed": followed})}
