# Exact changed and new files

Compared with the uploaded `Unmochon.zip`. The installer changes only these files; no source deletion is included. Tests with missing runtime assets explicitly skip instead of manufacturing data.

| File | Type | Purpose |
|---|---|---|
| `.env.example` | changed | Portable configuration and explicit job/model/OCR settings. |
| `README.md` | changed | Current integration entrypoint and honest test/runtime scope. |
| `config/research_sources.json` | new | Versioned scopes for original three ministries and four government service authorities. |
| `docs/AGENTIC_INTEGRATION_BN.md` | new | Architecture, setup, authority evidence, preservation or exact test results. |
| `docs/AGENTIC_PYTEST_OUTPUT.txt` | new | Architecture, setup, authority evidence, preservation or exact test results. |
| `docs/AGENTIC_TEST_ENVIRONMENT.json` | new | Architecture, setup, authority evidence, preservation or exact test results. |
| `docs/AGENTIC_TEST_RESULTS.md` | new | Architecture, setup, authority evidence, preservation or exact test results. |
| `docs/REGISTRY_AUTHORITY.md` | new | Architecture, setup, authority evidence, preservation or exact test results. |
| `docs/START_AGENTIC_WINDOWS_BN.md` | new | Architecture, setup, authority evidence, preservation or exact test results. |
| `docs/ui_preservation.json` | new | Architecture, setup, authority evidence, preservation or exact test results. |
| `scripts/agentic_diagnostic.py` | new | Read-only verification/query plus explicit manual complete-pair rollback. |
| `scripts/configure_agentic.py` | new | One-time hash-checked metadata/config migration with .env backup; no index mutation. |
| `scripts/install_agentic_patch.py` | new | Dry-run/hash checked code installation, backup, guarded restore and failure undo. |
| `scripts/stage5_finalize_review.py` | changed | Support package import as well as the unchanged direct review CLI. |
| `scripts/unmochon_pipeline.py` | changed | Include new workflow and installer tests in the existing unified test entrypoint. |
| `src/unmochon_live/agentic_worker.py` | new | Original hybrid/Stage2 query + generalized original Stage6 candidate build and fresh-process reopen. |
| `src/unmochon_live/api.py` | changed | Cancel/finish research safely during app shutdown. |
| `src/unmochon_live/config.py` | changed | Bundled code defaults, preserved runtime paths, bounded job settings. |
| `src/unmochon_live/controlled_update.py` | new | Candidate handoff, preserved sources, CAS activation and guarded paired rollback. |
| `src/unmochon_live/doctor.py` | changed | Read-only Stage6 generation and registry diagnostics. |
| `src/unmochon_live/evidence_verification.py` | new | Stage5 question/source/date/quality criteria, original human receipt and independently revalidated import receipt. |
| `src/unmochon_live/orchestrator.py` | changed | Search known services first; classify bounded evidence gaps without implicit crawl. |
| `src/unmochon_live/research_flow.py` | changed | One consented job across Stage3–6, progress/review/cancel/re-query/rollback. |
| `src/unmochon_live/research_registry.py` | new | Extend Stage3 immutable exact-host registry without changing frozen scope rules. |
| `src/unmochon_live/runtime.py` | new | Verify frozen runtime Python sources while keeping archived full-pilot validators unchanged. |
| `src/unmochon_live/stage4_dynamic.py` | changed | Reuse extraction/provenance with application registry, code-only guard and English service PDFs. |
| `src/unmochon_live/stage6_bridge.py` | changed | Route to offline app worker; preserve original result fields and verified PDF links. |
| `src/unmochon_live/ui.py` | changed | Wire consent/update disclosure, progress, cancellation, content review and exact saved PDF endpoints. |
| `src/unmochon_live/ui/static/app.js` | changed | Existing visual shell: disclose permission, poll full job, review uncertain evidence, render final answer. |
| `tests/agentic_fixture_worker.py` | new | Real-pair/offline end-to-end coverage; fake network and synthetic encoder confined to tests. |
| `tests/test_agentic_installer.py` | new | Real-pair/offline end-to-end coverage; fake network and synthetic encoder confined to tests. |
| `tests/test_agentic_integration.py` | new | Real-pair/offline end-to-end coverage; fake network and synthetic encoder confined to tests. |
| `tests/test_current_merge_contract.py` | changed | Update the intentional known-service routing contract or expose missing runtime asset skips; preserve regression checks. |
| `tests/test_original_merge.py` | changed | Update the intentional known-service routing contract or expose missing runtime asset skips; preserve regression checks. |
| `tests/test_pipeline.py` | changed | Update the intentional known-service routing contract or expose missing runtime asset skips; preserve regression checks. |
| `tests/test_research_http_pdf.py` | changed | Update the intentional known-service routing contract or expose missing runtime asset skips; preserve regression checks. |
| `tests/test_research_workflow.py` | changed | Update the intentional known-service routing contract or expose missing runtime asset skips; preserve regression checks. |
| `tests/test_stage6_bridge.py` | changed | Update the intentional known-service routing contract or expose missing runtime asset skips; preserve regression checks. |
| `tests/test_ui.py` | changed | Update the intentional known-service routing contract or expose missing runtime asset skips; preserve regression checks. |
| `docs/AGENTIC_CHANGED_FILES.md` | new | This exact change/purpose inventory. |
