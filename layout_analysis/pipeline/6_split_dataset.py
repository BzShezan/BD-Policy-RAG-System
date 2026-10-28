from original_paths import project_path
"""Split labeled pages into train/validation sets.

Split by document, not by page - pages from the same document share
fonts, headers and table styles. A random page-level split would let
the model see 90% of a document while training and be "tested" on the
other 10%, which inflates the score without proving generalization.

Rare labels get a stratification check - if a label only appears in
one or two documents, we make sure at least one of those documents
ends up in each split, or that label becomes unmeasurable.
"""

import json
import os
import random
from collections import defaultdict

LABELED_DIR = project_path('layout_analysis/workspace/labeled_pages')
OUTPUT_DIR = project_path('layout_analysis/data')
VAL_FRACTION = 0.2
SEED = 42  # fixed, so the split is reproducible

random.seed(SEED)


def load_all_pages():
    pages = []
    for fname in os.listdir(LABELED_DIR):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(LABELED_DIR, fname)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        pages.append((fname, data))
    return pages


def group_by_document(pages):
    by_doc = defaultdict(list)
    for fname, data in pages:
        by_doc[data["doc_id"]].append((fname, data))
    return by_doc


def labels_in_document(doc_pages):
    """Which labels appear anywhere in this document's pages."""
    labels = set()
    for _, data in doc_pages:
        for w in data["words"]:
            labels.add(w["label"])
    return labels


def main():
    print("Loading labeled pages ...")
    pages = load_all_pages()
    print(f"  {len(pages)} pages total")

    by_doc = group_by_document(pages)
    print(f"  {len(by_doc)} documents")

    # Work out which documents contain each label, so we can protect
    # rare ones during the split
    label_to_docs = defaultdict(set)
    for doc_id, doc_pages in by_doc.items():
        for label in labels_in_document(doc_pages):
            label_to_docs[label].add(doc_id)

    print("\nDocuments per label:")
    for label, docs in sorted(label_to_docs.items(), key=lambda x: len(x[1])):
        print(f"  {label:20s} {len(docs)} documents")

    doc_ids = list(by_doc.keys())
    random.shuffle(doc_ids)

    n_val_docs = max(1, int(len(doc_ids) * VAL_FRACTION))
    val_docs = set(doc_ids[:n_val_docs])
    train_docs = set(doc_ids[n_val_docs:])

    # Check every label has at least one document on each side.
    # If a label exists in only one document total, it cannot be
    # split - flag it rather than silently leaving one side empty.
    print("\nStratification check:")
    problem_labels = []
    for label, docs in label_to_docs.items():
        in_train = docs & train_docs
        in_val = docs & val_docs
        if not in_train or not in_val:
            problem_labels.append(label)
            print(f"  WARNING: {label} - train:{len(in_train)} val:{len(in_val)}")

    if problem_labels:
        print(f"\n  {len(problem_labels)} label(s) not present in both splits.")
        print("  Moving one document per problem label into the smaller side ...")
        for label in problem_labels:
            docs = label_to_docs[label]
            in_train = docs & train_docs
            in_val = docs & val_docs
            if not in_val and in_train:
                # move one training doc containing this label into val
                move_doc = next(iter(in_train))
                train_docs.discard(move_doc)
                val_docs.add(move_doc)
            elif not in_train and in_val:
                move_doc = next(iter(in_val))
                val_docs.discard(move_doc)
                train_docs.add(move_doc)

    # Rebuild page lists from the final document sets
    train_pages = [dp for d in train_docs for dp in by_doc[d]]
    val_pages = [dp for d in val_docs for dp in by_doc[d]]

    print(f"\nFinal split:")
    print(f"  train: {len(train_docs)} documents, {len(train_pages)} pages")
    print(f"  val:   {len(val_docs)} documents, {len(val_pages)} pages")

    # Save as two files - list of {doc_id, page_number, words}
    def save(pages, name):
        out = [data for _, data in pages]
        path = os.path.join(OUTPUT_DIR, name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False)
        print(f"  wrote {path}")

    save(train_pages, "lilt_train.json")
    save(val_pages, "lilt_val.json")

    # Final per-label counts on each side, for the record
    def label_counts(pages):
        c = defaultdict(int)
        for _, data in pages:
            for w in data["words"]:
                c[w["label"]] += 1
        return c

    print("\nWord counts by label:")
    train_counts = label_counts(train_pages)
    val_counts = label_counts(val_pages)
    all_labels = sorted(set(train_counts) | set(val_counts))
    for label in all_labels:
        t = train_counts.get(label, 0)
        v = val_counts.get(label, 0)
        flag = "  <-- check this" if v == 0 or t == 0 else ""
        print(f"  {label:20s} train:{t:6d}  val:{v:6d}{flag}")


if __name__ == "__main__":
    main()