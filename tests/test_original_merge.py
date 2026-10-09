import asyncio
import json
import os
import pickle
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

import chromadb
import numpy as np
import pytest
from fastapi.testclient import TestClient
from filelock import FileLock
from rank_bm25 import BM25Okapi

from unmochon_live.api import create_app
from unmochon_live.base_orchestrator import BaseOrchestrator
from unmochon_live.config import Settings
from unmochon_live.datasets import validate_dataset
from unmochon_live.original import OriginalBackend
from unmochon_live.schemas import Query
from scripts.retrieval.tokenize_bn import tokenize
from scripts.retrieval.search import HybridRetriever

ROOT = Path(__file__).resolve().parents[1]

class BengaliOnlyTranslator:
    def to_bengali(self, text):
        if text == "minimum age for old age allowance":
            return "বয়স্ক ভাতার সর্বনিম্ন বয়স কত?"
        return text

class ReplayStoredEmbedding:
    """TEST ONLY: actual stored vector exercises Chroma/HNSW without downloading models.
    This does not validate the encoder or dense semantic quality of a new question.
    """
    def __init__(self, vector): self.vector = vector
    def encode(self, texts, **kwargs): return np.array([self.vector for _ in texts])

@pytest.fixture(scope='module')
def original_engine():
    required = (ROOT/'data/chromedb/chroma.sqlite3', ROOT/'data/bm25_index.pkl', ROOT/'data/doc_metadata.json')
    if not all(path.exists() for path in required):
        pytest.skip('Private original corpus is not present in this source-only checkout')
    c = chromadb.PersistentClient(path=str(ROOT/'data/chromedb')).get_collection('unmochon_clauses')
    got = c.get(where={'ministry':'Social Welfare'}, include=['documents','embeddings'], limit=15000)
    position = next(i for i, text in enumerate(got['documents']) if '৬৫' in text and '৬২' in text)
    retriever = HybridRetriever(model=ReplayStoredEmbedding(got['embeddings'][position]))
    settings = Settings(root=ROOT, corpus_dir=ROOT/'data/corpus', source_registry=ROOT/'config/sources.json')
    return BaseOrchestrator(settings, OriginalBackend(settings, retriever, BengaliOnlyTranslator()))

def test_original_database_and_bm25_are_same(original_engine):
    c = original_engine.backend.original.retriever.collection
    with open(ROOT/'data/bm25_index.pkl','rb') as stream: bm25 = pickle.load(stream)
    assert c.count() == 15019
    assert set(c.get(include=[])['ids']) == set(bm25['ids'])

def test_real_original_clause_metadata_and_original_ner(original_engine):
    result = asyncio.run(original_engine.ask(Query(question='বয়স্ক ভাতার সর্বনিম্ন বয়স কত?', top_k=5)))
    assert result.backend == 'original_hybrid_two_stage' and result.route == 'RAG'
    assert result.status == 'EVIDENCE_FOUND' and result.intents
    assert result.evidence and any(e.extracted for e in result.evidence)
    for e in result.evidence:
        stored = original_engine.backend.original.retriever.collection.get(ids=[e.id], include=['documents','metadatas'])
        assert e.text == stored['documents'][0] and e.metadata == stored['metadatas'][0]
        assert e.metadata['doc_id'] == e.document_id
        assert e.bbox and e.confidence_tier in {'high','medium','low'}
    assert any('৬৫' in e.text and '৬২' in e.text for e in result.evidence)

def test_out_of_scope_does_not_route_to_web_or_invent_clause(original_engine):
    result = asyncio.run(original_engine.ask(Query(question='zzqxnonexistentquasar')))
    assert result.route == 'RAG' and result.status == 'NEEDS_VERIFICATION'
    assert not result.evidence and 'কর্পাস' in result.answer
    assert result.original_results[0]['confidence_tier'] == 'out_of_scope'

def test_english_pipeline_returns_translation_metadata(original_engine):
    result = asyncio.run(original_engine.ask(Query(question='minimum age for old age allowance')))
    assert result.translated == 'বয়স্ক ভাতার সর্বনিম্ন বয়স কত?'
    assert result.evidence

def test_original_exact_pdf_url_and_pdf_routes(tmp_path):
    from UI import app as original
    pdf_root = original.PDF_ROOT
    try:
        original.PDF_ROOT = str(tmp_path)
        (tmp_path/'social_welfare').mkdir()
        (tmp_path/'social_welfare/doc title.pdf').write_bytes(b'%PDF-1.4 synthetic test')
        url = original._viewer_url('c','doc title','Social Welfare',7,'প্রথম বাক্য। বয়স ৬৫ বছর হতে হবে। শেষ বাক্য।',[{'value':'৬৫'}])
        assert '#page=7' in url and '&phrase=true&highlight=true' in url
        assert 'বয়স ৬৫ বছর হতে হবে' in unquote(url)
        assert '/pdf/social_welfare/doc%20title.pdf' in url
        assert original._viewer_url('c','no such doc','Social Welfare',1,'test') is None
    finally: original.PDF_ROOT = pdf_root

