"""JobAdder screening-question answer builders for CV Studio.

Behaviour-preserving extraction from the app shell: presentability answer
resolution, rating/text answer splitting, and the JobAdder answer-model payload
bundles for candidate custom-field submission. Pure functions of their inputs --
no Flask, no globals, no network. This module never imports ``app``.
"""


_ONENOTE_JA_PRESENTABILITY_QUESTION_IDS = [62988, 52988]


def _ja_presentability_answer(qid, qtext, rating, mode="rating_full"):
    rating = int(rating) if str(rating).strip().isdigit() else rating
    rating_text = str(rating) if str(rating).strip() else ""
    answer = {
        "questionID": qid,
        "questionId": qid,
        "question_id": qid,
        "activityQuestionID": qid,
        "activityQuestionId": qid,
        "ratingQuestionID": qid,
        "ratingQuestionId": qid,
        "questionText": qtext,
        "questionType": "Rating",
        "answerType": "Rating",
        "fieldType": "Rating",
        "controlType": "Rating",
        "dataType": "Rating",
        "type": "Rating",
        "textValue": "",
        "startDateValue": None,
        "endDateValue": None,
        "numberValue": None,
        "numericValue": None,
        "decimalValue": None,
        "booleanValue": None,
        "singleSelectValue": None,
        "multiSelectValue": [],
    }
    # v24.6.116: live JobAdder diagnostic accepted object-shaped answers but
    # still complained: "All rating mandatory questions are required." This
    # means the endpoint/answer object shape is close, but the rating field name
    # is not one of the normal text/numeric fields. JobAdder web renders
    # Presentability as a required 1/2/3/4 button, so the first payload now
    # includes common rating/select aliases in one object. Unknown fields are
    # ignored by the API deserializer, while the correct rating field can satisfy
    # the mandatory rating question.
    def add_rating_aliases(include_text=False, include_select=False):
        answer["ratingValue"] = rating
        answer["rating"] = rating
        answer["ratingScore"] = rating
        answer["score"] = rating
        answer["value"] = rating
        answer["answerValue"] = rating
        answer["selectedValue"] = rating
        answer["selectedRating"] = rating
        answer["selectedRatingValue"] = rating
        answer["optionValue"] = rating_text
        answer["selectedOptionValue"] = rating_text
        answer["answerOptionValue"] = rating_text
        answer["numberValue"] = rating
        answer["numericValue"] = rating
        if include_select:
            answer["singleSelectValue"] = rating
            answer["selectedOptionID"] = rating
            answer["optionID"] = rating
            answer["answerOptionID"] = rating
        if include_text:
            answer["textValue"] = rating_text

    if mode in ("rating_full", "rating_aliases"):
        add_rating_aliases(include_text=True, include_select=True)
    elif mode == "rating_value":
        answer["ratingValue"] = rating
        answer["rating"] = rating
    elif mode == "number":
        answer["numberValue"] = rating
        answer["numericValue"] = rating
    elif mode == "decimal":
        answer["decimalValue"] = float(rating)
        answer["numericValue"] = rating
    elif mode == "single_int":
        answer["singleSelectValue"] = rating
    elif mode == "single_text":
        answer["singleSelectValue"] = rating_text
    elif mode == "single_object":
        answer["singleSelectValue"] = {"id": rating, "value": rating, "text": rating_text, "name": rating_text}
    elif mode == "text":
        answer["textValue"] = rating_text
    else:
        add_rating_aliases(include_text=False, include_select=False)
    return answer


def _ja_answers_object_variants(answers):
    """Return ActivityAnswerListModel-compatible shapes to try before answers[]."""
    by_qid_full = {str(a.get("questionID")): dict(a) for a in answers}
    by_qid_text = {str(a.get("questionID")): (a.get("textValue") or "") for a in answers}
    return [
        {"items": answers},
        {"answers": answers},
        {"activityAnswers": answers},
        {"values": answers},
        {"questions": answers},
        by_qid_full,
        by_qid_text,
    ]


def _ja_answer_is_presentability(answer):
    return str(answer.get("questionID") or answer.get("questionId") or "") in {str(x) for x in _ONENOTE_JA_PRESENTABILITY_QUESTION_IDS}


