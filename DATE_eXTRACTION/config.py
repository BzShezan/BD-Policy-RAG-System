from original_paths import PROCESSED_DIR, CHROMADB_DIR, COLLECTION_NAME
from original_paths import project_path
"""Paths and settings for date extraction."""


# Files to process. Each gets circular_date added to every clause.
TARGET_FILES = [
    "Social_Welfare_clauses.jsonl",
    "Disaster_Management_clauses.jsonl",
    "Agriculture_clauses.jsonl",
]

# Only look for dates in the first N pages of a document. The issue date
# lives in the page 1 letterhead - dates appearing later in a document
# are almost always references to other documents.
HEADER_PAGES = 2

# --- must match chromadb_build/config.py ---
