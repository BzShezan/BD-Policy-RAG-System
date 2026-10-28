from original_paths import project_path, PROCESSED_DIR
"""Direct clause lookup for verified questions.

For the 20-question demo set, we already know the exact correct
doc_id, page, and clause_id for each question - manually verified
against the real PDF earlier. This bypasses live search ranking
entirely, which can occasionally surface the wrong clause even when
the right one exists in the corpus.

Matching by clause_id, not just doc_id + page_number, because a
single page can contain many separate clauses - confirmed on this
corpus, one document had 10 different clauses all on page 11.

Live search (via search.py) remains separate, for general queries
outside the verified 20 - that's a different feature with different
guarantees, and should be presented as such.
"""

import json
import sys
import os

sys.path.insert(0, project_path('scripts/retrieval'))
from scripts.retrieval.pdf_lookup import find_pdf_path

CLAUSE_FILES = {
    "Social Welfare": os.path.join(PROCESSED_DIR, "Social_Welfare_clauses.jsonl"),
    "Agriculture": os.path.join(PROCESSED_DIR, "Agriculture_clauses.jsonl"),
    "Disaster Management": os.path.join(PROCESSED_DIR, "Disaster_Management_clauses.jsonl"),
}

_clause_cache = {}


def _load_ministry(ministry):
    if ministry not in _clause_cache:
        path = CLAUSE_FILES.get(ministry)
        if not path or not os.path.exists(path):
            _clause_cache[ministry] = []
        else:
            with open(path, encoding="utf-8") as f:
                _clause_cache[ministry] = [json.loads(l) for l in f if l.strip()]
    return _clause_cache[ministry]


def get_verified_clause(ministry, doc_id, page_number=None, clause_id=None):
    """Directly fetch the exact clause. Prefer matching by clause_id
    when given - a single page can contain many separate clauses, so
    doc_id + page_number alone is not always enough to find the
    specific one that was manually verified."""
    clauses = _load_ministry(ministry)

    if clause_id:
        for c in clauses:
            if c.get("clause_id") == clause_id:
                return c
        return None

    for c in clauses:
        if c.get("doc_id") == doc_id and c.get("page_number") == page_number:
            return c
    return None


def get_source_link(doc_id, ministry, source_url=""):
    """Build the source citation, including a real PDF link.
    Prefers the web source_url if one exists (from the metadata
    merge); falls back to the local file path so the PDF can still
    be opened directly."""
    if source_url:
        return source_url

    local_path = find_pdf_path(doc_id, ministry)
    if local_path:
        return local_path

    return "(source file not found)"