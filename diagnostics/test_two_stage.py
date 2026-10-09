"""Two-stage retrieval: find the document, then find the clause.

Stage 1: broad hybrid retrieval, aggregate clause scores per document
         with a doc_id name-match boost
Stage 1.5: intent-aware doc filter - drop candidates with no matching
           extractor hits for the query's intents
Stage 2: within surviving documents, extract answer-type values, rank

Confidence tiers on returned results:
  "high"    extractor fired at high confidence (>= 0.85)
  "medium"  extractor fired at moderate confidence
  "low"     no extractor fired; top clause returned as best-guess
            with explicit "see source" instruction
"""

from collections import defaultdict


def group_by_document(candidates, query=""):
    """Sum RRF scores per doc_id, with a boost for documents whose
    doc_id contains query terms.

    Fixes the failure mode where a large general document ranks
    above a small topic-specific document. Example: query
    "বেদে দলিত হরিজন" was returning widow gazette at rank 1 because
    the widow doc has 138 clauses vs Bede doc's ~50, and RRF sum-
    pooling favored raw volume. Boosting on doc_id name match makes
    the topically-named document win, as it should.
    """
    doc_scores = {}
    doc_hits   = {}
    for c in candidates:
        doc_id = c["doc_id"]
        doc_scores[doc_id] = doc_scores.get(doc_id, 0) + c["rrf_score"]
        doc_hits[doc_id]   = doc_hits.get(doc_id, 0) + 1

    # Doc-id keyword boost. Each query token that appears in the
    # document filename adds 1.0 - large compared to typical RRF
    # scores (0.01-0.05), so this dominates when there's a name match.
    if query:
        q_tokens = [t for t in query.split() if len(t) >= 3]
        for doc_id in list(doc_scores.keys()):
            doc_lower = doc_id.lower()
            for token in q_tokens:
                if token.lower() in doc_lower:
                    doc_scores[doc_id] += 1.0

    ranked = sorted(
        doc_scores.items(),
        key=lambda x: (x[1], doc_hits[x[0]]),
        reverse=True,
    )
    return ranked


def intent_coverage(retriever, doc_id, intents, extractors_for_intent):
    """How many of the query intents have at least one clause with
    an extractable answer in this document."""
    if not intents:
        return 0

    got = retriever.collection.get(
        where={"doc_id": doc_id},
        include=["documents"],
    )

    covered = 0
    for intent in intents:
        extractors = extractors_for_intent.get(intent, [])
        intent_found = False
        for text in got["documents"]:
            for extractor in extractors:
                value, conf = extractor(text)
                if value:
                    intent_found = True
                    break
            if intent_found:
                break
        if intent_found:
            covered += 1

    return covered


def score_clause(clause_text, question, intents, extractors_for_intent):
    """Score a clause by extractor confidence plus token overlap."""
    extracted = {}
    for intent in intents:
        for extractor in extractors_for_intent.get(intent, []):
            value, conf = extractor(clause_text)
            if value:
                extracted[extractor.__name__] = {
                    "value":      value,
                    "confidence": conf,
                }

    if not extracted:
        return 0.0, {}

    q_tokens = set(question.split())
    c_tokens = set(clause_text.split())
    overlap  = len(q_tokens & c_tokens) / max(len(q_tokens), 1)

    max_conf = max(e["confidence"] for e in extracted.values())
    score = 1.0 * max_conf + 0.3 * overlap
    return score, extracted


def _tier_for_confidence(max_conf):
    """Map extractor confidence to human-facing tier label."""
    if max_conf >= 0.85:
        return "high"
    if max_conf >= 0.6:
        return "medium"
    return "medium"


def _low_confidence_fallback(stage1_results, return_k):
    """Return top-N stage-1 clauses tagged as low-confidence.

    Used when no clause in the candidate documents has an extractable
    answer. Rather than returning nothing, we hand back the most
    relevant clauses with a clear "verify from source" signal.
    """
    results = []
    for c in stage1_results[:return_k]:
        results.append({
            "id":              c["id"],
            "text":            c["text"],
            "doc_id":          c["doc_id"],
            "page":            c["page"],
            "ministry":        c["ministry"],
            "bbox":            c["bbox"],
            "score":           c["rrf_score"],
            "extracted":       {},
            "confidence_tier": "low",
            "note":            "মূল লেখা দেখুন / See original source",
        })
    return results


def two_stage_search(
    retriever,
    question,
    intents,
    extractors_for_intent,
    ministry=None,
    stage1_k=100,
    top_docs=3,
    return_k=5,
):
    """Full two-stage search with intent-aware filtering, doc-name
    boost, and low-confidence fallback."""

    # ---- Stage 1: broad retrieval ----
    stage1 = retriever.search(question, top_k=stage1_k, ministry=ministry)
    if not stage1:
        return []

    # Pass query through so doc-name boost fires
    ranked_docs = group_by_document(stage1, query=question)

    # ---- Stage 1.5: intent-aware document filter ----
    if intents:
        coverage_scores = []
        for doc_id, rrf_score in ranked_docs[:10]:
            coverage = intent_coverage(retriever, doc_id, intents,
                                       extractors_for_intent)
            if coverage > 0:
                combined = coverage * 1000 + rrf_score
                coverage_scores.append((combined, doc_id))

        if coverage_scores:
            coverage_scores.sort(reverse=True)
            top_doc_ids = [d for _, d in coverage_scores[:top_docs]]
        else:
            return _low_confidence_fallback(stage1, return_k)
    else:
        return _low_confidence_fallback(stage1, return_k)

    # ---- Stage 2: pull all clauses from surviving docs ----
    all_clauses = []
    for doc_id in top_doc_ids:
        got = retriever.collection.get(
            where={"doc_id": doc_id},
            include=["documents", "metadatas"],
        )
        for cid, text, meta in zip(got["ids"], got["documents"],
                                   got["metadatas"]):
            all_clauses.append({
                "id":       cid,
                "text":     text,
                "doc_id":   doc_id,
                "page":     meta.get("page_number", 0),
                "ministry": meta.get("ministry", ""),
                "bbox":     meta.get("bbox", ""),
            })

    # ---- Stage 2: score each clause ----
    scored = []
    for c in all_clauses:
        score, extracted = score_clause(
            c["text"], question, intents, extractors_for_intent,
        )
        if not extracted:
            continue
        c["score"]     = score
        c["extracted"] = extracted
        max_conf = max(e["confidence"] for e in extracted.values())
        c["confidence_tier"] = _tier_for_confidence(max_conf)
        scored.append(c)

    if not scored:
        return _low_confidence_fallback(stage1, return_k)

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:return_k]