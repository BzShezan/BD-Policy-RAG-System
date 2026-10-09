"""Baseline comparison / ablation study for Unmochon.

Runs the same 15-question ground truth through four progressive
configurations to isolate the contribution of each pipeline layer:

  Row 1: BM25 only              (lexical baseline)
  Row 2: Dense only             (semantic baseline)
  Row 3: BM25 + Dense + RRF     (vanilla RAG - no re-ranking)
  Row 4: Full Unmochon          (two-stage + extractor re-rank)

Reports MRR, Hit@1, and average latency per config so the trade-off
between accuracy and speed is visible in one table. Also prints a
per-question win/loss breakdown to avoid overclaiming small deltas
on n=15.
"""

import sys, os, time
HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts", "retrieval"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "chatbot", "scripts"))

from scripts.retrieval.search        import HybridRetriever
from scripts.retrieval.translator    import Translator
from scripts.retrieval.two_stage     import two_stage_search
from scripts.retrieval.extractor_map import EXTRACTORS_FOR_INTENT
from chatbot.scripts.intent        import detect_intents


# Same 15 questions used in the main evaluation
GROUND_TRUTH = [
    ("Q1",  "বয়স্ক ভাতা পেতে সর্বনিম্ন বয়স কত হতে হবে?", "Social Welfare",
     ["SocialMin_OldAgeAll_2013_00_Policy_v1.pdf_C0006",
      "SocialMin_OldAgeAll_2013_00_Policy_v1.pdf_C0009"], False),
    ("Q2",  "বেদে, দলিত ও হরিজন ভাতার জন্য সর্বনিম্ন বয়স কত?", "Social Welfare",
     ["SW_DEPR_Bede, Dalit, AND Harijan_2013_00_Policy_v3_C0032"], False),
    ("Q3",  "চা-শ্রমিক কল্যাণে সর্বনিম্ন বয়স কত?", "Social Welfare",
     ["SW_Tea Workers_2013_00_Policy_v1_C0007"], False),
    ("Q4",  "বেদে, দলিত ও হরিজন সম্প্রদায়ের ভাতার জন্য প্রার্থীর বার্ষিক আয়সীমা কত?", "Social Welfare",
     ["SW_DEPR_Bede, Dalit, AND Harijan_2013_00_Policy_v3_C0033"], False),
    ("Q5",  "বিধবা ভাতা পেতে প্রার্থীর বার্ষিক আয়সীমা কত?", "Social Welfare",
     ["SociaMin_Widow_2025_09_25_Gazette_v1_C0016",
      "SociaMin_Widow_2025_09_25_webpage_v1_C0014"], False),
    ("Q6",  "চা-শ্রমিক ভাতার প্রার্থীর বার্ষিক আয়সীমা কত?", "Social Welfare",
     ["SW_Tea Workers_2013_00_Policy_v1_C0007",
      "SW_Tea Workers_2013_00_Policy_webpage_C0008"], False),
    ("Q7",  "সার উৎপাদনকারী হিসেবে নিবন্ধনের জন্য কী কী কাগজপত্র প্রয়োজন?", "Agriculture",
     ["013-057_C0016",
      "খসড়া সার (ব্যবস্থাপনা) বিধিমালা ২০২৩_C0069",
      "সার (ব্যবস্থাপনা) (সংশোধন) বিধিমালা- ২০২১ (খসড়া)_C0010"], False),
    ("Q8",  "সার ডিলার নিয়োগের জন্য কোন কাগজপত্র লাগে?", "Agriculture",
     ["সার ডিলার নিয়োগ ও সার বিতরণ সংক্রান্ত সমন্বিত নীতিমালা-২০২৫_C0007"], False),
    ("Q9",  "বীজ ডিলার নিবন্ধনের জন্য কী প্রয়োজন?", "Agriculture",
     ["বীজ বিধিমালা-২০২০_C0023", "বীজ ডিলার নিবন্ধন ও নবায়ন_C0018"], False),
    ("Q10", "পিতা-মাতা পরিচর্যা কেন্দ্র প্রতিষ্ঠার জন্য কী কাগজপত্র প্রয়োজন?", "Social Welfare",
     ["SW_PM_2017_00_Policy_v1_C0017"], False),
    ("Q11", "সার ব্যবস্থাপনা সংশোধন বিধিমালা ২০২১ অনুযায়ী নিবন্ধনের কাগজপত্র কী?", "Agriculture",
     ["সার (ব্যবস্থাপনা) (সংশোধন) বিধিমালা- ২০২১ (খসড়া)_C0007"], False),
    ("Q12-en", "What is the minimum age for Old Age Allowance?", "Social Welfare",
     ["SocialMin_OldAgeAll_2013_00_Policy_v1.pdf_C0006",
      "SocialMin_OldAgeAll_2013_00_Policy_v1.pdf_C0009"], True),
    ("Q13-en", "What is the minimum age and annual income limit for widow allowance?", "Social Welfare",
     ["SociaMin_Widow_2025_09_25_Gazette_v1_C0014",
      "SociaMin_Widow_2025_09_25_Gazette_v1_C0016"], True),
    ("Q14-en", "What documents are needed to register as a fertilizer dealer?", "Agriculture",
     ["খসড়া সার (ব্যবস্থাপনা) বিধিমালা ২০২৩_C0044",
      "খসড়া সার (ব্যবস্থাপনা) বিধিমালা ২০২৩_C0069"], True),
    ("Q15-dm", "দুর্যোগ ব্যবস্থাপনা কমিটি গঠনের নিয়ম কী?", "Disaster Management",
     [], False),
]


