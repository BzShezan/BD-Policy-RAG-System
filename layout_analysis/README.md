# Layout Analysis Pipeline

Run these in numbered order. Each stage reads the previous stage's output.

## 1_export_pages.py
Renders every SW PDF page to a PNG image with a meaningful filename:
`{doc_id}_p{page_number}.png`
Also computes a SHA256 hash per image and writes a manifest.
**Input:**  PDFs in `data/raw_pdfs/social_welfare/`
**Output:** `G:\reexport_named\` (images + manifest.json)
**Status:** Done — 102 documents, 2,265 pages

## 2_count_labels.py
Counts how many times each Label Studio label appears across all
annotated pages. Used once to decide the final 12-label set.
**Input:**  Label Studio JSON export (`data/annotation.json`)
**Output:** printed counts only
**Status:** Done — 12 labels finalized, none merged

## 3_match_images.py
Matches the sequentially-renamed Label Studio images (page_00001.png
etc.) back to real doc_id + page_number, by comparing exact SHA256
hashes against the manifest from step 1.
**Input:**  `G:\label_studio_images\`, `G:\reexport_named\manifest.json`
**Output:** `page_image_mapping.json`
**Status:** Done — 2,265 / 2,292 matched (98.8%)

## 4_extract_word_boxes.py
Runs Tesseract OCR on every mapped page to get word-level text +
pixel bounding boxes. One sidecar JSON per page.
**Input:**  `page_image_mapping.json`, images in `G:\reexport_named\`
**Output:** `G:\word_boxes\` (one JSON per page)
**Status:** Done — 2,258 pages

## 5_assign_labels.py
For every word, checks which Label Studio region (converted from
percent to pixel coordinates) contains its center point, and assigns
that region's label. Words outside every region get "O".
**Input:**  `page_image_mapping.json`, `data/annotation.json`,
            `G:\word_boxes\`
**Output:** `G:\labeled_pages\` (one JSON per page, ready for training)
**Status:** Done and spot-checked — 1,154 pages, labels verified correct

## 6_split_dataset.py  (not yet written)
Splits labeled pages into train/validation, by document not by page,
stratified so rare labels appear in both sets.

## 7_train.py  (not yet written)
Fine-tunes nielsr/lilt-xlm-roberta-base on the training split.

## 8_evaluate.py  (not yet written)
Computes per-label F1 on the held-out validation split.