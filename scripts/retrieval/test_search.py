"""Manual check on hybrid retrieval.

Not an evaluation - there are no metrics here because there is no
ground truth set yet. This is for eyeballing whether results look
sane after a change.
"""

from scripts.retrieval.search import HybridRetriever


def show(retriever, query, **kwargs):
    print("\n" + "=" * 70)
    print(f"query: {query}")
    if kwargs:
        print(f"filters: {kwargs}")
    print("=" * 70)

    results = retriever.search(query, top_k=5, **kwargs)
    if not results:
        print("  no results")
        return

    for i, r in enumerate(results, 1):
        src = []
        if r["in_dense"]:
            src.append("dense")
        if r["in_sparse"]:
            src.append("bm25")
        table = " [TABLE]" if r["is_table"] else ""

        print(f"\n[{i}] rrf={r['rrf_score']:.4f} | {'+'.join(src)}{table}")
        print(f"    {r['ministry']} | {r['doc_id'][:50]} | page {r['page']}")
        print(f"    {r['text'][:180]}")


if __name__ == "__main__":
    r = HybridRetriever()

    show(r, "বয়স্ক ভাতা প্রাপ্তির যোগ্যতা", ministry="Social Welfare")
    show(r, "widow allowance eligibility", ministry="Social Welfare")
    show(r, "বিধবা ভাতার আয়সীমা কত", ministry="Social Welfare")
    show(r, "সার ডিলার নিয়োগের শর্ত", ministry="Agriculture")