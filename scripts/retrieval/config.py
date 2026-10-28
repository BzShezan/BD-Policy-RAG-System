"""Paths and settings for retrieval.

The first three values are duplicated from chromadb_build/config.py on
purpose. If you change them there, change them here too. Two visible
copies are easier to catch than one hidden import that silently drifts.
"""

from pathlib import Path
from original_paths import PROJECT_ROOT, DATA_DIR, CHROMADB_DIR, BM25_INDEX_PATH, EMBED_MODEL, COLLECTION_NAME, PROCESSED_DIR


# ---------------------------------------------------------
# Project paths
# ---------------------------------------------------------

# config.py location:
# BD-Policy-RAG-System/scripts/retrieval/config.py
#
# parents[0] = retrieval
# parents[1] = scripts
# parents[2] = BD-Policy-RAG-System



# ---------------------------------------------------------
# Must match chromadb_build/config.py
# ---------------------------------------------------------





# ---------------------------------------------------------
# Retrieval only
# ---------------------------------------------------------



# How many results each retriever returns before fusion.
# Pull more than we need so RRF has something to work with.
CANDIDATES_PER_RETRIEVER = 50


# RRF constant.
# 60 is the value from the original paper and is what
# most implementations use.
RRF_K = 60