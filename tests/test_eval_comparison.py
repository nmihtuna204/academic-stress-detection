"""Tests for the baseline-comparison pipeline (datasets, baselines, compare)."""

import asyncio
import json

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


# Passed wherever `assess` is mocked. Without it run_llm_full builds a real
# ChatOpenAI, which raises "Missing credentials" on any machine without a key -
# so these tests passed locally only because the developer's .env held one, and
# failed the moment CI ran them on a clean box. The client is never used here:
# the mocked `assess` ignores it.
STUB_LLM = object()


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
        assert _parse_label_json("Level: High") == (None, None)


class TestLlmCache:
    def test_cache_roundtrip(self, tmp_path):
        key = _cache_key({"system": "x", "text": "pressure"})
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
                reasoning="x",
                suggestions=["a", "b", "c"],
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
        result = asyncio.run(run_llm_full(small, cache_dir=tmp_path, llm=STUB_LLM))
        assert result.y_pred == ["High", "High", "High"]
        assert result.notes["ground_truth_leakage"] is True
        # Second run must be served fully from cache (no assess calls needed).
        monkeypatch.setattr(chain_module, "assess", None)  # would crash if called
        result2 = asyncio.run(run_llm_full(small, cache_dir=tmp_path, llm=STUB_LLM))
        assert result2.y_pred == result.y_pred


class TestFailuresAreRecordedAndClassified:
    """A counted failure with no artefact is a number nobody can explain.

    The 2026-09-08 run recorded 32 failures: 31 were HTTP 429 and exactly one
    was malformed JSON. Reporting all 32 as "unparseable" - which the earlier
    run's notes did - claims the model cannot hold a format when the truth was
    that the account ran out of daily tokens.
    """

    def _run_with(self, exc, tmp_path, monkeypatch):
        import app.llm.chain as chain_module
        import app.nlp.emotion as emotion_module
        import app.rag.retriever as retriever_module

        async def raising_assess(**kwargs):
            raise exc

        monkeypatch.setattr(chain_module, "assess", raising_assess)
        monkeypatch.setattr(emotion_module, "analyze", lambda text: None)
        monkeypatch.setattr(retriever_module, "retrieve", lambda q, k=4: [])
        df = build_synthetic_dataset()
        row = df[df["split"] == "test"].head(1)
        return asyncio.run(run_llm_full(row, cache_dir=tmp_path, llm=STUB_LLM))

    def test_malformed_json_counts_as_a_parse_failure(self, tmp_path, monkeypatch):
        from langchain_core.exceptions import OutputParserException

        result = self._run_with(
            OutputParserException('Invalid json output: {"confidence": 0. nine}'),
            tmp_path,
            monkeypatch,
        )
        assert result.notes["parse_failures"] == 1
        assert result.notes["rate_limited"] == 0
        assert result.y_pred == ["Moderate"]  # the documented fallback

        recorded = list((tmp_path / "_parse_failures").glob("*.json"))
        assert len(recorded) == 1
        payload = json.loads(recorded[0].read_text(encoding="utf-8"))
        assert payload["error_type"] == "OutputParserException"
        assert "0. nine" in payload["error"]
        # A failure must never be served back as if it were a result.
        assert not (tmp_path / f"{recorded[0].stem}.json").exists()

    def test_rate_limit_is_not_reported_as_unparseable(self, tmp_path, monkeypatch):
        class RateLimitError(Exception):
            pass

        result = self._run_with(
            RateLimitError("Error code: 429 - rate_limit_exceeded on tokens per day"),
            tmp_path,
            monkeypatch,
        )
        assert result.notes["rate_limited"] == 1
        assert result.notes["parse_failures"] == 0, "a 429 says nothing about the model"

    def test_unreportable_reason_names_the_dominant_cause(self, tmp_path, monkeypatch):
        class RateLimitError(Exception):
            pass

        result = self._run_with(
            RateLimitError("Error code: 429 - rate_limit_exceeded"), tmp_path, monkeypatch
        )
        reason = result.unreportable_reason()
        assert reason is not None
        assert "429" in reason
        assert "unparseable" not in reason.lower()


class TestEvalUsesProductionRetrieval:
    """The evaluated system must be the deployed system.

    `_full_one` once built its own retrieval query with the lexicon keywords
    prepended, the reverse of the shape `build_rag_query()` was measured into.
    The two produced a different top-4 chunk set on 53 % of dataset items, so
    the reported `llm_full` number came from a retrieval path the app never
    runs. Nothing caught it because nothing compared the two.
    """

    def test_full_pipeline_retrieves_with_the_production_query(self, tmp_path, monkeypatch):
        from app.api.services import build_rag_query
        from app.schemas.enums import Language, SentimentPolarity, StressLevel
        from app.schemas.models import EmotionResult, LlmAssessment

        emotion = EmotionResult(
            emotion_label="negative",
            emotion_scores={},
            sentiment_polarity=SentimentPolarity.NEGATIVE,
            stress_keywords=["pressure", "insomnia"],
            language=Language.EN,
            model_stress_level=None,
        )

        seen: list[str] = []

        async def fake_assess(**kwargs):
            return LlmAssessment(
                predicted_level=StressLevel.LOW,
                confidence=0.5,
                reasoning="x",
                suggestions=["a"],
                risk_flags=[],
            )

        import app.llm.chain as chain_module
        import app.nlp.emotion as emotion_module
        import app.rag.retriever as retriever_module

        def spy_retrieve(query, k=4):
            seen.append(query)
            return []

        monkeypatch.setattr(chain_module, "assess", fake_assess)
        monkeypatch.setattr(emotion_module, "analyze", lambda text: emotion)
        monkeypatch.setattr(retriever_module, "retrieve", spy_retrieve)

        df = build_synthetic_dataset()
        row = df[df["split"] == "test"].head(1)
        asyncio.run(run_llm_full(row, cache_dir=tmp_path, llm=STUB_LLM))

        assert len(seen) == 1
        text = str(row.iloc[0]["text"])
        assert seen[0] == build_rag_query(text, emotion, None)
        # The specific regression: keywords must not lead the query.
        assert not seen[0].startswith("pressure insomnia")


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


