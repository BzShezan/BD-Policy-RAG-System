from original_paths import project_path
import shutil
import os

FOLDER = project_path('data/raw_pdfs/Agriculture')
DEST = project_path('layout_analysis/workspace/ag_rerun_batch2')
os.makedirs(DEST, exist_ok=True)

files = [
    "জাতীয় কৃষি যান্ত্রিকীকরণ নীতি ২০২০.pdf",
    "অভিযোগ প্রতিকার ব্যবস্থা সংক্রান্ত কর্মপরিকল্পনা, ২০২৩-২৪.pdf",
    "জাতীয় শুদ্ধাচার কৌশল কর্মপরিকল্পনা- ২০২৩-২৪.pdf",
    "আগাম ও স্বল্পমেয়াদী ফসলের জাত ও প্রযুক্তি উদ্ভাবন বিষয়ক নীতিমালা.pdf",
    "বাংলাদেশ কৃষি উন্নয়ন কর্পোরেশন আইন, ২০১৮.pdf",
]

for f in files:
    src = os.path.join(FOLDER, f)
    if not os.path.exists(src):
        print(f"NOT FOUND: {f}")
        continue
    dst = os.path.join(DEST, f)
    shutil.copy2(src, dst)
    print(f"copied: {f}")

print("\nDone.")