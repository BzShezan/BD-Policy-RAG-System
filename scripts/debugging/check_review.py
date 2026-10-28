from original_paths import project_path
import json

path = project_path('data/processed_jsonl/Disaster_Management_clauses_review.jsonl')
with open(path, encoding="utf-8") as f:
    clauses = [json.loads(l) for l in f if l.strip()]

scores = [c['quality_score'] for c in clauses]
print(f"Total: {len(clauses)}")
print(f"Min: {min(scores):.3f}")
print(f"Max: {max(scores):.3f}")
print(f"Avg: {sum(scores)/len(scores):.3f}")

for c in clauses[:3]:
    print(f"\nScore: {c['quality_score']:.3f}")
    print(f"Text: {c['text'][:200]}")