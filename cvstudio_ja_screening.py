"""JobAdder Screening Call activity payload construction.

Behaviour-preserving extraction of the pure payload/answer builders for the
JobAdder "Candidate Screening Call" activity, moved verbatim from the legacy
web shell: OneNote screening-field cleaning, the strict 1-4 Presentability
rating parser, the standard and browser-SPA answer-array builders, the many
candidate-activity payload variants (the exhaustive answers-shape sweep used to
satisfy JobAdder's ActivityAnswerListModel binding), and the create-only SPA
browser-helper generator.

Most functions are pure functions of their inputs. The sole exception is the
SPA browser-helper generator, which needs one piece of app state - the JobAdder
candidate activity URL builder - supplied through ``bind_screening_dependencies``
rather than imported. Otherwise this module depends only on helpers already
extracted into ``cvstudio_ja_answers`` / ``cvstudio_ja_salary_ai`` /
``cvstudio_ja_salary_notice``. This module never imports ``app``.

The OneNote field helpers (``_onenote_clean_field_value`` and friends) live here
because the screening builders are their primary consumer; ``app.py`` re-exports
them so their other callers (and the ``cvstudio_ja_salary_ai`` dependency
injection) are unaffected.
"""

import json
import re
import urllib.parse

from cvstudio_ja_answers import (
    _ONENOTE_JA_PRESENTABILITY_QUESTION_IDS,
    _ONENOTE_JA_SCREENING_SETTING_ID,
    _ja_answer_is_presentability,
    _ja_answer_model_bundle,
    _ja_answer_model_qid_list_payloads_v105,
    _ja_candidate_screening_call_base_payload,
    _ja_maybe_int,
    _ja_presentability_answer,
    _ja_rating_map_answer_payloads,
    _ja_split_text_rating_answers,
)
from cvstudio_ja_salary_ai import _ja_build_salary_notice_canonical
from cvstudio_ja_salary_notice import _ja_spa_salary_update_helper_js


# The create-only SPA browser helper reports the candidate's JobAdder Activity
# URL, which is derived from the connected account's api_url. That is request
# state, so it is injected here rather than imported.
_jobadder_candidate_activity_url = None


def bind_screening_dependencies(*, jobadder_candidate_activity_url):
    """Inject the app-state helper the SPA browser-bridge generator needs."""
    global _jobadder_candidate_activity_url
    _jobadder_candidate_activity_url = jobadder_candidate_activity_url


def _onenote_clean_field_value(value, max_len=4000):
    text = re.sub(r"\r\n?", "\n", str(value or ""))
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) > max_len:
        text = text[:max_len].rstrip() + "…"
    return text


def _onenote_presentability_rating_int(fields):
    """Return a strict Presentability rating from 1 to 4, or ``None``.

    Accept the normal one-digit value, an explicit ``3/4`` / ``3 out of 4``
    score, or a labelled ``rating 3`` form.  Do not pull a stray 1-4 digit from
    values such as ``14``, ``40``, ``10/4`` or ``4 years``.
    """
    text = str((fields or {}).get("presentability_rating") or "").strip()
    if not text:
        return None
    m = re.fullmatch(
        r"(?:presentability|rating|score)?\s*[:=\-–—]?\s*([1-4])"
        r"(?:\s*(?:/\s*4|out\s+of\s+4))?"
        r"(?:\s*[-–—:]\s*[^\d].*)?",
        text,
        re.I,
    )
    if not m:
        m = re.fullmatch(r"\s*[^\d]{0,60}([1-4])\s*(?:/\s*4|out\s+of\s+4)\s*", text, re.I)
    return int(m.group(1)) if m else None


def _onenote_screening_remarks_value(fields, note_text=""):
    remarks = _onenote_clean_field_value(
        (fields or {}).get("remarks")
        or (fields or {}).get("red_flags")
        or (fields or {}).get("next_steps")
        or (fields or {}).get("raw_presentability")
        or ""
    )
    if remarks:
        return remarks
    # Keep remarks blank unless the note explicitly has a remarks-ish field.
    # Full raw note is not copied here to avoid dumping excessive text into a
    # tenant-specific field that is often meant for brief recruiter reminders.
    return ""


