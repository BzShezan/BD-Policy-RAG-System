"""Verify extract_office_authority fires cleanly on real corpus clauses
and doesn't fire on non-office clauses."""

import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts", "retrieval"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "chatbot", "scripts"))

from scripts.retrieval.search import HybridRetriever
from chatbot.scripts.ner import extract_office_authority

r = HybridRetriever()
got = r.collection.get(include=["documents", "metadatas"])

hits = 0
sample_hits = []
for cid, text, meta in zip(got["ids"], got["documents"], got["metadatas"]):
    offices, conf = extract_office_authority(text)
    if offices:
        hits += 1
        if len(sample_hits) < 15:
            sample_hits.append((cid, meta.get("doc_id", ""), offices, conf, text[:200]))

print(f"\nTotal clauses with office extraction: {hits} / {len(got['ids'])}")
print(f"Coverage: {100*hits/len(got['ids']):.1f}%\n")

print("=" * 80)
print("SAMPLE EXTRACTIONS")
print("=" * 80)
for cid, doc_id, offices, conf, preview in sample_hits:
    print(f"\n  clause: {cid}")
    print(f"    doc:     {doc_id[:60]}")
    print(f"    offices: {offices}  (conf {conf})")
    print(f"    text:    {preview[:200]}")