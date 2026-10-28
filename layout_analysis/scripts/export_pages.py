from original_paths import project_path
import fitz
import os

PDF_FOLDER = project_path('data/raw_pdfs/social_welfare')
OUTPUT_FOLDER = project_path('layout_analysis/workspace/label_studio_images')

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

for pdf_name in os.listdir(PDF_FOLDER):
    if not pdf_name.endswith('.pdf'):
        continue
    pdf_path = os.path.join(PDF_FOLDER, pdf_name)
    doc = fitz.open(pdf_path)
    base = os.path.splitext(pdf_name)[0]
    for page_num in range(len(doc)):
        page = doc[page_num]
        mat = fitz.Matrix(150/72, 150/72)
        pix = page.get_pixmap(matrix=mat)
        out_path = os.path.join(OUTPUT_FOLDER, f"{base}_p{page_num+1:03d}.png")
        pix.save(out_path)
        print(f"Saved: {out_path}")
    doc.close()

print("Done.")