_ONENOTE_JA_SCREENING_QUESTIONS_BASE = [
    (41172, "Brief Overview of Experience", "brief_overview"),
    (41173, "Reason For Leaving", "reason_leaving"),
    (41174, "Looking For", "looking_for"),
    (41175, "Current Salary Breakdown", "current_salary_breakdown"),
    (41176, "Expected Salary", "expected_salary"),
    (41177, "Notice Period", "notice_period"),
    (35900, "Leads - Follow format: Active (Client - Role, Stage, Y/N)  Y denotes agency representation", "leads"),
    (41178, "Remarks and things to take note", "remarks"),
]


def _ja_screening_call_answers(fields, note_text="", presentability_question_id=None, presentability_mode="numeric"):
    fields = fields or {}
    rating = _onenote_presentability_rating_int(fields)
    values = {
        "brief_overview": _onenote_clean_field_value(fields.get("brief_overview", ""), max_len=8000),
        "reason_leaving": _onenote_clean_field_value(fields.get("reason_leaving", "")),
        "looking_for": _onenote_clean_field_value(fields.get("looking_for", "")),
        "current_salary_breakdown": _onenote_clean_field_value(fields.get("current_salary_breakdown", "")),
        "expected_salary": _onenote_clean_field_value(fields.get("expected_salary", "")),
        "notice_period": _onenote_clean_field_value(fields.get("notice_period", "")),
        "leads": _onenote_clean_field_value(fields.get("leads", "")),
        "remarks": _onenote_screening_remarks_value(fields, note_text),
    }
    answers = []
    for qid, qtext, key in _ONENOTE_JA_SCREENING_QUESTIONS_BASE:
        answers.append({
            "questionID": qid,
            "questionText": qtext,
            "textValue": values.get(key, ""),
            "startDateValue": None,
            "endDateValue": None,
            "numberValue": None,
            "numericValue": None,
            "decimalValue": None,
            "booleanValue": None,
            "singleSelectValue": None,
            "multiSelectValue": [],
        })
    answers.append(_ja_presentability_answer(
        presentability_question_id or _ONENOTE_JA_PRESENTABILITY_QUESTION_IDS[0],
        "Presentability (Confidence, Comms, Business Awareness)",
        rating or "",
        mode=presentability_mode,
    ))
    return answers


def _ja_spa_screening_call_answers(fields, note_text="", include_extended=False):
    """Return the flat answer array observed from JobAdder's SPA UI.

    v24.6.116: the user captured a successful *new* Candidate Screening Call
    create request. The SPA create route posts to
    /spa/api/candidates/{id}/activities/standardactivity and includes only the
    standard six text questions plus Presentability. Older edit requests can
    include additional Leads/Remarks questions, but sending them during create
    is less safe, so the browser-create helper defaults to the captured create
    shape.
    """
    fields = fields or {}
    rating = _onenote_presentability_rating_int(fields)
    rating = int(rating) if str(rating or "").strip().isdigit() else None
    values = {
        "brief_overview": _onenote_clean_field_value(fields.get("brief_overview", ""), max_len=8000),
        "reason_leaving": _onenote_clean_field_value(fields.get("reason_leaving", "")),
        "looking_for": _onenote_clean_field_value(fields.get("looking_for", "")),
        "current_salary_breakdown": _onenote_clean_field_value(fields.get("current_salary_breakdown", "")),
        "expected_salary": _onenote_clean_field_value(fields.get("expected_salary", "")),
        "notice_period": _onenote_clean_field_value(fields.get("notice_period", "")),
        "leads": _onenote_clean_field_value(fields.get("leads", "")),
        "remarks": _onenote_screening_remarks_value(fields, note_text),
    }
    question_rows = [
        (41172, "Brief Overview of Experience", "brief_overview"),
        (41173, "Reason For Leaving", "reason_leaving"),
        (41174, "Looking For?", "looking_for"),
        (41175, "Current Salary Breakdown", "current_salary_breakdown"),
        (41176, "Expected Salary", "expected_salary"),
        (41177, "Notice Period", "notice_period"),
    ]
    if include_extended:
        question_rows.extend([
            (35900, "Leads - Follow format: Active (Client - Role, Stage, Y/N)  Y denotes agency representation", "leads"),
            (41178, "Remarks and things to take note", "remarks"),
        ])
    answers = []
    # v24.6.116: user clarified that if Brief Overview / Summary is empty,
    # leave Brief Overview blank instead of stuffing the raw OneNote note there.
    # Other standard create fields still use N/A when absent to avoid vague
    # JobAdder 500s on empty required text fields.
    for qid, qtext, key in question_rows:
        text_value = values.get(key, "")
        if not text_value and key != "brief_overview":
            text_value = "N/A"
        answers.append({
            "questionID": qid,
            "questionText": qtext,
            "textValue": text_value,
            "startDateValue": None,
            "endDateValue": None,
            "numericValue": None,
        })
    answers.append({
        "questionID": _ONENOTE_JA_PRESENTABILITY_QUESTION_IDS[0],
        "questionText": "Presentability (Confidence, Comms, Business Awareness)",
        "textValue": str(rating or ""),
        "startDateValue": None,
        "endDateValue": None,
        "numericValue": rating,
    })
    return answers


