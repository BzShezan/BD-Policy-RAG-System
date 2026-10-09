from original_paths import project_path
import json

path = project_path('data/processed_jsonl/Disaster_Management_clauses.jsonl')
with open(path, encoding="utf-8") as f:
    clauses = [json.loads(l) for l in f if l.strip()]

print(f"total clauses: {len(clauses)}")

# DM is mostly allocation orders - look for amount/quantity patterns
keywords = ["বরাদ্দ", "টন", "মেট্রিক টন", "কেজি", "টাকা"]
matches = [c for c in clauses if any(k in c.get("text", "") for k in keywords)]

print(f"found with allocation keywords: {len(matches)}")
for c in matches[:5]:
    print(f"\n[{c['doc_id'][:50]}] page {c['page_number']}")
    print(c['text'][:250])