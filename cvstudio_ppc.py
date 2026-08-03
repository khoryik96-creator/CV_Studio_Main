"""Post Placement Care (PPC) placement helpers (Phase 7B).

Behaviour-preserving extraction of the PPC placement cluster from the legacy
web shell: date/name/int normalisation, JobAdder placement-type fetching with
pagination diagnostics, placement-record normalisation, and the per-run detail
cache. These are a verbatim move of the legacy helpers.

The application keeps ownership of the JobAdder OAuth token lifecycle and the
shared ``JobAdderClient`` transport. The two network helpers here receive that
client as an explicit argument resolved at call time, so this module never
imports ``app`` and performs no write. The Flask route handler stays in the web
shell and calls these through thin app-level wrappers that bind the client.
"""

from __future__ import annotations

import threading
import urllib.error
from datetime import datetime


def _ppc_clean_date(value):
    value = str(value or "").strip()
    if not value:
        return ""
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date().isoformat()
    except Exception:
        return ""


def _ppc_person_name(value):
    if not isinstance(value, dict):
        return ""
    direct = str(value.get("name") or value.get("displayName") or "").strip()
    if direct:
        return direct
    return " ".join(x for x in [str(value.get("firstName") or "").strip(), str(value.get("lastName") or "").strip()] if x).strip()


def ppc_get_json(client, token, path, params=None, timeout=30, retry_429=True):
    try:
        _status, payload = client.request_json(
            path,
            params=params,
            token=token,
            timeout=timeout,
            fallback={},
            retries=1 if retry_429 else 0,
        )
        return payload
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        err = RuntimeError("JobAdder error {}: {}".format(exc.code, body[:500]))
        err.http_code = exc.code
        err.retry_after = exc.headers.get("Retry-After") if getattr(exc, "headers", None) else None
        raise err


_PPC_PLACEMENT_TYPES = ("Permanent", "Contract", "Temporary", "Credit")
_ppc_detail_cache = {}
_ppc_detail_cache_lock = threading.Lock()


def _ppc_detail_cache_clear():
    with _ppc_detail_cache_lock:
        _ppc_detail_cache.clear()


def _ppc_int(value, default=None):
    try:
        return int(value)
    except Exception:
        return default


def ppc_fetch_type_collection(client, get_json, token, placement_type, base_params, max_records):
    """Fetch one JobAdder placement type completely and report pagination diagnostics.

    JobAdder accepts repeated Type parameters, but querying each type separately gives
    an independent totalCount and prevents a partial type result from being mistaken
    for a complete combined collection. Limit=0 is used first as the authoritative
    count, then Offset advances by the actual number of rows returned.

    ``get_json`` is the ``(token, path, params=, timeout=, retry_429=)`` JSON
    fetcher the web shell binds to its shared client; injecting it keeps the
    count/page fetch seam patchable at the application level.
    """
    max_records = max(0, int(max_records or 0))
    params_base = list(base_params) + [("Type", placement_type)]
    count_payload = get_json(token, "placements", params=params_base + [("Offset", 0), ("Limit", 0)], timeout=35)
    expected = max(0, _ppc_int(count_payload.get("totalCount") if isinstance(count_payload, dict) else None, 0) or 0)
    page_size = min(1000, max_records) if max_records else 0
    def parse_page(payload):
        items = payload.get("items") if isinstance(payload, dict) else []
        total = _ppc_int(payload.get("totalCount") if isinstance(payload, dict) else None, None)
        return (items if isinstance(items, list) else []), total

    def fetch_page(params):
        return get_json(token, "placements", params=params, timeout=40)

    def page_signature(items, _keys):
        ids = tuple(str(x.get("placementId") or "") for x in items if isinstance(x, dict))
        return repr((len(items), ids[:5], ids[-5:]))

    rows, page_state = client.paginate_offset(
        "placements",
        params=params_base,
        token=token,
        max_items=max_records,
        page_size=max(1, page_size),
        timeout=40,
        parse_page=parse_page,
        item_key=lambda item: str((item or {}).get("placementId") or "") if isinstance(item, dict) else "",
        page_signature=page_signature,
        initial_total=expected,
        total_mode="max",
        deduplicate=False,
        retry_empty=True,
        empty_retry_delay=0.35,
        fetch_page=fetch_page,
    )
    rows = [item for item in rows if isinstance(item, dict)]
    codes = set(page_state.get("codes") or [])
    observed_total = max(expected, int(page_state.get("reported_total") or 0))
    expected = observed_total
    truncated = bool(page_state.get("truncated"))
    complete = bool(not page_state.get("incomplete") and not truncated and len(rows) >= expected)
    return rows, {
        "type": placement_type,
        "expected": expected,
        "observed_total": observed_total,
        "returned": len(rows),
        "pages": int(page_state.get("pages") or 0),
        "complete": bool(complete and not truncated),
        "truncated": bool(truncated),
        "repeated_page": "repeated_page" in codes,
        "empty_before_total": "empty_before_total" in codes,
    }


