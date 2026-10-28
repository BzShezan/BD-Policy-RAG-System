from original_paths import project_path
"""Compare saved checkpoints on the validation set to see if more
epochs would have helped, or if performance already plateaued.

Tokenizer only loaded once from the final model folder - checkpoint
subfolders only contain model weights, not the tokenizer files.
"""

import json
import os
import numpy as np
import torch
from transformers import (
    AutoTokenizer,
    AutoModelForTokenClassification,
    Trainer,
    TrainingArguments,
    DataCollatorForTokenClassification,
)
from datasets import Dataset

DATA_DIR = project_path('layout_analysis/data')
MODEL_DIR = os.getenv("LAYOUT_MODEL_DIR", project_path('layout_analysis/models/lilt_sw_v1'))

LABEL_LIST = [
    "O", "CLAUSE", "text", "SECTION_TITLE", "Sub_Section", "METADATA",
    "TABLE", "FOOTER", "HEADER", "Page_header", "Signature", "Caption",
    "Fig_with_value", "Fig_without_value",
]
LABEL_TO_ID = {l: i for i, l in enumerate(LABEL_LIST)}
ID_TO_LABEL = {i: l for l, i in LABEL_TO_ID.items()}


def load_split(name):
    with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
        return json.load(f)


def normalize_bbox(bbox, w, h):
    x1, y1, x2, y2 = bbox
    return [int(1000*x1/w), int(1000*y1/h), int(1000*x2/w), int(1000*y2/h)]


def pages_to_dataset(pages):
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
                label_ids.append(-100)
                bbox_ids.append([0, 0, 0, 0])
            elif word_id != prev_word:
                label_ids.append(label[word_id])
                bbox_ids.append(bbox[word_id])
            else:
                label_ids.append(-100)
                bbox_ids.append(bbox[word_id])
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
        results[f"recall_{label_name}"] = round(recall, 3)
        recalls.append(recall)
    results["macro_recall"] = round(sum(recalls) / len(recalls), 4) if recalls else 0.0
    return results


val_pages = load_split("lilt_val.json")
val_ds = pages_to_dataset(val_pages)

checkpoints = [
    ("checkpoint-438", os.path.join(MODEL_DIR, "checkpoint-438")),
    ("checkpoint-657", os.path.join(MODEL_DIR, "checkpoint-657")),
    ("final (root)", MODEL_DIR),
]

tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)

for name, path in checkpoints:
    print(f"\n{'='*50}\nEvaluating: {name}\n{'='*50}")
    model = AutoModelForTokenClassification.from_pretrained(path)

    val_tok = val_ds.map(
        lambda x: tokenize_and_align(x, tokenizer), batched=True,
        remove_columns=val_ds.column_names,
    )

    args = TrainingArguments(
        output_dir="./tmp_eval",
        per_device_eval_batch_size=1,
        fp16=torch.cuda.is_available(),
    )
    trainer = Trainer(
        model=model, args=args, eval_dataset=val_tok,
        data_collator=DataCollatorForTokenClassification(tokenizer, padding=False),
        compute_metrics=compute_metrics,
    )

    metrics = trainer.evaluate()
    for k, v in sorted(metrics.items()):
        if 'recall' in k or 'macro' in k:
            print(f"  {k}: {v}")