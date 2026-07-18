"""Classical baseline for Vietnamese student stress detection.

Establishes reference numbers (before any deep model such as PhoBERT) using
TF-IDF features + linear classifiers, plus trivial majority/random baselines.

It also creates a reproducible, stratified train/val/test split and writes it
back to `data/stress_dataset_split.csv` (new `split` column) so that the
PhoBERT fine-tune reuses *exactly* the same partition — otherwise the two
scores are not comparable.

Reported metrics prioritise macro-F1 over accuracy because the label
distribution is imbalanced.

Usage:
    python app/baseline.py --data data/stress_dataset_clean.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

LABELS = ["Low", "Moderate", "High"]
TEXT_COL = "text"
LABEL_COL = "label"
SEED = 42


def make_split(df: pd.DataFrame, seed: int = SEED) -> pd.DataFrame:
    """Add a stratified `split` column (70% train / 15% val / 15% test)."""
    idx = np.arange(len(df))
    train_idx, temp_idx = train_test_split(
        idx, test_size=0.30, random_state=seed, stratify=df[LABEL_COL]
    )
    val_idx, test_idx = train_test_split(
        temp_idx, test_size=0.50, random_state=seed,
        stratify=df[LABEL_COL].iloc[temp_idx],
    )
    split = np.empty(len(df), dtype=object)
    split[train_idx] = "train"
    split[val_idx] = "val"
    split[test_idx] = "test"
    out = df.copy()
    out["split"] = split
    return out


def evaluate(name: str, y_true, y_pred) -> dict:
    """Print a metrics block and return the headline scores."""
    acc = float((np.asarray(y_true) == np.asarray(y_pred)).mean())
    macro_f1 = f1_score(y_true, y_pred, labels=LABELS, average="macro", zero_division=0)
    weighted_f1 = f1_score(y_true, y_pred, labels=LABELS, average="weighted", zero_division=0)

    print(f"\n=== {name} ===")
    print(f"accuracy    : {acc:.4f}")
    print(f"macro-F1    : {macro_f1:.4f}")
    print(f"weighted-F1 : {weighted_f1:.4f}")
    print(classification_report(y_true, y_pred, labels=LABELS, zero_division=0, digits=3))
    print("confusion matrix (rows=true, cols=pred), order =", LABELS)
    print(confusion_matrix(y_true, y_pred, labels=LABELS))
    return {"model": name, "accuracy": acc, "macro_f1": macro_f1, "weighted_f1": weighted_f1}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data/stress_dataset_clean.csv"))
    parser.add_argument(
        "--split-out", type=Path, default=Path("data/stress_dataset_split.csv"),
        help="where to write the dataset with the added split column",
    )
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()

    df = pd.read_csv(args.data, encoding="utf-8-sig")
    if TEXT_COL not in df.columns or LABEL_COL not in df.columns:
        raise SystemExit(f"expected columns '{TEXT_COL}' and '{LABEL_COL}', got {list(df.columns)}")

    df = make_split(df, seed=args.seed)
    args.split_out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.split_out, index=False, encoding="utf-8-sig")

    train = df[df["split"] == "train"]
    val = df[df["split"] == "val"]
    test = df[df["split"] == "test"]
    print(f"data: {len(df)} rows  ->  train {len(train)} | val {len(val)} | test {len(test)}")
    print("train label dist:", train[LABEL_COL].value_counts().to_dict())
    print("test  label dist:", test[LABEL_COL].value_counts().to_dict())

    # Fit on train, tune nothing here (single config) -> report on val and test.
    X_train, y_train = train[TEXT_COL].tolist(), train[LABEL_COL].tolist()
    X_test, y_test = test[TEXT_COL].tolist(), test[LABEL_COL].tolist()

    results: list[dict] = []

    # --- Trivial baselines -------------------------------------------------
    for strategy in ("most_frequent", "stratified"):
        dummy = DummyClassifier(strategy=strategy, random_state=args.seed)
        dummy.fit(X_train, y_train)
        results.append(evaluate(f"Dummy ({strategy})", y_test, dummy.predict(X_test)))

    # --- TF-IDF word (1-2 gram) + Logistic Regression ----------------------
    word_lr = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True)),
        ("clf", LogisticRegression(max_iter=2000, C=5.0, class_weight="balanced")),
    ])
    word_lr.fit(X_train, y_train)
    results.append(evaluate("TF-IDF(word 1-2) + LogReg", y_test, word_lr.predict(X_test)))

    # --- TF-IDF char (3-5 gram) + Linear SVM (robust to Vietnamese tokens) --
    char_svm = Pipeline([
        ("tfidf", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2, sublinear_tf=True)),
        ("clf", LinearSVC(C=1.0, class_weight="balanced")),
    ])
    char_svm.fit(X_train, y_train)
    results.append(evaluate("TF-IDF(char 3-5) + LinearSVM", y_test, char_svm.predict(X_test)))

    # --- Summary -----------------------------------------------------------
    summary = pd.DataFrame(results).sort_values("macro_f1", ascending=False)
    print("\n" + "=" * 60)
    print("SUMMARY (test set, sorted by macro-F1)")
    print("=" * 60)
    print(summary.to_string(index=False,
                            formatters={c: "{:.4f}".format for c in ["accuracy", "macro_f1", "weighted_f1"]}))

    best_f1 = summary["macro_f1"].max()
    print(f"\nSplit written to: {args.split_out}")
    if best_f1 > 0.90:
        print(
            "\n[!] DIAGNOSTIC: a plain TF-IDF linear model already reaches "
            f"macro-F1 = {best_f1:.3f}.\n"
            "    On genuinely hard, real free-text this should be far lower. "
            "Such a high score is a strong sign the text is template-generated "
            "and trivially separable (label leakage). Treat these numbers as a "
            "pipeline smoke-test, not evidence of model quality."
        )


if __name__ == "__main__":
    main()
