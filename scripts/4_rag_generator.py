
import json
import os
from sentence_transformers import SentenceTransformer
import chromadb
from rank_bm25 import BM25Okapi
from openai import OpenAI

# --- CONFIGURATION ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CENTRAL_JSONL_FOLDER = os.path.join(SCRIPT_DIR, '..', 'data', 'processed_jsonl')
CENTRAL_DB_DIR = os.path.join(SCRIPT_DIR, '..', 'data', 'central_chroma_db')

# PUT YOUR GROQ API KEY HERE
GROQ_API_KEY = " " 

def answer_query(query):
    print(f"\n❓ USER: {query}\n")
    
    # 1. Setup Clients
    model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    client = chromadb.PersistentClient(path=CENTRAL_DB_DIR)
    collection = client.get_collection(name="ministry_policies")
    llm_client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")
    
    # 2. Load Clauses for BM25
    clauses = []
    for filename in os.listdir(CENTRAL_JSONL_FOLDER):
        if filename.endswith(".jsonl"):
            with open(os.path.join(CENTRAL_JSONL_FOLDER, filename), 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        clauses.append(json.loads(line))
    tokenized_corpus = [doc['text'].split() for doc in clauses]
    bm25 = BM25Okapi(tokenized_corpus)

    # 3. Hybrid Search (UPGRADED: Fetch Top 20 for maximum accuracy)
    query_embedding = model.encode([query]).tolist()
    dense_results = collection.query(query_embeddings=query_embedding, n_results=20) # Wider Net!
    dense_ids = dense_results['ids'][0]
    
    tokenized_query = query.split()
    bm25_scores = bm25.get_scores(tokenized_query)
    bm25_top_indices = bm25_scores.argsort()[-20:][::-1] # Wider Net!
    bm25_ids = [clauses[idx]['clause_id'] for idx in bm25_top_indices if bm25_scores[idx] > 0]
    
    # Combine and deduplicate IDs
    retrieved_ids = list(dict.fromkeys(dense_ids + bm25_ids))
    
    # Fetch the actual text for the top retrieved IDs
    context_clauses = [next(c for c in clauses if c['clause_id'] == cid) for cid in retrieved_ids[:20]]
    context_text = "\n\n".join([f"Source Document: {c.get('doc_id', 'Unknown')} | Clause: {c['clause_id']}\n{c['text']}" for c in context_clauses])

    # 4. LLM Generation (UPGRADED: Stricter Prompt)
    prompt = f"""You are an expert assistant on Bangladesh Social Welfare policies. 
Use ONLY the following context clauses to answer the user's question. 

CRITICAL RULES:
1. If the user asks about amounts or money, scan the context very carefully for numbers and words like 'টাকা' or 'BDT' or 'কোটি'.
2. If you find the answer, state it clearly and mention which Source Document it came from.
3. If the context does not contain the answer, say "The provided documents do not contain this specific information."
4. Answer in the same language the user asked the question.

CONTEXT:
{context_text}

USER QUESTION: {query}

ANSWER:"""

    try:
        chat_completion = llm_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.0, # 0.0 temperature = purely factual, no hallucination
        )
        answer = chat_completion.choices[0].message.content
        print("💡 ASSISTANT:")
        print(answer)
    except Exception as e:
        print(f"❌ Error calling LLM: {e}")

if __name__ == "__main__":
    if GROQ_API_KEY == "gsk_YOUR_API_KEY_HERE":
        print("❌ Please add your Groq API key to the script first!")
    else:
        print("🤖 Social Welfare Policy Assistant Ready!")
        print("Type your question (or type 'exit' to quit):")
        while True:
            user_input = input("\nYou: ")
            if user_input.lower() in ['exit', 'quit']:
                break
            answer_query(user_input)