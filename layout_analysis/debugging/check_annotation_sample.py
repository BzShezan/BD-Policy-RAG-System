from original_paths import project_path
import json
d = json.load(open(project_path('layout_analysis/data/annotation.json'), encoding="utf-8"))
task = d[0]
print("image:", task['data']['image'])
print()
result = task['annotations'][0]['result'][0]
print("one labeled region:")
print(json.dumps(result, indent=2, ensure_ascii=False))