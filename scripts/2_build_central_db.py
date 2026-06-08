import json
import os
from sentence_transformers import SentenceTransformer
import chromadb

# --- CONFIGURATION ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CENTRAL_JSONL_FOLDER = os.path.join(SCRIPT_DIR, '..', 'data', 'processed_jsonl')
CENTRAL_DB_DIR = os.path.join(SCRIPT_DIR, '..', 'data', 'central_chroma_db')

def build_central_database():
    print("🌍 Building Central Vector Database for all Ministries...\n")
    
    # 1. Load Model
    print("📦 Loading embedding model (This might take a minute the first time)...")
    model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    
    # 2. Initialize Central ChromaDB
    client = chromadb.PersistentClient(path=CENTRAL_DB_DIR)
    # Delete old collection if rebuilding
    try:
        client.delete_collection(name="ministry_policies")
        print("🗑️ Cleared old database.")
    except:
        pass
        
    collection = client.get_or_create_collection(name="ministry_policies")

    # 3. Read ALL JSONL files from the folder
    all_clauses = []
    if not os.path.exists(CENTRAL_JSONL_FOLDER):
        os.makedirs(CENTRAL_JSONL_FOLDER)
        print(f"⚠️ Created empty folder {CENTRAL_JSONL_FOLDER}. Put your team's .jsonl files in there and run again.")
        return

    for filename in os.listdir(CENTRAL_JSONL_FOLDER):
       if filename.endswith("_CLEAN.jsonl") and "(1)" not in filename: # Skip duplicates!
            print(f"📄 Reading clauses from: {filename}")
            with open(os.path.join(CENTRAL_JSONL_FOLDER, filename), 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        all_clauses.append(json.loads(line))

    if not all_clauses:
        print("❌ No clauses found to process. Make sure .jsonl files are in the folder.")
        return

    print(f"\n🔄 Generating embeddings for {len(all_clauses)} total clauses...")
    
       # 4. Prepare data for ChromaDB
    documents = [c['text'] for c in all_clauses]
    ids = [c['clause_id'] for c in all_clauses]
    
    # UPDATED: Use .get() with defaults in case teammate's JSON is missing fields
    metadatas = [{
        "doc_id": c.get('doc_id', 'unknown_doc'),
        "section": c.get('section', '0'),
        "tag": c.get('tag', 'Social Welfare') # Default tag for this file
    } for c in all_clauses]
    
    # 5. Embed and Store (Batch processing for speed and memory efficiency)
    batch_size = 500
    for i in range(0, len(documents), batch_size):
        end_idx = i + batch_size
        batch_docs = documents[i:end_idx]
        batch_ids = ids[i:end_idx]
        batch_meta = metadatas[i:end_idx]
        
        print(f"   -> Embedding batch {i//batch_size + 1}/{(len(documents)-1)//batch_size + 1}...")
        embeddings = model.encode(batch_docs).tolist()
        
        collection.add(
            documents=batch_docs,
            embeddings=embeddings,
            metadatas=batch_meta,
            ids=batch_ids
        )

    print(f"\n✅ CENTRAL DATABASE COMPLETE! Total clauses stored: {collection.count()}")
    print(f"💾 Database saved to: {CENTRAL_DB_DIR}")

if __name__ == "__main__":
    build_central_database()