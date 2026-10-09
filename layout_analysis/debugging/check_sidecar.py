from original_paths import project_path
import json
d = json.load(open(project_path('layout_analysis/workspace/word_boxes/SW_OAA_2014_02_Gazette_v1_p001.json'), encoding="utf-8"))
print(f"image size: {d['image_width']} x {d['image_height']}")
print(f"word count: {len(d['words'])}")
print(d['words'][:5])