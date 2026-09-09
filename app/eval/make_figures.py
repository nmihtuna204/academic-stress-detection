"""Report figures generated from artefacts already on disk.

Three figures the report references by number and has never had:

    Figure 4.2  label distribution across the frozen splits
    Figure 4.3  PhoBERT training and validation curves
    Figure 4.6  macro-F1 across every evaluated system

Every one is derived from a file this repository already produces - the frozen
split CSV, the captured fine-tuning log, and the comparison artefact - so a
figure can never drift from the number in the table beside it. Nothing here
reads the network or a model.

Design constraints, applied deliberately rather than by matplotlib default:

* Stress level is ORDINAL (Low < Moderate < High < Severe), so it is drawn with
  a single-hue ramp stepped light to dark, not four unrelated categorical hues.
  The steps clear the ordinal gates (monotone lightness, adjacent dL >= 0.06,
  light end >= 2:1 against the chart surface).
* Training loss and validation macro-F1 have different units and different
  ranges, so they get two stacked panels sharing an epoch axis - never one
  panel carrying two y-scales, which invites a comparison the data cannot
  support.
* These are print figures: no tooltip is possible, so direct value labels do
  the job a hover layer would, and they double as the accessible table view.

Usage:
    python -m app.eval.make_figures
"""

from __future__ import annotations

import argparse
import logging
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from app.config import PROJECT_ROOT  # noqa: E402

logger = logging.getLogger(__name__)

OUT_DIR = PROJECT_ROOT / "data" / "eval"
# The 3-class fine-tuning split. Retained for provenance only - see
# figure_label_distribution() for why no figure is drawn from it.
SPLIT_CSV = PROJECT_ROOT / "data" / "stress_dataset_split.csv"
TRAIN_LOG = PROJECT_ROOT / "phobert_run.log"
COMPARISON_CSV = OUT_DIR / "comparison.csv"
SYNTHETIC_CSV = PROJECT_ROOT / "data" / "stress_dataset.csv"

STRESS_LEVELS = ["Low", "Moderate", "High", "Severe"]
SPLIT_ORDER = ["train", "val", "test"]

# Ordinal ramp: one hue, stepped light to dark. Validated on the light chart
# surface - monotone lightness, every adjacent gap >= 0.06, light end 2.06:1.
ORDINAL_BLUE = {"Low": "#86b6ef", "Moderate": "#3987e5", "High": "#256abf", "Severe": "#104281"}
SINGLE_SERIES = "#2a78d6"
REFERENCE_FILL = "#9ec5f4"

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
GRID = "#e4e3df"


def _style(ax) -> None:
    """Recessive chrome: the data should be the only thing carrying weight."""
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK_SECONDARY, labelsize=9, length=0)
    ax.set_axisbelow(True)


def figure_label_distribution(out_path: Path) -> Path:
    """Figure 4.2 - class balance across the frozen train/val/test splits.

    Drawn from the evaluation harness, not `stress_dataset_split.csv`. The two
    disagree on the label space and only one belongs beside Table 4.4: the CSV
    carries the THREE-class label PhoBERT was fine-tuned on (Low/Moderate/High,
    no Severe at all), while every system in the results table is scored on the
    unified FOUR-class label `derive_ground_truth()` produces. Plotting the CSV
    would put a three-bar figure next to a four-class table on the same page.
    """
    from app.eval.datasets import build_synthetic_dataset

    df = build_synthetic_dataset()
    counts = (
        df.groupby(["split", "label"]).size().unstack(fill_value=0).reindex(SPLIT_ORDER).fillna(0)
    )
    for level in STRESS_LEVELS:
        if level not in counts.columns:
            counts[level] = 0
    counts = counts[STRESS_LEVELS]

    fig, ax = plt.subplots(figsize=(7.5, 4.4))
    fig.patch.set_facecolor(SURFACE)
    width = 0.78 / len(STRESS_LEVELS)
    positions = list(range(len(SPLIT_ORDER)))

    for i, level in enumerate(STRESS_LEVELS):
        offsets = [p - 0.39 + width * (i + 0.5) for p in positions]
        values = [float(v) for v in counts[level].tolist()]
        # The 2px surface-coloured edge is the gap between adjacent bars.
        bars = ax.bar(
            offsets,
            values,
            width=width * 0.92,
            color=ORDINAL_BLUE[level],
            label=level,
            edgecolor=SURFACE,
            linewidth=2,
            zorder=3,
        )
        for rect, value in zip(bars, values):
            if value:
                ax.text(
                    rect.get_x() + rect.get_width() / 2,
                    value + 1.5,
                    str(int(value)),
                    ha="center",
                    va="bottom",
                    fontsize=8,
                    color=INK_SECONDARY,
                    zorder=4,
                )

    ax.set_xticks(positions)
    ax.set_xticklabels([f"{s}\n(n = {int(counts.loc[s].sum())})" for s in SPLIT_ORDER])
    ax.set_ylabel("items", color=INK_SECONDARY, fontsize=9)
    ax.set_title(
        "Label distribution across the frozen splits",
        color=INK,
        fontsize=11,
        loc="left",
        pad=12,
    )
    ax.grid(axis="y", color=GRID, linewidth=1)
    ax.set_ylim(0, float(counts.to_numpy().max()) * 1.20)
    legend = ax.legend(
        title="Stress level",
        frameon=False,
        fontsize=9,
        title_fontsize=9,
        ncol=4,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.13),
    )
    for text in legend.get_texts():
        text.set_color(INK_SECONDARY)
    legend.get_title().set_color(INK_SECONDARY)
    _style(ax)
    fig.tight_layout()
    fig.savefig(out_path, dpi=200, facecolor=SURFACE)
    plt.close(fig)
    return out_path


