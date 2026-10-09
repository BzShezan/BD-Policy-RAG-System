"""Show what the failing MISS clauses actually contain, so we can
decide: is our acceptable_ids wrong (top-returned is a legitimate
answer we didn't recognize), or is retrieval genuinely broken?"""

import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts", "retrieval"))

from scripts.retrieval.search import HybridRetriever

r = HybridRetriever()

TO_INSPECT = [
    # Q8 - what did the system return, what did we expect?
    ("Q8 returned", "খসড়া সার (ব্যবস্থাপনা) বিধিমালা ২০২৩_C0069"),
    ("Q8 expected", "013-057_C0016"),
    # Q9 - returned rank-3 clause vs expected clause
    ("Q9 returned rank1", "খসড়া সার (ব্যবস্থাপনা) বিধিমালা ২০২৩_C0044"),
    ("Q9 returned rank3", "সার ডিলার নিয়োগ ও সার বিতরণ সংক্রান্ত সমন্বিত নীতিমালা-২০২৫_C0007"),
    ("Q9 expected",       "সার ডিলার নিয়োগ ও সার বিতরণ সংক্রান্ত সমন্বিত নীতিমালা-২০২৫_C0006"),
]

for label, cid in TO_INSPECT:
    got = r.collection.get(ids=[cid], include=["documents"])
    if not got["ids"]:
        print(f"===== {label}: {cid} =====")
        print("  NOT FOUND IN INDEX")
        print()
        continue
    print(f"===== {label}: {cid} =====")
    print(got["documents"][0][:600])
    print()