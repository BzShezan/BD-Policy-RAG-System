import asyncio
import dataclasses
from pathlib import Path
import httpx
import pytest
from fastapi.testclient import TestClient
from unmochon_live.api import create_app
from unmochon_live.config import Settings
from unmochon_live.orchestrator import Orchestrator
from unmochon_live.rag import CorpusBackend,HttpBackend
from unmochon_live.registry import Registry
from unmochon_live.schemas import Evidence,Query,RagResult
from unmochon_live.web import OfficialFetcher,LiveRetriever,SourceError,verify_url,parse_page,Page

ROOT=Path(__file__).resolve().parents[1]
@pytest.fixture
def settings():
    return Settings(root=ROOT,corpus_dir=ROOT/'data/corpus',source_registry=ROOT/'config/sources.json',enable_web_search=False)

class RagStub:
    def __init__(self,sufficient=True):self.called=0;self.sufficient=sufficient
    async def search(self,q,k):
        self.called+=1
        return RagResult(backend='mock_hybrid',sufficient=self.sufficient,evidence=[Evidence(
            id='test-clause',text='Synthetic test clause only.',source_kind='corpus_clause',document_id='test',page=2)])
class LiveStub:
    def __init__(self):self.called=0
    async def retrieve(self,*a,**kw):
        self.called+=1
        return [],['synthetic offline failure'],['OFFICIAL_PAGES_FETCHED:0'],'UNAVAILABLE'

def run(c):return asyncio.run(c)

@pytest.mark.parametrize('question,expected',[('বয়স্ক ভাতার বয়স কত?','RAG'),('নতুন NID করার নিয়ম কী?','LIVE_SERVICE'),('e-passport documents','LIVE_SERVICE'),('জাতীয় পরিচয়পত্র','LIVE_SERVICE'),('ড্রাইভিং লাইসেন্স','LIVE_SERVICE'),('passport and NID','CLARIFY')])
def test_routes(settings,question,expected):
    rag=RagStub();live=LiveStub();r=run(Orchestrator(settings,rag=rag,live=live).ask(Query(question=question)))
    assert r.route==expected
    if expected!='RAG':assert rag.called==0

def test_explicit_freshness(settings):
    r=run(Orchestrator(settings,rag=RagStub(),live=LiveStub()).ask(Query(question='বর্তমান বয়স্ক ভাতা কত?')))
    assert r.route=='LIVE_SERVICE' and r.status=='UNAVAILABLE'
    assert r.evidence[0].freshness=='not_checked'
    assert r.evidence[0].checked_at is None

def test_gap_escalates(settings):
    live=LiveStub();run(Orchestrator(settings,rag=RagStub(False),live=live).ask(Query(question='কৃষি নীতিমালা কী?')))
    assert live.called==1

@pytest.mark.parametrize('url',['https://nidw.gov.bd.evil.com/a','https://evil.com/?next=nidw.gov.bd','http://nidw.gov.bd/','https://user:secret@nidw.gov.bd/','https://nidw.gov.bd:444/','https://127.0.0.1/','https://evilgov.bd/'])
def test_domain_rejection(url):
    with pytest.raises(SourceError):verify_url(url)

def test_relevant_authority():
    assert verify_url('https://services.nidw.gov.bd/',('nidw.gov.bd',))=='services.nidw.gov.bd'
    with pytest.raises(SourceError):verify_url('https://brta.gov.bd/',('nidw.gov.bd',))

async def resolver(_):pass

def test_redirect_checked_before_following(settings):
    requested=[]
    def handle(request):
        requested.append(str(request.url))
        return httpx.Response(302,headers={'location':'https://evil.example/page'})
    fetch=OfficialFetcher(settings,httpx.MockTransport(handle),resolver)
    with pytest.raises(SourceError):run(fetch.fetch('https://nidw.gov.bd/'))
    assert len(requested)==1

def test_same_authority_redirect_and_hash(settings):
    def handle(request):
        if request.url.path=='/':return httpx.Response(302,headers={'location':'/docs'})
        return httpx.Response(200,headers={'content-type':'text/html; charset=utf-8'},text='<main><p>Synthetic NID application document requirement for test only.</p></main>')
    p=run(OfficialFetcher(settings,httpx.MockTransport(handle),resolver).fetch('https://nidw.gov.bd/',('nidw.gov.bd',)))
    assert p.url.endswith('/docs') and len(p.sha256)==64 and p.checked_at

@pytest.mark.parametrize('content_type,body',[('application/pdf',b'%PDF-test'),('text/html',b'x'*3000)])
def test_type_and_size_limits(settings,content_type,body):
    s=dataclasses.replace(settings,web_max_bytes=1024)
    fetch=OfficialFetcher(s,httpx.MockTransport(lambda _:httpx.Response(200,headers={'content-type':content_type},content=body)),resolver)
    with pytest.raises(SourceError):run(fetch.fetch('https://nidw.gov.bd/'))

def test_private_dns_rejected(settings):
    async def reject(_):raise SourceError('Non-public address rejected')
    called=[]
    fetch=OfficialFetcher(settings,httpx.MockTransport(lambda _:called.append(1)),reject)
    with pytest.raises(SourceError):run(fetch.fetch('https://nidw.gov.bd/'))
    assert not called

def test_script_and_navigation_removed():
    p=parse_page('https://nidw.gov.bd/',b'<nav>application fake navigation</nav><script>secret invented facts</script><main><p>Synthetic application documentation passage used only in tests.</p></main>')
    assert 'fake navigation' not in str(p.passages) and 'invented' not in str(p.passages)

