from original_paths import project_path
import os
import json

RAW_PDF_DIR = project_path('data/raw_pdfs/social_welfare')
LABELED_DIR = project_path('layout_analysis/workspace/labeled_pages')

all_docs = set()
for f in os.listdir(RAW_PDF_DIR):
    if f.endswith(".pdf"):
        all_docs.add(os.path.splitext(f)[0])

labeled_docs = set()
for f in os.listdir(LABELED_DIR):
    if f.endswith(".json"):
        with open(os.path.join(LABELED_DIR, f), encoding="utf-8") as fh:
            d = json.load(fh)
        labeled_docs.add(d["doc_id"])

missing = all_docs - labeled_docs
print(f"total raw PDFs: {len(all_docs)}")
print(f"documents with labeled pages: {len(labeled_docs)}")
print(f"missing entirely: {len(missing)}\n")
for m in sorted(missing):
    print(f"  {m}")