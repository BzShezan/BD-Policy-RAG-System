# এখানে শুরু করুন — Merged Original RAG Base

১. Repository clone করে `BD-Policy-RAG-System/Unmochon_Live` folder খুলুন। Python **3.11/3.12** ব্যবহার করুন।
২. নিজের private backup-এর `data/` folder এই `Unmochon_Live/data/` path-এ রাখুন। পুরো `chromedb/` directory, `bm25_index.pkl`, `doc_metadata.json` ও processed JSONL লাগবে। GitHub-এ এই data দেওয়া নেই। এরপর PowerShell-এ:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python scripts/setup.py
python -m unmochon_live doctor
python -m unmochon_live serve
```

৩. Browser-এ http://127.0.0.1:8000 খুলুন। প্রথমবার original embedding model download হবে। English প্রশ্নের জন্য original NLLB translation model-ও download হবে।
৪. পুরোনো `.env` কপি করলে `RAG_BACKEND=original` ও `ENABLE_WEB_SEARCH=false` বসাবেন। `data/chromedb`-ই আসল database; `data/chroma_db` নয়।
৫. নিজের private original database-এ **১৫,০১৯টি indexed record**, matching BM25, processed JSONL, workbook ও metadata JSON আছে। GitHub থেকে শুধু source ও UI assets পাবেন; setup database download বা restore করে না। Database নতুন করে build বা `--fresh` করবেন না। অন্য drive থেকে data ব্যবহার করলে `.env`-এ প্রতিটি relevant data path বদলে `doctor` দিয়ে যাচাই করুন।
৬. **Original ZIP-এ raw policy PDF ও trained layout model নেই।** Exact PDF clause highlight feature-এর code দেওয়া আছে; আসল PDF `data/raw_pdfs/`-এর ministry folders-এ রাখলে সেই original feature কাজ করবে। Trained layout inference-এর জন্য নিজের checkpoint লাগবে।
৭. Dataset update করতে server বন্ধ করে original JSONL format-এ incoming folder তৈরি করুন:

```powershell
python -m unmochon_live update-dataset .\incoming --metadata .\incoming\doc_metadata.json
python -m unmochon_live serve
```

Metadata update না থাকলে `--metadata` অংশ বাদ দিন। Original filters, একই embedding model, stable clause IDs, ChromaDB/BM25 sync ও backup ব্যবহৃত হবে।

Updated database, incoming chunks, metadata এবং backup local/private রাখুন। এগুলো GitHub-এ push করবেন না; `.gitignore`-এ data, dataset, database ও archive files বাদ দেওয়া আছে।

Live-এর templates/CSS/fonts/logos অপরিবর্তিত। Original extraction, explanation, exact clause, PDF link এবং conflict-এর তথ্য আগের result page-এ যুক্ত হয়েছে। নতুন agent tools এই ধাপে চালু করা হয়নি।

বিস্তারিত setup, OCR/layout dependencies, dataset format ও সীমাবদ্ধতা: মূল `README.md` এবং `docs/MERGE_VALIDATION.md`।
