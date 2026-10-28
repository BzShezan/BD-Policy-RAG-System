"""Start this Unmochon folder using its own code and saved paths."""
import os
from pathlib import Path
import subprocess
import sys
from dotenv import dotenv_values
ROOT=Path(__file__).resolve().parent
KEYS=('SOURCE_REGISTRY', 'STAGE4_PACKAGE', 'STAGE6_PACKAGE', 'STAGE6_WORKSPACE', 'STAGE6_MODEL_PATH', 'STAGE6_MODEL_CACHE', 'STAGE2_EVIDENCE_DATA', 'RESEARCH_SOURCE_REGISTRY', 'RESEARCH_OUTPUT_ROOT', 'ORIGINAL_DATA_DIR', 'CORPUS_DIR', 'RAW_PDF_DIR', 'DOC_METADATA_PATH', 'PROCESSED_DIR', 'CHROMADB_DIR', 'BM25_INDEX_PATH', 'EMBED_MODEL', 'TRANSLATION_MODEL', 'STAGE4_OCR_MODELS', 'STAGE4_TESSERACT', 'STAGE6_PYTHON', 'HF_HOME', 'HF_HUB_CACHE', 'HUGGINGFACE_HUB_CACHE', 'TRANSFORMERS_CACHE', 'TORCH_HOME')
env=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8',UNMOCHON_HOME=str(ROOT))
for k,v in dotenv_values(ROOT/'.env').items():
    if k in KEYS and v is not None:env[k]=v
env['RAG_BACKEND']='stage6'
env['PYTHONPATH']=str(ROOT/'src')+os.pathsep+str(ROOT)
print('Unmochon: http://127.0.0.1:8000',flush=True)
try:
    raise SystemExit(subprocess.call([sys.executable,'-X','utf8','-m','unmochon_live','serve'],cwd=ROOT,env=env))
except KeyboardInterrupt:
    pass
