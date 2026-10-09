"""Print every OAA clause that plausibly contains the age eligibility
rule, so we can eyeball the correct clause_id."""

import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts", "retrieval"))

from scripts.retrieval.search import HybridRetriever

r = HybridRetriever()

# Grab every clause from the OAA document
got = r.collection.get(
    where={"doc_id": "SocialMin_OldAgeAll_2013_00_Policy_v1.pdf"},
    include=["documents", "metadatas"],
)

print(f"total OAA clauses in index: {len(got['ids'])}\n")

# Print any clause containing age-related tokens
AGE_HINTS = ["বয়স", "বৎসর", "বছর", "৬৫", "৬২", "60", "65", "62"]

for cid, text, meta in zip(got["ids"], got["documents"], got["metadatas"]):
    if any(h in text for h in AGE_HINTS):
        page = meta.get("page_number")
        print(f"--- {cid}  (page_number={page}) ---")
        print(text[:400])
        print()