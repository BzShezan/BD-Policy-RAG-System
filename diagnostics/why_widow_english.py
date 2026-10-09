import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts", "retrieval"))
sys.path.insert(0, os.path.join(HERE, "..", "chatbot", "scripts"))

from scripts.retrieval.search import HybridRetriever
from chatbot.scripts.ner import extract_age, extract_income_limit

r = HybridRetriever()
got = r.collection.get(
    where={"doc_id": "SociaMin_Widow_2025_09_25_Gazette_v1"},
    include=["documents"],
)

print(f"Total clauses: {len(got['ids'])}\n")

for cid, text in zip(got["ids"], got["documents"]):
    age_val, age_conf = extract_age(text)
    inc_val, inc_conf = extract_income_limit(text)
    if age_val or inc_val:
        print(f"--- {cid} ---")
        if age_val:
            print(f"  AGE:    {age_val}  (conf {age_conf})")
        if inc_val:
            print(f"  INCOME: {inc_val}  (conf {inc_conf})")
        print(f"  text: {text[:250]}")
        print()