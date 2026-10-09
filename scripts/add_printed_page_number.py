from original_paths import project_path
"""Add printed_page_number to every clause - the actual number that
appears on the physical page, which is what a human checking the
citation against the real PDF will expect to see (different from
page_number, which is the file's internal 1-indexed position).

Detection is intentionally conservative: only a genuinely isolated
number - alone on its own line at the top or bottom of the page, not
embedded in a longer line like a table-of-contents entry - counts as
a real page number. Front-matter pages (cover, preface, table of
contents) often have no printed number, or use Roman numerals, or
happen to contain numbers that are not actually the page number - all
of these correctly return None rather than a guessed value.

This means some pages will have no printed_page_number even after
running this script. That is by design - never state a citation that
was not confidently detected. Treat this script's output as a first
pass to verify per-question, not a guaranteed-correct final answer.

Includes a long-path fallback for the Windows MAX_PATH (260 char)
limit - some document filenames in this corpus exceed that, which was
already hit and fixed once during the original page export work.
"""

import json
import re
import os
import fitz

PROCESSED_DIR = project_path('data/processed_jsonl')
PDF_FOLDERS = {
    "Social_Welfare": project_path('data/raw_pdfs/social_welfare'),
    "Agriculture": project_path('data/raw_pdfs/Agriculture'),
    "Disaster_Management": project_path('data/raw_pdfs/Disaster Management'),
}


def get_printed_page_number(page):
    """Look for a standalone number, isolated from other text, at the
    very top or bottom of the page."""
    text = page.get_text()
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    if not lines:
        return None

    candidates = []
    for line in [lines[0], lines[-1]]:
        if re.fullmatch(r'\d{1,3}', line):
            candidates.append(int(line))

    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) == 2 and candidates[0] == candidates[1]:
        # number appears at both top AND bottom, matching - high confidence
        return candidates[0]

    # ambiguous or no match - do not guess
    return None


def find_pdf(doc_id, ministry_folder):
    """Find the real PDF file for a doc_id - prefix match, since
    doc_ids can be truncated versions of the real filename."""
    if not os.path.exists(ministry_folder):
        return None
    doc_id_clean = doc_id.strip()
    exact = os.path.join(ministry_folder, doc_id_clean + ".pdf")
    if os.path.exists(exact):
        return exact
    prefix = doc_id_clean[:40]
    for fname in os.listdir(ministry_folder):
        if fname.startswith(prefix) and fname.endswith(".pdf"):
            return os.path.join(ministry_folder, fname)
    return None


def open_pdf_safely(pdf_path):
    """Open a PDF, falling back to the \\\\?\\ long-path prefix if the
    normal path fails due to Windows' 260-character MAX_PATH limit."""
    try:
        return fitz.open(pdf_path)
    except Exception:
        try:
            long_path = "\\\\?\\" + os.path.abspath(pdf_path)
            return fitz.open(long_path)
        except Exception as e:
            print(f"  could not open {pdf_path}: {e}")
            return None


def process_file(jsonl_name, ministry_folder):
    path = os.path.join(PROCESSED_DIR, jsonl_name)
    if not os.path.exists(path):
        print(f"  not found, skipping: {jsonl_name}")
        return

    with open(path, encoding="utf-8") as f:
        clauses = [json.loads(l) for l in f if l.strip()]

    # cache: doc_id -> {file_position: printed_number_or_None}
    page_map_cache = {}
    filled = 0
    no_match = 0

    for c in clauses:
        doc_id = c.get("doc_id", "")
        file_pos = c.get("page_number", 0)

        if doc_id not in page_map_cache:
            pdf_path = find_pdf(doc_id, ministry_folder)
            mapping = {}
            if pdf_path:
                doc = open_pdf_safely(pdf_path)
                if doc:
                    for i in range(len(doc)):
                        printed = get_printed_page_number(doc[i])
                        mapping[i + 1] = printed
                    doc.close()
            page_map_cache[doc_id] = mapping

        printed = page_map_cache[doc_id].get(file_pos)
        c["printed_page_number"] = printed if printed is not None else ""
        if printed is not None:
            filled += 1
        else:
            no_match += 1

    with open(path, "w", encoding="utf-8") as f:
        for c in clauses:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print(f"  {jsonl_name}: {filled} clauses got a printed page number, "
          f"{no_match} could not be confidently detected")


def main():
    print("Adding printed_page_number ...\n")
    process_file("Social_Welfare_clauses.jsonl", PDF_FOLDERS["Social_Welfare"])
    process_file("Agriculture_clauses.jsonl", PDF_FOLDERS["Agriculture"])
    process_file("Disaster_Management_clauses.jsonl", PDF_FOLDERS["Disaster_Management"])
    print("\nDone.")


if __name__ == "__main__":
    main()