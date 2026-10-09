"""Run each new question through the pipeline. Report whether
the top-1 clause matches the expected clause_id and whether the
right extractor fired."""

import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts", "retrieval"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "chatbot", "scripts"))

from scripts.retrieval.search import HybridRetriever
from scripts.retrieval.two_stage import two_stage_search
from scripts.retrieval.extractor_map import EXTRACTORS_FOR_INTENT
from chatbot.scripts.intent import detect_intents

# Format: (id, question, ministry, expected_clause_id, expected_extractor)
QUESTIONS = [
    # Office authority
    ("Q16", "পাখি সংরক্ষণ কার্যক্রমের জন্য কোন মন্ত্রণালয় দায়ী?", "Agriculture",
     "কৃষি মন্ত্রণালয়ের বার্ষিক প্রতিবেদন ২০১৮-১৯ (কমপ্রেসড)_C1275", "extract_office_authority"),
    ("Q17", "রাসায়নিক সার আমদানির অনুমতি কোন মন্ত্রণালয় দেয়?", "Agriculture",
     "Chemical Fertilizer (Control) Order, 1999_C0075", "extract_office_authority"),
    ("Q18", "চা-শ্রমিক খাদ্য সহায়তার আবেদন কোথায় জমা দিতে হয়?", "Social Welfare",
     "SW_Tea Workers_2013_00_Policy_v1_C0011", "extract_office_authority"),
    ("Q19", "বেদে দলিত হরিজন ভাতা কোন অধিদপ্তর বাস্তবায়ন করে?", "Social Welfare",
     "SW_DEPR_2025_05_Policy_v1_C0006", "extract_office_authority"),
    ("Q20", "বিধবা ভাতা কোন মন্ত্রণালয় প্রদান করে?", "Social Welfare",
     "SociaMin_Widow_2025_09_25_Gazette_v1_C0008", "extract_office_authority"),
    ("Q21", "পরিবার কার্ড বাস্তবায়ন কোন অধিদপ্তর করে?", "Social Welfare",
     "SW_FC_2015_06_23_Circular_v1_C0011", "extract_office_authority"),
    ("Q22", "২০২১ সার সংশোধন বিধিমালা প্রণয়ন কোন মন্ত্রণালয় করে?", "Agriculture",
     "সার (ব্যবস্থাপনা) (সংশোধন) বিধিমালা- ২০২১ (খসড়া)_C0001", "extract_office_authority"),
    ("Q23", "বীজ ডিলার নিবন্ধন কোন কর্তৃপক্ষ করে?", "Agriculture",
     "বীজ ডিলার নিবন্ধন ও নবায়ন_C0011", "extract_office_authority"),
    ("Q24", "২০২৩ কৃষি প্রতিবেদন কোন মন্ত্রণালয়ের?", "Agriculture",
     "কৃষি মন্ত্রণালয়ের বার্ষিক প্রতিবেদন ২০২৩-২৪ (কমপ্রেসড)_C0001", "extract_office_authority"),
    ("Q25", "পিতা-মাতা পরিচর্যা কেন্দ্র কোন মন্ত্রণালয়ের অধীন?", "Social Welfare",
     "SW_PM_2017_00_Policy_v1_C0008", "extract_office_authority"),

    # Deadline date
    ("Q26", "সার আমদানি অনুমতির মেয়াদ কতদিন?", "Agriculture",
     "Chemical Fertilizer (Control) Order, 1999_C0089", "extract_deadline_date"),
    ("Q27", "২০১১ সালের ঘূর্ণিঝড় আশ্রয়কেন্দ্র নীতিমালা কোন তারিখে প্রকাশিত?", "Disaster Management",
     "ঘূর্ণিঝড় আশ্রয়কেন্দ্র নির্মাণ নীতিমালা-২০১১_C0001", "extract_deadline_date"),
    ("Q28", "চা-শ্রমিক ওয়েবপেজ কবে হালনাগাদ হয়েছে?", "Social Welfare",
     "SW_Tea Workers_2013_00_Policy_webpage_C0009", "extract_deadline_date"),
    ("Q29", "কৃষি প্রতিবেদন ২০২৪-২৫ কোন অর্থবছরের?", "Agriculture",
     "কৃষি মন্ত্রণালয়ের বার্ষিক প্রতিবেদন ২০২৪-২৫ (কমপ্রেসড)_C0075", "extract_deadline_date"),
    ("Q30", "কৃষি প্রতিবেদন ২০১৭-১৮ কোন অর্থবছরের?", "Agriculture",
     "কৃষি মন্ত্রণালয়ের বার্ষিক প্রতিবেদন ২০১৭-১৮_C0087", "extract_deadline_date"),
    ("Q31", "২০০৯ চা-শ্রমিক নীতিমালা কোন তারিখে প্রকাশিত?", "Social Welfare",
     "SW_Tea Workers_2013_00_Policy_v1_C0001", "extract_deadline_date"),
    ("Q32", "বীজ ডিলার নিবন্ধন সংশোধনের সময় সীমা কতদিন?", "Agriculture",
     "বীজ ডিলার নিবন্ধন ও নবায়ন_C0013", "extract_deadline_date"),
    ("Q33", "বীজ ডিলার লাইসেন্স নবায়নের মেয়াদ কতদিন?", "Agriculture",
     "বীজ ডিলার নিবন্ধন ও নবায়ন_C0022", "extract_deadline_date"),

    # Frequency
    ("Q34", "চা-শ্রমিক খাদ্য সহায়তা কত বার প্রদান করা হয়?", "Social Welfare",
     "SW_Tea Workers_2013_00_Policy_v1_C0012", "extract_frequency"),
    ("Q35", "২০২৪ বিধবা সার্কুলারে ভাতা প্রদান কেমন?", "Social Welfare",
     "SW_old_widow_2024_11_Circular_v1_C0038", "extract_frequency"),
    ("Q36", "পরিবার কার্ডে সহায়তা কীভাবে প্রদান করা হয়?", "Social Welfare",
     "SW_FC_2015_06_23_Circular_v1_C0022", "extract_frequency"),
    ("Q37", "কৃষি প্রতিবেদন কতবার প্রকাশিত হয়?", "Agriculture",
     "কৃষি মন্ত্রণালয়ের বার্ষিক প্রতিবেদন ২০১৭-১৮_C0001", "extract_frequency"),
    ("Q38", "দুর্যোগ ব্যবস্থাপনা কমিটি কতবার বসে?", "Disaster Management",
     "দুর্যোগ ব্যবস্থাপনা স্থায়ী আদেশাবলী-২০১৯ (বাংলা ভার্সন-চুড়ান্ত)_C0044", "extract_frequency"),

    # Duration
    ("Q39", "২০২১ সার সংশোধন বিধিমালা অনুযায়ী ডিলার নিবন্ধন কতদিনে হয়?", "Agriculture",
     "সার (ব্যবস্থাপনা) (সংশোধন) বিধিমালা- ২০২১ (খসড়া)_C0018", "extract_duration_period"),
    ("Q40", "বীজ ডিলার নিবন্ধন প্রক্রিয়ার সময়সীমা কী?", "Agriculture",
     "বীজ ডিলার নিবন্ধন ও নবায়ন_C0022", "extract_duration_period"),
    ("Q41", "২০০৯ সার নীতিমালা অনুযায়ী কতদিনে ডিলার নিয়োগ?", "Agriculture",
     "সার ডিলার নিয়োগ ও সার বিতরণ সংক্রান্ত সমন্বিত নীতিমালা-২০০৯_C0018", "extract_duration_period"),
    ("Q42", "সার আমদানি নিবন্ধনের মেয়াদ কতদিন?", "Agriculture",
     "Chemical Fertilizer (Control) Order, 1999_C0093", "extract_duration_period"),
    ("Q43", "২০২৩ খসড়া সার বিধিমালা অনুযায়ী প্রক্রিয়ার মেয়াদ?", "Agriculture",
     "খসড়া সার (ব্যবস্থাপনা) বিধিমালা ২০২৩_C0016", "extract_duration_period"),

    # Penalty
    ("Q44", "সার ব্যবসায় আইন লঙ্ঘনের জরিমানা কত?", "Agriculture",
     "Chemical Fertilizer (Control) Order, 1999_C0134", "extract_penalty_fine"),
    ("Q45", "সার লাইসেন্স নিয়ম লঙ্ঘনে সর্বনিম্ন জরিমানা কত?", "Agriculture",
     "Chemical Fertilizer (Control) Order, 1999_C0136", "extract_penalty_fine"),
    ("Q46", "সার আইন লঙ্ঘনে সর্বোচ্চ জরিমানা কত?", "Agriculture",
     "Chemical Fertilizer (Control) Order, 1999_C0139", "extract_penalty_fine"),
    ("Q47", "বীজ ডিলার নিয়ম ভঙ্গের শাস্তি কী?", "Agriculture",
     "বীজ ডিলার নিবন্ধন ও নবায়ন_C0038", "extract_penalty_fine"),
    ("Q48", "সার ব্যবসায় গুরুতর অপরাধের শাস্তি কী?", "Agriculture",
     "Chemical Fertilizer (Control) Order, 1999_C0142", "extract_penalty_fine"),
    ("Q49", "২০২১ সার সংশোধন বিধিমালা অনুযায়ী শাস্তি কী?", "Agriculture",
     "সার (ব্যবস্থাপনা) (সংশোধন) বিধিমালা- ২০২১ (খসড়া)_C0022", "extract_penalty_fine"),
    ("Q50", "২০০৯ সার নীতিমালায় শাস্তির পরিমাণ কী?", "Agriculture",
     "সার ডিলার নিয়োগ ও সার বিতরণ সংক্রান্ত সমন্বিত নীতিমালা-২০০৯_C0022", "extract_penalty_fine"),
]

