"""Find clauses in DM POLICY documents (not allocation orders) where
existing extractors fire cleanly. This gives us candidates for a
single-answer DM demo question that isn't overwhelmed by 100 similar
allocation orders."""

import sys, os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts", "retrieval"))
sys.path.insert(0, os.path.join(HERE, "..", "chatbot", "scripts"))

from scripts.retrieval.search import HybridRetriever
from chatbot.scripts.ner import (extract_age, extract_income_limit, extract_benefit_amount,
                 extract_document_requirements, extract_district_allocations)

# DM policy/guideline documents - excludes allocation orders which
# are event-specific and produce ambiguous ground truth
POLICY_DOCS = [
    "Standing Orders on Disaster 2019",
    "জাতীয় দুর্যোগ ব্যবস্থাপনা নীতিমালা ২০১৫",
    "ঘূর্ণিঝড় আশ্রয়কেন্দ্র নির্মাণ",
    "দুর্যোগ সহনীয় বাসগৃহ নির্মাণ",
    "কোরবানির গোশ্ত বিতরণ",
    "কাজের বিনিময়ে খাদ্য",
    "গ্রামীণ অবকাঠামো রক্ষণাবেক্ষণ",
    "টিআর বাস্তবায়ন",
    "EGPP বাস্তবায়ন",
    "মানবিক সহায়তা কর্মসূচী",
    "হাওরে বন্যা মোকাবেলায়",
    "মৃতদেহ ব্যবস্থাপনা",
    "নগর স্বেচ্ছাসেবক ব্যবস্থাপনা",
]

r = HybridRetriever()
all_data = r.collection.get(
    where={"ministry": "Disaster Management"},
    include=["documents", "metadatas"],
)

by_extractor = defaultdict(list)

for cid, text, meta in zip(all_data["ids"], all_data["documents"],
                           all_data["metadatas"]):
    doc_id = meta.get("doc_id", "")
    if not any(p in doc_id for p in POLICY_DOCS):
        continue

    val, conf = extract_age(text)
    if val and conf >= 0.85:
        by_extractor["age"].append((cid, doc_id, val, conf, text[:200]))

    val, conf = extract_income_limit(text)
    if val and conf >= 0.7:
        by_extractor["income"].append((cid, doc_id, val, conf, text[:200]))

    val, conf = extract_benefit_amount(text)
    if val and conf >= 0.7:
        by_extractor["amount"].append((cid, doc_id, val, conf, text[:200]))

    val, conf = extract_document_requirements(text)
    if val and conf >= 0.6:
        by_extractor["documents"].append((cid, doc_id, val, conf, text[:200]))

    val, conf = extract_district_allocations(text)
    if val and conf >= 0.7:
        by_extractor["allocation"].append((cid, doc_id, val, conf, text[:200]))

for extractor_name, hits in by_extractor.items():
    print(f"\n{'='*70}")
    print(f"  EXTRACTOR: {extractor_name}  ({len(hits)} clauses matched)")
    print(f"{'='*70}")

    seen_docs = set()
    unique = []
    for hit in sorted(hits, key=lambda x: -x[3]):
        if hit[1] not in seen_docs:
            unique.append(hit)
            seen_docs.add(hit[1])

    for cid, doc_id, val, conf, preview in unique[:8]:
        print(f"\n  {cid}")
        print(f"    doc:   {doc_id[:70]}")
        print(f"    value: {val}  (conf {conf})")
        print(f"    text:  {preview}")