def parse_training_log(log_path: Path) -> pd.DataFrame:
    """Pull the per-epoch metrics out of the captured fine-tuning log."""
    pattern = re.compile(r"epoch\s+(\d+)/(\d+)\s+train_loss=([0-9.]+)\s+val_macroF1=([0-9.]+)")
    text = log_path.read_text(encoding="utf-8", errors="replace")
    rows = [
        {
            "epoch": int(m.group(1)),
            "train_loss": float(m.group(3)),
            "val_macro_f1": float(m.group(4)),
        }
        for m in pattern.finditer(text)
    ]
    if not rows:
        raise ValueError(f"no epoch lines found in {log_path}")
    return pd.DataFrame(rows).sort_values("epoch").reset_index(drop=True)


def figure_training_curves(out_path: Path) -> Path:
    """Figure 4.3 - training loss and validation macro-F1, in two panels.

    Two panels rather than two y-axes on one set of marks: the series share an
    epoch axis and nothing else, and overlaying them would imply their crossing
    points mean something.
    """
    df = parse_training_log(TRAIN_LOG)
    best = df.loc[df["val_macro_f1"].idxmax()]

    fig, (ax_loss, ax_f1) = plt.subplots(
        2, 1, figsize=(7.0, 5.6), sharex=True, gridspec_kw={"hspace": 0.30}
    )
    fig.patch.set_facecolor(SURFACE)

    for ax, col, title in (
        (ax_loss, "train_loss", "Training loss"),
        (ax_f1, "val_macro_f1", "Validation macro-F1"),
    ):
        ax.plot(
            df["epoch"],
            df[col],
            color=SINGLE_SERIES,
            linewidth=2,
            marker="o",
            markersize=8,
            markeredgecolor=SURFACE,
            markeredgewidth=2,
            zorder=3,
        )
        for x, y in zip(df["epoch"], df[col]):
            ax.annotate(
                f"{y:.4f}",
                (x, y),
                textcoords="offset points",
                xytext=(0, 11),
                ha="center",
                fontsize=8,
                color=INK_SECONDARY,
                zorder=4,
            )
        ax.set_title(title, color=INK, fontsize=10, loc="left", pad=8)
        ax.grid(axis="y", color=GRID, linewidth=1)
        _style(ax)

    # The plateau is the point of this figure, so it is named on the figure.
    # Stops below the value labels rather than striking through them.
    ax_f1.axvline(
        float(best["epoch"]), ymax=0.80,
        color=INK_SECONDARY, linewidth=1, linestyle=(0, (4, 3)), zorder=2,
    )
    ax_f1.annotate(
        f"best epoch {int(best['epoch'])}, selected\nepochs 3-4 add nothing",
        (float(best["epoch"]), float(best["val_macro_f1"])),
        textcoords="offset points",
        xytext=(16, -30),
        fontsize=8,
        color=INK_SECONDARY,
    )
    ax_f1.set_xlabel("epoch", color=INK_SECONDARY, fontsize=9)
    ax_f1.set_xticks(df["epoch"].tolist())
    ax_f1.set_xlim(df["epoch"].min() - 0.28, df["epoch"].max() + 0.28)
    ax_loss.set_ylim(df["train_loss"].min() * 0.86, df["train_loss"].max() * 1.14)
    ax_f1.set_ylim(df["val_macro_f1"].min() * 0.982, df["val_macro_f1"].max() * 1.014)
    fig.suptitle(
        "PhoBERT fine-tuning, 3-class task",
        color=INK,
        fontsize=11,
        x=0.008,
        ha="left",
        y=0.985,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.955))
    fig.savefig(out_path, dpi=200, facecolor=SURFACE)
    plt.close(fig)
    return out_path


