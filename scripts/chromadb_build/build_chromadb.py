from original_paths import project_path
"""
Build the central ChromaDB vector database for Unmochon.

Handles three file types per ministry:
  - _clauses.jsonl        -> clean policy clauses (indexed)
  - _clauses_review.jsonl -> low quality clauses (cleaned, then indexed if readable)
  - _tables.jsonl         -> table rows, grouped into whole tables (indexed if clean)

Ministry is worked out from the filename since it is not stored in the JSONL.
Rows flagged broken_text are skipped and left for the layout pass once the
LiLT model is trained.

Clauses with a real layout_label (currently Social Welfare only, from
9_inference.py) are filtered to CLAUSE/TABLE only - this drops memo
headers, metadata blocks, signatures etc from the searchable index.
Clauses with NO layout_label (Agriculture, Disaster Management - never
run through layout inference) fall back to a cheap heuristic filter
instead (heuristic_filter.py) - catches the most obvious noise (short
chunks, known boilerplate phrases) without needing a trained model.
"""
import json
import os
from collections import defaultdict
from datetime import datetime

import chromadb

from scripts.chromadb_build import config
from scripts.chromadb_build.clean_text import clean_ocr_text, is_worth_keeping
from scripts.chromadb_build.heuristic_filter import is_likely_noise

# Corruption detector from the OCR pipeline, used to filter the residual
# corrupted clauses that survived the re-OCR pass
import sys
sys.path.insert(0, project_path('scripts'))
from scripts.ocr_pipeline.quality import is_broken_bengali


def load_jsonl(path):
    """Read a JSONL file into a list of dicts."""
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def ministry_from_filename(filename):
    """Work out which ministry a file belongs to from its name."""
    name = filename.lower()
    if name.startswith("social_welfare"):
        return "Social Welfare"
    if name.startswith("disaster_management"):
        return "Disaster Management"
    if name.startswith("agriculture"):
        return "Agriculture"
    if name.startswith("cit") or name.startswith("ict"):
        return "CIT"
    return "Unknown"


def bbox_to_string(bbox):
    """ChromaDB metadata cannot hold lists, so store bbox as a string."""
    if isinstance(bbox, list):
        return ",".join(str(x) for x in bbox)
    return str(bbox) if bbox else ""


def make_metadata(clause, source_type):
    """Build a clean metadata dict that ChromaDB will accept.
    Only strings, ints, floats, bools - no lists, no None."""
    return {
        "clause_id":     str(clause.get("clause_id", "")),
        "doc_id":        str(clause.get("doc_id", "")),
        "ministry":      str(clause.get("ministry", "")),
        "section":       str(clause.get("section", "0")),
        "tag":           str(clause.get("tag", "")),
        "page_number":   int(clause.get("page_number", 0)),
        "language":      str(clause.get("language", "Unknown")),
        "ocr_method":    str(clause.get("ocr_method", "")),
        "quality_score": float(clause.get("quality_score", 0.0)),
        "bbox":          bbox_to_string(clause.get("bbox", "")),
        "source_url":    str(clause.get("source_url", "")),
        "layout_label":  str(clause.get("layout_label", "")),
        "is_table":      source_type == "table",
        "from_review":   source_type == "review",
    }


def group_table_rows(rows, ministry):
    """Turn individual table rows into whole-table documents.

    Table rows are stored one per line in the JSONL. Indexing each row on
    its own gives thousands of meaningless fragments like '3 | Dhaka | 500'.
    Grouping by (doc_id, page, table_index) keeps the header attached to the
    data, which is what the NLI model needs to read a benefit amount in context.

    Rows flagged broken_text are skipped - those pages need re-extraction
    once the layout model can locate the table region on the rendered image.
    """
    tables = defaultdict(list)
    skipped_broken = 0

    for r in rows:
        if r.get("broken_text"):
            skipped_broken += 1
            continue
        key = (r.get("doc_id", ""), r.get("page_number", 0), r.get("table_index", 0))
        tables[key].append(r)

    items = []
    for (doc_id, page, t_idx), group in tables.items():
        group.sort(key=lambda r: r.get("row_index", 0))
        text = "\n".join(r.get("raw_text", "") for r in group if r.get("raw_text"))

        if len(text.strip()) < config.MIN_TEXT_LENGTH:
            continue

        scores = [r.get("quality_score", 0) for r in group]
        avg_q = sum(scores) / len(scores) if scores else 0.0

        table_id = f"{doc_id}_P{page}_T{t_idx}"
        meta_source = {
            "clause_id":     table_id,
            "doc_id":        doc_id,
            "ministry":      ministry,
            "section":       "0",
            "tag":           group[0].get("tag", ""),
            "page_number":   page,
            "language":      group[0].get("language", "Unknown"),
            "ocr_method":    "table_extract",
            "quality_score": avg_q,
            "bbox":          "",
            "source_url":    "",
            "layout_label":  "TABLE",
        }
        items.append((table_id, text, make_metadata(meta_source, "table")))

    return items, skipped_broken


