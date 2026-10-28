# Unmochon Stage 1–6: শুধু Integration, নতুন pilot নয়

এটি existing application-এর জন্য **single-repo entrypoint**। সব নতুন code `G:\Capston\Unmochon`-এ থাকবে। এই tool পুরোনো Stage 1–6 algorithm পরিবর্তন, নতুন indexing, web crawling, consent অনুমোদন, policy verification, index activation বা rollback করবে না।

## বর্তমান যুক্ত থাকার মানচিত্র

| Stage | Existing implementation | app integration |
|--|--|--|
| 1. OCR/extraction/retrieval baseline | `scripts/` + `reference_pipelines/stage1_*` | Original extraction/retrieval features, Stage6 verified hybrid bridge |
| 2. Evidence/permission gate | `stage6_bridge.py`, Stage2 source | App orchestrator, research trigger |
| 3. Government crawl | `research_flow.py`, Stage3 code | UI fresh one-use scoped consent; NO silent crawler |
| 4. HTML/PDF processing | `stage4_dynamic.py`, Stage4 original source | Stage3 snapshot verified, app process endpoint |
| 5. Human review | `scripts/stage5_prepare_review.py`, `stage5_finalize_review.py` | CLI/offline review, NOT yet one-click fully embedded in UI |
| 6. Controlled pair generation | `stage6_bridge.py`, original Stage6 `generations.py` | Verified existing generation **query**, original pilot update/rollback code is retained; generic new-evidence updater NOT wired to UI |

**Important:** Stage 1–6 code present in one repo is different from tested self-contained runtime. External checksum-sealed stage4/stage6 working folders and accepted index remain on Windows until a separate data migration is explicitly planned. Do not move them now.

## Windows — one folder, no new project directories

Unzip the package anywhere temporary and use the add-only installer. For example:

```powershell
cd G:\Capston\Unmochon
conda activate unmochon_stage1
python .\scripts\unmochon_pipeline.py doctor
python .\scripts\unmochon_pipeline.py test
python .\scripts\unmochon_pipeline.py serve
```

`doctor` reads six-stage code presence, Stage4/Stage6 external runtime paths, and reads `active.json` **without verifying the full sealed index**. It does not contact the network or change the index.

`serve` invokes the existing Live UI in local Stage6 mode; it refuses to run if `RAG_BACKEND=stage6`, `APP_ENV=local`, `ENABLE_WEB_SEARCH=false`, Stage6 query script, or `active.json` are missing. Research crawler network access is possible only after fresh question-bound in-app consent.

To query from CLI (existing app):

```powershell
python .\scripts\unmochon_pipeline.py ask 'ভিজিএফ উপকারভোগীর যোগ্যতার শর্তগুলো কী?'
```

To prepare a fresh Stage5 review, use `review-prepare --stage4 ... --snapshot ... --package ... --output ...` with your actual output paths; `review-finalize --review-dir ... --decisions ... --package ...` to record it. These commands call the *existing* Stage5 scripts and cannot directly approve index import.

## What remains intentionally separate

- Stage5 review decisions are not an import permit.
- Stage6 standalone pilot's `run_stage6_update.py` is not automatically called by this entrypoint. It was designed for a fixed accepted dataset; blindly using it for any new crawl is unsafe.
- App review UI for Stage5 and automated general-purpose index promotion are not claimed complete.
- KG / contradiction interface remains inactive, for teammate later.
- Source date/OCR correction and larger benchmarks are **deferred**, not blockers for the Stage1–6 code/runtime integration check.

No new network consent, no index writes or pointer changes occur in the installer, `doctor` or `test`.
