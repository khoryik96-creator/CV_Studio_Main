"""Characterization coverage for the extracted JobAdder screening-answer builders.

These are pure payload builders moved verbatim from the web shell into
cvstudio_ja_answers.py; app.py re-exports the names. The tests pin the current
answer-object shapes so the extraction (and any future edit) stays
behaviour-preserving.
"""

import unittest

import app


class JaAnswersCharacterizationTests(unittest.TestCase):
    def test_presentability_answer_rating_full(self):
        a = app._ja_presentability_answer(62988, "Presentability", 3, mode="rating_full")
        self.assertEqual(a["questionID"], 62988)
        self.assertEqual(a["questionType"], "Rating")
        self.assertEqual(a["ratingValue"], 3)
        self.assertEqual(a["rating"], 3)
        self.assertEqual(a["numberValue"], 3)
        self.assertEqual(a["textValue"], "3")
        self.assertEqual(a["singleSelectValue"], 3)

    def test_presentability_answer_text_mode_leaves_number_unset(self):
        a = app._ja_presentability_answer(62988, "Q", 2, mode="text")
        self.assertEqual(a["textValue"], "2")
        self.assertIsNone(a["numberValue"])

    def test_answer_is_presentability(self):
        self.assertTrue(app._ja_answer_is_presentability({"questionID": 62988}))
        self.assertTrue(app._ja_answer_is_presentability({"questionId": 52988}))
        self.assertFalse(app._ja_answer_is_presentability({"questionID": 999}))

    def test_answers_object_variants_shapes(self):
        answers = [{"questionID": 62988, "textValue": "3"}]
        variants = app._ja_answers_object_variants(answers)
        self.assertEqual(len(variants), 7)
        self.assertEqual(variants[0], {"items": answers})
        self.assertEqual(variants[5], {"62988": {"questionID": 62988, "textValue": "3"}})
        self.assertEqual(variants[6], {"62988": "3"})

    def test_answer_model_bundle_splits_text_and_rating(self):
        answers = [
            {"questionID": 111, "textValue": "hi"},
            {"questionID": 62988, "questionText": "P"},
        ]
        bundle = app._ja_answer_model_bundle(answers, 4)
        self.assertEqual(len(bundle["textAnswers"]), 1)
        self.assertEqual(len(bundle["ratingAnswers"]), 1)
        self.assertEqual(bundle["ratingAnswers"][0]["ratingValue"], 4)
        self.assertEqual(bundle["ratingAnswers"][0]["textValue"], "4")

    def test_split_text_rating_answers(self):
        answers = [
            {"questionID": 111, "textValue": "hi"},
            {"questionID": 52988, "questionText": "P"},
        ]
        text, rating, rating_by_qid = app._ja_split_text_rating_answers(answers, 1)
        self.assertEqual(len(text), 1)
        self.assertEqual(len(rating), 1)
        self.assertEqual(rating[0]["ratingValue"], 1)
        self.assertEqual(rating_by_qid["52988"]["rating"], 1)

    def test_module_never_imports_app(self):
        import inspect

        import cvstudio_ja_answers

        self.assertNotIn("import app", inspect.getsource(cvstudio_ja_answers))


if __name__ == "__main__":
    unittest.main()
