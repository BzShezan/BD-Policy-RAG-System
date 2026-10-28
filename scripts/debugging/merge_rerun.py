from original_paths import project_path
"""Replace corrupted clauses with freshly re-OCR'd ones.

Only clauses whose doc_id appears in the rerun output get replaced.
Everything else in the main file is left untouched.
"""
import json
import shutil
from datetime import datetime

MAIN   = project_path('data/processed_jsonl/Social_Welfare_clauses.jsonl')
RERUN  = project_path('data/processed_jsonl/Rerun_clauses.jsonl')

# Safety copy before touching anything
stamp = datetime.now().strftime("%Y%m%d_%H%M")
shutil.copy(MAIN, MAIN + f".before_merge_{stamp}")
print(f"Backed up to: {MAIN}.before_merge_{stamp}")


def load(path):
    return [json.loads(l) for l in open(path, encoding='utf-8') if l.strip()]


main_rows  = load(MAIN)
fresh_rows = load(RERUN)

# Which documents were re-run
fresh_docs = {r.get('doc_id', '') for r in fresh_rows}
print(f"\nDocuments re-run: {len(fresh_docs)}")
for d in sorted(fresh_docs):
    print(f"  {d}")

# Drop the old versions of those documents
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