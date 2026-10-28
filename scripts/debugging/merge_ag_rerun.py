from original_paths import project_path
"""Merge AG re-OCR results back into the main corpus.
Same approach as the SW merge - backs up first, replaces only the
clauses whose doc_id matches what was re-run, leaves everything else."""

import json
import shutil
from datetime import datetime

MAIN  = project_path('data/processed_jsonl/Agriculture_clauses.jsonl')
RERUN = project_path('data/processed_jsonl/AGRerun2_clauses.jsonl')

stamp = datetime.now().strftime("%Y%m%d_%H%M")
shutil.copy(MAIN, MAIN + f".before_merge_{stamp}")
print(f"Backed up to: {MAIN}.before_merge_{stamp}")


def load(path):
    return [json.loads(l) for l in open(path, encoding='utf-8') if l.strip()]


main_rows  = load(MAIN)
fresh_rows = load(RERUN)

fresh_docs = {r.get('doc_id', '') for r in fresh_rows}
print(f"\nDocuments re-run: {len(fresh_docs)}")
for d in sorted(fresh_docs):
    print(f"  {d}")

kept = [r for r in main_rows if r.get('doc_id', '') not in fresh_docs]
removed = len(main_rows) - len(kept)

merged = kept + fresh_rows

print(f"\nold clauses removed: {removed}")
print(f"new clauses added:   {len(fresh_rows)}")
print(f"total before:        {len(main_rows)}")
print(f"total after:         {len(merged)}")

with open(MAIN, 'w', encoding='utf-8') as f:
    for r in merged:
        f.write(json.dumps(r, ensure_ascii=False) + '\n')

print(f"\nWritten to: {MAIN}")