"""Comprehensive out-of-scope test. 40+ queries across categories.
Expected: IN queries pass through, OUT queries get rejected."""

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

QUERIES = [
    # ---- IN-SCOPE: should NOT be rejected ----
    ("IN", "বয়স্ক ভাতা পেতে সর্বনিম্ন বয়স কত?"),
    ("IN", "বেদে দলিত হরিজন ভাতার বয়স?"),
    ("IN", "চা-শ্রমিক কল্যাণে সর্বনিম্ন বয়স?"),
    ("IN", "বিধবা ভাতার আয়সীমা কত?"),
    ("IN", "সার উৎপাদনকারী নিবন্ধনের কাগজপত্র?"),
    ("IN", "বীজ ডিলার হতে কী প্রয়োজন?"),
    ("IN", "প্রতিবন্ধী ভাতার নিয়ম কী?"),
    ("IN", "দুর্যোগ ব্যবস্থাপনা কমিটি"),
    ("IN", "শিশু খাদ্য বিতরণের কর্তৃপক্ষ কে?"),
    ("IN", "সার ডিলার নিয়োগের নিয়ম?"),

    # ---- OUT-OF-SCOPE Bengali (should reject) ----
    ("OUT", "বাংলাদেশের রাজধানী কোনটি?"),
    ("OUT", "আজকের আবহাওয়া কেমন?"),
    ("OUT", "পিজ্জা কীভাবে বানাব?"),
    ("OUT", "ক্রিকেট খেলার নিয়ম কী?"),
    ("OUT", "প্রধানমন্ত্রীর নাম কী?"),
    ("OUT", "ঢাকায় সেরা রেস্টুরেন্ট"),
    ("OUT", "ফুটবল বিশ্বকাপ কে জিতেছে?"),
    ("OUT", "শাহরুখ খানের সিনেমা"),
    ("OUT", "ইউটিউব থেকে কিভাবে টাকা আয় করা যায়?"),
    ("OUT", "কম্পিউটার কেনার পরামর্শ"),

    # ---- OUT-OF-SCOPE English (should reject) ----
    ("OUT", "What is the capital of Bangladesh?"),
    ("OUT", "How do I make pizza?"),
    ("OUT", "Who is the prime minister?"),
    ("OUT", "Best restaurants in Dhaka"),
    ("OUT", "How to invest in stocks?"),

    # ---- TRICKY: has some domain vocab but off-topic ----
    ("OUT", "ভাতা কে আবিষ্কার করেছে?"),   # has ভাতা but nonsense
    ("OUT", "সার কে বানিয়েছে?"),          # has সার but nonsense
    ("OUT", "সমাজকল্যাণ মন্ত্রীর নাম কী?"),  # has domain word but off-topic
    ("OUT", "কৃষি মন্ত্রণালয়ের ফোন নম্বর"),   # has domain but off-topic
    ("OUT", "সরকার কী?"),                    # generic + short

    # ---- TRICKY: very short queries ----
    ("OUT", "কেন?"),
    ("OUT", "কী?"),
    ("OUT", "hi"),
    ("OUT", "test"),

    # ---- IN-SCOPE but tricky ----
    ("IN", "কৃষি নীতিমালা"),
    ("IN", "সমাজকল্যাণ যোগ্যতা"),
    ("IN", "দুর্যোগ নীতি"),
]

correct   = 0
false_pos = 0    # OUT wrongly accepted (bad - shows garbage answers)
false_neg = 0    # IN wrongly rejected (bad - real queries fail)

print(f"{'tag':<4} {'result':<8} {'expected':<9} {'top_score':>9}  query")
print("-" * 95)

for tag, q in QUERIES:
    translated = tr.to_bengali(q)
    intents    = detect_intents(translated)
    results    = two_stage_search(
        retriever=r, question=translated, intents=intents,
        extractors_for_intent=EXTRACTORS_FOR_INTENT, ministry=None,
    )
    top_result = results[0] if results else None
    is_oos     = (top_result and top_result.get("confidence_tier") == "out_of_scope")

    result = "OOS" if is_oos else "ACCEPT"
    expected = "OOS" if tag == "OUT" else "ACCEPT"

    stage1_top = r.search(translated, top_k=5)
    top_score  = stage1_top[0]["rrf_score"] if stage1_top else 0.0

    mark = "OK "
    if tag == "IN"  and is_oos:
        mark = "!! "  # false negative: rejected a real query
        false_neg += 1
    elif tag == "OUT" and not is_oos:
        mark = "XX "  # false positive: accepted garbage
        false_pos += 1
    else:
        correct += 1

    print(f"{tag:<4} {result:<8} {expected:<9} {top_score:>9.4f}  {mark}{q[:60]}")

total = len(QUERIES)
print()
print(f"Correct:         {correct} / {total}")
print(f"False positives: {false_pos}  (OUT queries wrongly accepted)")
print(f"False negatives: {false_neg}  (IN queries wrongly rejected)")