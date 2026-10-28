"""Add circular_date to ChromaDB metadata without re-encoding.

The embeddings have not changed - only the metadata gained two fields.
ChromaDB can update metadata in place, which takes seconds instead of
the hours a full rebuild would need on CPU.

Run this after extract_dates.py, before anything that filters or sorts
by date.
"""

import json
import os

import chromadb

from DATE_eXTRACTION import config


def load_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def build_date_lookup():
    """Map every clause_id to its date.

    Also maps doc_id to date, so table entries can be dated too - tables
    are indexed under a generated id like DOC_P3_T1 that will not appear
    in the clause files.
    """
    by_clause = {}
    by_doc = {}

    for filename in config.TARGET_FILES:
        path = os.path.join(config.PROCESSED_DIR, filename)
        if not os.path.exists(path):
            continue

        for c in load_jsonl(path):
            date = c.get("circular_date", "")
            source = c.get("date_source", "none")
            cid = c.get("clause_id", "")
            did = c.get("doc_id", "")

            if cid:
                by_clause[cid] = (date, source)
            if did and date and did not in by_doc:
                by_doc[did] = (date, source)

    return by_clause, by_doc


def main():
    print("Updating ChromaDB metadata with dates\n")

    by_clause, by_doc = build_date_lookup()
    print(f"dates loaded: {len(by_clause)} clauses, {len(by_doc)} documents")

    client = chromadb.PersistentClient(path=config.CHROMADB_DIR)
    collection = client.get_collection(config.COLLECTION_NAME)

    total = collection.count()
    print(f"collection holds {total} items\n")

    matched = 0
    via_doc = 0
    unmatched = 0
    offset = 0
    page = 1000

    while offset < total:
        got = collection.get(limit=page, offset=offset,
                             include=["metadatas"])
        if not got["ids"]:
            break

        ids = []
        metas = []

        for cid, meta in zip(got["ids"], got["metadatas"]):
            date, source = by_clause.get(cid, ("", ""))

            # Table entries have generated ids, so fall back to the
            # document they came from
            if not date:
                date, source = by_doc.get(meta.get("doc_id", ""), ("", "none"))
                if date:
                    via_doc += 1
            else:
                matched += 1

            if not date:
                unmatched += 1

            meta = dict(meta)
            meta["circular_date"] = date
            meta["date_source"] = source
            # Year on its own is easier to filter on than a full date
            meta["year"] = int(date[:4]) if date else 0

            ids.append(cid)
            metas.append(meta)

        collection.update(ids=ids, metadatas=metas)

        offset += page
        print(f"  updated {min(offset, total)} / {total}")

    print(f"\nmatched by clause_id: {matched}")
    print(f"matched by doc_id:    {via_doc}")
    print(f"no date found:        {unmatched}")


if __name__ == "__main__":
    main()