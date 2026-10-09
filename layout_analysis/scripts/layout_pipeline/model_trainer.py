import torch
from torch.utils.data import Dataset
from transformers import (
    AutoTokenizer,
    LiltForTokenClassification,
    TrainingArguments,
    Trainer,
    EarlyStoppingCallback,
)
from .converter import LABELS, LABEL2ID, ID2LABEL

MODEL_NAME = "nielsr/lilt-xlm-roberta-base"


class LiltDataset(Dataset):
    """
    LiLT (XLM-R) reuses XLM-R's text tokenizer, which does NOT accept boxes.
    We tokenize words with is_split_into_words=True, then manually expand each
    word's normalized box + label to all its subword tokens. First subword gets
    the real label; continuation subwords get -100 so loss ignores them.
    Special tokens (CLS/SEP/PAD) get box [0,0,0,0] and label -100.
    """
    def __init__(self, examples, tokenizer, max_len=512):
        self.examples = examples
        self.tok = tokenizer
        self.max_len = max_len

    def __len__(self):
        return len(self.examples)

    def __getitem__(self, idx):
        ex = self.examples[idx]
        words  = ex["words"]
        boxes  = ex["boxes"]
        labels = ex["labels"]

        enc = self.tok(
            words,
            is_split_into_words=True,
            truncation=True,
            padding="max_length",
            max_length=self.max_len,
            return_tensors="pt",
        )
        word_ids = enc.word_ids(0)

        bbox_seq  = []
        label_seq = []
        prev_wid  = None
        for wid in word_ids:
            if wid is None:
                bbox_seq.append([0, 0, 0, 0])
                label_seq.append(-100)
            else:
                bbox_seq.append(boxes[wid])
                if wid != prev_wid:
                    label_seq.append(labels[wid])   # first subword: real label
                else:
                    label_seq.append(-100)           # continuation: ignore
            prev_wid = wid

        item = {k: v.squeeze(0) for k, v in enc.items()}
        item["bbox"]   = torch.tensor(bbox_seq, dtype=torch.long)
        item["labels"] = torch.tensor(label_seq, dtype=torch.long)
        return item



def freeze_lower_layers(model, keep_top=6):
    """
    Freeze embeddings + all but the top `keep_top` encoder layers of BOTH
    the text stream and the layout stream. Prevents overfitting on small data.
    """
    for p in model.lilt.embeddings.parameters():
        p.requires_grad = False
    if hasattr(model.lilt, "layout_embeddings"):
        for p in model.lilt.layout_embeddings.parameters():
            p.requires_grad = False

    layers = model.lilt.encoder.layer
    n = len(layers)
    freeze_until = max(0, n - keep_top)
    for i in range(freeze_until):
        for p in layers[i].parameters():
            p.requires_grad = False

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"Trainable params: {trainable:,} / {total:,} "
          f"({100*trainable/total:.1f}%)  [froze {freeze_until}/{n} layers]")


def stratified_split(examples, eval_frac=0.15, seed=42):
    """
    Split so each page goes to train/eval, roughly preserving the mix of
    dominant label per page. Page-level split (not region) to avoid leakage.
    """
    import random
    rng = random.Random(seed)

    # bucket pages by their most common label
    from collections import Counter, defaultdict
    buckets = defaultdict(list)
    for ex in examples:
        dominant = Counter(ex["labels"]).most_common(1)[0][0]
        buckets[dominant].append(ex)

    train, ev = [], []
    for label_id, group in buckets.items():
        rng.shuffle(group)
        k = max(1, int(len(group) * eval_frac))
        ev.extend(group[:k])
        train.extend(group[k:])

    rng.shuffle(train)
    rng.shuffle(ev)
    return train, ev


def compute_metrics(pred):
    import numpy as np
    from sklearn.metrics import precision_recall_fscore_support, f1_score
    logits, labels = pred
    preds = np.argmax(logits, axis=-1)

    true, prd = [], []
    for p_row, l_row in zip(preds, labels):
        for p_i, l_i in zip(p_row, l_row):
            if l_i == -100:
                continue
            true.append(int(l_i))
            prd.append(int(p_i))

    clause_id = LABEL2ID["CLAUSE"]
    # per-class precision/recall/f1, indexed by class id
    p, r, f, _ = precision_recall_fscore_support(
        true, prd, labels=list(range(len(LABELS))),
        average=None, zero_division=0
    )
    macro_f1 = f1_score(true, prd, average="macro", zero_division=0)

    return {
        "clause_recall": float(r[clause_id]),
        "clause_f1":     float(f[clause_id]),
        "macro_f1":      float(macro_f1),
    }

def train(examples, output_dir, epochs=8, batch_size=4, keep_top=6):
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = LiltForTokenClassification.from_pretrained(
        MODEL_NAME,
        num_labels=len(LABELS),
        id2label=ID2LABEL,
        label2id=LABEL2ID,
    )
    freeze_lower_layers(model, keep_top=keep_top)

    train_ex, eval_ex = stratified_split(examples, eval_frac=0.15)
    print(f"Train pages: {len(train_ex)} | Eval pages: {len(eval_ex)}")

    train_ds = LiltDataset(train_ex, tokenizer)
    eval_ds  = LiltDataset(eval_ex, tokenizer)

    args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        learning_rate=3e-5,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="clause_f1",
        greater_is_better=True,
        save_total_limit=1,
        logging_steps=10,
        report_to=[],
        remove_unused_columns=False,
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=2)],
    )

    trainer.train()
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)
    print(f"Saved to {output_dir}")
    return model, tokenizer