# 🇧🇩 Bangladesh Policy Document Retrieval System (RAG)

This repository contains the data processing pipeline for building a Retrieval-Augmented Generation (RAG) system for Bangladeshi Government Policy Documents across three ministries: Social Welfare, Agriculture, and Disaster Management.

## 🏗️ Architecture

We use a **Decentralized Processing -> Centralized Storage** approach:

1. **Decentralized:** Team members process PDFs locally using their own machines.
2. **Shared:** Team members push the clean, lightweight `.jsonl` text files to this Git repository.
3. **Centralized:** The project lead pulls the `.jsonl` files and builds the unified Vector Database for the LLM.

---

## 🛠️ Setup Instructions (For All Team Members)

1. **Clone the Repository:**

   ```bash
   git clone https://github.com/BzShezan/BD-Policy-RAG-System.git
   cd BD-Policy-RAG-System

   ```

2. **Create and Activate Virtual Environment:**

   ```bash
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # Mac/Linux:
   source venv/bin/activate
   ```

3. **Install Dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Install Tesseract OCR (Required for Scanned PDFs):**
   - Download the installer from [UB Mannheim Tesseract](https://github.com/UB-Mannheim/tesseract/wiki).
   - **IMPORTANT:** During installation, select "Bengali" under Additional Languages.
   - Add Tesseract to your system PATH (usually `C:\Program Files\Tesseract-OCR`).

---

## 📂 Team Member Workflow

Your job is to convert a folder of PDFs into a single, clean `.jsonl` file.

1. **Place PDFs:** Put all the PDFs for your assigned ministry into the `data/raw_pdfs/` folder.
2. **Configure Script:** Open `scripts/1_batch_pipeline.py` and update these lines at the top:
   ```python
   MINISTRY_TAG = "Agriculture" # Change to your ministry!
   ```
3. **Run the Pipeline:**
   ```bash
   python scripts/1_batch_pipeline.py
   ```
   _The script will automatically detect digital text and use OCR for scanned documents._
4. **Check Output:** Once finished, you will find a file named `Agriculture_clauses.jsonl` (or your ministry name) in the `data/processed_jsonl/` folder.

5. **Commit and Push:** Add, commit, and push that `.jsonl` file to the repository:
   ```bash
   git add data/processed_jsonl/Agriculture_clauses.jsonl
   git commit -m "Add Agriculture Ministry processed clauses"
   git push origin main
   ```

---

## 🚀 Project Lead Workflow

Once team members have pushed their `.jsonl` files, you need to build the central search database.

1. **Pull Latest Data:**

   ```bash
   git pull origin main
   ```

2. **Build Central Database:**

   ```bash
   python scripts/2_build_central_db.py
   ```

   _This reads all `.jsonl` files in `data/processed_jsonl/`, generates embeddings, and saves the database to `data/central_chroma_db/`._

3. **Evaluate the Database:**
   ```bash
   python scripts/3_evaluate_search.py
   ```
   _Use this script to test Hybrid (BM25 + Dense) search queries against the central database._

---

## ⚠️ Important Notes

- **Do NOT** push raw PDFs to Git. They are too large and will break the repository. The `.gitignore` file is set up to prevent this.
- **Do NOT** push the `central_chroma_db` folder to Git. It contains thousands of small binary files that Git handles poorly. If a teammate needs the database, they can build it locally by running `2_build_central_db.py`.

````

***

Once you've saved this in VS Code, run these commands in your terminal to push the fix:

```bash
git add README.md
git commit -m "Fix README formatting"
git push origin main
````
