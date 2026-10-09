from original_paths import project_path
"""Check which of the 16 demo documents are digital vs scanned."""

import fitz
from pathlib import Path

PDF_DIR = Path(project_path('data/raw_pdfs'))

DEMO_DOCS = [
    "SocialMin_OldAgeAll_2013_00_Policy_v1.pdf",
    "SW_DEPR_Bede, Dalit, AND Harijan_2013_00_Policy_v3",
    "SW_Tea Workers_2013_00_Policy_v1",
    "SW_Tea Workers_2013_00_Policy_webpage",
    "SociaMin_Widow_2025_09_25_Gazette_v1",
    "SociaMin_Widow_2025_09_25_webpage_v1",
    "013-057",
    "খসড়া সার (ব্যবস্থাপনা) বিধিমালা ২০২৩",
    "সার (ব্যবস্থাপনা) (সংশোধন) বিধিমালা- ২০২১ (খসড়া)",
    "সার ডিলার নিয়োগ ও সার বিতরণ সংক্রান্ত সমন্বিত নীতিমালা-২০২৫",
    "বীজ বিধিমালা-২০২০",
    "বীজ ডিলার নিবন্ধন ও নবায়ন",
    "SW_PM_2017_00_Policy_v1",
    "DM_Baby_Food_Allocation of funds for purchase and distribution of baby food",
    "দুর্যোগ ব্যবস্থাপনা স্থায়ী আদেশাবলী-২০১৯",
]

for demo_id in DEMO_DOCS:
    matches = list(PDF_DIR.rglob(f"*{demo_id[:50]}*"))
    if not matches:
        print(f"NOT FOUND      {demo_id[:60]}")
        continue

    for pdf_path in matches[:1]:
        try:
            pdf = fitz.open(pdf_path)
            total_chars = sum(len(pdf[i].get_text()) for i in range(min(5, len(pdf))))
            avg = total_chars / min(5, len(pdf))
            pdf.close()
            tag = "DIGITAL" if avg > 200 else "SCANNED"
            print(f"{tag:<8}       {demo_id[:60]}")
        except Exception as e:
            print(f"ERROR ({e})   {demo_id[:60]}")