class TestOfflineBaselines:
    """Two comparators that need no API call, so there is no excuse for missing them."""

    def _frame(self):
        import pandas as pd

        rows = []
        for label, n in (("Low", 20), ("Moderate", 30), ("High", 20), ("Severe", 10)):
            rows += [
                {"split": "train", "label": label, "text": f"{label.lower()} sample text {i}"}
                for i in range(n)
            ]
        for label, n in (("Low", 4), ("Moderate", 6), ("High", 4), ("Severe", 2)):
            rows += [
                {"split": "test", "label": label, "text": f"{label.lower()} sample text {i}"}
                for i in range(n)
            ]
        return pd.DataFrame(rows)

    def test_majority_predicts_the_most_frequent_training_label(self):
        from app.eval.baselines import run_majority

        result = run_majority(self._frame())
        assert set(result.y_pred) == {"Moderate"}
        assert result.notes["majority_label"] == "Moderate"

    def test_majority_is_the_floor_a_system_must_clear(self):
        """Cohen's kappa of a constant predictor is 0 by definition."""
        from app.eval.baselines import run_majority
        from app.eval.evaluate import compute_metrics

        result = run_majority(self._frame())
        metrics = compute_metrics(result.y_true, result.y_pred)
        assert metrics["cohen_kappa"] == 0.0

    def test_tfidf_svm_produces_one_prediction_per_test_row(self):
        from app.eval.baselines import run_tfidf_svm

        df = self._frame()
        result = run_tfidf_svm(df)
        assert len(result.y_pred) == len(df[df["split"] == "test"])
        assert set(result.y_pred) <= {"Low", "Moderate", "High", "Severe"}


class TestPartialRunDoesNotClobber:
    """`--systems <subset>` must extend the artifact, not replace it.

    Overwriting discards results that cost real API quota to produce, which is
    how a full four-system table was reduced to two rows during development.
    """

    def test_previously_computed_systems_are_kept(self, tmp_path):
        import pandas as pd

        from app.eval.compare import _merge_with_previous

        csv = tmp_path / "comparison.csv"
        pd.DataFrame(
            [
                {"dataset": "synthetic", "system": "llm_full", "accuracy": 0.53},
                {"dataset": "synthetic", "system": "tfidf_lr", "accuracy": 0.69},
            ]
        ).to_csv(csv, index=False)

        fresh = pd.DataFrame([{"dataset": "synthetic", "system": "tfidf_svm", "accuracy": 0.66}])
        merged = _merge_with_previous(fresh, csv, "synthetic")

        assert set(merged["system"]) == {"llm_full", "tfidf_lr", "tfidf_svm"}

    def test_a_rerun_system_takes_the_fresh_number(self, tmp_path):
        import pandas as pd

        from app.eval.compare import _merge_with_previous

        csv = tmp_path / "comparison.csv"
        pd.DataFrame([{"dataset": "synthetic", "system": "tfidf_lr", "accuracy": 0.10}]).to_csv(
            csv, index=False
        )

        fresh = pd.DataFrame([{"dataset": "synthetic", "system": "tfidf_lr", "accuracy": 0.69}])
        merged = _merge_with_previous(fresh, csv, "synthetic")

        assert len(merged) == 1
        assert merged.iloc[0]["accuracy"] == 0.69

    def test_rows_from_another_dataset_are_not_mixed_in(self, tmp_path):
        import pandas as pd

        from app.eval.compare import _merge_with_previous

        csv = tmp_path / "comparison.csv"
        pd.DataFrame([{"dataset": "real", "system": "llm_full", "accuracy": 0.42}]).to_csv(
            csv, index=False
        )

        fresh = pd.DataFrame([{"dataset": "synthetic", "system": "tfidf_lr", "accuracy": 0.69}])
        merged = _merge_with_previous(fresh, csv, "synthetic")

        assert set(merged["system"]) == {"tfidf_lr"}

    def test_missing_artifact_is_not_an_error(self, tmp_path):
        import pandas as pd

        from app.eval.compare import _merge_with_previous

        fresh = pd.DataFrame([{"dataset": "synthetic", "system": "tfidf_lr", "accuracy": 0.69}])
        assert _merge_with_previous(fresh, tmp_path / "absent.csv", "synthetic").equals(fresh)