def _ja_spa_screening_call_payload(candidate_id, fields, note_text="", activity_id=None, include_extended=False):
    """Build the JobAdder browser-SPA payload captured from manual Network requests.

    This payload is not sent by the Flask backend. It is used to generate a
    console helper script that the user runs inside their already-authenticated
    JobAdder browser tab, so cookies/tokens never need to be copied into CV Studio.
    """
    cid_value = _ja_maybe_int(candidate_id)
    payload = {
        "activityID": _ja_maybe_int(activity_id) if activity_id else 0,
        "activitySettingID": _ONENOTE_JA_SCREENING_SETTING_ID,
        "actionName": "Candidate Screening Call",
        "activityType": "Screening",
        "answers": _ja_spa_screening_call_answers(fields, note_text, include_extended=include_extended),
        "attachments": None,
        "entity": {"entityID": cid_value},
        "entityID": cid_value,
        "mentionedUserIDs": None,
        "status": None,
        "task": "",
    }
    return payload


def _ja_candidate_screening_call_payload(candidate_id, fields, note_text, reference=None, activity_id=None, answers_shape="items", presentability_question_id=None, presentability_mode="numeric"):
    cid_value = _ja_maybe_int(candidate_id)
    answers = _ja_screening_call_answers(fields, note_text, presentability_question_id=presentability_question_id, presentability_mode=presentability_mode)
    rating_required_validation = None
    if answers_shape.startswith("top_rating_"):
        rating = _onenote_presentability_rating_int(fields)
        text_answers, rating_answers, rating_by_qid = _ja_split_text_rating_answers(answers, rating)
        if answers_shape == "top_rating_items":
            answers_payload = {"items": text_answers}
        elif answers_shape == "top_rating_text_answers":
            answers_payload = {"textAnswers": text_answers, "items": text_answers}
        elif answers_shape == "top_rating_map":
            answers_payload = {str(a.get("questionID")): {"questionID": a.get("questionID"), "textValue": a.get("textValue") or ""} for a in text_answers}
        elif answers_shape == "top_rating_questions":
            answers_payload = {"questions": text_answers, "values": text_answers}
        else:
            answers_payload = {"items": text_answers}
        rating_required_validation = {"rating_answers": rating_answers, "rating_by_qid": rating_by_qid}
    elif answers_shape == "array":
        answers_payload = answers
    elif answers_shape == "map_full":
        answers_payload = {str(a.get("questionID")): dict(a) for a in answers}
    elif answers_shape == "map_text":
        answers_payload = {str(a.get("questionID")): (a.get("textValue") or "") for a in answers}
    elif answers_shape == "map_value":
        answers_payload = {}
        for a in answers:
            qid = str(a.get("questionID"))
            val = a.get("textValue")
            if not val and (a.get("ratingValue") is not None or a.get("numericValue") is not None or a.get("numberValue") is not None):
                val = a.get("ratingValue") if a.get("ratingValue") is not None else (a.get("numericValue") if a.get("numericValue") is not None else a.get("numberValue"))
            answers_payload[qid] = val if val is not None else ""
    elif answers_shape == "map_compact":
        answers_payload = {}
        for a in answers:
            qid = str(a.get("questionID"))
            if a.get("ratingValue") is not None or a.get("numericValue") is not None or a.get("numberValue") is not None:
                answers_payload[qid] = {
                    "questionID": a.get("questionID"),
                    "questionId": a.get("questionID"),
                    "ratingValue": a.get("ratingValue") if a.get("ratingValue") is not None else a.get("numericValue"),
                    "rating": a.get("rating") if a.get("rating") is not None else a.get("numericValue"),
                    "value": a.get("value") if a.get("value") is not None else a.get("numericValue"),
                    "numericValue": a.get("numericValue"),
                    "numberValue": a.get("numberValue"),
                    "textValue": a.get("textValue") or str(a.get("numericValue") or a.get("numberValue") or ""),
                }
            else:
                answers_payload[qid] = {
                    "questionID": a.get("questionID"),
                    "questionId": a.get("questionID"),
                    "textValue": a.get("textValue") or "",
                }
    elif answers_shape.startswith("rating_map_"):
        rating = _onenote_presentability_rating_int(fields)
        payloads = _ja_rating_map_answer_payloads(answers, rating)
        try:
            idx = int(answers_shape.rsplit("_", 1)[-1])
        except Exception:
            idx = 0
        answers_payload = payloads[idx] if 0 <= idx < len(payloads) else payloads[0]
    elif answers_shape in ("answer_bundle", "answer_bundle_object", "answer_bundle_pascal", "answer_bundle_maps", "answer_bundle_values"):
        rating = _onenote_presentability_rating_int(fields)
        bundle_mode = {
            "answer_bundle": "camel",
            "answer_bundle_object": "camel_object",
            "answer_bundle_pascal": "pascal",
            "answer_bundle_maps": "maps",
            "answer_bundle_values": "dollar_values",
        }.get(answers_shape, "camel")
        answers_payload = _ja_answer_model_bundle(answers, rating, bundle_mode=bundle_mode)
    else:
        wrappers = {
            "items": {"items": answers},
            "answers": {"answers": answers},
            "activityAnswers": {"activityAnswers": answers},
            "values": {"values": answers},
            "questions": {"questions": answers},
        }
        answers_payload = wrappers.get(answers_shape) or {"items": answers}
    payload = {
        "activitySettingID": _ONENOTE_JA_SCREENING_SETTING_ID,
        "actionName": "Candidate Screening Call",
        "activityType": "Screening",
        "answers": answers_payload,
        "attachments": [],
        "entity": {"entityID": cid_value},
        "entityID": cid_value,
        "mentionedUserIDs": [],
        "status": None,
        "task": None,
    }
    if rating_required_validation:
        rating_answers = rating_required_validation.get("rating_answers") or []
        rating_by_qid = rating_required_validation.get("rating_by_qid") or {}
        payload.update({
            "ratingAnswers": rating_answers,
            "ratings": rating_answers,
            "ratingQuestionAnswers": rating_answers,
            "activityRatingAnswers": rating_answers,
            "ratingValues": rating_answers,
            "ratingsByQuestionID": rating_by_qid,
            "ratingAnswersByQuestionID": rating_by_qid,
        })
    if reference:
        payload["reference"] = reference
    # Optional only: if a future diagnostic captures a required draft activityID,
    # the UI/backend can pass it without hard-coding the user's sample ID.
    if activity_id:
        payload["activityID"] = _ja_maybe_int(activity_id)
    return payload


