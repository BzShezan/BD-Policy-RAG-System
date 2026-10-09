from original_paths import project_path
"""Runs a single verified question through the full pipeline,
using guaranteed-correct clause lookup instead of live search."""

import sys
sys.path.insert(0, project_path('chatbot/scripts'))

from chatbot.scripts.verified_lookup import get_verified_clause, get_source_link
from chatbot.scripts.intent import detect_intents
from chatbot.scripts.answer_generator import generate_answer

def answer_verified_question(query, ministry, doc_id, clause_id):
    clause = get_verified_clause(ministry, doc_id, clause_id=clause_id)
    if not clause:
        print("ERROR: verified clause not found - check doc_id/clause_id")
        return

    source_url = get_source_link(doc_id, ministry, clause.get("source_url", ""))
    intents = detect_intents(query)

    responses = generate_answer(
        clause_text=clause["text"],
        doc_id=doc_id,
        page=clause["page_number"],
        source_url=source_url,
        intents=intents,
    )

    print(f"\nQuestion: {query}")
    print(f"Detected intent: {intents}")
    for r in responses:
        print(f"\n[{r['tier'].upper()} confidence: {r['confidence']:.2f}]")
        print(r["answer"])
    print(f"\nSource: {source_url}")


# Test with question 1
answer_verified_question(
    query="বেদে দলিত হরিজন সম্প্রদায়ের আয়সীমা কত?",
    ministry="Social Welfare",
    doc_id="SW_DEPR_Bede, Dalit, AND Harijan_2013_00_Policy_v3",
    clause_id="SW_DEPR_Bede, Dalit, AND Harijan_2013_00_Policy_v3_C0033",
)