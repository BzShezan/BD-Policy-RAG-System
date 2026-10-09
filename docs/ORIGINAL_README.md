# Unmochon (উন্মোচন) — OCR Pipeline

Bilingual clause-level government policy search engine with contradiction detection.

---

## Repo Structure

```
BD-Policy-RAG-System/
    data/
        processed_jsonl/           ← OCR output files (push these)
            Social_Welfare_clauses.jsonl
            Social_Welfare_clauses_review.jsonl
            Social_Welfare_tables.jsonl
            Social_Welfare_skipped.txt
            Disaster_Management_clauses.jsonl
            ...
    scripts/
        1_batch_pipeline.py        ← main entry point
        ocr_pipeline/
            __init__.py
            ocr.py                 ← OCR logic
            chunker.py             ← clause splitting + bbox
            quality.py             ← quality scoring
            tables.py              ← table extraction
            checkpoint.py          ← file IO
    layout_analysis/
        scripts/
            export_pages.py
    setup.bat                      ← run this to install everything
    requirements.txt               ← package list for reference
    README.md
    .gitignore
```

**Not in repo (too large):**

- `data/raw_pdfs/`

---

## Output File Schema

Each line in `_clauses.jsonl` is one clause:

```json
{
  "clause_id": "SW_OAA_2025_01_Circular_v1_C0003",
  "text": "বয়স্ক ভাতার পরিমাণ মাসিক ৬৫০ টাকা",
  "doc_id": "SW_OAA_2025_01_Circular_v1",
  "section": "3",
  "tag": "Social Welfare",
  "page_number": 2,
  "ocr_method": "tesseract",
  "quality_score": 0.81,
  "language": "Bangla",
  "needs_review": false,
  "is_table": false,
  "bbox": [72.5, 210.3, 480.2, 228.6]
}
```

`bbox` = `[x1, y1, x2, y2]` in PDF points — used for PDF.js clause highlighting.

---

## Setup Guide (Windows)

### Prerequisites

- Windows 10 or 11
- At least 5GB free disk space

---

### Step 1 — Install Tesseract OCR

1. Go to: https://github.com/UB-Mannheim/tesseract/wiki
2. Download the Windows installer (64-bit)
3. Run the installer
4. On the "Choose Components" screen — expand **Additional language data** and check **Bengali**
5. Complete install — default path is `C:\Program Files\Tesseract-OCR\`
6. Verify: open Command Prompt and run:
   ```
   tesseract --version
   ```
   Should print version number.

---

### Step 2 — Install Miniconda

1. Go to: https://docs.conda.io/en/latest/miniconda.html or use this link for direct installation https://repo.anaconda.com/miniconda/Miniconda3-py39_23.5.2-0-Windows-x86_64.exe
2. Download **Miniconda3 Windows 64-bit**
3. Run installer
4. When asked "Add Miniconda to PATH" — check yes
5. Verify: open new Command Prompt and run:
   ```
   conda --version
   ```

---

### Step 3 — Clone the Repo

```bash
git clone https://github.com/Tamima-Hossen-Samantha/BD-Policy-RAG-System.git
cd BD-Policy-RAG-System
```

---

### Step 4 — Create Conda Environment

```bash
C:\Users\User\miniconda3\Scripts\activate.bat
conda create -n bbocr python=3.9 -y
conda activate bbocr
```

---

### Step 5 — Install All Dependencies

Run the setup script (installs everything in correct order):

```bash
setup.bat
```

This installs:

- PyMuPDF, Pytesseract, Pillow
- ApsisOCR + ONNX Runtime
- FastDeploy (CPU)
- PyTorch CPU
- pandas 1.5.3, numpy 1.24.3
- bijoy2unicode, shapely, ultralytics

Wait for all steps to complete — takes 10-15 minutes.

---

### Step 6 — Apply ApsisOCR Patch (Critical)

ApsisOCR has 3 bugs that crash the pipeline. You must patch it before running OCR.

**Find the patch file:** it's already in this repo as `patched_apsisocr_ocr.py`.

**Step 6a — Find where ApsisOCR is installed:**

```bash
python -c "import apsisocr; print(apsisocr.__file__)"
```

You will see something like:

C:\Users\User\miniconda3\envs\bbocr\Lib\site-packages\apsisocr\ocr.py

Copy this path — you need it in the next step.

**Step 6b — Replace the broken file with the patched one:**

```bash
copy "patched_apsisocr_ocr.py" "PASTE_YOUR_PATH_HERE"
```

Replace `PASTE_YOUR_PATH_HERE` with the path from Step 6a.

Example (your path will look similar):

```bash
copy "patched_apsisocr_ocr.py" "C:\Users\User\miniconda3\envs\bbocr\Lib\site-packages\apsisocr\ocr.py"
```

**Step 6c — When asked `Overwrite? (Yes/No/All):` type `Yes` and press Enter.**

---

---

### Step 7 — Add PDFs

Add the raw PDF folders:

```
data/
    raw_pdfs/
        social_welfare/      ← SW PDFs here
        Disaster Management/ ← DM PDFs here
        Agriculture/         ← AG PDFs here
```

---

### Step 8 — Configure Ministry

Open `scripts/1_batch_pipeline.py` in any text editor.

Change the top two lines for your ministry:

```python
# For Social Welfare:
MINISTRY_TAG = "Social Welfare"
INPUT_FOLDER = r"C:\path\to\BD-Policy-RAG-System\data\raw_pdfs\social_welfare"

# For Disaster Management:
MINISTRY_TAG = "Disaster Management"
INPUT_FOLDER = r"C:\path\to\BD-Policy-RAG-System\data\raw_pdfs\Disaster Management"

# For Agriculture:
MINISTRY_TAG = "Agriculture"
INPUT_FOLDER = r"C:\path\to\BD-Policy-RAG-System\data\raw_pdfs\Agriculture"
```

---

### Step 9 — Run the Pipeline

```bash
conda activate bbocr
cd BD-Policy-RAG-System
python scripts/1_batch_pipeline.py
```

The pipeline will print progress page by page. Let it run — do not close the terminal.

**If it stops mid-way:** just run the same command again. It automatically resumes from where it stopped.

**If a PDF keeps crashing:** rename it to `.pdf.skip`:

```bash
ren "data\raw_pdfs\social_welfare\problem_file.pdf" "problem_file.pdf.skip"
```

---

### Step 10 — Check Output

After completion you will see a summary:

```
=======================================================
COMPLETE : Social Welfare
=======================================================
Clean      : 4521
Review     : 312
Tables     : 890
bbox found : 3980/4521 (88%)
```

Output files are in `data/processed_jsonl/`.

---

## OCR Logic

```
PDF page
  ↓
PyMuPDF digital text
  quality >= 0.6 → CLEAN jsonl
  ↓
Tesseract (Bengali + English)
  quality >= 0.5 → CLEAN jsonl
  ↓
ApsisOCR (Bengali specialist)
  quality >= 0.5 → CLEAN jsonl
  quality < 0.5  → REVIEW jsonl
  ↓
