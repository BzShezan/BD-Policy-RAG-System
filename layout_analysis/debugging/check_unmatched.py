from original_paths import project_path
import os
import json
import hashlib
from PIL import Image

ANNOTATED_FOLDER = project_path('layout_analysis/workspace/label_studio_images')

with open("page_image_mapping.json", encoding="utf-8") as f:
    matched = json.load(f)

all_imgs = sorted(f for f in os.listdir(ANNOTATED_FOLDER) if f.endswith(".png"))
unmatched = [f for f in all_imgs if f not in matched]

print(f"Unmatched: {len(unmatched)}")
for f in unmatched:
    path = os.path.join(ANNOTATED_FOLDER, f)
    img = Image.open(path)
    print(f"  {f}   size={img.size}")