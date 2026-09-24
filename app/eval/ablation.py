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

Outputs (data/eval/): ablation.csv, ablation_paired.csv, ablation.md, ablation.png.
All configurations require a valid OPENAI_API_KEY; responses are disk-cached,
so a full re-run after the first costs nothing.

Statistics - PRE-SPECIFIED from 2026-09-24 for every run from then on:

- **Primary.** Each ablated configuration against `full`: the difference in
  accuracy, tested with an exact McNemar test on the items the two classify
  differently, Holm-corrected across the ablated configurations, alpha = 0.05.
  A direction ("removing X lowers accuracy") is stated only when that test
  rejects. Every configuration sees the same items, so the comparison is
  paired; the covariance between two systems scored on the same items is what
  a paired test uses and a per-system interval throws away.
- **Secondary, descriptive.** The labels are ordered, so quadratic-weighted
  kappa, with a paired bootstrap 95 % interval on its difference from `full`,
  and the share of predictions within one level of the truth. These are not
  tested and carry no direction on their own.
- **Power.** The observed paired outcomes are resampled to larger n to project
  how often the primary test would reject. A projection from a small sample,
  and optimistic, because effects measured on few items tend to be overstated.

The stratified n = 40 run of 2026-09-20 was specified against a
single-proportion "noise floor" (the 95 % Wilson half-width of one accuracy,
±0.148). That is not the right yardstick for a paired difference; the analysis
above replaced it after that run's results were known, so wherever it is quoted
for that run it is labelled post hoc.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
from pathlib import Path

import numpy as np
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

METRIC_COLS = ["accuracy", "within_one", "macro_f1", "cohen_kappa", "qwk"]
ALPHA = 0.05
COMPONENT = {
    "no_rag": "RAG retrieval",
    "no_questionnaire": "the questionnaire scores",
    "no_emotion": "the emotion features",
    "text_only": "everything except the raw text",
}


def ordinal_codes(labels) -> np.ndarray:
    """Labels as their position on the ordered scale Low < Moderate < High < Severe.

    Raises on anything outside the scale rather than coding it silently.
    """
    from app.eval.baselines import STRESS_LEVELS

    position = {level: i for i, level in enumerate(STRESS_LEVELS)}
    unknown = sorted({str(x) for x in labels} - set(position))
    if unknown:
        raise ValueError(f"labels outside the ordered scale: {unknown}")
    return np.array([position[x] for x in labels], dtype=int)


def _qwk(t: np.ndarray, p: np.ndarray, k: int = 4) -> float:
    """Quadratic-weighted kappa on integer-coded labels; nan where it is undefined.

    Equal to sklearn's cohen_kappa_score(weights="quadratic"), written out so a
    10,000-draw bootstrap stays fast.
    """
    observed = np.bincount(t * k + p, minlength=k * k).reshape(k, k).astype(float)
    n = observed.sum()
    weights = np.subtract.outer(np.arange(k), np.arange(k)) ** 2.0
    expected = np.outer(observed.sum(axis=1), observed.sum(axis=0)) / n if n else observed
    denom = (weights * expected).sum()
    return float(1.0 - (weights * observed).sum() / denom) if denom else float("nan")


def qwk(y_true, y_pred) -> float:
    """Quadratic-weighted kappa: an off-by-three costs nine times an off-by-one."""
    return _qwk(ordinal_codes(y_true), ordinal_codes(y_pred))


def within_one(y_true, y_pred) -> float:
    """Share of predictions at most one level from the truth."""
    return float(np.mean(np.abs(ordinal_codes(y_pred) - ordinal_codes(y_true)) <= 1))


def mcnemar_exact(ref_correct: np.ndarray, other_correct: np.ndarray) -> tuple[int, int, float]:
    """Exact McNemar test on paired correctness.

    Only the discordant items carry information: `b` the reference got right and
    the other got wrong, `c` the reverse. Under no difference each discordant
    item is a fair coin, so the p-value is a two-sided binomial test of b in b+c.
    """
    from scipy.stats import binomtest

    b = int(np.sum(ref_correct & ~other_correct))
    c = int(np.sum(~ref_correct & other_correct))
    return b, c, (1.0 if b + c == 0 else float(binomtest(b, b + c, 0.5).pvalue))


