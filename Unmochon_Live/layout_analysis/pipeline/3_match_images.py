from original_paths import project_path
"""Match annotated page_XXXXX.png files against the freshly re-exported,
properly-named images using exact SHA256 - rendering settings are
identical (DPI 150, same Matrix), so output should be byte-for-byte equal.
"""
import os
import json
import hashlib

ANNOTATED_FOLDER = project_path('layout_analysis/workspace/label_studio_images')
REEXPORT_FOLDER = project_path('layout_analysis/workspace/reexport_named')

def sha256_of(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

manifest = json.load(open(os.path.join(REEXPORT_FOLDER, "manifest.json"), encoding="utf-8"))
hash_to_real = {m["sha256"]: m for m in manifest}

matched = {}
unmatched = []

for fname in sorted(os.listdir(ANNOTATED_FOLDER)):
    if not fname.endswith(".png"):
        continue
    path = os.path.join(ANNOTATED_FOLDER, fname)
    h = sha256_of(path)

    if h in hash_to_real:
        info = hash_to_real[h]
        matched[fname] = {
            "doc_id": info["doc_id"],
            "page_number": info["page_number"],
        }
    else:
        unmatched.append(fname)

print(f"matched:   {len(matched)}")
print(f"unmatched: {len(unmatched)}")

with open("page_image_mapping.json", "w", encoding="utf-8") as f:
    json.dump(matched, f, ensure_ascii=False, indent=2)

if unmatched:
    print("\nFirst 15 unmatched:")
    for u in unmatched[:15]:
        print(f"  {u}")