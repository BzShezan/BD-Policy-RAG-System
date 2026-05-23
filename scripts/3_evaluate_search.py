import json
import os
from sentence_transformers import SentenceTransformer
import chromadb
from rank_bm25 import BM25Okapi

# --- CONFIGURATION ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CENTRAL_JSONL_FOLDER = os.path.join(SCRIPT_DIR, '..', 'data', 'processed_jsonl')
CENTRAL_DB_DIR = os.path.join(SCRIPT_DIR, '..', 'data', 'central_chroma_db')

def hybrid_evaluate():
    print("🔍 Setting up Hybrid Search Evaluation...\n")
    
    # 1. Load Embedding Model & ChromaDB
    model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    client = chromadb.PersistentClient(path=CENTRAL_DB_DIR)
    
    try:
        collection = client.get_collection(name="ministry_policies")
    except Exception:
        print("❌ Database not found! Run '2_build_central_db.py' first.")
        return
    
    # 2. Load Clauses for BM25 (We need the text for keyword matching)
    clauses = []
    if not os.path.exists(CENTRAL_JSONL_FOLDER):
        print("❌ Processed JSONL folder not found!")
        return

    for filename in os.listdir(CENTRAL_JSONL_FOLDER):
        if filename.endswith(".jsonl"):
            with open(os.path.join(CENTRAL_JSONL_FOLDER, filename), 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        clauses.append(json.loads(line))
                        
    if not clauses:
        print("❌ No clauses loaded for BM25.")
        return

    tokenized_corpus = [doc['text'].split() for doc in clauses]
    bm25 = BM25Okapi(tokenized_corpus)

    # --- EVALUATION QUERIES ---
    test_queries = [
        "What is the age limit for old age allowance?", 
        "ভাতার পরিমাণ কত?",
        "কারা এই প্রোগ্রামের জন্য যোগ্য?"
    ]

    for query in test_queries:
        print(f"="*60)
        print(f"❓ USER QUERY: {query}\n")
        
        # 1. Get Dense Results (Top 5 Semantic Matches)
        query_embedding = model.encode([query]).tolist()
        dense_results = collection.query(query_embeddings=query_embedding, n_results=5)
        dense_ids = dense_results['ids'][0]
        
        # 2. Get BM25 Results (Top 5 Keyword Matches)
        tokenized_query = query.split()
        bm25_scores = bm25.get_scores(tokenized_query)
        bm25_top_indices = bm25_scores.argsort()[-5:][::-1]
        bm25_ids = [clauses[idx]['clause_id'] for idx in bm25_top_indices if bm25_scores[idx] > 0]
        
        # 3. Reciprocal Rank Fusion (Merge the two lists)
        rrf_scores = {}
        for rank, clause_id in enumerate(dense_ids):
            rrf_scores[clause_id] = rrf_scores.get(clause_id, 0) + 1 / (rank + 1)
            
        for rank, clause_id in enumerate(bm25_ids):
            rrf_scores[clause_id] = rrf_scores.get(clause_id, 0) + 1 / (rank + 1)
            
        # Sort by highest combined score
        sorted_clauses = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        
        print("⚡ HYBRID SEARCH RESULTS (Combined BM25 + Semantic):")
        for i, (clause_id, score) in enumerate(sorted_clauses[:3]): # Show top 3
            # Find the text for this clause_id
            clause_text = next((c['text'] for c in clauses if c['clause_id'] == clause_id), "")
            clause_tag = next((c['tag'] for c in clauses if c['clause_id'] == clause_id), "")
            print(f"   {i+1}. [Score: {score:.3f} | Ministry: {clause_tag}]")
            print(f"      {clause_text[:150]}...\n")

if __name__ == "__main__":
    hybrid_evaluate()