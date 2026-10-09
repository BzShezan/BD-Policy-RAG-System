"""Read-only asset inspection; never initializes or rewrites the original database."""
import json
import sqlite3
import sys
from pathlib import Path

def diagnose(settings):
    from original_paths import CHROMADB_DIR, BM25_INDEX_PATH, METADATA_PATH, PDF_ROOT, EMBED_MODEL
    db = Path(CHROMADB_DIR)/'chroma.sqlite3'
    count = None
    if db.exists():
        with sqlite3.connect(db.as_uri() + '?mode=ro', uri=True) as connection:
            count = connection.execute('SELECT count(*) FROM embeddings').fetchone()[0]
    metadata = json.loads(METADATA_PATH.read_text(encoding='utf-8')) if METADATA_PATH.exists() else {}
    return {'python':sys.version.split()[0], 'root':str(settings.root), 'rag_backend':settings.rag_backend,
            'database_path':str(db), 'database_count':count, 'bm25_present':Path(BM25_INDEX_PATH).exists(),
            'document_metadata_count':len(metadata), 'raw_policy_pdf_count':len(list(PDF_ROOT.rglob('*.pdf'))),
            'layout_checkpoint_present':(settings.root/'layout_analysis/models/lilt_sw_v1').exists(),
            'embedding_model':EMBED_MODEL, 'models_tested':False, 'network_tested':False,
            'api_key_configured':bool(settings.api_key)}