def _ja_browser_activity_answer_list_payload_variants(candidate_id, fields, note_text, reference):
    """Build browser-observed answer-list payloads for JobAdder API.

    v24.6.116: the user's successful JobAdder SPA save shows the tenant stores
    Screening Call fields as a flat answers array. The public candidate activity
    API rejects answers as a raw array, but its .NET error reveals that inside
    ActivityAnswerListModel, textAnswers must be an IList[ActivityTextAnswerModel]
    rather than a questionID map. Try object-wrapping the exact browser answer
    models as answers.textAnswers = [ ... ], including Presentability 62988 with
    numericValue + textValue.
    """
    raw_answers = _ja_screening_call_answers(
        fields,
        note_text,
        presentability_question_id=_ONENOTE_JA_PRESENTABILITY_QUESTION_IDS[0],
        presentability_mode="number",
    )
    rating_int = _onenote_presentability_rating_int(fields)
    answer_list = []
    text_list = []
    rating_list = []
    for a in raw_answers:
        qid = a.get("questionID") or a.get("questionId")
        if not qid:
            continue
        qid_int = _ja_maybe_int(qid)
        is_rating = _ja_answer_is_presentability(a)
        model = {
            "questionID": qid_int,
            "questionText": a.get("questionText") or ("Presentability (Confidence, Comms, Business Awareness)" if is_rating else ""),
            "textValue": str(rating_int) if is_rating else (a.get("textValue") or ""),
            "numericValue": rating_int if is_rating else None,
            "startDateValue": None,
            "endDateValue": None,
        }
        answer_list.append(dict(model))
        if is_rating:
            rating_list.append(dict(model))
        else:
            text_list.append(dict(model))

    answers_payloads = [
        {"textAnswers": answer_list},
        {"textAnswers": text_list, "ratingAnswers": rating_list},
        {"activityTextAnswers": answer_list},
        {"activityAnswers": answer_list},
        {"questionAnswers": answer_list},
        {"items": answer_list},
        {"answers": answer_list},
        {"values": answer_list},
        {"TextAnswers": answer_list},
        {"TextAnswers": text_list, "RatingAnswers": rating_list},
        {"ActivityAnswers": answer_list},
        {"Items": answer_list},
    ]
    variants = []
    for answers_payload in answers_payloads:
        payload = _ja_candidate_screening_call_base_payload(candidate_id, reference=reference)
        payload["answers"] = answers_payload
        variants.append(payload)
    return variants


