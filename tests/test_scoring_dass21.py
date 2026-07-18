"""Unit tests for the DASS-21 scoring engine (ground-truth source)."""

import pytest

from app.scoring.dass21 import (
    DASS21_QUESTIONS,
    SUBSCALE_ITEMS,
    classify_severity,
    score_dass21,
)


def make_answers(value: int = 0, overrides: dict[int, int] | None = None) -> dict[int, int]:
    answers = {qid: value for qid in range(1, 22)}
    if overrides:
        answers.update(overrides)
    return answers


class TestStructure:
    def test_has_21_questions_with_unique_ids(self):
        assert len(DASS21_QUESTIONS) == 21
        assert {q["id"] for q in DASS21_QUESTIONS} == set(range(1, 22))

    def test_each_subscale_has_7_items(self):
        for subscale, items in SUBSCALE_ITEMS.items():
            assert len(items) == 7, subscale

    def test_official_subscale_mapping(self):
        assert SUBSCALE_ITEMS["depression"] == [3, 5, 10, 13, 16, 17, 21]
        assert SUBSCALE_ITEMS["anxiety"] == [2, 4, 7, 9, 15, 19, 20]
        assert SUBSCALE_ITEMS["stress"] == [1, 6, 8, 11, 12, 14, 18]

    def test_vietnamese_text_present(self):
        assert all(q["text_vi"] for q in DASS21_QUESTIONS)


class TestScoring:
    def test_all_zero_answers(self):
        result = score_dass21(make_answers(0))
        for subscale in ("depression", "anxiety", "stress"):
            assert result[subscale]["score"] == 0
            assert result[subscale]["severity"] == "Normal"
        assert result["overall_severity"] == "Normal"

    def test_all_max_answers(self):
        result = score_dass21(make_answers(3))
        for subscale in ("depression", "anxiety", "stress"):
            assert result[subscale]["score"] == 42  # 7 items * 3 * 2
            assert result[subscale]["severity"] == "Extremely Severe"
        assert result["overall_severity"] == "Extremely Severe"

    def test_scores_are_doubled_sums(self):
        # Depression items = 3,5,10,13,16,17,21; give each a 1 -> sum 7 -> score 14.
        answers = make_answers(0, {qid: 1 for qid in SUBSCALE_ITEMS["depression"]})
        result = score_dass21(answers)
        assert result["depression"]["score"] == 14
        assert result["anxiety"]["score"] == 0
        assert result["stress"]["score"] == 0

    def test_overall_severity_is_worst_subscale(self):
        # Max out anxiety only.
        answers = make_answers(0, {qid: 3 for qid in SUBSCALE_ITEMS["anxiety"]})
        result = score_dass21(answers)
        assert result["anxiety"]["severity"] == "Extremely Severe"
        assert result["depression"]["severity"] == "Normal"
        assert result["overall_severity"] == "Extremely Severe"


class TestCutoffs:
    """Boundary tests against the official Lovibond & Lovibond cutoffs."""

    @pytest.mark.parametrize(
        "score,expected",
        [(0, "Normal"), (9, "Normal"), (10, "Mild"), (13, "Mild"), (14, "Moderate"),
         (20, "Moderate"), (21, "Severe"), (27, "Severe"), (28, "Extremely Severe"), (42, "Extremely Severe")],
    )
    def test_depression_cutoffs(self, score, expected):
        assert classify_severity("depression", score) == expected

    @pytest.mark.parametrize(
        "score,expected",
        [(0, "Normal"), (7, "Normal"), (8, "Mild"), (9, "Mild"), (10, "Moderate"),
         (14, "Moderate"), (15, "Severe"), (19, "Severe"), (20, "Extremely Severe"), (42, "Extremely Severe")],
    )
    def test_anxiety_cutoffs(self, score, expected):
        assert classify_severity("anxiety", score) == expected

    @pytest.mark.parametrize(
        "score,expected",
        [(0, "Normal"), (14, "Normal"), (15, "Mild"), (18, "Mild"), (19, "Moderate"),
         (25, "Moderate"), (26, "Severe"), (33, "Severe"), (34, "Extremely Severe"), (42, "Extremely Severe")],
    )
    def test_stress_cutoffs(self, score, expected):
        assert classify_severity("stress", score) == expected


class TestValidation:
    def test_missing_question_rejected(self):
        answers = make_answers(1)
        del answers[21]
        with pytest.raises(ValueError):
            score_dass21(answers)

    def test_extra_question_rejected(self):
        with pytest.raises(ValueError):
            score_dass21(make_answers(1) | {22: 1})

    def test_out_of_range_answer_rejected(self):
        with pytest.raises(ValueError):
            score_dass21(make_answers(1, {5: 4}))
        with pytest.raises(ValueError):
            score_dass21(make_answers(1, {5: -1}))

    def test_bool_answer_rejected(self):
        with pytest.raises(ValueError):
            score_dass21(make_answers(1, {5: True}))
