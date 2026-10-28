"""Fresh scoped consent -> existing Stages 3/4/5/6 -> original application query."""
from __future__ import annotations
import asyncio
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import threading
import time
import uuid

ACTIVE = {'crawling','processing','processed','verifying','updating','activating','requerying','cancelling'}

class ResearchFlowError(ValueError):
    pass

def session_identity(cookie):
    return hashlib.sha256(cookie.encode('utf-8')).hexdigest()

class ResearchFlow:
    def __init__(self, settings, *, registry=None, controller_factory=None, crawler_factory=None,
                 execute=None, updater=None, transport_factory=None):
        self.settings = settings
        self.root = Path(settings.stage4_package or settings.root/'reference_pipelines/stage4').resolve()
        self.output_root = Path(settings.research_output_root or settings.root/'data/research_runs').resolve()
        self.requests = {}
        self.registry, self.controller_factory, self.crawler_factory = registry, controller_factory, crawler_factory
        self.execute, self.updater, self.transport_factory = execute, updater, transport_factory
        self._loaded = False

    def _load(self):
        if self._loaded: return
        if self.settings.app_env != 'local' or self.settings.rag_backend != 'stage6':
            raise ResearchFlowError('Research control is available only in local Stage 6 mode')
        from .runtime import load_stage4
        load_stage4(self.root)
        from .research_registry import make_registry
        from stage3.consent import CrawlerPermissionController
        from .research_crawler import crawler_factory
        from stage3.transport import HTTPStransport
        from .controlled_update import ControlledUpdater
        self.registry = self.registry or make_registry(self.settings.research_registry)
        self.controller_factory = self.controller_factory or (lambda: CrawlerPermissionController(self.registry))
        self.crawler_factory = self.crawler_factory or crawler_factory
        self.transport_factory = self.transport_factory or HTTPStransport
        self.updater = self.updater or ControlledUpdater(self.settings)
        self._loaded = True

    def offer(self, response, cookie):
        if response.action != 'REQUEST_RESEARCH_PERMISSION' or not response.generation: return None
        trigger = response.research_trigger or {}
        program, ministry = trigger.get('program'), trigger.get('ministry')
        if not isinstance(program,str) or not program.strip() or not ministry:
            return {'available':False, 'reason':'A bounded government program and authority must be established'}
        self._load()
        if ministry not in self.registry.entries:
            return {'available':False, 'reason':'Authority is not in the verified government registry'}
        reason = str(trigger.get('reason') or 'Insufficient verified evidence')[:500]
        plan = self.registry.make_plan(response.question, program, ministry, reason)
        controller = self.controller_factory()
        issued = controller.request(plan, ttl_seconds=300)
        for value in self.requests.values():
            if value['session'] == session_identity(cookie) and value['status'] == 'pending':
                value['controller'].decide(value['request'].request_id,decision='deny',
                    actor='local_browser',consent_note='Superseded by a newer question')
                value['status'] = 'denied'
        ticket = secrets.token_urlsafe(32)
        self.requests[ticket] = {'session':session_identity(cookie), 'question':response.question,
            'top_k':5, 'generation':response.generation, 'plan':plan, 'controller':controller,
            'request':issued, 'status':'pending', 'created':time.time(), 'output':None,
            'detail':None, 'task':None, 'cancel':threading.Event(), 'history':[], 'child':None,
            'activated':None, 'built':None, 'result':None, 'index_writes':0, 'review_dir':None}
        for key in list(self.requests):
            if len(self.requests) <= 40: break
            if self.requests[key]['status'] not in ACTIVE: del self.requests[key]
        from .evidence_verification import AUTO_POLICY as POLICY
        return {'available':True, 'ticket':ticket, 'request_id':issued.request_id,
            'question':plan.question, 'ministry':plan.ministry, 'program':plan.program,
            'reason':plan.reason, 'gap_type':trigger.get('gap_type','relevant_question_insufficient_evidence'),
            'hosts':list(plan.allowed_hosts), 'seed_urls':list(plan.seed_urls),
            'max_http_requests':plan.max_http_requests, 'max_pages':plan.max_pages,
            'max_bytes':plan.max_bytes, 'crawl_seconds':plan.timeout_seconds,
            'job_seconds':self.settings.research_job_seconds, 'expires_at':issued.expires_at,
            'generation':response.generation, 'status':'pending', 'verification_policy':POLICY,
            'conditional_update_disclosure':'এই প্রশ্নের জন্য সরকারি পৃষ্ঠা ও PDF সংগ্রহ করা হবে। পড়া যায় এমন '
                'সব content স্বয়ংক্রিয়ভাবে chunk করে জ্ঞানভান্ডারে যোগ হবে; human review লাগবে না। '
                'তারপর একই retrieval pipeline দিয়ে প্রশ্নের উত্তর ও মূল উৎস দেখানো হবে।'}

    def _get(self, ticket, cookie):
        e = self.requests.get(ticket)
        if not e or not secrets.compare_digest(e['session'], session_identity(cookie)):
            raise ResearchFlowError('Unknown or expired research request for this session')
        return e

    def _step(self,e,status,detail=None):
        e['status'], e['detail'] = status, detail
        e['history'].append({'status':status,'at':time.time()})
        e['history'] = e['history'][-25:]
        if e.get('update_consent'):
            from .evidence_verification import write
            try:
                write(self.output_root/'jobs'/(e['request'].request_id+'.json'),{
                    'request_id':e['request'].request_id,'question':e['question'],'status':status,
                    'generation_at_consent':e['generation'],'history':e['history'],'detail':detail,
                    'index_writes':e['index_writes'],'automatic_resume_authorized':False})
            except OSError:
                # Progress journaling is supplementary. Source/consent receipts
                # and sealed evidence are mandatory and fail the actual gates.
                e['journal_error']='Progress journal could not be saved'

    def _check(self,e):
        if e['cancel'].is_set(): raise ResearchFlowError('Research cancelled')
        if time.monotonic() >= e['deadline']: raise ResearchFlowError('Research processing deadline exceeded')

    def decide(self,ticket,cookie,decision,allow_update=False):
        e = self._get(ticket,cookie)
        if e['status'] != 'pending' or decision not in ('approve','deny') or type(allow_update) is not bool:
            raise ResearchFlowError('Only a pending request accepts one explicit decision')
        if decision == 'approve' and sum(v['status'] in ACTIVE for v in self.requests.values()) >= self.settings.research_max_jobs:
            raise ResearchFlowError('Research capacity reached; retry before consent expires')
        from .evidence_verification import AUTO_POLICY as POLICY,digest
        consent = {'policy':POLICY,'request_id':e['request'].request_id,
            'question_sha256':e['plan'].question_sha256,'allow_conditional_update':allow_update}
        permit = e['controller'].decide(e['request'].request_id,decision=decision,
            actor='local_authenticated_browser',consent_note='Fresh scoped UI decision; conditional update disclosure '+digest(consent))
        if decision == 'deny':
            e['status']='denied'
            return {'status':'denied','network_calls':0,'index_writes':0}
        e['update_consent']=consent
        e['deadline']=time.monotonic()+self.settings.research_job_seconds
        self._step(e,'crawling')
        e['task']=asyncio.create_task(self._pipeline(e,permit))
        return {'status':'crawling','network_calls':'pending','index_writes':0}

    async def _pipeline(self,e,permit=None,resume=False):
        try:
            self._check(e)
            if not resume:
                await asyncio.to_thread(self._crawl,e,permit)
                if e['status'] != 'staged_unverified' or not e['output']: return
                self._check(e); self._step(e,'processing',e['detail'])
                await asyncio.to_thread(self._process,e)
                if e['status'] != 'processed': return
                self._check(e); self._step(e,'verifying',e['detail'])
                receipt=await asyncio.to_thread(self._verify,e)
            else: receipt=e['receipt']
            self._check(e)
            if receipt['status'] != 'verified_eligible':
                self._step(e,'no_usable_evidence',{'issues':receipt['issues'],'review_available':False,
                    'message':'সরকারি উৎস থেকে পড়ার উপযোগী content পাওয়া যায়নি। নতুন chunk যোগ হয়নি।'})
                return
            self._step(e,'updating',{'message':'Isolated paired candidate তৈরি ও পরীক্ষা হচ্ছে।'})
            built=await asyncio.to_thread(self.updater.build,Path(e['review_dir'])/'verification_receipt.json',e)
            e['built']=built
            self._check(e); self._step(e,'activating')
            e['activated']=await asyncio.to_thread(self.updater.activate,built,e)
            self._check(e); self._step(e,'requerying')
            if self.execute is None: raise ResearchFlowError('Original application re-query callback is missing')
            from .schemas import Query
            result=await self.execute(Query(question=e['question'],top_k=e['top_k']))
            self._check(e)
            if result.generation != built['candidate']:
                raise ResearchFlowError('Original question could not query the activated generation')
            if result.status != 'EVIDENCE_FOUND':
                from .schemas import Evidence
                sources=[]
                for row in receipt['index_items'][:5]:
                    m=row['metadata'];page=m.get('page_number') or None
                    viewer=(f"/pdfjs/web/viewer.html?file=/verified-pdf/{m['source_raw_sha256']}.pdf#page={page}"
                            if page else None)
                    sources.append(Evidence(id=row['id'],text=row['text'],source_kind='corpus_clause' if page else 'official_web',
                        document_id=m['doc_id'],title=m.get('title') or '',source_url=m['source_url'],page=page,
                        ministry=m['ministry'],viewer_url=viewer,metadata=m,verification='official_fetched'))
                result=result.model_copy(update={'action':'RESEARCH_COMPLETE_NO_ANSWER','research_trigger':None,
                    'research_offer':None,'evidence':sources,'overview':{},
                    'answer':f"গবেষণা শেষ হয়েছে; {built['added_items']}টি নতুন chunk জ্ঞানভান্ডারে যোগ হয়েছে। "
                             'পাওয়া উৎসে এই প্রশ্নের সুনির্দিষ্ট উত্তর নেই। সংগৃহীত লেখা ও উৎস নিচে দেখানো হলো।'})
            e['result']=result.model_dump(mode='json')
            e['index_writes']=built['added_items']
            self._step(e,'answer_ready' if result.status == 'EVIDENCE_FOUND' else 'research_complete',{'added_items':built['added_items'],'active_generation':built['candidate'],
                'duplicate_skips':built['duplicate_skips'],'message':'প্রমাণসহ উত্তর প্রস্তুত।'})
        except Exception as ex:
            e['result']=None
            e['index_writes']=0
            recovery=None
            if e['activated']:
                try:
                    recovery=await asyncio.to_thread(self.updater.rollback,e['activated'],e['built']['before'])
                    e['activated']=None
                except Exception as rollback_error:
                    self._step(e,'recovery_required',{'message':str(ex),'rollback_error':str(rollback_error),
                        'message_bn':'Rollback নিশ্চিত করা যায়নি। নতুন update বন্ধ রেখে diagnostic দেখুন।'})
                    return
            self._step(e,'cancelled' if e['cancel'].is_set() else 'failed',{
                'error_type':type(ex).__name__,'message':str(ex),'rollback_performed':bool(recovery),
                'active_generation':recovery['generation'] if recovery else e['generation'],
                'message_bn':'যাচাইকৃত উত্তর তৈরি হয়নি। আগের generation বহাল আছে।'})

    def _crawl(self,e,permit):
        from stage3.crawler import json_write,prepare_output
        base=self.transport_factory(); flow=self
        class CancellableTransport:
            @property
            def calls(self): return base.calls
            def open(self,*args):
                flow._check(e)
                return base.open(*args)
        transport=CancellableTransport()
        output=self.output_root/('raw_'+uuid.uuid4().hex)
        try:
            self.output_root.mkdir(parents=True,exist_ok=True); prepare_output(output)
            e['output']=str(output)
            crawler=self.crawler_factory(self.registry,transport,output)
            staged=e['controller'].execute_crawl(permit,question=e['question'],plan=e['plan'],crawler=crawler)
            json_write(output/'stage3_app_summary.json',{'schema_version':1,'status':'staged_unverified',
                'request_id':e['request'].request_id,'generation_at_consent':e['generation'],
                'result':asdict(staged.result),'scope':asdict(e['plan']),
                'network_request_attempts':transport.calls,'index_writes':0,
                'current_policy_verified':False,'source_approval':False})
            json_write(output/'latest_consent_audit.json',e['controller'].audit)
            json_write(output/'conditional_update_consent.json',e['update_consent'])
            self._step(e,'staged_unverified',{'artifacts':len(staged.result.artifacts),
                'network_request_attempts':transport.calls})
        except Exception as ex:
            if output.is_dir(): json_write(output/'latest_consent_audit.json',e['controller'].audit)
            if e['cancel'].is_set(): raise
            self._step(e,'crawl_failed',{'error_type':type(ex).__name__,'message':str(ex),
                'network_request_attempts':transport.calls,'index_writes':0})

    def _process(self,e):
        output=self.output_root/('processed_'+uuid.uuid4().hex)
        env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONUTF8='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
        env['PYTHONPATH']=str(self.settings.root/'src')+os.pathsep+str(self.settings.root)
        if self.settings.research_registry: env['RESEARCH_SOURCE_REGISTRY']=str(self.settings.research_registry)
        command=[sys.executable,'-m','unmochon_live.stage4_dynamic','--snapshot',e['output'],
            '--output',str(output),'--package',str(self.root)]
        if self.settings.stage4_tesseract: command+=['--tesseract',str(self.settings.stage4_tesseract)]
        with tempfile.TemporaryFile(mode='w+b') as log:
            proc=subprocess.Popen(command,cwd=self.settings.root,env=env,stdout=log,stderr=log)
            e['child']=proc
            try:
                while proc.poll() is None:
                    self._check(e)
                    try: proc.wait(timeout=.25)
                    except subprocess.TimeoutExpired: pass
                if proc.returncode:
                    log.seek(0); error=log.read()[-1800:].decode('utf-8',errors='replace')
                    raise ResearchFlowError('Stage 4 processing failed: '+error)
            finally:
                if proc.poll() is None: proc.kill();proc.wait()
                e['child']=None
        report=json.loads((output/'stage4_dynamic_summary.json').read_text(encoding='utf-8'))
        e['processed']=str(output)
        self._step(e,'processed',{'processing_root':str(output),
            'artifacts_verified':report['artifacts_verified'],
            'html_artifacts_processed':report['html_artifacts_processed'],
            'pdf_artifacts_processed':report['pdf_artifacts_processed'],
            'pages_needing_extraction_review':report['pages_needing_extraction_review']})

    def _verify(self,e):
        from .evidence_verification import ingest_sources
        from .source_staging import prepare_sources
        review=self.output_root/('staged_'+uuid.uuid4().hex)
        prepare_sources(e['processed'],e['output'],self.root,review); e['review_dir']=str(review)
        if not e['update_consent']['allow_conditional_update']:
            return {'status':'no_usable_evidence','issues':[{'id':'consent','reasons':['conditional_update_not_authorized']}]}
        e['receipt']=ingest_sources(review,e['question'],e['plan'].program,e['plan'].ministry)
        return e['receipt']

    def process(self,ticket,cookie):
        e=self._get(ticket,cookie)
        if e['status'] in ACTIVE: return self.status(ticket,cookie)
        raise ResearchFlowError('Processing runs automatically after approval; no separate job can be started')

    def cancel(self,ticket,cookie):
        e=self._get(ticket,cookie)
        if e['status']=='pending': return self.decide(ticket,cookie,'deny')
        if e['status'] in ACTIVE:
            e['cancel'].set();e['status']='cancelling'
        elif e['status'] in ('review_required','processing_review_needed'):
            e['cancel'].set();self._step(e,'cancelled')
        return self.status(ticket,cookie)

    def review(self,ticket,cookie):
        e=self._get(ticket,cookie)
        if e['status']!='review_required' or not e['review_dir']: raise ResearchFlowError('No staged review available')
        from .evidence_verification import rows
        return {'status':e['status'],'items':rows(Path(e['review_dir'])/'review_items.jsonl'),
            'issues':(e['detail'] or {}).get('issues',[])}

    async def submit_review(self,ticket,cookie,reviewer,decisions):
        e=self._get(ticket,cookie)
        if e['status']!='review_required' or not e['review_dir'] or e['cancel'].is_set():
            raise ResearchFlowError('Only the staged review for this session can be submitted')
        if not e['update_consent']['allow_conditional_update']:
            raise ResearchFlowError('Conditional index update was not authorized')
        self._check(e)
        from .evidence_verification import write,verify_review
        from scripts.stage5_finalize_review import finalize
        directory=Path(e['review_dir'])
        document={'schema_version':1,'request_id':e['request'].request_id,
            'manifest_sha256':(directory/'review_manifest.sha256').read_text().strip(),
            'reviewer':reviewer,'decisions':decisions}
        path=directory/'human_decisions.json'
        if path.exists(): raise ResearchFlowError('A decision record exists; use a fresh reviewed job')
        write(path,document)
        try:
            await asyncio.to_thread(finalize,directory,path,self.root)
            receipt=await asyncio.to_thread(verify_review,directory,e['question'],e['plan'].program,
                e['plan'].ministry,human={d['id']:d for d in decisions})
        except ValueError as ex:
            if not (directory/'content_review_record.json').exists():
                path.unlink(missing_ok=True)
            raise ResearchFlowError(str(ex)) from ex
        e['receipt']=receipt
        if receipt['status']!='verified_eligible':
            self._step(e,'review_required',{'issues':receipt['issues'],'review_available':True})
            return self.status(ticket,cookie)
        self._step(e,'verifying');e['task']=asyncio.create_task(self._pipeline(e,resume=True))
        return self.status(ticket,cookie)

    def status(self,ticket,cookie):
        e=self._get(ticket,cookie)
        if e['status']=='pending' and e['controller'].status(e['request'].request_id)=='expired': e['status']='expired'
        return {'status':e['status'],'request_id':e['request'].request_id,'detail':e['detail'],
            'history':e['history'],'index_writes':e['index_writes'],'generation_at_consent':e['generation'],
            'result':e['result'],'stage5_content_review_required':e['status']=='review_required',
            'stage6_index_approval_required':not bool(e.get('update_consent',{}).get('allow_conditional_update')),
            'can_cancel':e['status'] in ACTIVE or e['status'] in ('pending','review_required')}

    async def close(self):
        tasks=[]
        for e in self.requests.values():
            if e['status'] in ACTIVE:
                e['cancel'].set()
                if e['task']: tasks.append(e['task'])
        if tasks: await asyncio.gather(*tasks,return_exceptions=True)
