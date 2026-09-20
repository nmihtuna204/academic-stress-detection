"""Fine-tune PhoBERT for Vietnamese student stress detection, over several seeds.

Two things changed on 2026-09-19, and both matter for what the numbers mean:

1. **The training target is now the evaluation target.** The first model
   (2026-07-17) learned the 3-class `label` column of `stress_dataset_split.csv`,
   which is NOT the label the evaluation scores against: the harness derives a
   4-class label with `app.scoring.derive_ground_truth`. The two disagree on 89 of
   466 rows - 69 Severe rows were collapsed into High, 16 Low rows are Moderate
   under the derived rule, and 4 Moderate rows are High. `--labels 4` (the
   default) trains on the derived label, so the model is scored on what it was
   taught. `--labels 3` reproduces the original setup.
2. **Several seeds, not one.** A single fine-tuning run on 326 examples says
   little: seed alone moves the score. Every run is recorded, and the summary
   reports mean and sample standard deviation across seeds.

Model selection uses the VALIDATION split only - the best epoch within a seed,
and the best seed for `--save-best-to`. The test split is scored once per seed
and never used to choose anything.

Segmentation: PhoBERT was pre-trained on text word-segmented by VnCoreNLP's
RDRSegmenter ("áp lực" -> "áp_lực"). `--segment vncorenlp` applies it to every
split; `--segment none` feeds raw text. Whichever is used at training time must
also be used at inference, so a segmented model needs Java in production. The
wrapper `py_vncorenlp` needs JAVA_HOME and a VnCoreNLP directory WITHOUT spaces
in its path (the jar URL-encodes spaces and then cannot find its own models), so
the default is C:/ProgramData/vncorenlp; override with VNCORENLP_DIR.

The split file is reused unchanged, so no fine-tuning data reaches the test set.

Usage:
    python research/phobert_finetune.py --labels 4 --segment none --seeds 13 42 7
    python research/phobert_finetune.py --labels 4 --segment vncorenlp --seeds 13 42 7
    python research/phobert_finetune.py --summarise        # table over all recorded runs
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import cohen_kappa_score, confusion_matrix, f1_score
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer, get_linear_schedule_with_warmup

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

MODEL_NAME = "vinai/phobert-base"
LABEL_SPACES = {
    3: ["Low", "Moderate", "High"],
    4: ["Low", "Moderate", "High", "Severe"],
}
RUNS_DIR = PROJECT_ROOT / "data" / "eval" / "phobert_runs"
SEGMENT_CACHE = PROJECT_ROOT / "data" / "eval" / "phobert_segmented_text.csv"
# Longest text in the dataset is 87 PhoBERT tokens unsegmented, so 96 truncates
# nothing and is much cheaper on CPU than the original 160.
DEFAULT_MAX_LEN = 96


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def load_frame(labels: int) -> pd.DataFrame:
    """The frozen split with the requested label column as `target`."""
    split = pd.read_csv(PROJECT_ROOT / "data" / "stress_dataset_split.csv", encoding="utf-8-sig")
    if labels == 3:
        return split.assign(target=split["label"])[["student_id", "text", "split", "target"]]

    from app.eval.datasets import build_synthetic_dataset

    derived = build_synthetic_dataset()[["student_id", "label"]].rename(columns={"label": "target"})
    merged = split[["student_id", "text", "split"]].merge(derived, on="student_id", how="inner")
    if len(merged) != len(split):
        raise SystemExit(f"label join lost rows: {len(merged)} of {len(split)}")
    return merged


def segment_texts(frame: pd.DataFrame) -> pd.Series:
    """RDRSegmenter output per row, cached on disk (the JVM start is the slow part)."""
    if SEGMENT_CACHE.exists():
        cache = pd.read_csv(SEGMENT_CACHE, encoding="utf-8")
        if set(frame["student_id"]) <= set(cache["student_id"]):
            lookup = dict(zip(cache["student_id"], cache["segmented"], strict=True))
            return frame["student_id"].map(lookup)

    import py_vncorenlp

    save_dir = os.environ.get("VNCORENLP_DIR", "C:/ProgramData/vncorenlp")
    cwd = os.getcwd()
    try:  # py_vncorenlp changes the working directory as a side effect
        segmenter = py_vncorenlp.VnCoreNLP(annotators=["wseg"], save_dir=save_dir)
    finally:
        os.chdir(cwd)
    segmented = [" ".join(segmenter.word_segment(str(t))) for t in frame["text"]]
    SEGMENT_CACHE.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"student_id": frame["student_id"], "segmented": segmented}).to_csv(
        SEGMENT_CACHE, index=False, encoding="utf-8"
    )
    return pd.Series(segmented, index=frame.index)


class StressDataset(Dataset):
    def __init__(self, texts, labels, tokenizer, max_len: int, label2id: dict[str, int]):
        self.enc = tokenizer(
            list(texts), truncation=True, padding="max_length",
            max_length=max_len, return_tensors="pt",
        )
        self.labels = torch.tensor([label2id[label] for label in labels], dtype=torch.long)

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, i):
        item = {k: v[i] for k, v in self.enc.items()}
        item["labels"] = self.labels[i]
        return item


@torch.no_grad()
def predict(model, loader) -> np.ndarray:
    model.eval()
    preds = []
    for batch in loader:
        logits = model(input_ids=batch["input_ids"], attention_mask=batch["attention_mask"]).logits
        preds.append(logits.argmax(dim=-1).numpy())
    return np.concatenate(preds)


def metrics(y_true_ids, y_pred_ids, label_names: list[str]) -> dict:
    y_true = [label_names[i] for i in y_true_ids]
    y_pred = [label_names[i] for i in y_pred_ids]
    per_class = f1_score(y_true, y_pred, labels=label_names, average=None, zero_division=0)
    return {
        "accuracy": round(float(np.mean(np.asarray(y_true) == np.asarray(y_pred))), 4),
        "macro_f1": round(float(f1_score(y_true, y_pred, labels=label_names, average="macro", zero_division=0)), 4),
        "cohen_kappa": round(float(cohen_kappa_score(y_true, y_pred, labels=label_names)), 4),
        "f1_per_class": {name: round(float(v), 4) for name, v in zip(label_names, per_class, strict=True)},
        "confusion": confusion_matrix(y_true, y_pred, labels=label_names).tolist(),
    }


def train_one_seed(frame: pd.DataFrame, args, seed: int, tokenizer) -> tuple[dict, dict]:
    """Train with one seed; return (record, best_state_dict)."""
    label_names = LABEL_SPACES[args.labels]
    label2id = {name: i for i, name in enumerate(label_names)}
    set_seed(seed)

    parts = {name: frame[frame["split"] == name] for name in ("train", "val", "test")}
    datasets = {
        name: StressDataset(part["model_text"], part["target"], tokenizer, args.max_len, label2id)
        for name, part in parts.items()
    }
    generator = torch.Generator().manual_seed(seed)
    train_loader = DataLoader(datasets["train"], batch_size=args.batch_size, shuffle=True, generator=generator)
    val_loader = DataLoader(datasets["val"], batch_size=64)
    test_loader = DataLoader(datasets["test"], batch_size=64)

    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME,
        num_labels=len(label_names),
        id2label=dict(enumerate(label_names)),
        label2id=label2id,
    )

    # Inverse-frequency class weights, computed on the train split only.
    counts = parts["train"]["target"].map(label2id).value_counts().reindex(range(len(label_names)), fill_value=0)
    weights = torch.tensor(len(parts["train"]) / (len(label_names) * np.maximum(counts.values, 1)), dtype=torch.float)
    loss_fn = torch.nn.CrossEntropyLoss(weight=weights)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    total_steps = len(train_loader) * args.epochs
    scheduler = get_linear_schedule_with_warmup(optimizer, int(0.1 * total_steps), total_steps)

    curve: list[dict] = []
    best_val_f1, best_epoch, best_state = -1.0, 0, None
    started = time.perf_counter()
    for epoch in range(1, args.epochs + 1):
        model.train()
        running = 0.0
        for batch in train_loader:
            optimizer.zero_grad()
            logits = model(input_ids=batch["input_ids"], attention_mask=batch["attention_mask"]).logits
            loss = loss_fn(logits, batch["labels"])
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            running += loss.item()
        val_f1 = f1_score(datasets["val"].labels.numpy(), predict(model, val_loader), average="macro", zero_division=0)
        curve.append({"epoch": epoch, "train_loss": round(running / len(train_loader), 4), "val_macro_f1": round(float(val_f1), 4)})
        print(f"  seed {seed} epoch {epoch}/{args.epochs} loss={curve[-1]['train_loss']:.4f} val_macroF1={val_f1:.4f}", flush=True)
        if val_f1 > best_val_f1:
            best_val_f1, best_epoch = float(val_f1), epoch
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}

    model.load_state_dict(best_state)
    record = {
        "labels": args.labels,
        "segment": args.segment,
        "seed": seed,
        "epochs": args.epochs,
        "lr": args.lr,
        "batch_size": args.batch_size,
        "max_len": args.max_len,
        "best_epoch": best_epoch,
        "train_seconds": round(time.perf_counter() - started, 1),
        "curve": curve,
        "val": metrics(datasets["val"].labels.numpy(), predict(model, val_loader), label_names),
        "test": metrics(datasets["test"].labels.numpy(), predict(model, test_loader), label_names),
    }
    return record, best_state


def run_tag(labels: int, segment: str) -> str:
    return f"{labels}c_{segment}"


def train(args) -> None:
    frame = load_frame(args.labels)
    frame["model_text"] = segment_texts(frame) if args.segment == "vncorenlp" else frame["text"]
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, use_fast=False)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    counts = frame.groupby(["split", "target"]).size().unstack(fill_value=0)
    print(f"labels={args.labels} segment={args.segment} seeds={args.seeds}\n{counts}\n", flush=True)

    best = None
    for seed in args.seeds:
        record, state = train_one_seed(frame, args, seed, tokenizer)
        path = RUNS_DIR / f"{run_tag(args.labels, args.segment)}_seed{seed}.json"
        path.write_text(json.dumps(record, indent=1), encoding="utf-8")
        print(
            f"seed {seed}: val macro-F1 {record['val']['macro_f1']:.4f} | "
            f"test acc {record['test']['accuracy']:.4f} macro-F1 {record['test']['macro_f1']:.4f} "
            f"({record['train_seconds']:.0f}s) -> {path.name}",
            flush=True,
        )
        if args.save_best_to and (best is None or record["val"]["macro_f1"] > best[0]["val"]["macro_f1"]):
            best = (record, state)
        del state

    if args.save_best_to and best is not None:
        record, state = best
        label_names = LABEL_SPACES[args.labels]
        model = AutoModelForSequenceClassification.from_pretrained(
            MODEL_NAME, num_labels=len(label_names),
            id2label=dict(enumerate(label_names)), label2id={n: i for i, n in enumerate(label_names)},
        )
        model.load_state_dict(state)
        out = Path(args.save_best_to)
        out.mkdir(parents=True, exist_ok=True)
        model.save_pretrained(out)
        tokenizer.save_pretrained(out)
        (out / "training_record.json").write_text(json.dumps(record, indent=1), encoding="utf-8")
        print(f"\nsaved seed {record['seed']} (best on VALIDATION, {record['val']['macro_f1']:.4f}) to {out}")

    print("\n" + summarise())


def summarise() -> str:
    """Markdown table over every recorded run, grouped by configuration."""
    rows = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(RUNS_DIR.glob("*.json"))]
    if not rows:
        return "No recorded runs."
    lines = [
        "# PhoBERT fine-tuning across seeds",
        "",
        "> **Computed on SYNTHETIC data** (the frozen 326/70/70 split). Test is scored once per seed "
        "and never used for selection. Mean ± sample SD across seeds.",
        "",
        "| labels | segmentation | seeds | test accuracy | test macro-F1 | test kappa | val macro-F1 | per seed (test macro-F1) |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    groups: dict[tuple, list[dict]] = {}
    for r in rows:
        groups.setdefault((r["labels"], r["segment"]), []).append(r)
    for (labels, segment), rs in sorted(groups.items()):
        def ms(key, split="test", rs=rs):
            vals = np.array([r[split][key] for r in rs])
            sd = vals.std(ddof=1) if len(vals) > 1 else 0.0
            return f"{vals.mean():.3f} ± {sd:.3f}"
        per_seed = ", ".join(f"{r['seed']}: {r['test']['macro_f1']:.3f}" for r in sorted(rs, key=lambda r: r["seed"]))
        lines.append(
            f"| {labels}-class | {segment} | {len(rs)} | {ms('accuracy')} | {ms('macro_f1')} | "
            f"{ms('cohen_kappa')} | {ms('macro_f1', 'val')} | {per_seed} |"
        )
    lines += ["", "Per-class test F1, mean across seeds:", ""]
    for (labels, segment), rs in sorted(groups.items()):
        names = LABEL_SPACES[labels]
        means = {n: np.mean([r["test"]["f1_per_class"][n] for r in rs]) for n in names}
        lines.append(f"- {labels}-class / {segment}: " + ", ".join(f"{n} {v:.3f}" for n, v in means.items()))
    text = "\n".join(lines) + "\n"
    (PROJECT_ROOT / "data" / "eval" / "phobert_finetune.md").write_text(text, encoding="utf-8")
    return text


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--labels", type=int, choices=sorted(LABEL_SPACES), default=4)
    parser.add_argument("--segment", choices=["none", "vncorenlp"], default="none")
    parser.add_argument("--seeds", type=int, nargs="+", default=[13, 42, 7])
    parser.add_argument("--epochs", type=int, default=6)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--max-len", type=int, default=DEFAULT_MAX_LEN)
    parser.add_argument("--save-best-to", default=None,
                        help="Save the seed with the best VALIDATION macro-F1 as a deployable model.")
    parser.add_argument("--summarise", action="store_true", help="Only print the table over recorded runs.")
    args = parser.parse_args()
    if args.summarise:
        print(summarise())
        return
    train(args)


if __name__ == "__main__":
    main()
