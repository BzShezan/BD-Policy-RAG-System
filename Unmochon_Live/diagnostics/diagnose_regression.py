"""Show per-question intent detection + top-1 result to identify
which 3 questions regressed and why."""

import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, ".."))   # only ONE dotdot
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts", "retrieval"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "chatbot", "scripts"))


from scripts.retrieval.search import HybridRetriever
from scripts.retrieval.translator import Translator
from scripts.retrieval.two_stage import two_stage_search
from scripts.retrieval.extractor_map import EXTRACTORS_FOR_INTENT
from chatbot.scripts.intent import detect_intents

# Copy the ground truth from evaluate_metrics.py
QUESTIONS = [
    ("Q1",  "বয়স্ক ভাতা পেতে সর্বনিম্ন বয়স কত হতে হবে?", "Social Welfare",
     ["SocialMin_OldAgeAll_2013_00_Policy_v1.pdf_C0006",
      "SocialMin_OldAgeAll_2013_00_Policy_v1.pdf_C0009"]),
    ("Q2",  "বেদে, দলিত ও হরিজন ভাতার জন্য সর্বনিম্ন বয়স কত?", "Social Welfare",
     ["SW_DEPR_Bede, Dalit, AND Harijan_2013_00_Policy_v3_C0032"]),
    ("Q3",  "চা-শ্রমিক কল্যাণে সর্বনিম্ন বয়স কত?", "Social Welfare",
     ["SW_Tea Workers_2013_00_Policy_v1_C0007"]),
    ("Q4",  "বেদে, দলিত ও হরিজন সম্প্রদায়ের ভাতার জন্য প্রার্থীর বার্ষিক আয়সীমা কত?", "Social Welfare",
     ["SW_DEPR_Bede, Dalit, AND Harijan_2013_00_Policy_v3_C0033"]),
    ("Q5",  "বিধবা ভাতা পেতে প্রার্থীর বার্ষিক আয়সীমা কত?", "Social Welfare",
     ["SociaMin_Widow_2025_09_25_Gazette_v1_C0016",
      "SociaMin_Widow_2025_09_25_webpage_v1_C0014"]),
    ("Q6",  "চা-শ্রমিক ভাতার প্রার্থীর বার্ষিক আয়সীমা কত?", "Social Welfare",
     ["SW_Tea Workers_2013_00_Policy_v1_C0007",
      "SW_Tea Workers_2013_00_Policy_webpage_C0008"]),
    ("Q7",  "সার উৎপাদনকারী হিসেবে নিবন্ধনের জন্য কী কী কাগজপত্র প্রয়োজন?", "Agriculture",
     ["013-057_C0016",
      "খসড়া সার (ব্যবস্থাপনা) বিধিমালা ২০২৩_C0069",
      "সার (ব্যবস্থাপনা) (সংশোধন) বিধিমালা- ২০২১ (খসড়া)_C0010"]),
    ("Q8",  "সার ডিলার নিয়োগের জন্য কোন কাগজপত্র লাগে?", "Agriculture",
     ["সার ডিলার নিয়োগ ও সার বিতরণ সংক্রান্ত সমন্বিত নীতিমালা-২০২৫_C0007"]),
    ("Q9",  "বীজ ডিলার নিবন্ধনের জন্য কী প্রয়োজন?", "Agriculture",
     ["বীজ বিধিমালা-২০২০_C0023", "বীজ ডিলার নিবন্ধন ও নবায়ন_C0018"]),
    ("Q10", "পিতা-মাতা পরিচর্যা কেন্দ্র প্রতিষ্ঠার জন্য কী কাগজপত্র প্রয়োজন?", "Social Welfare",
     ["SW_PM_2017_00_Policy_v1_C0017"]),
    ("Q11", "সার ব্যবস্থাপনা সংশোধন বিধিমালা ২০২১ অনুযায়ী নিবন্ধনের কাগজপত্র কী?", "Agriculture",
     ["সার (ব্যবস্থাপনা) (সংশোধন) বিধিমালা- ২০২১ (খসড়া)_C0007"]),
]

r = HybridRetriever()

print(f"{'ID':<5} {'rank':>5} intents")
print("-" * 100)
for qid, q, ministry, acceptable in QUESTIONS:
    intents = detect_intents(q)
    results = two_stage_search(
        retriever=r, question=q, intents=intents,
        extractors_for_intent=EXTRACTORS_FOR_INTENT, ministry=ministry,
    )
    ids = [x["id"] for x in results]
    rank = next((i+1 for i, x in enumerate(ids) if x in acceptable), None)

    top_id = results[0]["id"] if results else "NONE"
    print(f"{qid:<5} {str(rank):>5}  intents={intents}")
    print(f"      top-1: {top_id}")
    if rank is None or rank > 3:
        print(f"      EXPECTED: {acceptable[0][:70]}")