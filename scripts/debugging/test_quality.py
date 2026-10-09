from original_paths import project_path
import json, sys
sys.path.insert(0, project_path('scripts'))
from scripts.ocr_pipeline.quality import quality_score, bengali_ratio

path = project_path('data/processed_jsonl/Social_Welfare_clauses.jsonl')

pass_new = pass_old = 0
total = 0
flipped = []

for line in open(path, encoding='utf-8'):
    if not line.strip():
        continue
    c = json.loads(line)
    t = c.get('text', '')
    total += 1
    old = bengali_ratio(t)
    new = quality_score(t)
    if old >= 0.6: pass_old += 1
    if new >= 0.6: pass_new += 1
    if old >= 0.6 and new < 0.6 and len(flipped) < 5:
        flipped.append((round(old,2), round(new,2), t[:90]))

print(f"total clauses:        {total}")
print(f"passed old gate (0.6): {pass_old}")
print(f"passed new gate (0.6): {pass_new}")
print("\nNow rejected (were wrongly trusted before):")
for o, n, s in flipped:
    print(f"\n  old={o} new={n}")
    print(f"  {s}")