PDF crash → skipped.txt
```

Quality score = Bengali character ratio (0.0 to 1.0).

---

## Team

| Person   | Role                                          |
| -------- | --------------------------------------------- |
| Samantha | SW + DM tracks, OCR pipeline, Layout analysis |
| Shezan   | ChromaDB (`2_build_central_db.py`)            |

---

## For Shezan — ChromaDB Integration

The `_clauses.jsonl` files are the input to `2_build_central_db.py`.

File naming:

- `Social_Welfare_clauses.jsonl`
- `Disaster_Management_clauses.jsonl`
- `Agriculture_clauses.jsonl`

Key fields for indexing: `clause_id`, `text`, `tag`, `doc_id`, `page_number`, `bbox`

Do NOT index `_review.jsonl` files — those are low quality.  
`_tables.jsonl` files can be indexed separately if needed.

# Letest Update of Unmochon (উন্মোচন) — Bangladesh Government Policy RAG System

A bilingual (Bangla/English) Retrieval-Augmented Generation system for Bangladesh government policy documents across three ministries: **Agriculture**, **Disaster Management & Relief**, and **Social Welfare**.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    OFFLINE INGESTION PIPELINE               │
├─────────────────────────────────────────────────────────────┤
│  1. PDF Ingestion → OCR (PyMuPDF) → Clause Segmentation    │
│  2. BanglaBERT NER (7 custom entity types)                 │
│  3. BM25 + FAISS Dual Indexing                             │
│  4. Knowledge Graph (Temporal Triples)                     │
│  5. XLM-R NLI Contradiction Detection                      │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                     ONLINE QUERY PIPELINE                   │
├─────────────────────────────────────────────────────────────┤
│  1. Bilingual Query (Bangla/English/Code-switched)         │
│  2. Hybrid Retrieval (BM25 + BanglaBERT FAISS + RRF)       │
│  3. Contradiction Validation (XLM-R NLI)                   │
│  4. Source-Attributed Response                             │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Setup Environment (Conda)

```bash
conda create -n unmochon python=3.10
conda activate unmochon
pip install -r requirements.txt
```

### 2. Add Your PDFs

Place ministry PDFs jsonl under:

```
data/processed_jsonl/
```

### 3. Run Full Pipeline

```bash
cd scripts
python 13_run_pipeline.py --start-from index # Cause OCR is done
```

Or run individual stages:

```bash
python 13_run_pipeline.py --stage ingest    # PDF → clauses
python 13_run_pipeline.py --stage index     # Build BM25 + FAISS
python 13_run_pipeline.py --stage ner       # BanglaBERT NER
python 13_run_pipeline.py --stage nli       # XLM-R contradiction
python 13_run_pipeline.py --stage retrieve  # Test search
```

## Custom Entity Types (7)

| Entity                  | Description         | Example                    |
| ----------------------- | ------------------- | -------------------------- |
| `PROG_NAME`             | Policy program name | "বয়স্ক ভাতা", "VGF"       |
| `ELIGIBILITY_AGE`       | Age requirement     | "Aged 62 or above"         |
| `BENEFIT_AMOUNT`        | Monetary benefit    | "BDT 500 per month"        |
| `INCOME_LIMIT`          | Income ceiling      | "Income below 50,000 taka" |
| `ELIGIBILITY_CRITERIA`  | Who qualifies       | "যোগ্য ব্যক্তিগণ"          |
| `APPLICATION_PROCEDURE` | How to apply        | "আবেদন পদ্ধতি"             |
| `AUTHORITY_ORG`         | Governing body      | "সমাজসেবা অধিদপ্তর"        |

## Models Used

| Component         | Model                            |
| ----------------- | -------------------------------- |
| Dense Embeddings  | `csebuetnlp/banglabert`          |
| NLI Contradiction | `joeddav/xlm-roberta-large-xnli` |
| Sparse Retrieval  | BM25Okapi                        |
| Vector Index      | FAISS (IndexFlatIP)              |
| RRF Fusion        | k=60                             |

## File Structure

```
BD-Policy-RAG-System/
├── data/
│   ├── raw_pdfs/              # Input PDFs per ministry
│   ├── processed_jsonl/       # Output clauses, NER, triples, contradictions
│   ├── index/                 # BM25 + FAISS per ministry
│   └── faiss_index/           # Central FAISS index
├── scripts/
│   ├── ocr_pipeline/          # OCR, tables, chunker, checkpoint
│   ├── config.py              # Central configuration
│   ├── utils.py               # BanglaBERT embedder
│   ├── 1_batch_pipeline.py    # Document ingestion
│   ├── 2_build_central_db.py  # Central FAISS database
│   ├── 3_evaluate_search.py   # Hybrid search evaluation
│   ├── 4_analyze_json.py      # Quality analysis
│   ├── 5_build_index.py       # BM25 + FAISS per ministry
│   ├── 6_retrieval_engine.py  # Hybrid search engine
│   ├── 7_nli_contradiction.py # XLM-R NLI contradiction
│   ├── 8_evaluate.py          # Retrieval metrics (MRR, Hit@K)
│   ├── 9_policy_ner.py        # BanglaBERT 7-entity NER
│   ├── 10_knowledge_graph.py  # Temporal triple construction
│   ├── 11_nli_finetuned.py    # XLM-R NLI (full integration)
│   ├── 12_llm_training_prep.py# Training data generation
│   └── 13_run_pipeline.py     # Orchestrator
└── requirements.txt
```

> ⚠️ **TEAM NOTE — READ THIS FIRST**
> This README documents what is **WORKING** vs what **NEEDS FIXING**.
> Last updated: 2026-07-11 | Pipeline runs end-to-end but has quality gaps.

---

## Pipeline Status Overview

| Stage                   | Script                    | Status                     | Notes                                                          |
| ----------------------- | ------------------------- | -------------------------- | -------------------------------------------------------------- |
| PDF Ingestion           | `1_batch_pipeline.py`     | ✅ **WORKING**             | PyMuPDF + ApsisOCR. 5,373 clauses extracted, 95.6% avg quality |
| Quality Analysis        | `4_analyze_json.py`       | ✅ **WORKING**             | Stats, training pairs generated                                |
| Index Building          | `5_build_index.py`        | ✅ **WORKING**             | BM25 + FAISS indexes built per ministry                        |
| Central DB              | `2_build_central_db.py`   | ✅ **WORKING**             | Unified FAISS index (5,351 clauses)                            |
| NER                     | `9_policy_ner.py`         | ⚠️ **FUNCTIONAL BUT WEAK** | Heuristic regex fallback — **needs BanglaBERT fine-tuning**    |
| Knowledge Graph         | `10_knowledge_graph.py`   | ✅ **WORKING**             | 188 temporal triples generated                                 |
| Contradiction Detection | `7_nli_contradiction.py`  | ✅ **WORKING**             | XLM-R NLI detects 962 contradictions                           |
| Contradiction (alt)     | `11_nli_finetuned.py`     | ✅ **WORKING**             | Same model, same results                                       |
| Training Data           | `12_llm_training_prep.py` | ✅ **WORKING**             | 384 query pairs in 3 formats                                   |
| Search Demo             | `3_evaluate_search.py`    | ✅ **WORKING**             | Hybrid search runs                                             |
| Evaluation Metrics      | `8_evaluate.py`           | ✅ **WORKING**             | MRR/Hit@K computed                                             |
| Interactive Search      | `6_retrieval_engine.py`   | ✅ **WORKING**             | Retrieval engine class loads                                   |

**Overall Pipeline**: ✅ Runs end-to-end without errors.

---

## ⚠️ Critical Gaps (What Needs Fixing)

### 1. Embedding Model: NOT BanglaBERT (CRITICAL)

| What README Claims                           | What Actually Runs                                            | Gap                |
| -------------------------------------------- | ------------------------------------------------------------- | ------------------ |
| `csebuetnlp/banglabert` for dense embeddings | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | ❌ **Wrong model** |

**Why we switched**: BanglaBERT base is trained for Masked Language Modeling (MLM). Its `[CLS]` token is **not semantically meaningful** for sentence similarity without fine-tuning on sentence pairs. Using it raw gave near-random retrieval scores (~0.016 cosine similarity).

**What needs to happen**:

- [ ] **Option A (Quick)**: Switch to `intfloat/multilingual-e5-base` — asymmetric retrieval model designed for query→document matching
- [ ] **Option B (Methodology-compliant)**: Fine-tune BanglaBERT on our policy clause pairs using contrastive loss (SentenceTransformers framework)

**File to edit**: `scripts/utils.py` — change `EMBEDDING_MODEL` in `config.py`

---

### 2. NER: Heuristic Regex, NOT Fine-Tuned BanglaBERT (CRITICAL)

| What README Claims                                | What Actually Runs                         | Gap                |
| ------------------------------------------------- | ------------------------------------------ | ------------------ |
| "Fine-tuned BanglaBERT for 7 custom entity types" | Regex pattern matching + dictionary lookup | ❌ **No ML model** |

**Why**: `csebuetnlp/banglabert` is a base model with **no token classification head**. Loading it as `AutoModelForTokenClassification` initializes random weights (see `classifier.weight: MISSING` in logs).

**Current heuristic detects**:

- `PROG_NAME`: Dictionary match (বয়স্ক ভাতা, VGF, etc.)
- `BENEFIT_AMOUNT`: Regex `[০-৯\d,]+\s*(টাকা|taka|৳)`
- `ELIGIBILITY_AGE`: Regex `বয়স[\s\w]*[০-৯\d]+[\s\w]*বছর`
- `INCOME_LIMIT`, `ELIGIBILITY_CRITERIA`, `APPLICATION_PROCEDURE`, `AUTHORITY_ORG`: Similar regex

**What needs to happen**:

- [ ] Annotate ~500-1000 policy clauses with the 7 entity types (LabelStudio / Doccano)
- [ ] Compute inter-annotator agreement (Cohen's Kappa ≥ 0.8)
- [ ] Fine-tune BanglaBERT with `AutoModelForTokenClassification` on annotated data
- [ ] Replace heuristic in `scripts/9_policy_ner.py` with fine-tuned model

**Files to edit**: `scripts/9_policy_ner.py`, add `data/annotations/` folder

---

### 3. Retrieval Quality: POOR (CRITICAL)

| Metric               | Your Result | Target    | Status                       |
| -------------------- | ----------- | --------- | ---------------------------- |
| MRR (Agriculture)    | 0.129       | 0.30–0.60 | ❌ **3× below**              |
| MRR (Disaster)       | 0.104       | 0.30–0.60 | ❌ **3× below**              |
| MRR (Social Welfare) | 0.057       | 0.30–0.60 | ❌ **5× below, near-random** |
| Hit@1                | 0%          | 15–30%    | ❌ **Zero top-1 accuracy**   |
| Hit@5                | 12–30%      | 45–65%    | ❌ **2× below**              |
| Hit@10               | 19–40%      | 60–80%    | ❌ **2× below**              |

**Why so bad**:

1. **Embedding model** (MiniLM) is symmetric, not designed for query→document retrieval
2. **Training pairs** are artificially easy (same-document clauses) — evaluation doesn't reflect real user queries
3. **Bengali is low-resource** in MiniLM — representation quality is weak

**What needs to happen**:

- [ ] Fix embedding model (see Gap #1)
- [ ] Generate harder evaluation queries: real user questions → policy clauses
- [ ] Add query expansion: "বয়স্ক ভাতা" → "old age allowance, বয়স্ক ভাতা, OAA"
- [ ] Consider re-ranking with cross-encoder (BanglaBERT fine-tuned for relevance scoring)

**Files to edit**: `scripts/utils.py`, `scripts/8_evaluate.py`, `scripts/3_evaluate_search.py`

---

### 4. LayoutLMv3: NOT IMPLEMENTED (MEDIUM)

| What README Claims               | What Actually Runs              | Gap                     |
| -------------------------------- | ------------------------------- | ----------------------- |
| "LayoutLMv3 for layout analysis" | PyMuPDF `get_text("dict")` only | ❌ **Missing entirely** |

**Why it matters**: Your PDFs have headers, footers, tables, multi-column layouts. PyMuPDF reads top-to-bottom linearly, mixing headers with body text. LayoutLMv3 would segment pages into semantic regions (header, body, table, footer).

**What needs to happen**:

- [ ] Install `transformers` LayoutLMv3: `microsoft/layoutlmv3-base`
- [ ] Render each PDF page to image (PyMuPDF `get_pixmap()`)
- [ ] Run LayoutLMv3 inference to detect text blocks + bounding boxes
- [ ] Feed segmented regions into OCR instead of full-page text
- [ ] Map LayoutLMv3 regions to our clause segmentation

**Files to create**: `scripts/layoutlmv3_processor.py`
**Files to edit**: `scripts/1_batch_pipeline.py`, `scripts/ocr_pipeline/ocr.py`

---

### 5. Contradiction Detection: Many False Positives (LOW)

**Current behavior**: XLM-R NLI flags 962 contradictions, but many are **not real contradictions**:

```
A: "৬. জেলা মৎস্য অফিসার - সদস্য"
B: "১২. জেলা সমবায় অফিসার সদস্য"
→ Flagged as contradiction (both are committee member lists, not contradictory)
```

**Why**: NLI model sees "different text about same topic" and labels contradiction. These are **structural differences** (different districts, different roles), not policy conflicts.

**What needs to happen**:

- [ ] Add post-filter: only flag contradictions when entities differ (amount, age, date)
- [ ] Filter out committee member lists, district allocations, etc.
- [ ] Add manual review step for confidence < 0.85

**Files to edit**: `scripts/7_nli_contradiction.py`, `scripts/11_nli_finetuned.py`

---

### 6. LLM Training Data: Low Volume (LOW)

**Current**: 384 training pairs across all 3 ministries
**Target**: 2,000–5,000 pairs for effective fine-tuning

**What needs to happen**:

- [ ] Increase `num_per_ministry` in `generate_queries()` from 200 to 1000
- [ ] Add more query templates (currently 7 types, add 10+ more)
- [ ] Use GPT/LLM to generate synthetic queries from clause text
- [ ] Ensure hard negatives are actually hard (not just contradictions)

**Files to edit**: `scripts/12_llm_training_prep.py`

---


---

# 🔄 Update from Samantha — Unmochon v2 Rebuild

*Everything below this line documents the rebuilt version of Unmochon, covering the full pipeline from OCR through to the working web UI, plus the reasoning behind major design decisions. This work lives on the `unmochon-v2` branch. The original `legacy-faiss-version` is preserved untouched for reference.*

---

## What Changed and Why

The original pipeline used FAISS with BanglaBERT embeddings for retrieval. Testing showed this gave near-random retrieval scores (MRR 0.057–0.129 across ministries) because BanglaBERT-base was trained for masked-language-modeling, not sentence-embedding/similarity tasks — its output vectors were never organized in a way where "similar meaning" maps to "similar vector."

This rebuild replaces that architecture with **ChromaDB + a proper multilingual sentence-embedding model**, and adds an entire new layer on top: a rule-based chatbot pipeline that turns retrieved clauses into plain-language, citation-backed answers, plus a bilingual web UI.

The rebuild also fixed four separate corruption bugs in the OCR pipeline that were silently damaging the underlying text — meaning even a perfect retrieval system would have been searching over broken data before this fix.

---

## Full Pipeline — What's Built

### 1. OCR & Data Cleaning

Four bugs found and fixed in the original extraction pipeline:

- **Bijoy-encoding detector never fired** — its reference marker strings were themselves corrupted (saved as UTF-8, read back as cp437), so the detector silently matched nothing.
- **Quality-scoring function was inverted** — it measured Bengali-character ratio, not actual text quality. Garbled Bengali scored 1.0 (perfect), clean English scored 0.0 (worst). This meant clean English pages were needlessly sent through OCR, and corrupted Bengali pages were accepted as fine.
- **No detection for legacy-font corruption** — a distinct pattern from Bijoy encoding, where PDFs using legacy fonts map text to Bengali codepoints in visual order with conjuncts dropped or replaced by Latin glyphs. Added `is_broken_bengali()` with three rules: pre-base vowel signs at word start, stray Latin fused to Bengali, and adjacent invalid vowel sequences.
- **Broken `bijoy2unicode` import** — the import silently failed on every run (wrong API usage), so Bijoy-to-Unicode conversion never actually executed despite the code appearing to call it.

**Verified impact (Social Welfare):**
- Corrupted clauses: 896 of 4,623 (19.4%) → ~84 of 4,596 (1.8%)
- Worst single document (RSS policy): 468 of 554 clauses corrupted (84.5%) → 0, fully recovered via targeted re-OCR

Same fixes applied to Agriculture; corruption dropped from 469 corrupted clauses to a small residual after two targeted re-OCR batches on the worst-affected documents (fertilizer regulation, SDG localization, seed dealer registration, and others).

### 2. Retrieval — Hybrid Search (Dense + Sparse + Fusion)

- **Dense retrieval**: ChromaDB, using `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` — a model actually trained for cross-lingual sentence similarity, unlike BanglaBERT-base.
- **Sparse retrieval**: BM25 (`rank_bm25`), built by reading documents directly out of ChromaDB (not re-parsing source files) to guarantee both retrievers see an identical corpus.
- **Fusion**: Reciprocal Rank Fusion, k=60 (standard value from the original RRF paper). A clause found by both retrievers ranks above one found by only one.
- **~15,019 items indexed** across all three ministries after the final rebuild.

**Bugs found and fixed in retrieval:**

- **Ministry filter leak** — metadata filters (e.g. `ministry="Social Welfare"`) were only applied to the dense retriever, not BM25, so BM25 could still surface wrong-ministry results that leaked through the RRF fusion. Fixed by pre-computing the allowed id set from the metadata filter and applying it to both retrievers before fusion runs, not after.
- **Cover-page/memo-header noise dominating results** — short, keyword-dense boilerplate (ministry letterhead, memo numbers) was scoring artificially high on both dense and sparse retrieval, frequently outranking the actual answer clause. Root cause and fix described in Layout Classification below.

### 3. Layout Classification (LiLT model)

Trained a token-classification model to distinguish real policy content from administrative noise, so the search index can be filtered to exclude non-content regions.

- **Base model**: `nielsr/lilt-xlm-roberta-base` (LiLT architecture + XLM-RoBERTa backbone) — chosen because it's layout-aware (reads word position, not just text) without needing full image processing like LayoutLMv3.
- **Training data**: 1,181 hand-annotated Social Welfare pages, 12 labels finalized after checking real per-label frequency counts (avoiding the failure mode of an earlier, rejected annotation attempt that produced 0% accuracy on one label due to insufficient training examples).
- **Split**: document-level (not page-level) — 43 training documents / 12 validation documents — so pages from the same document can't appear in both sets and inflate validation scores through partial memorization.
- **Results (8 epochs, held-out validation)**: CLAUSE recall 83–90%, TABLE recall 82–99% (the two labels that matter for downstream filtering). Weaker on administrative labels (HEADER 35–43%, Signature 47–89%) — acceptable since those get excluded from the index regardless of exact accuracy. Two rare labels (Fig_with_value, Fig_without_value) never learned anything — confirmed to be a data-scarcity problem (40 and 26 training examples respectively), not a training-duration problem, since more epochs did not improve them.
- **Applied via inference** (`9_inference.py`) across the full Social Welfare corpus — 3,896 of 4,136 clauses (94.2%) received a real predicted layout label. Word-box files were matched to clauses by filename **prefix**, not exact match, because clause `doc_id` values are sometimes truncated versions of the real document filenames (a pre-existing, unrelated OCR/chunking issue found during this work).

**Agriculture and Disaster Management** do not have a trained layout model — no annotation exists for those ministries yet. A **heuristic fallback filter** (`heuristic_filter.py`) is used instead: excludes chunks under 15 words, and chunks where more than 40% of the text matches known boilerplate phrases (ministry letterhead, government website URLs). This is explicitly a stopgap, documented as less accurate than the trained model, but sufficient to remove the most obvious noise (confirmed via direct corruption-text check after rebuild — the specific garbled text samples found in testing were confirmed gone).

### 4. Date Extraction

- **Priority chain**: doc_id filename prefix → OCR'd header text → filename convention → Bengali calendar (বঙ্গাব্দ) fallback, in that order.
- **Deliberately excludes numeric DD/MM/YYYY parsing** — nearly every document in the corpus references a 2005 Ministry of Finance memo using exactly that numeric format. A naive parser would have mis-dated hundreds of real 2025 documents as 2005.
- **Coverage**: 95.3% of Social Welfare clauses have a verified circular date.
- **`printed_page_number` field**: attempted automated detection of the number actually printed on each physical page (distinct from file position — see Known Limitations). Detection is intentionally conservative (only trusts an isolated standalone number, not one embedded in surrounding text), which means real coverage came back low (16–47% depending on ministry) — treated as a first-pass helper, not a trusted final answer. Page citations for the verified question set were manually confirmed against the actual PDF instead.

### 5. Chatbot Pipeline

Located in `chatbot/scripts/`. Built specifically to satisfy a supervisor requirement: auto-generated, plain-language, citation-backed answers — without using an LLM, since free-form generation would contradict this project's core no-hallucination design principle.

- **`normalize.py`** — Bengali digit normalization (০-৯ → 0-9), reused directly from the date-extraction module.
- **`confidence.py`** — three-tier confidence-gated response builder:
  - High (≥0.85): state the answer directly
  - Medium (≥0.6): state the answer with a "please verify" caveat
  - Low (below 0.6): **never guess** — show the raw retrieved clause and say a specific answer could not be confidently extracted
  - This is the single most important safety mechanism in the whole chatbot layer — it's what makes "auto-generated" compatible with "must never confidently state a wrong fact."
- **`ner.py`** — rule-based (regex) entity extraction, not a trained model. No labeled training data exists for a real NER model, and rule-based patterns are transparent and auditable — you can point at the exact pattern that produced a given extraction, which a trained model cannot offer. Contextual, not naive keyword matching (a bare "টাকা" regex pulls noise from budget allocation tables). Ministry-specific, because each ministry genuinely uses different vocabulary for its real facts:
  - Social Welfare: `extract_age`, `extract_income_limit`, `extract_benefit_amount` (বয়স, আয়সীমা, ভাতা)
  - Agriculture: `extract_document_requirements` (Trade License, TIN Certificate, VAT Registration, bank solvency certificate — confirmed against real Fertilizer Act text)
  - Disaster Management: `extract_district_allocations` (district name + taka amount pairs, e.g. "রংপুর ১,০০,০০০ টাকা" — confirmed against real relief allocation orders)
- **`intent.py`** — multi-intent question classification via keyword scoring. Detects **all** matching intent categories in a question, not just the first match — a compound question like "what's the age AND income limit" needs both intents detected and both answered, not just one.
- **`answer_generator.py`** — extractive-sentence framing: finds the specific real sentence within a clause that answers the question, wraps it in a citation frame. **Deliberately does not rebuild a sentence from individually extracted values** — Bengali grammar has case markers and postpositions that change based on surrounding words, so naive template-filling (`"The age is [X]"` with a value slotted in) risks producing grammatically broken Bengali. This fix came directly out of a multi-AI roundtable review (see below).
- **`explain.py`** — wraps the confidence-tiered response into a natural paragraph instead of a labeled quote, for the plain-language explanation requirement.
- **`verified_lookup.py`** — direct clause_id lookup for a small table of manually verified questions, bypassing live search ranking entirely. **See Known Limitations — this was flagged as a problem, not a solution, and is being phased out in favor of fixing retrieval ranking directly.**

### 6. Web UI

Located in `UI/`. Flask backend + plain HTML/CSS/JS frontend (no framework) ----- it will updated after defense i will add landing page and all detailed stuff. As we dont have that much time i kept it simple



---

## Design Decisions — Roundtable Discussions

after researching few stuff from all other as as well as few important structure profile i had feew things to decide and clear. This is my personal note that i am sharing so that we can discuss later


### Roundtable 1 — PT-NLI Novelty & Retrieval Architecture

**Context:** when novelty is concerend

**Novelty framing settled on:** *supersession as a deterministic override on top of NLI's semantic judgment* — the idea that two clauses can be semantically contradictory and temporally overlapping, yet not count as a real conflict if one document formally supersedes the other. Verified directly against the literature this claim would be compared to:

- **ConflictBank** — studies knowledge conflicts in LLMs (retrieved-knowledge conflicts, internal-knowledge conflicts, and their interplay). Fundamentally about LLM behavior when facing conflicting facts, not document-level policy contradiction.
- **WikiContradict** — studies how LLMs *answer questions* when RAG feeds them two contradictory retrieved passages. About generation behavior specifically — this project does not do generation at all, so the comparison barely applies.

Neither paper models formal document-level supersession, and neither is doing the same *kind* of task (retrieve-then-compare with no generation, applied to real institutional documents with legal supersession relationships) — confirmed as a genuinely different problem, not an incremental addition to existing work.

**Retrieval architecture confirmed correct:** Dense + BM25 + RRF, unanimous across all reviewers. Do not switch to ColBERT or train a custom retriever — not worth the engineering time for the corpus size and available timeline.

**Cover-page noise problem identified**, with the fix (layout-based filtering) confirmed as the correct, literature-aligned approach — not a hack.

**Ministry filter / BM25 interaction:** confirmed that filtering only the dense retriever while leaving BM25 unfiltered is a known bad pattern in hybrid retrieval systems; the correct fix is applying the same filter to both retrievers before fusion runs.

**Deferred, not forgotten:** the 85-pair contradiction validation experiment (35 real pairs + 35 negative pairs + 15 known-superseded pairs, run through the NLI model, reported as three separate scores: semantic-only / semantic+temporal / semantic+temporal+supersession) — this is the single most important unbuilt piece for the eventual Q1 journal paper, and has not yet been started.

### Roundtable 2 — Chatbot Explanation Layer

**Context:** supervisor requirement for an auto-generated, plain-language, citation-backed chatbot interface, explicitly without using an LLM (to preserve the no-hallucination design principle). (if possible for easy process make it look like a chatbot)

**Core approach confirmed:** retrieve → extract structured facts (rule-based NER) → deterministic generation. All four independent reviewers named this as an established, defensible academic pattern (extractive QA / semi-extractive QA / slot-filling), not a workaround — one reviewer (z.ai) specifically framed it as *stricter* safety discipline than most production RAG systems, since it structurally cannot hallucinate a fact that isn't present in the retrieved source.

**The one genuine disagreement, resolved:** two reviewers proposed filling a hand-written template sentence with extracted entity values (e.g. `"The age is [X] years."`). **Gemini specifically flagged a risk the other three missed**: Bengali grammar uses case markers and postpositions that change based on surrounding context — rigid template-filling risks producing grammatically broken Bengali sentences, something only testable by actually running it on real Bengali text, not visible from an English-language design discussion. **Adopted Gemini's fix instead**: extract the whole real answering sentence from the source document and wrap it in a fixed citation frame, rather than rebuilding a sentence from individual values. This is also simpler to implement — no per-question-type template library with grammatical agreement rules needed.

**Multi-intent handling required:** all four reviewers independently flagged the same failure mode with nearly identical examples — a compound question ("what's the age and income limit") would silently get only half-answered by a single-intent classifier. Built from the start as multi-match keyword scoring, not a later patch.

**Accuracy evaluation:** exact string matching rejected as too strict (different phrasing of the same fact should count as correct). Adopted a three-column fact-level table instead: retrieval correct? / extraction correct? / end-to-end correct? — this isolates *where* a failure happens (wrong document found vs. wrong value extracted vs. both correct but poorly phrased), which is more diagnostically useful than one binary pass/fail number, and was specifically called out as what a technical defense committee would want to see.

**Confidence-gated fallback:** unanimous across all four reviewers as the load-bearing safety mechanism — described almost identically in every response. Three-tier behavior (high/medium/low confidence → direct answer / caveated answer / raw-text fallback) is what makes "auto-generated" compatible with "must never confidently state a wrong fact."

---

## Setup Instructions

```bash
# Environments needed (three separate conda environments):
#   bbocr    - OCR pipeline, PyMuPDF, Tesseract
#   chroma   - ChromaDB, sentence-transformers, Flask, the chatbot pipeline, the UI
#   layout2  - LiLT training/inference (transformers, torch with CUDA)

