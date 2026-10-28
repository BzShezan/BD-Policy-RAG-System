"""Update an isolated database copy using ORIGINAL filters and ORIGINAL BM25 builder."""
import json
import os
import sys
from pathlib import Path

def prepare(dataset, metadata_path=None, model=None):
    from scripts.chromadb_build import build_chromadb as builder
    from scripts.retrieval import build_bm25
    from original_paths import CHROMADB_DIR, COLLECTION_NAME, EMBED_MODEL, METADATA_PATH
    import chromadb
    previous = builder.config.PROCESSED_DIR
    try:
        builder.config.PROCESSED_DIR = str(dataset)
        items, review = builder.collect_clauses()
    finally:
        builder.config.PROCESSED_DIR = previous
    if not items:
        raise ValueError('Original quality/layout filters accepted no chunks; database was not changed.')
    source_rows = {}
    for path in Path(dataset).glob('*.jsonl'):
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            if line.strip():
                row = json.loads(line)
                if row.get('clause_id'): source_rows[str(row['clause_id'])] = row
    # Whole-table ids differ from row ids. Preserve their complete source rows too.
    from collections import defaultdict
    tables = defaultdict(list)
    for path in Path(dataset).glob('*_tables.jsonl'):
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            if line.strip():
                row = json.loads(line)
                cid = f"{row['doc_id']}_P{row['page_number']}_T{row.get('table_index', 0)}"
                tables[cid].append(row)
    client = chromadb.PersistentClient(path=CHROMADB_DIR)
    collection = client.get_collection(COLLECTION_NAME)
    old_ids = set(collection.get(include=[])['ids'])
    changed = []
    unchanged = 0
    for cid, text, filtered_meta in items:
        got = collection.get(ids=[cid], include=['documents', 'metadatas'])
        old_meta = got['metadatas'][0] if got['ids'] else {}
        # Retain previous dates/fields absent from this incoming row, along with all new fields.
        meta = dict(old_meta)
        meta.update(filtered_meta)
        raw = source_rows.get(cid, {})
        for key, value in raw.items():
            if key in {'text', 'clause_id', 'bbox', 'ministry'} or value is None or str(key).startswith('chroma:'): continue
            meta[key] = value if isinstance(value, (str, bool, int, float)) else json.dumps(value, ensure_ascii=False)
        if cid in tables:
            meta['original_table_rows_json'] = json.dumps(tables[cid], ensure_ascii=False, sort_keys=True)
            for key in ('source_url', 'circular_date', 'date_source', 'year'):
                values = [row[key] for row in tables[cid] if row.get(key) is not None]
                if values and all(value == values[0] for value in values): meta[key] = values[0]
        if raw: meta['original_chunk_json'] = json.dumps(raw, ensure_ascii=False, sort_keys=True)
        if got['ids'] and got['documents'][0] == text and old_meta == meta:
            unchanged += 1
        else:
            changed.append((cid, text, meta))
    if changed and model is None:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(EMBED_MODEL)
    # Explicit vectors avoid Chroma's default embedding function; SAME model as retrieval.
    for start in range(0, len(changed), 128):
        batch = changed[start:start+128]
        embeddings = model.encode([x[1] for x in batch], show_progress_bar=False).tolist()
        collection.upsert(ids=[x[0] for x in batch], documents=[x[1] for x in batch],
                          metadatas=[x[2] for x in batch], embeddings=embeddings)
    if metadata_path:
        existing = json.loads(METADATA_PATH.read_text(encoding='utf-8')) if METADATA_PATH.exists() else {}
        incoming = json.loads(Path(metadata_path).read_text(encoding='utf-8-sig'))
        for doc_id, entry in incoming.items():
            existing[doc_id] = {**existing.get(doc_id, {}), **entry}
        METADATA_PATH.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding='utf-8')
    # Reuse the original builder: sparse and dense indexes must have exactly the same ids.
    build_bm25.build()
    import pickle
    from original_paths import BM25_INDEX_PATH
    with open(BM25_INDEX_PATH, 'rb') as stream: sparse = pickle.load(stream)
    if set(sparse['ids']) != set(collection.get(include=[])['ids']):
        raise RuntimeError('ChromaDB/BM25 ID mismatch; staged update rejected.')
    report = {'before': len(old_ids), 'after': collection.count(), 'accepted': len(items),
              'added': sum(cid not in old_ids for cid, _, _ in changed),
              'updated': sum(cid in old_ids for cid, _, _ in changed), 'unchanged': unchanged,
              'bm25_ids_match': True}
    return report

if __name__ == '__main__':
    report = prepare(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    Path(os.environ['UPDATE_REPORT_PATH']).write_text(json.dumps(report, indent=2), encoding='utf-8')
