from original_paths import project_path
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from layout_analysis.scripts.layout_pipeline.converter import get_image_filename, load_tasks

EXPORT_FILE = project_path('layout_analysis/data/annotations.json')
IMAGES_DIR  = project_path('layout_analysis/data/annotation_images')

tasks = load_tasks(EXPORT_FILE)
print(f"Total tasks: {len(tasks)}")

t = tasks[0]
print("Raw image field  :", t["data"]["image"])

filename = get_image_filename(t)
print("Extracted filename:", filename)

img_path = os.path.join(IMAGES_DIR, filename)
print("Looking for      :", img_path)
print("Exists?          :", os.path.exists(img_path))

print()
print("First 5 files in IMAGES_DIR:")
for f in os.listdir(IMAGES_DIR)[:5]:
    print(" ", f)

print()
usable = 0
skipped = 0
for task in tasks:
    fn  = get_image_filename(task)
    ip  = os.path.join(IMAGES_DIR, fn)
    anns = task.get("annotations", [])
    has_results = anns and len(anns[0].get("result", [])) > 0
    if os.path.exists(ip) and has_results:
        usable += 1
    else:
        skipped += 1

print(f"Usable pages : {usable}")
print(f"Skipped      : {skipped}")