def holm(pvalues: list[float]) -> list[float]:
    """Holm step-down adjusted p-values, controlling the family-wise error rate."""
    m = len(pvalues)
    adjusted = [0.0] * m
    running = 0.0
    for rank, i in enumerate(sorted(range(m), key=lambda j: pvalues[j])):
        running = max(running, min(1.0, (m - rank) * pvalues[i]))
        adjusted[i] = running
    return adjusted


def paired_comparison(y_true, predictions: dict[str, list[str]], reference: str = "full",
                      resamples: int = 10_000, seed: int = 42) -> pd.DataFrame:
    """Every configuration against the reference, on the same items.

    Primary: exact McNemar on accuracy, Holm-corrected across configurations.
    Descriptive: a paired bootstrap interval on the difference in QWK.
    """
    t = ordinal_codes(y_true)
    ref = ordinal_codes(predictions[reference])
    draws = np.random.default_rng(seed).integers(0, len(t), size=(resamples, len(t)))
    rows = []
    for config, labels in predictions.items():
        if config == reference:
            continue
        p = ordinal_codes(labels)
        b, c, pvalue = mcnemar_exact(ref == t, p == t)
        boot = np.array([_qwk(t[i], p[i]) - _qwk(t[i], ref[i]) for i in draws])
        low, high = np.nanpercentile(boot, [2.5, 97.5])
        rows.append({
            "config": config,
            "n": len(t),
            "reference_only_correct": b,
            "other_only_correct": c,
            "delta_accuracy": round(float(np.mean(p == t) - np.mean(ref == t)), 4),
            "mcnemar_p": round(pvalue, 4),
            "delta_qwk": round(_qwk(t, p) - _qwk(t, ref), 4),
            "delta_qwk_ci_low": round(float(low), 4),
            "delta_qwk_ci_high": round(float(high), 4),
        })
    table = pd.DataFrame(rows)
    if not table.empty:
        table["mcnemar_p_holm"] = [round(x, 4) for x in holm(table["mcnemar_p"].tolist())]
        table["significant"] = table["mcnemar_p_holm"] < ALPHA
    return table


def power_projection(y_true, predictions: dict[str, list[str]], reference: str = "full",
                     sizes: tuple[int, ...] = (40, 70, 100, 150, 200), draws: int = 2000,
                     seed: int = 7) -> pd.DataFrame:
    """Share of resamples in which the McNemar test rejects, at larger n.

    Resamples the observed item pairs, so it assumes the discordance seen at the
    current n is the true one. Per comparison and unadjusted: under the Holm
    correction the primary analysis applies, the n needed is larger still.
    """
    t = ordinal_codes(y_true)
    ref_correct = ordinal_codes(predictions[reference]) == t
    rng = np.random.default_rng(seed)
    rows = []
    for config, labels in predictions.items():
        if config == reference:
            continue
        other_correct = ordinal_codes(labels) == t
        row = {"config": config}
        for n in sizes:
            hits = 0
            for _ in range(draws):
                i = rng.integers(0, len(t), n)
                hits += mcnemar_exact(ref_correct[i], other_correct[i])[2] < ALPHA
            row[f"n={n}"] = round(hits / draws, 3)
        rows.append(row)
    return pd.DataFrame(rows)


