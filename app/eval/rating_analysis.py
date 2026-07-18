"""Analyze completed human-rating sheets.

Reads all `rating_sheet_rater*.csv` files in a directory, joins them on
`item_id`, and reports per-criterion means/SDs plus inter-rater agreement
(Krippendorff's alpha, interval metric - the standard choice for 1-5 scales;
`--metric ordinal` is also available).

Krippendorff's alpha is implemented here (no extra dependency):
    alpha = 1 - D_observed / D_expected
over the coincidence matrix of paired values within items; handles missing
ratings by construction.

Usage:
    python -m app.eval.rating_analysis --dir data/eval/rating
"""

from __future__ import annotations

import argparse
from itertools import permutations
from pathlib import Path

import numpy as np
import pandas as pd

from app.config import PROJECT_ROOT

CRITERIA = ["accuracy_1_5", "helpfulness_1_5", "respectfulness_1_5"]

DEFAULT_DIR = PROJECT_ROOT / "data" / "eval" / "rating"


def _delta_squared(a: float, b: float, metric: str, values: list[float]) -> float:
    """Squared difference function for the chosen alpha metric."""
    if metric == "nominal":
        return 0.0 if a == b else 1.0
    if metric == "interval":
        return (a - b) ** 2
    if metric == "ordinal":
        # Sum of coincidence-weighted ranks between the two values.
        values_sorted = sorted(set(values))
        ia, ib = values_sorted.index(a), values_sorted.index(b)
        lo, hi = min(ia, ib), max(ia, ib)
        span = sum(values.count(v) for v in values_sorted[lo : hi + 1])
        half_ends = (values.count(values_sorted[ia]) + values.count(values_sorted[ib])) / 2
        return (span - half_ends) ** 2
    raise ValueError(f"unknown metric {metric!r}")


def krippendorff_alpha(ratings: pd.DataFrame, metric: str = "interval") -> float:
    """Krippendorff's alpha for a units x raters matrix (NaN = missing).

    Returns NaN when there is nothing to compare (fewer than 2 pairable values
    overall) and 1.0 when there is no variation at all.
    """
    units: list[list[float]] = [
        [v for v in row if not pd.isna(v)] for _, row in ratings.iterrows()
    ]
    units = [u for u in units if len(u) >= 2]
    if not units:
        return float("nan")

    all_values: list[float] = [v for unit in units for v in unit]
    if len(set(all_values)) == 1:
        return 1.0

    # Observed disagreement: pairs within units, weighted by 1/(m_u - 1).
    observed_num = 0.0
    total_pairable = 0
    for unit in units:
        m = len(unit)
        total_pairable += m
        for a, b in permutations(unit, 2):
            observed_num += _delta_squared(a, b, metric, all_values) / (m - 1)
    observed = observed_num / total_pairable

    # Expected disagreement: all cross pairs of pairable values.
    n = len(all_values)
    expected_num = sum(
        _delta_squared(a, b, metric, all_values) for a, b in permutations(all_values, 2)
    )
    expected = expected_num / (n * (n - 1))
    if expected == 0:
        return 1.0
    return 1.0 - observed / expected


def load_sheets(directory: Path) -> dict[str, pd.DataFrame]:
    """Load rater sheets keyed by rater name; validate scores are 1-5 or blank."""
    sheets: dict[str, pd.DataFrame] = {}
    for path in sorted(directory.glob("rating_sheet_rater*.csv")):
        df = pd.read_csv(path, encoding="utf-8-sig")
        for criterion in CRITERIA:
            df[criterion] = pd.to_numeric(df[criterion], errors="coerce")
            bad = df[criterion].dropna()
            if not bad.between(1, 5).all():
                raise ValueError(f"{path.name}: {criterion} contains values outside 1-5")
        sheets[path.stem.replace("rating_sheet_", "")] = df
    if not sheets:
        raise SystemExit(f"No rating_sheet_rater*.csv files found in {directory}")
    return sheets


def analyze(directory: Path, metric: str = "interval") -> dict:
    sheets = load_sheets(directory)
    results: dict = {"n_raters": len(sheets), "criteria": {}}
    for criterion in CRITERIA:
        # units x raters matrix joined on item_id.
        matrix = pd.DataFrame(
            {rater: df.set_index("item_id")[criterion] for rater, df in sheets.items()}
        )
        rated = matrix.dropna(how="all")
        values = matrix.values.flatten()
        values = values[~pd.isna(values)]
        results["criteria"][criterion] = {
            "n_items_rated": int(len(rated)),
            "n_ratings": int(len(values)),
            "mean": round(float(np.mean(values)), 3) if len(values) else None,
            "sd": round(float(np.std(values, ddof=1)), 3) if len(values) > 1 else None,
            "krippendorff_alpha": (
                round(krippendorff_alpha(matrix, metric=metric), 3)
                if len(values)
                else None
            ),
        }
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default=str(DEFAULT_DIR))
    parser.add_argument("--metric", choices=["nominal", "interval", "ordinal"], default="interval")
    args = parser.parse_args()

    results = analyze(Path(args.dir), metric=args.metric)
    print(f"Raters: {results['n_raters']}  (alpha metric: {args.metric})")
    print(f"{'criterion':<22}{'items':>6}{'ratings':>9}{'mean':>7}{'sd':>7}{'alpha':>8}")
    for criterion, stats in results["criteria"].items():
        print(
            f"{criterion:<22}{stats['n_items_rated']:>6}{stats['n_ratings']:>9}"
            f"{str(stats['mean']):>7}{str(stats['sd']):>7}{str(stats['krippendorff_alpha']):>8}"
        )
    print(
        "\nInterpretation guide (Krippendorff): alpha >= 0.800 reliable; "
        "0.667-0.800 tentative; below 0.667 insufficient agreement."
    )


if __name__ == "__main__":
    main()