def test_original_conflict_algorithm_retained(original_engine):
    original = original_engine.backend.original
    previous = original.DOC_METADATA
    try:
        original.DOC_METADATA = {'old':{'program':'same','date_sortable':'20130101','date_display':'2013'}, 'new':{'program':'same','date_sortable':'20250101','date_display':'2025'}}
        rows = [{'doc_id':'old','extracted':{'extract_age':{'value':'60','confidence':.9}}}, {'doc_id':'new','extracted':{'extract_age':{'value':'65','confidence':.9}}}]
        conflicts = original.detect_conflicts(rows)
        assert len(conflicts) == 1 and conflicts[0]['values'][0]['doc_id'] == 'new'
        assert conflicts[0]['values'][0]['is_current'] is True
        original.DOC_METADATA['new']['program'] = 'different'
        assert not original.detect_conflicts(rows)
    finally: original.DOC_METADATA = previous

def test_live_css_and_templates_identical_to_uploaded_live():
    # This assertion is backed by a hash manifest delivered with the integration.
    import hashlib
    manifest = json.loads((ROOT/'docs/ui_preservation.json').read_text(encoding='utf-8'))
    for relative, expected in manifest.items():
        assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest() == expected

def test_real_engine_api_and_ui_share_original_metadata(original_engine):
    settings = Settings(root=ROOT,corpus_dir=ROOT/'data/corpus',source_registry=ROOT/'config/sources.json',api_key='test-key')
    with TestClient(create_app(settings,original_engine),client=('127.0.0.1',9000)) as client:
        import re
        token = re.search(r'name="ui-csrf" content="([^"]*)"',client.get('/').text).group(1)
        result = client.post('/ui/query',json={'question':'বয়স্ক ভাতার সর্বনিম্ন বয়স কত?'},headers={'x-csrf-token':token})
        assert result.status_code == 200 and result.json()['evidence'][0]['metadata']
        assert client.get('/pdfjs/web/viewer.html').status_code == 200
        assert client.get('/pdfjs/build/pdf.mjs').status_code == 200
        assert client.get('/pdf/../../.env').status_code == 404

def valid_row(text=None):
    return {'clause_id':'synthetic-new_C0001','doc_id':'synthetic-new','page_number':1,'text':text or 'This synthetic agriculture policy clause is for dataset tests only and contains sufficient clean text for original quality filtering.','quality_score':1.0,'layout_label':'CLAUSE','source_url':'https://example.gov.bd/test','circular_date':'20261009','bbox':[1,2,3,4], 'extra_metadata':{'retain':'all fields'}}

def test_dataset_validation_before_any_write(tmp_path):
    with pytest.raises(ValueError): validate_dataset(tmp_path)
    path = tmp_path/'Agriculture_clauses.jsonl'
    path.write_text('{invalid',encoding='utf-8')
    with pytest.raises(ValueError,match='invalid JSON'): validate_dataset(tmp_path)
    path.write_text(json.dumps(valid_row())+'\n'+json.dumps(valid_row()),encoding='utf-8')
    with pytest.raises(ValueError,match='duplicate'): validate_dataset(tmp_path)
    row = valid_row(); row['page_number'] = 0
    path.write_text(json.dumps(row),encoding='utf-8')
    with pytest.raises(ValueError,match='page_number'): validate_dataset(tmp_path)

# Execute worker in its own process to test REAL Chroma upserts/BM25; use deterministic test vectors only.
WORKER = r"""
import os,sys,json
from pathlib import Path
import numpy as np
from unmochon_live.dataset_worker import prepare
class TestModel:
 def encode(self,texts,**kwargs):return np.array([[.1,.2,.3,.4] for _ in texts])
report=prepare(sys.argv[1],sys.argv[2] if len(sys.argv)>2 else None,model=TestModel())
Path(os.environ['UPDATE_REPORT_PATH']).write_text(json.dumps(report))
"""

