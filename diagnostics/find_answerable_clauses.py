"""Find clauses in the corpus where existing extractors fire with
high confidence. These are candidate 'answerable' clauses - each one
becomes a demo question by writing the question that the extractor
value answers.

This is faster than inventing questions and hoping the corpus contains
the answer. We know the answer is there because the extractor found it.
"""

import sys, os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts", "retrieval"))
sys.path.insert(0, os.path.join(HERE, "..", "chatbot", "scripts"))

from scripts.retrieval.search import HybridRetriever
from chatbot.scripts.ner import (extract_age, extract_income_limit, extract_benefit_amount,
                 extract_document_requirements, extract_district_allocations)

r = HybridRetriever()

# Pull everything - 15k items, one query, done
all_data = r.collection.get(include=["documents", "metadatas"])

# Group answerable clauses by extractor type and confidence
by_extractor = defaultdict(list)

for cid, text, meta in zip(all_data["ids"], all_data["documents"],
                           all_data["metadatas"]):
    doc_id   = meta.get("doc_id", "")
    ministry = meta.get("ministry", "")

    # Age
    val, conf = extract_age(text)
    if val and conf >= 0.85:
        by_extractor["age"].append((cid, doc_id, ministry, val, conf, text[:200]))

    # Income
    val, conf = extract_income_limit(text)
    if val and conf >= 0.7:
        by_extractor["income"].append((cid, doc_id, ministry, val, conf, text[:200]))

    # Benefit amount
    val, conf = extract_benefit_amount(text)
    if val and conf >= 0.7:
        by_extractor["amount"].append((cid, doc_id, ministry, val, conf, text[:200]))

    # Documents required
    val, conf = extract_document_requirements(text)
    if val and conf >= 0.6:
        by_extractor["documents"].append((cid, doc_id, ministry, val, conf, text[:200]))

    # District allocations
    val, conf = extract_district_allocations(text)
    if val and conf >= 0.6:
        by_extractor["allocation"].append((cid, doc_id, ministry, val, conf, text[:200]))

# Print top candidates per extractor
for extractor_name, hits in by_extractor.items():
    print(f"\n{'='*70}")
    print(f"  EXTRACTOR: {extractor_name}  ({len(hits)} clauses matched)")
    print(f"{'='*70}")

    # Deduplicate by doc_id so we don't get 10 clauses from one document
    seen_docs = set()
    unique = []
    for hit in sorted(hits, key=lambda x: -x[4]):   # highest confidence first
        if hit[1] not in seen_docs:
            unique.append(hit)
            seen_docs.add(hit[1])

    for cid, doc_id, ministry, val, conf, preview in unique[:15]:
        print(f"\n  {cid}")
        print(f"    doc:      {doc_id}")
        print(f"    ministry: {ministry}")
        print(f"    value:    {val}  (conf {conf})")
        print(f"    text:     {preview}")