def _ja_answer_model_bundle(answers, rating, bundle_mode="camel"):
    """Build richer ActivityAnswerListModel-style objects.

    Live diagnostics prove JobAdder's candidate activity endpoint accepts an
    object for `answers`, but the exact model properties for rating/button
    questions are tenant/API-version specific.  Keep this object entirely under
    `answers` and include common collection names for text/rating answers so the
    API can bind the required rating question without falling back to Candidate
    Notes.
    """
    text_answers = [dict(a) for a in answers if not _ja_answer_is_presentability(a)]
    rating_answers = [dict(a) for a in answers if _ja_answer_is_presentability(a)]
    enriched_ratings = []
    for a in rating_answers:
        qid = a.get("questionID") or a.get("questionId")
        qtext = a.get("questionText") or "Presentability (Confidence, Comms, Business Awareness)"
        rating_int = int(rating) if str(rating).strip().isdigit() else rating
        rating_text = str(rating_int) if str(rating_int).strip() else ""
        enriched = dict(a)
        # Leave every common text/rating/null field present, but add nested
        # aliases as several JobAdder UI payloads bind button/rating questions
        # through a nested answer/rating object rather than textValue.
        nested = {
            "id": rating_int,
            "value": rating_int,
            "text": rating_text,
            "name": rating_text,
            "label": rating_text,
            "rating": rating_int,
            "ratingValue": rating_int,
            "score": rating_int,
        }
        enriched.update({
            "questionID": qid,
            "questionId": qid,
            "question_id": qid,
            "questionText": qtext,
            "ratingValue": rating_int,
            "rating": rating_int,
            "ratingScore": rating_int,
            "ratingAnswer": nested,
            "ratingAnswerValue": rating_int,
            "answer": nested,
            "answerValue": rating_int,
            "value": rating_int,
            "score": rating_int,
            "selectedValue": rating_int,
            "selectedRating": rating_int,
            "selectedRatingValue": rating_int,
            "selectedOption": nested,
            "selectedOptionID": rating_int,
            "selectedOptionId": rating_int,
            "option": nested,
            "optionID": rating_int,
            "optionId": rating_int,
            "answerOptionID": rating_int,
            "answerOptionId": rating_int,
            "numberValue": rating_int,
            "numericValue": rating_int,
            "decimalValue": float(rating_int) if str(rating_int).strip().isdigit() else None,
            "textValue": rating_text,
            "singleSelectValue": nested if bundle_mode.endswith("object") else rating_int,
        })
        enriched_ratings.append(enriched)
    all_answers = text_answers + enriched_ratings
    by_qid = {str(a.get("questionID") or a.get("questionId")): dict(a) for a in all_answers}
    rating_by_qid = {str(a.get("questionID") or a.get("questionId")): dict(a) for a in enriched_ratings}
    text_by_qid = {str(a.get("questionID") or a.get("questionId")): dict(a) for a in text_answers}

    if bundle_mode == "dollar_values":
        return {"$values": all_answers}
    if bundle_mode == "pascal":
        return {
            "Items": all_answers,
            "Answers": all_answers,
            "ActivityAnswers": all_answers,
            "TextAnswers": text_answers,
            "RatingAnswers": enriched_ratings,
            "RatingQuestionAnswers": enriched_ratings,
            "QuestionAnswers": all_answers,
            "Values": all_answers,
        }
    if bundle_mode == "maps":
        return {
            "items": all_answers,
            "byQuestionID": by_qid,
            "answersByQuestionID": by_qid,
            "textAnswersByQuestionID": text_by_qid,
            "ratingAnswersByQuestionID": rating_by_qid,
            "ratingsByQuestionID": rating_by_qid,
        }
    return {
        "items": all_answers,
        "answers": all_answers,
        "activityAnswers": all_answers,
        "questionAnswers": all_answers,
        "activityQuestionAnswers": all_answers,
        "values": all_answers,
        "questions": all_answers,
        "textAnswers": text_answers,
        "textQuestionAnswers": text_answers,
        "ratingAnswers": enriched_ratings,
        "ratings": enriched_ratings,
        "ratingQuestionAnswers": enriched_ratings,
        "ratingValues": enriched_ratings,
    }


