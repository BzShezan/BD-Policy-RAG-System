from original_paths import project_path
import json
import os

LABELED_DIR = project_path('layout_analysis/workspace/labeled_pages')

for fname in os.listdir(LABELED_DIR):
    if not fname.endswith(".json"):
        continue
    path = os.path.join(LABELED_DIR, fname)
    try:
        with open(path, encoding="utf-8") as f:
            json.load(f)
    except json.JSONDecodeError as e:
        print(f"BROKEN: {fname}")
        print(f"  {e}")