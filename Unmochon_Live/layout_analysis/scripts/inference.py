from original_paths import project_path
import os
import sys
import json
import fitz
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from layout_analysis.scripts.layout_pipeline.model_predictor import (
    load_model, predict_words, merge_regions, classify_clause,
)
from layout_analysis.scripts.layout_pipeline.heuristics import apply_header_footer_rules
from layout_analysis.scripts.layout_pipeline.table_detect import region_is_table
from layout_analysis.scripts.layout_pipeline.visualizer import draw_regions_on_image

MODEL_DIR = os.getenv("LAYOUT_MODEL_DIR", project_path('layout_analysis/models/lilt_sw'))
CLAUSES_FILE = project_path('data/processed_jsonl/Social_Welfare_clauses.jsonl')
PDF_DIR      = project_path('data/raw_pdfs/social_welfare')
OUTPUT_FILE  = CLAUSES_FILE.replace(".jsonl", "_with_layout.jsonl")
SAMPLE_DIR   = project_path('layout_analysis/output/inference_samples')
RENDER_DPI   = 150
PX_TO_PT     = 72.0 / RENDER_DPI

import pytesseract


def find_pdf(doc_id):
    for f in os.listdir(PDF_DIR):
        if f.lower().endswith(".pdf") and os.path.splitext(f)[0][:80] == doc_id:
            return os.path.join(PDF_DIR, f)
    for f in os.listdir(PDF_DIR):
        if f.lower().endswith(".pdf") and doc_id[:20] in f:
            return os.path.join(PDF_DIR, f)
    return None


def page_words_boxes(pil_img):
    """Tesseract words for a rendered page, boxes normalized 0-1000, sorted."""
    data = pytesseract.image_to_data(pil_img, lang="ben+eng",
                                     output_type=pytesseract.Output.DICT)
    W, H = pil_img.size
    items = []
    for i in range(len(data["text"])):
        w = str(data["text"][i]).strip()
        if not w or int(data["conf"][i]) < 0:
            continue
        x, y = data["left"][i], data["top"][i]
        bw, bh = data["width"][i], data["height"][i]
        items.append((data["block_num"][i], y, x, w,
                      [max(0, min(1000, int(1000 * x / W))),
                       max(0, min(1000, int(1000 * y / H))),
                       max(0, min(1000, int(1000 * (x + bw) / W))),
                       max(0, min(1000, int(1000 * (y + bh) / H)))]))
    items.sort(key=lambda t: (t[0], t[1], t[2]))
    words = [t[3] for t in items]
    boxes = [t[4] for t in items]
    return words, boxes


def main():
    print("Loading LiLT model...")
    model, tokenizer = load_model(MODEL_DIR)

    clauses = [json.loads(l) for l in open(CLAUSES_FILE, encoding="utf-8") if l.strip()]
    print(f"Clauses: {len(clauses)}")
    os.makedirs(SAMPLE_DIR, exist_ok=True)

    page_cache = {}   # (doc_id, page) -> {regions, page_w, page_h, page_bgr}
    pdf_cache  = {}
    samples_saved = 0

    for i, c in enumerate(clauses):
        if i % 100 == 0:
            print(f"  {i}/{len(clauses)}")

        doc_id = c.get("doc_id", "")
        page_num = c.get("page_number", 1)
        bbox = c.get("bbox")
        key = (doc_id, page_num)

        if key not in page_cache:
            if doc_id not in pdf_cache:
                pdf_cache[doc_id] = find_pdf(doc_id)
            path = pdf_cache[doc_id]
            if not path:
                page_cache[key] = None
            else:
                try:
                    doc = fitz.open(path)
                    page = doc[page_num - 1]
                    pw, ph = page.rect.width, page.rect.height
                    pix = page.get_pixmap(dpi=RENDER_DPI)
                    pil = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    bgr = np.array(pil)[:, :, ::-1].copy()

                    words, boxes = page_words_boxes(pil)
                    preds = predict_words(words, boxes, model, tokenizer)
                    regions = merge_regions(preds)

                    page_cache[key] = {"regions": regions, "pw": pw, "ph": ph, "bgr": bgr}

                    if samples_saved < 20:
                        out = os.path.join(SAMPLE_DIR, f"{doc_id[:30]}_p{page_num}.png")
                        draw_regions_on_image(pil, regions, out)
                        samples_saved += 1
                    doc.close()
                except Exception:
                    page_cache[key] = None

        cached = page_cache[key]
        if not cached:
            c["layout_label"] = "CLAUSE"
            continue

        # 1) base label from LiLT via overlap
        label = classify_clause(bbox, cached["regions"], cached["pw"], cached["ph"])

        # 2) header/footer geometric override
        hf = apply_header_footer_rules(bbox, cached["ph"], c.get("text", ""))
        if hf:
            label = hf

        # 3) table override via OpenCV (only if not already header/footer)
        elif bbox and region_is_table(cached["bgr"], bbox, cached["pw"], cached["ph"]):
            label = "TABLE"

        c["layout_label"] = label

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for c in clauses:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    from collections import Counter
    dist = Counter(c.get("layout_label", "CLAUSE") for c in clauses)
    print(f"\nDone. Label distribution: {dict(dist)}")
    print(f"Output: {OUTPUT_FILE}")
    print(f"Samples: {SAMPLE_DIR}")
    print(f"\nReplace original:\n  copy \"{OUTPUT_FILE}\" \"{CLAUSES_FILE}\"")


if __name__ == "__main__":
    main()