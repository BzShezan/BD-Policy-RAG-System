from original_paths import project_path
import os

INPUT_FOLDER = project_path('layout_analysis/workspace/label_studio_images')
counter = 1

for filename in os.listdir(INPUT_FOLDER):
    if filename.endswith('.png'):
        old_path = os.path.join(INPUT_FOLDER, filename)
        new_name = f"page_{counter:05d}.png"
        new_path = os.path.join(INPUT_FOLDER, new_name)
        os.rename(old_path, new_path)
        counter += 1
        print(f"Renamed: {filename[:40]}... -> {new_name}")

print(f"Done. Total: {counter-1} files renamed.")