from original_paths import project_path
"""Fine-tune LiLT on the Social Welfare layout dataset.

Writes a results table after every epoch to epoch_results.txt,
formatted for screenshotting - one section per epoch, aligned columns.
"""

import faulthandler
faulthandler.enable()

import argparse
import json
import os

import numpy as np
import torch
from transformers import (
    AutoTokenizer,
    AutoModelForTokenClassification,
    TrainingArguments,
    Trainer,
    DataCollatorForTokenClassification,
    TrainerCallback,
)
from datasets import Dataset

MODEL_NAME = "nielsr/lilt-xlm-roberta-base"
DATA_DIR = project_path('layout_analysis/data')
OUTPUT_DIR = project_path('layout_analysis/models/lilt_sw_v1')
RESULTS_LOG = project_path('layout_analysis/epoch_results.txt')

LABEL_LIST = [
    "O", "CLAUSE", "text", "SECTION_TITLE", "Sub_Section", "METADATA",
    "TABLE", "FOOTER", "HEADER", "Page_header", "Signature", "Caption",
    "Fig_with_value", "Fig_without_value",
]
LABEL_TO_ID = {l: i for i, l in enumerate(LABEL_LIST)}
ID_TO_LABEL = {i: l for l, i in LABEL_TO_ID.items()}


def load_split(name):
    path = os.path.join(DATA_DIR, name)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def normalize_bbox(bbox, w, h):
    x1, y1, x2, y2 = bbox
    return [int(1000*x1/w), int(1000*y1/h), int(1000*x2/w), int(1000*y2/h)]


def pages_to_dataset(pages, smoke=False):
    if smoke:
        pages = pages[:5]
    records = {"words": [], "bboxes": [], "labels": []}
    for page in pages:
        w, h = page["image_width"], page["image_height"]
        words, boxes, labels = [], [], []
        for word in page["words"]:
            text = word["text"].strip()
            if not text:
                continue
            words.append(text)
            boxes.append(normalize_bbox(word["bbox"], w, h))
            labels.append(LABEL_TO_ID.get(word["label"], LABEL_TO_ID["O"]))
        if words:
            records["words"].append(words)
            records["bboxes"].append(boxes)
            records["labels"].append(labels)
    return Dataset.from_dict(records)


def tokenize_and_align(examples, tokenizer):
    tokenized = tokenizer(
        examples["words"], truncation=True, is_split_into_words=True,
        padding="max_length", max_length=128,
    )
    all_labels, all_bboxes = [], []
    for i, (label, bbox) in enumerate(zip(examples["labels"], examples["bboxes"])):
        word_ids = tokenized.word_ids(batch_index=i)
        prev_word = None
        label_ids, bbox_ids = [], []
        for word_id in word_ids:
            if word_id is None:
                label_ids.append(-100); bbox_ids.append([0, 0, 0, 0])
            elif word_id != prev_word:
                label_ids.append(label[word_id]); bbox_ids.append(bbox[word_id])
            else:
                label_ids.append(-100); bbox_ids.append(bbox[word_id])
            prev_word = word_id
        all_labels.append(label_ids)
        all_bboxes.append(bbox_ids)
    tokenized["labels"] = all_labels
    tokenized["bbox"] = all_bboxes
    return tokenized


def compute_metrics(eval_pred):
    predictions, labels = eval_pred
    predictions = np.argmax(predictions, axis=2)
    true_labels = [[] for _ in LABEL_LIST]
    pred_labels = [[] for _ in LABEL_LIST]
    for pred_seq, label_seq in zip(predictions, labels):
        for p, l in zip(pred_seq, label_seq):
            if l == -100:
                continue
            true_labels[l].append(1)
            pred_labels[l].append(1 if p == l else 0)
    results = {}
    recalls = []
    for i, label_name in enumerate(LABEL_LIST):
        support = len(true_labels[i])
        if support == 0:
            continue
        recall = sum(pred_labels[i]) / support
        results[f"recall_{label_name}"] = recall
        results[f"support_{label_name}"] = support
        recalls.append(recall)
    results["macro_recall"] = sum(recalls) / len(recalls) if recalls else 0.0
    return results


