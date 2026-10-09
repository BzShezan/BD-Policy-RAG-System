# Merge validation

Validated on Python 3.12.14 with ChromaDB 1.5.9. The supplied raw policy PDFs, trained LiLT checkpoints and cached embedding/translation models were not present in this environment.

## Passed

- **56 Python tests**: original Live regressions plus merge checks, and real digital-PDF extraction/chunk bounding boxes.
- JavaScript syntax and shipped-renderer checks: original extraction/explanation slots, official source and exact PDF links, original conflicts, escaped source text and unsafe-URL rejection.
- Original ChromaDB loads; collection contains **15,019 records**. BM25 also has 15,019 IDs, with exact ID-set equality.
- Real original clauses pass through original query expansion, BM25+dense/RRF, two-stage ranking, original NER, original templates, original extractive answers and Live API serialization. All returned clause text/metadata matches database records.
- Out-of-scope sentinel remains an out-of-scope result with no invented evidence or automatic web escalation.
- Original PDF sentence-boundary search URL targets the exact requested page and highlighted phrase. Original PDF.js viewer/build routes are available. Missing PDFs return no viewer URL.
- Original date-aware conflict function and frontend renderer retained.
- Incremental update exercises **real Chroma upsert + original BM25 rebuild in a separate process**, addition, identical-input idempotency, complete incoming metadata retention, processed-JSONL verified lookup, backup, staging failure and writer lock.
- **14 Live visual files** (templates, CSS, fonts and logos) match the uploaded Live bytes exactly. Only JavaScript result wiring changed. Hashes: `ui_preservation.json`.
- Original BM25, metadata JSON and metadata workbook retained unchanged. The database and original explanation cache were restored to the exact input bytes after tests. Hashes: `original_data_checksums.json`.
- All original source feature directories retained; the one code utility inside an omitted historical dataset backup is preserved as `scripts/debugging/original_backup_check_review.py`.
- Editable packaging installation succeeds; declared dependency resolution was checked. Python sources compile and JavaScript parses.

## Scope of model tests

The real-corpus retrieval test **replays a stored corpus embedding**, and the isolated updater test uses deterministic synthetic vectors. This tests Chroma/HNSW, fusion, sparse indexing, filtering and the pipeline, but **does not validate the embedding model on a new query or the semantic quality of dense retrieval**. English-query orchestration uses a test translator; NLLB's original translation implementation and dictionaries are retained, but model inference was not executed here.

The digital-PDF OCR test runs the original digital extraction and chunker against a real generated test PDF. Scanned policy PDF Tesseract/Apsis recognition and trained LiLT inference were not executed. Gemini calls and model availability were not verified. Browser pixel rendering was not performed; layout preservation is verified by asset-byte equality, existing UI server tests and renderer tests.

## Assets needed for full local verification

1. The same original embedding and NLLB models (download once or configure local copies).
2. Original raw policy PDFs under `data/raw_pdfs/` for source-PDF viewing/highlighting.
3. Original trained layout checkpoint for LiLT inference, plus OCR tools/language data for scanned PDFs.
4. Optional private Gemini key/model access for remote refinement; original template fallback works without it.

Duplicate historical backup datasets/databases are omitted from this runnable ZIP; the supplied Original Source archive remains the reference for them. No production data was ingested during testing. Docker configuration is supplied but a Docker build was not executed in this environment.

## Source-only GitHub checkout

The checks above describe the original private merged package. GitHub publishes its source code and UI assets; the database, BM25, chunk datasets, document metadata, policy PDFs, layout data/checkpoints and generated reports are excluded. Supply those private assets locally before running corpus-dependent checks. See `GITHUB_DISTRIBUTION.md` for the source-only setup and verification.
