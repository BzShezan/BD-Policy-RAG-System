from original_paths import project_path
import json
import os
import fitz

# First, confirm what page_number the $25 million clause claims
path = project_path('data/processed_jsonl/Disaster_Management_clauses.jsonl')
with open(path, encoding="utf-8") as f:
    clauses = [json.loads(l) for l in f if l.strip()]

doc_clauses = [c for c in clauses if c.get("doc_id") == "National Strategy for Disaster Risk Financing"]

target = [c for c in doc_clauses if "25 million" in c.get("text", "")]
for c in target:
    print(f"clause_id: {c.get('clause_id')}")
    print(f"page_number: {c.get('page_number')}")
    print(f"printed_page_number: {c.get('printed_page_number', 'not detected')}")
    print(f"text: {c.get('text','')[:400]}")
    print()

# Now open the real PDF at that exact file position to visually confirm
if target:
    file_pos = target[0].get("page_number")
    pdf_path = project_path('data/raw_pdfs/Disaster Management/National Strategy for Disaster Risk Financing.pdf')
    doc = fitz.open(pdf_path)
    real_page = doc[file_pos - 1]
    print(f"\n=== Real PDF content at file position {file_pos} ===")
    print(real_page.get_text()[:600])