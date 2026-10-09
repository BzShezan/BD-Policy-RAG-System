from original_paths import project_path
import json
p = project_path('data/processed_jsonl/Social_Welfare_clauses.jsonl')
rows = [json.loads(l) for l in open(p, encoding='utf-8') if l.strip()]
meta = [r for r in rows if r.get('layout_label') == 'METADATA']
for r in meta[:5]:
    print(r['text'][:150])
    print('---')