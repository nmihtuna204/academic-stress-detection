"""Verify the 4-class PhoBERT checkpoint, and test it against the deployed one.

The multi-seed study (research/phobert_finetune.py) saved its best seed, chosen
on VALIDATION, to models/phobert-stress-4c. The application still loads the
3-class checkpoint in models/phobert-stress. Published macro-F1 is 0.613 for the
new model against 0.533 for the deployed one, which looks like an improvement.
This checks whether it is one.

Step 1 - the saved weights must reproduce the validation and test metrics
recorded at training time, or the script stops.

Step 2 - PLAN, fixed before any comparison was computed; reported whatever it
shows:
  Primary:   4-class vs the deployed 3-class, exact McNemar on accuracy, ONE
             pre-specified comparison, alpha 0.05.
  Secondary: 4-class vs llm_full and vs tfidf_lr, Holm across those two.
  RISKS R9:  tfidf_lr vs the deployed 3-class - the question "is 0.682 against
             0.533 real?" - one separate comparison, exact McNemar.
  Descriptive: macro-F1, QWK, within one level, and F1 on Severe.

Both systems are read on the comparison's 70 test items; the 4-class model's
items are aligned by text and its labels must equal the comparison labels. The
published llm_full predictions are read back under their pre-pinning cache keys
with a client that fails on any cache miss, so no provider call is made.

Regenerate the checkpoint (CPU, roughly 15-55 minutes per seed):
    python research/phobert_finetune.py --labels 4 --segment none --seeds 13 42 7 \\
        --save-best-to models/phobert-stress-4c

Usage:
    python scripts/phobert_checkpoint_compare.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "research"))
sys.path.insert(0, str(REPO / "scripts"))
os.environ.setdefault("HF_HUB_OFFLINE", "1")

import phobert_finetune as ft  # noqa: E402
import torch  # noqa: E402
from comparison_paired import _NoCalls  # noqa: E402
from torch.utils.data import DataLoader  # noqa: E402
from transformers import AutoModelForSequenceClassification, AutoTokenizer  # noqa: E402

import app.api.services as services  # noqa: E402
from app.eval import baselines  # noqa: E402
from app.eval.ablation import (  # noqa: E402
    holm,
    mcnemar_exact,
    ordinal_codes,
    paired_comparison,
    qwk,
    within_one,
)
from app.eval.datasets import load_eval_dataset  # noqa: E402
from app.eval.evaluate import compute_metrics  # noqa: E402

CHECKPOINT = REPO / "models" / "phobert-stress-4c"


def verified_test_predictions() -> tuple[dict[str, str], dict[str, str]]:
    """Test predictions and labels of the saved checkpoint, keyed by text, after checking it."""
    record = json.loads((CHECKPOINT / "training_record.json").read_text(encoding="utf-8"))
    labels = ft.LABEL_SPACES[4]
    label2id = {n: i for i, n in enumerate(labels)}
    frame = ft.load_frame(4)
    tokenizer = AutoTokenizer.from_pretrained(CHECKPOINT, use_fast=False)
    model = AutoModelForSequenceClassification.from_pretrained(CHECKPOINT).eval()
    by_text: dict[str, str] = {}
    for split in ("val", "test"):
        part = frame[frame["split"] == split]
        data = ft.StressDataset(part["text"], part["target"], tokenizer, record["max_len"], label2id)
        with torch.no_grad():
            pred = ft.predict(model, DataLoader(data, batch_size=64))
        got = ft.metrics(data.labels.numpy(), pred, labels)
        want = record[split]
        if abs(got["accuracy"] - want["accuracy"]) > 1e-4 or abs(got["macro_f1"] - want["macro_f1"]) > 1e-4:
            raise SystemExit(f"{split}: saved weights give {got['accuracy']:.4f}/{got['macro_f1']:.4f}, "
                             f"the record says {want['accuracy']:.4f}/{want['macro_f1']:.4f}")
        print(f"Verified {split}: accuracy {got['accuracy']:.4f}, macro-F1 {got['macro_f1']:.4f} "
              f"(seed {record['seed']}, best epoch {record['best_epoch']}) - matches the training record")
        if split == "test":
            by_text = {str(t): labels[i] for t, i in zip(part["text"], pred, strict=True)}
            truth = dict(zip(part["text"].astype(str), part["target"], strict=True))
    return by_text, truth


def main() -> int:
    by_text, truth = verified_test_predictions()
    df = load_eval_dataset("synthetic", out_dir=REPO / "data" / "eval")
    test = df[df["split"] == "test"]
    texts, y_true = test["text"].astype(str).tolist(), test["label"].tolist()
    if [truth.get(t) for t in texts] != y_true:
        raise SystemExit("the checkpoint's test labels do not match the comparison labels")

    original = services.needs_support_material
    services.needs_support_material = lambda *_a, **_k: False  # the published row predates pinning
    try:
        full = asyncio.run(baselines.run_llm_full(df, llm=_NoCalls()))
    finally:
        services.needs_support_material = original
    if full.notes.get("unusable"):
        raise SystemExit("llm_full predictions missing from the cache")

    systems = {
        "phobert_4c": [by_text[t] for t in texts],
        "phobert_3c_deployed": baselines.run_phobert_ft(df).y_pred,
        "llm_full": full.y_pred,
        "tfidf_lr": baselines.run_tfidf_lr(df).y_pred,
    }
    print(f"\n{'system':22} {'accuracy':>9} {'macro-F1':>9} {'QWK':>6} {'within 1':>9} {'F1 Severe':>10}")
    for name, pred in systems.items():
        m = compute_metrics(y_true, pred)
        print(f"{name:22} {m['accuracy']:9.3f} {m['macro_f1']:9.3f} {qwk(y_true, pred):6.3f} "
              f"{within_one(y_true, pred):9.3f} {m['per_class']['Severe']['f1-score']:10.3f}")

    table = paired_comparison(y_true, systems, reference="phobert_4c").set_index("config")
    p = table.loc["phobert_3c_deployed"]
    print("\nPRIMARY - 4-class vs deployed 3-class, one comparison:")
    print(f"  4-class alone correct {p['reference_only_correct']}, 3-class alone correct {p['other_only_correct']}, "
          f"exact McNemar p = {p['mcnemar_p']:.4f}; delta QWK (3-class minus 4-class) {p['delta_qwk']:+.3f} "
          f"[{p['delta_qwk_ci_low']:+.3f}, {p['delta_qwk_ci_high']:+.3f}]")

    secondary = table.loc[["llm_full", "tfidf_lr"]]
    print("\nSECONDARY - 4-class vs each, Holm across two:")
    for (name, r), adj in zip(secondary.iterrows(), holm(secondary["mcnemar_p"].tolist()), strict=True):
        print(f"  {name:9} 4-class alone {r['reference_only_correct']:2d}, {name} alone {r['other_only_correct']:2d}, "
              f"p = {r['mcnemar_p']:.4f}, Holm {adj:.4f}")

    t = ordinal_codes(y_true)
    b, c, pr = mcnemar_exact(ordinal_codes(systems["tfidf_lr"]) == t, ordinal_codes(systems["phobert_3c_deployed"]) == t)
    print(f"\nRISKS R9 - tfidf_lr vs deployed 3-class, one comparison: tfidf_lr alone correct {b}, "
          f"3-class alone correct {c}, exact McNemar p = {pr:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
