from original_paths import project_path
import json
path = project_path('data/processed_jsonl/Trial_tables.jsonl')
rows = [json.loads(l) for l in open(path, encoding='utf-8') if l.strip()]
print(f"rows: {len(rows)}")
print(f"distinct tables: {len(set((r['doc_id'], r['page_number'], r['table_index']) for r in rows))}")
print(f"flagged broken: {sum(1 for r in rows if r.get('broken_text'))}")
print()
for r in rows[:5]:
    print(f"[q={r.get('quality_score')}] broken={r.get('broken_text')}")
    print(f"  {r.get('raw_text','')[:150]}\n")