"""Parsing the author's label review: what is ticked, unticked and added must land exactly."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from apply_query_review import parse_review  # noqa: E402

DECISION = """## One decision before the run

- [{keep}] Keep the pre-registered definition: `01::3` or any `03::*`
- [{extend}] Also count `02::3` and `05::2`

## Rows to review
"""


def _review(body: str, keep: str = "x", extend: str = " ") -> str:
    return DECISION.format(keep=keep, extend=extend) + body + "\n## When you are done\n"


def test_ticked_kept_unticked_dropped_and_added_included():
    labels, definition = parse_review(_review(
        "### Query 58 · en\n\n> text\n\n"
        "- [x] `01::2` Signs — R3\n"
        "- [ ] `01::3` When to seek help — R1\n"
        "- [X] `03::1` Counselling — R2\n\n"
        "Add: 02::3 04::1\n"
    ))
    assert definition == "preregistered"
    assert labels[58] == {
        "01_academic_stress.md::2",
        "03_support_resources_vietnam.md::1",
        "02_coping_strategies.md::3",
        "04_sleep_and_study.md::1",
    }


def test_an_empty_add_line_adds_nothing():
    labels, _ = parse_review(_review("### Query 61 · en\n\n- [x] `01::3` x\n\nAdd:\n"))
    assert labels == {61: {"01_academic_stress.md::3"}}


def test_the_extended_definition_is_read():
    _, definition = parse_review(_review("### Query 58\n\n- [x] `01::3` x\n\nAdd:\n", keep=" ", extend="x"))
    assert definition == "extended"


@pytest.mark.parametrize("keep, extend", [("x", "x"), (" ", " ")])
def test_exactly_one_definition_must_be_ticked(keep, extend):
    with pytest.raises(ValueError, match="exactly one"):
        parse_review(_review("### Query 58\n\n- [x] `01::3` x\n\nAdd:\n", keep=keep, extend=extend))


def test_a_query_left_with_no_label_is_refused():
    with pytest.raises(ValueError, match="query 58 has no relevant chunk"):
        parse_review(_review("### Query 58\n\n- [ ] `01::3` x\n\nAdd:\n"))


def test_an_unknown_file_prefix_is_refused():
    with pytest.raises(ValueError, match="09::1"):
        parse_review(_review("### Query 58\n\n- [x] `01::3` x\n\nAdd: 09::1\n"))
