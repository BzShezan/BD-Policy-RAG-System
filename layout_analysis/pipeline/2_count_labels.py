from original_paths import project_path
import json
from collections import Counter

path = project_path('layout_analysis/data/annotation_images/annotation.json')   # <-- change to your actual file

data = json.load(open(path, encoding="utf-8"))

labels = Counter()
pages = 0

for task in data:
    anns = task.get("annotations", [])
    if not anns:
        continue
    found = False
    for ann in anns:
        for r in ann.get("result", []):
            for v in r.get("value", {}).get("rectanglelabels", []):
                labels[v.strip()] += 1
                found = True
    if found:
        pages += 1

print(f"annotated pages: {pages}")
print(f"total regions:   {sum(labels.values())}\n")
for lbl, n in labels.most_common():
    flag = "   <-- too few" if n < 30 else ""
    print(f"  {n:5d}  {repr(lbl)}{flag}")