from original_paths import project_path
"""Assign layout labels to words.

For every annotated page:
  1. load its word boxes (pixel coordinates, from OCR)
  2. load its Label Studio regions (percentage coordinates)
  3. convert regions to pixels using that page's own dimensions
  4. give each word the label of whichever region contains its center
  5. words outside every region get 'O' (nothing)
"""

import json
import os

MAPPING_PATH = project_path('layout_analysis/data/page_image_mapping.json')
ANNOTATION_PATH = project_path('layout_analysis/data/annotation.json')
WORD_BOX_DIR = project_path('layout_analysis/workspace/word_boxes')
OUTPUT_DIR = project_path('layout_analysis/workspace/labeled_pages')

os.makedirs(OUTPUT_DIR, exist_ok=True)


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def region_to_pixels(region, img_w, img_h):
    """Convert one Label Studio region from percent to pixel coordinates."""
    v = region["value"]
    x1 = v["x"] / 100 * img_w
    y1 = v["y"] / 100 * img_h
    x2 = (v["x"] + v["width"]) / 100 * img_w
    y2 = (v["y"] + v["height"]) / 100 * img_h
    label = v["rectanglelabels"][0] if v.get("rectanglelabels") else "O"
    return (x1, y1, x2, y2, label)


def word_center(bbox):
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def find_label(center, regions_px):
    """Which region, if any, contains this word's center point.
    If more than one matches, the smallest region wins - that handles
    a small box nested inside a bigger one, like a caption inside a
    table region."""
    cx, cy = center
    best = None
    best_area = None
    for x1, y1, x2, y2, label in regions_px:
        if x1 <= cx <= x2 and y1 <= cy <= y2:
            area = (x2 - x1) * (y2 - y1)
            if best_area is None or area < best_area:
                best = label
                best_area = area
    return best or "O"


def main():
    mapping = load_json(MAPPING_PATH)           # page_XXXXX.png -> {doc_id, page_number}
    annotation_data = load_json(ANNOTATION_PATH)  # list of Label Studio tasks

    # index annotation tasks by their image filename, e.g. page_00001.png
    tasks_by_image = {}
    for task in annotation_data:
        img_path = task["data"]["image"]
        img_name = os.path.basename(img_path)
        # Label Studio prefixes with an upload hash: c44841e4-page_00001.png
        # strip that off so it matches the mapping file's keys
        if "-" in img_name and img_name.split("-", 1)[1].startswith("page_"):
            img_name = img_name.split("-", 1)[1]
        tasks_by_image[img_name] = task

    print(f"annotation tasks: {len(tasks_by_image)}")
    print(f"page mapping entries: {len(mapping)}")

    done = 0
    skipped_no_annotation = 0
    skipped_no_wordbox = 0

    for img_name, info in mapping.items():
        doc_id = info["doc_id"]
        page_num = info["page_number"]

        task = tasks_by_image.get(img_name)
        if not task:
            skipped_no_annotation += 1
            continue

        wb_path = os.path.join(WORD_BOX_DIR, f"{doc_id}_p{page_num:03d}.json")
        if not os.path.exists(wb_path):
            skipped_no_wordbox += 1
            continue

        wb_data = load_json(wb_path)
        img_w = wb_data["image_width"]
        img_h = wb_data["image_height"]

        # gather all labeled regions on this page from every annotation result
        regions_px = []
        for ann in task.get("annotations", []):
            for r in ann.get("result", []):
                if r.get("type") == "rectanglelabels":
                    regions_px.append(region_to_pixels(r, img_w, img_h))

        labeled_words = []
        for w in wb_data["words"]:
            center = word_center(w["bbox"])
            label = find_label(center, regions_px)
            labeled_words.append({
                "text": w["text"],
                "bbox": w["bbox"],
                "label": label,
            })

        out_path = os.path.join(OUTPUT_DIR, f"{doc_id}_p{page_num:03d}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({
                "doc_id": doc_id,
                "page_number": page_num,
                "image_width": img_w,
                "image_height": img_h,
                "words": labeled_words,
            }, f, ensure_ascii=False)

        done += 1
        if done % 100 == 0:
            print(f"  progress: {done}")

    print(f"\nDone. Labeled pages written: {done}")
    print(f"skipped (no annotation found): {skipped_no_annotation}")
    print(f"skipped (no word box found):   {skipped_no_wordbox}")


if __name__ == "__main__":
    main()