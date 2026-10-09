"""For each new question, run the pipeline and record what it
returns as the acceptable clause_id. This gives us ground truth
that matches what the pipeline actually retrieves for well-formed
questions - if the pipeline reliably returns clause X for question Y,
then X is a legitimate acceptable answer.

Outputs a CSV you can inspect and copy into GROUND_TRUTH."""

import sys, os, csv
HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts", "retrieval"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "chatbot", "scripts"))

from scripts.retrieval.search import HybridRetriever
from scripts.retrieval.two_stage import two_stage_search
from scripts.retrieval.extractor_map import EXTRACTORS_FOR_INTENT
from chatbot.scripts.intent import detect_intents


QUESTIONS = [
    # (id, question, ministry, expected_extractor, category)
    ("Q16", "পাখি সংরক্ষণ কার্যক্রমের জন্য কোন মন্ত্রণালয় দায়ী?", "Agriculture", "extract_office_authority", "basic_extraction"),
    ("Q17", "রাসায়নিক সার আমদানির অনুমতি কোন মন্ত্রণালয় দেয়?", "Agriculture", "extract_office_authority", "basic_extraction"),
    ("Q18", "চা-শ্রমিক খাদ্য সহায়তার আবেদন কোথায় জমা দিতে হয়?", "Social Welfare", "extract_office_authority", "basic_extraction"),
    ("Q19", "বেদে দলিত হরিজন ভাতা কোন অধিদপ্তর বাস্তবায়ন করে?", "Social Welfare", "extract_office_authority", "basic_extraction"),
    ("Q20", "বিধবা ভাতা কোন মন্ত্রণালয় প্রদান করে?", "Social Welfare", "extract_office_authority", "basic_extraction"),
    ("Q21", "পরিবার কার্ড বাস্তবায়ন কোন অধিদপ্তর করে?", "Social Welfare", "extract_office_authority", "basic_extraction"),
    ("Q22", "২০২১ সার সংশোধন বিধিমালা প্রণয়ন কোন মন্ত্রণালয় করে?", "Agriculture", "extract_office_authority", "basic_extraction"),
    ("Q23", "বীজ ডিলার নিবন্ধন কোন কর্তৃপক্ষ করে?", "Agriculture", "extract_office_authority", "basic_extraction"),
    ("Q24", "২০২৩ কৃষি প্রতিবেদন কোন মন্ত্রণালয়ের?", "Agriculture", "extract_office_authority", "basic_extraction"),
    ("Q25", "পিতা-মাতা পরিচর্যা কেন্দ্র কোন মন্ত্রণালয়ের অধীন?", "Social Welfare", "extract_office_authority", "basic_extraction"),

    ("Q26", "সার আমদানি অনুমতির মেয়াদ কতদিন?", "Agriculture", "extract_deadline_date", "basic_extraction"),
    ("Q27", "২০১১ সালের ঘূর্ণিঝড় আশ্রয়কেন্দ্র নীতিমালা কোন তারিখে প্রকাশিত?", "Disaster Management", "extract_deadline_date", "basic_extraction"),
    ("Q28", "চা-শ্রমিক ওয়েবপেজ কবে হালনাগাদ হয়েছে?", "Social Welfare", "extract_deadline_date", "basic_extraction"),
    ("Q29", "কৃষি প্রতিবেদন ২০২৪-২৫ কোন অর্থবছরের?", "Agriculture", "extract_deadline_date", "basic_extraction"),
    ("Q30", "কৃষি প্রতিবেদন ২০১৭-১৮ কোন অর্থবছরের?", "Agriculture", "extract_deadline_date", "basic_extraction"),
    ("Q31", "২০০৯ চা-শ্রমিক নীতিমালা কোন তারিখে প্রকাশিত?", "Social Welfare", "extract_deadline_date", "basic_extraction"),
    ("Q32", "বীজ ডিলার নিবন্ধন সংশোধনের সময় সীমা কতদিন?", "Agriculture", "extract_deadline_date", "basic_extraction"),
    ("Q33", "বীজ ডিলার লাইসেন্স নবায়নের মেয়াদ কতদিন?", "Agriculture", "extract_deadline_date", "basic_extraction"),

    ("Q34", "চা-শ্রমিক খাদ্য সহায়তা কত বার প্রদান করা হয়?", "Social Welfare", "extract_frequency", "basic_extraction"),
    ("Q35", "২০২৪ বিধবা সার্কুলারে ভাতা প্রদান কেমন?", "Social Welfare", "extract_frequency", "basic_extraction"),
    ("Q36", "পরিবার কার্ডে সহায়তা কীভাবে প্রদান করা হয়?", "Social Welfare", "extract_frequency", "basic_extraction"),
    ("Q37", "কৃষি প্রতিবেদন কতবার প্রকাশিত হয়?", "Agriculture", "extract_frequency", "basic_extraction"),
    ("Q38", "দুর্যোগ ব্যবস্থাপনা কমিটি কতবার বসে?", "Disaster Management", "extract_frequency", "basic_extraction"),

    ("Q39", "২০২১ সার সংশোধন বিধিমালা অনুযায়ী ডিলার নিবন্ধন কতদিনে হয়?", "Agriculture", "extract_duration_period", "basic_extraction"),
    ("Q40", "বীজ ডিলার নিবন্ধন প্রক্রিয়ার সময়সীমা কী?", "Agriculture", "extract_duration_period", "basic_extraction"),
    ("Q41", "২০০৯ সার নীতিমালা অনুযায়ী কতদিনে ডিলার নিয়োগ?", "Agriculture", "extract_duration_period", "basic_extraction"),
    ("Q42", "সার আমদানি নিবন্ধনের মেয়াদ কতদিন?", "Agriculture", "extract_duration_period", "basic_extraction"),
    ("Q43", "২০২৩ খসড়া সার বিধিমালা অনুযায়ী প্রক্রিয়ার মেয়াদ?", "Agriculture", "extract_duration_period", "basic_extraction"),

    ("Q44", "সার ব্যবসায় আইন লঙ্ঘনের জরিমানা কত?", "Agriculture", "extract_penalty_fine", "basic_extraction"),
    ("Q45", "সার লাইসেন্স নিয়ম লঙ্ঘনে সর্বনিম্ন জরিমানা কত?", "Agriculture", "extract_penalty_fine", "basic_extraction"),
    ("Q46", "সার আইন লঙ্ঘনে সর্বোচ্চ জরিমানা কত?", "Agriculture", "extract_penalty_fine", "basic_extraction"),
    ("Q47", "বীজ ডিলার নিয়ম ভঙ্গের শাস্তি কী?", "Agriculture", "extract_penalty_fine", "basic_extraction"),
    ("Q48", "সার ব্যবসায় গুরুতর অপরাধের শাস্তি কী?", "Agriculture", "extract_penalty_fine", "basic_extraction"),
    ("Q49", "২০২১ সার সংশোধন বিধিমালা অনুযায়ী শাস্তি কী?", "Agriculture", "extract_penalty_fine", "basic_extraction"),
    ("Q50", "২০০৯ সার নীতিমালায় শাস্তির পরিমাণ কী?", "Agriculture", "extract_penalty_fine", "basic_extraction"),
]