# Activate the environment needed for the UI/chatbot:
G:\Conda\Scripts\activate.bat chroma

# Run the web UI:
cd G:\BD-Policy-RAG-System\UI
python app.py

# Then open in a browser:
http://127.0.0.1:5000
```

**To rebuild the ChromaDB index from scratch** (needed after any change to the layout filter, heuristic filter, or source data):

```bash
conda activate chroma
cd G:\BD-Policy-RAG-System\scripts\chromadb_build
python build_chromadb.py --fresh
```

⚠️ This is a long-running operation (~4 hours observed on CPU). Prefer running on a machine with a working CUDA-enabled `torch` install if speed matters.

**To rebuild BM25** (must be done after any ChromaDB rebuild, so both retrievers see identical content):

```bash
cd G:\BD-Policy-RAG-System\scripts\retrieval
python build_bm25.py
```

**To test the chatbot pipeline directly** (without the UI):

```bash
cd G:\BD-Policy-RAG-System\chatbot\scripts
python chatbot_cli.py
```

---

## What's Working

- OCR pipeline — verified corruption fix, ~98% clean text on Social Welfare added source link even though few pdf dont have the source link because of the cruppted and bijoy 
- ChromaDB hybrid retrieval (dense + BM25 + RRF) — built, tested, ministry-filter leak fixed and verified
- Layout classification for Social Welfare — trained, verified accuracy numbers on held-out data, applied across the corpus
- Heuristic noise filtering for Agriculture/Disaster Management — deployed, corruption-text check confirmed clean
- Date extraction — 95.3% coverage, verified against a real known trap (2005 memo date format) that was correctly avoided
- source_url backfill — 74% of Social Welfare clauses (67 documents) have real, verified government URLs, merged from a teammate's metadata spreadsheet
- Chatbot pipeline (NER, intent detection, confidence-gated answers, extractive-sentence framing) — built and tested end-to-end on multiple real verified questions across all three ministries
- Bilingual web UI — two-page architecture, working search flow, working language toggle, working PDF citation links

## What's NOT Working / Known Limitations

- **Live retrieval ranking is not yet fully reliable.** The system found the *right document* but the *wrong specific clause/page* within it multiple times during testing (e.g. a known-correct income-limit clause returning a page containing an unrelated committee list instead). A guaranteed direct-lookup table (`verified_lookup.py`) was built as a stopgap for a small set of manually verified questions — A re-ranking fix (checking whether each of the top-5 retrieved candidates actually contains a successfully extractable entity, not just trusting raw similarity score) has been designed but not yet fully implemented and tested across all entity types.
- **Some documents have unreliable `page_number` metadata** — confirmed via manual PDF verification that certain documents (particularly ones assembled from larger legal compilations) have a `page_number` field that does not correspond to the actual page containing the relevant text, sometimes off by several pages, and not by a single consistent offset. This is a data-quality issue at the source, not a retrieval bug, and needs direct correction in the JSONL for affected documents.
- **No trained layout classification model for Agriculture or Disaster Management** — only the SW model exists; the other two ministries rely on a cruder heuristic filter.
- **The 85-pair contradiction validation experiment has not been built** — this is the actual core research contribution (PT-NLI, supersession-aware contradiction detection) and remains entirely unimplemented in code. Everything documented above is the *foundation* the contradiction-detection layer will eventually sit on top of, not the contradiction-detection layer itself.
- **No formal retrieval metrics exist yet** (MRR, Hit@k) — a ground-truth evaluation query set was planned but not completed as of this writing. i am working on but needed to discuss with my teamamte so its paused for a momenty
- **CIT ministry** has not been started.

## Next Steps

1. Fix retrieval re-ranking properly (extend the entity-match re-ranking approach to all five extractor types, test against every known-problematic question, confirm real search — not lookup — produces correct results)
2. Correct known-bad `page_number` values directly in the JSONL for documents already identified as broken
3. Decide whether `verified_lookup.py` should be removed entirely once re-ranking is proven reliable, or kept as a documented, transparent fallback for specific edge cases
4. Build the 85-pair contradiction validation experiment (S-only / S+T / S+T+¬U scoring)
5. Build the GovKG (NetworkX supersession graph) and wire it into actual NLI-based contradiction detection
6. Extend layout classification to Agriculture
7. Build the ground-truth retrieval evaluation set and compute real MRR/Hit@k numbers

## Environment Setup

This project uses three separate conda environments, each with different
dependencies. None of these environments are included in the repository
(see `.gitignore`) — they must be created locally after cloning.

### `bbocr` — OCR pipeline
Used for: PyMuPDF, Tesseract, ApsisOCR, all document extraction and
OCR-related scripts.

```bash
conda create -n bbocr python=3.9
conda activate bbocr
pip install pymupdf pytesseract --break-system-packages
# (add any other OCR-specific packages used - bijoy2unicode, etc.)
```

### `chroma` — Retrieval, chatbot, and web UI
Used for: ChromaDB, sentence-transformers, rank_bm25, Flask, and
everything under `chatbot/` and `UI/`.

```bash
conda create -n chroma python=3.11
conda activate chroma
pip install "numpy>=2.0" --force-reinstall
pip install chromadb sentence-transformers rank_bm25 flask
```

⚠️ **Important**: ChromaDB requires numpy 2.x. If cloned into an
environment with an older numpy already installed, `chromadb` operations
will crash with an unhelpful native error (`access violation` /
`pool timed out`) rather than a clear Python exception. If you hit this,
reinstall numpy as shown above.

### `layout2` — Layout classification model training/inference
Used for: training and running the LiLT layout classifier
(`layout_analysis/pipeline/`).

```bash
conda create -n layout2 python=3.10
conda activate layout2
pip install torch --index-url https://download.pytorch.org/whl/cu118
pip install transformers datasets accelerate
```

Requires a CUDA-capable GPU for reasonable training speed — CPU training
is possible but was observed to take multiple hours for 8 epochs on
~900 pages, versus minutes on GPU.

---

### Which environment for which task

| Task | Environment |
|---|---|
| Running OCR / `1_batch_pipeline.py` | `bbocr` |
| Building/querying ChromaDB | `chroma` |
| Running BM25 build/retrieval scripts | `chroma` |
| Running the chatbot CLI or web UI | `chroma` |
| Training or running the LiLT layout model | `layout2` |

-------

# 🔄 8/28/2026 Final Update from samantha's Side 

---

## what this part of readme file contain
1. [System Architecture](#system-architecture)
2. [Setup from Scratch](#setup-from-scratch)
3. [Directory Structure](#directory-structure)
4. [What's Built (Working)](#whats-built-working)
5. [What's NOT Built (Capstone C)](#whats-not-built-capstone-c)
6. [Running the System](#running-the-system)
7. [Evaluation Results](#evaluation-results)
8. [Known Issues & Limitations](#known-issues--limitations)
9. [File-by-File Guide](#file-by-file-guide)
10. [Common Errors & Fixes](#common-errors--fixes)


---

**What it is doing current now :**
- Takes a question in Bengali OR English
- Retrieves the most relevant clauses from 15,019 pre-processed policy clauses
- Extracts structured facts (age, income, documents required, etc.) using 10 domain-specific extractors
- Presents answers with confidence tiers, plain-language explanations, and PDF viewer with page highlighting
- Detects date-based conflicts (when policies change over time)

## The flow 

User Question (Bengali/English)
↓
[Translation] NLLB-200 if English → Bengali
↓
[Intent Classification] detect_intents() → e.g. ["income_limit"]
↓
[Ministry Inference] keyword matching → e.g. "Social Welfare"
↓
[Stage 1 Retrieval] BM25 + Dense (MiniLM) + RRF fusion → top-100 clauses
↓
[Stage 2 Doc Filter] Group by document, apply intent-aware boost → top-3 docs
↓
[Extractor Re-ranking] Run 10 extractors, boost clauses with clean extractions
↓
[Confidence Tiering] High (≥0.7) / Medium / Low / Out-of-scope
↓
[Explanation Layer] Template + Gemini LLM refinement (top-1 only)
↓
[Conflict Detection] Group by (program, extractor), flag different values across dates
↓
Response to Frontend


---


### Core Components

| Component | Location | Purpose |
|---|---|---|
| Retriever | `scripts/retrieval/search.py` | Hybrid BM25 + dense search |
| Two-stage pipeline | `scripts/retrieval/two_stage.py` | Doc filter + extractor re-rank |
| Translator | `scripts/retrieval/translator.py` | NLLB-200 for EN→BN |
| Extractors (10) | `chatbot/scripts/ner.py` | Rule-based fact extraction |
| Intent classifier | `chatbot/scripts/intent.py` | Question intent detection |
| Explainer | `chatbot/scripts/explainer.py` | Gemini LLM plain-language layer |
| Flask backend | `UI/app.py` | HTTP API + PDF serving |
| Frontend | `UI/static/app.js` + `UI/templates/*.html` | UI rendering |
| Metadata | `data/doc_metadata.json` | Doc names, URLs, dates |
| Vector DB | `data/chroma_db/` | ChromaDB with 15,019 clauses |

---

## Setup from Scratch

### 1. Prerequisites

- **OS:** Windows 10/11 (development done on Windows; Linux should also work)
- **Python:** 3.10 or 3.11
- **Conda:** Anaconda or Miniconda installed
- **Storage:** ~5 GB free (models + PDFs + ChromaDB)
- **Optional GPU:** NVIDIA GPU with CUDA — makes retrieval faster but works on CPU too

### 2. Clone the Repository

```bash
git clone https://github.com/Tamima-Hossen-Samantha/BD-Policy-RAG-System.git
cd BD-Policy-RAG-System
```
if we can push the whole

### 3. Create Conda Environment

```bash
conda create -n chroma python=3.11 -y
conda activate chroma
```

### 4. Install Dependencies

if you dont have torch first run this

```bash
pip install torch==2.8.0 torchvision==0.23.0 --index-url https://download.pytorch.org/whl/cu118
```

```bash
pip install -r requirements.txt
```

If `requirements.txt` doesn't exist, install manually:

```bash
pip install flask
pip install chromadb
pip install sentence-transformers
pip install transformers
pip install rank_bm25
pip install openpyxl
pip install google-generativeai
pip install torch --index-url https://download.pytorch.org/whl/cu118  # for GPU, or torch alone for CPU
```

### 5. data list

-The 15,019-clause ChromaDB   `data/chroma_db/`

- `data/raw_pdfs/` (200+ PDF files)
-  `data/doc_metadata.json` (for now only social meta data is present)
- Place all in `G:\BD-Policy-RAG-System\data\`

**Option B: Rebuild from scratch (takes ~2 hours)**
```bash
# Not documented here — see scripts/ingestion/ for the pipeline
```

### 6. Set Up Gemini API Key

Required for the plain-language explanation layer.

1. Go to https://aistudio.google.com/apikey
2. Sign in with Google account
3. Click "Create API key" → "Create API key in new project"
4. Copy the key (starts with `AIzaSy...`)
5. Create file at `G:\BD-Policy-RAG-System\.gemini_key`
6. Paste ONLY the key inside, no quotes, no spaces
7. Save

**IMPORTANT:** Add `.gemini_key` to `.gitignore` — never commit API keys to Git.

Verify:
```bash
type G:\BD-Policy-RAG-System\.gemini_key
```
Should print your API key.

### 7. Build Metadata JSON

If `data/doc_metadata.json` doesn't exist:

```bash
python scripts/metadata/build_metadata_sourcelink.py
```
for social welfare its 
78 entries to G:\BD-Policy-RAG-System\data\doc_metadata.json
with source_url: 66
with date: 78


### 8. Test the Setup

```bash
cd chatbot/scripts
python -c "from explainer import build_plain_explanation; print(build_plain_explanation('বয়স্ক ভাতা পাওয়ার জন্য বয়স ৬৫ বছর', {'extract_age': {'value': '65', 'confidence': 0.95}}))"
```

Should print a Bengali explanation. If it prints template output only, Gemini API might be down or quota exceeded — that's OK, template fallback works.

### 9. Run Flask

```bash
cd UI
python app.py
```

## folder structure

G:\BD-Policy-RAG-System
│
├── README.md ← This file
├── .gemini_key ← Your Gemini API key (NOT in Git)
├── .gitignore
├── chatbot/
│ └── scripts/
│ ├── ner.py ← 10 extractors (age, income, etc.)
│ ├── intent.py ← Intent classification keywords
│ ├── explainer.py ← Gemini plain-language layer
│ ├── cli_chatbot.py ← Terminal CLI version of the search
│ ├── normalize.py ← Text normalization
│ ├── confidence.py ← Confidence tier logic
│ └── answer_generator.py ← Answer framing
├── data/
│ ├── chroma_db/ ← ChromaDB with 15,019 clauses
│ ├── raw_pdfs/ ← Source PDF files
│ │ ├── social_welfare/
│ │ ├── Agriculture/
│ │ └── Disaster Management/
│ ├── Policies Metadata.xlsx ← Master metadata spreadsheet
│ └── doc_metadata.json ← Generated from Excel
│
├── scripts/
│ ├── retrieval/
│ │ ├── search.py ← HybridRetriever (BM25 + Dense)
│ │ ├── two_stage.py ← Full pipeline entrypoint
│ │ ├── translator.py ← NLLB-200 EN→BN translation
│ │ ├── extractor_map.py ← Intent → extractor mapping
│ │ └── config.py ← Model paths, thresholds
│ ├── metadata/
│ │ └── build_metadata_sourcelink.py ← Excel → JSON converter
│ └── ingestion/ ← One-time corpus building scripts
│

│
├── UI/
│ ├── app.py ← Flask backend
│ ├── templates/
│ │ ├── index.html ← Homepage
│ │ └── results.html ← Results page
│ └── static/
│ ├── app.js ← Frontend JavaScript
│ ├── style.css ← Styling
│ ├── logo/ ← Logos (Unmochon + 3 ministries)
│ └── pdfjs/ ← PDF.js viewer assets
│
└── diagnostics/
├── evaluate_metrics.py ← 15-question benchmark
├── extract/
│ ├── extractor_stats.py ← Coverage of 10 extractors
│ ├── test_penalty_extractor.py ← Per-extractor tests
│ └── find_all_candidates.py ← Candidate question finder
└── eval/
└── ... (various eval scripts)


---

## What's Built (Working)

### ✅ Core Retrieval Pipeline

- **Hybrid retrieval:** BM25 + MiniLM dense embeddings, fused via Reciprocal Rank Fusion (RRF)
- **Two-stage architecture:** Stage 1 retrieves top-100 clauses; Stage 2 filters to top-3 docs based on intent + extractor firing
- **Bilingual support:** NLLB-200 translates English queries to Bengali before search
- **Ministry inference:** Query keywords auto-detect Social Welfare / Agriculture / Disaster Management
- **Confidence tiers:** High (≥0.7) / Medium / Low / Out-of-scope
- **Out-of-scope detection:** Three-layer gate (score threshold + vocabulary overlap + domain keywords)

### ✅ 10 Extractors (all tested against corpus)

| # | Extractor | Coverage | What it extracts |
|---|---|---|---|
| 1 | `extract_age` | ~5% | Minimum/maximum age requirements |
| 2 | `extract_income_limit` | ~3% | Annual income eligibility limits |
| 3 | `extract_benefit_amount` | Noisy | Allowance amounts per month/year |
| 4 | `extract_document_requirements` | ~10% | Required application documents |
| 5 | `extract_district_allocations` | Corpus-limited | District-wise fund allocations |
| 6 | `extract_office_authority` | 41.9% | Responsible ministries/offices |
| 7 | `extract_deadline_date` | 10.4% | Application deadlines, fiscal years |
| 8 | `extract_frequency` | 9.4% | Payment frequency (monthly, yearly) |
| 9 | `extract_duration_period` | 11.1% | Time durations (validity periods) |
| 10 | `extract_penalty_fine` | 6.6% | Fines and penalties for violations |

### ✅ Plain-Language Explanation Layer

- Template-based baseline (guaranteed safe, never hallucinates)
- Optional Gemini LLM refinement for natural phrasing
- Validation: LLM output must contain all extracted values, else falls back to template
- Uses Gemini 3.6 Flash (free tier, 20 requests/day)
- Only called for top-1 result to reduce latency

### ✅ Date-Aware Conflict Detection (partial)

- Groups results by (program, extractor)
- When same fact has different values across differently-dated documents, flags conflict
- Sorts by document date, marks newest as "বর্তমান" (current), older as "পুরাতন" (superseded)
- **This previews the PT-NLI temporal supersession contribution planned for Capstone C**

### ✅ Web UI (Flask + PDF.js)

- Yandex-style search interface
- Result cards with ministry logos
- Confidence badges (নিশ্চিত তথ্য, সম্ভাব্য উত্তর, মূল লেখা দেখুন)
- Plain-language explanation box ("সহজ ভাষায়:")
- Extracted values displayed prominently
- Collapsible source text
- PDF viewer with page number + text highlighting
- Official government URL link ("সরকারি লিঙ্ক ↗")
- Bilingual toggle (Bengali/English)

### ✅ CLI Chatbot

- Terminal REPL version of the search
- Uses same pipeline as web UI
- Located at `chatbot/scripts/cli_chatbot.py`

### ✅ Evaluation Framework

- 15 curated Q&A pairs with verified ground truth
- Metrics: MRR (0.836), Hit@1 (73.3%), Hit@3 (100%), Hit@5 (100%), Extraction Accuracy (100%), Recall@100 (92.9%)

## Questions

-বয়স্ক ভাতা পেতে সর্বনিম্ন বয়স কত হতে হবে?
-বেদে, দলিত ও হরিজন ভাতার জন্য সর্বনিম্ন বয়স কত?
-চা-শ্রমিক কল্যাণে সর্বনিম্ন বয়স কত?
-বেদে, দলিত ও হরিজন সম্প্রদায়ের ভাতার জন্য প্রার্থীর বার্ষিক আয়সীমা কত? 
-বিধবা ভাতা পেতে প্রার্থীর বার্ষিক আয়সীমা কত?
-চা-শ্রমিক ভাতার প্রার্থীর বার্ষিক আয়সীমা কত?
-সার উৎপাদনকারী হিসেবে নিবন্ধনের জন্য কী কী কাগজপত্র প্রয়োজন?
-বেদে হরিজন ভাতার বয়স এবং আয়সীমা কত?
-চা-শ্রমিক ভাতার বয়স এবং আয়সীমা কত?
-What is the minimum age for Old Age Allowance?
-What is the minimum age and annual income limit for widow allowance?
-What documents are needed to register as a fertilizer dealer?
-শিশু খাদ্য বিতরণের জন্য কোন কর্তৃপক্ষ অর্থ বরাদ্দ প্রদান করে? (No extractor fires — this is deliberate deferral)
-দুর্যোগ ব্যবস্থাপনা কমিটি গঠনের নিয়ম কী? ((No extractor fires — this is deliberate deferral))

##Additional question that sometimes work sometimes dont (controversial)
-সার ডিলার নিয়োগের জন্য কোন কাগজপত্র লাগে?
-বীজ ডিলার নিবন্ধনের জন্য কী প্রয়োজন?
-সার ব্যবস্থাপনা সংশোধন বিধিমালা ২০২১ অনুযায়ী নিবন্ধনের কাগজপত্র কী?

## for manual verification
(chroma) (venv) G:\BD-Policy-RAG-System\diagnostics>python get_pages.py
loading retriever ...
Warning: You are sending unauthenticated requests to the HF Hub. Please set a HF_TOKEN to enable higher rate limits and faster downloads.
Loading weights: 100%|██████████████████████████████████████████████████████████████████████████████| 199/199 [00:00<00:00, 2301.72it/s]
  ready, 15019 items indexed
page   4  |  SocialMin_OldAgeAll_2013_00_Policy_v1.pdf_C0006
page   5  |  SocialMin_OldAgeAll_2013_00_Policy_v1.pdf_C0009
page  11  |  SW_DEPR_Bede, Dalit, AND Harijan_2013_00_Policy_v3_C0032
page  11  |  SW_DEPR_Bede, Dalit, AND Harijan_2013_00_Policy_v3_C0033
page   5  |  SW_Tea Workers_2013_00_Policy_v1_C0007
page   2  |  SW_Tea Workers_2013_00_Policy_webpage_C0008
page   5  |  SociaMin_Widow_2025_09_25_Gazette_v1_C0014
page   5  |  SociaMin_Widow_2025_09_25_Gazette_v1_C0016
page  16  |  013-057_C0016
page  22  |  খসড়া সার (ব্যবস্থাপনা) বিধিমালা ২০২৩_C0069
page   7  |  সার (ব্যবস্থাপনা) (সংশোধন) বিধিমালা- ২০২১ (খসড়া)_C0010
page   7  |  সার ডিলার নিয়োগ ও সার বিতরণ সংক্রান্ত সমন্বিত নীতিমালা-২০২৫_C0007
page  23  |  বীজ বিধিমালা-২০২০_C0023
page  12  |  বীজ ডিলার নিবন্ধন ও নবায়ন_C0018
page  17  |  SW_PM_2017_00_Policy_v1_C0017
page   6  |  সার (ব্যবস্থাপনা) (সংশোধন) বিধিমালা- ২০২১ (খসড়া)_C0007

(chroma) (venv) G:\BD-Policy-RAG-System\diagnostics>

## if you need to check any specific stuff here is question mores detailed note

Category 1 — Basic Bengali extraction (7)
Q1
বয়স্ক ভাতা পেতে সর্বনিম্ন বয়স কত হতে হবে?
Social Welfare
Program: Old Age Allowance (OAA)
Document: SocialMin_OldAgeAll_2013_00_Policy_v1.pdf
Acceptable clause_ids: C0006 (definition clause) or C0009 (scope clause)
Expected answer: 65 বছর (men), 62 বছর (women)
Extractor: extract_age
Expected confidence: high (0.95)
Q2
Question: বেদে, দলিত ও হরিজন ভাতার জন্য সর্বনিম্ন বয়স কত?
Ministry: Social Welfare
Program: Bede/Dalit/Harijan community allowance
Document: SW_DEPR_Bede, Dalit, AND Harijan_2013_00_Policy_v3
Acceptable clause_id: C0032
Expected answer: 50 বছর
Extractor: extract_age
Expected confidence: high (0.95)
Q3
Question: চা-শ্রমিক কল্যাণে সর্বনিম্ন বয়স কত?
Ministry: Social Welfare
Program: Tea Worker food assistance
Document: SW_Tea Workers_2013_00_Policy_v1
Acceptable clause_id: C0007
Expected answer: 18 বছর
Extractor: extract_age
Expected confidence: high (0.95 after marker fix)
Q4
Question:বেদে, দলিত ও হরিজন সম্প্রদায়ের ভাতার জন্য প্রার্থীর বার্ষিক আয়সীমা কত? 
Ministry: Social Welfare
Program: Bede/Dalit/Harijan community allowance
Document: SW_DEPR_Bede, Dalit, AND Harijan_2013_00_Policy_v3
Acceptable clause_id: C0033
Expected answer: 36,000 টাকা
Extractor: extract_income_limit
Expected confidence: high (0.8)
Q5
Question: বিধবা ভাতা পেতে প্রার্থীর বার্ষিক আয়সীমা কত?
Ministry: Social Welfare
Program: Widow Allowance
Document: SociaMin_Widow_2025_09_25_Gazette_v1
Acceptable clause_ids: C0016 (gazette) or C0014 (webpage version)
Expected answer: 15,000 টাকা
Extractor: extract_income_limit
Expected confidence: high (0.8)
Q6
Question: চা-শ্রমিক ভাতার প্রার্থীর বার্ষিক আয়সীমা কত?
Ministry: Social Welfare
Program: Tea Worker food assistance
Documents (either acceptable):
SW_Tea Workers_2013_00_Policy_v1_C0007 → 36,000 টাকা
SW_Tea Workers_2013_00_Policy_webpage_C0008 → 48,000 টাকা
Expected answer: 36,000 OR 48,000 (both acceptable — this is your contradiction demo bridge)
Extractor: extract_income_limit
Expected confidence: high (0.8)
Q7
Question: সার উৎপাদনকারী হিসেবে নিবন্ধনের জন্য কী কী কাগজপত্র প্রয়োজন?
Ministry: Agriculture
Program: Fertilizer producer registration
Documents (any acceptable):
013-057_C0016 (main fertilizer regulation)
খসড়া সার (ব্যবস্থাপনা) বিধিমালা ২০২৩_C0069 (2023 draft rules)
সার (ব্যবস্থাপনা) (সংশোধন) বিধিমালা- ২০২১ (খসড়া)_C0010 (2021 amendment)
Expected answer: Trade License, TIN Certificate, VAT Registration, Bank Solvency Certificate, financial statements
Extractor: extract_document_requirements
Expected confidence: high (0.7)

Category 2 — Multi-intent Bengali (2)
Q11
Question: বেদে হরিজন ভাতার বয়স এবং আয়সীমা কত?
Ministry: Social Welfare
Program: Bede/Dalit/Harijan community allowance
Document: SW_DEPR_Bede, Dalit, AND Harijan_2013_00_Policy_v3
Acceptable clause_ids: C0032 (age 50) and C0033 (income 36,000)
Expected answer: two clauses returned, one with age, one with income
Extractors: extract_age + extract_income_limit
Expected confidence: high (0.95 age, 0.8 income)
Q12
Question: চা-শ্রমিক ভাতার বয়স এবং আয়সীমা কত?
Ministry: Social Welfare
Program: Tea Worker food assistance
Document: SW_Tea Workers_2013_00_Policy_v1
Acceptable clause_id: C0007 (contains BOTH age 18 and income 36,000 in one clause)
Expected answer: single clause with both extracted values
Extractors: extract_age + extract_income_limit
Expected confidence: high

Category 3 — Bilingual English (3)
Q8
Question: What is the minimum age for Old Age Allowance?
Ministry: Social Welfare (search across all)
Translation path: NLLB → "বয়স্কদের জন্য সর্বনিম্ন বয়স কত? বয়স্ক ভাতা"
Document: SocialMin_OldAgeAll_2013_00_Policy_v1.pdf
Acceptable clause_id: C0006
Expected answer: 65
Extractor: extract_age
Expected confidence: high (0.95)
Q9
Question: What is the minimum age and annual income limit for widow allowance?
Ministry: Social Welfare (search across all)
Translation path: NLLB → Bengali normalization → policy dictionary
Document: SociaMin_Widow_2025_09_25_Gazette_v1
Acceptable clause_ids: C0014 (age 18) and C0016 (income 15,000)
Expected answer: both age 18 and income 15,000 from two separate clauses
Extractors: extract_age + extract_income_limit
Expected confidence: medium-high
Q10
Question: What documents are needed to register as a fertilizer dealer?
Ministry: Agriculture (search across all)
Translation path: NLLB → dictionary
Document: fertilizer documents (multiple acceptable)
Expected answer: Trade License, TIN, etc.
Extractor: extract_document_requirements
Expected confidence: high (0.7)

Category 4 — DM low-confidence deferral (2)
Q13 (was labeled Q14 earlier — renumbering for clarity)
Question: শিশু খাদ্য বিতরণের জন্য কোন কর্তৃপক্ষ অর্থ বরাদ্দ প্রদান করে?
Ministry: Disaster Management
Documents: any baby food or dry food allocation memo
Expected behavior: system returns top matching DM clause tagged low-confidence with "মূল লেখা দেখুন" note
No extractor fires — this is deliberate deferral
Q14 (was Q15)
Question: দুর্যোগ ব্যবস্থাপনা কমিটি গঠনের নিয়ম কী?
Ministry: Disaster Management
Documents: Standing Orders on Disaster 2019 or related policy
Expected behavior: low-confidence deferral, top clause returned with source-check note
No extractor fires

Additional Ag documents
Additional Ag Q1 
Question: সার ডিলার নিয়োগের জন্য কোন কাগজপত্র লাগে?
Ministry: Agriculture
Document: সার ডিলার নিয়োগ ও সার বিতরণ সংক্রান্ত সমন্বিত নীতিমালা-২০২৫
Acceptable clause_id: C0007
Status: PASS-but-not-top1 (at rank 3, top-1 is a related but not-acceptable clause)
Additional Ag Q2 (labeled Q9 in test)
Question: বীজ ডিলার নিবন্ধনের জন্য কী প্রয়োজন?
Ministry: Agriculture
Documents (either acceptable):
বীজ বিধিমালা-২০২০_C0023
বীজ ডিলার নিবন্ধন ও নবায়ন_C0018
Status: PASS top-1
Additional Ag Q3 (labeled Q11 in test)
Question: সার ব্যবস্থাপনা সংশোধন বিধিমালা ২০২১ অনুযায়ী নিবন্ধনের কাগজপত্র কী?
Ministry: Agriculture
Document: সার (ব্যবস্থাপনা) (সংশোধন) বিধিমালা- ২০২১ (খসড়া)
Acceptable clause_id: C0007
Status: PASS-but-not-top1 (rank 3)

---


## What's NOT Built (Capstone C)

These items are documented as future work :

### ❌ PT-NLI (Policy-aware Temporal Natural Language Inference)

- **Formal framework:** `Contradiction(ci,cj) = S(ti,tj) ∧ T(τi,τj) ∧ ¬U(ci,cj)`
  - S = semantic conflict via XLM-R NLI
  - T = temporal overlap
  - U = supersession relation
- **85-pair validation experiment:** ablation study (S-only / S+T / S+T+¬U)
- **XLM-R NLI pipeline:** Not implemented; contradiction detection currently rule-based

### ❌ GovKG (NetworkX Supersession Graph)

- Not built. Currently the conflict detector uses metadata dates directly.
- Capstone C plan: NetworkX-based supersession graph to implement `¬U` condition

### ❌ Full Contradiction Detection Corpus

- Only 15 confirmed contradiction pairs currently annotated
- Capstone C target: 250 annotated pairs with Cohen's Kappa ≥ 0.80

### ❌ CIT Ministry (Citizen Services)

- Reserved for Capstone C 
- Not present in current corpus

### ❌ Migration from Gemini to Ollama

- Gemini used for defense (fast, free)
- Capstone C: migrate to locally-hosted Aya-8b or Llama 3.1 8B for reproducibility

### ❌ Bilingual Probe Test

- Translation works end-to-end but no formal probe test with 10-15 mixed queries

### ❌ 20-Question Evaluation Table (formatted as 3 columns)

- Have 15-question evaluation; not yet in the "retrieval correct? / extraction correct? / end-to-end correct?" format

---

## Running the System

### Web UI

```bash
conda activate chroma
cd G:\BD-Policy-RAG-System\UI
python app.py
```

Open browser: http://localhost:5000

### CLI Chatbot

```bash
conda activate chroma
cd G:\BD-Policy-RAG-System\chatbot\scripts
python cli_chatbot.py
```

Type Bengali or English questions. Ctrl+C to exit.

### Evaluation

```bash
conda activate chroma
cd G:\BD-Policy-RAG-System\diagnostics
python evaluate_metrics.py
```

Prints per-question results + aggregate metrics.

### Extractor Coverage Stats

```bash
cd G:\BD-Policy-RAG-System\diagnostics\extract
python extractor_stats.py
```

Prints coverage percentages + sample extractions for all 10 extractors.

### Test Individual Extractor

```bash
cd G:\BD-Policy-RAG-System\diagnostics\extract
python test_penalty_extractor.py    # or test_duration_extractor.py, etc.
```

---

## Evaluation Results

### Current Metrics (15-Question Benchmark)

| Metric | Value | Details |
|---|---|---|
| MRR | 0.836 | Mean Reciprocal Rank |
| Hit@1 | 73.3% | 11/15 |
| Hit@3 | 100% | 15/15 |
| Hit@5 | 100% | 15/15 |
| Extraction Accuracy | 100% | 7/7 on top-1 correct retrievals |
| Recall@10 | 57.1% | 8/14 questions |
| Recall@50 | 71.4% | 10/14 |
| Recall@100 | 92.9% | 13/14 |

### Out-of-Scope Detection

- 33/38 correctly rejected
- 1 false positive: "সমাজকল্যাণ মন্ত্রীর নাম" (asks for minister's name — legitimately out-of-scope)
- 2 false negatives: edge cases where irrelevant queries accepted

### Extractor Component Evaluation

50 real clauses tested across 10 extractors (5 samples per extractor). All extractors fire cleanly at expected confidence tiers. See `extractor_stats.py` output for details.

---

## Known Issues & Limitations

### 🟡 PDF Highlighting

- **Highlighting depends on the source PDF's text layer.** PDF.js searches the extracted text of the PDF, not the visual content.
- **Works for:** PDFs with proper Unicode text layer (~60% of the corpus). These highlight the answer sentence correctly when the viewer opens.
- **Does NOT work for:** 
  - Scanned PDFs without a text layer (image-only)
  - PDFs with Bijoy-encoded fonts (older Bangladesh government documents)
  - PDFs where Bengali text uses non-standard Unicode composition
- **Fallback:** When highlighting fails silently, the PDF still opens at the correct page. Users can visually locate the answer by matching the clause text shown in the search result card.
- **Root cause:** Bangladesh government publishes many older documents (pre-2018) as scans or with legacy encodings that predate Unicode Bengali standardization. This is a corpus quality issue, not a system flaw. Capstone C plan: re-OCR affected PDFs with Tesseract Bengali to produce searchable text layers.


### 🔴 Critical Issues

1. **Gemini API rate limit (20 requests/day free tier)**
   - After 20 queries, LLM refinement fails, template fallback used instead
   - Workaround: use fresh Google account for defense day
   - Long-term: migrate to Ollama in Capstone C

2. **Slow response time when Gemini is rate-limited**
   - Each API call retries with backoff, adding ~10 seconds per failed call
   - Currently only top-1 result gets LLM refinement (others use template) to reduce load
   - Total response time normally ~3-5 seconds; can spike to 30+ seconds if Gemini is being retried

3. **Page number citation accuracy varies**
   - Some documents have unreliable page_number fields (fragments of larger compilations)
   - `printed_page_number` detection script only achieves 16-47% coverage
   - **Do not overpromise page-perfect citations during demo**

### 🟡 Moderate Issues

4. **Retrieval precision for narrow topical queries**
   - System works well for specific policy queries with distinctive vocabulary
   - Struggles with generic queries ("which ministry handles X?")
   - Root cause: BM25+MiniLM insufficient precision at document level

5. **Bengali digit vs Latin digit inconsistency**
   - Extractor output sometimes uses Latin digits (65), sometimes Bengali (৬৫)
   - Normalization added in comparison logic, but display can be inconsistent

6. **Widow/Bede contamination**
   - Old bug: Bede queries returned Widow content
   - Fixed via ministry inference + doc-name keyword boost
   - Watch for regression if similar programs are added

7. **Conflict detection false positives**
   - Extractor may fire on unrelated numbers within same document
   - Example: Tea Workers doc has "62 years retirement" and "35 years minimum" — flagged as conflict even though they mean different things
   - Mitigated by requiring conflicts across different documents

### 🟢 Minor Issues

8. **Bijoy-encoded PDFs**
   - Several older PDFs use Bijoy encoding, not Unicode
   - Flagged in metadata, some content may be garbled
   - Requires manual conversion (not automated)

9. **Deprecated Gemini SDK warning**
   - `google-generativeai` package is deprecated
   - Still works but shows warning on every import
   - Migrate to `google-genai` in Capstone C

---

## File-by-File Guide

### `UI/app.py` — Flask Backend

Main entry point. Contains:
- `/` — home page
- `/results` — results page (renders template)
- `/ask` — POST endpoint, runs full pipeline, returns JSON
- `/pdf/<path>` — serves PDF files
- `/pdfjs/<path>` — serves PDF.js viewer assets

Key functions:
- `_infer_ministry(query)` — keyword-based ministry detection
- `_lookup_metadata(doc_id)` — get display name + source URL from JSON
- `_get_doc_date(doc_id)` — get date_sortable + date_display
- `_get_program(doc_id)` — get program name for conflict grouping
- `_format_extracted(extracted)` — convert extractor output to UI format
- `_viewer_url(...)` — build PDF.js viewer URL with page + highlight
- `detect_conflicts(results)` — find date-based conflicts across docs

### `scripts/retrieval/two_stage.py` — Main Pipeline

Orchestrates the full search flow:
- Stage 1: BM25 + Dense fusion, top-100 clauses
- Stage 2: Group by document, apply intent-aware filter
- Extractor re-ranking based on intent
- Confidence tiering (high/medium/low/out-of-scope)

### `scripts/retrieval/search.py` — HybridRetriever

Wraps BM25 (rank_bm25 library) + MiniLM dense embeddings via ChromaDB.
- `search(question, top_k, ministry)` — returns ranked clauses

### `scripts/retrieval/translator.py` — Bilingual Support

Uses `facebook/nllb-200-distilled-600M` for English → Bengali translation.
- `to_bengali(text)` — translates if English, passes through if Bengali

### `chatbot/scripts/ner.py` — 10 Extractors

Regex-based fact extraction. Each extractor returns `(value, confidence)`.
Extractors:
1. `extract_age` — age numbers
2. `extract_income_limit` — annual income limits (টাকা)
3. `extract_benefit_amount` — allowance amounts
4. `extract_document_requirements` — required documents list
5. `extract_district_allocations` — district-wise allocations
6. `extract_office_authority` — ministries/offices
7. `extract_deadline_date` — deadlines, dates
8. `extract_frequency` — payment frequency
9. `extract_duration_period` — duration/validity periods
10. `extract_penalty_fine` — fines/penalties

### `chatbot/scripts/intent.py` — Intent Classification

Keyword-based intent detection. `detect_intents(query)` returns list of matched intents.
Intents map to extractors via `extractor_map.py`.

### `chatbot/scripts/explainer.py` — Gemini LLM Layer

- Template-based fallback (safe)
- Optional Gemini refinement (natural language)
- Validation: rejects LLM output missing extracted values
- Uses `.gemini_key` for API access

### `UI/static/app.js` — Frontend Rendering

- `runSearch(question)` — hits `/ask`, renders results
- `renderResults(data)` — orchestrates render
- `renderCard(res, isTop)` — regular result card
- `renderConflictCard(conflict)` — yellow conflict card
- `ministryLogoFile(ministry)` — maps ministry to logo

### `UI/static/style.css` — Styling

- Yandex-inspired design
- CSS variables for theming (`--green`, `--maroon`)
- Result cards with ministry logos
- Conflict card with yellow accent

---

## Common Errors & Fixes

### `ModuleNotFoundError: No module named 'chromadb'`

**Cause:** Wrong conda environment.  
**Fix:**
```bash
conda activate chroma
```

### `FileNotFoundError: '.gemini_key'`

**Cause:** API key file missing.  
**Fix:** Create file at `G:\BD-Policy-RAG-System\.gemini_key` with your key.

### `[explainer] LLM refinement failed: 429 Quota exceeded`

**Cause:** Hit Gemini free tier limit (20 requests/day).  
**Fix:** Template fallback works automatically. For long-running usage, get new API key from fresh Google account.

### Page loads but no results appear

**Cause:** Flask backend not running or wrong URL.  
**Fix:** Ensure `python app.py` is running in `UI/` folder. Open http://localhost:5000.

### `KeyError: 'display_name'` or similar

**Cause:** Metadata JSON not built or corrupted.  
**Fix:** Rebuild metadata:
```bash
python scripts/metadata/build_metadata_sourcelink.py
```

### PDFs don't load in viewer

**Cause:** URL encoding issue with commas in filenames.  
**Fix:** Verified in code — uses `quote(path, safe="/")` single-pass encoding.

### Conflict card shows wrong data

**Cause:** Extractor firing on unrelated numbers within same doc.  
**Fix:** Now requires 2+ different documents for conflict. Confidence threshold 0.85.

### `renderConflictCard is not defined`

**Cause:** Function defined outside the IIFE in `app.js`.  
**Fix:** Function must be inside `(function () { ... })();` block.

### Slow response (30+ seconds)

**Cause:** Gemini API being retried due to rate limit.  
**Fix:** Only top-1 result gets LLM refinement. Check terminal for 429 errors.

---

## Defense Day Checklist

- [ ] Test on defense laptop (Windows Terminal for Bengali fonts, NOT cmd)
- [ ] Verify Gemini API key not exhausted (or use fresh account)
- [ ] Uninstall/disable IDM extension (it hijacks PDF URLs)
- [ ] Verify Flask starts cleanly
- [ ] Run through 10 test queries to warm up caches
- [ ] Check PDF.js viewer works for all three ministries
- [ ] Ensure metadata JSON is up-to-date
- [ ] Screenshot key results as backup slides



### Demo Flow (Suggested)

**Part 1: Retrieval**
- Query: "বয়স্ক ভাতা পেতে সর্বনিম্ন বয়স কত?"
- Show: Correct answer, PDF opens at right page with highlighting
- Explain: extractor + template + LLM refinement

**Part 2: Bilingual**
- Query: "What is the minimum age for Old Age Allowance?"
- Show: NLLB translation happens invisibly, same answer returned

**Part 3: Out-of-scope**
- Query: "পিজ্জা কীভাবে বানাব?"
- Show: Rejected with yellow card explaining why

**Part 4: Contradiction detection (temporal)**
- Query: "বিধবা ভাতার আয়সীমা কত?"
- Show: Yellow conflict card at top, 15,000 (2025) marked current, older values marked superseded
- Explain: This previews the PT-NLI contribution planned for Capstone C

### If Something Breaks

- **Terminal freezes:** Ctrl+C to kill, restart Flask
- **Gemini fails:** Point to template output, explain LLM is optional
- **PDF doesn't open:** Show extracted values, explain PDF viewer is polish
- **Any Python error:** Show the CLI chatbot instead (`cli_chatbot.py`)

### What NOT to Overpromise

- Do NOT claim 100% precision on retrieval
- Do NOT claim contradiction detection is complete (it's a preview)
- Do NOT claim page numbers are always perfect
- Do NOT hide the Gemini fallback (be honest about template fallback)

---

*Last updated: August 28, 2026*