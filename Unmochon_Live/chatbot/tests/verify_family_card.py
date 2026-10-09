from original_paths import project_path
import fitz

path = project_path('data/raw_pdfs/social_welfare/SocialMin_OldAgeAll_2013_00_Policy_v1.pdf.pdf')
doc = fitz.open(path)

for i in [3, 4, 5]:  # file positions 4, 5, 6
    text = doc[i].get_text()
    print(f"=== file position {i+1} ===")
    print(text[:400])
    print()