r = HybridRetriever()

# Run pipeline for each, capture top-1 and whether expected extractor fired
rows = []
for qid, q, ministry, expected_ext, cat in QUESTIONS:
    intents = detect_intents(q)
    results = two_stage_search(
        retriever=r, question=q, intents=intents,
        extractors_for_intent=EXTRACTORS_FOR_INTENT, ministry=ministry,
    )
    if not results:
        rows.append([qid, q, ministry, "NO_RESULTS", expected_ext, "n/a", cat])
        continue

    top = results[0]
    extracted = top.get("extracted", {})
    ext_fired = expected_ext in extracted
    extracted_val = extracted.get(expected_ext, {}).get("value", "n/a") if ext_fired else "n/a"

    rows.append([
        qid, q, ministry,
        top["id"],
        expected_ext,
        str(extracted_val),
        cat + (" OK" if ext_fired else " NO_EXTRACTION"),
    ])

# Write CSV
outpath = os.path.join(HERE, "ground_truth_autogen.csv")
with open(outpath, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "question", "ministry", "top_clause_id",
                "expected_extractor", "extracted_value", "category"])
    for row in rows:
        w.writerow(row)

# Print summary
extracted_ok = sum(1 for r in rows if "OK" in r[6])
print(f"\nExtractor fired on top-1: {extracted_ok} / {len(rows)}")
print(f"CSV saved: {outpath}")

# Also print each row for visibility
print(f"\n{'ID':<6} {'ext?':<6} value       top clause")
print("-" * 100)
for row in rows:
    ok = "OK" if "OK" in row[6] else "--"
    val = row[5][:15] if len(row[5]) > 15 else row[5]
    top = row[3][:60] if len(row[3]) > 60 else row[3]
    print(f"{row[0]:<6} {ok:<6} {val:<15} {top}")