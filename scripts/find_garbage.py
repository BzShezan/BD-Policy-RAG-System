import json
import os
import re
from collections import defaultdict

INPUT_DIR = os.path.join('..', 'data', 'processed_jsonl')
OUTPUT_FILE = os.path.join('..', 'data', 'garbage_blacklist.jsonl')

# Words we KNOW are good (do not delete these)
KNOWN_WHITELIST = {
    'UP', 'GB', 'ID', 'NGO', 'UN', 'US', 'UK', 'EC', 'PO', 'NO',
    'GOVT', 'DEPT', 'MIN', 'DIV', 'SEC', 'INST', 'AMT', 'NOS',
    'VAT', 'IT', 'BDT', 'TIN', 'BIN', 'FY', 'BANK', 'LOAN', 'FUND',
    'NID', 'DOB', 'PDF', 'DOC', 'GPS', 'SIM', 'CEO', 'DA', 'TA',
    'KG', 'GM', 'ML', 'LT', 'KM', 'MM', 'CM', 'MB', 'TB', 'KB',
    'No', 'age', 'old', 'new', 'per', 'year', 'male', 'female', 'date', 'name'
}

word_stats = defaultdict(lambda: {'count': 0, 'examples': []})

print("🔍 Scanning all JSONL files for mixed English/Bengali words...\n")

for filename in sorted(os.listdir(INPUT_DIR)):
    if filename.endswith(".jsonl") and not filename.endswith("_CLEAN.jsonl") and "RAW" not in filename:
        filepath = os.path.join(INPUT_DIR, filename)
        
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    text = data.get('text', '')
                    
                    # Only check lines that contain Bengali characters
                    if re.search(r'[\u0980-\u09FF]', text):
                        # Find ALL 1 to 5 letter English words
                        words = re.findall(r'\b([a-zA-Z]{1,5})\b', text)
                        for word in words:
                            word_stats[word]['count'] += 1
                            if len(word_stats[word]['examples']) < 2:
                                # Save a short snippet of context
                                snippet = text[:120].replace('\n', ' ').strip()
                                word_stats[word]['examples'].append(snippet)
                except:
                    pass

# Sort by frequency (most common first)
sorted_words = sorted(word_stats.items(), key=lambda x: x[1]['count'], reverse=True)

suspicious_upper = []
suspicious_lower = []
confirmed_good = []

for word, stats in sorted_words:
    if word in KNOWN_WHITELIST:
        confirmed_good.append((word, stats['count']))
    elif word.isupper():
        suspicious_upper.append((word, stats['count'], stats['examples']))
    else:
        suspicious_lower.append((word, stats['count'], stats['examples']))

# --- CONSOLE OUTPUT ---
print(f"✅ Found {len(confirmed_good)} known good words (Whitelist).")
print(f"🔴 Found {len(suspicious_upper)} suspicious UPPERCASE words (Likely OCR Garbage).")
print(f"🟡 Found {len(suspicious_lower)} suspicious LOWERCASE words (Check carefully).")

# --- SAVE TO JSONL ---
print(f"\n💾 Saving garbage words to {OUTPUT_FILE}...")
saved_count = 0
with open(OUTPUT_FILE, 'w', encoding='utf-8') as outfile:
    # Save Uppercase garbage
    for word, count, examples in suspicious_upper:
        record = {
            "word": word, 
            "count": count, 
            "type": "uppercase_garbage", 
            "example": examples[0] if examples else ""
        }
        outfile.write(json.dumps(record, ensure_ascii=False) + '\n')
        saved_count += 1
        
    # Save Lowercase garbage
    for word, count, examples in suspicious_lower:
        record = {
            "word": word, 
            "count": count, 
            "type": "lowercase_garbage", 
            "example": examples[0] if examples else ""
        }
        outfile.write(json.dumps(record, ensure_ascii=False) + '\n')
        saved_count += 1

print(f"✅ Success! Saved {saved_count} garbage words to blacklist.")
print("👉 Next step: Run clean_jsonl.py (it will automatically use this list!)")