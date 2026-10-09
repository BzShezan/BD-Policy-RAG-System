from original_paths import PROJECT_ROOT, DATA_DIR, CHROMADB_DIR, BM25_INDEX_PATH, EMBED_MODEL, COLLECTION_NAME, PROCESSED_DIR
from original_paths import project_path
"""All paths and settings in one place."""

# Where your JSONL files live

# Where ChromaDB will be saved

# Embedding model - multilingual, works for Bengali + English

# Collection name inside ChromaDB

# Quality thresholds for each file type
CLAUSE_MIN_QUALITY = 0.4    # main clauses
REVIEW_MIN_QUALITY = 0.3    # cleaned review clauses
TABLE_MIN_QUALITY  = 0.4    # tables

# Minimum text length to keep (characters)
MIN_TEXT_LENGTH = 50