def figure_macro_f1(out_path: Path) -> Path:
    """Figure 4.6 - macro-F1 for every system on the shared 4-class split.

    No error bars. Every number in the artefact comes from a single seed, so
    there is no dispersion to draw, and a whisker here would be a fabricated
    interval. The title states the seed count instead.
    """
    df = pd.read_csv(COMPARISON_CSV).sort_values("macro_f1", ascending=True)
    labels = df["system"].tolist()
    values = [float(v) for v in df["macro_f1"].tolist()]

    fig, ax = plt.subplots(figsize=(7.5, 0.62 * len(labels) + 2.0))
    fig.patch.set_facecolor(SURFACE)
    bars = ax.barh(labels, values, height=0.62, color=SINGLE_SERIES, zorder=3)

    # The majority-class row is the floor the others must clear - a reference,
    # not a peer, so it is drawn as one.
    if "majority" in labels:
        floor = float(df.loc[df["system"] == "majority", "macro_f1"].iloc[0])
        bars[labels.index("majority")].set_color(REFERENCE_FILL)
        ax.axvline(floor, color=INK_SECONDARY, linewidth=1, linestyle=(0, (4, 3)), zorder=2)
        # Sits just above the frame, in the gap under the title: inside the
        # plot it lands on a bar, where dark ink on the series fill is both a
        # collision and a contrast failure.
        ax.annotate(
            "majority-class floor",
            (floor, 1.0),
            xycoords=("data", "axes fraction"),
            textcoords="offset points",
            xytext=(6, 5),
            fontsize=8,
            color=INK_SECONDARY,
            va="bottom",
            ha="left",
        )

    for rect, value in zip(bars, values):
        ax.text(
            value + max(values) * 0.015,
            rect.get_y() + rect.get_height() / 2,
            f"{value:.4f}",
            va="center",
            fontsize=9,
            color=INK_SECONDARY,
            zorder=4,
        )

    ax.set_xlim(0, max(values) * 1.24)
    ax.set_xlabel("macro-F1", color=INK_SECONDARY, fontsize=9)
    ax.set_title(
        "Macro-F1 across systems, unified 4-class split (n = 70, single seed)",
        color=INK,
        fontsize=11,
        loc="left",
        pad=24,
    )
    ax.grid(axis="x", color=GRID, linewidth=1)
    _style(ax)
    fig.tight_layout()
    fig.savefig(out_path, dpi=200, facecolor=SURFACE)
    plt.close(fig)
    return out_path


def run(out_dir: Path | None = None) -> list[Path]:
    """Build every figure whose inputs are present; skip the rest loudly."""
    out_dir = Path(out_dir) if out_dir else OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    jobs = [
        ("fig_4_2_label_distribution.png", figure_label_distribution, SYNTHETIC_CSV),
        ("fig_4_3_training_curves.png", figure_training_curves, TRAIN_LOG),
        ("fig_4_6_macro_f1.png", figure_macro_f1, COMPARISON_CSV),
    ]
    written: list[Path] = []
    for name, builder, source in jobs:
        if not source.exists():
            logger.warning("skipping %s - missing input %s", name, source)
            print(f"  [skip] {name}: missing {source}")
            continue
        try:
            written.append(builder(out_dir / name))
            print(f"  [ok]   {name}")
        except Exception as exc:  # noqa: BLE001 - one bad figure must not stop the rest
            logger.warning("could not build %s: %s", name, exc)
            print(f"  [fail] {name}: {exc}")
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the report figures.")
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    print("Building report figures")
    written = run(args.out_dir)
    print(f"\n{len(written)} figure(s) written to {args.out_dir or OUT_DIR}")


if __name__ == "__main__":
    main()