def interpret(table: pd.DataFrame, paired: pd.DataFrame | None = None) -> str:
    """One computed paragraph: what removing each component did, and whether it is real.

    A direction is stated only where the pre-specified primary test - exact
    McNemar, Holm-corrected - rejects at alpha = 0.05. Without per-item paired
    results no direction is claimed at all: a difference between two summary
    numbers says nothing about whether it would survive another sample.
    """
    if table.empty or "full" not in set(table["config"]):
        return (
            "No interpretation available: the ablation has not produced results yet "
            "(a valid OPENAI_API_KEY is required)."
        )
    full_row = table[table["config"] == "full"].iloc[0]
    tests = {} if paired is None or paired.empty else paired.set_index("config").to_dict("index")
    parts: list[str] = []
    for _, row in table[table["config"] != "full"].iterrows():
        config = row["config"]
        delta = row["accuracy"] - full_row["accuracy"]
        text = (
            f"removing {COMPONENT.get(config, config)} moves accuracy by {delta:+.3f} "
            f"({full_row['accuracy']:.3f} → {row['accuracy']:.3f})"
        )
        test = tests.get(config)
        if test is None:
            text += ", with no paired test available, so no direction is claimed"
        else:
            b, c = int(test["reference_only_correct"]), int(test["other_only_correct"])
            text += (
                f"; full alone right on {b} item{'s' if b != 1 else ''}, {config} alone on {c}, "
                f"exact McNemar p = {test['mcnemar_p']:.3f}, "
                f"Holm-adjusted {test['mcnemar_p_holm']:.3f}"
            )
            if test["significant"]:
                text += f" — a real {'drop' if delta < 0 else 'gain'} at α = {ALPHA}"
            else:
                text += f" — not distinguishable from no effect at α = {ALPHA}"
        parts.append(text)
    return (
        "Interpretation (computed; primary test pre-specified in the module docstring): "
        + "; ".join(parts)
        + ". Note that the questionnaire scores define the ground-truth label, so the "
        "no_questionnaire comparison measures label leakage as much as feature value."
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
    # Per-item labels, kept for the paired analysis: summary numbers alone cannot
    # say whether a difference between two configurations would survive.
    predictions: dict[str, list[str]] = {}
    y_true: list[str] | None = None
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
        row["within_one"] = round(within_one(result.y_true, result.y_pred), 4)
        row["qwk"] = round(qwk(result.y_true, result.y_pred), 4)
        rows.append(row)
        if y_true is None:
            y_true = list(result.y_true)
        elif list(result.y_true) != y_true:
            raise RuntimeError(f"{config} was scored on different items; the comparison is not paired")
        predictions[config] = list(result.y_pred)
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

    display_cols = ["config"] + METRIC_COLS
    table = table[display_cols + [c for c in table.columns if c not in display_cols]]
    table.to_csv(out / "ablation.csv", index=False)

    paired = None
    sections = ""
    if "full" in predictions and len(predictions) > 1:
        paired = paired_comparison(y_true, predictions)
        paired.to_csv(out / "ablation_paired.csv", index=False)
        power = power_projection(y_true, predictions)
        shown = paired.assign(
            delta_qwk_95ci=[f"[{lo:+.3f}, {hi:+.3f}]"
                            for lo, hi in zip(paired["delta_qwk_ci_low"], paired["delta_qwk_ci_high"], strict=True)]
        )[["config", "reference_only_correct", "other_only_correct", "delta_accuracy",
           "mcnemar_p", "mcnemar_p_holm", "significant", "delta_qwk", "delta_qwk_95ci"]]
        sections = (
            "\n## Paired comparison against `full`\n\n"
            f"Same {len(y_true)} items for every configuration. `reference_only_correct` = items "
            "`full` classified correctly and the configuration did not; `other_only_correct` = the "
            "reverse. Only those discordant items carry information about a difference. "
            f"**Primary:** exact McNemar, Holm-corrected, α = {ALPHA}. "
            "**Descriptive only:** ΔQWK with a paired bootstrap 95 % interval (10,000 resamples).\n\n"
            + shown.to_markdown(index=False)
            + "\n\n## Projected power of the primary test\n\n"
            "Share of resamples of the observed item pairs in which McNemar rejects at α = "
            f"{ALPHA}, per comparison and before the Holm correction. It assumes the discordance "
            "seen here is the true one, and effects measured on few items tend to be overstated, "
            "so read it as an upper bound on what a larger sample would show.\n\n"
            + power.to_markdown(index=False)
            + "\n"
        )

    markdown = (
        banner
        + table[display_cols].to_markdown(index=False)
        + "\n\n`within_one` = share of predictions at most one level from the truth; "
        "`qwk` = quadratic-weighted kappa, which weights a miss by its distance on the "
        "ordered scale.\n"
        + sections
        + "\n"
        + interpret(table, paired)
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
