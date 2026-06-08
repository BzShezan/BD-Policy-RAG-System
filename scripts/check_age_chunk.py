import os
import json

JSONL_DIR = os.path.join('..', 'data', 'processed_jsonl')

print("🔍 Searching for '৬৫' in CLEAN JSONL files...\n")

found = False
for filename in os.listdir(JSONL_DIR):
    if filename.endswith("_CLEAN.jsonl"):
        filepath = os.path.join(JSONL_DIR, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                data = json.loads(line)
                text = data.get('text', '')
                if '৬৫' in text and 'বয়স' in text:
                    found = True
                    print(f"✅ FOUND IN: {filename}")
                    print(f"   Text: {text[:300]}...")
                    print("-" * 60)

if not found:
    print("❌ CRITICAL: The chunk with '৬৫ বছর' was DELETED by the cleaner!")
    print("   The garbage blacklist might be too aggressive.")