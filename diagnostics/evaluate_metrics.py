"""Full evaluation on 15 curated ground-truth questions.

Reports four industry-standard metrics + one extraction-specific:

  Recall@k    Did stage-1 retrieval reach the correct clause within
              top-k, before any two-stage re-ranking? Tests the
              retrieval ceiling. If Recall@100 is low, no amount of
              re-ranking helps.

  MRR         Mean Reciprocal Rank. For each question, 1/(rank of
              first acceptable clause). Rewards top positions
              heavily. Standard IR metric expected in the paper.

  Hit@k       Did an acceptable clause appear in the top-k results
              after two-stage re-ranking? Reflects what the user
              actually sees. Hit@1 is the strictest, Hit@5 the
              most permissive.

  Extraction  For questions where top-1 was correct, did the
   Accuracy   extractor pull the right value? Separates NER
              quality from retrieval quality.

Bilingual questions (Q8-Q10) run English input through the
translator before evaluation - same path as the live system.
Low-confidence questions (Q14, Q15) are evaluated with looser
criteria: any DM ministry clause counts as PASS.
"""

import sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts", "retrieval"))
sys.path.insert(0, os.path.join(HERE, "..", "chatbot", "scripts"))

from scripts.retrieval.search        import HybridRetriever
from scripts.retrieval.translator    import Translator
from scripts.retrieval.two_stage     import two_stage_search
from scripts.retrieval.extractor_map import EXTRACTORS_FOR_INTENT
from chatbot.scripts.intent        import detect_intents


# ---------------------------------------------------------------
# Ground truth for all 15 questions.
# expected_value is the string the extractor should return (or
# a list of acceptable strings when multiple documents give
# different-but-both-valid answers, e.g. tea worker 36k vs 48k).
# ---------------------------------------------------------------

