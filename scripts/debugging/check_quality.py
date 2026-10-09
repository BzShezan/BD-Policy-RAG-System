from original_paths import project_path
import json
import random

path = project_path('data/processed_jsonl/Social_Welfare_clauses.jsonl')
clauses = [json.loads(l) for l in open(path, encoding='utf-8') if l.strip()]

print(f'Total clauses: {len(clauses)}')

q_scores = [c['quality_score'] for c in clauses]
print(f'Avg quality  : {sum(q_scores)/len(q_scores):.3f}')
print(f'q >= 0.7     : {sum(1 for q in q_scores if q >= 0.7)}')
print(f'q 0.5-0.7    : {sum(1 for q in q_scores if 0.5 <= q < 0.7)}')
print(f'q < 0.5      : {sum(1 for q in q_scores if q < 0.5)}')

methods = {}
for c in clauses:
    m = c['ocr_method']
    methods[m] = methods.get(m, 0) + 1
print(f'OCR methods  : {methods}')

bbox = sum(1 for c in clauses if c.get('bbox'))
print(f'bbox found   : {bbox}/{len(clauses)} ({100*bbox//len(clauses)}%)')

print()
print('=== 3 RANDOM SAMPLE CLAUSES ===')
for c in random.sample(clauses, min(3, len(clauses))):
    print(f'quality={c["quality_score"]} method={c["ocr_method"]}')
    print(c['text'][:150])
    print()
