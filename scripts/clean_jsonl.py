import json
import os
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = os.path.join(SCRIPT_DIR, '..', 'data', 'processed_jsonl', 'Social_Welfare_clauses.jsonl')
OUTPUT_FILE = os.path.join(SCRIPT_DIR, '..', 'data', 'processed_jsonl', 'Social_Welfare_clauses_CLEAN.jsonl')

def is_clean_text(text):
    # Rule 1: Skip if it contains known severe OCR garbage strings
    garbage_patterns = ['ae a', 'aথর্', '£', 'ɛ', 'Geet', 'Bat হাজার', 'aye']
    for pattern in garbage_patterns:
        if pattern.lower() in text.lower():
            return False
            
    # Rule 2: Skip if the text is too short (likely just a header or page number)
    if len(text.strip()) < 40:
        return False
        
    # Rule 3: Skip if there are too many non-Bengali, non-numeric characters 
    # (A simple heuristic: if it has more than 40% English alphabet characters in a Bangla doc, it's likely bad OCR)
    english_chars = len(re.findall(r'[a-zA-Z]', text))
    total_chars = len(text)
    if total_chars > 0 and (english_chars / total_chars) > 0.4:
        return False

    return True

def clean_data():
    print("🧹 Cleaning the JSONL file...")
    
    if not os.path.exists(INPUT_FILE):
        print(f"❌ File not found: {INPUT_FILE}")
        return

    clean_clauses = []
    dirty_count = 0
    
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            clause = json.loads(line)
            if is_clean_text(clause['text']):
                clean_clauses.append(clause)
            else:
                dirty_count += 1

    # Save the clean data
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for clause in clean_clauses:
            f.write(json.dumps(clause, ensure_ascii=False) + '\n')
            
    print(f"✅ Cleaned! Kept {len(clean_clauses)} clauses. Removed {dirty_count} garbage clauses.")
    print(f"💾 Saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    clean_data()