# ---------------------------------------------------------------
# Helper: build the ChromaDB `where` filter for a ministry
# ---------------------------------------------------------------
# Matches how HybridRetriever.search() builds its where clause.
# Ministry filter applied so all four configs get the same corpus
# scope (fair comparison, per requirement #2).

def _ministry_where(ministry):
    """Build the ChromaDB where filter for a ministry, or None if
    no ministry given (search everything)."""
    if not ministry:
        return None
    return {"ministry": ministry}


# ---------------------------------------------------------------
# Baseline configurations
# ---------------------------------------------------------------
# Each config takes (retriever, question, ministry) and returns
# a list of dicts each with an "id" key. Standard interface.

def config_bm25_only(retriever, question, ministry, top_k=10):
    """BM25 only - no dense embeddings, no fusion.

    Uses HybridRetriever._sparse() directly. Manually applies the
    ministry filter via _get_allowed_ids() to match how the full
    search() method scopes results."""
    where = _ministry_where(ministry)
    allowed_ids = retriever._get_allowed_ids(where) if where else None

    ids = retriever._sparse(question, k=top_k, allowed_ids=allowed_ids)
    return [{"id": cid} for cid in ids]


def config_dense_only(retriever, question, ministry, top_k=10):
    """Dense only - no BM25, no fusion."""
    where = _ministry_where(ministry)
    hits = retriever._dense(question, k=top_k, where=where)
    return [{"id": h["id"]} for h in hits]


def config_vanilla_rag(retriever, question, ministry, top_k=10):
    """BM25 + Dense fused via RRF. This is the pre-two-stage output
    of your existing HybridRetriever.search()."""
    hits = retriever.search(query=question, top_k=top_k, ministry=ministry)
    return [{"id": h["id"]} for h in hits]


def config_full_unmochon(retriever, question, ministry, top_k=10):
    """Full pipeline: hybrid + two-stage doc filter + extractor
    re-ranking + intent-aware boosting."""
    intents = detect_intents(question)
    results = two_stage_search(
        retriever=retriever, question=question, intents=intents,
        extractors_for_intent=EXTRACTORS_FOR_INTENT,
        ministry=ministry, return_k=top_k,
    )
    return [{"id": r["id"]} for r in results]


CONFIGS = [
    ("BM25 only",              config_bm25_only),
    ("Dense only",             config_dense_only),
    ("Vanilla RAG (BM25+RRF)", config_vanilla_rag),
    ("Full Unmochon",          config_full_unmochon),
]


# ---------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------

def rank_of_hit(results, acceptable_ids):
    for i, r in enumerate(results, 1):
        if r["id"] in acceptable_ids:
            return i
    return None


# ---------------------------------------------------------------
# Runner
# ---------------------------------------------------------------

