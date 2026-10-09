from original_paths import project_path
import json
import fitz
import os

manifest = json.load(open(project_path('layout_analysis/workspace/reexport_named/manifest.json'), encoding="utf-8"))
doc_id_to_pdf = {}
for m in manifest:
    doc_id_to_pdf[m["doc_id"]] = m["doc_id"] + ".pdf"

p = project_path('data/processed_jsonl/Social_Welfare_clauses.jsonl')
r = [json.loads(l) for l in open(p, encoding='utf-8') if l.strip()]
tess = [x for x in r if x.get('ocr_method') == 'tesseract'][:5]

FOLDER = project_path('data/raw_pdfs/social_welfare')

for c in tess:
    doc_id = c['doc_id'].strip()
    page_num = c['page_number']

    # find matching manifest doc_id by fuzzy contains check
    match = None
    for m_doc_id in doc_id_to_pdf:
        if m_doc_id.strip() == doc_id or doc_id.startswith(m_doc_id.strip()) or m_doc_id.strip().startswith(doc_id):
            match = m_doc_id
            break

    print(f"clause doc_id: {doc_id[:50]}")
    print(f"  matched manifest doc_id: {match}")

    if match:
        pdf_path = os.path.join(FOLDER, match + ".pdf")
        if os.path.exists(pdf_path):
            doc = fitz.open(pdf_path)
            page = doc[page_num - 1]
            text = page.get_text()
            print(f"  digital text length: {len(text.strip())}")
            print(f"  sample: {text[:100]}")
        else:
            print(f"  file still not found at: {pdf_path}")
    print()