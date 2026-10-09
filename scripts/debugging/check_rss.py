from original_paths import project_path
import json
from collections import Counter

path = project_path('data/processed_jsonl/Rerun_clauses.jsonl')
rows = [json.loads(l) for l in open(path, encoding='utf-8') if l.strip()]

print(f"clauses: {len(rows)}")
print(f"doc_ids: {set(r.get('doc_id','') for r in rows)}")

print("\nextraction method:")
for m, n in Counter(r.get('ocr_method','') for r in rows).most_common():
    print(f"  {m}: {n}")

print("\nfirst 3 clauses:")
for r in rows[:3]:
    print(f"\n[{r.get('ocr_method')}] q={r.get('quality_score')}")
    print(f"  {r.get('text','')[:250]}")