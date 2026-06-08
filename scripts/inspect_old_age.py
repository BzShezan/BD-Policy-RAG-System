import os
import chromadb

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CENTRAL_DB_DIR = os.path.join(SCRIPT_DIR, '..', 'data', 'central_chroma_db')

client = chromadb.PersistentClient(path=CENTRAL_DB_DIR)
collection = client.get_collection(name="ministry_policies")

# Get all items from the database
all_data = collection.get(include=['documents', 'metadatas'])

target_doc = "SocialMin_OldAgeAll_2013_00_Policy_v1.pdf"

print(f"🔍 Extracting ALL chunks for: {target_doc}\n")
print("=" * 70)

found_count = 0
for doc, meta in zip(all_data['documents'], all_data['metadatas']):
    if meta['doc_id'] == target_doc:
        # Only print chunks that might contain the answer
        if any(kw in doc for kw in ['৬৫', 'বয়স', 'ভাতা', 'টাকা', 'বয়স্ক', 'অক্ষম']):
            found_count += 1
            print(f"ID: {meta.get('clause_id', 'N/A')}")
            print(f"Text: {doc}")
            print("-" * 70)

if found_count == 0:
    print("❌ No chunks found containing age/amount keywords!")
else:
    print(f"\n✅ Found {found_count} relevant chunks.")