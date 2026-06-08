import os
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JSONL_DIR = os.path.join(SCRIPT_DIR, '..', 'data', 'processed_jsonl')

search_terms = ['ভাতা']

print(f"🔍 Searching for {search_terms} in Old Age JSONL files...\n")

found_any = False
for filename in os.listdir(JSONL_DIR):
    # Only search Old Age related files
    if "OldAge" in filename or "OAA" in filename:
        if filename.endswith(".jsonl") and "RAW" not in filename:
            filepath = os.path.join(JSONL_DIR, filename)
            print(f"📄 Scanning: {filename}")
            with open(filepath, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        data = json.loads(line)
                        text = data.get('text', '')
                        # Check if any search term is in text
                        if any(term in text for term in search_terms):
                            found_any = True
                            print(f"  ✅ Line {line_num} [ID: {data.get('clause_id', 'N/A')}]: {text[:200]}...")
                    except Exception as e:
                        pass
            print()

if not found_any:
    print("❌ CRITICAL: No chunks containing '৬৫' or 'বয়স' were found in the Old Age files!")
    print("   This means the OCR cleaner deleted the age limit chunk, or the PDF didn't extract it properly.")