def _ja_precise_qid_activity_payload_variants(candidate_id, fields, note_text, reference):
    """Build precise v105 JobAdder answer-map attempts before older guesses."""
    answers = _ja_screening_call_answers(
        fields,
        note_text,
        presentability_question_id=_ONENOTE_JA_PRESENTABILITY_QUESTION_IDS[0],
        presentability_mode="number",
    )
    rating = _onenote_presentability_rating_int(fields)
    variants = []
    for answers_payload in _ja_answer_model_qid_list_payloads_v105(answers, rating):
        payload = _ja_candidate_screening_call_base_payload(candidate_id, reference=reference)
        payload["answers"] = answers_payload
        variants.append(payload)
    return variants


def _ja_activity_payload_variants(candidate_id, activity_type, subject, note_text, fields, reference, now_utc):
    """Build JobAdder candidate activity payload variants.

    v24.6.97: Live diagnostics show candidates/{id}/activities is the
    reachable endpoint, but it rejects answers[] and expects an answers object
    (ActivityAnswerListModel). Therefore the first variants use exact tenant
    IDs with answers wrapped as objects. Browser-like answers[] remains last
    only for diagnostics.
    """
    cid = str(candidate_id or "")
    exact_variants = []
    # v24.6.116: Presentability is a mandatory 1-4 button/rating in JobAdder,
    # not a free-text field.  Try rating/numeric/select payloads before the
    # older text-style fallback.  Keep the attempt list short enough to avoid
    # slow transfers/timeouts.
    # Keep attempts limited: the user's captured browser payload confirms
    # Presentability questionID 62988, while 52988 is only a historical fallback.
    primary_presentability_qid = _ONENOTE_JA_PRESENTABILITY_QUESTION_IDS[0]
    # v24.6.116: the successful JobAdder SPA payload is a flat answers array.
    # The API rejects answers as a raw array, but its model binder says
    # answers.textAnswers must be an IList. Try answers.textAnswers = [models]
    # first, including Presentability 62988 as numericValue/textValue.
    exact_variants.extend(_ja_browser_activity_answer_list_payload_variants(cid, fields, note_text, reference))
    # v24.6.106 fallback: qid-map/list variants retained for diagnostics.
    exact_variants.extend(_ja_precise_qid_activity_payload_variants(cid, fields, note_text, reference))
    # v24.6.116: try top-level rating collections before answer-object
    # variants, because live JobAdder says the mandatory rating question is
    # still missing even though the endpoint and activity setting are valid.
    # First try answer-object shapes that explicitly expose rating values by
    # question ID. This targets JobAdder's ActivityAnswerListModel binding where
    # normal answers are object-wrapped but rating controls require a separate
    # rating map/typed answer.
    for p_mode in ("rating_full", "rating_value", "number", "single_int"):
        for shape in ("rating_map_0", "rating_map_1", "rating_map_2", "rating_map_3", "rating_map_4", "rating_map_5", "rating_map_6"):
            exact_variants.append(_ja_candidate_screening_call_payload(
                cid, fields, note_text, reference=reference,
                answers_shape=shape, presentability_question_id=primary_presentability_qid,
                presentability_mode=p_mode,
            ))
    for p_mode in ("rating_full", "rating_value", "number", "single_int"):
        for shape in ("top_rating_items", "top_rating_text_answers", "top_rating_map", "top_rating_questions"):
            exact_variants.append(_ja_candidate_screening_call_payload(
                cid, fields, note_text, reference=reference,
                answers_shape=shape, presentability_question_id=primary_presentability_qid,
                presentability_mode=p_mode,
            ))
    # v24.6.116: diagnostics still say the mandatory rating question is not
    # bound. Try richer ActivityAnswerListModel-style objects before older maps.
    for p_mode in ("rating_full", "rating_value", "number", "single_int"):
        for shape in ("answer_bundle", "answer_bundle_object", "answer_bundle_pascal", "answer_bundle_maps", "answer_bundle_values", "map_full", "map_compact", "map_value", "items"):
            exact_variants.append(_ja_candidate_screening_call_payload(
                cid, fields, note_text, reference=reference,
                answers_shape=shape, presentability_question_id=primary_presentability_qid,
                presentability_mode=p_mode,
            ))
    # Fallbacks only if the tenant still expects a different legacy ID/shape.
    for presentability_qid in _ONENOTE_JA_PRESENTABILITY_QUESTION_IDS[1:]:
        for shape in ("map_full", "map_compact", "items"):
            exact_variants.append(_ja_candidate_screening_call_payload(
                cid, fields, note_text, reference=reference,
                answers_shape=shape, presentability_question_id=presentability_qid,
                presentability_mode="rating_full",
            ))
    # Late diagnostics only: retained for tenants that unexpectedly accept the
    # original browser-like array or text maps.
    for shape in ("answers", "map_text", "array"):
        exact_variants.append(_ja_candidate_screening_call_payload(
            cid, fields, note_text, reference=reference,
            answers_shape=shape, presentability_question_id=primary_presentability_qid,
            presentability_mode="text",
        ))

    base = {
        "type": activity_type,
        "activityType": activity_type,
        "activityTypeName": activity_type,
        "subject": subject,
        "title": subject,
        "description": note_text,
        "text": note_text,
        "comments": note_text,
        "comment": note_text,
        "note": note_text,
        "completed": True,
        "completedAt": now_utc,
        "date": now_utc,
        "reference": reference,
        "fields": fields,
        "answers": {"items": _ja_screening_call_answers(fields, note_text)},
    }
    with_candidate = dict(base)
    with_candidate.update({
        "entityType": "candidate",
        "candidateId": cid,
        "candidate_id": cid,
        "entityId": cid,
        "entityID": _ja_maybe_int(cid),
        "entity": {"entityID": _ja_maybe_int(cid)},
        "candidate": {"candidateId": cid, "id": cid},
    })
    setting_named = dict(base)
    setting_named.update({
        "candidateId": cid,
        "activitySettingID": _ONENOTE_JA_SCREENING_SETTING_ID,
        "activitySetting": {"name": "Candidate Screening Call", "id": _ONENOTE_JA_SCREENING_SETTING_ID},
        "activitySettingName": "Candidate Screening Call",
        "actionName": "Candidate Screening Call",
        "activityType": "Screening",
        "isCompleted": True,
    })
    return exact_variants + [setting_named, with_candidate, base]


