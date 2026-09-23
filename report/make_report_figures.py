"""Render every data figure used by the HCMIU LaTeX report.

Numbers come from the artefacts in data/eval/ and phobert_run.log. Two figures
are recomputed rather than copied (TF-IDF confusion matrix, nearest-neighbour
leakage distribution); the script prints the headline value of each so it can
be checked against docs/RESULTS.md before the figure is trusted.

Usage:
    python report/make_report_figures.py
Output:
    report/latex/images/fig_*.png
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
EVAL = ROOT / "data" / "eval"
OUT = ROOT / "report" / "latex" / "images"
OUT.mkdir(parents=True, exist_ok=True)

LEVELS = ["Low", "Moderate", "High", "Severe"]
# Ordinal single-hue ramp for stress levels (light -> dark).
RAMP = ["#BFD4F2", "#7FA8E0", "#3F73C4", "#1C3F7A"]
INK = "#1E293B"
MUTED = "#64748B"
GRID = "#E2E8F0"
ACCENT = "#2F63BD"
WARN = "#B45309"
BAD = "#B3261E"
GOOD = "#2E7D32"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.edgecolor": MUTED,
    "axes.labelcolor": INK,
    "axes.titlesize": 11,
    "axes.titleweight": "bold",
    "axes.titlecolor": INK,
    "xtick.color": INK,
    "ytick.color": INK,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "savefig.dpi": 220,
    "savefig.bbox": "tight",
    "figure.facecolor": "white",
})


def save(fig, name: str) -> None:
    fig.savefig(OUT / name)
    plt.close(fig)
    print(f"  wrote {name}")


def label_bars(ax, bars, fmt="{:.3f}", pad=0.01, horizontal=False):
    for b in bars:
        if horizontal:
            w = b.get_width()
            ax.text(w + pad, b.get_y() + b.get_height() / 2, fmt.format(w), va="center", fontsize=8.5, color=INK)
        else:
            h = b.get_height()
            ax.text(b.get_x() + b.get_width() / 2, h + pad, fmt.format(h), ha="center", va="bottom", fontsize=8, color=INK)


# ---------------------------------------------------------------- dataset
def fig_label_distribution(df: pd.DataFrame) -> None:
    splits = ["train", "val", "test"]
    counts = df.groupby(["split", "label"]).size().unstack(fill_value=0).reindex(index=splits, columns=LEVELS)
    print("  label counts per split:\n", counts.to_string())
    fig, ax = plt.subplots(figsize=(7, 3.6))
    x = np.arange(len(splits))
    w = 0.2
    for i, lvl in enumerate(LEVELS):
        bars = ax.bar(x + (i - 1.5) * w, counts[lvl], w, color=RAMP[i], label=lvl, edgecolor="white")
        label_bars(ax, bars, fmt="{:.0f}", pad=1)
    ax.set_xticks(x, [f"{s}\n(n = {counts.loc[s].sum()})" for s in splits])
    ax.set_ylabel("Number of items")
    ax.set_title("Unified four-class label distribution across the frozen splits")
    ax.legend(frameon=False, ncol=4, loc="upper right")
    ax.yaxis.grid(True, color=GRID)
    ax.set_axisbelow(True)
    save(fig, "fig_label_distribution.png")


def fig_training_curves() -> None:
    log = (ROOT / "phobert_run.log").read_text(encoding="utf-8", errors="ignore")
    rows = re.findall(r"epoch (\d+)/\d+\s+train_loss=([\d.]+)\s+val_macroF1=([\d.]+)", log)
    ep = [int(r[0]) for r in rows]
    loss = [float(r[1]) for r in rows]
    f1 = [float(r[2]) for r in rows]
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(6.4, 4.6), sharex=True)
    a1.plot(ep, loss, "-o", color=ACCENT)
    for e, v in zip(ep, loss):
        a1.annotate(f"{v:.3f}", (e, v), textcoords="offset points", xytext=(0, 7), ha="center", fontsize=8.5)
    a1.set_ylabel("Training loss")
    a1.set_title("PhoBERT fine-tuning (3 classes, seed 42)")
    a1.set_ylim(0.35, 1.08)
    a2.plot(ep, f1, "-o", color=GOOD)
    for e, v in zip(ep, f1):
        a2.annotate(f"{v:.3f}", (e, v), textcoords="offset points", xytext=(0, -14), ha="center", fontsize=8.5)
    a2.axvline(2, color=MUTED, ls="--", lw=1)
    a2.text(2.05, 0.785, "selected checkpoint\n(best val macro-F1)", fontsize=8, color=MUTED)
    a2.set_ylabel("Validation macro-F1")
    a2.set_xlabel("Epoch")
    a2.set_xticks(ep)
    a2.set_ylim(0.75, 0.87)
    for a in (a1, a2):
        a.yaxis.grid(True, color=GRID)
        a.set_axisbelow(True)
    save(fig, "fig_training_curves.png")


# ---------------------------------------------------------------- classifiers
SYSTEM_NAMES = {
    "majority": "Majority class",
    "tfidf_lr": "TF-IDF + LogReg",
    "tfidf_svm": "TF-IDF + SVM",
    "phobert_ft": "PhoBERT fine-tuned",
    "llm_zeroshot": "LLM zero-shot",
    "llm_full": "Proposed pipeline",
}


def fig_system_comparison(cmp: pd.DataFrame) -> None:
    cmp = cmp.set_index("system").loc[list(SYSTEM_NAMES)]
    names = [SYSTEM_NAMES[s] for s in cmp.index]
    metrics = [("accuracy", "Accuracy", "#9DB8E6"), ("macro_f1", "Macro-F1", ACCENT), ("cohen_kappa", "Cohen's κ", "#1C3F7A")]
    fig, ax = plt.subplots(figsize=(7.6, 4.2))
    y = np.arange(len(names))
    h = 0.26
    for i, (col, lab, colr) in enumerate(metrics):
        bars = ax.barh(y + (i - 1) * h, cmp[col], h, color=colr, label=lab)
        label_bars(ax, bars, horizontal=True, pad=0.006)
    ax.set_yticks(y, names)
    ax.invert_yaxis()
    ax.set_xlim(0, 0.8)
    ax.axvline(cmp.loc["majority", "macro_f1"], color=MUTED, ls="--", lw=1)
    ax.set_xlabel("Score (test split, n = 70, single seed, synthetic data)")
    ax.set_title("Classification systems on the unified four-class test split")
    ax.legend(frameon=False, loc="lower right")
    ax.xaxis.grid(True, color=GRID)
    ax.set_axisbelow(True)
    save(fig, "fig_system_comparison.png")


def fig_per_class_f1(cmp: pd.DataFrame) -> None:
    cmp = cmp.set_index("system").loc[list(SYSTEM_NAMES)]
    mat = cmp[["f1_low", "f1_moderate", "f1_high", "f1_severe"]].to_numpy()
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    im = ax.imshow(mat, cmap="Blues", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(4), LEVELS)
    ax.set_yticks(range(len(cmp)), [SYSTEM_NAMES[s] for s in cmp.index])
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            v = mat[i, j]
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=9, color="white" if v > 0.55 else INK)
    ax.set_title("Per-class F1 by system")
    for s in ax.spines.values():
        s.set_visible(False)
    fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02, label="F1")
    save(fig, "fig_per_class_f1.png")


def draw_confusion(cm: np.ndarray, labels: list[str], title: str, name: str) -> None:
    fig, ax = plt.subplots(figsize=(4.6, 3.9))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(len(labels)), labels)
    ax.set_yticks(range(len(labels)), labels)
    ax.set_xlabel("Predicted label")
    ax.set_ylabel("True label")
    ax.set_title(title)
    thr = cm.max() / 2
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, str(cm[i, j]), ha="center", va="center", fontsize=11,
                    color="white" if cm[i, j] > thr else INK, fontweight="bold" if i == j else "normal")
    for s in ax.spines.values():
        s.set_visible(False)
    fig.colorbar(im, ax=ax, fraction=0.045, pad=0.03)
    save(fig, name)


def fig_confusions(df: pd.DataFrame) -> None:
    from sklearn.metrics import confusion_matrix, f1_score

    from app.eval.baselines import run_tfidf_lr

    res = run_tfidf_lr(df, seed=42)
    mf1 = f1_score(res.y_true, res.y_pred, labels=LEVELS, average="macro", zero_division=0)
    print(f"  TF-IDF+LR recomputed macro-F1 = {mf1:.4f} (published 0.6816)")
    cm = confusion_matrix(res.y_true, res.y_pred, labels=LEVELS)
    print("  TF-IDF+LR confusion:\n", cm)
    draw_confusion(cm, LEVELS, "TF-IDF + LogReg (4 classes, n = 70)", "fig_confusion_tfidf_lr.png")

    log = (ROOT / "phobert_run.log").read_text(encoding="utf-8", errors="ignore")
    test_part = log.split("PhoBERT — TEST")[1]
    nums = re.search(r"\[\[(.*?)\]\]", test_part, re.S).group(1)
    cm3 = np.array([[int(v) for v in row.split()] for row in nums.replace("[", "").split("]")])
    print("  PhoBERT 3-class test confusion:\n", cm3)
    draw_confusion(cm3, LEVELS[:3], "PhoBERT fine-tuned (3 classes, n = 70)", "fig_confusion_phobert.png")


# ---------------------------------------------------------------- ablation
def fig_ablation() -> None:
    ab = pd.read_csv(EVAL / "ablation.csv").set_index("config")
    order = ["full", "no_emotion", "no_questionnaire"]
    names = {"full": "full\n(RAG + questionnaire + emotion)", "no_emotion": "no_emotion", "no_questionnaire": "no_questionnaire"}
    vals = ab.loc[order, "macro_f1"]
    fig, ax = plt.subplots(figsize=(6.8, 3.6))
    colors = [ACCENT, "#7FA8E0", BAD]
    full = vals["full"]
    ax.axhspan(full - 0.148, full + 0.148, color="#E2E8F0", lw=0, zorder=0)
    bars = ax.bar([names[c] for c in order], vals, color=colors, width=0.55, zorder=2)
    label_bars(ax, bars, fmt="{:.3f}", pad=0.012)
    ax.text(2.33, full + 0.155, "shaded: ±0.148 noise floor around full\n(95% Wilson interval, n = 40)", fontsize=8, color=MUTED, ha="right")
    ax.axhline(0.1237, color=MUTED, ls="--", lw=1, zorder=3)
    ax.text(1.0, 0.14, "majority-class floor 0.124", fontsize=8, color=MUTED, ha="center")
    ax.set_ylim(0, 0.85)
    ax.set_ylabel("Macro-F1")
    ax.set_title("Component ablation (stratified 40-item subsample)")
    ax.yaxis.grid(True, color=GRID)
    ax.set_axisbelow(True)
    save(fig, "fig_ablation.png")


# ---------------------------------------------------------------- retrieval
def fig_retrieval() -> None:
    k = [1, 3, 5, 8]
    recall = [0.658, 0.838, 0.903, 0.965]
    prec = [0.684, 0.298, 0.200, 0.136]
    ndcg = [0.684, 0.776, 0.807, 0.829]
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    # Recall labels above, nDCG below, Precision above. At k = 1 precision and
    # nDCG are identical (0.684) and recall sits just under them, so that point
    # gets hand-placed labels instead of colliding ones.
    offsets = {"Recall@k": (0, 8), "nDCG@k": (0, -14), "Precision@k": (0, 8)}
    for series, lab, c, m in [(recall, "Recall@k", ACCENT, "o"), (ndcg, "nDCG@k", GOOD, "s"), (prec, "Precision@k", WARN, "^")]:
        ax.plot(k, series, marker=m, color=c, label=lab)
        for kk, v in zip(k, series):
            if kk == 1:
                continue
            ax.annotate(f"{v:.3f}", (kk, v), textcoords="offset points", xytext=offsets[lab], ha="center", fontsize=8, color=c)
    ax.annotate("nDCG = P = 0.684", (1, 0.684), textcoords="offset points", xytext=(-6, 22), fontsize=8, color=INK,
                bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.5})
    ax.annotate("Recall 0.658", (1, 0.658), textcoords="offset points", xytext=(8, -14), fontsize=8, color=ACCENT)
    ax.axvline(4, color=MUTED, ls="--", lw=1)
    ax.text(4.1, 0.05, "production k = 4", fontsize=8, color=MUTED)
    ax.set_xticks(k)
    ax.set_ylim(0, 1.08)
    ax.set_xlabel("k")
    ax.set_ylabel("Score")
    ax.set_title("Retrieval quality over 57 labelled queries (MRR = 0.787)")
    ax.legend(frameon=False, loc="center right")
    ax.yaxis.grid(True, color=GRID)
    ax.set_axisbelow(True)
    save(fig, "fig_retrieval_at_k.png")


def fig_query_construction() -> None:
    metrics = ["MRR", "Recall@1", "Recall@5", "nDCG@5"]
    old = [0.509, 0.344, 0.688, 0.540]
    sent = [0.778, 0.656, 0.938, 0.809]
    cur = [0.839, 0.719, 1.000, 0.879]
    x = np.arange(len(metrics))
    w = 0.26
    fig, ax = plt.subplots(figsize=(7, 3.7))
    for i, (vals, lab, c) in enumerate([(old, "Old: keywords + label", "#CBD5E1"), (sent, "Student's sentence only", "#7FA8E0"), (cur, "Current: sentence + keywords", ACCENT)]):
        bars = ax.bar(x + (i - 1) * w, vals, w, label=lab, color=c)
        label_bars(ax, bars, fmt="{:.2f}", pad=0.012)
    ax.set_xticks(x, metrics)
    ax.set_ylim(0, 1.15)
    ax.set_ylabel("Score")
    ax.set_title("Paired comparison of RAG query constructions (16 affected queries)")
    ax.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.1), fontsize=8.5)
    ax.yaxis.grid(True, color=GRID)
    ax.set_axisbelow(True)
    save(fig, "fig_query_construction.png")


# ---------------------------------------------------------------- safety
def fig_crisis() -> None:
    sets = ["Held-out\n(n=60)", "VI dev\n(n=50)", "EN dev\n(n=50)"]
    before = {"P": [0.600, 0.800, 1.000], "R": [0.200, 0.500, 0.417], "F1": [0.300, 0.615, 0.588]}
    after = {"P": [1.000, 1.000, 1.000], "R": [0.867, 1.000, 0.833], "F1": [0.929, 1.000, 0.909]}
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.5), sharey=True)
    for ax, key, title in zip(axes, ["P", "R", "F1"], ["Precision", "Recall", "F1"]):
        x = np.arange(3)
        b1 = ax.bar(x - 0.19, before[key], 0.36, color="#CBD5E1", label="Phrase list (before)")
        b2 = ax.bar(x + 0.19, after[key], 0.36, color=ACCENT, label="Construct patterns (after)")
        for bars in (b1, b2):
            for b in bars:
                ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.015, f"{b.get_height():.2f}",
                        ha="center", va="bottom", fontsize=7, color=INK)
        ax.set_xticks(x, sets, fontsize=8.5)
        ax.set_title(title)
        ax.set_ylim(0, 1.15)
        ax.yaxis.grid(True, color=GRID)
        ax.set_axisbelow(True)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, fontsize=9, loc="upper center", ncol=2, bbox_to_anchor=(0.5, -0.02))
    fig.suptitle("Crisis-detection rule before and after the construct-based rebuild", fontweight="bold", color=INK, y=1.02)
    save(fig, "fig_crisis_before_after.png")


def fig_crisis_categories() -> None:
    cats = [("Explicit ideation", 12, 12), ("Indirect ideation", 11, 14), ("Borderline", 7, 8),
            ("Hyperbole (hard negative)", 20, 20), ("Normal academic stress", 6, 6)]
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    names = [c[0] for c in cats]
    acc = [c[1] / c[2] for c in cats]
    colors = [ACCENT if a == 1 else WARN for a in acc]
    bars = ax.barh(names, acc, color=colors, height=0.55)
    for b, (_, ok, tot) in zip(bars, cats):
        ax.text(b.get_width() + 0.01, b.get_y() + b.get_height() / 2, f"{ok}/{tot}", va="center", fontsize=9)
    ax.invert_yaxis()
    ax.set_xlim(0, 1.12)
    ax.set_xlabel("Share of items classified correctly")
    ax.set_title("Held-out crisis set: per-category accuracy (TP 26, FP 0, FN 4, TN 30)")
    ax.xaxis.grid(True, color=GRID)
    ax.set_axisbelow(True)
    save(fig, "fig_crisis_categories.png")


# ---------------------------------------------------------------- latency
def fig_latency() -> None:
    lat = json.loads((EVAL / "latency.json").read_text(encoding="utf-8"))["stages"]
    order = sorted(lat, key=lambda s: lat[s]["p50_ms"])
    fig, ax = plt.subplots(figsize=(6.8, 3.2))
    for i, s in enumerate(order):
        p50, p95 = lat[s]["p50_ms"], lat[s]["p95_ms"]
        ax.plot([p50, p95], [i, i], color="#94A3B8", lw=3, solid_capstyle="round")
        ax.plot(p50, i, "o", color=ACCENT, ms=8)
        ax.plot(p95, i, "o", color="white", mec=ACCENT, ms=8, mew=2)
        ax.text(p95 * 1.35, i, f"p50 {p50:.2f} ms · p95 {p95:.2f} ms", va="center", fontsize=8.5)
    ax.set_yticks(range(len(order)), order)
    ax.set_xscale("log")
    ax.set_xlim(0.01, 3000)
    ax.set_xlabel("Latency per call (ms, log scale; filled = p50, hollow = p95; n = 30)")
    ax.set_title("Per-stage latency of the deterministic pipeline (CPU)")
    ax.xaxis.grid(True, color=GRID, which="major")
    ax.set_axisbelow(True)
    save(fig, "fig_latency.png")


# ---------------------------------------------------------------- leakage
def fig_leakage() -> None:
    # Use the project's own leakage functions so the figure cannot disagree
    # with data/eval/leakage.md.
    from scripts.check_leakage import difflib_nearest, load_splits

    sims, _ = difflib_nearest(load_splits(), "test")
    sims = np.asarray(sims)
    print(f"  leakage test median = {np.median(sims):.3f} (published 0.799); >0.80: {(sims > 0.8).sum()}/70 (published 34)")
    fig, ax = plt.subplots(figsize=(6.6, 3.4))
    ax.hist(sims, bins=np.arange(0.55, 0.96, 0.025), color=ACCENT, edgecolor="white")
    ax.axvline(0.80, color=BAD, ls="--", lw=1.2)
    ax.axvline(np.median(sims), color=INK, ls=":", lw=1.2)
    top = ax.get_ylim()[1]
    box = {"facecolor": "white", "edgecolor": "none", "pad": 1.5}
    ax.text(0.82, top * 0.93, f"> 0.80: {(sims > 0.8).sum()} / {len(sims)} items", color=BAD, fontsize=8.5, bbox=box)
    ax.text(0.56, top * 0.93, f"median {np.median(sims):.3f} (dotted line)", color=INK, fontsize=8.5, bbox=box)
    ax.set_xlabel("Similarity of each test text to its nearest training text (difflib ratio)")
    ax.set_ylabel("Test items")
    ax.set_title("Near-duplicate leakage: zero exact duplicates, high near-duplication")
    ax.yaxis.grid(True, color=GRID)
    ax.set_axisbelow(True)
    save(fig, "fig_leakage.png")


def main() -> None:
    df = pd.read_csv(EVAL / "dataset_synthetic.csv")
    cmp = pd.read_csv(EVAL / "comparison.csv")
    print("Rendering report figures ->", OUT)
    fig_label_distribution(df)
    fig_training_curves()
    fig_system_comparison(cmp)
    fig_per_class_f1(cmp)
    fig_confusions(df)
    fig_ablation()
    fig_retrieval()
    fig_query_construction()
    fig_crisis()
    fig_crisis_categories()
    fig_latency()
    fig_leakage()


if __name__ == "__main__":
    main()
