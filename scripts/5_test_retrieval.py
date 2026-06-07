import os
from sentence_transformers import SentenceTransformer
import chromadb

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CENTRAL_DB_DIR = os.path.join(SCRIPT_DIR, '..', 'data', 'central_chroma_db')

def test_retrieval():
    model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    client = chromadb.PersistentClient(path=CENTRAL_DB_DIR)
    collection = client.get_collection(name="ministry_policies")
    
    queries = [
        "বয়স্ক ভাতায় কত টাকা দেওয়া হয়?",
        "What is the age limit for old age allowance?"
    ]

    for query in queries:
        print(f"\n{'='*60}")
        print(f"❓ QUERY: {query}\n")
        
        query_embedding = model.encode([query]).tolist()
        results = collection.query(query_embeddings=query_embedding, n_results=5)
        
        for i, doc_id in enumerate(results['ids'][0]):
            doc = results['documents'][0][i]
            meta = results['metadatas'][0][i]
            print(f"Rank {i+1}: [Doc: {meta.get('doc_id', 'N/A')}]")
            print(f"   Text: {doc[:150]}...")
            print()

if __name__ == "__main__":
    test_retrieval()