def _ppc_normalize_placement(item):
    item = item if isinstance(item, dict) else {}
    candidate = item.get("candidate") if isinstance(item.get("candidate"), dict) else {}
    job = item.get("job") if isinstance(item.get("job"), dict) else {}
    company = item.get("company") if isinstance(item.get("company"), dict) else {}
    if not company:
        company = job.get("company") if isinstance(job.get("company"), dict) else {}
    status = item.get("status") if isinstance(item.get("status"), dict) else {}
    created_by = item.get("createdBy") if isinstance(item.get("createdBy"), dict) else {}
    owner = item.get("owner") if isinstance(item.get("owner"), dict) else {}
    job_owner = job.get("owner") if isinstance(job.get("owner"), dict) else {}
    billing = item.get("billing") if isinstance(item.get("billing"), dict) else {}
    billing_contact = billing.get("contact") if isinstance(billing.get("contact"), dict) else {}
    salary = item.get("salary") if isinstance(item.get("salary"), dict) else {}
    recruiter_rows = item.get("recruiters") if isinstance(item.get("recruiters"), list) else []
    recruiter_names, recruiter_ids, recruiter_pairs = [], [], []
    for recruiter in recruiter_rows:
        if not isinstance(recruiter, dict):
            continue
        name = _ppc_person_name(recruiter)
        user_id = recruiter.get("userId")
        if name and name not in recruiter_names:
            recruiter_names.append(name)
        if user_id not in (None, "") and user_id not in recruiter_ids:
            recruiter_ids.append(user_id)
        if user_id not in (None, "") or name:
            recruiter_pairs.append({
                "user_id": user_id,
                "name": name or ("Recruiter {}".format(user_id) if user_id not in (None, "") else "Unknown recruiter"),
                "fee_split": recruiter.get("feeSplit"),
            })
    candidate_name = " ".join(x for x in [str(candidate.get("firstName") or "").strip(), str(candidate.get("lastName") or "").strip()] if x).strip()
    placement_id = item.get("placementId")
    job_id = job.get("jobId")
    company_id = company.get("companyId")
    candidate_id = candidate.get("candidateId")
    return {
        "placement_id": placement_id,
        "candidate_id": candidate_id,
        "candidate_name": candidate_name or ("Candidate {}".format(candidate_id) if candidate_id else "Unknown candidate"),
        "candidate_email": str(candidate.get("email") or "").strip(),
        "company_id": company_id,
        "company_name": str(company.get("name") or "").strip(),
        "job_id": job_id,
        "job_title": str(item.get("jobTitle") or job.get("jobTitle") or "").strip(),
        "type": str(item.get("type") or "").strip(),
        "status_id": status.get("statusId"),
        "status_name": str(status.get("name") or "").strip(),
        "start_date": str(item.get("startDate") or "")[:10],
        "end_date": str(item.get("endDate") or "")[:10],
        "approved": bool(item.get("approved")),
        "approved_at": str(item.get("approvedAt") or ""),
        "created_by_id": created_by.get("userId"),
        "created_by": _ppc_person_name(created_by),
        "recruiter_ids": recruiter_ids,
        "recruiters": recruiter_names,
        "recruiter_pairs": recruiter_pairs,
        # "Placed by" is deliberately sourced only from Placement.recruiters.
        # createdBy, placement owner and job owner are different concepts and
        # must never make the recruiter filter return another recruiter's rows.
        "placed_by_id": recruiter_ids[0] if len(recruiter_ids) == 1 else None,
        "placed_by": ", ".join(recruiter_names),
        "placement_owner_id": owner.get("userId"),
        "placement_owner": _ppc_person_name(owner),
        "job_owner_id": job_owner.get("userId"),
        "job_owner": _ppc_person_name(job_owner),
        # Placement billing data used only to prepare an invoice-request email.
        # These values come from the read-only full placement representation.
        "billing_contact_id": billing_contact.get("contactId"),
        "billing_contact_name": _ppc_person_name(billing_contact),
        "billing_email": str(billing.get("email") or billing_contact.get("email") or "").strip(),
        "billing_payment_terms": str(billing.get("terms") or "").strip(),
        "billing_due_date": str(billing.get("dueDate") or "")[:10],
        "placement_fee": salary.get("fee"),
        "charge_currency": str(item.get("chargeCurrency") or item.get("payCurrency") or "").strip(),
        "created_at": str(item.get("createdAt") or ""),
        "updated_at": str(item.get("updatedAt") or ""),
    }
