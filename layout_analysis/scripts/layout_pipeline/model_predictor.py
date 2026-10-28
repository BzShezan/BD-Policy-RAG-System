import torch
from transformers import AutoTokenizer, LiltForTokenClassification
from .converter import ID2LABEL


def load_model(model_dir):
    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    model = LiltForTokenClassification.from_pretrained(model_dir)
    model.eval()
    if torch.cuda.is_available():
        model.cuda()
    return model, tokenizer


def predict_words(words, boxes, model, tokenizer, max_len=512):
    """
    words: list[str], boxes: list[[x1,y1,x2,y2]] normalized 0-1000.
    Returns list of (word, box, predicted_label) aligned to input words.
    XLM-R tokenizer takes no boxes; we expand boxes to subwords manually.
    """
    if not words:
        return []

    enc = tokenizer(
        words,
        is_split_into_words=True,
        truncation=True,
        padding="max_length",
        max_length=max_len,
        return_tensors="pt",
    )
    word_ids = enc.word_ids(0)

    import torch as _torch
    bbox_seq = []
    for wid in word_ids:
        bbox_seq.append([0, 0, 0, 0] if wid is None else boxes[wid])
    enc["bbox"] = _torch.tensor([bbox_seq], dtype=_torch.long)

    inputs = {k: v.to(model.device) for k, v in enc.items()}
    with torch.no_grad():
        logits = model(**inputs).logits[0]
    pred_ids = logits.argmax(-1).tolist()

    out = []
    seen = set()
    for pos, wid in enumerate(word_ids):
        if wid is None or wid in seen:
            continue
        seen.add(wid)
        label = ID2LABEL.get(pred_ids[pos], "CLAUSE")
        out.append((words[wid], boxes[wid], label))
    return out


def merge_regions(word_preds):
    """
    Merge consecutive words with the same label into regions.
    Returns [{label, box[0-1000]}].
    """
    if not word_preds:
        return []
    regions = []
    cur_label = word_preds[0][2]
    cur_box = list(word_preds[0][1])
    for _, box, label in word_preds[1:]:
        if label == cur_label:
            cur_box[0] = min(cur_box[0], box[0])
            cur_box[1] = min(cur_box[1], box[1])
            cur_box[2] = max(cur_box[2], box[2])
            cur_box[3] = max(cur_box[3], box[3])
        else:
            regions.append({"label": cur_label, "box": cur_box})
            cur_label = label
            cur_box = list(box)
    regions.append({"label": cur_label, "box": cur_box})
    return regions


def denorm(box_1000, page_w_pt, page_h_pt):
    x1, y1, x2, y2 = box_1000
    return [
        round(x1 / 1000 * page_w_pt, 2),
        round(y1 / 1000 * page_h_pt, 2),
        round(x2 / 1000 * page_w_pt, 2),
        round(y2 / 1000 * page_h_pt, 2),
    ]


def classify_clause(clause_bbox_pt, regions_1000, page_w_pt, page_h_pt):
    """
    Assign a layout label to an existing OCR clause by max overlap
    between its PDF-point bbox and the model's predicted regions.
    """
    if not clause_bbox_pt or not regions_1000:
        return "CLAUSE"
    cx1, cy1, cx2, cy2 = clause_bbox_pt
    best, best_ov = "CLAUSE", 0
    for r in regions_1000:
        rx1, ry1, rx2, ry2 = denorm(r["box"], page_w_pt, page_h_pt)
        ox = max(0, min(cx2, rx2) - max(cx1, rx1))
        oy = max(0, min(cy2, ry2) - max(cy1, ry1))
        ov = ox * oy
        if ov > best_ov:
            best_ov, best = ov, r["label"]
    return best