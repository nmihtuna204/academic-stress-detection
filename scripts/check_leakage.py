"""Near-duplicate leakage between the frozen train and test splits.

The report's sharpest self-criticism rests on a number: test items are close
paraphrases of training items, so the classifier is recognising templates rather
than detecting stress. Until now that number had no script. This is it.

Why exact-duplicate checking is the wrong instrument here. The standard control
asks whether any test string appears verbatim in training. On this corpus it
passes perfectly - 466 distinct texts, none crossing a split - and passing tells
you almost nothing, because the corpus is generated from 41 sentence templates.
Two items from one template differ in a few slots and are different strings, so
exact matching scores them as unrelated while a model sees near-identical
surface form. Measuring the *nearest neighbour* rather than an exact hit is what
makes the problem visible.

Three similarity measures are reported, deliberately.

    difflib  `difflib.SequenceMatcher` ratio - the headline, and the measure the
             report has always described. It is the most literal notion of "how
             much of this sentence is reused".
    word     TF-IDF over word unigrams, cosine - the standard, trivially
             replicable check.
    char     TF-IDF over word-boundary character 3-5-grams, cosine - catches
             reuse that survives inflection and spacing changes.

Reporting three is the point: if the conclusion held under only one it would be
an artefact of that metric. It holds under all three.

A note on provenance, because the figures here differ slightly from earlier ones.
AUDIT.md records the original method as "maximum `difflib` similarity", which
names the function but not the details that change its output: which pool the
test items were compared against (train, or train and validation), whether
`autojunk` was left at its default, and whether the text was normalised first.
Those variants were tried and none reproduces the previously cited
median 0.808 / p90 0.899 / max 0.924 / 36 of 70 above 0.80 exactly. Rather than
keep tuning a measure until it matched a target - which is the reverse of how a
measurement is supposed to work, and the opposite of what this project does
elsewhere - the method is pinned here in full and its output supersedes the
earlier figures. The conclusion is unchanged and now reproducible.

Usage:
    python scripts/check_leakage.py
    python scripts/check_leakage.py --examples 5
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import PROJECT_ROOT  # noqa: E402

OUT_PATH = PROJECT_ROOT / "data" / "eval" / "leakage.md"

TFIDF_MEASURES = {
    "word": dict(analyzer="word", ngram_range=(1, 1)),
    "char": dict(analyzer="char_wb", ngram_range=(3, 5)),
}

# Pinned so the numbers are reproducible: test items are compared against the
# TRAINING split only (the data the model actually saw), `autojunk` is left at
# the library default, and the text is compared as stored with no normalisation.
DIFFLIB_POOL = "train"
DIFFLIB_AUTOJUNK = True


def load_splits() -> pd.DataFrame:
    """Load the frozen split as the evaluation harness sees it."""
    from app.eval.datasets import build_synthetic_dataset

    return build_synthetic_dataset()


def exact_duplicate_check(df: pd.DataFrame) -> dict:
    """The control that passes - reported so the reader can see it pass."""
    train = set(df[df.split == "train"]["text"].astype(str))
    out = {"n_total": len(df), "n_distinct": df["text"].nunique()}
    for split in ("val", "test"):
        texts = df[df.split == split]["text"].astype(str)
        out[f"{split}_exact_in_train"] = int(sum(1 for t in texts if t in train))
        out[f"{split}_n"] = int(len(texts))
    return out


def nearest_neighbour_similarity(
    df: pd.DataFrame, split: str, measure: str
) -> tuple[np.ndarray, np.ndarray]:
    """Max similarity of each `split` item to ANY training item.

    Returns (best_similarity, index_of_nearest_training_item).
    """
    train = df[df.split == "train"]["text"].astype(str).tolist()
    held = df[df.split == split]["text"].astype(str).tolist()
    vec = TfidfVectorizer(**TFIDF_MEASURES[measure])
    matrix_train = vec.fit_transform(train)
    matrix_held = vec.transform(held)
    sims = (matrix_held @ matrix_train.T).toarray()
    return sims.max(axis=1), sims.argmax(axis=1)


def difflib_nearest(df: pd.DataFrame, split: str) -> tuple[np.ndarray, np.ndarray]:
    """Max `difflib.SequenceMatcher` ratio of each held-out item to any train item.

    Quadratic, so the cheap bounds `real_quick_ratio` and `quick_ratio` prune
    candidates that cannot beat the best score found so far. Both are upper
    bounds on `ratio()`, so pruning on them changes the runtime and not the
    result.
    """
    import difflib

    pool = df[df.split == DIFFLIB_POOL]["text"].astype(str).tolist()
    held = df[df.split == split]["text"].astype(str).tolist()
    best = np.zeros(len(held))
    which = np.zeros(len(held), dtype=int)
    matcher = difflib.SequenceMatcher(autojunk=DIFFLIB_AUTOJUNK)
    for i, text in enumerate(held):
        matcher.set_seq2(text)
        top, top_idx = 0.0, 0
        for j, candidate in enumerate(pool):
            matcher.set_seq1(candidate)
            if matcher.real_quick_ratio() <= top or matcher.quick_ratio() <= top:
                continue
            ratio = matcher.ratio()
            if ratio > top:
                top, top_idx = ratio, j
        best[i], which[i] = top, top_idx
    return best, which


def summarise(values: np.ndarray) -> dict:
    return {
        "n": int(values.size),
        "median": float(np.median(values)),
        "mean": float(values.mean()),
        "p90": float(np.percentile(values, 90)),
        "max": float(values.max()),
        "over_80": int((values > 0.80).sum()),
        "over_90": int((values > 0.90).sum()),
        "pct_over_80": float((values > 0.80).mean() * 100),
    }


def run(n_examples: int = 3, out_path: Path | None = None) -> dict:
    out_path = Path(out_path) if out_path else OUT_PATH
    df = load_splits()
    exact = exact_duplicate_check(df)

    train_texts = df[df.split == "train"]["text"].astype(str).tolist()
    results: dict[str, dict] = {}
    examples: list[tuple[float, str, str]] = []

    for split in ("val", "test"):
        best, nearest = difflib_nearest(df, split)
        results[f"{split}_difflib"] = summarise(best)
        if split == "test":
            held = df[df.split == "test"]["text"].astype(str).tolist()
            order = np.argsort(-best)[:n_examples]
            examples = [
                (float(best[i]), held[i], train_texts[int(nearest[i])]) for i in order
            ]

    for measure in TFIDF_MEASURES:
        for split in ("val", "test"):
            best, _ = nearest_neighbour_similarity(df, split, measure)
            results[f"{split}_{measure}"] = summarise(best)

    _write_markdown(exact, results, examples, out_path)
    _print_console(exact, results, examples)
    return {"exact": exact, "similarity": results}


def _print_console(exact: dict, results: dict, examples: list) -> None:
    print("Near-duplicate leakage check")
    print(f"\n  corpus: {exact['n_total']} rows, {exact['n_distinct']} distinct texts")
    print("\n1. Exact-duplicate control (the standard check)")
    for split in ("val", "test"):
        n_dup = exact[f"{split}_exact_in_train"]
        verdict = "PASSES" if n_dup == 0 else "FAILS"
        print(f"  {split:5s} {n_dup}/{exact[f'{split}_n']} items appear verbatim in train -> {verdict}")

    print("\n2. Nearest-neighbour similarity to any training item")
    print(f"  {'split/measure':16s} {'median':>7s} {'p90':>7s} {'max':>7s} {'>0.80':>7s} {'>0.90':>7s}")
    for key, s in results.items():
        print(
            f"  {key:16s} {s['median']:7.3f} {s['p90']:7.3f} {s['max']:7.3f} "
            f"{s['over_80']:7d} {s['over_90']:7d}"
        )

    if examples:
        print("\n3. Closest test/train pairs (difflib, the headline measure)")
        for sim, held, near in examples:
            print(f"\n  similarity {sim:.3f}")
            print(f"    test  : {held[:140]}")
            print(f"    train : {near[:140]}")


def _write_markdown(exact: dict, results: dict, examples: list, out_path: Path) -> None:
    head = results["test_difflib"]
    test_word = results["test_word"]
    test_char = results["test_char"]
    lines = [
        "# Near-duplicate leakage between train and test",
        "",
        f"Generated by `python scripts/check_leakage.py` on {pd.Timestamp.now():%Y-%m-%d}.",
        "",
        "## 1. The exact-duplicate control passes",
        "",
        f"The corpus holds {exact['n_total']} rows and {exact['n_distinct']} distinct texts.",
        "",
        "| Split | Items appearing verbatim in train | Verdict |",
        "|---|---:|---|",
    ]
    for split in ("val", "test"):
        n_dup = exact[f"{split}_exact_in_train"]
        lines.append(
            f"| {split} | {n_dup} / {exact[f'{split}_n']} | "
            f"{'passes' if n_dup == 0 else 'FAILS'} |"
        )
    lines += [
        "",
        "This is the control most papers report, and on this corpus it is the wrong",
        "instrument. The texts are generated from 41 sentence templates, so two items",
        "from one template differ in a few slots: different strings, near-identical",
        "surface form. Exact matching scores them as unrelated.",
        "",
        "## 2. Nearest-neighbour similarity tells the real story",
        "",
        "For each held-out item, the maximum similarity to **any** training item.",
        "",
        "| Split / measure | median | mean | p90 | max | > 0.80 | > 0.90 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for key, s in results.items():
        lines.append(
            f"| {key} | {s['median']:.3f} | {s['mean']:.3f} | {s['p90']:.3f} | "
            f"{s['max']:.3f} | {s['over_80']} / {s['n']} | {s['over_90']} / {s['n']} |"
        )
    lines += [
        "",
        "`difflib` is `SequenceMatcher.ratio()` against the training split; `word` and",
        "`char` are TF-IDF cosines over word unigrams and word-boundary character",
        "3-5-grams. All three are reported so the conclusion cannot be an artefact of",
        "one metric.",
        "",
        "**Reading.** On the test split the median nearest-neighbour similarity is "
        f"**{head['median']:.3f}** (difflib), **{test_word['median']:.3f}** (word TF-IDF) "
        f"and **{test_char['median']:.3f}** (char TF-IDF); under the headline measure "
        f"**{head['over_80']} of {head['n']}** test items "
        f"({head['pct_over_80']:.0f} %) sit above 0.80. "
        "The model is therefore largely being asked to recognise wording it has already",
        "seen, not to detect stress. Every text-classification figure in this project",
        "should be read as a pipeline demonstration on that basis.",
        "",
        "## 3. The closest pairs, verbatim",
        "",
        "Judge the measure yourself rather than taking the number on trust. These are",
        "the nearest neighbours under the headline `difflib` measure.",
        "",
    ]
    for sim, held, near in examples:
        lines += [
            f"**similarity {sim:.3f}**",
            "",
            f"- test:  {held}",
            f"- train: {near}",
            "",
        ]
    lines += [
        "## Method and provenance",
        "",
        "Splits are the frozen ones the evaluation harness uses. Similarity is cosine",
        "over TF-IDF vectors fitted on the training split only, so no test text",
        "influences the vocabulary or the IDF weights.",
        "",
        "Earlier drafts cited a median of 0.808 with 36 of 70 items above 0.80. The",
        "method behind those figures was never recorded and is not reproduced exactly by",
        "any variant tried here. The numbers above supersede them: the conclusion is",
        "unchanged, and it is now checkable.",
        "",
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--examples", type=int, default=3, help="closest pairs to print")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    run(n_examples=args.examples, out_path=args.out)
    print(f"\nWrote {args.out or OUT_PATH}")


if __name__ == "__main__":
    main()
