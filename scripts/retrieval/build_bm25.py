"""Build the BM25 sparse index.

Reads the documents straight out of ChromaDB rather than re-reading the
JSONL. That guarantees both retrievers see exactly the same corpus - if
they were built from separate sources they could drift apart and the
fusion step would be comparing different documents.

Saves to a pickle so the API does not spend time tokenising 16k
documents on every startup.
"""

import pickle
import time

import chromadb
from rank_bm25 import BM25Okapi

from scripts.retrieval import config
from scripts.retrieval.tokenize_bn import tokenize


def load_documents():
    """Pull every document and its id out of ChromaDB, in pages.

    Reading all 16k at once has crashed before on this machine, so this
    walks through in chunks.
    """
    client = chromadb.PersistentClient(path=config.CHROMADB_DIR)
    collection = client.get_collection(config.COLLECTION_NAME)

    total = collection.count()
    print(f"collection holds {total} items")

    ids, docs = [], []
    offset, page = 0, 2000

    while offset < total:
        got = collection.get(limit=page, offset=offset,
                             include=["documents"])
        if not got["ids"]:
            break
        ids.extend(got["ids"])
        docs.extend(got["documents"])
        offset += page
        print(f"  read {offset} / {total}")

    return ids, docs


def build():
    print("Building BM25 index\n")

    ids, docs = load_documents()
    if not docs:
        print("No documents found. Build ChromaDB first.")
        return

    print(f"\ntokenising {len(docs)} documents ...")
    start = time.time()
    tokenized = [tokenize(d) for d in docs]

    empty = sum(1 for t in tokenized if not t)
    if empty:
        print(f"  warning: {empty} documents produced no tokens")

    print(f"  done in {time.time() - start:.1f}s")

    print("fitting BM25 ...")
    bm25 = BM25Okapi(tokenized)

    # Store the ids alongside the model. BM25Okapi works on positions,
    # so without this mapping a result index means nothing.
    payload = {"bm25": bm25, "ids": ids}

    with open(config.BM25_INDEX_PATH, "wb") as f:
        pickle.dump(payload, f)

    print(f"\nDone. Saved to: {config.BM25_INDEX_PATH}")
    print(f"Documents indexed: {len(ids)}")


if __name__ == "__main__":
    build()