"""Agreement evaluation: LLM predicted label vs questionnaire ground truth.

Reads the `predictions` table (rows where both labels are present), computes
accuracy, macro-F1, Cohen's kappa and a per-class report, and writes a
confusion-matrix PNG plus a metrics JSON to `data/eval/`.

Usage:
    python -m app.eval.evaluate [--out data/eval]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from sqlalchemy import select

from app.config import PROJECT_ROOT
from app.db.database import get_session, init_db
from app.db.models import Prediction

STRESS_LEVELS = ["Low", "Moderate", "High", "Severe"]
LEVEL_LABELS_VI = {"Low": "Thấp", "Moderate": "Trung bình", "High": "Cao", "Severe": "Rất cao"}


def load_label_pairs() -> tuple[list[str], list[str]]:
    """Return (ground_truth, predicted) label lists from the predictions table."""
    init_db()
    session = next(get_session())
    try:
        rows = session.scalars(
            select(Prediction).where(
                Prediction.ground_truth_label.is_not(None),
                Prediction.llm_predicted_label.is_not(None),
            )
        ).all()
        return (
            [r.ground_truth_label for r in rows],
            [r.llm_predicted_label for r in rows],
        )
    finally:
        session.close()


def compute_metrics(y_true: list[str], y_pred: list[str]) -> dict:
    from sklearn.metrics import (
        accuracy_score,
        classification_report,
        cohen_kappa_score,
        confusion_matrix,
        f1_score,
    )

    return {
        "n_samples": len(y_true),
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "macro_f1": round(float(f1_score(y_true, y_pred, labels=STRESS_LEVELS, average="macro", zero_division=0)), 4),
        "cohen_kappa": round(float(cohen_kappa_score(y_true, y_pred, labels=STRESS_LEVELS)), 4),
        "per_class": classification_report(
            y_true, y_pred, labels=STRESS_LEVELS, output_dict=True, zero_division=0
        ),
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=STRESS_LEVELS).tolist(),
    }


def plot_confusion_matrix(matrix: list[list[int]], out_path: Path) -> None:
    """Single-hue sequential heatmap with direct cell annotations."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    data = np.array(matrix)
    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    im = ax.imshow(data, cmap="Blues")

    tick_labels = [f"{lv}\n({LEVEL_LABELS_VI[lv]})" for lv in STRESS_LEVELS]
    ax.set_xticks(range(len(STRESS_LEVELS)), tick_labels)
    ax.set_yticks(range(len(STRESS_LEVELS)), tick_labels)
    ax.set_xlabel("LLM predicted label")
    ax.set_ylabel("Ground truth (DASS-21 / PSS-10)")
    ax.set_title("LLM vs questionnaire ground truth")

    threshold = data.max() / 2 if data.max() > 0 else 0.5
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            ax.text(
                j, i, str(data[i, j]),
                ha="center", va="center", fontsize=12,
                color="white" if data[i, j] > threshold else "#1a1a19",
            )
    fig.colorbar(im, ax=ax, shrink=0.8, label="count")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def run(out_dir: str | Path | None = None) -> dict:
    """Compute metrics from the DB and write artifacts; returns the metrics."""
    y_true, y_pred = load_label_pairs()
    if not y_true:
        raise SystemExit(
            "No prediction rows with both labels found. "
            "Seed synthetic data first: python -m app.eval.synthetic --rows 200"
        )

    metrics = compute_metrics(y_true, y_pred)

    out = Path(out_dir) if out_dir else PROJECT_ROOT / "data" / "eval"
    out.mkdir(parents=True, exist_ok=True)
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    plot_confusion_matrix(metrics["confusion_matrix"], out / "confusion_matrix.png")
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=None, help="output directory (default: data/eval)")
    args = parser.parse_args()

    results = run(args.out)
    print(f"Samples:      {results['n_samples']}")
    print(f"Accuracy:     {results['accuracy']:.3f}")
    print(f"Macro-F1:     {results['macro_f1']:.3f}")
    print(f"Cohen kappa:  {results['cohen_kappa']:.3f}")
    print("Confusion matrix (rows=truth, cols=pred, order Low/Moderate/High/Severe):")
    for row in results["confusion_matrix"]:
        print("  ", row)
    print("Artifacts written to data/eval/ (metrics.json, confusion_matrix.png)")
