# BD Policy RAG System — Unmochon Live

The merged **Unmochon Live + Original Source** application is in [`Unmochon_Live/`](Unmochon_Live/). This repository contains the original OCR-to-search source code, dataset-update tools, exact PDF clause/link feature and the existing Live interface. The original 15,019-record ChromaDB, BM25, datasets and document metadata remain private local assets.

## Run the merged application

Use Python **3.11 or 3.12**. After cloning, run in Windows PowerShell:

```powershell
cd Unmochon_Live
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python scripts/setup.py
python -m unmochon_live doctor
python -m unmochon_live serve
```

Before serving, copy your existing private `data/` folder into `Unmochon_Live/data/`, including the full `chromedb/` directory, `bm25_index.pkl`, `doc_metadata.json` and processed JSONL. Alternatively configure all relevant private data paths in `.env` as described in the full setup guide. Setup creates configuration and preserves existing data. Open http://127.0.0.1:8000 after `doctor` confirms your local assets.

See the [full setup and dataset-update guide](Unmochon_Live/README.md), [Bangla starting guide](Unmochon_Live/docs/START_HERE_BN.md), [feature mapping](Unmochon_Live/docs/FEATURE_MAP.md) and [merge validation](Unmochon_Live/docs/MERGE_VALIDATION.md). Original raw policy PDFs and trained layout checkpoints were not supplied; add them at the paths documented in the setup guide.

The repository's earlier root-level processing scripts are retained. Previously tracked datasets are removed from the current file tree and remain in local copies; existing Git history is preserved. The previous root instructions are in [the previous README](docs/PREVIOUS_REPOSITORY_README.md). Use the merged application's instructions above for the current Live server. Database/dataset/archive files and credentials are excluded by `.gitignore`.
