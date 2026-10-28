"""Read-only asset inspection; never initializes or rewrites the original database."""
import json
import sqlite3
import sys
from pathlib import Path

def diagnose(settings):
    if settings.rag_backend == 'stage6':
        from .runtime import load_stage4,load_stage6
        from .research_registry import make_registry
        load_stage4(settings.stage4_package or settings.root/'reference_pipelines/stage4')
        load_stage6(settings.stage6_package or settings.root/'reference_pipelines/stage6')
        from stage6.generations import active,generation
        from stage6.common import read
        workspace=settings.stage6_workspace or settings.root/'data/stage6_workspace'
        pointer=active(workspace)
        report=read(generation(workspace,pointer['generation'])/'index/build_report.json')
        return {'python':sys.version.split()[0],'root':str(settings.root),'rag_backend':'stage6',
            'generation':pointer['generation'],'generation_files_verified':True,
            'indexed_items':report.get('selection',{}).get('indexed_items'),
            'sealed_pair_consistency':report.get('consistency'),
            'registered_authorities':list(make_registry(settings.research_registry).entries),
            'models_tested':False,'network_tested':False,'index_writes':0}
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
