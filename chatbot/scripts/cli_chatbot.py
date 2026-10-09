"""Unmochon CLI chatbot.

Interactive command-line interface over the same live retrieval
pipeline that powers the web search engine. Same two-stage search,
same extractors, same confidence tiers, same out-of-scope handling.
Only difference: responses are formatted as natural-language Bengali
prose with citation rather than result cards.

Design principle: never fabricate. Every answer comes from a
retrieved clause. When extractors cannot verify a specific value,
the chatbot returns the top matching clause verbatim with a
"see source" note - never invents an answer.

Type 'exit' or 'quit' to leave.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts", "retrieval"))
sys.path.insert(0, HERE)   # for intent, extractor_map in same dir

from scripts.retrieval.search        import HybridRetriever
from scripts.retrieval.translator    import Translator
from scripts.retrieval.two_stage     import two_stage_search
from scripts.retrieval.extractor_map import EXTRACTORS_FOR_INTENT
from chatbot.scripts.intent        import detect_intents


# ---------------------------------------------------------------
# Response formatters
# ---------------------------------------------------------------

EXTRACTOR_LABELS_BN = {
    "extract_age":                  "বয়স",
    "extract_income_limit":         "বার্ষিক আয়সীমা",
    "extract_benefit_amount":       "ভাতার পরিমাণ",
    "extract_document_requirements":"প্রয়োজনীয় কাগজপত্র",
    "extract_district_allocations": "জেলা বরাদ্দ",
}


def _format_extracted_value(extractor_name, value):
    """Turn an extracted value into a readable Bengali string.
    Handles list values (documents, district-amount tuples) and
    scalar values (age, income) uniformly."""
    if isinstance(value, list):
        if value and isinstance(value[0], tuple):
            return "; ".join(f"{d}: {a} টাকা" for d, a in value)
        return ", ".join(str(v) for v in value)
    return str(value)


def format_high_confidence(result):
    """Confident answer with extracted values. User gets a direct
    statement of the extracted facts plus source citation."""
    extracted = result.get("extracted", {})
    if not extracted:
        # Fallback if tier is high but no extraction (shouldn't happen)
        return format_low_confidence(result)

    lines = ["নিশ্চিত করে বলা যায়:\n"]
    for ext_name, entry in extracted.items():
        label = EXTRACTOR_LABELS_BN.get(ext_name, ext_name)
        value = _format_extracted_value(ext_name, entry["value"])
        lines.append(f"  • {label}: {value}")

    lines.append("")
    lines.append(f"সূত্র: {result['doc_id']}")
    lines.append(f"পৃষ্ঠা: {result.get('page', '?')}")
    return "\n".join(lines)


def format_medium_confidence(result):
    """Answer found but confidence is moderate. Same shape as high,
    with a hedging phrase so the user knows to verify."""
    extracted = result.get("extracted", {})
    if not extracted:
        return format_low_confidence(result)

    lines = ["সম্ভাব্য উত্তর (যাচাই করা উচিত):\n"]
    for ext_name, entry in extracted.items():
        label = EXTRACTOR_LABELS_BN.get(ext_name, ext_name)
        value = _format_extracted_value(ext_name, entry["value"])
        lines.append(f"  • {label}: {value}")

    lines.append("")
    lines.append(f"সূত্র: {result['doc_id']}")
    lines.append(f"পৃষ্ঠা: {result.get('page', '?')}")
    return "\n".join(lines)


def format_low_confidence(result):
    """No extractor fired. Return the top clause verbatim with a
    clear "see source" instruction. No fabrication."""
    text = (result.get("text") or "").strip()
    if len(text) > 400:
        text = text[:400] + "..."

    return (
        "আপনার প্রশ্নের সঠিক উত্তর নিষ্কাশন করা যায়নি। "
        "সম্পর্কিত এই তথ্যটি পাওয়া গেছে (মূল লেখা দেখুন):\n\n"
        f"  {text}\n\n"
        f"সূত্র: {result['doc_id']}\n"
        f"পৃষ্ঠা: {result.get('page', '?')}"
    )


def format_out_of_scope(result):
    """Query has no meaningful corpus match. Tell the user honestly
    rather than force a low-confidence answer on unrelated content."""
    return result.get("note",
        "আপনার প্রশ্নটি আমাদের কর্পাসের সাথে সম্পর্কিত নয়।"
    )


def format_response(results):
    """Route to the right formatter based on top result's tier."""
    if not results:
        return "কোনো ফলাফল পাওয়া যায়নি।"

    top = results[0]
    tier = top.get("confidence_tier", "medium")

    if tier == "out_of_scope":
        return format_out_of_scope(top)
    if tier == "high":
        return format_high_confidence(top)
    if tier == "medium":
        return format_medium_confidence(top)
    if tier == "low":
        return format_low_confidence(top)
    return format_low_confidence(top)


# ---------------------------------------------------------------
# Chat loop
# ---------------------------------------------------------------

BANNER = """
======================================================================
                    উন্মোচন — Unmochon চ্যাটবট
======================================================================
বাংলাদেশ সরকারি নীতিমালা সংক্রান্ত প্রশ্নের উত্তর দিতে প্রস্তুত।
সামাজিক কল্যাণ, কৃষি, ও দুর্যোগ ব্যবস্থাপনা মন্ত্রণালয়ের নীতিমালা।

আপনার প্রশ্ন বাংলা বা ইংরেজিতে লিখুন।
বেরিয়ে যেতে 'exit' বা 'quit' লিখুন।
======================================================================
"""

EXIT_WORDS = {"exit", "quit", "bye", "বিদায়", "ছাড়ো"}


def chat_loop(retriever, translator):
    """Main REPL. Runs until user types an exit word."""
    print(BANNER)

    while True:
        try:
            question = input("আপনি > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nবিদায়।")
            break

        if not question:
            continue
        if question.lower() in EXIT_WORDS:
            print("বিদায়।")
            break

        # Translate if English
        translated = translator.to_bengali(question)

        # Full pipeline
        intents = detect_intents(translated)
        results = two_stage_search(
            retriever             = retriever,
            question              = translated,
            intents               = intents,
            extractors_for_intent = EXTRACTORS_FOR_INTENT,
            ministry              = None,
        )

        # Optional: show translated form if English was translated
        response = format_response(results)
        print()
        if translated != question:
            print(f"[অনুবাদিত: {translated}]")
        print("উন্মোচন > " + response)
        print()


def main():
    print("[startup] লোড হচ্ছে ...")
    retriever  = HybridRetriever()
    translator = Translator()
    print("[startup] প্রস্তুত।\n")

    chat_loop(retriever, translator)


if __name__ == "__main__":
    main()