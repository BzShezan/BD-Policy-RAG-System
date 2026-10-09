from original_paths import project_path, PDF_ROOT
"""Map a ChromaDB doc_id back to the actual PDF file on disk.

Clause doc_ids can be truncated versions of the real document title
(a pre-existing OCR/chunking issue - confirmed yesterday when this
broke word-box matching too). So this matches by PREFIX, not exact
filename, same fix as 9_inference.py.
"""

import os

PDF_FOLDERS = {
    "Social Welfare": str(PDF_ROOT / "social_welfare"),
    "Agriculture": str(PDF_ROOT / "Agriculture"),
    "Disaster Management": str(PDF_ROOT / "Disaster Management"),
}

_pdf_cache = {}  # ministry -> list of filenames, loaded once


def _pdf_list(ministry):
    if ministry not in _pdf_cache:
        folder = PDF_FOLDERS.get(ministry)
        if folder and os.path.exists(folder):
            _pdf_cache[ministry] = os.listdir(folder)
        else:
            _pdf_cache[ministry] = []
    return _pdf_cache[ministry]


def find_pdf_path(doc_id, ministry):
    """Find the real PDF file for a doc_id, or None if not found."""
    folder = PDF_FOLDERS.get(ministry)
    if not folder:
        return None

    doc_id_clean = doc_id.strip()

    # Try exact match first (fast path, works for most documents)
    exact = doc_id_clean + ".pdf"
    exact_path = os.path.join(folder, exact)
    if os.path.exists(exact_path):
        return exact_path

    # Fall back to prefix match for truncated doc_ids
    prefix = doc_id_clean[:40]
    for fname in _pdf_list(ministry):
        if fname.startswith(prefix) and fname.endswith(".pdf"):
            return os.path.join(folder, fname)

    return None