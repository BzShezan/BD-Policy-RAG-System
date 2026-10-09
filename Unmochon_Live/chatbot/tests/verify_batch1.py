from original_paths import project_path
import fitz
import os

def check_page(doc_search_term, folder, file_position, label):
    matches = [f for f in os.listdir(folder) if doc_search_term in f]
    if not matches:
        print(f"[{label}] FILE NOT FOUND for search term: {doc_search_term}")
        return
    path = os.path.join(folder, matches[0])
    doc = fitz.open(path)
    print(f"[{label}] file: {matches[0]}")
    print(f"[{label}] total pages: {len(doc)}")
    if file_position <= len(doc):
        text = doc[file_position - 1].get_text()
        print(f"[{label}] content at file position {file_position}:")
        print(text[:500])
    print()

folder = project_path('data/raw_pdfs/social_welfare')

# widow amount
check_page("SW_old_widow_2024_11_Circular", folder, 58, "widow_amount")

# disability eligibility
check_page("SW_DA_2013_00_Policy_v1", folder, 26, "disability_eligibility")