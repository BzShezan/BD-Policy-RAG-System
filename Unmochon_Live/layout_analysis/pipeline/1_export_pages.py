from original_paths import project_path
import fitz
import os
import hashlib
import json
import unicodedata

PDF_FOLDER = project_path('data/raw_pdfs/social_welfare')
OUTPUT_FOLDER = project_path('layout_analysis/workspace/reexport_named')

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

manifest = []
failed = []

for pdf_name in sorted(os.listdir(PDF_FOLDER)):
    if not pdf_name.endswith('.pdf'):
        continue

    pdf_path = os.path.join(PDF_FOLDER, pdf_name)
    pdf_path = unicodedata.normalize('NFC', pdf_path)

    doc = None
    try:
        doc = fitz.open(pdf_path)
    except Exception:
        try:
            long_path = "\\\\?\\" + os.path.abspath(pdf_path)
            doc = fitz.open(long_path)
        except Exception as e:
            print(f"SKIPPED (could not open): {pdf_name}  [{e}]")
            failed.append(pdf_name)
            continue

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

    print(f"done: {base}")
    doc.close()

with open(os.path.join(OUTPUT_FOLDER, "manifest.json"), "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)

with open(os.path.join(OUTPUT_FOLDER, "failed.json"), "w", encoding="utf-8") as f:
    json.dump(failed, f, ensure_ascii=False, indent=2)

print(f"\nTotal pages: {len(manifest)}")
print(f"Failed documents: {len(failed)}")
print("Manifest written to manifest.json, failures to failed.json")