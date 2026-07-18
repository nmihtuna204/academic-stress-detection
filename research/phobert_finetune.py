"""Fine-tune PhoBERT for 3-class Vietnamese student stress detection.

Reuses the exact train/val/test split produced by `app/baseline.py`
(`data/stress_dataset_split.csv`) so the PhoBERT score is directly comparable
to the TF-IDF baselines. Uses a manual training loop (no Trainer) to stay
robust across transformers versions.

Note on segmentation: PhoBERT was pre-trained on word-segmented text
(VnCoreNLP). We feed raw text here to avoid an extra dependency; for the
final thesis runs, segment `text` first (underthesea / pyvi / VnCoreNLP) for
a small but real quality gain.

Usage:
    python app/phobert_finetune.py --epochs 4 --batch-size 16
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer, get_linear_schedule_with_warmup

LABELS = ["Low", "Moderate", "High"]
LABEL2ID = {label: i for i, label in enumerate(LABELS)}
MODEL_NAME = "vinai/phobert-base"


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


class StressDataset(Dataset):
    def __init__(self, texts, labels, tokenizer, max_len: int):
        self.enc = tokenizer(
            list(texts), truncation=True, padding="max_length",
            max_length=max_len, return_tensors="pt",
        )
        self.labels = torch.tensor([LABEL2ID[l] for l in labels], dtype=torch.long)

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, i):
        item = {k: v[i] for k, v in self.enc.items()}
        item["labels"] = self.labels[i]
        return item


@torch.no_grad()
def predict(model, loader, device) -> np.ndarray:
    model.eval()
    preds = []
    for batch in loader:
        batch = {k: v.to(device) for k, v in batch.items()}
        logits = model(input_ids=batch["input_ids"], attention_mask=batch["attention_mask"]).logits
        preds.append(logits.argmax(dim=-1).cpu().numpy())
    return np.concatenate(preds)


def report(name: str, y_true_ids, y_pred_ids) -> float:
    y_true = [LABELS[i] for i in y_true_ids]
    y_pred = [LABELS[i] for i in y_pred_ids]
    macro_f1 = f1_score(y_true, y_pred, labels=LABELS, average="macro", zero_division=0)
    acc = float((np.asarray(y_true) == np.asarray(y_pred)).mean())
    print(f"\n=== {name} ===  accuracy={acc:.4f}  macro-F1={macro_f1:.4f}")
    print(classification_report(y_true, y_pred, labels=LABELS, zero_division=0, digits=3))
    print("confusion matrix (rows=true, cols=pred), order =", LABELS)
    print(confusion_matrix(y_true, y_pred, labels=LABELS))
    return macro_f1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data/stress_dataset_split.csv"))
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--max-len", type=int, default=160)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-dir", type=Path, default=Path("models/phobert-stress"))
    args = parser.parse_args()

    set_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"device: {device} | model: {MODEL_NAME}")

    df = pd.read_csv(args.data, encoding="utf-8-sig")
    if "split" not in df.columns:
        raise SystemExit("input must contain a 'split' column; run app/baseline.py first")
    train_df = df[df["split"] == "train"]
    val_df = df[df["split"] == "val"]
    test_df = df[df["split"] == "test"]
    print(f"train {len(train_df)} | val {len(val_df)} | test {len(test_df)}")

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, use_fast=False)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME, num_labels=len(LABELS))
    model.to(device)

    train_ds = StressDataset(train_df["text"], train_df["label"], tokenizer, args.max_len)
    val_ds = StressDataset(val_df["text"], val_df["label"], tokenizer, args.max_len)
    test_ds = StressDataset(test_df["text"], test_df["label"], tokenizer, args.max_len)

    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size)
    test_loader = DataLoader(test_ds, batch_size=args.batch_size)

    # Class weights to counter imbalance.
    counts = train_df["label"].map(LABEL2ID).value_counts().sort_index()
    weights = torch.tensor((len(train_df) / (len(LABELS) * counts.values)), dtype=torch.float, device=device)
    loss_fn = torch.nn.CrossEntropyLoss(weight=weights)

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    total_steps = len(train_loader) * args.epochs
    scheduler = get_linear_schedule_with_warmup(optimizer, int(0.1 * total_steps), total_steps)

    best_val_f1 = -1.0
    best_state = None
    for epoch in range(1, args.epochs + 1):
        model.train()
        running = 0.0
        for batch in train_loader:
            batch = {k: v.to(device) for k, v in batch.items()}
            optimizer.zero_grad()
            logits = model(input_ids=batch["input_ids"], attention_mask=batch["attention_mask"]).logits
            loss = loss_fn(logits, batch["labels"])
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            running += loss.item()

        val_pred = predict(model, val_loader, device)
        val_f1 = f1_score(val_ds.labels.numpy(), val_pred, average="macro", zero_division=0)
        print(f"epoch {epoch}/{args.epochs}  train_loss={running / len(train_loader):.4f}  val_macroF1={val_f1:.4f}")
        if val_f1 > best_val_f1:
            best_val_f1 = val_f1
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

    if best_state is not None:
        model.load_state_dict(best_state)
    print(f"\nbest val macro-F1 = {best_val_f1:.4f}")

    report("PhoBERT — VAL", val_ds.labels.numpy(), predict(model, val_loader, device))
    report("PhoBERT — TEST", test_ds.labels.numpy(), predict(model, test_loader, device))

    args.out_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(args.out_dir)
    tokenizer.save_pretrained(args.out_dir)
    print(f"\nsaved model to {args.out_dir}")


if __name__ == "__main__":
    main()
