from original_paths import project_path
"""Run the trained LiLT model over the full Social Welfare corpus,
assigning a layout_label to every clause - not just the 1,181
annotated pages, but everything in Social_Welfare_clauses.jsonl.

Word-box files are matched by PREFIX, not exact filename, because
clause doc_ids are truncated versions of the real document titles
(a pre-existing OCR/chunking issue unrelated to this script) - e.g.
clause doc_id "...বেতন খাতে " vs real filename
"...বেতন খাতে অর্থ বরাদ্দ ও মঞ্জুরি প্রদান_p001.json".
"""

import json
import os
from collections import defaultdict, Counter

import torch
from transformers import AutoTokenizer, AutoModelForTokenClassification

MODEL_DIR = os.getenv("LAYOUT_MODEL_DIR", project_path('layout_analysis/models/lilt_sw_v1'))
JSONL_PATH = project_path('data/processed_jsonl/Social_Welfare_clauses.jsonl')
WORD_BOX_DIR = project_path('layout_analysis/data/word_boxes')

LABEL_LIST = [
    "O", "CLAUSE", "text", "SECTION_TITLE", "Sub_Section", "METADATA",
    "TABLE", "FOOTER", "HEADER", "Page_header", "Signature", "Caption",
    "Fig_with_value", "Fig_without_value",
]
ID_TO_LABEL = {i: l for i, l in enumerate(LABEL_LIST)}


def normalize_bbox(bbox, w, h):
    x1, y1, x2, y2 = bbox
    return [int(1000*x1/w), int(1000*y1/h), int(1000*x2/w), int(1000*y2/h)]


def load_word_boxes(doc_id, page_number, word_box_files):
    """Find the word-box file whose name starts with this doc_id and
    has the right page number. Prefix match, not exact - see module
    docstring for why."""
    suffix = f"_p{page_number:03d}.json"
    doc_id_clean = doc_id.strip()
    prefix = doc_id_clean[:40]

    from original_paths import PROJECT_ROOT
    mapping_path = PROJECT_ROOT / "docs" / "long_filename_mapping.json"
    reverse = {v: k for k, v in json.loads(mapping_path.read_text(encoding="utf-8")).items()} if mapping_path.exists() else {}
    for fname in word_box_files:
        original_name = reverse.get(fname, fname)
        if original_name.endswith(suffix) and original_name.startswith(prefix):
            path = os.path.join(WORD_BOX_DIR, fname)
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    return None



def predict_page_labels(words, boxes, img_w, img_h, tokenizer, model, device):
    """Run the model on one page's words, return {word_index: label}.

    LiLT takes bbox as a direct model input, not a tokenizer keyword -
    same fix as in 7_train.py. Tokenize words normally, get word_ids
    to know which subwords belong to which word, then build the bbox
    tensor separately and pass both to the model.
    """
    if not words:
        return {}

    norm_boxes = [normalize_bbox(b, img_w, img_h) for b in boxes]

    encoded = tokenizer(
        words,
        truncation=True, is_split_into_words=True,
        padding="max_length", max_length=128, return_tensors="pt",
    )
    word_ids = encoded.word_ids(batch_index=0)

    # Build the bbox sequence to match token positions - every subword
    # of a word repeats that word's box, padding gets [0,0,0,0]
    bbox_seq = []
    for word_id in word_ids:
        if word_id is None:
            bbox_seq.append([0, 0, 0, 0])
        else:
            bbox_seq.append(norm_boxes[word_id])

    encoded["bbox"] = torch.tensor([bbox_seq])
    encoded = {k: v.to(device) for k, v in encoded.items()}

    with torch.no_grad():
        outputs = model(**encoded)
    predictions = torch.argmax(outputs.logits, dim=2)[0].cpu().tolist()

    word_preds = {}
    for token_idx, word_id in enumerate(word_ids):
        if word_id is None or word_id in word_preds:
            continue
        word_preds[word_id] = ID_TO_LABEL[predictions[token_idx]]

    return word_preds


def clause_layout_label(labels_in_clause):
    """A clause spans many words, each with its own predicted label.
    Take the most common label across the clause as its overall tag."""
    if not labels_in_clause:
        return "CLAUSE"  # fallback to the old stub default
    return Counter(labels_in_clause).most_common(1)[0][0]


def main():
    print("Loading model ...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = AutoModelForTokenClassification.from_pretrained(MODEL_DIR).to(device)
    model.eval()
    print(f"  device: {device}")

    print("Listing word-box files ...")
    word_box_files = os.listdir(WORD_BOX_DIR)
    print(f"  {len(word_box_files)} files available")

    print("Loading clauses ...")
    clauses = [json.loads(l) for l in open(JSONL_PATH, encoding="utf-8") if l.strip()]
    print(f"  {len(clauses)} clauses")

    by_page = defaultdict(list)
    for c in clauses:
        by_page[(c["doc_id"], c["page_number"])].append(c)
    print(f"  {len(by_page)} unique pages")

    updated = 0
    no_wordbox = 0

    for i, ((doc_id, page_num), page_clauses) in enumerate(by_page.items()):
        wb = load_word_boxes(doc_id, page_num, word_box_files)
        if wb is None:
            no_wordbox += 1
            continue

        words = [w["text"] for w in wb["words"]]
        boxes = [w["bbox"] for w in wb["words"]]

        word_preds = predict_page_labels(
            words, boxes, wb["image_width"], wb["image_height"],
            tokenizer, model, device,
        )

        for c in page_clauses:
            c_bbox = c.get("bbox")
            if not c_bbox:
                continue
            cx1, cy1, cx2, cy2 = c_bbox
            labels_in_clause = []
            for idx, w in enumerate(wb["words"]):
                wx1, wy1, wx2, wy2 = w["bbox"]
                wcx, wcy = (wx1 + wx2) / 2, (wy1 + wy2) / 2
                if cx1 <= wcx <= cx2 and cy1 <= wcy <= cy2:
                    if idx in word_preds:
                        labels_in_clause.append(word_preds[idx])
            c["layout_label"] = clause_layout_label(labels_in_clause)
            updated += 1

        if (i + 1) % 100 == 0:
            print(f"  processed {i+1}/{len(by_page)} pages")

    print(f"\nupdated: {updated} clauses")
    print(f"no word boxes found: {no_wordbox} pages (left as stub default)")

    with open(JSONL_PATH, "w", encoding="utf-8") as f:
        for c in clauses:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print(f"Written to: {JSONL_PATH}")


if __name__ == "__main__":
    main()