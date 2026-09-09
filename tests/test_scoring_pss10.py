"""Unit tests for the PSS-10 scoring engine (ground-truth source)."""

import pytest

from app.scoring.pss10 import (
    PSS10_QUESTIONS,
    REVERSE_SCORED_ITEMS,
    classify_pss,
    score_pss10,
)


def make_answers(value: int = 0, overrides: dict[int, int] | None = None) -> dict[int, int]:
    answers = {qid: value for qid in range(1, 11)}
    if overrides:
        answers.update(overrides)
    return answers


class TestStructure:
    def test_has_10_questions(self):
        assert len(PSS10_QUESTIONS) == 10
        assert {q["id"] for q in PSS10_QUESTIONS} == set(range(1, 11))

    def test_reverse_items_are_4_5_7_8(self):
        assert REVERSE_SCORED_ITEMS == frozenset({4, 5, 7, 8})
        assert {q["id"] for q in PSS10_QUESTIONS if q["reverse"]} == {4, 5, 7, 8}

    def test_vietnamese_text_present(self):
        assert all(q["text"] for q in PSS10_QUESTIONS)


class TestScoring:
    def test_all_zero_gives_16(self):
        # Reverse items 4,5,7,8 each become 4-0=4 -> total 16 -> Moderate.
        result = score_pss10(make_answers(0))
        assert result["total_score"] == 16
        assert result["category"] == "Moderate"

    def test_all_four_gives_24(self):
        # Direct items: 6*4=24; reverse items: 4-4=0 -> total 24 -> Moderate.
        result = score_pss10(make_answers(4))
        assert result["total_score"] == 24
        assert result["category"] == "Moderate"

    def test_max_stress_pattern(self):
        # Direct items at 4, reverse items at 0 -> 24 + 16 = 40 -> High.
        answers = make_answers(4, {qid: 0 for qid in REVERSE_SCORED_ITEMS})
        result = score_pss10(answers)
        assert result["total_score"] == 40
        assert result["category"] == "High"

    def test_min_stress_pattern(self):
        # Direct items at 0, reverse items at 4 -> 0 -> Low.
        answers = make_answers(0, {qid: 4 for qid in REVERSE_SCORED_ITEMS})
        result = score_pss10(answers)
        assert result["total_score"] == 0
        assert result["category"] == "Low"

    def test_item_scores_reflect_reversal(self):
        answers = make_answers(1)
        result = score_pss10(answers)
        assert result["item_scores"][1] == 1
        assert result["item_scores"][4] == 3


class TestCutoffs:
    @pytest.mark.parametrize(
        "score,expected",
        [(0, "Low"), (13, "Low"), (14, "Moderate"), (26, "Moderate"), (27, "High"), (40, "High")],
    )
    def test_category_boundaries(self, score, expected):
        assert classify_pss(score) == expected

    def test_out_of_range_score_rejected(self):
        with pytest.raises(ValueError):
            classify_pss(41)
        with pytest.raises(ValueError):
            classify_pss(-1)


class TestValidation:
    def test_missing_question_rejected(self):
        answers = make_answers(1)
        del answers[10]
        with pytest.raises(ValueError):
            score_pss10(answers)

    def test_out_of_range_answer_rejected(self):
        with pytest.raises(ValueError):
            score_pss10(make_answers(1, {3: 5}))

    def test_bool_answer_rejected(self):
        with pytest.raises(ValueError):
            score_pss10(make_answers(1, {3: True}))
