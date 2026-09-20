"""Ablation study over the proposed system's components.

Configurations (same frozen split and metrics as the baseline comparison):

| id               | RAG | questionnaire | emotion |
|------------------|-----|---------------|---------|
| full             | on  | on            | on      |
| no_rag           | off | on            | on      |
| no_questionnaire | on  | off           | on      |
| no_emotion       | on  | on            | off     |
| text_only        | off | off           | off     |

Usage:
    python -m app.eval.ablation --dataset synthetic

Outputs (data/eval/): ablation.csv, ablation.md, ablation.png.
All configurations require a valid OPENAI_API_KEY; responses are disk-cached,
so a full re-run after the first costs nothing.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import math
import os
from pathlib import Path

import pandas as pd

from app.config import PROJECT_ROOT

logger = logging.getLogger(__name__)

# id -> (use_rag, use_questionnaire, use_emotion)
CONFIGS: dict[str, tuple[bool, bool, bool]] = {
    "full": (True, True, True),
    "no_rag": (False, True, True),
    "no_questionnaire": (True, False, True),
    "no_emotion": (True, True, False),
    "text_only": (False, False, False),
}

METRIC_COLS = ["accuracy", "macro_f1", "cohen_kappa"]


def noise_floor(n: int, p: float = 0.5) -> float:
    """Half-width of the 95% Wilson interval on accuracy at sample size `n`.

    A delta smaller than this cannot be distinguished from sampling noise, and
    reporting it directionally would claim a result the data does not support.
    Computed at p=0.5, the widest (most conservative) case.
    """
    if n <= 0:
        return float("inf")
    z = 1.96
    denom = 1 + z * z / n
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return half


def interpret(table: pd.DataFrame, n_used: int | None = None) -> str:
    """One short computed paragraph: which components matter, per the deltas.

    Deltas below the sampling-noise floor are reported as indistinguishable from
    zero rather than given a direction. Without this the paragraph would say
    things like "removing the emotion features IMPROVES macro-F1 by 0.059" at
    n=40, where the 95% interval is +/-0.148 - a claim the sample cannot carry.
    """
    if table.empty or "full" not in set(table["config"]):
        return (
            "No interpretation available: the ablation has not produced results yet "
            "(a valid OPENAI_API_KEY is required)."
        )
    full_row = table[table["config"] == "full"].iloc[0]
    floor = noise_floor(n_used) if n_used else None
    parts: list[str] = []
    for _, row in table[table["config"] != "full"].iterrows():
        delta = row["macro_f1"] - full_row["macro_f1"]
        component = {
            "no_rag": "RAG retrieval",
            "no_questionnaire": "the questionnaire scores",
            "no_emotion": "the emotion features",
            "text_only": "everything except the raw text",
        }.get(row["config"], row["config"])
        if floor is not None and abs(delta) < floor:
            parts.append(
                f"removing {component} moves macro-F1 by {delta:+.3f} "
                f"({full_row['macro_f1']:.3f} → {row['macro_f1']:.3f}), which is INSIDE the "
                f"±{floor:.3f} sampling-noise floor at n={n_used} and therefore cannot be "
                "distinguished from no effect"
            )
        else:
            direction = "drops" if delta < 0 else ("is unchanged" if delta == 0 else "IMPROVES")
            parts.append(
                f"removing {component} {direction} macro-F1 by {abs(delta):.3f} "
                f"({full_row['macro_f1']:.3f} → {row['macro_f1']:.3f})"
            )
    return (
        "Interpretation (computed from the table above): " + "; ".join(parts) + ". "
        "Components whose removal barely moves macro-F1 contribute little measurable "
        "signal on this dataset; large drops mark load-bearing components. Note that "
        "the questionnaire scores define the ground-truth label, so the "
        "no_questionnaire delta measures label leakage as much as feature value."
        + (
            f" Sampling-noise floor at n={n_used} is ±{floor:.3f} on accuracy (95% Wilson, "
            "worst case p=0.5); only deltas larger than that are reported directionally."
            if floor is not None
            else ""
        )
    )


def plot(table: pd.DataFrame, out_path: Path) -> None:
    """Grouped bar chart: accuracy and macro-F1 per configuration."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    configs = table["config"].tolist()
    x = np.arange(len(configs))
    width = 0.35

    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars1 = ax.bar(x - width / 2, table["accuracy"], width, label="Accuracy", color="#5c7cfa")
    bars2 = ax.bar(x + width / 2, table["macro_f1"], width, label="Macro-F1", color="#20c997")
    for bars in (bars1, bars2):
        ax.bar_label(bars, fmt="%.3f", fontsize=9)

    ax.set_xticks(x, configs)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("score")
    ax.set_title("Ablation study — proposed system components")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def subsample_test_split(df: pd.DataFrame, limit: int, seed: int = 42) -> pd.DataFrame:
    """Cut the test split to `limit` rows, stratified by label, deterministically.

    An ablation is a paired comparison: every configuration must see the SAME
    items, or the differences between configurations stop being attributable to
    the configuration. Subsampling therefore happens once, here, before any
    configuration runs, and is seeded so a re-run reproduces it.

    Stratifying matters at these sizes. The test split is Low 16 / Moderate 23 /
    High 22 / Severe 9; an unstratified cut to 35 could easily leave 2 Severe
    items, and a per-class F1 computed on 2 items is noise.

    Rows outside the test split are untouched: `run_llm_full` only evaluates
    test rows, but the train rows must stay for anything that fits on them.
    """
    test = df[df["split"] == "test"]
    if limit >= len(test):
        return df

    share = limit / len(test)
    kept: list = []
    for _label, group in test.groupby("label", sort=True):
        # At least one row per class, so no class silently disappears.
        n = max(1, round(len(group) * share))
        kept.extend(group.sample(n=min(n, len(group)), random_state=seed).index)

    dropped = test.index.difference(pd.Index(kept))
    return df.drop(index=dropped)


