"""Original corpus-only base system; agent/web workflows are a later phase."""
import time
import uuid
from .original import OriginalBackend
from .schemas import Response

class BaseOrchestrator:
    def __init__(self, settings, backend=None):
        self.backend = backend or OriginalBackend(settings)

    async def ask(self, query):
        start = time.monotonic()
        result = await self.backend.search(query.question, query.top_k)
        status = 'EVIDENCE_FOUND' if result.sufficient else 'NEEDS_VERIFICATION'
        answers = []
        for e in result.evidence:
            # Original extractive-sentence generation remains available, with its confidence gate.
            from chatbot.scripts.answer_generator import generate_answer
            blocks = generate_answer(e.text, e.document_id, e.page, e.source_url or '', result.intents)
            answers.extend(str(b.get('answer') or b.get('text') or e.text) for b in blocks)
        return Response(request_id=str(uuid.uuid4()), question=query.question, route='RAG', status=status,
            answer='\n\n'.join(answers) or result.reason or 'কোনো ফলাফল পাওয়া যায়নি।',
            evidence=result.evidence, warnings=result.warnings, backend=result.backend,
            trace=['RECEIVED', 'ORIGINAL_TRANSLATION_INTENT', 'ORIGINAL_HYBRID_TWO_STAGE'],
            elapsed_ms=int((time.monotonic()-start)*1000), translated=result.translated,
            intents=result.intents, ministry=result.ministry, conflicts=result.conflicts,
            original_results=result.original_results)
