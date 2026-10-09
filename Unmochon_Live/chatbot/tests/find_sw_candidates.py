from original_paths import project_path
import json

path = project_path('data/processed_jsonl/Social_Welfare_clauses.jsonl')
with open(path, encoding="utf-8") as f:
    clauses = [json.loads(l) for l in f if l.strip()]

matches = [c for c in clauses if c.get("doc_id") == "SocialMin_OldAgeAll_2013_00_Policy_v1.pdf"
           and "বয়স" in c.get("text","") and "৬" in c.get("text","")]

for c in matches[:8]:
    print(f"clause_id: {c['clause_id']}")
    print(f"page: {c['page_number']}")
    print(c['text'][:200])
    print()