GROUND_TRUTH = [
    # ---- Q1-Q3: age extraction ----
    {
        "id":               "Q1",
        "question":         "বয়স্ক ভাতা পেতে সর্বনিম্ন বয়স কত হতে হবে?",
        "ministry":         "Social Welfare",
        "acceptable_ids":   [
            "SocialMin_OldAgeAll_2013_00_Policy_v1.pdf_C0006",
            "SocialMin_OldAgeAll_2013_00_Policy_v1.pdf_C0009",
        ],
        "expected_value":   "65",
        "expected_extractor":"extract_age",
    },
    {
        "id":               "Q2",
        "question":         "বেদে, দলিত ও হরিজন ভাতার জন্য সর্বনিম্ন বয়স কত?",
        "ministry":         "Social Welfare",
        "acceptable_ids":   [
            "SW_DEPR_Bede, Dalit, AND Harijan_2013_00_Policy_v3_C0032",
        ],
        "expected_value":   "50",
        "expected_extractor":"extract_age",
    },
    {
        "id":               "Q3",
        "question":         "চা-শ্রমিক কল্যাণে সর্বনিম্ন বয়স কত?",
        "ministry":         "Social Welfare",
        "acceptable_ids":   [
            "SW_Tea Workers_2013_00_Policy_v1_C0007",
        ],
        "expected_value":   "18",
        "expected_extractor":"extract_age",
    },
    # ---- Q4-Q6: income extraction ----
    {
        "id":               "Q4",
        "question":         "বেদে, দলিত ও হরিজন সম্প্রদায়ের ভাতার জন্য প্রার্থীর বার্ষিক আয়সীমা কত?",
        "ministry":         "Social Welfare",
        "acceptable_ids":   [
            "SW_DEPR_Bede, Dalit, AND Harijan_2013_00_Policy_v3_C0033",
        ],
        "expected_value":   "36,000",
        "expected_extractor":"extract_income_limit",
    },
    {
        "id":               "Q5",
        "question":         "বিধবা ভাতা পেতে প্রার্থীর বার্ষিক আয়সীমা কত?",
        "ministry":         "Social Welfare",
        "acceptable_ids":   [
            "SociaMin_Widow_2025_09_25_Gazette_v1_C0016",
            "SociaMin_Widow_2025_09_25_webpage_v1_C0014",
        ],
        "expected_value":   "15,000",
        "expected_extractor":"extract_income_limit",
    },
    {
        "id":               "Q6",
        "question":         "চা-শ্রমিক ভাতার প্রার্থীর বার্ষিক আয়সীমা কত?",
        "ministry":         "Social Welfare",
        "acceptable_ids":   [
            "SW_Tea Workers_2013_00_Policy_v1_C0007",
            "SW_Tea Workers_2013_00_Policy_webpage_C0008",
        ],
        # Contradiction bridge: both values acceptable
        "expected_value":   ["36,000", "48,000"],
        "expected_extractor":"extract_income_limit",
    },
    # ---- Q7-Q11: document requirements ----
    {
        "id":               "Q7",
        "question":         "সার উৎপাদনকারী হিসেবে নিবন্ধনের জন্য কী কী কাগজপত্র প্রয়োজন?",
        "ministry":         "Agriculture",
        "acceptable_ids":   [
            "013-057_C0016",
            "খসড়া সার (ব্যবস্থাপনা) বিধিমালা ২০২৩_C0069",
            "সার (ব্যবস্থাপনা) (সংশোধন) বিধিমালা- ২০২১ (খসড়া)_C0010",
        ],
        "expected_value":   None,        # any list is acceptable
        "expected_extractor":"extract_document_requirements",
    },
    {
        "id":               "Q8-doc",
        "question":         "সার ডিলার নিয়োগের জন্য কোন কাগজপত্র লাগে?",
        "ministry":         "Agriculture",
        "acceptable_ids":   [
            "সার ডিলার নিয়োগ ও সার বিতরণ সংক্রান্ত সমন্বিত নীতিমালা-২০২৫_C0007",
        ],
        "expected_value":   None,
        "expected_extractor":"extract_document_requirements",
    },
    {
        "id":               "Q9-doc",
        "question":         "বীজ ডিলার নিবন্ধনের জন্য কী প্রয়োজন?",
        "ministry":         "Agriculture",
        "acceptable_ids":   [
            "বীজ বিধিমালা-২০২০_C0023",
            "বীজ ডিলার নিবন্ধন ও নবায়ন_C0018",
        ],
        "expected_value":   None,
        "expected_extractor":"extract_document_requirements",
    },
    {
        "id":               "Q10-doc",
        "question":         "পিতা-মাতা পরিচর্যা কেন্দ্র প্রতিষ্ঠার জন্য কী কাগজপত্র প্রয়োজন?",
        "ministry":         "Social Welfare",
        "acceptable_ids":   [
            "SW_PM_2017_00_Policy_v1_C0017",
        ],
        "expected_value":   None,
        "expected_extractor":"extract_document_requirements",
    },
    {
        "id":               "Q11-doc",
        "question":         "সার ব্যবস্থাপনা সংশোধন বিধিমালা ২০২১ অনুযায়ী নিবন্ধনের কাগজপত্র কী?",
        "ministry":         "Agriculture",
        "acceptable_ids":   [
            "সার (ব্যবস্থাপনা) (সংশোধন) বিধিমালা- ২০২১ (খসড়া)_C0007",
        ],
        "expected_value":   None,
        "expected_extractor":"extract_document_requirements",
    },
    # ---- Q12-Q14: bilingual (English -> Bengali) ----
    {
        "id":               "Q12-en",
        "question":         "What is the minimum age for Old Age Allowance?",
        "ministry":         "Social Welfare",
        "acceptable_ids":   [
            "SocialMin_OldAgeAll_2013_00_Policy_v1.pdf_C0006",
            "SocialMin_OldAgeAll_2013_00_Policy_v1.pdf_C0009",
        ],
        "expected_value":   "65",
        "expected_extractor":"extract_age",
        "translate":        True,
    },
    {
        "id":               "Q13-en",
        "question":         "What is the minimum age and annual income limit for widow allowance?",
        "ministry":         "Social Welfare",
        "acceptable_ids":   [
            "SociaMin_Widow_2025_09_25_Gazette_v1_C0014",
            "SociaMin_Widow_2025_09_25_Gazette_v1_C0016",
        ],
        # Multi-intent: accepts either 18 (age) or 15,000 (income)
        "expected_value":   ["18", "15,000"],
        "expected_extractor":None,       # skip strict extraction check
        "translate":        True,
    },
    {
        "id":               "Q14-en",
        "question":         "What documents are needed to register as a fertilizer dealer?",
        "ministry":         "Agriculture",
        "acceptable_ids":   [
            "খসড়া সার (ব্যবস্থাপনা) বিধিমালা ২০২৩_C0044",
            "খসড়া সার (ব্যবস্থাপনা) বিধিমালা ২০২৩_C0069",
            "সার (ব্যবস্থাপনা) (সংশোধন) বিধিমালা- ২০২১ (খসড়া)_C0017",
        ],
        "expected_value":   None,
        "expected_extractor":"extract_document_requirements",
        "translate":        True,
    },
    # ---- Q15: DM low-confidence deferral ----
    {
        "id":               "Q15-dm",
        "question":         "দুর্যোগ ব্যবস্থাপনা কমিটি গঠনের নিয়ম কী?",
        "ministry":         "Disaster Management",
        "acceptable_ids":   [],           # any DM clause accepted
        "expected_value":   None,
        "expected_extractor":None,
        "low_confidence":   True,
    },
]


