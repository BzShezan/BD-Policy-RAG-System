# Unmochon — Single Repository (working migration)

**Root:** `G:\Capston\Unmochon`

The existing Live UI/app is the primary application. Research agents, indexing code,
benchmark tools and teammate KG interface are kept in this single CODE repository.
Runtime research outputs, ChromaDB, BM25, PDF archives and models remain on the local
drive, outside Git. See `docs/MIGRATION_STATUS_BN.md`.

Stage code in `reference_pipelines` is preserved for subsequent import/path refactoring.
Do not delete or move any old folders until independent end-to-end and rollback tests pass.
