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
