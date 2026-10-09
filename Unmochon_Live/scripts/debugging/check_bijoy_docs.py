from original_paths import project_path
import json, re
from collections import Counter

path = project_path('data/processed_jsonl/Agriculture_clauses.jsonl')
pre_base = 'িেৈোৌ'
per_doc = Counter()
doc_total = Counter()

for line in open(path, encoding='utf-8'):
    if not line.strip():
        continue
    c = json.loads(line)
    t = c.get('text', '')
    d = c.get('doc_id', '')
    doc_total[d] += 1
    if re.search(r'(^|\s)[' + pre_base + r']', t) or 'X' in t or '#' in t:
        per_doc[d] += 1

print(f"Documents with corruption: {len(per_doc)} / {len(doc_total)}\n")
for d, n in per_doc.most_common(30):
    pct = n / doc_total[d] * 100
    print(f"{n:4d}/{doc_total[d]:<4d} ({pct:5.1f}%)  {d[:70]}")