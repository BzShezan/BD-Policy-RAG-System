# Teammate integration contract v1.0

The agent project remains `unmochon-live/`. Teammate owns the retriever, translation,
extractors, Knowledge Graph, contradictions and supersession decisions. These stay
in their existing project/environment. No direct Chroma writes from this agent.

POST `/v1/search`, header `X-API-Key`:
```json
{"schema_version":"1.0","question":"বয়স্ক ভাতার বয়স কত?","top_k":3}
```
Successful JSON response:
```json
{
  "schema_version":"1.0",
  "backend":"unmochon_hybrid_v2",
  "sufficient":true,
  "reason":"Relevant clause and requested age extractor verified",
  "warnings":[],
  "evidence":[{
    "id":"real_clause_id",
    "text":"Exact original clause text, not a generated answer",
    "source_kind":"corpus_clause",
    "title":"Real policy title",
    "document_id":"real_doc_id",
    "page":3,
    "source_url":null,
    "published_at":null,
    "checked_at":null,
    "verification":"corpus_only",
    "freshness":"not_checked"
  }]
}
```
The sample values above are schema examples, not policy evidence. Maximum 10
clauses and 50,000 characters per clause. `sufficient=true` requires nonempty
clause evidence. Scores from different retrievers are not comparable; the adapter
owner must decide sufficiency using validated extraction/relevance. Missing,
uncalibrated or conflicting evidence should return `sufficient=false` with a reason.
Do not label a document current solely because it is newer or was fetched today.

Agent `.env` changes only:
```dotenv
RAG_BACKEND=http
RAG_API_URL=http://127.0.0.1:8101/v1/search
RAG_API_KEY=the-shared-rag-service-key
```
Restart the agent process. Its folder, `.venv`, CLI, API route and response schema
stay the same. The agent does not load teammate Python modules into its process.
An unavailable/broken HTTP backend does not silently fall back to the BM25 baseline.

`scripts/teammate_api_example.py` is an optional serving template. It requires the
teammate's real `module:function` adapter. Missing retrieval files from the supplied
ZIP cannot be reconstructed faithfully from a thesis description.

Future ingestion event contract (Week 2/3, not implemented): document hash, source
page URL, download URL, acquisition timestamp, metadata quality and review state.
Semantic `supersedes/contradicts/coexists` decisions belong to teammate. Agent only
emits candidate-version events. Ingestion needs idempotent writes, review gates,
atomic publication and rollback before enabling production corpus updates.
