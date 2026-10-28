# Unmochon — Bangladesh Government Policy Research Assistant

> **Project:** Unmochon  
> **Purpose:** Help users find answers to questions about Bangladesh government policies using retrieved policy clauses and cited evidence, with a permission-based government-research path for questions that are outside the existing indexed coverage.

This README is the onboarding guide for developers and teammates. It describes the intended system, local setup, a Cloudflare Tunnel demo, the main known code areas, and the remaining work. Because local datasets, environment files, and the latest GitHub tree can differ, **always verify the paths and commands in the checked-out branch before treating a step as confirmed**.

---

## Contents

- [1. Project overview](#1-project-overview)
- [2. How the system is intended to work](#2-how-the-system-is-intended-to-work)
- [3. Current integration context](#3-current-integration-context)
- [4. Repository areas](#4-repository-areas)
- [5. Requirements](#5-requirements)
- [6. Run locally on a new Windows device](#6-run-locally-on-a-new-windows-device)
- [7. Run a temporary public demo with Cloudflare Tunnel](#7-run-a-temporary-public-demo-with-cloudflare-tunnel)
- [8. Tests and verification](#8-tests-and-verification)
- [9. Remaining team tasks](#9-remaining-team-tasks)
- [10. Documentation guide](#10-documentation-guide)
- [11. Data, secrets, and Git policy](#11-data-secrets-and-git-policy)
- [12. Troubleshooting](#12-troubleshooting)
- [13. Suggested teammate workflow](#13-suggested-teammate-workflow)

---

## 1. Project overview

Unmochon is an evidence-focused policy research assistant for Bangladesh government policy and public-benefit information. The goal is to make answers traceable to source documents instead of presenting unsupported model-generated claims.

The project brings together the existing policy-retrieval application and an agentic research workflow. The intended merged system preserves the established retrieval features while adding an out-of-scope (OOS) research path.

### Main goals

- Retrieve relevant policy clauses from a local index.
- Use hybrid retrieval (vector search with ChromaDB and BM25 keyword retrieval where configured).
- Detect when the available indexed evidence is not sufficient for a question.
- Ask the user for permission before starting external government research.
- Search relevant official Bangladesh government websites, retrieve pages/PDFs, extract and chunk their content, and preserve source metadata.
- Make researched evidence available to retrieval through the controlled indexing workflow.
- Return a final answer grounded in retrieved evidence and source references.
- Keep the app runnable without the teammate-owned knowledge-graph/contradiction component, using the adapter boundary where supported.

### Important scope note

The workflow above is the **intended end-to-end behavior**, not a guarantee that every stage is currently production-ready on every machine. Confirm the live app, configured index, permission gate, research path, indexing policy, and final citations using the checks in this README before presenting a demo or claiming a stage is complete.

---

## 2. How the system is intended to work

```text
User question
     |
     v
Existing retrieval (ChromaDB + BM25, where configured)
     |
     v
Evaluate relevance / determine whether evidence is sufficient
     |
     +---- Evidence sufficient -------------------------------+
     |                                                       |
     |                                                       v
     |                                         Evidence-grounded answer
     |
     +---- Out of scope / insufficient evidence
                         |
                         v
                Ask user for permission
                         |
                 +-------+-------+
                 |               |
              Decline          Approve
                 |               |
          Do not crawl           v
                           Research official
                           government sources
                                  |
                                  v
                         Fetch HTML pages and PDFs
                                  |
                                  v
                       Extract text / OCR as needed
                                  |
                                  v
                         Chunk + metadata + dedupe
                                  |
                                  v
                     Controlled ChromaDB/BM25 update
                                  |
                                  v
                        Retrieve new evidence
                                  |
                                  v
                      Final answer + source references
```

### Expected safety and evidence behavior

1. **Consent first:** external crawling should not begin before the user approves the research request.
2. **Official-source priority:** prefer relevant official government domains, especially `.gov.bd`, and preserve source URLs and document metadata.
3. **Evidence before explanation:** answers should be supported by retrieved clauses or researched source chunks.
4. **Traceability:** preserve source links and, where available, document title, page/section, dates, and other metadata.
5. **Controlled indexing:** do not overwrite the active ChromaDB generation or bulk-import candidate evidence without checking the project's current Stage 5/Stage 6 authorization and rollback rules.
6. **No false success:** if retrieval, scraping, OCR, or indexing fails, report the limitation rather than pretending evidence was added.

---

## 3. Current integration context

The unified repository has been developed around the local project root:

```text
G:\Capston\Unmochon
```

The integration work has included an application entry point and research workflow, a Stage 6 bridge, a knowledge-graph adapter boundary, and reference/test pipelines. Earlier integration checks reported successful source-integrity checks and passing focused test suites, but those results are historical and should be rerun against the latest commit.

Known code areas from prior integration work include:

- `src/unmochon_live/cli.py`
- `src/unmochon_live/research_flow.py`
- `src/unmochon_live/stage6_bridge.py`
- `integrations/kg/adapter.py`
- `reference_pipelines/stage4/stage3/consent.py`
- `reference_pipelines/stage6/stage6/generations.py`
- `benchmarks/independent/score_retrieval.py`
- `.env.example`

**Do not assume these paths are unchanged.** Check the latest branch with the commands in [Repository inspection](#repository-inspection).

### Known integration considerations

- The live app and research flow must use the intended merged retrieval implementation.
- The active runtime index may be separate from source code and may not have been migrated with the repository.
- Python packages and environment variables can differ between Conda environments.
- The knowledge-graph/contradiction work is a teammate integration point; the base application should degrade gracefully if that optional component is not configured.
- Stage 5/Stage 6 controls are important. Verify the current policy before enabling automatic imports into the active index.

---

## 4. Repository areas

The following describes the **known intended areas**. Use the actual checked-out tree as the source of truth.

| Path / area | Intended responsibility |
|---|---|
| `src/unmochon_live/` | Main application package and runtime entry points. |
| `src/unmochon_live/cli.py` | CLI commands / application launch integration, subject to the current implementation. |
| `src/unmochon_live/research_flow.py` | Permission-led out-of-scope research orchestration. |
| `src/unmochon_live/stage6_bridge.py` | Connects the app/research workflow to the controlled Stage 6 index-update flow. |
| `integrations/kg/adapter.py` | Adapter boundary for teammate-owned knowledge-graph or contradiction integration. |
| `reference_pipelines/stage4/` | Evidence processing / consent-related reference workflow. |
| `reference_pipelines/stage6/` | Controlled index-generation and update logic. |
| `benchmarks/independent/score_retrieval.py` | Independent retrieval-scoring / benchmark utility. |
| `.env.example` | Example environment configuration; inspect it for required variable names. |
| `tests/` or test files named below | Automated regression checks. Actual test locations may vary by branch. |
| `data/`, `storage/`, ChromaDB paths | Local data/index locations, if present; do not assume the database is included in Git. |

### Repository inspection

Run from the repository root in PowerShell:

```powershell
git status --short --branch
git log -5 --oneline
Get-ChildItem -Force
Get-ChildItem -Recurse -File -Filter "*.md" |
  Select-Object -ExpandProperty FullName
Get-ChildItem -Recurse -File -Filter "pyproject.toml"
Get-ChildItem -Recurse -File -Filter "requirements*.txt"
Get-ChildItem -Recurse -File -Filter ".env.example"
Get-ChildItem -Recurse -File -Filter "run_unmochon.py"
```

To inspect a folder without printing every file:

```powershell
Get-ChildItem .\src\unmochon_live -Recurse -File |
  Select-Object FullName
```

If a path listed in this README does not exist in the current branch, do not create a duplicate just to match the documentation. Find the current entry point and update this README after confirming the architecture.

---

## 5. Requirements

For the previously tested Windows setup, the project used a Conda environment named `unmochon_stage1`, Python 3.12.x, and `PYTHONPATH=src`. A separate learning project used Python 3.14; **do not use that learning project's Python version as the assumed runtime for Unmochon**.

Recommended starting point:

- Windows 10/11
- Git
- Miniconda or Anaconda (if using the known Conda setup)
- Python version compatible with the checked-out project's dependencies (historically Python 3.12.x)
- The project dependency manifest, if present (`requirements.txt`, `pyproject.toml`, or environment file)
- Tesseract OCR installed and available on `PATH` if the PDF OCR path requires it
- Access to any required API provider only if the current `.env.example` and code require it
- A local copy of the required policy index/data if it is not tracked in Git

Do not commit API keys, `.env` files containing secrets, private user data, or the ChromaDB runtime database to GitHub.

---

## 6. Run locally on a new Windows device

### Step 1 — Clone the repository

Replace the URL below if the repository owner/name or clone URL differs in the latest GitHub project.

```powershell
git clone <YOUR_UNMOCHON_GITHUB_REPOSITORY_URL>
cd Unmochon
```

If the folder is cloned under another name, enter that folder instead. The repository URL must be copied from the GitHub **Code → HTTPS** button; do not guess it.

### Step 2 — Create/activate the Conda environment

If the project provides an `environment.yml`, follow that file first. Otherwise, the historical environment name was `unmochon_stage1`.

```powershell
conda create -n unmochon_stage1 python=3.12 -y
conda activate unmochon_stage1
python --version
```

If the environment already exists:

```powershell
conda activate unmochon_stage1
```

### Step 3 — Install dependencies

First inspect the repository root:

```powershell
Get-ChildItem -Force
```

Use the dependency manifest that actually exists. For example:

```powershell
# Run only if requirements.txt exists at the repository root:
python -m pip install -r requirements.txt
```

If the project uses `pyproject.toml`, use the installation instructions defined there instead. Do not install several competing dependency sets blindly.

### Step 4 — Configure environment variables

If `.env.example` exists:

```powershell
Copy-Item .env.example .env
notepad .env
```

Fill in only the values required by the current code. Check the configuration for:

- Application/backend selection
- Local workspace or Stage 6 candidate directory
- ChromaDB/index path and collection name
- Optional model/API settings
- OCR executable path, if needed
- Any source/research limits

Never copy another developer's API key. Never upload `.env` to GitHub.

### Step 5 — Set Python paths and UTF-8 output

From the repository root, in the same PowerShell terminal:

```powershell
$env:PYTHONPATH = "$PWD\src"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
```

The UTF-8 settings help avoid Windows console encoding errors when Bangla text or Unicode symbols are printed.

If the Stage 4 evidence-processing package is stored separately on your machine, set `STAGE4_PACKAGE` only if the current code expects it. Example from the previous local setup:

```powershell
$env:STAGE4_PACKAGE = "G:\Capston\Unmochon_Stage4_Evidence_Processing"
```

That path is machine-specific. On a new device, locate the corresponding package in the current checkout and use its actual path; do not copy the `G:\` path blindly.

### Step 6 — Check the runtime index/data

The Git repository may contain source code without containing the active ChromaDB database. Before running the app, confirm that the configured index path exists and contains the expected collection/data.

- Check `.env` and the retrieval configuration for the configured path.
- Confirm the correct collection name and embedding/model configuration.
- Use the project's index validation or preflight command if available.
- Do not point a test run at a valuable active database until you understand whether the command can write to it.
- If the database must be transferred, use the project's documented backup/restore procedure; do not upload the database to GitHub.

### Step 7 — Start the application

The previous integration used this launch command from the repository root:

```powershell
python -m unmochon_live serve
```

If that command is not available in the latest commit, inspect the CLI help and current entry point:

```powershell
python -m unmochon_live --help
```

The repository has also previously used a root-level launcher:

```powershell
python .\run_unmochon.py
```

Use the launcher that exists in the current branch and is documented by its help/output. Do not run both at once. A previous local run printed:

```text
Unmochon: http://127.0.0.1:8000
```

When the server starts, open the local address printed by the application (historically `http://127.0.0.1:8000`) in your browser.

Keep this terminal open while using the application. Stop the server with `Ctrl+C`.

---

## 7. Run a temporary public demo with Cloudflare Tunnel

Cloudflare Tunnel can expose the local app to a temporary public URL without deploying the app to a paid server. This is useful for a short teammate/supervisor demo, but it is **not a production deployment**.

### Before starting

1. Confirm the app works locally first.
2. Confirm the server is listening on the expected port (historically `8000`).
3. Do not expose an app containing secrets, private data, debug consoles, or unrestricted write/admin actions.
4. Remember that anyone who gets the temporary URL may be able to access the exposed app. Share it only with intended testers and stop the tunnel after the demo.

### Step A — Terminal 1: start Unmochon

Open PowerShell in the repository root:

```powershell
conda activate unmochon_stage1
$env:PYTHONPATH = "$PWD\src"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

python -m unmochon_live serve
```

If the current checkout uses `run_unmochon.py` instead, use that verified launcher. Wait until the server reports that it is running locally.

### Step B — Terminal 2: start Cloudflare Tunnel

Open a **second** PowerShell terminal. Keep Terminal 1 running.

Check that Cloudflare Tunnel is installed:

```powershell
cloudflared --version
```

If Windows says the command is not recognized, install Cloudflare's official `cloudflared` client using the current official Cloudflare installation instructions, then reopen PowerShell. If it was installed but is not on `PATH`, locate the executable and use its full path.

Start a temporary quick tunnel to the local app:

```powershell
cloudflared tunnel --url http://127.0.0.1:8000
```

### Step C — Find and share the URL

In Terminal 2, look for a line similar to:

```text
https://some-generated-name.trycloudflare.com
```

The exact generated hostname will be different each time. Copy the complete `https://...trycloudflare.com` address and send it to your testers.

If the URL is not visible:

- Maximize Terminal 2.
- Scroll to the most recent output.
- Look for `trycloudflare.com`.
- Wait for the tunnel to finish connecting.
- Check that Terminal 1 is still running and that `http://127.0.0.1:8000` opens locally.
- Check the tunnel error messages before trying again.

### Step D — End the demo

When finished:

1. Stop Cloudflare Tunnel in Terminal 2 with `Ctrl+C`.
2. Stop Unmochon in Terminal 1 with `Ctrl+C`.

A Quick Tunnel URL is temporary and may change on the next run. Do not treat it as a permanent deployment URL. For a longer-lived public service, configure a named tunnel and appropriate access controls using Cloudflare's official documentation.

---

## 8. Tests and verification

Run checks from the repository root, with the project environment activated.

### Inspect available tests

```powershell
Get-ChildItem -Recurse -File |
  Where-Object { $_.Name -match '(^test_.*\.py$|.*_test\.py$)' } |
  Select-Object -ExpandProperty FullName
```

Earlier integration work used focused tests with these names:

```powershell
python -m pytest
```

If the full suite is too large or the project defines a specific test command, run the documented suite. Earlier known test areas included:

- `test_stage6_bridge.py`
- `test_current_merge_contract.py`
- `test_research_workflow.py`
- `test_research_http_pdf.py`

Find their actual paths before running them. Example:

```powershell
Get-ChildItem -Recurse -File -Include `
  test_stage6_bridge.py, `
  test_current_merge_contract.py, `
  test_research_workflow.py, `
  test_research_http_pdf.py
```

Then pass the actual paths to pytest, for example:

```powershell
python -m pytest <actual-test-paths>
```

### Manual end-to-end checklist

- [ ] App starts and local UI loads.
- [ ] An in-scope policy query retrieves relevant existing policy evidence.
- [ ] The answer contains source references and does not invent a clause.
- [ ] An out-of-scope query triggers the expected permission prompt.
- [ ] Declining permission does not start external crawling.
- [ ] Approving permission starts the configured government-source research flow.
- [ ] HTML and PDF sources are handled; OCR runs when required and available.
- [ ] Extracted chunks retain source URLs and metadata.
- [ ] Deduplication and evidence checks behave as designed.
- [ ] Index changes follow the current Stage 5/Stage 6 authorization and rollback rules.
- [ ] Newly indexed evidence can be retrieved for a follow-up question.
- [ ] Final answer cites the retrieved/researched evidence.
- [ ] Logs/errors do not reveal API keys or private information.
- [ ] The app remains usable when the optional KG adapter is unavailable.

A passing unit test does not by itself prove the live index is correct or that the complete public-demo workflow works. Run both automated and manual checks.

---

## 9. Remaining team tasks

Use this list as a handoff checklist. Assign an owner and record the verification evidence for each item. Some items may already have been completed after this README was drafted; check the current code and test results before duplicating work.

### A. Retrieval and original behavior

- [ ] Compare the merged retrieval path against the original Unmochon source behavior.
- [ ] Confirm hybrid vector + BM25 retrieval is used where intended.
- [ ] Verify PDF clause/source-link/metadata display and any original OCR/extractor functionality.
- [ ] Run a representative benchmark for in-scope queries, false-OOS cases, and source accuracy.
- [ ] Confirm the configured ChromaDB collection and BM25 corpus refer to consistent document generations.

**Deliverable:** retrieval regression report with queries, expected evidence, actual results, and known gaps.

### B. Permission-led government research

- [ ] Verify the permission prompt is shown before any external request or crawl.
- [ ] Verify declining permission stops the research flow.
- [ ] Test official government page discovery and URL handling.
- [ ] Test HTML, PDF download, extraction, and OCR fallback.
- [ ] Preserve source URLs, document titles, timestamps and page/section information where available.
- [ ] Test timeouts, broken links, empty documents, unsupported files, duplicate sources and network failures.
- [ ] Add clear UI status messages so users can tell what the agent is doing.

**Deliverable:** end-to-end test report and a list of unsupported source formats.

### C. Evidence quality and index updates

- [ ] Verify chunk boundaries, metadata, deduplication and source attribution.
- [ ] Verify the current Stage 5/Stage 6 preflight, authorization, backup, generation consistency and rollback behavior.
- [ ] Confirm whether the latest accepted workflow allows automatic imports. Do not assume older Stage 5 review/Stage 6 authorization rules have changed unless the current code and accepted project decision prove it.
- [ ] Test index updates against a disposable candidate generation before any active-index change.
- [ ] Verify BM25 is updated consistently with ChromaDB.
- [ ] Verify the final answer retrieves the newly added evidence after an approved update.

**Deliverable:** reproducible index-update report including preflight, before/after counts, consistency checks and rollback test.

### D. Knowledge graph and contradiction integration

- [ ] Teammate to complete the KG/contradiction component and document its input/output contract.
- [ ] Connect it through `integrations/kg/adapter.py` or the current adapter path instead of tightly coupling it to the UI.
- [ ] Add tests for missing KG configuration, unavailable service, malformed output and contradictory evidence.
- [ ] Ensure the base application still runs when the optional integration is absent.
- [ ] Define how conflicts between official sources are surfaced rather than silently choosing one.

**Deliverable:** adapter contract, integration tests and a short demo.

### E. UI and final-answer quality

- [ ] Check in-scope and OOS interactions end-to-end.
- [ ] Verify the permission approval/cancel buttons and loading/error states.
- [ ] Verify answers include clear source links and do not claim unsupported eligibility or benefit amounts.
- [ ] Check Bangla and English text rendering, Unicode output and PDF-related UI behavior.
- [ ] Test a fresh session and follow-up questions after research.

**Deliverable:** screenshots or a short demo recording plus the test cases used.

### F. Fresh-machine setup and demo readiness

- [ ] Confirm a new developer can install dependencies from documented files.
- [ ] Document how the required index/data is obtained without putting it in Git.
- [ ] Test the actual launcher and port on a clean environment.
- [ ] Test the Cloudflare Quick Tunnel from a second device/network.
- [ ] Ensure debug mode, secrets and write-capable admin routes are not exposed.
- [ ] Add a concise known-issues list and update this README after verification.

**Deliverable:** clean-machine setup log and a demo checklist.

---

## 10. Documentation guide

Markdown documentation may change between branches. List the actual files before relying on a filename:

```powershell
Get-ChildItem -Recurse -File -Filter "*.md" |
  Select-Object FullName
```

Known handoff/documentation items from the project's integration work include the following. Confirm each file exists in the latest branch before following it.

| File / document | Purpose |
|---|---|
| `README.md` | Main project overview, setup, run instructions, testing and teammate handoff. |
| `START_HERE_BN.md` | Bengali-language starting guide for the project handoff, if present. Read this first when onboarding from the handoff bundle. |
| `CURRENT_STATE.json` | Machine-readable snapshot of the handoff/current state. It is JSON, not Markdown; check its timestamp and status before relying on it. |
| Narrative report / integration report | Explains decisions, what was integrated, verification performed, and remaining gaps. Use the exact filename found in the repository or handoff bundle. |
| Accepted Stage 6 summary | Records the accepted Stage 6 run/status and constraints. Verify whether it describes a candidate run or an authorized active-index update. |
| `Stage 6 TEAMMATE_INTEGRATION.md` | Teammate handoff for the Stage 6 integration, if present. |
| `.env.example` | Example configuration variable names. It should not contain real secrets. |
| Test files | Executable regression checks for the bridge, merge contract, research workflow and HTTP/PDF path. |
| Benchmark reports / scoring scripts | Explain or execute retrieval evaluation. Check the report date and dataset/index generation. |

**Documentation rule:** when two files disagree, do not silently assume the older or newer one is correct. Compare their dates/commit history, accepted decisions, and the actual implementation; then update the documentation to match the verified current state.

---

## 11. Data, secrets, and Git policy

- **Do not commit ChromaDB runtime data** or large local vector-index directories unless the project owner explicitly changes this policy.
- Do not commit `.env`, API keys, access tokens, credentials, private datasets or user information.
- Keep `.env.example` limited to placeholder values and variable names.
- Avoid hard-coded machine-specific paths such as `G:\Capston\...` in reusable code. Prefer environment variables or paths resolved relative to the repository.
- Keep raw government PDFs and generated OCR/chunk files out of Git unless they are intentionally approved, legally shareable, and small enough for the repository.
- Before any active index update, check the current generation, take the documented backup, validate the candidate, and know the rollback command.
- Never run a destructive cleanup or index migration solely because a folder looks old. First check references, tests, data ownership, and the accepted integration report.

---

## 12. Troubleshooting

### `ModuleNotFoundError` (for example, `fastapi`)

The wrong Python environment may be active, or dependencies may not have been installed in that environment.

```powershell
where.exe python
python --version
python -m pip --version
python -m pip install -r requirements.txt
```

Only run the install command if the repository actually contains `requirements.txt`. Confirm the correct environment and manifest first.

### `No module named unmochon_live`

Run from the repository root and set the source path:

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m unmochon_live --help
```

Confirm that `src\unmochon_live` exists in the current checkout.

### Unicode / `charmap` errors

In the same PowerShell terminal:

```powershell
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
```

Restart the app from that terminal.

### ChromaDB collection missing or empty

- Inspect the configured index path and collection name.
- Check whether the database is external/local and absent from the clone.
- Confirm the environment uses compatible dependencies.
- Do not create or overwrite an active collection without a backup and a clear target path.

### Cloudflare Tunnel does not provide a URL

- Ensure the app is reachable locally first.
- Confirm the tunnel command points to the actual port.
- Keep the app and tunnel running in separate terminals.
- Look for error output in the tunnel terminal and check the current official Cloudflare documentation if the client reports a changed requirement.

### OOS research produces no final answer

Check each step separately: permission result → source discovery → HTTP fetch → PDF/HTML extraction → chunk creation → evidence validation → index update or candidate handoff → retrieval → answer formatting. Use logs and tests to find the first failed stage rather than assuming the crawler alone is responsible.

---

## 13. Suggested teammate workflow

1. Clone the latest default branch and read this README.
2. Read `START_HERE_BN.md` and the current-state/integration reports if present.
3. Create the correct Python environment and configure `.env` locally.
4. Confirm the expected data/index is available before starting the application.
5. Run automated tests and record the commit SHA and output.
6. Run one in-scope query and one OOS query manually.
7. Test permission decline and approval separately.
8. Validate evidence and index behavior on a candidate/test index.
9. Work on one assigned task in a separate branch.
10. Add or update tests and documentation with each change.
11. Open a pull request describing changed files, test evidence, risks and rollback steps.
12. Do not delete old folders, replace the active index, or change architecture without review and approval.

### Pull request checklist

- [ ] Change is limited to the assigned task.
- [ ] No secrets, `.env`, runtime ChromaDB database or accidental local files are included.
- [ ] Tests and manual verification are documented.
- [ ] Source references and metadata remain intact.
- [ ] No active-index write occurs without the required authorization.
- [ ] README or relevant docs are updated.
- [ ] Known limitations are recorded honestly.

---

## Project status

This repository is an evolving capstone project. Treat a feature as complete only when the current code, tests and end-to-end behavior support that claim. Keep this README aligned with the latest accepted integration decisions and the actual default branch.
