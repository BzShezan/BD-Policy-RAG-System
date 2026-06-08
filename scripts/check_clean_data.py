import os
import json

JSONL_DIR = os.path.join('..', 'data', 'processed_jsonl')

search_terms = ["৬৫", "বয়স্ক", "বয়স"]

print("=" * 70)
print("🔍 CHECKING: Does '৬৫ বছর' survive the cleaning process?")
print("=" * 70)

# Check ALL jsonl files
for filename in sorted(os.listdir(JSONL_DIR)):
    if not filename.endswith(".jsonl"):
        continue
    if "RAW" in filename:
        continue
        
    filepath = os.path.join(JSONL_DIR, filename)
    
    found_count = 0
    examples = []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            try:
                data = json.loads(line)
                text = data.get('text', '')
                
                if any(term in text for term in search_terms):
                    found_count += 1
                    if len(examples) < 3:
                        examples.append((line_num, data.get('clause_id', 'N/A'), text[:200]))
            except:
                pass
    
    status = "✅ HAS DATA" if found_count > 0 else "❌ NO DATA"
    clean_tag = "(CLEAN)" if "_CLEAN" in filename else "(ORIGINAL)"
    
    print(f"\n{status} {clean_tag} {filename}")
    print(f"   Chunks with '৬৫/বয়স্ক/বয়স': {found_count}")
    
    for line_num, clause_id, text in examples:
        print(f"   Line {line_num} [{clause_id}]: {text}...")

print("\n" + "=" * 70)
print("📊 COMPARISON: Original vs CLEAN")
print("=" * 70)

# Compare original and clean versions of the same file
for filename in sorted(os.listdir(JSONL_DIR)):
    if filename.endswith(".jsonl") and not filename.endswith("_CLEAN.jsonl") and "RAW" not in filename:
        orig_path = os.path.join(JSONL_DIR, filename)
        clean_path = os.path.join(JSONL_DIR, filename.replace(".jsonl", "_CLEAN.jsonl"))
        
        orig_count = 0
        clean_count = 0
        
        with open(orig_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    if any(t in data.get('text', '') for t in search_terms):
                        orig_count += 1
                except: pass
        
        if os.path.exists(clean_path):
            with open(clean_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        if any(t in data.get('text', '') for t in search_terms):
                            clean_count += 1
                    except: pass
        else:
            clean_count = -1  # File doesn't exist
        
        if orig_count > 0 or clean_count > 0:
            print(f"\n📄 {filename}")
            print(f"   Original: {orig_count} chunks with '৬৫/বয়স্ক/বয়স'")
            if clean_count == -1:
                print(f"   CLEAN:    FILE DOES NOT EXIST!")
            else:
                print(f"   CLEAN:    {clean_count} chunks with '৬৫/বয়স্ক/বয়স'")
                if orig_count > 0 and clean_count == 0:
                    print(f"   ⚠️ THE CLEANER DELETED ALL THE DATA!")
                elif orig_count > clean_count:
                    print(f"   ⚠️ THE CLEANER DELETED {orig_count - clean_count} CHUNKS!")