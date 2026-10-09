"""Same verify but shows intents for each question - critical for
diagnosing why the pipeline picked the wrong doc."""

import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts", "retrieval"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "chatbot", "scripts"))

from scripts.retrieval.search import HybridRetriever
from scripts.retrieval.two_stage import two_stage_search
from scripts.retrieval.extractor_map import EXTRACTORS_FOR_INTENT
from chatbot.scripts.intent import detect_intents

# 5 sample questions from each new extractor
SAMPLES = [
    # office
    ("Q16", "পাখি সংরক্ষণ কার্যক্রমের জন্য কোন মন্ত্রণালয় দায়ী?", "Agriculture", "office_authority"),
    ("Q20", "বিধবা ভাতা কোন মন্ত্রণালয় প্রদান করে?", "Social Welfare", "office_authority"),
    # deadline
    ("Q26", "সার আমদানি অনুমতির মেয়াদ কতদিন?", "Agriculture", "deadline_date"),
    ("Q31", "২০০৯ চা-শ্রমিক নীতিমালা কোন তারিখে প্রকাশিত?", "Social Welfare", "deadline_date"),
    # frequency
    ("Q34", "চা-শ্রমিক খাদ্য সহায়তা কত বার প্রদান করা হয়?", "Social Welfare", "frequency"),
    ("Q37", "কৃষি প্রতিবেদন কতবার প্রকাশিত হয়?", "Agriculture", "frequency"),
    # duration
    ("Q39", "২০২১ সার সংশোধন বিধিমালা অনুযায়ী ডিলার নিবন্ধন কতদিনে হয়?", "Agriculture", "duration_period"),
    ("Q42", "সার আমদানি নিবন্ধনের মেয়াদ কতদিন?", "Agriculture", "duration_period"),
    # penalty
    ("Q44", "সার ব্যবসায় আইন লঙ্ঘনের জরিমানা কত?", "Agriculture", "penalty_fine"),
    ("Q47", "বীজ ডিলার নিয়ম ভঙ্গের শাস্তি কী?", "Agriculture", "penalty_fine"),
]

r = HybridRetriever()

for qid, q, ministry, expected_intent in SAMPLES:
    intents = detect_intents(q)
    match = "OK" if expected_intent in intents else "WRONG"
    print(f"{qid} {match}  expected={expected_intent}  got={intents}")
    print(f"       Q: {q}")
    print()