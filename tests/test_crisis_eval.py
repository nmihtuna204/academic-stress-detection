"""Tests for the crisis-rule evaluation harness."""

from app.eval.crisis_eval import (
    DEFAULT_TESTSET,
    Item,
    evaluate,
    format_report,
    load_testset,
    predict,
)


class TestTestset:
    def test_loads_50_items(self):
        items = load_testset()
        assert len(items) == 50
        assert len({i.id for i in items}) == 50  # unique ids

    def test_label_balance(self):
        items = load_testset()
        positives = sum(1 for i in items if i.expected)
        negatives = sum(1 for i in items if not i.expected)
        assert 20 <= positives <= 26
        assert 24 <= negatives <= 30

    def test_borderline_items_have_notes(self):
        items = load_testset()
        borderline = [i for i in items if i.category == "borderline"]
        assert len(borderline) == 10
        assert all(i.note for i in borderline)

    def test_testset_is_committed(self):
        # The testset is source data and must not be swallowed by data/eval/ ignore.
        import subprocess

        result = subprocess.run(
            ["git", "check-ignore", str(DEFAULT_TESTSET)],
            capture_output=True,
            cwd=DEFAULT_TESTSET.parent,
        )
        assert result.returncode != 0, "crisis_testset.jsonl must NOT be gitignored"


class TestPredict:
    def test_explicit_text_predicts_crisis(self):
        assert predict(Item(id=0, text="em muốn tự tử", expected=True, category="x"))

    def test_neutral_text_predicts_no_crisis(self):
        assert not predict(Item(id=0, text="em hơi mệt vì ôn thi", expected=False, category="x"))

    def test_partial_dass_items_use_maximal_rule_only(self):
        item = Item(id=0, text="mệt", expected=True, category="x", dass_items={17: 3, 21: 3})
        assert predict(item)
        item2 = Item(id=0, text="mệt", expected=False, category="x", dass_items={17: 2, 21: 2})
        assert not predict(item2)


class TestEvaluate:
    def test_metrics_math(self):
        items = [
            Item(id=1, text="em muốn tự tử", expected=True, category="tp"),        # TP
            Item(id=2, text="trời đẹp quá", expected=False, category="neg"),       # TN
            Item(id=3, text="mệt muốn chết luôn", expected=False, category="neg"), # FP
            Item(id=4, text="em là gánh nặng của mọi người", expected=True, category="tp"),  # FN
        ]
        results = evaluate(items)
        assert (results["tp"], results["fp"], results["fn"], results["tn"]) == (1, 1, 1, 1)
        assert results["precision"] == 0.5
        assert results["recall"] == 0.5

    def test_report_lists_every_error_verbatim(self):
        items = [
            Item(id=3, text="mệt muốn chết luôn", expected=False, category="neg"),
            Item(id=4, text="em là gánh nặng của mọi người", expected=True, category="tp",
                 note="passive marker"),
        ]
        report = format_report(evaluate(items))
        assert "mệt muốn chết luôn" in report
        assert "gánh nặng" in report
        assert "passive marker" in report

    def test_full_testset_runs(self):
        results = evaluate(load_testset())
        assert results["n"] == 50
        # Sanity: the rule must at least catch all explicit phrasing.
        explicit_misses = [
            i for i in results["false_negatives"] if i.category == "explicit_tp"
        ]
        assert explicit_misses == []
