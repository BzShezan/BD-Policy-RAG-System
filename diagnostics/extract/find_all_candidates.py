"""Surface candidate clauses for each of the 5 new extractors.
Each clause where the extractor fires cleanly is a candidate for
a new test question - you write a question around the extracted
value, verify it, add to the ground truth."""

import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts", "retrieval"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "chatbot", "scripts"))

from scripts.retrieval.search import HybridRetriever
from chatbot.scripts.ner import (
    extract_office_authority,
    extract_deadline_date,
    extract_frequency,
    extract_duration_period,
    extract_penalty_fine,
)

# (extractor_fn, min_confidence, samples_per_extractor)
EXTRACTORS = {
    "office_authority":  (extract_office_authority,  0.9, 10),
    "deadline_date":     (extract_deadline_date,     0.8, 10),
    "frequency":         (extract_frequency,         0.7, 10),
    "duration_period":   (extract_duration_period,   0.7, 10),
    "penalty_fine":      (extract_penalty_fine,      0.8, 10),
}


r = HybridRetriever()
got = r.collection.get(include=["documents", "metadatas"])

for name, (extractor, min_conf, max_samples) in EXTRACTORS.items():
    print(f"\n{'='*80}")
    print(f"  {name}  (conf >= {min_conf})")
    print(f"{'='*80}")

    seen_docs = set()
    hits = []
    for cid, text, meta in zip(got["ids"], got["documents"], got["metadatas"]):
        val, conf = extractor(text)
        if not val or conf < min_conf:
            continue

        doc_id = meta.get("doc_id", "")
        # One per document to spread samples across the corpus
        if doc_id in seen_docs:
            continue
        seen_docs.add(doc_id)

        hits.append((cid, doc_id, val, conf, text[:250]))
        if len(hits) >= max_samples:
            break

    for cid, doc_id, val, conf, preview in hits:
        print(f"\n  clause_id: {cid}")
        print(f"    doc:     {doc_id[:70]}")
        print(f"    value:   {val}  (conf {conf})")
        print(f"    text:    {preview}")