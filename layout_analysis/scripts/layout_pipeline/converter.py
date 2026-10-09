import json
import os
import pytesseract
from PIL import Image

LABELS   = ["HEADER", "CLAUSE", "TABLE", "FOOTER", "SECTION_TITLE"]
LABEL2ID = {l: i for i, l in enumerate(LABELS)}
ID2LABEL = {i: l for i, l in enumerate(LABELS)}


def get_image_filename(task):
    # strip Label Studio hash prefix: 049067a9-doc0001_p1.png -> doc0001_p1.png
    raw = os.path.basename(task["data"]["image"])
    if "-" in raw:
        parts = raw.split("-", 1)
        if parts[1].startswith("doc"):
            return parts[1]
    return raw


def load_tasks(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def percent_to_pixels(v, img_w, img_h):
    x1 = v["x"] / 100 * img_w
    y1 = v["y"] / 100 * img_h
    x2 = x1 + v["width"]  / 100 * img_w
    y2 = y1 + v["height"] / 100 * img_h
    return [x1, y1, x2, y2]


def norm_1000(box, img_w, img_h):
    x1, y1, x2, y2 = box
    return [
        max(0, min(1000, int(1000 * x1 / img_w))),
        max(0, min(1000, int(1000 * y1 / img_h))),
        max(0, min(1000, int(1000 * x2 / img_w))),
        max(0, min(1000, int(1000 * y2 / img_h))),
    ]


def word_label(word_px_box, regions_px):
    cx = (word_px_box[0] + word_px_box[2]) / 2
    cy = (word_px_box[1] + word_px_box[3]) / 2
    for label, rb in regions_px:
        if rb[0] <= cx <= rb[2] and rb[1] <= cy <= rb[3]:
            return label
    return None


def tesseract_words(image):
    data = pytesseract.image_to_data(image, lang="ben+eng",
                                     output_type=pytesseract.Output.DICT)
    items = []
    for i in range(len(data["text"])):
        w = str(data["text"][i]).strip()
        if not w or int(data["conf"][i]) < 0:
            continue
        x, y = data["left"][i], data["top"][i]
        bw, bh = data["width"][i], data["height"][i]
        items.append({
            "word": w,
            "box": [x, y, x + bw, y + bh],
            "block": data["block_num"][i],
            "top": y,
            "left": x,
        })
    items.sort(key=lambda d: (d["block"], d["top"], d["left"]))
    return items


def build_examples(export_path, images_dir):
    tasks = load_tasks(export_path)
    examples = []
    skipped = 0
    no_word_pages = 0

    for task in tasks:
        fn = get_image_filename(task)
        img_path = os.path.join(images_dir, fn)
        if not os.path.exists(img_path):
            skipped += 1
            continue

        anns = task.get("annotations", [])
        if not anns or not anns[0].get("result"):
            skipped += 1
            continue

        img = Image.open(img_path).convert("RGB")
        img_w, img_h = img.size

        regions_px = []
        for r in anns[0]["result"]:
            v = r.get("value", {})
            labs = v.get("rectanglelabels", [])
            if not labs or labs[0] not in LABEL2ID:
                continue
            regions_px.append((labs[0], percent_to_pixels(v, img_w, img_h)))

        if not regions_px:
            skipped += 1
            continue

        tokens = tesseract_words(img)
        if not tokens:
            no_word_pages += 1
            continue

        words, boxes, labels = [], [], []
        for t in tokens:
            lab = word_label(t["box"], regions_px)
            if lab is None:
                continue
            words.append(t["word"])
            boxes.append(norm_1000(t["box"], img_w, img_h))
            labels.append(LABEL2ID[lab])

        if not words:
            no_word_pages += 1
            continue

        examples.append({
            "words": words,
            "boxes": boxes,
            "labels": labels,
            "image_path": img_path,
        })

    print(f"Examples built : {len(examples)}")
    print(f"Skipped        : {skipped}")
    print(f"No-word pages  : {no_word_pages}")
    return examples