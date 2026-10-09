"""Recall diagnostic: does the correct clause reach the candidate pool?

Runs each ground-truth question through the retriever and reports the
rank of the known-correct clause. Also compares the natural user query
against the expanded query - lets us see whether query_expansion.py is
actually closing the semantic gap for the OAA-style failures.

Interpretation:
  rank <= 5     ranking + reranker will handle it
  rank 6-100    recall is fine, reranker needed for top-1
  rank None     retrieval broken - reranker cannot help
"""

import sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts", "retrieval"))

from scripts.retrieval.search import HybridRetriever
from scripts.retrieval.query_expansion import expand


# Ground-truth pairs: question -> the clause_id that actually answers it
GROUND_TRUTH = [
    {
        "question":  "বেদে দলিত হরিজন ভাতার আয়সীমা কত?",
        "ministry":  "Social Welfare",
        "clause_id": "SW_DEPR_Bede, Dalit, AND Harijan_2013_00_Policy_v3_C0033",
    },
    {
        "question":  "বয়স্ক ভাতার বয়সসীমা কত?",
        "ministry":  "Social Welfare",
        "clause_id": "SocialMin_OldAgeAll_2013_00_Policy_v1.pdf_C0009",
    },
]


def rank_of(retriever, query, ministry, target_id, top_k=100):
    """Return 1-indexed rank of target_id, or None if not in top_k."""
    ids = [x["id"] for x in retriever.search(query, top_k=top_k,
                                             ministry=ministry)]
    return ids.index(target_id) + 1 if target_id in ids else None


def main():
    r = HybridRetriever()

    # -------- main recall check --------
    print("--- recall check (top-100, with query expansion) ---")
    for tc in GROUND_TRUTH:
        rank = rank_of(r, tc["question"], tc["ministry"],
                       tc["clause_id"], top_k=100)
        rank_str = f"rank={rank:>3}" if rank else "MISS     "
        print(f"  {rank_str}  {tc['question'][:60]}")

    # -------- OAA rephrasing sensitivity --------
    # If natural queries now rank C0009 in top-20 but section-heading
    # queries still win, expansion is working but not enough - a
    # reranker on top will finish the job.
    print("\n--- OAA query rephrasings (top-100) ---")
    target = "SocialMin_OldAgeAll_2013_00_Policy_v1.pdf_C0009"
    for q in [
        "বয়স্ক ভাতার বয়সসীমা কত?",              # natural user question
        "বয়স্ক ভাতা কত বছর বয়সে পাওয়া যায়?",   # rephrased natural
        "বয়স্ক ভাতার যোগ্যতা",                   # eligibility keyword
        "৬৫ বছর বয়স্ক ভাতা",                     # contains answer token
        "বয়স্কভাতা কর্মসূচির পরিধি",             # matches clause's own heading
        "কার্যক্রমের পরিধি বয়স্ক",                # section-title style
    ]:
        rank = rank_of(r, q, "Social Welfare", target, top_k=100)
        rank_str = f"{rank:>4}" if rank else "None"
        print(f"  rank={rank_str}  {q}")

    # -------- expansion visibility --------
    # Print what expand() is actually producing so we can see whether
    # the synonym table fired for each query. If a natural query still
    # ranks None even after expansion adds the right synonyms, the
    # problem is the embedding model, not the vocabulary.
    print("\n--- expansion output for each OAA query ---")
    for q in [
        "বয়স্ক ভাতার বয়সসীমা কত?",
        "বয়স্ক ভাতার যোগ্যতা",
    ]:
        print(f"  original: {q}")
        print(f"  expanded: {expand(q)}")
        print()


if __name__ == "__main__":
    main()