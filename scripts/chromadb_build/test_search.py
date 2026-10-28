"""Quick test to confirm the ChromaDB build actually works."""

import chromadb
from sentence_transformers import SentenceTransformer

from scripts.chromadb_build import config


def search(query, top_k=5):
    model = SentenceTransformer(config.EMBED_MODEL)
    client = chromadb.PersistentClient(path=config.CHROMADB_DIR)
    collection = client.get_collection(config.COLLECTION_NAME)

    query_embedding = model.encode([query]).tolist()
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=top_k,
    )

    print(f"\nQuery: {query}\n" + "=" * 60)
    for i in range(len(results["ids"][0])):
        meta = results["metadatas"][0][i]
        doc = results["documents"][0][i]
        dist = results["distances"][0][i]
        print(f"\n[{i+1}] distance={dist:.3f} | {meta['doc_id']} | page {meta['page_number']}")
        print(f"    tag: {meta['tag']} | table: {meta['is_table']} | review: {meta['from_review']}")
        print(f"    {doc[:200]}")


if __name__ == "__main__":
    # Try a Bengali query about old age allowance
    search("বয়স্ক ভাতা প্রাপ্তির যোগ্যতা")

    # Try an English query
    search("widow allowance eligibility")