# ---------------------------------------------------------------
# Metric computation
# ---------------------------------------------------------------

def recall_at_k(retriever, question, ministry, acceptable_ids, k):
    """Stage-1 raw retrieval. Was any acceptable_id in the top-k?"""
    results = retriever.search(question, top_k=k, ministry=ministry)
    returned = {r["id"] for r in results}
    return bool(returned & set(acceptable_ids))


def rank_of_first_hit(results, acceptable_ids):
    """1-indexed rank of the first acceptable clause. None if not
    found in the returned results."""
    for i, r in enumerate(results, 1):
        if r["id"] in acceptable_ids:
            return i
    return None


def check_extracted_value(extracted, expected_extractor, expected_value):
    """Does the top-1 extraction match the expected value?"""
    if expected_extractor is None or expected_value is None:
        return None       # not checked for this question

    if expected_extractor not in extracted:
        return False

    actual = extracted[expected_extractor].get("value")
    if isinstance(actual, list):
        actual_str = ",".join(str(x) for x in actual)
    else:
        actual_str = str(actual)
    actual_norm = actual_str.replace(",", "").replace(" ", "")

    if isinstance(expected_value, list):
        return any(
            e.replace(",", "").replace(" ", "") in actual_norm
            for e in expected_value
        )
    expected_norm = str(expected_value).replace(",", "").replace(" ", "")
    return expected_norm in actual_norm


# ---------------------------------------------------------------
# Main
# ---------------------------------------------------------------

