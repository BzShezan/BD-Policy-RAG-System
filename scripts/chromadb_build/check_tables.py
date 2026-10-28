from original_paths import project_path
import json

path = project_path('data/processed_jsonl/Agriculture_tables.jsonl')
with open(path, encoding="utf-8") as f:
    rows = [json.loads(l) for l in f if l.strip()]

print(f"Total rows: {len(rows)}")
print(f"Keys present: {list(rows[0].keys())}\n")

for r in rows[:3]:
    print(f"quality_score: {r.get('quality_score', 'MISSING')}")
    print(f"text length:   {len(r.get('text', ''))}")
    print(f"text: {str(r.get('text', ''))[:200]}\n")