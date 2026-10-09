import logging
import time
import uuid
from .rag import CorpusBackend,HttpBackend
from .registry import Registry
from .schemas import Query,Response
from .text import freshness_requested
from .web import LiveRetriever

log=logging.getLogger("unmochon")

class Orchestrator:
    def __init__(self,settings,rag=None,live=None,registry=None):
        self.settings=settings
        self.registry=registry or Registry(settings.source_registry)
        self.rag=rag or (CorpusBackend(settings.corpus_dir) if settings.rag_backend=="corpus" else HttpBackend(settings))
        self.live=live or LiveRetriever(settings,self.registry)

    async def ask(self,query:Query):
        start=time.monotonic();req=str(uuid.uuid4());trace=["RECEIVED"]
        services=self.registry.match(query.question)
        if len(services)>1:
            return self._response(query,req,start,"CLARIFY","CLARIFICATION_REQUIRED",
                "একবারে একটি service বেছে প্রশ্ন করুন: "+", ".join(s.id for s in services),[],[],trace,"router")
        service=services[0] if services else None
        if service:
            trace.append("KNOWN_SERVICE_OUTSIDE_POLICY_CORPUS")
            evidence,warnings,events,status=await self.live.retrieve(query.question,service)
            return self._response(query,req,start,"LIVE_SERVICE",status,self._format(evidence,status,query.question),
                evidence,warnings,trace+events,"official_web",service.id)
        trace.append("RAG_SEARCH")
        result=await self.rag.search(query.question,query.top_k)
        trace.append("RAG_SUFFICIENT" if result.sufficient else "RAG_INSUFFICIENT")
        if result.sufficient and not freshness_requested(query.question):
            return self._response(query,req,start,"RAG","EVIDENCE_FOUND",self._format(result.evidence,"EVIDENCE_FOUND",query.question),
                result.evidence,result.warnings,trace,result.backend)
        trace.append("FRESHNESS_REQUEST" if freshness_requested(query.question) else "CORPUS_GAP")
        seeds=[e.source_url for e in result.evidence if e.source_url]
        evidence,warnings,events,status=await self.live.retrieve(query.question,extra_seeds=seeds)
        if not evidence and result.evidence:
            # Show existing candidates separately, with not_checked freshness; don't upgrade failed live checks.
            warnings.append("Stored clauses are related candidates only; requested freshness/sufficiency was not established.")
            evidence=result.evidence
        return self._response(query,req,start,"LIVE_SERVICE",status,self._format(evidence,status,query.question),
            evidence,result.warnings+warnings,trace+events,result.backend+"+official_web")

    def _format(self,evidence,status,question=""):
        lead={"EVIDENCE_FOUND":"প্রশ্নের সঙ্গে সম্পর্কিত উৎসের উদ্ধৃতি পাওয়া গেছে। মূল উৎস মিলিয়ে দেখুন।",
            "UNAVAILABLE":"সরকারি উৎস এখন পড়া যায়নি। যাচাইকৃত service নির্দেশনা দেওয়া যাচ্ছে না।",
            "NEEDS_VERIFICATION":"সম্পূর্ণ উত্তর যাচাই করার মতো তথ্য পাওয়া যায়নি।"}[status]
        blocks=[lead]
        for index,e in enumerate(evidence,1):
            reference=e.source_url or f"{e.document_id}, page {e.page}"
            excerpt=e.text[:1600]
            if any(term in question for term in ("age","বয়স","বয়স")):
                lines=e.text.split("\n")
                for line_index,line in enumerate(lines):
                    if any(term in line for term in ("বয়স","বয়স","age")):
                        excerpt="\n".join(lines[max(0,line_index-1):line_index+2])[:1600]
                        break
            blocks.append(f"[{index}] {excerpt}\nসূত্র: {reference}")
        return "\n\n".join(blocks)

    def _response(self,query,req,start,route,status,answer,evidence,warnings,trace,backend,service=None):
        elapsed=int((time.monotonic()-start)*1000)
        # Never log citizen questions, tokens, or retrieved personal data.
        log.info("request_id=%s route=%s status=%s elapsed_ms=%s",req,route,status,elapsed)
        return Response(request_id=req,question=query.question,route=route,status=status,answer=answer,
            evidence=evidence,warnings=warnings,trace=trace,backend=backend,elapsed_ms=elapsed,service=service)
