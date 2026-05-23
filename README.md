This is your team's instruction manual. It explains the architecture and exactly what they need to do.

🇧🇩 Bangladesh Policy Document Retrieval System (RAG)
This repository contains the data processing pipeline for building a Retrieval-Augmented Generation (RAG) system for Bangladeshi Government Policy Documents across three ministries: Social Welfare, Agriculture, and Disaster Management.

🏗️ Architecture
We use a Decentralized Processing -> Centralized Storage approach:

Decentralized: Team members process PDFs locally using their own machines.
Shared: Team members push the clean, lightweight .jsonl text files to this Git repository.
Centralized: The project lead pulls the .jsonl files and builds the unified Vector Database for the LLM.
🛠️ Setup Instructions (For All Team Members)
Clone the Repository:
git clone <YOUR_REPO_URL>cd BD-Policy-RAG-System
Create and Activate Virtual Environment:
bash

python -m venv venv

# Windows:

venv\Scripts\activate

# Mac/Linux:

source venv/bin/activate
Install Dependencies:
bash

pip install -r requirements.txt
Install Tesseract OCR (Required for Scanned PDFs):
Download the installer from UB Mannheim Tesseract.
IMPORTANT: During installation, select "Bengali" under Additional Languages.
Add Tesseract to your system PATH (usually C:\Program Files\Tesseract-OCR).
📂 Team Member Workflow
Your job is to convert a folder of PDFs into a single, clean .jsonl file.

Place PDFs: Put all the PDFs for your assigned ministry into the data/raw_pdfs/ folder.
Configure Script: Open scripts/1_batch_pipeline.py and update these lines at the top:
python

MINISTRY_TAG = "Agriculture" # Change to your ministry!
Run the Pipeline:
bash

python scripts/1_batch_pipeline.py
The script will automatically detect digital text and use OCR for scanned documents.
Check Output: Once finished, you will find a file named Agriculture_clauses.jsonl (or your ministry name) in the data/processed_jsonl/ folder.
Commit and Push: Add, commit, and push that .jsonl file to the repository:
bash

git add data/processed_jsonl/Agriculture_clauses.jsonl
git commit -m "Add Agriculture Ministry processed clauses"
git push origin main
🚀 Project Lead Workflow
Once team members have pushed their .jsonl files, you need to build the central search database.

Pull Latest Data:
bash

git pull origin main
Build Central Database:
bash

python scripts/2_build_central_db.py
This reads all .jsonl files in data/processed_jsonl/, generates embeddings, and saves the database to data/central_chroma_db/.
Evaluate the Database:
bash

python scripts/3_evaluate_search.py
Use this script to test Hybrid (BM25 + Dense) search queries against the central database.
⚠️ Important Notes
Do NOT push raw PDFs to Git. They are too large and will break the repository. The .gitignore file is set up to prevent this.
Do NOT push the central_chroma_db folder to Git. It contains thousands of small binary files that Git handles poorly. If a teammate needs the database, they can build it locally by running 2_build_central_db.py.
text

---

### 3. Updating the Scripts for the New Structure

You need to slightly update the file paths inside your Python scripts to match this new structure.

**In `scripts/1_batch_pipeline.py`**, change the paths at the top to:

```python
MINISTRY_TAG = "Social Welfare" # Team changes this
INPUT_FOLDER = "../data/raw_pdfs"
OUTPUT_FILE = f"../data/processed_jsonl/{MINISTRY_TAG.replace(' ', '_')}_clauses.jsonl"
In scripts/2_build_central_db.py, change the paths to:

python

CENTRAL_JSONL_FOLDER = "../data/processed_jsonl"
CENTRAL_DB_DIR = "../data/central_chroma_db"
How to Initialize the Git Repo
Open your terminal in the root BD-Policy-RAG-System folder and run:

bash

git init
git add .
git commit -m "Initial commit: Project structure and pipelines"
git branch -M main
git remote add origin <YOUR_GITHUB_REPO_URL>
git push -u origin main
Now, you can invite your teammates to the GitHub repository, and they can follow the README exactly!
```