def main():
    print("[startup] loading retriever ...")
    r = HybridRetriever()
    tr = Translator()
    print("[startup] ready\n")

    per_q = []

    for tc in GROUND_TRUTH:
        question = tc["question"]
        # Translate if English
        if tc.get("translate"):
            translated = tr.to_bengali(question)
        else:
            translated = question

        intents = detect_intents(translated)

        # --- Stage-1 recall metrics (no re-ranking) ---
        r10  = recall_at_k(r, translated, tc["ministry"],
                           tc["acceptable_ids"], 10)  if tc["acceptable_ids"] else None
        r50  = recall_at_k(r, translated, tc["ministry"],
                           tc["acceptable_ids"], 50)  if tc["acceptable_ids"] else None
        r100 = recall_at_k(r, translated, tc["ministry"],
                           tc["acceptable_ids"], 100) if tc["acceptable_ids"] else None

        # --- Full pipeline for MRR, Hit@k, extraction ---
        results = two_stage_search(
            retriever             = r,
            question              = translated,
            intents               = intents,
            extractors_for_intent = EXTRACTORS_FOR_INTENT,
            ministry              = tc["ministry"],
            return_k              = 10,
        )

        if tc.get("low_confidence"):
            # PASS if we got a DM clause tagged low-confidence
            top = results[0] if results else None
            hit1 = (top is not None
                    and top.get("confidence_tier") == "low"
                    and top.get("ministry") == tc["ministry"])
            hit3 = hit1
            hit5 = hit1
            rank = 1 if hit1 else None
            extraction_ok = None
        elif tc["acceptable_ids"]:
            rank = rank_of_first_hit(results, tc["acceptable_ids"])
            hit1 = rank == 1
            hit3 = rank is not None and rank <= 3
            hit5 = rank is not None and rank <= 5

            if hit1:
                top_extracted = results[0].get("extracted", {})
                extraction_ok = check_extracted_value(
                    top_extracted,
                    tc.get("expected_extractor"),
                    tc.get("expected_value"),
                )
            else:
                extraction_ok = None
        else:
            hit1 = hit3 = hit5 = False
            rank = None
            extraction_ok = None

        rr = 1.0 / rank if rank else 0.0

        per_q.append({
            "id":            tc["id"],
            "question":      tc["question"][:55],
            "rank":          rank,
            "hit1":          hit1,
            "hit3":          hit3,
            "hit5":          hit5,
            "reciprocal":    rr,
            "r10":           r10,
            "r50":           r50,
            "r100":          r100,
            "extraction_ok": extraction_ok,
        })

    # --- Print per-question table ---
    print(f"{'ID':<10} {'rank':>5} {'Hit@1':>6} {'Hit@3':>6} {'Hit@5':>6} "
          f"{'R@10':>5} {'R@100':>6} {'extract':>8}   question")
    print("-" * 120)
    for q in per_q:
        print(
            f"{q['id']:<10} "
            f"{str(q['rank']):>5} "
            f"{str(q['hit1']):>6} "
            f"{str(q['hit3']):>6} "
            f"{str(q['hit5']):>6} "
            f"{str(q['r10']):>5} "
            f"{str(q['r100']):>6} "
            f"{str(q['extraction_ok']):>8}   "
            f"{q['question']}"
        )

    # --- Aggregate metrics ---
    n = len(per_q)

    # Recall computed only on questions with acceptable_ids
    with_ids = [q for q in per_q if q["r10"] is not None]
    n_ids    = len(with_ids)

    print()
    print("=" * 60)
    print("  AGGREGATE METRICS")
    print("=" * 60)
    print(f"  Questions evaluated:        {n}")
    print()

    if n_ids:
        r10_rate  = sum(1 for q in with_ids if q["r10"])  / n_ids
        r50_rate  = sum(1 for q in with_ids if q["r50"])  / n_ids
        r100_rate = sum(1 for q in with_ids if q["r100"]) / n_ids
        print(f"  Recall@10:                  {r10_rate :.3f}   ({n_ids} questions)")
        print(f"  Recall@50:                  {r50_rate :.3f}")
        print(f"  Recall@100:                 {r100_rate:.3f}")

    mrr = sum(q["reciprocal"] for q in per_q) / n
    print(f"\n  MRR:                        {mrr:.3f}")

    hit1_rate = sum(1 for q in per_q if q["hit1"]) / n
    hit3_rate = sum(1 for q in per_q if q["hit3"]) / n
    hit5_rate = sum(1 for q in per_q if q["hit5"]) / n
    print(f"\n  Hit@1 (strict top-1):       {hit1_rate:.3f}   ({sum(1 for q in per_q if q['hit1'])}/{n})")
    print(f"  Hit@3:                      {hit3_rate:.3f}   ({sum(1 for q in per_q if q['hit3'])}/{n})")
    print(f"  Hit@5:                      {hit5_rate:.3f}   ({sum(1 for q in per_q if q['hit5'])}/{n})")

    ext_checked = [q for q in per_q if q["extraction_ok"] is not None]
    if ext_checked:
        ext_ok = sum(1 for q in ext_checked if q["extraction_ok"])
        print(f"\n  Extraction Accuracy:        {ext_ok/len(ext_checked):.3f}   "
              f"({ext_ok}/{len(ext_checked)} on top-1 correct retrievals)")


if __name__ == "__main__":
    main()