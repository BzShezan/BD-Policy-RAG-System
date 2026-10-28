# Stage 5/6 integration boundary (no automatic approval)

The original Stage 5 flow uses `stage5.workflow.stage_candidate` and separate `stage5.review.record_content_review`. `run_stage5_approve.py` explicitly records *content* approval only; index-import approval remains separate. Fresh browser crawl outputs cannot be treated as approved merely because OCR ran.

Accepted Stage 6 `run_stage6_update.py` loads the **frozen 54 reviewed H01–H03 clauses** using `stage6.approved.load_approved`. It is NOT a generic new-data incremental builder. Do not rerun it against the accepted workspace or try to inject new raw records in its approved files.

Future new-data adapter requirements:
1. Stage 3 raw provenance and immutable raw SHA-256 verified; Stage 4 extracted text and OCR review.
2. Reviewer approves each exact chunk and effective-date provenance; separate explicit index-import authorization.
3. Deduplicate and stage new corpus ONLY in newly named, isolated candidate pair; baseline generation and accepted generation remain sealed.
4. Build both ChromaDB & BM25 from the same logical ID list; verify count, IDs, hashes, embedding stability/consistency, metadata and benchmark/no-regression on DEV plus held-out.
5. Verify candidate restart, seal it, and require explicit promotion; `stage6.generations.switch` already provides atomic pointer/rollback. No browser activation without deliberate operator confirmation.
6. Use the unmodified `stage6.versions.source_versions(..., hook=teammate_adapter)` when the KG/contradiction module is ready. Annotation can never silently select a policy winner or approve index imports.

Output of this patch ends at review handoff; it does not claim that step 3–5 are implemented for fresh documents.
