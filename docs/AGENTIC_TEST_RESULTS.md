# Integration verification evidence — 2026-10-19

> Historical implementation record: mandatory review and pilot answer gates below were superseded by [READY_UPDATE_BN.md](READY_UPDATE_BN.md). The current application automatically ingests readable sources after permission.

## What passed

Final command: `python -m pytest -q --tb=short -r s`.

Result: **139 passed, 19 skipped**. The exact output is included in `AGENTIC_PYTEST_OUTPUT.txt`. Python 3.12 on Linux; dependency versions are recorded in `AGENTIC_TEST_ENVIRONMENT.json`.

Seventeen new integration cases exercise the real application contracts and existing Stage 3/4/5/6 modules. Six additional tests cover the installer and environment parsing. The remaining passing tests cover the existing application, UI/session/CSRF, source/review interfaces and original processing components.

| Check | Evidence and scope |
|---|---|
| Existing answerable policy | Original two-stage retrieval + Stage 2 on a clearly synthetic policy fixture; answer without research |
| Genuine non-policy OOS | Original Stage 2 evaluator declines; orchestrator does not crawl |
| Known NID gap | Actual Stage 6 bridge/orchestrator returns a usable Election Commission research offer after stored search |
| Allow / deny / replay / expiry / session isolation | Fresh controller, one-use question/scope bindings; no crawl on deny or expiry; duplicated decision does not launch another job |
| Generalized official scope | Seven-authority registry; exact host checks reject suffix spoofing, arbitrary government hosts and unregistered subdomains |
| HTML + PDF | Actual Stage 3 crawler with synthetic HTTPS responses and a valid generated PDF; actual offline Stage 4 processors and provenance verification |
| Missing/unclear date, corrupt text and simulated OCR | Automatic update blocked; review required, original pair remains active |
| Human review resume | Original Stage 5 finalizer records reviewed decisions; the same job resumes without another crawl |
| Safe update | Actual ChromaDB 1.5.9 + rank-bm25 0.2.2; ORIGINAL Stage 6 append_candidate, pair verification and vector-hash primitives |
| Fresh-process queryability | Separate writer/reopen children; every new dense clause queried; exact dense/sparse consistency checked |
| Re-query | Original hybrid retrieval methods (BM25 + dense + RRF), original two-stage pipeline and evaluator; automatic original-question answer after activation |
| Partial writer interruption | Encoder failure after 32 real dense additions; sparse mismatch rejected; no READY or activation |
| Failure / cancellation / deadline | Candidate build failure, restart failure, research-only consent and cancellation do not update the active pair |
| Rollback | Forced post-activation re-query failure restores previous generation; damaged-current-candidate rollback also tested through explicit diagnostic CLI |
| Concurrent pointer changes | Compare-and-swap rejects a stale expected pointer; another generation is not silently overwritten |
| Provenance tampering | Changed raw source bytes invalidate the Stage 5→6 verification receipt |
| UI/API/PDF | Signed session and CSRF; consent/progress/final answer endpoints; preserved PDF.js path; exact saved PDF bytes returned from verified generation |
| Installer | Dry run, hash mismatch refusal, payload corruption rejection, idempotency, automatic undo after interrupted replacement, guarded restore |

The 384-D encoder is explicitly synthetic and exists only in `tests/agentic_fixture_worker.py`. The production entrypoint does not import it. The tests execute unchanged original retrieval class methods with this fixture to check plumbing, not semantic model quality. Synthetic source text is marked as fictional test material and is never added to the user's actual index.

## What was skipped

| Count | Missing asset |
|---|---|
| 6 | Original real Chroma/BM25 corpus, absent from uploaded code-only ZIP |
| 2 | Original corpus JSONL, absent from uploaded code-only ZIP |
| 8 | Archived Stage 4 captured pilot snapshot, absent from uploaded code-only ZIP |
| 3 | Original binary logos/font, absent from uploaded code-only ZIP |

These are **not passes**. The skips were made explicit; tests no longer create an empty original collection when the required real index is absent. Existing local copies of those assets are preserved by installation. Frozen pilot test datasets and source-review packages were not fabricated.

## Not executed / remaining real validation

- Windows Conda execution using the real accepted `reviewed_c02a1b74041d` 14,397-item generation.
- The user's actual SentenceTransformer model cache and model-file hash resolution.
- Actual NID/other government requests made by this application's crawler.
- Real scanned Bengali-page Tesseract/model execution, CER/WER or a large retrieval benchmark.
- End-to-end migration of the user's four original reviewed Stage 2 JSON files; they are excluded from the ZIP and must be copied from the existing complete local Stage 6 package. The configuration script checks their frozen hashes and refuses missing/changed files.

The small remaining validation is the setup/diagnostic and UI sequence in `START_AGENTIC_WINDOWS_BN.md`. No full index, model or raw-PDF upload is required.

## Preservation audit

Compared byte-for-byte with the uploaded source manifest:

- `reference_pipelines/`: 2,602 files unchanged.
- `scripts/retrieval/`: 15 files unchanged.
- `chatbot/`: 24 files unchanged.
- `scripts/ocr_pipeline/`: 6 files unchanged.
- `integrations/kg/`: 2 files unchanged.
- Live HTML templates and CSS: unchanged; `ui_preservation.json` records original hashes.

The installer independently validates unchanged borrowed runtime source hashes. The sealed runtime generation is validated separately by Stage 6 and was never available or modified in this environment.