def collect_clauses():
    """Go through every JSONL file and decide what to index.
    Returns (items_to_index, review_log)."""
    items = []
    review_log = []
    seen_ids = set()
    skipped_corrupt = 0
    skipped_layout = 0

    for filename in sorted(os.listdir(config.PROCESSED_DIR)):
        path = os.path.join(config.PROCESSED_DIR, filename)
        ministry = ministry_from_filename(filename)

        # ---- MAIN CLAUSES ----
        if filename.endswith("_clauses.jsonl"):
            clauses = load_jsonl(path)
            kept = 0
            corrupt = 0
            layout_dropped = 0
            for c in clauses:
                text = c.get("text", "").strip()
                if len(text) < config.MIN_TEXT_LENGTH:
                    continue
                if "[FAILED" in text or "[PAGE FAILED" in text:
                    continue
                if c.get("quality_score", 0) < config.CLAUSE_MIN_QUALITY:
                    continue

                # Residual corruption that survived the re-OCR pass
                if is_broken_bengali(text):
                    corrupt += 1
                    continue

                # If this clause has a real layout label (from the LiLT
                # model), use it - only index CLAUSE and TABLE.
                # Otherwise (AG/DM, never run through layout inference)
                # fall back to the cheap heuristic filter.
                layout_label = c.get("layout_label", "")
                if layout_label:
                    if layout_label not in ("CLAUSE", "TABLE"):
                        layout_dropped += 1
                        continue
                else:
                    if is_likely_noise(text):
                        layout_dropped += 1
                        continue

                cid = str(c.get("clause_id", ""))
                if cid in seen_ids:
                    continue
                seen_ids.add(cid)

                c["ministry"] = ministry
                items.append((cid, text, make_metadata(c, "clause")))
                kept += 1

            skipped_corrupt += corrupt
            skipped_layout += layout_dropped
            print(f"  {filename}: {kept} clauses indexed "
                  f"({corrupt} corrupt skipped, {layout_dropped} noise skipped)")

        # ---- REVIEW CLAUSES ----
        elif filename.endswith("_clauses_review.jsonl"):
            clauses = load_jsonl(path)
            kept = 0
            dropped = 0
            for c in clauses:
                raw_text = c.get("text", "")
                cleaned = clean_ocr_text(raw_text)
                score = c.get("quality_score", 0)

                keep = (
                    score >= config.REVIEW_MIN_QUALITY
                    and is_worth_keeping(cleaned, config.MIN_TEXT_LENGTH)
                    and not is_broken_bengali(cleaned)
                )

                review_log.append({
                    "file": filename,
                    "clause_id": c.get("clause_id", ""),
                    "quality_score": round(float(score), 3),
                    "decision": "KEPT" if keep else "DROPPED",
                    "cleaned_preview": cleaned[:120],
                })

                if keep:
                    cid = str(c.get("clause_id", ""))
                    if cid in seen_ids:
                        continue
                    seen_ids.add(cid)
                    c["text"] = cleaned
                    c["ministry"] = ministry
                    items.append((cid, cleaned, make_metadata(c, "review")))
                    kept += 1
                else:
                    dropped += 1
            print(f"  {filename}: {kept} kept, {dropped} dropped (see log)")

        # ---- TABLES ----
        elif filename.endswith("_tables.jsonl"):
            rows = load_jsonl(path)
            table_items, skipped = group_table_rows(rows, ministry)
            for tid, text, meta in table_items:
                if tid in seen_ids:
                    continue
                seen_ids.add(tid)
                items.append((tid, text, meta))
            print(f"  {filename}: {len(table_items)} tables indexed "
                  f"({skipped} broken rows left for layout pass)")

    print(f"\nTotal corrupt clauses skipped: {skipped_corrupt}")
    print(f"Total noise clauses skipped (layout model or heuristic): {skipped_layout}")
    return items, review_log


