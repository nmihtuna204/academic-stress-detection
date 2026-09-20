"""Tests for the ablation study (LLM mocked; no network)."""

import pandas as pd

from app.eval.ablation import CONFIGS, interpret, plot, run


class TestConfigs:
    def test_five_required_configs(self):
        assert set(CONFIGS) == {"full", "no_rag", "no_questionnaire", "no_emotion", "text_only"}

    def test_full_has_everything_on_text_only_everything_off(self):
        assert CONFIGS["full"] == (True, True, True)
        assert CONFIGS["text_only"] == (False, False, False)


class TestInterpretation:
    def make_table(self):
        return pd.DataFrame(
            [
                {"config": "full", "accuracy": 0.80, "macro_f1": 0.78, "cohen_kappa": 0.70},
                {"config": "no_rag", "accuracy": 0.79, "macro_f1": 0.77, "cohen_kappa": 0.69},
                {"config": "no_questionnaire", "accuracy": 0.60, "macro_f1": 0.55, "cohen_kappa": 0.45},
            ]
        )

    def test_interpretation_mentions_each_removed_component(self):
        text = interpret(self.make_table())
        assert "RAG retrieval" in text
        assert "questionnaire" in text
        assert "0.230" in text  # 0.78 - 0.55 delta appears

    def test_interpretation_flags_leakage_caveat(self):
        assert "leakage" in interpret(self.make_table())

    def test_empty_table_says_not_run(self):
        assert "not produced results" in interpret(pd.DataFrame())


class TestPlot:
    def test_writes_png(self, tmp_path):
        table = pd.DataFrame(
            [
                {"config": "full", "accuracy": 0.8, "macro_f1": 0.78},
                {"config": "text_only", "accuracy": 0.6, "macro_f1": 0.55},
            ]
        )
        out = tmp_path / "ablation.png"
        plot(table, out)
        assert out.exists() and out.stat().st_size > 1000


class TestRunWithoutKey:
    def test_skips_cleanly_without_key(self, tmp_path, monkeypatch):
        from app.eval import compare

        monkeypatch.setattr(compare, "_openai_key_available", lambda: False)
        table = run("synthetic", list(CONFIGS), out_dir=tmp_path)
        assert table.empty
        content = (tmp_path / "ablation.md").read_text(encoding="utf-8")
        assert "NOT RUN" in content


class TestRunMocked:
    def test_run_produces_deltas_and_artifacts(self, tmp_path, monkeypatch):
        """End-to-end ablation with the LLM engine mocked per-config."""
        import app.eval.ablation as ablation_module
        from app.eval import compare
        from app.eval.baselines import SystemResult

        monkeypatch.setattr(compare, "_openai_key_available", lambda: True)

        fake_quality = {"full": 1.0, "no_rag": 0.9, "text_only": 0.5}

        async def fake_run_llm_full(df, use_rag=True, use_questionnaire=True,
                                    use_emotion=True, system_id="llm_full", **kwargs):
            test = df[df["split"] == "test"]
            y_true = test["label"].tolist()
            quality = fake_quality[system_id]
            # Degrade predictions deterministically with config quality.
            y_pred = [t if i / len(y_true) < quality else "Low" for i, t in enumerate(y_true)]
            return SystemResult(system=system_id, y_true=y_true, y_pred=y_pred)

        import app.eval.baselines as baselines_module

        monkeypatch.setattr(baselines_module, "run_llm_full", fake_run_llm_full)

        table = ablation_module.run("synthetic", ["full", "no_rag", "text_only"], out_dir=tmp_path)
        assert len(table) == 3
        full_acc = table.loc[table["config"] == "full", "accuracy"].iloc[0]
        text_only_delta = table.loc[table["config"] == "text_only", "delta_accuracy"].iloc[0]
        assert full_acc == 1.0
        assert text_only_delta < 0
        assert (tmp_path / "ablation.csv").exists()
        assert (tmp_path / "ablation.png").exists()
        assert "Interpretation" in (tmp_path / "ablation.md").read_text(encoding="utf-8")


