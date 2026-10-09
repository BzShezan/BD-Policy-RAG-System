"""One portable path/model configuration shared by original and Live modules."""
import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(os.getenv('UNMOCHON_HOME', Path(__file__).resolve().parent)).expanduser().resolve()
load_dotenv(PROJECT_ROOT / '.env', override=False)

def project_path(relative):
    return str(PROJECT_ROOT / relative)

def configured_path(key, relative):
    value = Path(os.getenv(key, relative)).expanduser()
    return value.resolve() if value.is_absolute() else (PROJECT_ROOT / value).resolve()

DATA_DIR = configured_path('ORIGINAL_DATA_DIR', 'data')
CHROMADB_DIR = str(configured_path('CHROMADB_DIR', str(DATA_DIR / 'chromedb')))
BM25_INDEX_PATH = str(configured_path('BM25_INDEX_PATH', str(DATA_DIR / 'bm25_index.pkl')))
PROCESSED_DIR = str(configured_path('PROCESSED_DIR', str(DATA_DIR / 'processed_jsonl')))
METADATA_PATH = configured_path('DOC_METADATA_PATH', str(DATA_DIR / 'doc_metadata.json'))
PDF_ROOT = configured_path('RAW_PDF_DIR', str(DATA_DIR / 'raw_pdfs'))
EMBED_MODEL = os.getenv('EMBED_MODEL', 'paraphrase-multilingual-MiniLM-L12-v2')
COLLECTION_NAME = 'unmochon_clauses'
