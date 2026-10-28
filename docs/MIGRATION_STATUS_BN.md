# Unmochon unified workspace — Migration phase A

This is a **new source-only working tree**, built from the current Windows `Unmochon_Live`.
Existing app, Stage 1–6 folders, accepted generation and backups were NOT edited.

- Main application: `src/unmochon_live/`, `UI/`, `chatbot/`, `scripts/` (where present).
- Source-only preserved stage code: `reference_pipelines/stage*/`.
- External sealed runtime (Stage 3/4 source checksum and Stage 6 active index) remains at original paths in `.env.example`.
- Current working app research patch status at build: **apply-to-new-tree**.
- Total source files copied from local folders: **3052**.
- Research UI, consent, crawler and Stage 4 processing still need Windows regression tests.
- Stage 5 arbitrary newly approved content -> Stage 6 general paired index update **not yet implemented**.
- KG / contradiction code **not installed**; `integrations/kg/adapter.py` is a NO-OP placeholder; see `KG_TEAMMATE_PORT.md`.
- Existing `stage6_candidate_local/active.json`, ChromaDB, BM25, model cache remain EXTERNAL/read-only.
- Source in `reference_pipelines` is an archive of code, not necessarily executable in isolation: checksum seals rely on excluded source assets.
- No network crawl, source approval, index promotion or production deployment is performed by migration.

## First run (PowerShell)

```powershell
conda activate unmochon_stage1
cd G:\Capston\Unmochon
Copy-Item .env.example .env    # ONLY if .env does not exist; inspect and customize it
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
python -m pytest -q tests/test_stage6_bridge.py tests/test_current_merge_contract.py tests/test_research_workflow.py tests/test_research_http_pdf.py
python -m unmochon_live ask 'ভিজিএফ উপকারভোগীর যোগ্যতার শর্তগুলো কী?' --json
python -m unmochon_live serve
```

Do not push to GitHub until you review `git status`, test, audit for secrets, and ensure `.env` / indexes are ignored.
