# Original feature map

| Feature | Reused source | Integration |
|---|---|---|
| OCR, quality, boxes, tables, chunking | `scripts/ocr_pipeline/`, `scripts/1_batch_pipeline.py` | Original processing code, portable input/output settings |
| Layout datasets, training, inference | `layout_analysis/` | Original code retained; trained checkpoint must be supplied |
| Hybrid retrieval | `scripts/retrieval/search.py` | Original BM25+dense+RRF; imports/config namespaced; empty DB and compound metadata filters made Chroma compatible |
| Query expansion/tokenization | `query_expansion.py`, `tokenize_bn.py` | Original algorithms retained |
| English/Bengali translation | `translator.py` | Original NLLB flow and dictionaries; model loading remains lazy |
| Two-stage search | `two_stage.py` | Original ranking/intent/OOS algorithm unchanged |
| NER, normalization, intent | `chatbot/scripts/ner.py`, `normalize.py`, `intent.py` | Original extractors/classifier reused |
| Confidence, extractive answers | `confidence.py`, `answer_generator.py` | Original gating and sentence answers reused |
| Verified clause lookup | `verified_lookup.py` | Original direct lookup retained; portable processed JSONL/PDF paths |
| Explanations | `explainer.py` | Original cache/template/LLM refinement; private env key; model setting configurable |
| Exact clause and PDF source | `UI/app.py` helpers, `UI/static/pdfjs/` | Original sentence-search viewer URL and PDF.js served from Live |
| Date-aware conflicts | `UI/app.py:detect_conflicts`, original JS renderer | Original algorithm and markup reused |
| Metadata/dates | private original workbook, JSON, Chroma fields, `DATE_eXTRACTION/` | Metadata processing code retained; private metadata stays local; API exposes full per-clause and per-document objects |
| Existing UI | Live templates/CSS/fonts/logos; original `UI/` retained | Default Live visual assets unchanged; result data wiring adapted |
| Dataset updates | original `collect_clauses`, `group_table_rows`, `build_bm25` | New offline staging/commit wrapper reuses original filters/indexer; stable IDs, backups and same embedding model |

`src/unmochon_live/original.py` adapts the original query payload to Live's evidence schema. `base_orchestrator.py` runs that engine only. The prior baseline/web modules remain available as legacy code but do not run in the default `RAG_BACKEND=original` mode. Future agent integration is separate.

No new clause extractor, PDF highlighter, policy answer generator or source-link lookup implementation replaces the original features.