r = HybridRetriever()

print(f"{'ID':<5} {'expected match':<40} {'extractor fired':<25}")
print("-" * 100)

correct = 0
partial = 0
missed  = 0

for qid, q, ministry, expected_id, expected_extractor in QUESTIONS:
    intents = detect_intents(q)
    results = two_stage_search(
        retriever=r, question=q, intents=intents,
        extractors_for_intent=EXTRACTORS_FOR_INTENT, ministry=ministry,
    )
    if not results:
        print(f"{qid:<5} NO RESULTS")
        missed += 1
        continue

    top = results[0]
    top_id = top["id"]
    extracted = top.get("extracted", {})

    id_match = top_id == expected_id
    ext_fired = expected_extractor in extracted

    if id_match and ext_fired:
        correct += 1
        status = "OK"
    elif ext_fired:
        partial += 1
        status = "wrong doc, right extractor"
    else:
        missed += 1
        status = "MISS"

    print(f"{qid:<5} {status:<40} intents={intents}")
    if not id_match:
        print(f"       expected: {expected_id[:70]}")
        print(f"       got:      {top_id[:70]}")

print(f"\nCorrect (id + extractor): {correct}/{len(QUESTIONS)}")
print(f"Partial (extractor only): {partial}/{len(QUESTIONS)}")
print(f"Missed:                   {missed}/{len(QUESTIONS)}")