# checkpoint.py — save/load checkpoint, write output files, log skipped docs

import json
import os


def load_checkpoint(path):
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return set(f.read().splitlines())
    return set()


def mark_done(path, doc_id):
    with open(path, 'a', encoding='utf-8') as f:
        f.write(doc_id + '\n')


def log_skipped(path, filename, reason):
    write_header = not os.path.exists(path)
    with open(path, 'a', encoding='utf-8') as f:
        if write_header:
            f.write("filename\treason\n")
        f.write(f"{filename}\t{reason}\n")


def append_jsonl(path, records):
    if not records:
        return
    with open(path, 'a', encoding='utf-8') as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')


def save_results(clean_file, review_file, tables_file, chunks, table_rows):
    clean  = [c for c in chunks if not c.get("needs_review")]
    review = [c for c in chunks if c.get("needs_review")]

    append_jsonl(clean_file, clean)
    append_jsonl(review_file, review)
    append_jsonl(tables_file, table_rows)

    return len(clean), len(review), len(table_rows)