class EpochTableLogger(TrainerCallback):
    """Writes a clean, screenshot-ready table to a text file after
    every epoch, appending so all epochs stay visible in one file."""

    def __init__(self, log_path):
        self.log_path = log_path
        # start fresh each run
        with open(self.log_path, "w", encoding="utf-8") as f:
            f.write("LiLT Training - Per-Epoch Validation Results\n")
            f.write("=" * 60 + "\n\n")

    def on_evaluate(self, args, state, control, metrics=None, **kwargs):
        if metrics is None:
            return

        epoch = metrics.get("epoch", state.epoch)
        macro = metrics.get("eval_macro_recall", 0.0)

        rows = []
        for label in LABEL_LIST:
            recall_key = f"eval_recall_{label}"
            support_key = f"eval_support_{label}"
            if recall_key in metrics:
                rows.append((label, metrics[recall_key], metrics.get(support_key, 0)))

        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(f"Epoch {epoch}\n")
            f.write("-" * 60 + "\n")
            f.write(f"{'Label':<20}{'Recall':>10}{'Support':>12}\n")
            f.write("-" * 60 + "\n")
            for label, recall, support in sorted(rows, key=lambda x: -x[1]):
                f.write(f"{label:<20}{recall:>10.3f}{support:>12}\n")
            f.write("-" * 60 + "\n")
            f.write(f"{'MACRO RECALL':<20}{macro:>10.3f}\n")
            f.write("=" * 60 + "\n\n")

        print(f"\n[Epoch {epoch} results written to {self.log_path}]\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--epochs", type=int, default=5,
                        help="number of training epochs (default 5)")
    args = parser.parse_args()

    print(f"smoke test: {args.smoke}", flush=True)
    print(f"epochs requested: {args.epochs}", flush=True)
    print(f"CUDA available: {torch.cuda.is_available()}", flush=True)

    print("\nLoading data ...", flush=True)
    train_pages = load_split("lilt_train.json")
    val_pages = load_split("lilt_val.json")
    print(f"  train pages: {len(train_pages)}", flush=True)
    print(f"  val pages:   {len(val_pages)}", flush=True)

    train_ds = pages_to_dataset(train_pages, smoke=args.smoke)
    val_ds = pages_to_dataset(val_pages, smoke=args.smoke)

    print("\nLoading tokenizer and model ...", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForTokenClassification.from_pretrained(
        MODEL_NAME,
        num_labels=len(LABEL_LIST),
        id2label=ID_TO_LABEL,
        label2id=LABEL_TO_ID,
        low_cpu_mem_usage=True,
        device_map="cuda" if torch.cuda.is_available() else None,
    )
    print("model loaded", flush=True)

    print("Tokenizing ...", flush=True)
    train_tok = train_ds.map(
        lambda x: tokenize_and_align(x, tokenizer), batched=True,
        remove_columns=train_ds.column_names,
    )
    val_tok = val_ds.map(
        lambda x: tokenize_and_align(x, tokenizer), batched=True,
        remove_columns=val_ds.column_names,
    )

    data_collator = DataCollatorForTokenClassification(tokenizer, padding=False)

    epochs = 1 if args.smoke else args.epochs
    batch_size = 1
    grad_accum = 4

    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        gradient_accumulation_steps=grad_accum,
        eval_strategy="epoch",
        save_strategy="epoch",
        logging_steps=10,
        save_total_limit=3,   # keep a few more now that we're doing 5 epochs
        load_best_model_at_end=not args.smoke,
        metric_for_best_model="macro_recall" if not args.smoke else None,
        no_cuda=args.smoke,
        fp16=torch.cuda.is_available(),
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_tok,
        eval_dataset=val_tok,
        data_collator=data_collator,
        compute_metrics=compute_metrics,
        callbacks=[EpochTableLogger(RESULTS_LOG)],
    )

    print(f"\nStarting training - {epochs} epochs ...", flush=True)
    trainer.train()
    print("training finished", flush=True)

    if not args.smoke:
        trainer.save_model(OUTPUT_DIR)
        tokenizer.save_pretrained(OUTPUT_DIR)
        print(f"\nModel saved to {OUTPUT_DIR}", flush=True)

    print(f"\nFull per-epoch results are in: {RESULTS_LOG}", flush=True)


if __name__ == "__main__":
    main()