"""Paired re-analysis of the published baseline comparison (docs/RESULTS.md §2).

The comparison scores six systems on the same 70 test items, so every pairwise
comparison is paired. docs/RESULTS.md §2 judged them against a single-proportion
"noise floor" (±0.117 at n = 70) and called the full system's lead over
zero-shot "clear". This tests those statements properly.

ANALYSIS PLAN - fixed here before any number below was computed; reported
whatever it shows; POST HOC relative to the published comparison:

  Primary:     llm_full against each of the other five systems, difference in
               accuracy, exact McNemar, Holm-corrected across the five, alpha 0.05.
  Descriptive: difference in quadratic-weighted kappa, paired bootstrap 95 % CI.

VALIDITY. The published predictions are read back, not regenerated:
- llm_full from the LLM cache under `full_cache_key` with support pinning
  switched off, because the published row predates pinning (2026-09-20);
- llm_zeroshot from its own cache key;
- the offline systems by re-running them (deterministic, seed 42).
Any LLM cache miss would be a request to the provider, so a stub client that
raises is passed in and every miss surfaces as a failure. All six rows must
reproduce the published table exactly, or the script stops.

Usage:
    python scripts/comparison_paired.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("HF_HUB_OFFLINE", "1")

import pandas as pd  # noqa: E402

import app.api.services as services  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.eval import baselines  # noqa: E402
from app.eval.ablation import paired_comparison  # noqa: E402
from app.eval.datasets import load_eval_dataset  # noqa: E402
from app.eval.evaluate import compute_metrics  # noqa: E402

PUBLISHED = {  # docs/RESULTS.md §2: accuracy, macro-F1, kappa
    "tfidf_lr": (0.6857, 0.6816, 0.5807),
    "phobert_ft": (0.6571, 0.5329, 0.5156),
    "majority": (0.3286, 0.1237, 0.0),
    "tfidf_svm": (0.6571, 0.6524, 0.5424),
    "llm_zeroshot": (0.5286, 0.5238, 0.3892),
    "llm_full": (0.6714, 0.6495, 0.5764),
}


class _NoCalls:
    """Stands in for the LLM client: a cache miss must fail, not spend quota."""

    async def ainvoke(self, *_args, **_kwargs):
        raise RuntimeError("cache miss - this script makes no provider calls")


def _zeroshot(test: pd.DataFrame) -> list[str]:
    settings = get_settings()
    labels = []
    for text in test["text"].astype(str):
        key = baselines._cache_key({
            "system": "llm_zeroshot",
            "model": settings.openai_model,
            "endpoint": settings.openai_base_url,
            "text": text,
        })
        hit = baselines.cache_get(baselines.DEFAULT_CACHE_DIR, key)
        if hit is None:
            raise SystemExit("llm_zeroshot: a published prediction is missing from the cache")
        labels.append(hit["label"])
    return labels


def main() -> int:
    df = load_eval_dataset("synthetic", out_dir=Path("data/eval"))
    test = df[df["split"] == "test"]
    y_true = test["label"].tolist()

    predictions = {
        "tfidf_lr": baselines.run_tfidf_lr(df).y_pred,
        "phobert_ft": baselines.run_phobert_ft(df).y_pred,
        "majority": baselines.run_majority(df).y_pred,
        "tfidf_svm": baselines.run_tfidf_svm(df).y_pred,
        "llm_zeroshot": _zeroshot(test),
    }
    # The published llm_full row predates support pinning: with pinning off,
    # full_cache_key yields exactly the keys that run used.
    original = services.needs_support_material
    services.needs_support_material = lambda *_a, **_k: False
    try:
        result = asyncio.run(baselines.run_llm_full(df, llm=_NoCalls()))
    finally:
        services.needs_support_material = original
    if result.notes.get("unusable"):
        raise SystemExit(f"llm_full: {result.notes['unusable']} predictions were not in the cache")
    predictions["llm_full"] = result.y_pred

    for system, labels in predictions.items():
        m = compute_metrics(y_true, labels)
        got = (m["accuracy"], m["macro_f1"], m["cohen_kappa"])
        if any(abs(g - p) > 1e-4 for g, p in zip(got, PUBLISHED[system], strict=True)):
            raise SystemExit(f"VALIDITY FAILED for {system}: {got} vs published {PUBLISHED[system]}")
    print(f"Validity: all six systems reproduce the published §2 table on {len(y_true)} items.\n")

    table = paired_comparison(y_true, predictions, reference="llm_full")
    shown = table.assign(
        delta_qwk_95ci=[f"[{lo:+.3f}, {hi:+.3f}]"
                        for lo, hi in zip(table["delta_qwk_ci_low"], table["delta_qwk_ci_high"], strict=True)]
    )[["config", "reference_only_correct", "other_only_correct", "delta_accuracy",
       "mcnemar_p", "mcnemar_p_holm", "significant", "delta_qwk", "delta_qwk_95ci"]]
    shown = shown.rename(columns={
        "config": "system", "reference_only_correct": "llm_full_only_correct",
        "other_only_correct": "system_only_correct",
    })
    print("llm_full against each system. delta = system - llm_full.")
    print("Primary: exact McNemar, Holm across 5. Descriptive: delta QWK, paired bootstrap 95% CI.\n")
    print(shown.to_markdown(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
