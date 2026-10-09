from original_paths import project_path
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from layout_analysis.scripts.layout_pipeline.converter import build_examples
from layout_analysis.scripts.layout_pipeline.model_trainer import train

EXPORT_FILE = project_path('layout_analysis/data/annotations.json')
IMAGES_DIR  = project_path('layout_analysis/data/annotation_images')
MODEL_DIR = os.getenv("LAYOUT_MODEL_DIR", project_path('layout_analysis/models/lilt_sw'))
EPOCHS      = 8


def main():
    print("Building training examples (running Tesseract on annotation images)...")
    examples = build_examples(EXPORT_FILE, IMAGES_DIR)

    if len(examples) < 30:
        print("Too few examples, aborting.")
        return

    os.makedirs(os.path.dirname(MODEL_DIR), exist_ok=True)
    print(f"\nTraining LiLT on {len(examples)} pages, {EPOCHS} epochs max...")
    train(examples, MODEL_DIR, epochs=EPOCHS)


if __name__ == "__main__":
    main()