def write_review_log(review_log):
    """Save the kept/dropped decisions so the supervisor can inspect them."""
    log_path = os.path.join(config.PROCESSED_DIR, "review_cleaning_log.txt")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"Review Cleaning Log - {datetime.now()}\n")
        f.write("=" * 70 + "\n\n")

        kept = [r for r in review_log if r["decision"] == "KEPT"]
        dropped = [r for r in review_log if r["decision"] == "DROPPED"]

        f.write(f"Total review clauses examined: {len(review_log)}\n")
        f.write(f"Kept:    {len(kept)}\n")
        f.write(f"Dropped: {len(dropped)}\n\n")

        f.write("-" * 70 + "\nKEPT CLAUSES\n" + "-" * 70 + "\n")
        for r in kept:
            f.write(f"[{r['quality_score']}] {r['clause_id']} ({r['file']})\n")
            f.write(f"    {r['cleaned_preview']}\n\n")

        f.write("-" * 70 + "\nDROPPED CLAUSES\n" + "-" * 70 + "\n")
        for r in dropped:
            f.write(f"[{r['quality_score']}] {r['clause_id']} ({r['file']})\n")
            f.write(f"    {r['cleaned_preview']}\n\n")

    print(f"\nReview log written to: {log_path}")


def build(fresh=False):
    print("Building Unmochon ChromaDB\n")

    print("Reading JSONL files ...")
    items, review_log = collect_clauses()

    if not items:
        print("Nothing to index. Check your JSONL files.")
        return

    print(f"\nTotal items to index: {len(items)}")
    write_review_log(review_log)

    print("\nLoading embedding model ...")
    device = "cpu"
    try:
        import torch
        if torch.cuda.is_available():
            device = "cuda"
    except ImportError:
        pass
    print(f"  encoding on: {device}")
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(config.EMBED_MODEL, device=device)

    print("Setting up ChromaDB ...")
    client = chromadb.PersistentClient(path=config.CHROMADB_DIR)

    if fresh:
        try:
            client.delete_collection(config.COLLECTION_NAME)
            print("  removed old collection")
        except Exception:
            pass
        collection = client.create_collection(
            name=config.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    else:
        collection = client.get_or_create_collection(
            name=config.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        existing_ids = set()
        already = collection.count()
        if already:
            print(f"  found {already} items already indexed, checking which ...")
            offset = 0
            page = 5000
            while offset < already:
                got = collection.get(limit=page, offset=offset, include=[])
                existing_ids.update(got["ids"])
                offset += page
        items = [x for x in items if x[0] not in existing_ids]
        print(f"  {len(existing_ids)} already done, {len(items)} left to add")
        if not items:
            print(f"\nNothing left to add. Total stored: {collection.count()}")
            return

    print("Encoding and adding to ChromaDB ...")
    batch_size = 128
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        ids       = [x[0] for x in batch]
        texts     = [x[1] for x in batch]
        metadatas = [x[2] for x in batch]

        try:
            embeddings = model.encode(texts, show_progress_bar=False).tolist()
            collection.add(
                ids=ids,
                documents=texts,
                embeddings=embeddings,
                metadatas=metadatas,
            )
        except Exception as e:
            print(f"  batch at {i} failed: {e}")
            continue

        print(f"  added {min(i + batch_size, len(items))} / {len(items)}")

    print(f"\nDone. Total items stored: {collection.count()}")
    print(f"ChromaDB saved to: {config.CHROMADB_DIR}")


if __name__ == "__main__":
    import sys
    build(fresh="--fresh" in sys.argv)