def _ja_official_screening_activity_payload(fields, note_text=""):
    fields = fields or {}
    rating = _onenote_presentability_rating_int(fields)
    if rating not in (1, 2, 3, 4):
        raise ValueError("Presentability rating must be 1-4")
    values = {
        "brief_overview": _onenote_clean_field_value(fields.get("brief_overview", ""), max_len=8000),
        "reason_leaving": _onenote_clean_field_value(fields.get("reason_leaving", "")),
        "looking_for": _onenote_clean_field_value(fields.get("looking_for", "")),
        "current_salary_breakdown": _onenote_clean_field_value(fields.get("current_salary_breakdown", "")),
        "expected_salary": _onenote_clean_field_value(fields.get("expected_salary", "")),
        "notice_period": _onenote_clean_field_value(fields.get("notice_period", "")),
        "leads": _onenote_clean_field_value(fields.get("leads", "")),
        "remarks": _onenote_screening_remarks_value(fields, note_text),
    }
    text_answers = []
    for question_id, _question_text, key in _ONENOTE_JA_SCREENING_QUESTIONS_BASE:
        value = values.get(key, "")
        # Normal Screening Call text fields are optional in this tenant. Omit
        # unanswered questions rather than inserting artificial N/A text.
        if value:
            text_answers.append({"questionId": int(question_id), "text": value})
    return {
        "activitySettingId": _ONENOTE_JA_SCREENING_SETTING_ID,
        "answers": {
            "textAnswers": text_answers,
            "listValueAnswers": [],
            "dateRangeValueAnswers": [],
            "ratingValueAnswers": [
                {"questionId": _ONENOTE_JA_PRESENTABILITY_QUESTION_IDS[0], "rating": int(rating)}
            ],
        },
    }


