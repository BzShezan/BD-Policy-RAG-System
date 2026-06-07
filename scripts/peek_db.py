import chromadb
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(SCRIPT_DIR, '..', 'data', 'central_chroma_db')

# 1. Connect to the database
client = chromadb.PersistentClient(path=DB_DIR)

try:
    # 2. Get the collection
    collection = client.get_collection(name="ministry_policies")
    
    # 3. Fetch the first 5 records to inspect them
    print(f"📦 Total Clauses in Database: {collection.count()}\n")
    print("🔍 Showing the first 5 clauses:\n")
    
    results = collection.get(limit=5, include=["documents", "metadatas"])
    
    for i in range(len(results['ids'])):
        clause_id = results['ids'][i]
        metadata = results['metadatas'][i]
        text = results['documents'][i]
        
        print(f"ID: {clause_id}")
        print(f"Ministry Tag: {metadata.get('tag')}")
        print(f"Doc ID: {metadata.get('doc_id')}")
        print(f"Text Snippet: {text[:150]}...") # Only show first 150 characters
        print("-" * 60)

except Exception as e:
    print(f"❌ Error: {e}")
    print("Make sure you have run '2_build_central_db.py' first!")