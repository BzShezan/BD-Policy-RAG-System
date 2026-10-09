"""Two-stage retrieval with layered out-of-scope detection.

Stage 1: broad hybrid retrieval
Stage 1a: out-of-scope guard (3 checks: score, vocab overlap, keywords)
Stage 1.5: intent-aware doc filter
Stage 2: within surviving documents, extract answers, rank
"""

from collections import defaultdict


# ---- Out-of-scope thresholds ----
OUT_OF_SCOPE_SCORE_MIN     = 0.015   # top RRF must exceed this
OUT_OF_SCOPE_VOCAB_MIN     = 0.10   # ≥10% of query tokens must appear in top-3 clauses
OUT_OF_SCOPE_MIN_QTOK_LEN  = 3      # ignore short function words in overlap check

# Domain vocabulary. Query must contain at least one meaningful
# domain word OR fire an intent to be considered in-scope. Prevents
# generic queries like "কে" "কী" "সরকার" from passing.
DOMAIN_KEYWORDS = {
    # Social Welfare
    "বয়স্ক", "বিধবা", "প্রতিবন্ধী", "চা-শ্রমিক", "চা শ্রমিক",
    "বেদে", "দলিত", "হরিজন", "ভাতা", "সমাজকল্যাণ",
    "পিতা-মাতা", "পরিচর্যা", "প্রার্থী",
    "widow", "old age", "disability", "tea worker", "allowance",
    "bede", "dalit", "harijan",
    # Agriculture
    "সার", "বীজ", "কৃষি", "কৃষক", "ডিলার", "উৎপাদনকারী",
    "নিবন্ধন", "লাইসেন্স", "কাগজপত্র",
    "fertilizer", "seed", "agriculture", "dealer", "farmer",
    "producer", "documents",
    # Disaster Management
    "দুর্যোগ", "ত্রাণ", "শিশুখাদ্য", "শিশু খাদ্য", "কমিটি",
    "শুকনা খাবার", "বরাদ্দ", "কমিটি গঠন",
    "disaster", "relief", "allocation", "baby food",
    # Generic policy vocab
    "নীতিমালা", "যোগ্যতা", "শর্ত", "আবেদন", "বয়স", "আয়সীমা",
    "policy", "eligibility", "criteria", "age", "income",
}


def group_by_document(candidates, query=""):
    """Sum RRF per doc_id + doc-name keyword boost."""
    doc_scores = {}
    doc_hits   = {}
    for c in candidates:
        doc_id = c["doc_id"]
        doc_scores[doc_id] = doc_scores.get(doc_id, 0) + c["rrf_score"]
        doc_hits[doc_id]   = doc_hits.get(doc_id, 0) + 1

    if query:
        q_tokens = [t for t in query.split() if len(t) >= 3]
        for doc_id in list(doc_scores.keys()):
            doc_lower = doc_id.lower()
            for token in q_tokens:
                if token.lower() in doc_lower:
                    doc_scores[doc_id] += 1.0

    return sorted(doc_scores.items(),
                  key=lambda x: (x[1], doc_hits[x[0]]),
                  reverse=True)


def intent_coverage(retriever, doc_id, intents, extractors_for_intent):
    """How many intents this doc can extract."""
    if not intents:
        return 0
    got = retriever.collection.get(
        where={"doc_id": doc_id}, include=["documents"]
    )
    covered = 0
    for intent in intents:
        extractors = extractors_for_intent.get(intent, [])
        for text in got["documents"]:
            if any(ex(text)[0] for ex in extractors):
                covered += 1
                break
    return covered


def score_clause(clause_text, question, intents, extractors_for_intent):
    """Score a clause: extractor confidence + token overlap."""
    extracted = {}
    for intent in intents:
        for extractor in extractors_for_intent.get(intent, []):
            value, conf = extractor(clause_text)
            if value:
                extracted[extractor.__name__] = {
                    "value": value, "confidence": conf
                }
    if not extracted:
        return 0.0, {}
    q_tokens = set(question.split())
    c_tokens = set(clause_text.split())
    overlap  = len(q_tokens & c_tokens) / max(len(q_tokens), 1)
    max_conf = max(e["confidence"] for e in extracted.values())
    return 1.0 * max_conf + 0.3 * overlap, extracted


