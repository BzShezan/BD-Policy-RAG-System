"""For each extractor, list every clause where it fires at reasonable
confidence. These are candidates for new test questions - each such
clause is something the pipeline can extract, so you can write a
question knowing what the answer should be."""

import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts", "retrieval"))
sys.path.insert(0, os.path.join(HERE, "..", "chatbot", "scripts"))

from scripts.retrieval.search import HybridRetriever
from chatbot.scripts.ner import (extract_age, extract_income_limit, extract_benefit_amount,
                 extract_document_requirements, extract_district_allocations)

# Only include these ministries (skip Extra Stuff, etc.)
MINISTRIES = ["Social Welfare", "Agriculture", "Disaster Management"]

# Already used in your 15 questions - skip so you don't duplicate
ALREADY_USED = {
    "SocialMin_OldAgeAll_2013_00_Policy_v1.pdf_C0006",
    "SocialMin_OldAgeAll_2013_00_Policy_v1.pdf_C0009",
    "SW_DEPR_Bede, Dalit, AND Harijan_2013_00_Policy_v3_C0032",
    "SW_DEPR_Bede, Dalit, AND Harijan_2013_00_Policy_v3_C0033",
    "SW_Tea Workers_2013_00_Policy_v1_C0007",
    "SW_Tea Workers_2013_00_Policy_webpage_C0008",
    "SociaMin_Widow_2025_09_25_Gazette_v1_C0014",
    "SociaMin_Widow_2025_09_25_Gazette_v1_C0016",
    "013-057_C0016",
    "খসড়া সার (ব্যবস্থাপনা) বিধিমালা ২০২৩_C0069",
    "সার (ব্যবস্থাপনা) (সংশোধন) বিধিমালা- ২০২১ (খসড়া)_C0010",
    "সার ডিলার নিয়োগ ও সার বিতরণ সংক্রান্ত সমন্বিত নীতিমালা-২০২৫_C0007",
    "বীজ বিধিমালা-২০২০_C0023",
    "বীজ ডিলার নিবন্ধন ও নবায়ন_C0018",
    "SW_PM_2017_00_Policy_v1_C0017",
    "সার (ব্যবস্থাপনা) (সংশোধন) বিধিমালা- ২০২১ (খসড়া)_C0007",
}

EXTRACTORS = {
    "extract_age":                  (extract_age, 0.85),
    "extract_income_limit":         (extract_income_limit, 0.8),
    "extract_document_requirements":(extract_document_requirements, 0.7),
}

r = HybridRetriever()

for ministry in MINISTRIES:
    print(f"\n{'='*80}")
    print(f"  MINISTRY: {ministry}")
    print(f"{'='*80}")

    got = r.collection.get(
        where={"ministry": ministry},
        include=["documents", "metadatas"],
    )

    for ext_name, (extractor, min_conf) in EXTRACTORS.items():
        print(f"\n  --- {ext_name} (conf >= {min_conf}) ---")
        hits = []
        seen_docs = set()
        for cid, text, meta in zip(got["ids"], got["documents"], got["metadatas"]):
            if cid in ALREADY_USED:
                continue
            val, conf = extractor(text)
            if val and conf >= min_conf:
                doc_id = meta.get("doc_id", "")
                if doc_id in seen_docs:
                    continue      # one per doc, otherwise output is huge
                seen_docs.add(doc_id)
                hits.append((cid, doc_id, val, conf, text[:150]))

        for cid, doc_id, val, conf, preview in hits[:8]:
            print(f"    {cid}")
            print(f"      doc:     {doc_id[:65]}")
            print(f"      value:   {val}  (conf {conf})")
            print(f"      preview: {preview}")