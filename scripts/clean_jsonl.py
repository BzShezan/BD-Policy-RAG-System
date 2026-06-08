import json
import os
import re

# Paths
INPUT_DIR = os.path.join('..', 'data', 'processed_jsonl')
OUTPUT_DIR = os.path.join('..', 'data', 'processed_jsonl')
BLACKLIST_FILE = os.path.join('..', 'data', 'garbage_blacklist.jsonl')

def load_blacklist():
    """Read the JSONL blacklist file and return a set of words to delete"""
    blacklist = set()
    if not os.path.exists(BLACKLIST_FILE):
        print("⚠️ Warning: garbage_blacklist.jsonl not found! No OCR scrubbing will occur.")
        return blacklist

    with open(BLACKLIST_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data = json.loads(line)
                blacklist.add(data['word'])
            except json.JSONDecodeError:
                continue
    
    # Add custom hardcoded words that must ALWAYS be deleted (like 'A' or 'I' as standalone words)
    # 'A' and 'I' are common OCR glitches in Bengali text
    blacklist.update(['A', 'I'])
    
    return blacklist

# Load the blacklist once when the script starts
OCR_BLACKLIST = load_blacklist()
print(f"🧹 Loaded {len(OCR_BLACKLIST)} words from garbage blacklist.")


def scrub_ocr_errors(text):
    """Remove bad English words from Bengali text using the Blacklist"""
    # Only process if there is Bengali text
    if re.search(r'[\u0980-\u09FF]', text):
        # Find all 1 to 5 letter English words
        english_words = re.findall(r'\b([a-zA-Z]{1,5})\b', text)
        
        for word in english_words:
            # If the word is in our blacklist, erase it from the text!
            if word in OCR_BLACKLIST:
                # Use regex word boundary to ensure we only delete the isolated word
                text = re.sub(r'\b' + re.escape(word) + r'\b', '', text)
                
    # Clean up double spaces left behind by removed words
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def is_very_short(text):
    clean_text = text.strip()
    if len(clean_text) < 20:
        return True
    return False

def is_garbage_table(text):
    """Detect broken tables with isolated English letters or too many numbers"""
    isolated_eng_letters = re.findall(r'\b[a-z]\b', text)
    if len(isolated_eng_letters) >= 2:
        return True
    numbers = re.findall(r'\b\d{3,}\b', text)
    if len(numbers) > 5:
        return True
    return False

def is_mostly_gibberish(text):
    special_count = sum(1 for c in text if not c.isalnum() and c not in ' .,;:!?()-—।৳')
    total_chars = len(text)
    if total_chars > 0 and special_count / total_chars > 0.4:
        return True
    return False

def clean_jsonl_file(input_filepath, output_filepath):
    total_lines = 0
    kept_lines = 0
    removed_short = 0
    removed_gibberish = 0
    
    with open(input_filepath, 'r', encoding='utf-8') as infile, \
         open(output_filepath, 'w', encoding='utf-8') as outfile:
        
        for line in infile:
            total_lines += 1
            try:
                data = json.loads(line.strip())
                text = data.get('text', '')
                
                # 1. SCRUB OCR errors (instead of deleting the whole chunk)
                text = scrub_ocr_errors(text)
                data['text'] = text  # Update the text in JSON
                
                # 2. Filter out very short/empty chunks
                if is_very_short(text):
                    removed_short += 1
                    continue
                
                # 3. Filter out broken table fragments
                if is_garbage_table(text):
                    removed_gibberish += 1
                    continue
                    
                # 4. Filter out pure garbage tables
                if is_mostly_gibberish(text):
                    removed_gibberish += 1
                    continue
                
                # If it passes, write to clean file
                outfile.write(json.dumps(data, ensure_ascii=False) + '\n')
                kept_lines += 1
                
            except json.JSONDecodeError:
                continue

    print(f"  📊 Results for {os.path.basename(input_filepath)}:")
    print(f"     Total: {total_lines} | ✅ Kept: {kept_lines} | ❌ Short: {removed_short} | ❌ Gibberish: {removed_gibberish}")

if __name__ == "__main__":
    if not os.path.exists(INPUT_DIR):
        print(f"❌ Error: Directory not found at {INPUT_DIR}")
    else:
        print("🧹 Starting Smart OCR Scrubbing Process...\n")
        for filename in os.listdir(INPUT_DIR):
            if filename.endswith(".jsonl") and not filename.endswith("_CLEAN.jsonl") and "RAW" not in filename:
                input_path = os.path.join(INPUT_DIR, filename)
                output_path = os.path.join(INPUT_DIR, filename.replace(".jsonl", "_CLEAN.jsonl"))
                
                print(f"🧼 Scrubbing: {filename}")
                clean_jsonl_file(input_path, output_path)