def _tier_for_confidence(max_conf):
    if max_conf >= 0.7:  return "high"
    if max_conf >= 0.5:  return "medium"
    return "medium"


def _low_confidence_fallback(stage1_results, return_k):
    return [{
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
    } for c in stage1_results[:return_k]]


def _out_of_scope_response():
    return [{
        "id":              "out_of_scope",
        "text":            "",
        "doc_id":          "",
        "page":            0,
        "ministry":        "",
        "bbox":            "",
        "score":           0.0,
        "extracted":       {},
        "confidence_tier": "out_of_scope",
        "note":            ("আপনার প্রশ্নটি আমাদের কর্পাসের সাথে সম্পর্কিত "
                            "নয় বলে মনে হচ্ছে। আমরা সামাজিক কল্যাণ, কৃষি, "
                            "এবং দুর্যোগ ব্যবস্থাপনা মন্ত্রণালয়ের নীতিমালা "
                            "সংক্রান্ত প্রশ্নের উত্তর দিতে পারি।"),
    }]


def _is_out_of_scope(question, intents, stage1_results):
    """Three-check gate. Query is out-of-scope unless ALL three pass.
    Each check catches a different failure mode:
      (1) score - was there any decent match at all?
      (2) vocab overlap - are query words actually in the retrieved
          clauses, or is this a spurious high score from shared
          stopwords like "কী"/"কত"?
      (3) domain gate - does the query touch a real domain concept,
          or is it a generic sentence that happened to score high?
    """
    if not stage1_results:
        return True

    # Check 1: minimum score
    if stage1_results[0]["rrf_score"] < OUT_OF_SCOPE_SCORE_MIN:
        return True

    # Check 2: vocabulary overlap. What fraction of meaningful query
    # tokens appear in the top-3 retrieved clauses combined?
    q_tokens = [t.lower() for t in question.split()
                if len(t) >= OUT_OF_SCOPE_MIN_QTOK_LEN]
    if q_tokens:
        top_text = " ".join(
            r["text"].lower() for r in stage1_results[:3]
        )
        matches  = sum(1 for t in q_tokens if t in top_text)
        overlap  = matches / len(q_tokens)
        if overlap < OUT_OF_SCOPE_VOCAB_MIN:
            return True

    # Check 3: domain gate. Query must contain a domain keyword OR
    # fire an intent. Generic English/Bengali sentences with no
    # domain relevance fail here.
    q_lower = question.lower()
    has_domain_keyword = any(kw.lower() in q_lower for kw in DOMAIN_KEYWORDS)
    has_intent        = bool(intents)
    if not has_domain_keyword and not has_intent:
        return True

    return False


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
    """Full pipeline with layered out-of-scope detection."""

    # Stage 1
    stage1 = retriever.search(question, top_k=stage1_k, ministry=ministry)

    # Out-of-scope gate (checks BEFORE intent-filter logic)
    if _is_out_of_scope(question, intents, stage1):
        return _out_of_scope_response()

    ranked_docs = group_by_document(stage1, query=question)

    # Stage 1.5: intent-aware doc filter
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

    # Stage 2: expand candidate docs
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

    # Stage 2: extractor scoring
    scored = []
    for c in all_clauses:
        score, extracted = score_clause(
            c["text"], question, intents, extractors_for_intent,
        )
        if not extracted:
            continue
        c["score"]           = score
        c["extracted"]       = extracted
        max_conf             = max(e["confidence"] for e in extracted.values())
        c["confidence_tier"] = _tier_for_confidence(max_conf)
        scored.append(c)

    if not scored:
        return _low_confidence_fallback(stage1, return_k)

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:return_k]