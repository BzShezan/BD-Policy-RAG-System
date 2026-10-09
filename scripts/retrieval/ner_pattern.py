from original_paths import project_path
import fitz
import re

def get_printed_page_number(page):
    """Try to find the page number actually printed on this page,
    usually a standalone number at the very top or bottom."""
    text = page.get_text()
    lines = [l.strip() for l in text.split('\n') if l.strip()]

    if not lines:
        return None

    # Check the first line - printed numbers often appear at the very top
    first = lines[0]
    if re.fullmatch(r'\d{1,3}', first):
        return int(first)

    # Check the last line - sometimes printed at the bottom instead
    last = lines[-1]
    if re.fullmatch(r'\d{1,3}', last):
        return int(last)

    return None


# test on the Bede/Dalit/Harijan document
import os
folder = project_path('data/raw_pdfs/social_welfare')
target = [f for f in os.listdir(folder) if "Bede" in f and "Dalit" in f][0]
doc = fitz.open(os.path.join(folder, target))

for i in range(min(15, len(doc))):
    printed = get_printed_page_number(doc[i])
    print(f"file position {i+1}: printed number = {printed}")