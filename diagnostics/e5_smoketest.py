"""Test E5 on a small sample BEFORE committing to full reindex.

We embed the OAA document's clauses with E5, run the 5 failing queries
against just those clauses, and see if C0009 ranks higher than it does
with MiniLM. If yes -> full reindex is justified. If no -> save the
weekend and go with document-scoped fallback instead.
"""

import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts", "retrieval"))

import numpy as np
from sentence_transformers import SentenceTransformer
from scripts.retrieval.search import HybridRetriever

# Test docs - the ones your failing queries target
TEST_DOCS = [
    "SocialMin_OldAgeAll_2013_00_Policy_v1.pdf",
    "SW_DEPR_Bede, Dalit, AND Harijan_2013_00_Policy_v3",
    # add family card doc_id once you know it
]

TEST_QUERIES = [
    ("বয়স্ক ভাতা পেতে সর্বনিম্ন বয়স কত হতে হবে?",
     "SocialMin_OldAgeAll_2013_00_Policy_v1.pdf_C0009"),
    ("বেদে, দলিত ও হরিজন সম্প্রদায়ের ভাতার জন্য প্রার্থীর বার্ষিক আয়সীমা কত?",
     "SW_DEPR_Bede, Dalit, AND Harijan_2013_00_Policy_v3_C0033"),
]

# 1. Pull all clauses for test docs from ChromaDB
r = HybridRetriever()
all_data = r.collection.get(include=["documents", "metadatas"])

pool = []
for cid, text, meta in zip(all_data["ids"], all_data["documents"],
                           all_data["metadatas"]):
    if meta.get("doc_id") in TEST_DOCS:
        pool.append((cid, text))

print(f"Test pool: {len(pool)} clauses from {len(TEST_DOCS)} documents\n")

# 2. Load E5 (small footprint, one-time download ~280MB)
print("Loading E5-base ...")
e5 = SentenceTransformer("intfloat/multilingual-e5-base")

# E5 needs specific prefixes for query vs passage - this matters
passages = [f"passage: {t}" for _, t in pool]
pool_ids = [c for c, _ in pool]
pool_emb = e5.encode(passages, normalize_embeddings=True,
                     show_progress_bar=True)

# 3. Rank each query against the pool
print("\n--- E5 rankings on isolated pool ---")
for query, target in TEST_QUERIES:
    q_emb = e5.encode([f"query: {query}"], normalize_embeddings=True)
    scores = (pool_emb @ q_emb.T).flatten()
    ranked = sorted(zip(pool_ids, scores), key=lambda x: -x[1])
    rank = next((i+1 for i, (cid, _) in enumerate(ranked) if cid == target),
                None)
    top5 = [cid for cid, _ in ranked[:5]]
    print(f"\n  Q: {query[:70]}")
    print(f"  target rank: {rank}")
    print(f"  top-5: {top5}")

# 4. Compare vs MiniLM on same pool
print("\n\n--- MiniLM rankings on same pool (baseline) ---")
minilm = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
pool_emb_m = minilm.encode([t for _, t in pool],
                            normalize_embeddings=True,
                            show_progress_bar=True)
for query, target in TEST_QUERIES:
    q_emb = minilm.encode([query], normalize_embeddings=True)
    scores = (pool_emb_m @ q_emb.T).flatten()
    ranked = sorted(zip(pool_ids, scores), key=lambda x: -x[1])
    rank = next((i+1 for i, (cid, _) in enumerate(ranked) if cid == target),
                None)
    print(f"\n  Q: {query[:70]}")
    print(f"  target rank: {rank}")