def _ja_split_text_rating_answers(answers, rating):
    """Return text-only answers plus top-level rating bundles for JobAdder.

    v24.6.116: live diagnostics reached candidates/{id}/activities but still
    returned "All rating mandatory questions are required."  Try keeping text
    answers inside ActivityAnswerListModel while also sending Presentability as
    separate top-level rating collections.
    """
    rating_int = int(rating) if str(rating).strip().isdigit() else rating
    rating_text = str(rating_int) if str(rating_int).strip() else ""
    text_answers = [dict(a) for a in answers if not _ja_answer_is_presentability(a)]
    rating_answers = []
    for a in answers:
        if not _ja_answer_is_presentability(a):
            continue
        qid = a.get("questionID") or a.get("questionId")
        qtext = a.get("questionText") or "Presentability (Confidence, Comms, Business Awareness)"
        rating_answers.append({
            "questionID": qid,
            "questionId": qid,
            "question_id": qid,
            "activityQuestionID": qid,
            "activityQuestionId": qid,
            "ratingQuestionID": qid,
            "ratingQuestionId": qid,
            "id": qid,
            "questionText": qtext,
            "questionType": "Rating",
            "answerType": "Rating",
            "fieldType": "Rating",
            "controlType": "Rating",
            "dataType": "Rating",
            "type": "Rating",
            "value": rating_int,
            "rating": rating_int,
            "ratingValue": rating_int,
            "rateValue": rating_int,
            "ratingScore": rating_int,
            "score": rating_int,
            "stars": rating_int,
            "numberValue": rating_int,
            "numericValue": rating_int,
            "decimalValue": float(rating_int) if str(rating_int).strip().isdigit() else None,
            "textValue": rating_text,
            "answerValue": rating_int,
            "selectedValue": rating_int,
            "selectedRating": rating_int,
            "selectedRatingValue": rating_int,
            "selectedOption": {"id": rating_int, "value": rating_int, "text": rating_text, "name": rating_text},
            "selectedOptionID": rating_int,
            "selectedOptionId": rating_int,
            "optionID": rating_int,
            "optionId": rating_int,
            "answerOptionID": rating_int,
            "answerOptionId": rating_int,
        })
    rating_by_qid = {str(x.get("questionID") or x.get("questionId")): dict(x) for x in rating_answers}
    return text_answers, rating_answers, rating_by_qid


# --- JobAdder screening/activity answer payload builders (Phase 7B slice) ---

def _ja_maybe_int(value):
    """Return an integer when JobAdder expects numeric IDs, otherwise a string."""
    text = str(value or "").strip()
    return int(text) if text.isdigit() else text


_ONENOTE_JA_SCREENING_SETTING_ID = 8225


def _ja_answer_model_qid_list_payloads(answers, rating):
    """ActivityAnswerListModel variants where question IDs map to lists.

    v24.6.116: JobAdder returned a very useful .NET binding error:
    answers.textAnswers.41172 expected IList[ActivityTextAnswerModel]. That means
    a likely public API shape is answers.textAnswers.{questionID}: [answerModel]
    and answers.ratingAnswers.{questionID}: [ratingAnswerModel]. Try those before
    the broader/older rating guesses.
    """
    rating_int = int(rating) if str(rating).strip().isdigit() else None
    if rating_int not in (1, 2, 3, 4):
        rating_int = None
    rating_text = str(rating_int or "")
    text_answers = []
    rating_answers = []
    for a in answers:
        qid = a.get("questionID") or a.get("questionId")
        if not qid:
            continue
        if _ja_answer_is_presentability(a):
            ra = {
                "questionID": _ja_maybe_int(qid),
                "questionId": _ja_maybe_int(qid),
                "questionText": a.get("questionText") or "Presentability (Confidence, Comms, Business Awareness)",
                "numericValue": rating_int,
                "numberValue": rating_int,
                "textValue": rating_text,
                "startDateValue": None,
                "endDateValue": None,
            }
            # Keep the exact browser-observed shape first, with a few harmless
            # aliases for tenants/API builds that name the rating property differently.
            ra.update({
                "ratingValue": rating_int,
                "rating": rating_int,
                "value": rating_int,
                "score": rating_int,
            })
            rating_answers.append(ra)
        else:
            text_answers.append({
                "questionID": _ja_maybe_int(qid),
                "questionId": _ja_maybe_int(qid),
                "questionText": a.get("questionText") or "",
                "textValue": a.get("textValue") or "",
                "startDateValue": None,
                "endDateValue": None,
            })
    text_map_list = {str(a["questionID"]): [a] for a in text_answers}
    rating_map_list = {str(a["questionID"]): [a] for a in rating_answers}
    # Also try dict values with explicit nested collection names because the
    # .NET error path can vary depending on the generated model binder.
    text_map_named_list = {k: {"textAnswers": v} for k, v in text_map_list.items()}
    rating_map_named_list = {k: {"ratingAnswers": v} for k, v in rating_map_list.items()}
    text_map_values = {str(a["questionID"]): (a.get("textValue") or "") for a in text_answers}
    rating_map_values = {str(a["questionID"]): rating_int for a in rating_answers if rating_int is not None}
    return [
        {"textAnswers": text_map_list, "ratingAnswers": rating_map_list},
        {"textAnswers": text_map_list, "ratingQuestionAnswers": rating_map_list},
        {"activityTextAnswers": text_map_list, "activityRatingAnswers": rating_map_list},
        {"textQuestionAnswers": text_map_list, "ratingQuestionAnswers": rating_map_list},
        {"textAnswers": text_answers, "ratingAnswers": rating_answers},
        {"textQuestionAnswers": text_answers, "ratingQuestionAnswers": rating_answers},
        {"items": text_answers + rating_answers, "textAnswers": text_map_list, "ratingAnswers": rating_map_list},
        {"textAnswers": text_map_named_list, "ratingAnswers": rating_map_named_list},
        {"textValues": text_map_values, "ratingValues": rating_map_values},
    ]


