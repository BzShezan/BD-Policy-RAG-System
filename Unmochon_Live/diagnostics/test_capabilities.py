"""Test bilingual + multi-intent retrieval.

Translation happens BEFORE detect_intents so the intent classifier
sees Bengali policy vocabulary, not English. If we translated inside
search.py instead, intent classification would run on English words
that don't match any Bengali intent triggers - which is why the
earlier test showed intents=[] for English document questions.
"""

import sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts", "retrieval"))
sys.path.insert(0, os.path.join(HERE, "..", "chatbot", "scripts"))

from scripts.retrieval.search import HybridRetriever
from scripts.retrieval.translator import Translator
from scripts.retrieval.two_stage import two_stage_search
from scripts.retrieval.extractor_map import EXTRACTORS_FOR_INTENT
from chatbot.scripts.intent import detect_intents


r  = HybridRetriever()
tr = Translator()


def run(question, ministry=None):
    """Full pipeline for one question. Translates first if English."""
    translated = tr.to_bengali(question)
    if translated != question:
        print(f"  translated: {translated}")

    intents = detect_intents(translated)
    results = two_stage_search(
        retriever=r,
        question=translated,
        intents=intents,
        extractors_for_intent=EXTRACTORS_FOR_INTENT,
        ministry=ministry,
    )
    print(f"  intents: {intents}")
    if results:
        for i, res in enumerate(results[:3], 1):
            print(f"  {i}. {res['id']}")
            print(f"     extracted: {res['extracted']}")
    else:
        print(f"  NO RESULTS")


print("=" * 60)
print("BILINGUAL RETRIEVAL TEST")
print("=" * 60)
for q in [
    "What is the minimum age for Old Age Allowance?",
    "What is the minimum age and annual income limit for widow allowance?",
    "What documents are needed to register as a fertilizer dealer?",
]:
    print(f"\nQ: {q}")
    run(q, ministry=None)


print("\n" + "=" * 60)
print("MULTI-INTENT QUESTION TEST")
print("=" * 60)
for q in [
    "বয়স্ক ভাতা পেতে বয়স ও বার্ষিক আয়সীমা কত?",
    "বেদে হরিজন ভাতার বয়স এবং আয়সীমা কত?",
    "চা-শ্রমিক ভাতার বয়স এবং আয়সীমা কত?",   # cleaner than widow compound
]:
    print(f"\nQ: {q}")
    run(q, ministry="Social Welfare")