from original_paths import project_path
import os
import json

files = os.listdir(project_path('layout_analysis/workspace/labeled_pages'))
first = files[0]
print(f"using file: {first}")

d = json.load(open(os.path.join(project_path('layout_analysis/workspace/labeled_pages'), first), encoding="utf-8"))
for w in d["words"][:20]:
    print(f"{w['label']:15s} {w['text']}")