from original_paths import project_path
import json
p = project_path('data/processed_jsonl/Social_Welfare_clauses.jsonl')
rows = [json.loads(l) for l in open(p, encoding='utf-8') if l.strip()]
c = rows[0]
doc_id = c['doc_id']
page_num = c['page_number']
print(f"doc_id: {repr(doc_id)}")
print(f"page_number: {page_num}")

expected_filename = f"{doc_id}_p{page_num:03d}.json"
print(f"expected filename: {repr(expected_filename)}")

import os
actual_files = os.listdir(project_path('layout_analysis/data/word_boxes'))
print(f"\ndoes it exist exactly? {expected_filename in actual_files}")

# show a few real filenames for comparison
print("\nsample real filenames:")
for f in actual_files[:5]:
    print(f"  {repr(f)}")