def run_config(config_name, config_fn, retriever, translator):
    """Run one configuration through all 15 questions."""
    per_question = []
    latencies = []

    for qid, q, ministry, acceptable, is_english in GROUND_TRUTH:
        query = translator.to_bengali(q) if is_english else q

        t0 = time.time()
        try:
            results = config_fn(retriever, query, ministry, top_k=10)
        except Exception as e:
            print(f"    [{config_name}] {qid} FAILED: {e}")
            results = []
        elapsed = time.time() - t0
        latencies.append(elapsed)

        rank = rank_of_hit(results, acceptable) if acceptable else None
        per_question.append({
            "qid":    qid,
            "rank":   rank,
            "hit1":   rank == 1,
            "hit3":   rank is not None and rank <= 3,
            "hit5":   rank is not None and rank <= 5,
            "no_gt":  not acceptable,
        })

    scored = [p for p in per_question if not p["no_gt"]]
    n = len(scored)

    mrr  = sum(1.0/p["rank"] if p["rank"] else 0.0 for p in scored) / n if n else 0
    hit1 = sum(1 for p in scored if p["hit1"]) / n if n else 0
    hit3 = sum(1 for p in scored if p["hit3"]) / n if n else 0
    hit5 = sum(1 for p in scored if p["hit5"]) / n if n else 0
    avg_latency_ms = sum(latencies) / len(latencies) * 1000

    return {
        "name":           config_name,
        "mrr":            mrr,
        "hit1":           hit1,
        "hit3":           hit3,
        "hit5":           hit5,
        "avg_latency_ms": avg_latency_ms,
        "per_question":   per_question,
        "n":              n,
    }


def print_headline_table(results):
    print()
    print("=" * 78)
    print("  BASELINE COMPARISON - HEADLINE METRICS")
    print("=" * 78)
    print(f"  n = {results[0]['n']} questions with ground truth (pilot evaluation)")
    print()
    print(f"  {'Configuration':<28} {'MRR':>7}  {'Hit@1':>7}  {'Latency':>10}")
    print(f"  {'-'*28} {'-'*7}  {'-'*7}  {'-'*10}")
    for r in results:
        print(f"  {r['name']:<28} {r['mrr']:>7.3f}  {r['hit1']:>7.3f}  "
              f"{r['avg_latency_ms']:>7.1f} ms")


def print_full_table(results):
    print()
    print("=" * 78)
    print("  APPENDIX - ALL METRICS")
    print("=" * 78)
    print(f"  {'Configuration':<28} {'MRR':>7}  {'Hit@1':>7}  {'Hit@3':>7}  {'Hit@5':>7}")
    print(f"  {'-'*28} {'-'*7}  {'-'*7}  {'-'*7}  {'-'*7}")
    for r in results:
        print(f"  {r['name']:<28} {r['mrr']:>7.3f}  {r['hit1']:>7.3f}  "
              f"{r['hit3']:>7.3f}  {r['hit5']:>7.3f}")


def print_per_question_breakdown(results):
    print()
    print("=" * 78)
    print("  PER-QUESTION HIT@1 BREAKDOWN")
    print("=" * 78)

    header = f"  {'QID':<8} "
    for r in results:
        header += f"{r['name'][:13]:>14} "
    print(header)
    print(f"  {'-'*8} " + " ".join(["-"*14 for _ in results]))

    for i, q_row in enumerate(results[0]["per_question"]):
        qid = q_row["qid"]
        line = f"  {qid:<8} "
        for r in results:
            pq = r["per_question"][i]
            if pq["no_gt"]:
                cell = "(no GT)"
            elif pq["hit1"]:
                cell = "PASS"
            elif pq["rank"]:
                cell = f"rank={pq['rank']}"
            else:
                cell = "MISS"
            line += f"{cell:>14} "
        print(line)

    print()
    print("  Win/loss vs Full Unmochon:")
    unmochon_per_q = results[-1]["per_question"]
    for r in results[:-1]:
        wins = ties = losses = 0
        for pq_baseline, pq_unmochon in zip(r["per_question"], unmochon_per_q):
            if pq_baseline["no_gt"]:
                continue
            if pq_baseline["hit1"] and not pq_unmochon["hit1"]:
                wins += 1
            elif pq_baseline["hit1"] == pq_unmochon["hit1"]:
                ties += 1
            else:
                losses += 1
        print(f"    {r['name']:<28} "
              f"wins {wins}  ties {ties}  losses {losses}")


def main():
    print("[baseline] loading retriever and translator...")
    retriever = HybridRetriever()
    translator = Translator()
    print("[baseline] ready\n")

    results = []
    for name, fn in CONFIGS:
        print(f"[baseline] running: {name}")
        r = run_config(name, fn, retriever, translator)
        results.append(r)
        print(f"           MRR={r['mrr']:.3f}  Hit@1={r['hit1']:.3f}  "
              f"latency={r['avg_latency_ms']:.1f}ms")

    print_headline_table(results)
    print_full_table(results)
    print_per_question_breakdown(results)


if __name__ == "__main__":
    main()