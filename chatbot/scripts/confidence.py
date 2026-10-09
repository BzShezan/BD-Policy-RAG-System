"""Confidence-gated answer generation.

Three tiers, per the roundtable decision:
  high   -> answer directly, extractive-sentence framing
  medium -> answer, but flagged as uncertain
  low    -> do NOT guess. Show the raw clause and say so.

This is the safety layer everything else builds on top of.
"""

CONFIDENCE_HIGH = 0.85
CONFIDENCE_MEDIUM = 0.6


def decide_tier(confidence_score):
    if confidence_score >= CONFIDENCE_HIGH:
        return "high"
    elif confidence_score >= CONFIDENCE_MEDIUM:
        return "medium"
    else:
        return "low"


def build_response(clause_text, doc_id, page, source_url, confidence_score, extracted_sentence=None):
    """Build the final answer shown to the user, based on confidence tier.

    Includes doc_id, page, source_url, and quoted_text as separate
    fields (not just baked into the formatted answer string), so
    downstream code like explain.py can build its own phrasing.
    """
    tier = decide_tier(confidence_score)

    citation = f"{doc_id}, page {page}"
    if source_url:
        citation += f" ({source_url})"

    quoted_text = extracted_sentence if extracted_sentence else clause_text[:400]

    base = {
        "tier": tier,
        "confidence": confidence_score,
        "doc_id": doc_id,
        "page": page,
        "source_url": source_url,
        "quoted_text": quoted_text,
    }

    if tier == "high" and extracted_sentence:
        base["answer"] = f"According to {citation}:\n\n\"{extracted_sentence}\""

    elif tier == "medium" and extracted_sentence:
        base["answer"] = (
            f"According to {citation}, this appears to be the relevant provision "
            f"(please verify):\n\n\"{extracted_sentence}\""
        )

    else:
        base["answer"] = (
            f"A relevant clause was found in {citation}, but a specific answer "
            f"could not be confidently extracted. Full clause text:\n\n"
            f"\"{clause_text[:400]}\""
        )

    return base