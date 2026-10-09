from original_paths import project_path
import os
import sys
import fitz

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scripts.ocr_pipeline.ocr import extract_page_text, cleanup_tmp, APSIS_AVAILABLE
from scripts.ocr_pipeline.tables import extract_tables, has_tables
from scripts.ocr_pipeline.chunker import chunk_text
from scripts.ocr_pipeline.checkpoint import load_checkpoint, mark_done, log_skipped, save_results

# ============================================================
# CHANGE THESE TWO LINES PER MINISTRY RUN
# ============================================================
MINISTRY_TAG = os.getenv("OCR_MINISTRY", "Social_Welfare")
INPUT_FOLDER = os.getenv("OCR_INPUT_DIR", project_path("data/raw_pdfs/social_welfare"))
# ============================================================

from original_paths import PROCESSED_DIR
BASE = PROCESSED_DIR
TAG   = MINISTRY_TAG.replace(' ', '_')

CLEAN_FILE      = os.path.join(BASE, f"{TAG}_clauses.jsonl")
REVIEW_FILE     = os.path.join(BASE, f"{TAG}_clauses_review.jsonl")
TABLES_FILE     = os.path.join(BASE, f"{TAG}_tables.jsonl")
CHECKPOINT_FILE = os.path.join(BASE, f"{TAG}_checkpoint.txt")
SKIPPED_FILE    = os.path.join(BASE, f"{TAG}_skipped.txt")


def process_pdf(pdf_path, doc_id):
    doc = fitz.open(pdf_path)
    if doc.page_count == 0:
        doc.close()
        raise ValueError("PDF has 0 pages")

    all_chunks = []
    all_tables = []
    counter = 1

    for i, page in enumerate(doc):
        page_num = i + 1

        try:
            # table extraction (PyMuPDF native)
            if has_tables(page):
                rows = extract_tables(page, doc_id, page_num, MINISTRY_TAG)
                all_tables.extend(rows)
                print(f"      [Page {page_num}] Table: {len(rows)} rows")

            # text + word boxes
            result     = extract_page_text(page)
            text       = result["text"]
            method     = result["ocr_method"]
            quality    = result["quality"]
            review     = result["needs_review"]
            word_boxes = result["word_boxes"]

            if not text.strip():
                print(f"      [Page {page_num}] No text")
                continue

            bbox_count = len(word_boxes)
            status = f"q={quality:.2f} {'REVIEW' if review else 'OK'} boxes={bbox_count}"
            print(f"      [Page {page_num}] {method} ({status})")

            # chunking with bbox
            chunks, counter = chunk_text(
                text, doc_id, page_num, method, quality, review,
                MINISTRY_TAG, word_boxes, counter
            )
            all_chunks.extend(chunks)

        except Exception as e:
            print(f"      [Page {page_num}] ERROR: {e}")
            all_chunks.append({
                "clause_id":     f"{doc_id}_C{counter:04d}",
                "text":          f"[PAGE FAILED: {str(e)}]",
                "doc_id":        doc_id,
                "section":       "0",
                "tag":           MINISTRY_TAG,
                "page_number":   page_num,
                "ocr_method":    "failed",
                "quality_score": 0.0,
                "language":      "Unknown",
                "needs_review":  True,
                "is_table":      False,
                "bbox":          None,
            })
            counter += 1

    doc.close()
    return all_chunks, all_tables


def main():
    os.makedirs(BASE, exist_ok=True)

    print(f"\nMinistry : {MINISTRY_TAG}")
    print(f"Input    : {INPUT_FOLDER}")
    print(f"ApsisOCR : {'yes' if APSIS_AVAILABLE else 'no'}\n")

    done = load_checkpoint(CHECKPOINT_FILE)
    if done:
        print(f"Resuming — {len(done)} PDFs done\n")

    pdf_files = []
    for root, _, files in os.walk(INPUT_FOLDER):
        for f in sorted(files):
            full = os.path.join(root, f)
            if f.lower().endswith('.pdf'):
                pdf_files.append(full)
            elif f.lower().endswith('.pdf.skip'):
                log_skipped(SKIPPED_FILE, f, "renamed to .skip")

    print(f"Found {len(pdf_files)} PDFs\n")

    total_clean = total_review = total_tables = 0
    bbox_found = bbox_missed = 0

    for pdf_path in pdf_files:
        filename = os.path.basename(pdf_path)
        doc_id   = os.path.splitext(filename)[0][:80]

        if doc_id in done:
            print(f"Skip : {filename[:70]}")
            continue

        print(f"\n{filename[:70]}")

        try:
            chunks, table_rows = process_pdf(pdf_path, doc_id)

            n_clean, n_review, n_tables = save_results(
                CLEAN_FILE, REVIEW_FILE, TABLES_FILE, chunks, table_rows
            )
            total_clean  += n_clean
            total_review += n_review
            total_tables += n_tables

            # count bbox hits
            for c in chunks:
                if c.get("bbox"):
                    bbox_found += 1
                else:
                    bbox_missed += 1

            mark_done(CHECKPOINT_FILE, doc_id)
            print(f"   {n_clean}/{len(chunks)} clean | {n_tables} tables | bbox: {sum(1 for c in chunks if c.get('bbox'))}/{len(chunks)}")

        except Exception as e:
            print(f"   FAILED: {e}")
            log_skipped(SKIPPED_FILE, filename, str(e))
            save_results(CLEAN_FILE, REVIEW_FILE, TABLES_FILE, [{
                "clause_id":     f"{doc_id}_C0001",
                "text":          f"[PDF FAILED: {str(e)}]",
                "doc_id":        doc_id,
                "section":       "0",
                "tag":           MINISTRY_TAG,
                "page_number":   0,
                "ocr_method":    "failed",
                "quality_score": 0.0,
                "language":      "Unknown",
                "needs_review":  True,
                "is_table":      False,
                "bbox":          None,
            }], [])
            mark_done(CHECKPOINT_FILE, doc_id)

    cleanup_tmp()

    total = total_clean + total_review
    print(f"\n{'='*55}")
    print(f"COMPLETE : {MINISTRY_TAG}")
    print(f"{'='*55}")
    print(f"Clean      : {total_clean}")
    print(f"Review     : {total_review}")
    print(f"Tables     : {total_tables}")
    print(f"bbox found : {bbox_found}/{total} ({100*bbox_found//max(total,1)}%)")
    print(f"bbox missed: {bbox_missed}/{total}")


if __name__ == "__main__":
    main()