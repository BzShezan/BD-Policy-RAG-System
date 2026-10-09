# Source-only GitHub distribution

GitHub contains the merged source, original PDF.js renderer source/assets and unchanged Live visual assets. Private ChromaDB/HNSW, BM25, processed/incoming chunks, metadata workbook/JSON, policy PDFs, layout datasets/checkpoints and generated outputs stay local.

The application is under `Unmochon_Live/`; earlier root-level processing scripts and Git history are retained. Previously tracked root datasets are removed from the current file tree. The unpublished database-bundle commit is not part of the pushed commit's parent chain.

Setup creates `.env` without rebuilding or downloading data. Copy the existing private data into `Unmochon_Live/data/`, or configure its paths individually in `.env`. Docker builds exclude private files; mount data when running a container. The original incremental updater still operates on your private local database and preserves the original retrieval/metadata schema.

Validation for this source-only distribution checks that:

- The proposed Git tree contains no database, BM25, dataset, workbook, archive-part, credential or policy-PDF files.
- Private local files retain their original checksums; the `unmochon_clauses` collection still has 15,019 records.
- All 14 Live template, CSS, font and logo checksums match `ui_preservation.json`.
- Setup works in a source-only checkout and retains existing configuration on repeated runs.
- Corpus-dependent tests skip when private corpus files are absent; model runtime limits remain documented in `MERGE_VALIDATION.md`.

Existing published Git history is not rewritten. Removing older root datasets from the current tree does not remove them from historical commits.

Verified in a checkout containing no private data: **43 pipeline/UI tests passed, 2 private-corpus tests skipped**; renderer checks and first-run/repeated-run setup checks passed. All 193 tracked Python files parsed. The 19 private original data/index checksum entries and 14 Live visual asset checksum entries matched. The full embedding/translation model stack was not rerun for this distribution change.
