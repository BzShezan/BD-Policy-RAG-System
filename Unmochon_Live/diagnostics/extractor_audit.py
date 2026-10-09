"""Show WHERE in each candidate clause extract_age finds a value.
If it's matching numbers that aren't ages, the extractor pattern is
too loose and needs to be tightened before we trust any ranking."""

import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts", "retrieval"))
sys.path.insert(0, os.path.join(HERE, "..", "chatbot", "scripts"))

from scripts.retrieval.search import HybridRetriever
from chatbot.scripts.ner import extract_age

r = HybridRetriever()

# The five clauses the two-stage retriever returned for OAA
SUSPECT_IDS = [
    "SocialMin_OldAgeAll_2013_00_Policy_v1.pdf_C0006",
    "SocialMin_OldAgeAll_2013_00_Policy_v1.pdf_C0009",   # the correct one
    "SW_teaWorker_2025_06_Report_v1_C0041",
    "SW_teaWorker_2025_06_Report_v1_C0070",
    "SW_teaWorker_2025_06_Report_v1_C0072",
    "SW_teaWorker_2025_06_Report_v1_C0085",
]

got = r.collection.get(ids=SUSPECT_IDS,
                       include=["documents", "metadatas"])

for cid, text in zip(got["ids"], got["documents"]):
    value, conf = extract_age(text)
    print(f"===== {cid} =====")
    print(f"  extracted: value={value}  confidence={conf}")
    print(f"  text (500 chars):")
    print(f"  {text[:500]}")
    print()