def run(
    dataset_name: str,
    configs: list[str],
    out_dir: Path | None = None,
    limit: int | None = None,
) -> pd.DataFrame:
    from app.eval.baselines import run_llm_full
    from app.eval.compare import _openai_key_available, metrics_row
    from app.eval.datasets import load_eval_dataset

    out = out_dir or (PROJECT_ROOT / "data" / "eval")
    out.mkdir(parents=True, exist_ok=True)

    if not _openai_key_available():
        message = (
            "# Ablation study\n\nNOT RUN: OPENAI_API_KEY is missing or a placeholder. "
            "Set it in .env and run `python -m app.eval.ablation --dataset "
            f"{dataset_name}`.\n"
        )
        (out / "ablation.md").write_text(message, encoding="utf-8")
        print(message)
        return pd.DataFrame()

    df = load_eval_dataset(dataset_name, out_dir=out)

    n_full = int((df["split"] == "test").sum())
    n_used = n_full
    if limit is not None:
        df = subsample_test_split(df, limit)
        n_used = int((df["split"] == "test").sum())
        if n_used < n_full:
            print(
                f"Subsampled test split: {n_used}/{n_full} items, stratified, seed 42. "
                "Report this alongside the numbers - the comparison stays paired, but "
                "every per-class figure rests on fewer items."
            )

    rows = []
    unreported: list[tuple[str, str]] = []
    for config in configs:
        use_rag, use_questionnaire, use_emotion = CONFIGS[config]
        print(f"\n=== Ablation config: {config} ===")
        result = asyncio.run(
            run_llm_full(
                df,
                use_rag=use_rag,
                use_questionnaire=use_questionnaire,
                use_emotion=use_emotion,
                system_id=config,
            )
        )
        unreportable = result.unreportable_reason()
        if unreportable:
            print(f"NOT REPORTED {config}: {unreportable}")
            unreported.append((config, unreportable))
            continue

        row, _metrics = metrics_row(result)
        row["config"] = config
        rows.append(row)
        print(f"{config}: acc={row['accuracy']:.3f} macro_f1={row['macro_f1']:.3f}")

    table = pd.DataFrame(rows)

    banner = (
        f"# Ablation study — dataset: `{dataset_name}`\n\n"
        + ("> **Computed on SYNTHETIC data.**\n\n" if dataset_name == "synthetic" else "")
    )
    if limit is not None and n_used < n_full:
        banner += (
            f"> Evaluated on a stratified {n_used}/{n_full}-item subsample of the test "
            "split (seed 42), identical across configurations. Quote the sample size "
            "wherever these figures appear.\n\n"
        )

    def _not_reported_section() -> str:
        if not unreported:
            return ""
        text = "\n**Not reported** (the run produced no usable predictions):\n\n"
        for config, reason in unreported:
            text += f"- `{config}` — {reason}\n"
        return text

    # Every configuration failed the reportability check: write the explanation
    # rather than an empty table, and leave any earlier artifact untouched below.
    if table.empty:
        markdown = banner + "No configuration produced reportable results.\n" + _not_reported_section()
        (out / "ablation.md").write_text(markdown, encoding="utf-8")
        print("\n" + markdown)
        return table

    # Deltas vs the full configuration.
    if "full" in set(table["config"]):
        full_row = table[table["config"] == "full"].iloc[0]
        for metric in METRIC_COLS:
            table[f"delta_{metric}"] = (table[metric] - full_row[metric]).round(4)

    display_cols = ["config"] + METRIC_COLS + [f"delta_{m}" for m in METRIC_COLS if f"delta_{m}" in table]
    table = table[display_cols + [c for c in table.columns if c not in display_cols]]
    table.to_csv(out / "ablation.csv", index=False)

    markdown = (
        banner
        + table[display_cols].to_markdown(index=False)
        + "\n\n"
        + interpret(table, n_used=n_used)
        + "\n"
        + _not_reported_section()
    )
    (out / "ablation.md").write_text(markdown, encoding="utf-8")
    plot(table, out / "ablation.png")
    print("\n" + markdown)
    return table


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=["synthetic", "real"], default="synthetic")
    parser.add_argument("--configs", nargs="+", choices=list(CONFIGS), default=list(CONFIGS))
    parser.add_argument("--out", default=None)
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "Evaluate only N test items (stratified, seed 42, identical across "
            "configs). Halves the token cost at the price of wider error bars; "
            "must be disclosed wherever the numbers are reported."
        ),
    )
    parser.add_argument("--online-hub", action="store_true")
    args = parser.parse_args()

    if not args.online_hub:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
    logging.basicConfig(level=logging.WARNING)
    run(args.dataset, args.configs, Path(args.out) if args.out else None, limit=args.limit)


if __name__ == "__main__":
    main()
