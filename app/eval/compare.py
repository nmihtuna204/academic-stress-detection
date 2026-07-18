"""Baseline comparison runner: four systems, one split, one metric set.

Usage:
    python -m app.eval.compare --dataset synthetic
    python -m app.eval.compare --dataset synthetic --systems tfidf_lr phobert_ft
    python -m app.eval.compare --dataset real

Outputs (in data/eval/):
    comparison.csv / comparison.md   - metric table for all systems run
    confusion_<system>.png           - per-system confusion matrix
    dataset_<name>.csv               - the exact evaluated dataframe (with split)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
from pathlib import Path

import pandas as pd

from app.config import PROJECT_ROOT

logger = logging.getLogger(__name__)

ALL_SYSTEMS = ["tfidf_lr", "phobert_ft", "llm_zeroshot", "llm_full"]

STRESS_LEVELS = ["Low", "Moderate", "High", "Severe"]


def _openai_key_available() -> bool:
    """True when a plausibly real OpenAI key is configured (not the placeholder)."""
    from app.config import get_settings

    key = get_settings().openai_api_key
    return bool(key) and key != "sk-..." and len(key) > 20


def metrics_row(result) -> dict:
    """One comparison-table row (accuracy, macro-F1, per-class F1, kappa)."""
    from app.eval.evaluate import compute_metrics

    metrics = compute_metrics(result.y_true, result.y_pred)
    row = {
        "system": result.system,
        "n_test": metrics["n_samples"],
        "accuracy": metrics["accuracy"],
        "macro_f1": metrics["macro_f1"],
        "cohen_kappa": metrics["cohen_kappa"],
    }
    for level in STRESS_LEVELS:
        row[f"f1_{level.lower()}"] = round(metrics["per_class"][level]["f1-score"], 4)
    row["notes"] = "; ".join(f"{k}={v}" for k, v in result.notes.items())
    return row, metrics


def to_markdown_table(df: pd.DataFrame, dataset_name: str) -> str:
    banner = (
        f"# Baseline comparison — dataset: `{dataset_name}`\n\n"
        + (
            "> **All numbers below are computed on SYNTHETIC data** "
            "(generated text and questionnaire answers); they demonstrate the "
            "pipeline, not real-world performance.\n\n"
            if dataset_name == "synthetic"
            else ""
        )
        + "> `llm_full` receives the DASS/PSS scores from which the ground-truth label is "
        "derived, so its agreement is partly by construction (see ablation `no_questionnaire`).\n\n"
    )
    cols = ["system", "n_test", "accuracy", "macro_f1", "cohen_kappa"] + [
        f"f1_{lv.lower()}" for lv in STRESS_LEVELS
    ]
    return banner + df[cols].to_markdown(index=False) + "\n"


def run(dataset_name: str, systems: list[str], out_dir: Path | None = None) -> pd.DataFrame:
    from app.eval.baselines import (
        run_llm_full,
        run_llm_zeroshot,
        run_phobert_ft,
        run_tfidf_lr,
    )
    from app.eval.datasets import load_eval_dataset
    from app.eval.evaluate import plot_confusion_matrix

    out = out_dir or (PROJECT_ROOT / "data" / "eval")
    out.mkdir(parents=True, exist_ok=True)

    df = load_eval_dataset(dataset_name, out_dir=out)
    print(f"Dataset '{dataset_name}': {len(df)} rows "
          f"(test={len(df[df['split'] == 'test'])}), label distribution: "
          f"{df['label'].value_counts().to_dict()}")

    rows = []
    skipped: list[tuple[str, str]] = []
    for system in systems:
        print(f"\n=== Running {system} ===")
        if system.startswith("llm_") and not _openai_key_available():
            reason = "OPENAI_API_KEY missing or placeholder - set it in .env and re-run"
            print(f"SKIPPED {system}: {reason}")
            skipped.append((system, reason))
            continue
        try:
            if system == "tfidf_lr":
                result = run_tfidf_lr(df)
            elif system == "phobert_ft":
                result = run_phobert_ft(df)
            elif system == "llm_zeroshot":
                result = asyncio.run(run_llm_zeroshot(df))
            elif system == "llm_full":
                result = asyncio.run(run_llm_full(df))
            else:
                raise ValueError(f"unknown system {system!r}")
        except Exception as exc:
            print(f"SKIPPED {system}: {type(exc).__name__}: {exc}")
            skipped.append((system, f"{type(exc).__name__}: {exc}"))
            continue

        row, metrics = metrics_row(result)
        rows.append(row)
        plot_confusion_matrix(metrics["confusion_matrix"], out / f"confusion_{system}.png")
        print(f"{system}: acc={row['accuracy']:.3f} macro_f1={row['macro_f1']:.3f} "
              f"kappa={row['cohen_kappa']:.3f}")

    table = pd.DataFrame(rows)
    if not table.empty:
        table.insert(0, "dataset", dataset_name)
        table.to_csv(out / "comparison.csv", index=False)
    markdown = to_markdown_table(table, dataset_name) if not table.empty else ""
    if skipped:
        markdown += "\n**Not run** (no numbers were produced for these systems):\n\n"
        for system, reason in skipped:
            markdown += f"- `{system}` — {reason}\n"
    (out / "comparison.md").write_text(markdown, encoding="utf-8")
    print("\n" + markdown)
    print(f"Artifacts written to {out} (comparison.csv, comparison.md, confusion_*.png)")
    return table


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=["synthetic", "real"], default="synthetic")
    parser.add_argument("--systems", nargs="+", choices=ALL_SYSTEMS, default=ALL_SYSTEMS)
    parser.add_argument("--out", default=None)
    parser.add_argument(
        "--online-hub",
        action="store_true",
        help="allow HuggingFace hub downloads (default: offline, local/cached models only)",
    )
    args = parser.parse_args()

    if not args.online_hub:
        # Avoid multi-minute hangs on slow connections: local + cached models only.
        os.environ.setdefault("HF_HUB_OFFLINE", "1")

    logging.basicConfig(level=logging.WARNING)
    run(args.dataset, args.systems, Path(args.out) if args.out else None)


if __name__ == "__main__":
    main()
