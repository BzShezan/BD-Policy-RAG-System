"""Terminal-only report: 10 extractors with coverage + 5 real samples each.
Output is designed for screenshotting into your report."""

import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts", "retrieval"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "chatbot", "scripts"))

from scripts.retrieval.search import HybridRetriever
from chatbot.scripts.ner import (
    extract_age, extract_income_limit, extract_benefit_amount,
    extract_document_requirements, extract_district_allocations,
    extract_office_authority, extract_deadline_date,
    extract_frequency, extract_duration_period, extract_penalty_fine,
)

EXTRACTORS = [
    (extract_age,                   "extract_age",                  0.85),
    (extract_income_limit,          "extract_income_limit",         0.7),
    (extract_benefit_amount,        "extract_benefit_amount",       0.7),
    (extract_document_requirements, "extract_document_requirements",0.6),
    (extract_district_allocations,  "extract_district_allocations", 0.7),
    (extract_office_authority,      "extract_office_authority",     0.9),
    (extract_deadline_date,         "extract_deadline_date",        0.8),
    (extract_frequency,             "extract_frequency",            0.7),
    (extract_duration_period,       "extract_duration_period",      0.7),
    (extract_penalty_fine,          "extract_penalty_fine",         0.8),
]


def main():
    r = HybridRetriever()
    got = r.collection.get(include=["documents", "metadatas"])
    total = len(got["ids"])

    print()
    print("=" * 78)
    print("  UNMOCHON - 10 EXTRACTOR EVALUATION")
    print("=" * 78)
    print(f"  Total corpus clauses: {total:,}")
    print()

    # --- Coverage summary table ---
    print("-" * 78)
    print("  COVERAGE SUMMARY")
    print("-" * 78)
    print(f"  {'#':<3} {'Extractor':<32} {'Matches':>10}  {'Coverage':>10}")
    print(f"  {'-'*3} {'-'*32} {'-'*10}  {'-'*10}")

    stats = []
    for i, (fn, name, min_conf) in enumerate(EXTRACTORS, 1):
        hits = sum(1 for t in got["documents"]
                   if (result := fn(t))[0] and result[1] >= min_conf)
        pct = 100 * hits / total
        stats.append((fn, name, min_conf, hits, pct))
        print(f"  {i:<3} {name:<32} {hits:>10,}  {pct:>9.2f}%")

    # --- Sample extractions per extractor ---
    for fn, name, min_conf, hits, pct in stats:
        print()
        print("-" * 78)
        print(f"  {name.upper()}   coverage: {pct:.2f}%   min_conf: {min_conf}")
        print("-" * 78)

        samples = []
        seen = set()
        for cid, text, meta in zip(got["ids"], got["documents"], got["metadatas"]):
            val, conf = fn(text)
            if not val or conf < min_conf:
                continue
            doc_id = meta.get("doc_id", "")
            if doc_id in seen:
                continue
            seen.add(doc_id)
            samples.append((cid, val, conf, text[:150]))
            if len(samples) >= 5:
                break

        for i, (cid, val, conf, preview) in enumerate(samples, 1):
            val_str = str(val)
            if isinstance(val, list):
                if val and isinstance(val[0], tuple):
                    val_str = "; ".join(f"{d}:{a}" for d, a in val[:2])
                else:
                    val_str = ", ".join(str(v) for v in val[:2])
            val_str = val_str[:55]
            preview = preview.replace("\n", " ").strip()[:100]
            print(f"    [{i}] value: {val_str}  (conf {conf})")
            print(f"        clause: {cid[-45:]}")
            print(f"        text:   {preview}...")

    print()
    print("=" * 78)


if __name__ == "__main__":
    main()