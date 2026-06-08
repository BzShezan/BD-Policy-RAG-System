import os
import chromadb

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CENTRAL_DB_DIR = os.path.join(SCRIPT_DIR, '..', 'data', 'central_chroma_db')

def debug_database():
    client = chromadb.PersistentClient(path=CENTRAL_DB_DIR)
    collection = client.get_collection(name="ministry_policies")
    
    print(f"📊 Total chunks in database: {collection.count()}")
    print("=" * 60)
    
    # Get all unique document IDs
    all_data = collection.get(include=['metadatas'])
    doc_ids = set(meta['doc_id'] for meta in all_data['metadatas'])
    
    print(f"📁 Unique documents: {len(doc_ids)}")
    for doc_id in sorted(doc_ids):
        count = sum(1 for meta in all_data['metadatas'] if meta['doc_id'] == doc_id)
        print(f"   - {doc_id}: {count} chunks")
    
    print("\n" + "=" * 60)
    
    # Search specifically for old age allowance age limit
    print("\n🔍 Searching for 'বয়স্ক ভাতা বয়স ৬৫' (Old Age Allowance age 65)...")
    results = collection.query(
        query_texts=["বয়স্ক ভাতা বয়স ৬৫"],
        n_results=3
    )
    
    for i, doc in enumerate(results['documents'][0]):
        meta = results['metadatas'][0][i]
        print(f"\n  Result {i+1} [Doc: {meta['doc_id']}]:")
        print(f"  {doc[:200]}...")
    
    print("\n" + "=" * 60)
    
    # Search for the specific answer about age limit
    print("\n🔍 Searching for '৬৫ বছর' (65 years)...")
    results2 = collection.query(
        query_texts=["৬৫ বছর বয়স"],
        n_results=3
    )
    
    for i, doc in enumerate(results2['documents'][0]):
        meta = results2['metadatas'][0][i]
        print(f"\n  Result {i+1} [Doc: {meta['doc_id']}]:")
        print(f"  {doc[:200]}...")
    
    # Check if any chunk contains "৬৫"
    print("\n" + "=" * 60)
    print("\n🔍 Checking if ANY chunk contains '৬৫' (65)...")
    all_docs = collection.get(include=['documents', 'metadatas'])
    found = 0
    for doc, meta in zip(all_docs['documents'], all_docs['metadatas']):
        if '৬৫' in doc:
            found += 1
            if found <= 5:  # Show first 5
                print(f"\n  Found in [Doc: {meta['doc_id']}]:")
                print(f"  {doc[:200]}...")
    
    print(f"\n  Total chunks containing '৬৫': {found}")
    if found == 0:
        print("  ⚠️ WARNING: No chunks with '৬৫' found! The age limit data may be missing!")

if __name__ == "__main__":
    debug_database()