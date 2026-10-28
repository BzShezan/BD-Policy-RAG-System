from original_paths import project_path
"""Export the 5 documents that failed in the main reexport run.
Their Bengali filenames were renamed to plain ASCII first because
cmd/PyMuPDF path resolution couldn't reliably open the originals.

Appends to the existing manifest.json rather than overwriting it.
"""

import fitz
import os
import hashlib
import json

FOLDER = project_path('data/raw_pdfs/social_welfare')
OUTPUT_FOLDER = project_path('layout_analysis/workspace/reexport_named')

renamed_files = [
    "SW_ANOGROSHOR_shiksha_upobritti_23-24.pdf",
    "SW_ANOGROSHOR_prshikkhon_24-25.pdf",
    "SW_ANOGROSHOR_bishesh_bhata_23-24.pdf",
    "SW_ANOGROSHOR_bishesh_bhata_24-25.pdf",
    "SW_ANOGROSHOR_shiksha_upobritti_24-25.pdf",
]

manifest_path = os.path.join(OUTPUT_FOLDER, "manifest.json")
manifest = json.load(open(manifest_path, encoding="utf-8"))

still_failed = []

for pdf_name in renamed_files:
    pdf_path = os.path.join(FOLDER, pdf_name)

    if not os.path.exists(pdf_path):
        print(f"NOT FOUND: {pdf_name}")
        still_failed.append(pdf_name)
        continue

    doc = fitz.open(pdf_path)
    base = os.path.splitext(pdf_name)[0]

    for page_num in range(len(doc)):
        page = doc[page_num]
        mat = fitz.Matrix(150 / 72, 150 / 72)
        pix = page.get_pixmap(matrix=mat)

        out_name = f"{base}_p{page_num+1:03d}.png"
        out_path = os.path.join(OUTPUT_FOLDER, out_name)
        pix.save(out_path)

        with open(out_path, "rb") as f:
            sha = hashlib.sha256(f.read()).hexdigest()

        manifest.append({
            "filename": out_name,
            "doc_id": base,
            "page_number": page_num + 1,
            "sha256": sha,
        })

    print(f"done: {base}  ({len(doc)} pages)")
    doc.close()

with open(manifest_path, "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)

print(f"\nTotal pages now in manifest: {len(manifest)}")
if still_failed:
    print(f"Still not found: {still_failed}")
else:
    print("All 5 documents recovered successfully.")