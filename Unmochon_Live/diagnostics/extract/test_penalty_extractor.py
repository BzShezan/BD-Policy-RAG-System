"""Verify extract_penalty_fine fires correctly on real corpus."""

import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts", "retrieval"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "chatbot", "scripts"))

from scripts.retrieval.search import HybridRetriever
from chatbot.scripts.ner import extract_penalty_fine

r = HybridRetriever()
got = r.collection.get(include=["documents", "metadatas"])

hits = 0
by_conf = {0.9: [], 0.8: [], 0.7: []}

for cid, text, meta in zip(got["ids"], got["documents"], got["metadatas"]):
    penalties, conf = extract_penalty_fine(text)
    if penalties:
        hits += 1
        if len(by_conf[conf]) < 5:
            by_conf[conf].append((cid, meta.get("doc_id", ""), penalties, text[:200]))

print(f"\nTotal clauses with penalty/fine: {hits} / {len(got['ids'])}")
print(f"Coverage: {100*hits/len(got['ids']):.1f}%\n")

for conf in [0.9, 0.8, 0.7]:
    print(f"\n{'='*80}")
    print(f"  CONFIDENCE {conf}: {len(by_conf[conf])} samples")
    print(f"{'='*80}")
    for cid, doc_id, penalties, preview in by_conf[conf]:
        print(f"\n  clause: {cid}")
        print(f"    doc:    {doc_id[:60]}")
        print(f"    penal:  {penalties}")
        print(f"    text:   {preview}")