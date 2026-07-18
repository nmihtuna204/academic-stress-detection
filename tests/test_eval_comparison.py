"""Tests for the baseline-comparison pipeline (datasets, baselines, compare)."""

import asyncio

import pandas as pd
import pytest

from app.eval.baselines import (
    SystemResult,
    _cache_key,
    _parse_label_json,
    cache_get,
    cache_put,
    run_llm_full,
    run_tfidf_lr,
)
from app.eval.datasets import (
    build_synthetic_dataset,
    dass_answers_from_row,
    has_questionnaire_items,
    load_eval_dataset,
    pss_answers_from_row,
)


class TestDatasets:
    def test_synthetic_dataset_schema(self):
        df = build_synthetic_dataset()
        assert len(df) == 466
        assert set(df["split"].unique()) == {"train", "val", "test"}
        assert set(df["label"].unique()) <= {"Low", "Moderate", "High", "Severe"}
        assert has_questionnaire_items(df)

    def test_split_is_frozen(self):
        # The split must come from the frozen research split file, not be redrawn.
        df1 = build_synthetic_dataset()
        df2 = build_synthetic_dataset()
        assert (df1["split"] == df2["split"]).all()
        assert len(df1[df1["split"] == "test"]) == 70

    def test_answers_from_row(self):
        df = build_synthetic_dataset()
        row = df.iloc[0]
        dass = dass_answers_from_row(row)
        pss = pss_answers_from_row(row)
        assert set(dass.keys()) == set(range(1, 22))
        assert all(0 <= v <= 3 for v in dass.values())
        assert set(pss.keys()) == set(range(1, 11))
        assert all(0 <= v <= 4 for v in pss.values())

    def test_load_writes_dataset_copy(self, tmp_path):
        load_eval_dataset("synthetic", out_dir=tmp_path)
        assert (tmp_path / "dataset_synthetic.csv").exists()

    def test_unknown_dataset_rejected(self):
        with pytest.raises(ValueError):
            load_eval_dataset("bogus")

    def test_real_dataset_missing_gives_clear_error(self, monkeypatch, tmp_path):
        from app.eval import datasets

        monkeypatch.setattr(datasets, "REAL_DATASET_PATH", tmp_path / "nope.csv")
        with pytest.raises(FileNotFoundError, match="export_dataset"):
            load_eval_dataset("real", out_dir=tmp_path)


class TestTfidfBaseline:
    def test_runs_on_synthetic_dataset(self):
        df = build_synthetic_dataset()
        result = run_tfidf_lr(df)
        assert result.system == "tfidf_lr"
        assert len(result.y_pred) == len(result.y_true) == 70
        assert set(result.y_pred) <= {"Low", "Moderate", "High", "Severe"}

    def test_deterministic(self):
        df = build_synthetic_dataset()
        assert run_tfidf_lr(df).y_pred == run_tfidf_lr(df).y_pred


class TestLlmParsing:
    def test_parses_clean_json(self):
        label, conf = _parse_label_json('{"label": "High", "confidence": 0.8}')
        assert label == "High" and conf == 0.8

    def test_parses_fenced_json(self):
        label, _ = _parse_label_json('```json\n{"label": "Low", "confidence": 0.9}\n```')
        assert label == "Low"

    def test_rejects_bad_label(self):
        assert _parse_label_json('{"label": "Extreme"}') == (None, None)

    def test_rejects_non_json(self):
        assert _parse_label_json("Mức độ: High") == (None, None)


class TestLlmCache:
    def test_cache_roundtrip(self, tmp_path):
        key = _cache_key({"system": "x", "text": "áp lực"})
        assert cache_get(tmp_path, key) is None
        cache_put(tmp_path, key, {"label": "High"})
        assert cache_get(tmp_path, key)["label"] == "High"

    def test_key_is_deterministic_and_input_sensitive(self):
        a = _cache_key({"text": "a", "system": "s"})
        b = _cache_key({"system": "s", "text": "a"})  # key order must not matter
        c = _cache_key({"system": "s", "text": "b"})
        assert a == b
        assert a != c


class TestLlmFullMocked:
    def test_pipeline_with_mocked_chain(self, tmp_path, monkeypatch):
        """llm_full plumbing works end-to-end with the LLM and NLP mocked."""
        from app.schemas.enums import StressLevel
        from app.schemas.models import LlmAssessment

        async def fake_assess(**kwargs):
            # Echo the questionnaire-informed level to check plumbing.
            level = "High" if kwargs["dass_result"] else "Low"
            return LlmAssessment(
                predicted_level=StressLevel(level),
                confidence=0.9,
                reasoning_vi="x",
                suggestions_vi=["a", "b", "c"],
                risk_flags=[],
            )

        import app.llm.chain as chain_module
        import app.nlp.emotion as emotion_module
        import app.rag.retriever as retriever_module

        monkeypatch.setattr(chain_module, "assess", fake_assess)
        monkeypatch.setattr(emotion_module, "analyze", lambda text: None)
        monkeypatch.setattr(retriever_module, "retrieve", lambda q, k=4: [])

        df = build_synthetic_dataset()
        small = pd.concat([df[df["split"] == "test"].head(3)])
        result = asyncio.run(run_llm_full(small, cache_dir=tmp_path))
        assert result.y_pred == ["High", "High", "High"]
        assert result.notes["ground_truth_leakage"] is True
        # Second run must be served fully from cache (no assess calls needed).
        monkeypatch.setattr(chain_module, "assess", None)  # would crash if called
        result2 = asyncio.run(run_llm_full(small, cache_dir=tmp_path))
        assert result2.y_pred == result.y_pred


class TestCompare:
    def test_metrics_row_shape(self):
        from app.eval.compare import metrics_row

        result = SystemResult(
            system="dummy",
            y_true=["Low", "High", "Moderate", "Severe"],
            y_pred=["Low", "High", "High", "Severe"],
        )
        row, metrics = metrics_row(result)
        assert row["system"] == "dummy"
        assert 0 < row["accuracy"] <= 1
        assert "f1_severe" in row
        assert len(metrics["confusion_matrix"]) == 4
