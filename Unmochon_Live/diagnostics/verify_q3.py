import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts", "retrieval"))

from scripts.retrieval.search import HybridRetriever

r = HybridRetriever()
got = r.collection.get(
    ids=["SW_Tea Workers_2013_00_Policy_v1_C0007"],
    include=["documents"],
)
print(got["documents"][0])