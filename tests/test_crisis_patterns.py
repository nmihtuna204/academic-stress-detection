"""Tests for the construct-organised crisis patterns.

This is safety-critical code: a regression here means a student who discloses
self-harm is shown ordinary advice instead of helplines. The tests are written
to fail loudly on that, and to hold the precision guards in place so the fix
for one problem does not silently create another.
"""

from __future__ import annotations

import pytest

from app.llm.safety import check_crisis
from app.nlp.crisis_patterns import CRISIS_PATTERNS, find_crisis_matches
from app.nlp.lexicon import find_crisis_constructs, find_crisis_keywords, normalize


def fires(text: str) -> bool:
    return bool(find_crisis_keywords(text))


def constructs(text: str) -> set[str]:
    return {c for c, _ in find_crisis_constructs(text)}


class TestEveryConstructFires:
    """Each clinical construct must be reachable, in both languages."""

    @pytest.mark.parametrize(
        "construct,text",
        [
            ("explicit", "I want to kill myself"),
            ("explicit", "Em muốn chết"),
            ("passive_wish", "I keep hoping I will not wake up"),
            ("passive_wish", "Em mong sáng mai đừng tỉnh dậy nữa"),
            ("existence", "I would like to stop existing"),
            ("existence", "Em không muốn tồn tại nữa"),
            ("burden", "Everyone would be better off without me"),
            ("burden", "Em thấy mình là gánh nặng cho cả nhà"),
            ("preparation", "I have written a goodbye letter"),
            ("preparation", "Em đã viết sẵn thư tạm biệt cho gia đình"),
            ("escape", "I am so tired of being alive"),
            ("escape", "Em mệt vì phải sống chứ không phải vì học"),
        ],
    )
    def test_construct_is_detected(self, construct, text):
        assert construct in constructs(text), f"{construct} did not fire on: {text}"


class TestIdiomGuards:
    """Lethal vocabulary in ordinary complaint must not trigger a crisis."""

    @pytest.mark.parametrize(
        "text",
        [
            "I'm killing myself at the gym six days a week",
            "My laptop died and took my draft with it",
            "I nearly died laughing at my own thesis title",
            "I would kill for a decent night of sleep",
            "This lab report is the hill I will die on",
            "I'm going to end it all — this group chat, I mean",
            "Bài tập lớn khó muốn chết luôn",
            "Mệt muốn chết nhưng vẫn phải cố ôn thi",
            "Em cười muốn chết với cái tên đề tài",
            "Em định kết thúc tất cả — cái nhóm chat này ấy",
        ],
    )
    def test_idiom_does_not_fire(self, text):
        assert not fires(text), f"false positive on idiom: {text}"


class TestGuardsAreSpanLocal:
    """A guard must silence its own idiom, never the whole message.

    This is the property that makes guards safe to add at all: a student can
    complain about a deadline in one clause and disclose in the next.
    """

    def test_idiom_beside_a_real_disclosure_still_fires(self):
        text = (
            "This deadline is literally killing me, and honestly I have been "
            "thinking about ending my life."
        )
        assert fires(text)
        assert "explicit" in constructs(text)

    def test_vietnamese_idiom_beside_a_real_disclosure_still_fires(self):
        text = "Bài tập khó muốn chết luôn. Mà thật ra em không còn lý do gì để sống nữa."
        assert fires(text)

    def test_the_guarded_idiom_alone_is_still_silent(self):
        assert not fires("This deadline is literally killing me")


class TestPronounVersusAdjective:
    """`muốn chết` is ideation after a pronoun and hyperbole after an adjective."""

    def test_pronoun_form_is_ideation(self):
        assert fires("Em muốn chết")
        assert fires("Nhiều lúc mình muốn chết")

    def test_adjective_form_is_hyperbole(self):
        assert not fires("Đói muốn chết")
        assert not fires("Buồn ngủ muốn chết")


class TestRegressionsFromTheSupersededRule:
    """Phrases the old flat list caught must not be lost in the rewrite.

    Both of these were dropped in the first version of the pattern set and were
    caught by the Vietnamese development set, not by inspection.
    """

    @pytest.mark.parametrize(
        "text",
        [
            "Em thấy sống không còn ý nghĩa gì nữa",
            "Chắc em sẽ kết thúc tất cả trong tuần này",
        ],
    )
    def test_still_detected(self, text):
        assert fires(text)


class TestSafetyPathIntegration:
    def test_check_crisis_still_reports_the_reason_and_message(self):
        result = check_crisis(raw_text="I have been planning how to end my life")
        assert result.is_crisis
        assert "self_harm_language_in_text" in result.reasons
        assert result.matched_keywords
        assert result.message and "115" in result.message

    def test_ordinary_stress_does_not_trigger(self):
        result = check_crisis(raw_text="I am behind on every subject and sleeping badly")
        assert not result.is_crisis

    def test_empty_and_blank_text_are_safe(self):
        assert find_crisis_matches("") == []
        assert not fires("   ")
        assert not check_crisis(raw_text=None).is_crisis


class TestPatternHygiene:
    def test_every_pattern_compiles_and_is_labelled(self):
        allowed = {"explicit", "passive_wish", "existence", "burden", "preparation", "escape"}
        assert CRISIS_PATTERNS
        for construct, pattern in CRISIS_PATTERNS:
            assert construct in allowed, f"unknown construct: {construct}"
            assert pattern.pattern

    def test_matching_is_case_insensitive_and_normalised(self):
        assert fires("I WANT TO KILL MYSELF")
        assert fires("I   want   to   kill   myself")

    def test_matches_are_returned_without_duplicates(self):
        text = "I want to kill myself. I really want to kill myself."
        assert len(find_crisis_matches(normalize(text))) == len(set(find_crisis_matches(normalize(text))))
