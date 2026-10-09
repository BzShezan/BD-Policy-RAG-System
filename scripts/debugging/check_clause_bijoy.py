from original_paths import project_path
import json, re

path = project_path('data/processed_jsonl/Social_Welfare_clauses.jsonl')
pre_base = 'িেৈোৌ'
total = bad = 0
samples = []

for line in open(path, encoding='utf-8'):
    if not line.strip():
        continue
    c = json.loads(line)
    t = c.get('text', '')
    total += 1
    if re.search(r'(^|\s)[' + pre_base + r']', t) or 'X' in t or '#' in t:
        bad += 1
        if len(samples) < 5:
            samples.append((c.get('clause_id', ''), t[:120]))

print(f"clauses: {total}")
print(f"suspect: {bad} ({bad/total*100:.1f}%)")
for cid, s in samples:
    print(f"\n{cid}\n  {s}")