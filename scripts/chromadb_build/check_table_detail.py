from original_paths import project_path
import json

path = project_path('data/processed_jsonl/Agriculture_tables.jsonl')
with open(path, encoding="utf-8") as f:
    rows = [json.loads(l) for l in f if l.strip()]

# First 5 rows in full
for r in rows[:5]:
    print(json.dumps(r, ensure_ascii=False, indent=2))
    print("-" * 60)

# How many distinct tables are there really?
keys = {(r["doc_id"], r["page_number"], r["table_index"]) for r in rows}
print(f"\nTotal rows:            {len(rows)}")
print(f"Distinct tables:       {len(keys)}")
print(f"Rows marked as header: {sum(1 for r in rows if r.get('is_header'))}")