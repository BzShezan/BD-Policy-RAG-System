"""Run the ACTUAL two_stage_search and see what happens step by step."""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts", "retrieval"))
sys.path.insert(0, os.path.join(HERE, "..", "chatbot", "scripts"))

from scripts.retrieval.search import HybridRetriever
from scripts.retrieval.two_stage import two_stage_search, _is_out_of_scope
from scripts.retrieval.extractor_map import EXTRACTORS_FOR_INTENT
from chatbot.scripts.intent import detect_intents

r = HybridRetriever()

for q in [
    "বীজ ডিলার হতে কী প্রয়োজন?",
    "শিশু খাদ্য বিতরণের কর্তৃপক্ষ কে?",
]:
    print(f"\n=== {q} ===")
    intents = detect_intents(q)
    stage1  = r.search(q, top_k=100)

    print(f"  intents from detect_intents: {intents}")
    print(f"  stage1 returned {len(stage1)} results")
    print(f"  stage1 top: {stage1[0]['id']}  score {stage1[0]['rrf_score']:.4f}")

    # Call _is_out_of_scope directly with the exact same args
    oos = _is_out_of_scope(q, intents, stage1)
    print(f"  _is_out_of_scope returned: {oos}")

    # Now run the full pipeline
    results = two_stage_search(
        retriever=r, question=q, intents=intents,
        extractors_for_intent=EXTRACTORS_FOR_INTENT, ministry=None,
    )
    if results:
        tier = results[0].get("confidence_tier", "?")
        print(f"  final tier: {tier}")
        print(f"  final top id: {results[0].get('id', '?')}")