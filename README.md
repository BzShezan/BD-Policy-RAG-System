# Unmochon Live — Original RAG Base

This merged project runs the **original Unmochon engine** behind the existing Live FastAPI server and visual shell. It uses your private original 15,019-record `unmochon_clauses` collection and matching BM25 index. GitHub contains source code and UI assets only; the database, datasets, document metadata, policy PDFs and model checkpoints stay local. This phase uses the original corpus only; agent/web routing is not part of the default request path.

## Clone from GitHub

```powershell
git clone https://github.com/BzShezan/BD-Policy-RAG-System.git
cd BD-Policy-RAG-System
```

Copy your existing private `data/` folder into `BD-Policy-RAG-System/data/` before serving. Keep `chromedb/` together with **all its SQLite and HNSW files**, `bm25_index.pkl`, `doc_metadata.json` and `processed_jsonl/`; do not copy only the SQLite file or rebuild its embeddings. Keep the original workbook, corpus, policy PDFs and any layout inputs/checkpoints in your private backup too. Setup creates local configuration and preserves existing data; it does not download or restore a database. Alternatively, set `ORIGINAL_DATA_DIR`, `CHROMADB_DIR`, `BM25_INDEX_PATH`, `PROCESSED_DIR`, `DOC_METADATA_PATH` and `RAW_PDF_DIR` to your existing private paths in `.env`. Paths already set in `.env` take priority, so update each relevant setting when using external data.

## Start on Windows PowerShell

Use **Python 3.11 or 3.12** for the original model stack. Python 3.14 from the previous lightweight Live project is not the supported environment for this merge.

```powershell
# You are in BD-Policy-RAG-System after cloning.
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python scripts/setup.py
python -m unmochon_live doctor
python -m unmochon_live serve
```

Open http://127.0.0.1:8000. The first embedding query downloads the original `paraphrase-multilingual-MiniLM-L12-v2` model if it is not cached. The first English query additionally downloads the original NLLB model. To run offline, set `EMBED_MODEL` and `TRANSLATION_MODEL` in `.env` to local copies of those **same** models. Do not substitute another embedding model into the existing vectors.

For optional original Gemini explanations, install `python -m pip install -e ".[explanation]"` and supply `GEMINI_API_KEY` privately in `.env`. `GEMINI_MODEL` keeps the original source setting and can be set to a model available to your account. Its remote availability was not tested. Without a key, the original extractor/template explanation fallback remains available. No key is bundled.

## Features included

- Original digital/Tesseract/Apsis OCR flow, word boxes, quality detection, clause chunking and table extraction (`scripts/ocr_pipeline/`, `scripts/1_batch_pipeline.py`).
- Original layout conversion, training/inference, geometry rules and table verification (`layout_analysis/`).
- Original Chroma dense retrieval, BM25, RRF, Bengali tokenization and query expansion (`scripts/retrieval/`).
- Original two-stage document/intent filtering, out-of-scope guard and confidence tiers.
- Original 10 NER extractors, normalization, intent detection, confidence responses, extractive answer generation and verified clause lookup (`chatbot/scripts/`). Verified lookup remains a direct clause lookup utility; arbitrary queries use the original search pipeline.
- Original explanations, metadata lookup, date-aware conflict grouping, exact PDF clause search/highlight URL builder and original PDF.js assets (`UI/`).
- Original date, metadata-processing, evaluation and layout code from the supplied source. The workbook/JSON, processed chunks, layout datasets and generated reports remain private local inputs.

Live HTML templates, CSS, fonts and logos are byte-for-byte unchanged. JavaScript wiring uses original result fields and the original conflict renderer within the existing result page. It now exposes extraction values, explanations and the PDF link using the existing CSS classes. Login/session/CSRF behavior is preserved. `/v1/query` and `/ui/query` return the same original evidence, with complete `metadata` and `document_metadata` fields. The original Flask UI is also retained in `UI/`; the default interface is Live.

## Missing assets in the supplied ZIP

**No raw policy PDFs or trained layout-model checkpoints were uploaded.** Add your original assets to:

```text
data/raw_pdfs/social_welfare/
data/raw_pdfs/Agriculture/
data/raw_pdfs/Disaster Management/
layout_analysis/models/lilt_sw_v1/
```

