from original_paths import project_path
"""Merge source_url from the metadata spreadsheet into the JSONL files.

Matches by PREFIX, not exact doc_id, because clause doc_ids are
sometimes truncated versions of the real document titles - the same
issue that broke word-box matching earlier this week.

Only fills source_url when the metadata value actually looks like a
URL (starts with http) - some rows have memo numbers instead of real
links, which should not be written into source_url.
"""

import json
import os
import openpyxl

METADATA_XLSX = project_path('data/Policies Metadata.xlsx')

TARGET_FILES = [
    project_path('data/processed_jsonl/Social_Welfare_clauses.jsonl'),
    # r"G:\BD-Policy-RAG-System\data\processed_jsonl\Agriculture_clauses.jsonl",
    # r"G:\BD-Policy-RAG-System\data\processed_jsonl\Disaster_Management_clauses.jsonl",
]


def load_metadata():
    """Read the spreadsheet into a list of (doc_id, url) pairs,
    keeping only rows where the value is really a URL."""
    wb = openpyxl.load_workbook(METADATA_XLSX, data_only=True)
    ws = wb["Metadata"]
    rows = list(ws.iter_rows(values_only=True))

    pairs = []
    for r in rows[1:]:
        doc_id = r[0]
        url = r[5]
        if not doc_id or not url:
            continue
        url = str(url).strip()
        if not url.startswith("http"):
            continue
        # strip .pdf if present - clause doc_ids never carry the extension
        doc_id_clean = str(doc_id).strip()
        if doc_id_clean.lower().endswith(".pdf"):
            doc_id_clean = doc_id_clean[:-4]
        pairs.append((doc_id_clean, url))

    return pairs


def find_url(clause_doc_id, metadata_pairs, cache):
    """Match a clause's doc_id against the metadata list by prefix,
    in either direction, since either one could be the truncated one."""
    if clause_doc_id in cache:
        return cache[clause_doc_id]

    clean = clause_doc_id.strip()
    url = ""

    for meta_doc_id, meta_url in metadata_pairs:
        if clean.startswith(meta_doc_id[:30]) or meta_doc_id.startswith(clean[:30]):
            url = meta_url
            break

    cache[clause_doc_id] = url
    return url


def process_file(path, metadata_pairs):
    if not os.path.exists(path):
        print(f"  not found, skipping: {path}")
        return

    with open(path, encoding="utf-8") as f:
        clauses = [json.loads(l) for l in f if l.strip()]

    cache = {}
    filled = 0
    for c in clauses:
        url = find_url(c.get("doc_id", ""), metadata_pairs, cache)
        if url:
            c["source_url"] = url
            filled += 1

    with open(path, "w", encoding="utf-8") as f:
        for c in clauses:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print(f"  {os.path.basename(path)}: {filled} / {len(clauses)} clauses got a source_url")


def main():
    print("Loading metadata spreadsheet ...")
    metadata_pairs = load_metadata()
    print(f"  {len(metadata_pairs)} documents with a real URL\n")

    print("Merging into JSONL files ...")
    for path in TARGET_FILES:
        process_file(path, metadata_pairs)

    print("\nDone.")


if __name__ == "__main__":
    main()