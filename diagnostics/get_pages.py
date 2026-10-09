import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts", "retrieval"))

from scripts.retrieval.search import HybridRetriever

r = HybridRetriever()

CLAUSE_IDS = [
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
]

for cid in CLAUSE_IDS:
    got = r.collection.get(ids=[cid], include=["metadatas"])
    if got["ids"]:
        meta = got["metadatas"][0]
        page = meta.get("page_number", "?")
        print(f"page {page:>3}  |  {cid}")
    else:
        print(f"NOT FOUND  |  {cid}")