def _ja_spa_browser_bridge(candidate_id, fields, note_text="", email="", salary_canonical=None, spelling_correction=True):
    """Return a safe copy/paste browser helper for the JobAdder SPA endpoint.

    v24.6.116: create-only. The user clarified OneNote transfer must always
    create a new Screening Call and must not update an existing Screening Call.
    The helper therefore tries likely JobAdder SPA create routes only. If all
    create routes fail, it prints a concise diagnostic and asks the user to
    capture the Network request from manually creating a brand-new Screening
    Call (not editing an existing one).
    """
    cid = str(candidate_id or "").strip()
    cid_q = urllib.parse.quote(cid, safe="")
    endpoint = "/spa/api/candidates/{}/activities/standardactivity".format(cid_q)
    profile_path = "/candidates/{}?tab=2&activityView=Activity".format(cid_q)
    # v24.6.116: captured successful create request uses standardactivity,
    # activityID: 0, attachments/mentionedUserIDs as null, task as empty string.
    # Add an in-browser sanitizer too, because older row.browser_bridge objects can
    # linger in the UI and because JobAdder returns only a vague HTTP 500 when a
    # required standard text field is blank.
    payload = _ja_spa_screening_call_payload(cid, fields, note_text, include_extended=False)
    if salary_canonical is None:
        salary_canonical = _ja_build_salary_notice_canonical(fields, {}, spelling_correction=spelling_correction)
    payload_json = json.dumps(payload, ensure_ascii=False, indent=2)
    compact_payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    script = """(async () => {
  const helperVersion = 'v24.6.329';
  const candidateId = %s;
  const payload = %s;
  const profilePath = %s;
  const headers = {
    'Accept': 'application/json, text/plain, */*',
    'Content-Type': 'application/json',
    'x-jobadder-spa': '1'
  };
  function cleanText(value, fallback) {
    const s = String(value == null ? '' : value).replace(/\\s+/g, ' ').trim();
    return s || fallback || 'N/A';
  }
  function answerByQuestion(qid) {
    return (Array.isArray(payload.answers) ? payload.answers : []).find(a => Number(a && a.questionID) === Number(qid)) || {};
  }
  function textAnswer(qid, qtext) {
    const a = answerByQuestion(qid);
    const fallback = Number(qid) === 41172 ? '' : 'N/A';
    return {
      questionID: qid,
      questionText: qtext,
      textValue: cleanText(a.textValue, fallback),
      startDateValue: null,
      endDateValue: null,
      numericValue: null
    };
  }
  function ratingAnswer() {
    const a = answerByQuestion(62988);
    let rating = Number(a.numericValue || a.textValue || 0);
    if (![1, 2, 3, 4].includes(rating)) {
      throw new Error('Presentability must be 1, 2, 3 or 4 before creating the Screening Call.');
    }
    return {
      questionID: 62988,
      questionText: 'Presentability (Confidence, Comms, Business Awareness)',
      textValue: String(rating),
      startDateValue: null,
      endDateValue: null,
      numericValue: rating
    };
  }
  // Match the successful manual-create shape exactly: six text answers + rating.
  const createPayload = {
    activityID: 0,
    activitySettingID: 8225,
    actionName: 'Candidate Screening Call',
    activityType: 'Screening',
    answers: [
      textAnswer(41172, 'Brief Overview of Experience'),
      textAnswer(41173, 'Reason For Leaving'),
      textAnswer(41174, 'Looking For?'),
      textAnswer(41175, 'Current Salary Breakdown'),
      textAnswer(41176, 'Expected Salary'),
      textAnswer(41177, 'Notice Period'),
      ratingAnswer()
    ],
    attachments: null,
    entity: {entityID: Number(candidateId) || candidateId},
    entityID: Number(candidateId) || candidateId,
    mentionedUserIDs: null,
    status: null,
    task: ''
  };
  async function readText(res) {
    try { return await res.text(); } catch (e) { return String(e || ''); }
  }
%s
  console.log('CV Studio OneNote → CREATE-ONLY helper', helperVersion);
  console.log('CV Studio OneNote → sanitized JobAdder CREATE payload', createPayload);
  const url = '/spa/api/candidates/' + encodeURIComponent(candidateId) + '/activities/standardactivity';
  const res = await fetch(url, {
    method: 'POST',
    credentials: 'same-origin',
    headers,
    body: JSON.stringify(createPayload)
  });
  const text = await readText(res);
  console.log('CV Studio OneNote → create-only response', res.status, text);
  if (res.ok) {
    let salaryResult = null;
    try {
      salaryResult = await cvStudioOneNoteSalaryUpdate();
      console.log('CV Studio OneNote → salary/notice update result', salaryResult);
    } catch (salaryErr) {
      salaryResult = { ok: false, reason: String(salaryErr && salaryErr.message || salaryErr) };
      console.warn('CV Studio OneNote → salary/notice update failed after Screening Call create', salaryResult);
    }
    const salaryMsg = salaryResult && salaryResult.ok
      ? 'Salary/notice update also completed.'
      : 'Screening Call created, but salary/notice update needs review in console.';
    alert('CV Studio Screening Call created as a NEW activity. ' + salaryMsg + ' Refresh the Activity tab if you do not see it immediately.');
    if (location.pathname !== profilePath.split('?')[0]) location.href = profilePath;
    return;
  }
  console.error('CV Studio OneNote → CREATE-ONLY failed. No existing Screening Call was updated.', {status: res.status, response: text, payload: createPayload});
  alert([
    'CV Studio could not create a NEW Candidate Screening Call via JobAdder standardactivity.',
    'No existing Screening Call was updated.',
    '',
    'Please copy the failed Network request Payload and Preview/Response only.'
  ].join(String.fromCharCode(10)));
  throw new Error('Create-only JobAdder SPA attempt failed: HTTP ' + res.status);
})();""" % (json.dumps(cid), compact_payload_json, json.dumps(profile_path), _ja_spa_salary_update_helper_js(salary_canonical))
    return {
        "method": "CREATE-ONLY browser SPA helper using /standardactivity; never updates existing Screening Calls",
        "endpoint": endpoint,
        "fallback": "No update fallback. Uses the captured JobAdder SPA create route /activities/standardactivity. If it fails, capture the successful Network request from manually creating a brand-new Candidate Screening Call.",
        "profile_url": _jobadder_candidate_activity_url(cid),
        "payload": payload,
        "payload_json": payload_json,
        "script": script,
        "warning": "Run this only in the JobAdder candidate page DevTools Console while logged into JobAdder. It uses your browser session automatically and does not expose cookies to CV Studio. This script never updates an existing Screening Call; it posts only to /activities/standardactivity to create a new one. Blank standard text fields are filled with N/A for create compatibility.",
        "email": email,
        "candidate_id": cid,
        "salary_canonical": salary_canonical,
    }
