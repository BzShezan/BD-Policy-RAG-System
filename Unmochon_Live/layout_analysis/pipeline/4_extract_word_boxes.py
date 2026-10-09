from original_paths import project_path
import os
import json
import fitz
import pytesseract
from PIL import Image
import time

REEXPORT_FOLDER = project_path('layout_analysis/workspace/reexport_named')
SIDECAR_FOLDER = project_path('layout_analysis/workspace/word_boxes')
os.makedirs(SIDECAR_FOLDER, exist_ok=True)

manifest = json.load(open(os.path.join(REEXPORT_FOLDER, "manifest.json"), encoding="utf-8"))
mapping = json.load(open("page_image_mapping.json", encoding="utf-8"))

needed = set()
for fname, info in mapping.items():
    needed.add((info["doc_id"], info["page_number"]))

print(f"pages needing word boxes: {len(needed)}")

def ocr_with_retry(img, retries=3):
    for attempt in range(retries):
        try:
            return pytesseract.image_to_data(img, lang='ben+eng', output_type=pytesseract.Output.DICT)
        except PermissionError:
            if attempt < retries - 1:
                time.sleep(1)
                continue
            raise

done = 0
failed = []

for doc_id, page_num in sorted(needed):
    out_path = os.path.join(SIDECAR_FOLDER, f"{doc_id}_p{page_num:03d}.json")
    if os.path.exists(out_path):
        done += 1
        continue

    img_path = os.path.join(REEXPORT_FOLDER, f"{doc_id}_p{page_num:03d}.png")
    if not os.path.exists(img_path):
        print(f"missing image: {img_path}")
        continue

    img = Image.open(img_path)

    try:
        data = ocr_with_retry(img)
    except Exception as e:
        print(f"FAILED (will retry later): {doc_id}_p{page_num:03d}  [{e}]")
        failed.append(f"{doc_id}_p{page_num:03d}")
        continue

    words = []
    n = len(data['text'])
    for i in range(n):
        word = str(data['text'][i]).strip()
        conf = int(data['conf'][i])
        if not word or conf < 0:
            continue
        x = data['left'][i]
        y = data['top'][i]
        w = data['width'][i]
        h = data['height'][i]
        words.append({
            "text": word,
            "bbox": [x, y, x + w, y + h],
        })

    sidecar = {
        "doc_id": doc_id,
        "page_number": page_num,
        "image_width": img.width,
        "image_height": img.height,
        "words": words,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(sidecar, f, ensure_ascii=False)

    done += 1
    if done % 50 == 0:
        print(f"progress: {done}/{len(needed)}")

print(f"\nDone. Total sidecars: {done}")
if failed:
    print(f"Failed after retries: {len(failed)}")
    for f in failed:
        print(f"  {f}")