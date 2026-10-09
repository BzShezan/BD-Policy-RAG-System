"""Hybrid retrieval: BM25 + dense vectors, fused with RRF.

Dense search finds clauses that mean the same thing in different words.
BM25 finds exact matches, which matters here because government text is
full of memo numbers, amounts and ages that must match precisely.
Neither alone is enough, so both run and RRF merges the two rankings.

Queries are passed through a Bengali policy-domain synonym expander
before retrieval - user vocabulary (বয়সসীমা, আয়সীমা) rarely matches
the wording used in the actual policy clauses (বছর, আয়), and the
multilingual embedding model does not bridge that gap reliably.

Note on bilingual queries: English->Bengali translation is done by
the CALLER (e.g. app.py, test scripts) BEFORE calling search(), not
here. This is because detect_intents() also needs the translated
query, so translation must happen up the stack. Doing it here would
mean intent classification sees English while retrieval sees Bengali,
breaking intent detection on English queries.
"""

import pickle

import chromadb

from scripts.retrieval import config
from scripts.retrieval.tokenize_bn import tokenize
from scripts.retrieval.query_expansion import expand


class HybridRetriever:
    """Loads both indexes once and answers queries against them."""

    def __init__(self, model=None):
        print("loading retriever ...")

        self.client = chromadb.PersistentClient(path=config.CHROMADB_DIR)
        self.collection = self.client.get_collection(config.COLLECTION_NAME)

        if model is None:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer(config.EMBED_MODEL)
        self.model = model

        with open(config.BM25_INDEX_PATH, "rb") as f:
            payload = pickle.load(f)
        self.bm25 = payload["bm25"]
        self.bm25_ids = payload["ids"]

        # id -> position in the BM25 arrays, needed to filter sparse
        # results by allowed id set without a linear scan every query
        self.bm25_id_to_pos = {doc_id: i for i, doc_id in enumerate(self.bm25_ids)}

        print(f"  ready, {self.collection.count()} items indexed")

    # ---------------------------------------------------------------

    def _dense(self, query, k, where=None):
        emb = self.model.encode([query]).tolist()
        res = self.collection.query(
            query_embeddings=emb,
            n_results=k,
            where=where,
        )
        return res["ids"][0]

    def _sparse(self, query, k, allowed_ids=None):
        """BM25 search. Returns ids in rank order.

        allowed_ids restricts results to a specific set of ids (e.g. one
        ministry). Filtering happens BEFORE ranking is truncated to k,
        not after - otherwise a query could return fewer than k allowed
        results even though more exist further down the full ranking.
        """
        tokens = tokenize(query)
        if not tokens:
            return []

        scores = self.bm25.get_scores(tokens)
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)

        results = []
        for i in ranked:
            if scores[i] <= 0:
                break
            doc_id = self.bm25_ids[i]
            if allowed_ids is not None and doc_id not in allowed_ids:
                continue
            results.append(doc_id)
            if len(results) >= k:
                break

        return results

    def _get_allowed_ids(self, where):
        """Ask ChromaDB which ids match the metadata filter, so BM25
        can be restricted to the same set before fusion. Pulling ids
        only (no documents/embeddings) keeps this cheap even at scale.
        """
        if where is None:
            return None
        got = self.collection.get(where=where, include=[])
        return set(got["ids"])

    @staticmethod
    def _rrf(rankings, k):
        """Reciprocal Rank Fusion.

        Each list contributes 1/(k + rank) to every id it contains. A
        document ranked well by both retrievers beats one ranked highly
        by only one, which is the whole point of running both.
        """
        scores = {}
        for ranking in rankings:
            for rank, doc_id in enumerate(ranking, start=1):
                scores[doc_id] = scores.get(doc_id, 0) + 1.0 / (k + rank)
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)

    # ---------------------------------------------------------------

    def search(self, query, top_k=10, ministry=None, exclude_tables=False):
        """Run both retrievers, fuse, and return results with metadata.

        Query is expected to already be in Bengali (translated by
        caller if the user typed English). See module docstring for why.

        ministry       restricts to one ministry, e.g. "Social Welfare"
        exclude_tables drops table documents from the dense side
        """
        # Expand query with domain synonyms BEFORE retrieval so both
        # BM25 (via tokenize) and dense (via encode) see the enriched
        # form. Original query terms are preserved and still carry the
        # strongest weight - synonyms are appended, not substituted.
        query = expand(query)

        where = {}
        if ministry:
            where["ministry"] = ministry
        if exclude_tables:
            where["is_table"] = False
        where = ({"$and": [{key: value} for key, value in where.items()]}
                 if len(where) > 1 else where or None)

        n = min(config.CANDIDATES_PER_RETRIEVER, self.collection.count())
        if not n:
            return []

        # Work out which ids are allowed under the filter ONCE, then
        # apply it to both retrievers - this is the fix for the leak.
        allowed_ids = self._get_allowed_ids(where)

        dense_ids  = self._dense(query, n, where=where)
        sparse_ids = self._sparse(query, n, allowed_ids=allowed_ids)

        fused = self._rrf([dense_ids, sparse_ids], config.RRF_K)
        top_ids = [doc_id for doc_id, _ in fused[:top_k]]

        if not top_ids:
            return []

        got = self.collection.get(ids=top_ids,
                                  include=["documents", "metadatas"])

        # ChromaDB returns these in its own order, so rebuild the
        # ranking we actually asked for
        by_id = {
            i: (d, m)
            for i, d, m in zip(got["ids"], got["documents"], got["metadatas"])
        }

        score_by_id = dict(fused)
        results = []
        for doc_id in top_ids:
            if doc_id not in by_id:
                continue
            text, meta = by_id[doc_id]
            results.append({
                "id":         doc_id,
                "text":       text,
                "rrf_score":  score_by_id[doc_id],
                "in_dense":   doc_id in dense_ids,
                "in_sparse":  doc_id in sparse_ids,
                "ministry":   meta.get("ministry", ""),
                "doc_id":     meta.get("doc_id", ""),
                "page":       meta.get("page_number", 0),
                "bbox":       meta.get("bbox", ""),
                "is_table":   meta.get("is_table", False),
                "metadata":   dict(meta),
            })

        return results