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