class FakeFetcher:
    def __init__(self,passages):self.passages=passages
    async def fetch(self,url,domains):return Page(url,'test',self.passages,[],'2026-10-07T00:00:00+00:00','a'*64)

def test_live_evidence_is_source_text_not_generated(settings):
    registry=Registry(settings.source_registry)
    text='Synthetic NID application documents passage. Fixture only; not citizen guidance.'
    r=run(LiveRetriever(settings,registry,FakeFetcher([text])).retrieve('NID documents',registry.services[0]))
    assert r[3]=='EVIDENCE_FOUND' and r[0][0].text==text
    assert r[0][0].freshness=='checked_now_version_unknown'

def test_maintenance_is_not_service_evidence(settings):
    registry=Registry(settings.source_registry)
    r=run(LiveRetriever(settings,registry,FakeFetcher(['NID portal unavailable for scheduled maintenance.'])).retrieve('NID documents',registry.services[0]))
    assert r[3]=='NEEDS_VERIFICATION' and not r[0]

@pytest.mark.parametrize('body',[{'schema_version':'2.0','backend':'bad'}, {'backend':'bad','sufficient':True,'evidence':[]}])
def test_invalid_teammate_contract(settings,body):
    r=run(HttpBackend(settings,httpx.MockTransport(lambda _:httpx.Response(200,json=body))).search('test question',3))
    assert not r.sufficient and not r.evidence and r.warnings

def test_http_adapter_preserves_contract_and_key(settings):
    def handle(request):
        assert request.headers['x-api-key']=='rag-secret'
        import json
        assert json.loads(request.content)['schema_version']=='1.0'
        return httpx.Response(200,json={'schema_version':'1.0','backend':'real_hybrid','sufficient':True,'evidence':[{'id':'c','text':'Exact synthetic clause for contract test.','source_kind':'corpus_clause','page':4}]})
    r=run(HttpBackend(dataclasses.replace(settings,rag_api_key='rag-secret'),httpx.MockTransport(handle)).search('test question',3))
    assert r.sufficient and r.evidence[0].page==4 and r.backend=='real_hybrid'

def test_http_failure_no_silent_corpus_fallback(settings):
    r=run(HttpBackend(settings,httpx.MockTransport(lambda _:httpx.Response(503))).search('test question',3))
    assert r.backend=='teammate_http' and not r.evidence

@pytest.fixture(scope='module')
def actual_corpus():
    if not list((ROOT/'data/corpus').glob('*.jsonl*')):
        pytest.skip('Private corpus is not present in this source-only checkout')
    return CorpusBackend(ROOT/'data/corpus')

def test_actual_corpus_clauses_not_mock(actual_corpus):
    r=run(actual_corpus.search('বয়স্ক ভাতার বয়স কত?',3))
    assert r.sufficient and r.backend=='corpus_bm25_baseline'
    assert r.evidence[0].page and r.evidence[0].document_id
    assert r.evidence[0].source_url and r.evidence[0].source_url.startswith('https://dss.gov.bd/')
    assert any('৬৫' in e.text and '৬২' in e.text for e in r.evidence)
    assert all(e.freshness=='not_checked' for e in r.evidence)

def test_corpus_unknown_query(actual_corpus):
    r=run(actual_corpus.search('zzqxnonexistentquasar',3))
    assert not r.sufficient and not r.evidence

def test_api_auth_validation_and_health(settings):
    s=dataclasses.replace(settings,api_key='test-key')
    app=create_app(s,Orchestrator(s,rag=RagStub(),live=LiveStub()))
    with TestClient(app) as client:
        assert client.get('/health/live').status_code==200
        assert client.get('/health/ready').json()['upstream_verified'] is False
        assert client.post('/v1/query',json={'question':'test question'}).status_code==401
        assert client.post('/v1/query',json={'question':'   '},headers={'x-api-key':'test-key'}).status_code==422
        r=client.post('/v1/query',json={'question':'বয়স্ক ভাতার বয়স কত?'},headers={'x-api-key':'test-key'})
        assert r.status_code==200 and r.json()['route']=='RAG'
        assert r.json()['request_id'] and r.json()['elapsed_ms']>=0

def test_production_requires_key(monkeypatch,tmp_path):
    monkeypatch.setenv('UNMOCHON_HOME',str(tmp_path));monkeypatch.setenv('APP_ENV','production');monkeypatch.setenv('API_KEY','')
    with pytest.raises(ValueError,match='Production requires'):Settings.load()

def test_relative_paths_do_not_depend_on_cwd(monkeypatch,tmp_path):
    monkeypatch.setenv('UNMOCHON_HOME',str(ROOT));monkeypatch.chdir(tmp_path);monkeypatch.setenv('APP_ENV','local')
    s=Settings.load();assert s.corpus_dir==ROOT/'data/corpus'

def test_fee_query_does_not_promote_document_requirements(settings):
    registry=Registry(settings.source_registry)
    text='Synthetic passport application documents requirement for test only.'
    r=run(LiveRetriever(settings,registry,FakeFetcher([text])).retrieve('passport fee',registry.services[1]))
    assert r[3]=='NEEDS_VERIFICATION'

def test_http_response_size_budget(settings):
    backend=HttpBackend(settings,httpx.MockTransport(lambda _:httpx.Response(200,content=b'x'*1000001)))
    result=run(backend.search('test question',3))
    assert not result.sufficient and not result.evidence
