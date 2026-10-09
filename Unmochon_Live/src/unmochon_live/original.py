"""Adapter for the original UI/app.py pipeline, without replacing its algorithms."""
import asyncio
import threading
import os
from .schemas import Evidence, RagResult

class OriginalBackend:
    def __init__(self, settings, retriever=None, translator=None):
        os.environ.setdefault("UNMOCHON_HOME", str(settings.root))
        from UI import app as original
        original.initialize(retriever, translator)
        self.original = original
        self.lock = threading.Lock()

    def _search(self, question, top_k):
        # Original model objects and Gemini SDK key selection have mutable state.
        with self.lock:
            data = self.original.search_question(question, return_k=top_k)
            evidence = []
            for row in data['results']:
                if row.get('confidence_tier') == 'out_of_scope' or not row.get('clause_text'):
                    continue
                metadata = row.get('metadata', {})
                docmeta = row.get('document_metadata', {})
                evidence.append(Evidence(
                    id=row['clause_id'], text=row['clause_text'], source_kind='corpus_clause',
                    title=row['display_name'], source_url=row.get('source_url') or metadata.get('source_url') or None,
                    document_id=row['doc_id'], page=row['page'], ministry=row['ministry'],
                    published_at=metadata.get('circular_date') or docmeta.get('date_display'),
                    viewer_url=row.get('viewer_url'), confidence_tier=row['confidence_tier'],
                    extracted=row['extracted'], explanation=row.get('explanation'), bbox=row.get('bbox'),
                    metadata=metadata, document_metadata=docmeta))
            sufficient = bool(evidence and any(e.confidence_tier in {'high', 'medium'} for e in evidence))
            return RagResult(backend='original_hybrid_two_stage', evidence=evidence, sufficient=sufficient,
                reason=data.get('note', ''), translated=data.get('translated'), intents=data['intents'],
                ministry=data.get('ministry'), conflicts=data.get('conflicts', []),
                original_results=data['results'])

    async def search(self, question, top_k):
        return await asyncio.to_thread(self._search, question, top_k)