Original official URLs still come from your private metadata. The original PDF highlight link appears only when the matching local PDF exists; no replacement PDFs or invented URLs are created. The original PDF.js source and supporting renderer assets are included; its demonstration PDF is omitted. Layout inference requires your trained checkpoint; `LAYOUT_MODEL_DIR` can point to it. Search can use the already indexed layout labels without rerunning that model.

## Add or update new dataset chunks

Stop the search server and other database writers first. Put the new chunks in a separate folder using the original filenames:

```text
incoming/
  Agriculture_clauses.jsonl
  Agriculture_clauses_review.jsonl       (optional)
  Agriculture_tables.jsonl              (optional)
  doc_metadata.json                     (optional)
```

The other supported prefixes are `Social_Welfare` and `Disaster_Management`. New clause rows use the original fields (`clause_id`, `doc_id`, `page_number`, `text`, `quality_score`, `layout_label`, `bbox`, `source_url`, dates and any extra metadata). Stable `clause_id` identifies updates; a new ID adds a new record. Duplicate IDs inside a dataset are rejected. Table files use the original row schema, including `raw_text`, `table_index` and `row_index`. Metadata JSON is the original `doc_id -> object` mapping; omitted document fields are retained.

```powershell
python -m unmochon_live update-dataset .\incoming --metadata .\incoming\doc_metadata.json
python -m unmochon_live serve
```

Omit `--metadata` if you have no document metadata update. The updater:

1. Validates JSONL before writing and applies the **original quality/layout/corruption filters and table grouping**.
2. Updates an isolated copy of the existing ChromaDB with the same embedding model, preserving other records and metadata. New extra fields and complete incoming chunk/table JSON remain in Chroma metadata.
3. Rebuilds BM25 with the **original builder**, then verifies exact ID equality with ChromaDB.
4. Commits the database, BM25, document metadata and merged processed JSONL while the server is stopped. A timestamped backup and report are saved in `data/update_backups/`.

Repeated identical input does not add duplicates. Ordinary staging failures leave the active data unchanged; commit exceptions restore saved files. Backups also allow manual recovery after abrupt power/process interruption. Do not run the old builder with `--fresh`: that deletes/recreates the collection. Keep disk space for the staging copy and backup.

Keep updated chunks, the database, BM25, metadata and update backups private. Git ignores `data/`, `incoming/`, database/archive files and model/dataset directories. Share source-code changes through GitHub; transfer data separately only to authorized local users.

## Docker with private data

The Docker build includes source and UI assets only. Supply configuration with `--env-file` and mount your private data at `/app/data` when running the container. Use container paths in that configuration. Layout inputs/checkpoints require their own private mount if used. `.dockerignore` excludes database, dataset, archive and credential files from the build context.

## Original processing tools

```powershell
python -m pip install -e ".[ocr,metadata]"
# Install Tesseract and Bengali/English language data on your PC too.
$env:OCR_MINISTRY="Social_Welfare"
$env:OCR_INPUT_DIR="G:\your-pdfs\social_welfare"
python scripts/1_batch_pipeline.py

# Separate original layout environment/checkpoint workflow:
python -m pip install -e ".[layout,ocr,metadata]"
$env:LAYOUT_MODEL_DIR="G:\your-models\lilt_sw_v1"
python layout_analysis/pipeline/9_inference.py
```

The numbered original layout preparation/training scripts and README are preserved. Historical external drive paths are redirected under `layout_analysis/workspace/`; put the required exported/annotated inputs there or adjust the script's input setting. ApsisOCR/FastDeploy are optional original fallback dependencies; their exact old versions are preserved in `requirements-original.txt`, not forced into every search install.

Long Bengali word-box filenames exceeding Linux limits are shortened with a reversible mapping in `docs/long_filename_mapping.json`; the original full-corpus inference script consults the mapping when matching document names. Document IDs and original corpus text are not renamed.

## Validation

```powershell
python -m pip install -e ".[test]"
python -m pytest -q
```

See `docs/MERGE_VALIDATION.md` and `docs/FEATURE_MAP.md` for verified checks and remaining runtime limits. Tests using synthetic or replayed vectors are clearly labeled; they do not certify embedding/translation model quality or Gemini availability.
Tests that use the original corpus skip when the private database/BM25/metadata are absent; synthetic dataset-update and source/UI tests remain available.
