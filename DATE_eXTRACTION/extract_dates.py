"""Give every clause the date its document was issued.

Dates only appear in the page 1 letterhead, so this finds one date per
document and hands it to all of that document's clauses.

Three sources, tried in order:
  1. doc_id prefix       2025.07.17-495-...   exact, from the filename
  2. header text         ১৭ জুলাই ২০২৫        parsed from page 1 OCR
  3. naming convention   SW_OAA_2014_02_...   year and month only

Adds two fields to every clause:
  circular_date   'YYYY-MM-DD' or ''
  date_source     which source it came from, so the result can be audited

Overwrites the JSONL files in place. Back them up first.
"""

import json
import os
from collections import defaultdict

from DATE_eXTRACTION import config
from bn_dates import (
    find_gregorian,
    find_bangla_calendar,
    from_doc_id,
    from_filename_convention,
)


def load_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def save_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def header_text_for_docs(clauses):
    """Join the page 1 and 2 text of each document into one string.

    OCR splits the date across lines, and the memo number often lands
    between the two halves, so searching the whole header at once works
    better than checking clauses individually.
    """
    headers = defaultdict(list)
    for c in clauses:
        if c.get("page_number", 99) <= config.HEADER_PAGES:
            headers[c.get("doc_id", "")].append(c.get("text", ""))
    return {doc: "\n".join(parts) for doc, parts in headers.items()}


def date_for_document(doc_id, header):
    """Work out one issue date for a document.
    Returns (date_string, source_name)."""

    # The doc_id prefix never went through OCR, so it wins when present
    d = from_doc_id(doc_id)
    if d:
        return d, "doc_id"

    d = find_gregorian(header)
    if d:
        return d, "header"

    d = from_filename_convention(doc_id)
    if d:
        return d, "filename"

    d = find_bangla_calendar(header)
    if d:
        return d, "bangla_calendar"

    return "", "none"


def process_file(filename):
    path = os.path.join(config.PROCESSED_DIR, filename)
    if not os.path.exists(path):
        print(f"  {filename}: not found, skipping")
        return

    clauses = load_jsonl(path)
    if not clauses:
        print(f"  {filename}: empty, skipping")
        return

    headers = header_text_for_docs(clauses)

    # Resolve the date once per document, not once per clause
    doc_dates = {}
    for doc_id in {c.get("doc_id", "") for c in clauses}:
        doc_dates[doc_id] = date_for_document(doc_id, headers.get(doc_id, ""))

    for c in clauses:
        date, source = doc_dates.get(c.get("doc_id", ""), ("", "none"))
        c["circular_date"] = date
        c["date_source"] = source

    save_jsonl(path, clauses)

    found = sum(1 for d, _ in doc_dates.values() if d)
    by_source = defaultdict(int)
    for _, s in doc_dates.values():
        by_source[s] += 1

    print(f"  {filename}")
    print(f"    documents: {len(doc_dates)}, dated: {found} "
          f"({found / len(doc_dates) * 100:.1f}%)")
    for s, n in sorted(by_source.items(), key=lambda x: -x[1]):
        print(f"      {s}: {n}")


def main():
    print("Extracting circular dates\n")
    for filename in config.TARGET_FILES:
        process_file(filename)
    print("\nDone. Run check_dates.py to inspect the results.")


if __name__ == "__main__":
    main()