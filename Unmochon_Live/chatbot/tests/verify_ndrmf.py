from original_paths import project_path
import json

path = project_path('data/processed_jsonl/Disaster_Management_clauses.jsonl')
with open(path, encoding="utf-8") as f:
    clauses = [json.loads(l) for l in f if l.strip()]

doc_clauses = [c for c in clauses if c.get("doc_id") == "National Strategy for Disaster Risk Financing"]

print(f"total clauses in this doc: {len(doc_clauses)}")

for c in doc_clauses:
    text = c.get("text", "")
    if "NDRMF" in text or "25" in text and "million" in text.lower():
        print(f"\npage: {c.get('page_number')}")
        print(text[:400])