def _ja_rating_map_answer_payloads(answers, rating):
    """Extra ActivityAnswerListModel object shapes for rating/button fields.

    JobAdder's error now consistently says the activity endpoint and setting are
    accepted, but the mandatory rating question is not bound. These variants keep
    text answers separate and expose Presentability as explicit rating maps by
    question ID inside the answers object, with type metadata for rating controls.
    """
    rating_int = int(rating) if str(rating).strip().isdigit() else None
    if rating_int not in (1, 2, 3, 4):
        rating_int = None
    rating_text = str(rating_int or "")
    text_answers = [dict(a) for a in answers if not _ja_answer_is_presentability(a)]
    text_values = {str(a.get("questionID")): (a.get("textValue") or "") for a in text_answers}
    rating_qids = [str(a.get("questionID") or a.get("questionId")) for a in answers if _ja_answer_is_presentability(a)] or [str(_ONENOTE_JA_PRESENTABILITY_QUESTION_IDS[0])]
    rating_values = {qid: rating_int for qid in rating_qids if rating_int is not None}
    rating_objects = {qid: {
        "questionID": _ja_maybe_int(qid),
        "questionId": _ja_maybe_int(qid),
        "activityQuestionID": _ja_maybe_int(qid),
        "ratingQuestionID": _ja_maybe_int(qid),
        "questionText": "Presentability (Confidence, Comms, Business Awareness)",
        "questionType": "Rating",
        "answerType": "Rating",
        "fieldType": "Rating",
        "controlType": "Rating",
        "dataType": "Rating",
        "type": "Rating",
        "ratingValue": rating_int,
        "rateValue": rating_int,
        "rating": rating_int,
        "score": rating_int,
        "value": rating_int,
        "numericValue": rating_int,
        "numberValue": rating_int,
        "decimalValue": float(rating_int) if rating_int is not None else None,
        "textValue": rating_text,
    } for qid in rating_qids if rating_int is not None}
    qid_list_payloads = _ja_answer_model_qid_list_payloads(answers, rating)
    return qid_list_payloads + [
        {"items": text_answers, "textValues": text_values, "ratingValues": rating_values},
        {"items": text_answers, "textAnswers": text_values, "ratingAnswers": rating_values},
        {"items": text_answers, "textQuestionAnswers": text_values, "ratingQuestionAnswers": rating_values},
        {"items": text_answers, "textAnswersByQuestionID": text_values, "ratingAnswersByQuestionID": rating_objects},
        {"items": text_answers, "answersByQuestionID": {**{k: {"questionID": _ja_maybe_int(k), "textValue": v} for k, v in text_values.items()}, **rating_objects}},
        {"text": text_values, "ratings": rating_values},
        {"values": {**text_values, **{k: v for k, v in rating_values.items()}}, "types": {**{k: "Text" for k in text_values}, **{k: "Rating" for k in rating_values}}},
    ]


def _ja_candidate_screening_call_base_payload(candidate_id, reference=None, activity_id=None):
    """Base JobAdder Candidate Screening Call activity payload."""
    cid_value = _ja_maybe_int(candidate_id)
    payload = {
        "activitySettingID": _ONENOTE_JA_SCREENING_SETTING_ID,
        "actionName": "Candidate Screening Call",
        "activityType": "Screening",
        "attachments": [],
        "entity": {"entityID": cid_value},
        "entityID": cid_value,
        "mentionedUserIDs": [],
        "status": None,
        "task": None,
    }
    if reference:
        payload["reference"] = reference
    if activity_id:
        payload["activityID"] = _ja_maybe_int(activity_id)
    return payload