def test_incremental_real_database_update_and_idempotency(tmp_path):
    root = tmp_path/'project'; data = root/'data'; data.mkdir(parents=True)
    db = data/'chromedb'; index = data/'bm25_index.pkl'; meta = data/'doc_metadata.json'
    # Seed in separate process so there are no open handles during offline commit.
    seed = """import chromadb,pickle,sys
from rank_bm25 import BM25Okapi
from scripts.retrieval.tokenize_bn import tokenize
c=chromadb.PersistentClient(path=sys.argv[1]).create_collection('unmochon_clauses',metadata={'hnsw:space':'cosine'})
c.add(ids=['old'],documents=['old agriculture text for fixture'],metadatas=[{'doc_id':'old','ministry':'Agriculture','page_number':1,'circular_date':'20140101'}],embeddings=[[.1,.2,.3,.4]])
pickle.dump({'bm25':BM25Okapi([tokenize('old agriculture text for fixture')]),'ids':['old']},open(sys.argv[2],'wb'))
"""
    env = {**os.environ,'PYTHONPATH':str(ROOT/'src')+os.pathsep+str(ROOT), 'UNMOCHON_HOME':str(root)}
    subprocess.run([sys.executable,'-c',seed,str(db),str(index)],env=env,check=True)
    meta.write_text('{"old":{"program":"preserved","custom":"keep"}}')
    dataset = tmp_path/'incoming'; dataset.mkdir()
    rows = dataset/'Agriculture_clauses.jsonl'; rows.write_text(json.dumps(valid_row())+'\n')
    incoming_meta = dataset/'doc_metadata.json'; incoming_meta.write_text('{"synthetic-new":{"display_name":"New test document","source_url":"https://example.gov.bd/test","program":"new"}}')
    test_runner = r"""
import sys,json,subprocess
from unmochon_live.datasets import update_dataset
def worker(command,**kwargs):
 subprocess.run([sys.executable,'-c',sys.argv[3],*command[3:]],**kwargs)
print('REPORT:'+json.dumps(update_dataset(sys.argv[1],sys.argv[2],worker=worker)))
"""
    def run_update():
        process = subprocess.run([sys.executable,'-c',test_runner,str(dataset),str(incoming_meta),WORKER],env=env,check=False,capture_output=True,text=True)
        assert process.returncode == 0, process.stderr + process.stdout
        return json.loads(next(line[7:] for line in process.stdout.splitlines() if line.startswith('REPORT:')))
    first = run_update()
    assert first['before']==1 and first['after']==2 and first['added']==1 and first['bm25_ids_match']
    second = run_update()
    assert second['after']==2 and second['added']==0 and second['updated']==0 and second['unchanged']==1
    assert json.loads(meta.read_text())['old']['custom']=='keep'
    assert (data/'processed_jsonl/Agriculture_clauses.jsonl').exists()
    check = r"""
import chromadb,sys,json
c=chromadb.PersistentClient(path=sys.argv[1]).get_collection('unmochon_clauses')
r=c.get(ids=['synthetic-new_C0001'],include=['documents','metadatas'])
assert c.count()==2 and r['metadatas'][0]['circular_date']=='20261009'
assert json.loads(r['metadatas'][0]['extra_metadata'])['retain']=='all fields'
assert json.loads(r['metadatas'][0]['original_chunk_json'])['bbox']==[1,2,3,4]
from chatbot.scripts.verified_lookup import get_verified_clause
assert get_verified_clause('Agriculture','synthetic-new',clause_id='synthetic-new_C0001')
"""
    subprocess.run([sys.executable,'-c',check,str(db)],env=env,check=True)
    # Invalid staged worker cannot change the original DB/index/metadata.
    import hashlib
    before = {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in data.rglob('*') if p.is_file()}
    failed_runner = """import sys,subprocess
from unmochon_live.datasets import update_dataset
def fail(*args,**kw):raise RuntimeError('synthetic failure')
try:update_dataset(sys.argv[1],worker=fail)
except RuntimeError:pass
else:raise AssertionError('expected failure')
"""
    subprocess.run([sys.executable,'-c',failed_runner,str(dataset)],env=env,check=True)
    after = {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in data.rglob('*') if p.is_file()}
    assert before == after
    with FileLock(str(root/'.database.lock')):
        result = subprocess.run([sys.executable,'-c',failed_runner,str(dataset)],env=env,capture_output=True,text=True)
        assert result.returncode==0


def test_original_ocr_digital_pdf_and_chunk_bounding_boxes(tmp_path):
    fitz = pytest.importorskip('fitz')
    from scripts.ocr_pipeline.ocr import extract_page_text
    from scripts.ocr_pipeline.chunker import chunk_text
    from layout_analysis.scripts.layout_pipeline.heuristics import apply_header_footer_rules
    document = fitz.open(); page = document.new_page()
    page.insert_text((72,120), '1. Agriculture policy requires original documents and verified applicant information.')
    pdf = tmp_path / 'digital.pdf'; document.save(pdf); document.close()
    with fitz.open(pdf) as doc:
        result = extract_page_text(doc[0])
        assert result['ocr_method'] == 'digital' and result['quality'] >= .6
        assert result['word_boxes']
        chunks, counter = chunk_text(result['text'], 'test-doc', 1, result['ocr_method'], result['quality'], False, 'Agriculture', result['word_boxes'])
        assert chunks and chunks[0]['bbox'] and chunks[0]['clause_id'] == 'test-doc_C0001'
        assert chunks[0]['page_number'] == 1 and counter == 2
    assert apply_header_footer_rules([1,2,30,50],1000,'short text') == 'HEADER'
    assert apply_header_footer_rules([1,910,30,950],1000,'short text') == 'FOOTER'
