"""Tests for the crisis-rule evaluation harness."""

from app.config import PROJECT_ROOT
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


class TestEnglishTestset:
    """The English set exists because the app stopped being Vietnamese.

    The application was converted to English on 2026-09-05. The crisis lexicon
    is bilingual, but every published precision/recall figure came from 50
    Vietnamese items, so the half of the rule that real users now exercise had
    never been measured.
    """

    PATH = PROJECT_ROOT / "data" / "eval" / "crisis_testset_en.jsonl"

    def test_it_is_committed(self):
        """Hand-written source data, not a derived artefact - it must be in git."""
        assert self.PATH.exists(), "English crisis test set is missing"

    def test_shape_matches_the_vietnamese_set(self):
        items = load_testset(self.PATH)
        assert len(items) == 50
        assert sum(1 for i in items if i.expected) == 24
        assert sum(1 for i in items if not i.expected) == 26

    def test_borderline_items_carry_their_rationale(self):
        items = load_testset(self.PATH)
        borderline = [i for i in items if i.category == "borderline"]
        assert borderline
        assert all(i.note for i in borderline), "a borderline label without a reason is not a label"

    def test_it_is_not_a_translation_of_the_published_set(self):
        """A translated set is not held-out.

        Twelve false negatives of the Vietnamese set are published verbatim in
        the report. If the English set were those same items translated, using
        it to validate an expanded lexicon would be tuning against known
        failures rather than measuring on unseen ones.
        """
        vi = {i.text.strip().lower() for i in load_testset()}
        en = {i.text.strip().lower() for i in load_testset(self.PATH)}
        assert not (vi & en)

    def test_lethal_sounding_idiom_is_represented(self):
        """Precision in English is only meaningful if the hard negatives are hard."""
        items = load_testset(self.PATH)
        negatives = " ".join(i.text.lower() for i in items if not i.expected)
        for idiom in ("killing me", "shoot me now", "rather die", "murdered me"):
            assert idiom in negatives, f"missing hard negative: {idiom}"


class TestPredict:
    def test_explicit_text_predicts_crisis(self):
        assert predict(Item(id=0, text="I want to kill myself", expected=True, category="x"))

    def test_neutral_text_predicts_no_crisis(self):
        assert not predict(Item(id=0, text="I am a bit tired from revising", expected=False, category="x"))

    def test_partial_dass_items_use_maximal_rule_only(self):
        item = Item(id=0, text="tired", expected=True, category="x", dass_items={17: 3, 21: 3})
        assert predict(item)
        item2 = Item(id=0, text="tired", expected=False, category="x", dass_items={17: 2, 21: 2})
        assert not predict(item2)


class TestEvaluate:
    def test_metrics_math(self):
        items = [
            Item(id=1, text="I want to kill myself", expected=True, category="tp"),        # TP
            Item(id=2, text="the weather is lovely today", expected=False, category="neg"),       # TN
            Item(id=3, text="this homework makes me want to die", expected=False, category="neg"), # FP
            # A genuine false negative: real intent carried with no crisis
            # vocabulary at all, which is the limit of any lexical rule. The
            # previous fixture used "I feel like a burden to everyone", which
            # the construct-based rule now detects - a fixture must not encode
            # a defect the rule has since fixed.
            Item(id=4, text="I have made my decision and I am at peace with it now",
                 expected=True, category="tp"),  # FN
        ]
        results = evaluate(items)
        assert (results["tp"], results["fp"], results["fn"], results["tn"]) == (1, 1, 1, 1)
        assert results["precision"] == 0.5
        assert results["recall"] == 0.5

    def test_report_lists_every_error_verbatim(self):
        items = [
            Item(id=3, text="this homework makes me want to die", expected=False, category="neg"),
            Item(id=4, text="I have made my decision and I am at peace with it now",
                 expected=True, category="tp", note="passive marker"),
        ]
        report = format_report(evaluate(items))
        assert "makes me want to die" in report
        assert "at peace with it now" in report
        assert "passive marker" in report

    def test_full_testset_runs(self):
        results = evaluate(load_testset())
        assert results["n"] == 50
        # Sanity: the rule must at least catch all explicit phrasing.
        explicit_misses = [
            i for i in results["false_negatives"] if i.category == "explicit_tp"
        ]
        assert explicit_misses == []