def _ja_answer_model_qid_list_payloads_v105(answers, rating):
    """Highest-priority ActivityAnswerListModel shapes.

    JobAdder's binder error says answers.textAnswers.<questionID> expects an
    IList[ActivityTextAnswerModel]. Put every field, including Presentability
    62988 with numericValue and textValue, under textAnswers.<qid> = [answer].
    """
    rating_int = int(rating) if str(rating).strip().isdigit() else None
    if rating_int not in (1, 2, 3, 4):
        rating_int = None
    rating_text = str(rating_int or "")
    text_only_map = {}
    rating_map = {}
    all_as_text_map = {}
    for a in answers:
        qid = a.get("questionID") or a.get("questionId")
        if not qid:
            continue
        key = str(qid)
        qid_value = _ja_maybe_int(key)
        qtext = a.get("questionText") or ""
        if _ja_answer_is_presentability(a):
            model = {
                "questionID": qid_value,
                "questionId": qid_value,
                "questionText": qtext or "Presentability (Confidence, Comms, Business Awareness)",
                "textValue": rating_text,
                "numericValue": rating_int,
                "numberValue": rating_int,
                "decimalValue": float(rating_int) if rating_int is not None else None,
                "startDateValue": None,
                "endDateValue": None,
            }
            rating_model = dict(model)
            rating_model.update({"ratingValue": rating_int, "rating": rating_int, "score": rating_int, "value": rating_int})
            rating_map[key] = [rating_model]
            all_as_text_map[key] = [model]
        else:
            model = {
                "questionID": qid_value,
                "questionId": qid_value,
                "questionText": qtext,
                "textValue": a.get("textValue") or "",
                "startDateValue": None,
                "endDateValue": None,
            }
            text_only_map[key] = [model]
            all_as_text_map[key] = [model]
    # v24.6.116: JobAdder diagnostic path says
    # answers.textAnswers.41172.textAnswers expected IList[ActivityTextAnswerModel].
    # That means each question-ID entry is likely a wrapper object with a
    # nested textAnswers/ratingAnswers list, not just qid -> [model]. Try the
    # nested wrapper first, then keep the direct qid -> list shapes as fallback.
    text_only_nested = {k: {"textAnswers": v} for k, v in text_only_map.items()}
    rating_nested = {k: {"ratingAnswers": v} for k, v in rating_map.items()}
    all_as_text_nested = {k: {"textAnswers": v} for k, v in all_as_text_map.items()}
    rating_nested_text_named = {k: {"textAnswers": v} for k, v in rating_map.items()}
    return [
        {"textAnswers": text_only_nested, "ratingAnswers": rating_nested},
        {"textAnswers": all_as_text_nested},
        {"textAnswers": text_only_nested, "ratingQuestionAnswers": rating_nested},
        {"textAnswers": text_only_nested, "ratings": rating_nested},
        {"textAnswers": {**text_only_nested, **rating_nested_text_named}},
        {"textAnswers": all_as_text_map},
        {"textAnswers": text_only_map, "ratingAnswers": rating_map},
        {"textAnswers": all_as_text_map, "ratingAnswers": rating_map},
        {"TextAnswers": all_as_text_nested},
        {"TextAnswers": all_as_text_map},
        {"textQuestionAnswers": all_as_text_nested},
        {"textQuestionAnswers": all_as_text_map},
        {"activityTextAnswers": all_as_text_nested},
        {"activityTextAnswers": all_as_text_map},
        {"textAnswers": all_as_text_map, "ratingQuestionAnswers": rating_map},
    ]


def _ja_controlled_official_activity_payload(candidate_id):
    """Build one AddCandidateActivity request from JobAdder's official v2 schema.

    Official reference:
    https://api.jobadder.com/v2/docs#operation/AddCandidateActivity

    The public OAuth write model is intentionally different from both the SPA
    request model and the GET response model:
      - textAnswers: [{questionId, text}]
      - listValueAnswers: [{questionId, values}]
      - dateRangeValueAnswers: [{questionId, startDate, endDate}]
      - ratingValueAnswers: [{questionId, rating}]

    This diagnostic sends one exact documented request only. It does not add
    SPA-only fields, response-only fields, aliases, or automatic fallbacks.
    """
    _ = _ja_maybe_int(candidate_id)  # Validate the fixture ID shape without adding it to the body.
    text_rows = [
        (41172, "N/A"),
        (41173, "why"),
        (41174, "somethjihng"),
        (41175, "2324rm + 32sllowance + 3months"),
        (41176, "4222rm"),
        (41177, "2 months"),
    ]
    return {
        "activitySettingId": _ONENOTE_JA_SCREENING_SETTING_ID,
        "answers": {
            "textAnswers": [
                {"questionId": question_id, "text": answer}
                for question_id, answer in text_rows
            ],
            "listValueAnswers": [],
            "dateRangeValueAnswers": [],
            "ratingValueAnswers": [
                {"questionId": 62988, "rating": 3}
            ],
        },
    }

