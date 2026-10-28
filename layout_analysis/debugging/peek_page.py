from original_paths import project_path
import pytesseract
from PIL import Image

for n in [84, 90, 95, 100, 105, 110]:
    img = Image.open(rf"project_path('layout_analysis/workspace/label_studio_images/page_00'){n:03d}.png")
    text = pytesseract.image_to_string(img, lang='ben+eng')
    print(f"--- page_00{n} ---")
    print(text[:150])
    print()