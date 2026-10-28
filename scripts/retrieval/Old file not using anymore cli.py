"""Unmochon search CLI.

Type a question, get back matching clauses with their source, and
open the actual PDF for any result you want to check.
"""

import os

from scripts.retrieval.search import HybridRetriever
from scripts.retrieval.pdf_lookup import find_pdf_path


def show_results(results):
    if not results:
        print("\nNo results found.\n")
        return

    print()
    for i, r in enumerate(results, 1):
        src = []
        if r["in_dense"]:
            src.append("dense")
        if r["in_sparse"]:
            src.append("bm25")
        table_tag = " [TABLE]" if r["is_table"] else ""

        print(f"[{i}] {'+'.join(src)}{table_tag}")
        print(f"    {r['ministry']} | {r['doc_id'][:60]} | page {r['page']}")
        print(f"    {r['text'][:200]}")
        print()


def open_pdf(results, choice):
    try:
        idx = int(choice) - 1
    except ValueError:
        print("Enter a number from the list above.")
        return

    if idx < 0 or idx >= len(results):
        print("That number isn't in the results list.")
        return

    r = results[idx]
    path = find_pdf_path(r["doc_id"], r["ministry"])

    if not path:
        print(f"Could not find the source PDF for: {r['doc_id']}")
        print("(the clause is real, but its source file could not be located)")
        return

    print(f"Opening: {path}")
    print(f"(the answer is on page {r['page']})")
    os.startfile(path)


def main():
    print("Loading Unmochon search ...")
    retriever = HybridRetriever()
    print("Ready.\n")
    print("Type a question in Bengali or English.")
    print("After results appear, type a number to open that result's PDF,")
    print("or type a new question. Type 'quit' to exit.\n")

    last_results = []

    while True:
        query = input("> ").strip()

        if not query:
            continue
        if query.lower() in ("quit", "exit"):
            break

        # If they typed just a number, treat it as "open this result"
        if query.isdigit() and last_results:
            open_pdf(last_results, query)
            continue

        results = retriever.search(query, top_k=5)
        show_results(results)
        last_results = results


if __name__ == "__main__":
    main()