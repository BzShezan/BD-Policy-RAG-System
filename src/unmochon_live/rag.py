import gzip
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Protocol
import httpx
from .schemas import Evidence, RagResult
from .text import tokens

class RagBackend(Protocol):
    async def search(self, question: str, top_k: int) -> RagResult: ...

class CorpusBackend:
    """Read-only BM25 baseline over REAL uploaded clauses; never masquerades as hybrid RAG."""
    def __init__(self, folder: Path):
        self.rows = []
        self.postings = defaultdict(dict)
        self.lengths = []
        metadata_path = folder / "doc_metadata.json"
        self.metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
        files = sorted(folder.glob("*_clauses.jsonl.gz")) + sorted(folder.glob("*_clauses.jsonl"))
        if not files:
            raise ValueError("No corpus files; check CORPUS_DIR")
        seen = set()
        for file in files:
            opener = gzip.open if file.suffix == ".gz" else open
            with opener(file, "rt", encoding="utf-8") as stream:
                for line_no, line in enumerate(stream, 1):
                    if not line.strip(): continue
                    try: row = json.loads(line)
                    except ValueError as exc:
                        raise ValueError(f"Invalid JSON in {file.name}:{line_no}") from exc
                    if not row.get("text") or row.get("needs_review", False): continue
                    identity = row.get("clause_id") or (row.get("doc_id"), row.get("page_number"), row["text"])
                    if identity in seen: continue
                    seen.add(identity)
                    counts = Counter(tokens(row["text"] + " " + row.get("doc_id", "")))
                    index = len(self.rows)
                    self.rows.append(row); self.lengths.append(sum(counts.values()))
                    for token, count in counts.items(): self.postings[token][index] = count
        if not self.rows: raise ValueError("Corpus contains no usable clauses")
        self.avg_length = sum(self.lengths) / len(self.rows)

    async def search(self, question, top_k):
        terms = set(tokens(question))
        scores = defaultdict(float); matched = defaultdict(set)
        n = len(self.rows)
        for term in terms:
            posting = self.postings.get(term, {})
            idf = math.log(1 + (n - len(posting) + .5) / (len(posting) + .5))
            for index, freq in posting.items():
                scores[index] += idf * freq * 2.5 / (freq + 1.5 * (.25 + .75 * self.lengths[index] / self.avg_length))
                matched[index].add(term)
        # Require all salient query terms. This is a conservative demo gate, NOT calibrated confidence.
        ranked = sorted(scores, key=lambda i: (len(matched[i]) / max(len(terms), 1), scores[i]), reverse=True)
        selected = ranked[:top_k]
        sufficient = bool(selected and terms and matched[selected[0]] == terms)
        evidence = []
        for index in selected:
            row = self.rows[index]; doc_id=row.get("doc_id", "")
            meta = self.metadata.get(doc_id) or self.metadata.get(doc_id.removesuffix(".pdf")) or {}
            evidence.append(Evidence(id=row.get("clause_id", str(index)), text=row["text"],
                title=meta.get("display_name", row.get("doc_id", "")), source_kind="corpus_clause",
                document_id=row.get("doc_id"), page=row.get("page_number"),
                source_url=row.get("source_url") or meta.get("source_url"),
                published_at=row.get("circular_date") or meta.get("date_display") or None))
        return RagResult(backend="corpus_bm25_baseline", evidence=evidence, sufficient=sufficient,
            reason="All salient query tokens found in top clause" if sufficient else "Insufficient lexical evidence",
            warnings=["BM25 bootstrap baseline; not the original hybrid retriever. Dates and source URLs are inherited metadata, not freshly verified."])

class HttpBackend:
    """One versioned contract; full hybrid retrieval / KG stays under teammate ownership."""
    def __init__(self, settings, transport=None):
        self.settings = settings; self.transport = transport

    async def search(self, question, top_k):
        headers = {"X-API-Key": self.settings.rag_api_key} if self.settings.rag_api_key else {}
        try:
            async with httpx.AsyncClient(timeout=self.settings.rag_timeout, transport=self.transport, trust_env=False) as client:
                async with client.stream("POST", self.settings.rag_api_url,
                    json={"schema_version": "1.0", "question": question, "top_k": top_k}, headers=headers) as response:
                    response.raise_for_status()
                    chunks=[]; size=0
                    async for chunk in response.aiter_bytes():
                        size+=len(chunk)
                        if size>1000000: raise ValueError("RAG response too large")
                        chunks.append(chunk)
                result = RagResult.model_validate_json(b"".join(chunks))
                if any(e.source_kind != "corpus_clause" for e in result.evidence):
                    raise ValueError("RAG contract accepts corpus clauses only")
                if result.sufficient and not result.evidence:
                    raise ValueError("RAG sufficiency requires evidence")
                return result
        except (httpx.HTTPError, ValueError):
            return RagResult(backend="teammate_http", reason="RAG API unavailable or invalid contract",
                warnings=["RAG API unavailable or invalid contract; no silent baseline substitution."])
