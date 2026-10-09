"""For each proposed new extractor, count how many clauses in your
corpus contain matching patterns. Tells us which extractors will
have enough training data / examples to be worth building."""

import sys, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
# Script is at diagnostics/extract/, go up TWO levels to project root
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts", "retrieval"))

from scripts.retrieval.search import HybridRetriever

r = HybridRetriever()
got = r.collection.get(include=["documents", "metadatas"])

PATTERNS = {
    "date/deadline": [
        r"তারিখের মধ্যে", r"পর্যন্ত", r"অর্থবছর",
        r"\d+\s*জানুয়ারি", r"\d+\s*জুলাই", r"\d+\s*ডিসেম্বর",
    ],
    "office/authority": [
        r"সমাজসেবা কার্যালয়", r"মন্ত্রণালয়",
        r"অধিদপ্তর", r"কর্মকর্তা", r"বিভাগ",
    ],
    "duration/period": [
        r"মাস মেয়াদ", r"বছর পর্যন্ত", r"বছর মেয়াদে",
        r"কর্মদিবস", r"\d+\s*মাস", r"\d+\s*বছর",
    ],
    "frequency": [
        r"মাসিক", r"বার্ষিক", r"সাপ্তাহিক",
        r"প্রতি মাসে", r"প্রতি বছর",
    ],
    "penalty/fine": [
        r"জরিমানা", r"শাস্তি", r"বাতিল", r"কারাদণ্ড",
        r"দণ্ডনীয়",
    ],
}

for name, patterns in PATTERNS.items():
    combined = re.compile("|".join(patterns))
    hits = sum(1 for text in got["documents"] if combined.search(text))
    total = len(got["documents"])
    pct = 100 * hits / total
    print(f"{name:<25}  {hits:>5} / {total}  ({pct:.1f}% of clauses)")