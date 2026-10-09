"""Extractive-sentence answer generation.

Given a retrieved clause and the intent(s) detected in the question,
find the SPECIFIC SENTENCE within the clause that answers it, and wrap
it in a fixed attribution frame - never rebuild a new sentence from
extracted values, since Bengali grammar (case markers, postpositions)
breaks under naive template-filling. See roundtable decision.
"""

import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from chatbot.scripts.ner import (
    extract_age, extract_income_limit, extract_benefit_amount,
    extract_document_requirements, extract_district_allocations,
)
from chatbot.scripts.confidence import build_response


def split_into_sentences(text):
    """Rough sentence split for Bengali/English mixed text.
    Splits on Bengali full stop (।), English period, and semicolons
    (common in numbered legal clauses)."""
    parts = re.split(r'[।;.]\s*', text)
    return [p.strip() for p in parts if p.strip()]


def find_answering_sentence(clause_text, intent):
    """Find the specific sentence within a clause that contains the
    answer for a given intent. Returns (sentence, confidence) - the
    sentence is the REAL text from the source, never rebuilt."""

    sentences = split_into_sentences(clause_text)

    extractors = {
        "age": extract_age,
        "income_limit": extract_income_limit,
        "benefit_amount": extract_benefit_amount,
        "required_documents": extract_document_requirements,
        "district_allocation": extract_district_allocations,
    }

    extractor = extractors.get(intent)
    if not extractor:
        # no specific extractor for this intent - fall back to
        # returning the whole clause, low confidence
        return clause_text, 0.5

    # check each sentence individually - the one containing the
    # matched entity is the answering sentence
    for sentence in sentences:
        value, conf = extractor(sentence)
        if value:
            return sentence, conf

    # entity pattern didn't match any single sentence cleanly -
    # try the whole clause as a fallback before giving up
    value, conf = extractor(clause_text)
    if value:
        return clause_text, conf * 0.8  # slightly lower confidence

    return None, 0.0


def generate_answer(clause_text, doc_id, page, source_url, intents):
    """Main entry point. Given a clause and the list of detected
    intents, produce one or more extractive answers, run through the
    confidence-gated fallback layer.

    Returns a list of response dicts, one per intent that was
    successfully or unsuccessfully answered - so a multi-intent
    question ("age AND income limit") gets multiple answer blocks.
    """
    if not intents:
        # no specific intent detected - show the raw clause,
        # explicitly low confidence, per the fallback design
        return [build_response(clause_text, doc_id, page, source_url, 0.3)]

    responses = []
    for intent in intents:
        sentence, confidence = find_answering_sentence(clause_text, intent)
        responses.append(
            build_response(clause_text, doc_id, page, source_url,
                          confidence, extracted_sentence=sentence)
        )

    return responses