class TestSubsampleTestSplit:
    """`--limit` trades statistical power for quota. It must not trade validity.

    An ablation is a paired comparison, so every configuration has to see the
    same items. The subsample therefore happens once before any config runs, is
    seeded, and is stratified so no class is reduced to noise.
    """

    def _frame(self):
        import pandas as pd

        rows = []
        for label, n in (("Low", 16), ("Moderate", 23), ("High", 22), ("Severe", 9)):
            rows += [{"split": "test", "label": label, "text": f"{label}{i}"} for i in range(n)]
        rows += [{"split": "train", "label": "Low", "text": f"tr{i}"} for i in range(30)]
        return pd.DataFrame(rows)

    def test_cuts_the_test_split_to_about_the_limit(self):
        from app.eval.ablation import subsample_test_split

        out = subsample_test_split(self._frame(), 35)
        assert len(out[out["split"] == "test"]) == 35

    def test_leaves_the_train_split_untouched(self):
        from app.eval.ablation import subsample_test_split

        df = self._frame()
        out = subsample_test_split(df, 35)
        assert len(out[out["split"] == "train"]) == len(df[df["split"] == "train"])

    def test_every_class_survives(self):
        """An unstratified cut can erase the smallest class entirely."""
        from app.eval.ablation import subsample_test_split

        out = subsample_test_split(self._frame(), 25)
        test = out[out["split"] == "test"]
        assert set(test["label"]) == {"Low", "Moderate", "High", "Severe"}

    def test_is_deterministic_so_configs_see_identical_items(self):
        from app.eval.ablation import subsample_test_split

        df = self._frame()
        first = subsample_test_split(df, 35).index.tolist()
        second = subsample_test_split(df, 35).index.tolist()
        assert first == second

    def test_limit_at_or_above_the_split_size_is_a_no_op(self):
        from app.eval.ablation import subsample_test_split

        df = self._frame()
        assert subsample_test_split(df, 70).equals(df)
        assert subsample_test_split(df, 999).equals(df)


class TestNoiseAwareInterpretation:
    """A delta smaller than sampling noise must not be given a direction.

    Before this guard the generated paragraph said "removing the emotion
    features IMPROVES macro-F1 by 0.059" at n=40, where the 95% Wilson interval
    is +/-0.148. The number was real; the word "IMPROVES" was not supported.
    """

    def _table(self, full_f1: float, other_f1: float, config: str = "no_emotion"):
        import pandas as pd

        return pd.DataFrame(
            [
                {"config": "full", "accuracy": 0.5, "macro_f1": full_f1, "cohen_kappa": 0.3},
                {"config": config, "accuracy": 0.5, "macro_f1": other_f1, "cohen_kappa": 0.3},
            ]
        )

    def test_noise_floor_shrinks_with_sample_size(self):
        from app.eval.ablation import noise_floor

        assert noise_floor(40) > noise_floor(70) > noise_floor(500)
        assert noise_floor(0) == float("inf")

    def test_small_delta_is_not_given_a_direction(self):
        from app.eval.ablation import interpret

        text = interpret(self._table(0.534, 0.593), n_used=40)
        assert "INSIDE" in text and "cannot be distinguished" in text
        assert "IMPROVES" not in text

    def test_large_delta_still_reads_directionally(self):
        from app.eval.ablation import interpret

        text = interpret(self._table(0.534, 0.123, config="no_questionnaire"), n_used=40)
        assert "drops" in text
        assert "INSIDE" not in text

    def test_without_a_sample_size_it_stays_silent_about_noise(self):
        from app.eval.ablation import interpret

        text = interpret(self._table(0.534, 0.593))
        assert "sampling-noise floor" not in text


class TestUnreportableResults:
    """A run whose replies mostly failed must not be published as a number.

    Real incident: a daily quota ran out mid-ablation, four configurations
    returned 30/30 unparseable replies, every one fell back to a fixed label,
    and the harness reported accuracy 0.333 — numerically identical to the
    majority-class baseline and indistinguishable from a real result.
    """

    def _result(self, failures: int, n: int = 30):
        from app.eval.baselines import SystemResult

        return SystemResult(
            system="full",
            y_true=["Low"] * n,
            y_pred=["Moderate"] * n,
            notes={"parse_failures": failures},
        )

    def test_total_failure_is_refused(self):
        assert self._result(30).unreportable_reason() is not None

    def test_a_clean_run_is_reportable(self):
        assert self._result(0).unreportable_reason() is None

    def test_a_few_failures_are_tolerated_and_reported(self):
        """Some noise is acceptable and is disclosed via notes, not suppressed."""
        assert self._result(3).unreportable_reason() is None

    def test_the_threshold_is_where_it_is_documented(self):
        from app.eval.baselines import MAX_TOLERABLE_FAILURE_RATE

        n = 30
        just_over = int(n * MAX_TOLERABLE_FAILURE_RATE) + 1
        just_under = int(n * MAX_TOLERABLE_FAILURE_RATE)
        assert self._result(just_over, n).unreportable_reason() is not None
        assert self._result(just_under, n).unreportable_reason() is None

    def test_the_reason_names_the_cause(self):
        """The message has to tell the reader why, not just that.

        `_result` builds a parse-failure-only result, so the reason must name
        the parser specifically. It deliberately no longer says "unparseable"
        for every cause: a rate-limit refusal produces the same fallback label
        but means the request never reached the model.
        """
        reason = self._result(30).unreportable_reason()
        assert "parser rejected as malformed" in reason
        assert "30/30" in reason

    def test_systems_without_a_failure_count_are_unaffected(self):
        """Offline baselines report no parse_failures and must stay reportable."""
        from app.eval.baselines import SystemResult

        result = SystemResult(
            system="tfidf_lr", y_true=["Low"], y_pred=["Low"], notes={"train_size": 300}
        )
        assert result.unreportable_reason() is None
