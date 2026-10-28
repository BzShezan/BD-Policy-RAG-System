"""Offline end-to-end integration. Real Stage3/4/5/6, Chroma and BM25.
Only HTTPS responses and the missing embedding model are synthetic test fixtures.
"""
import asyncio
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from unmochon_live.config import Settings
from unmochon_live.schemas import Query,Response
from unmochon_live.stage6_bridge import Stage6Backend
from unmochon_live.orchestrator import Orchestrator
from unmochon_live.research_flow import ResearchFlow,ResearchFlowError
from unmochon_live.runtime import load_stage4,load_stage6
from unmochon_live.controlled_update import ControlledUpdater,compare_switch
from unmochon_live.evidence_verification import validate_receipt

ROOT=Path(__file__).resolve().parents[1]
S4=ROOT/'reference_pipelines/stage4'
S6=ROOT/'reference_pipelines/stage6'
QUESTION='How to apply for NID card?'
# Deliberately fictional process; never used as government guidance.
TEXT=('Date: 19/10/2026. SYNTHETIC TEST ONLY. NID national identity application process. '
      'First fill in the application form with fictional test data. '
      'Then submit the form to the fictional test office and collect a test receipt. '
      'This is generated solely to exercise the integration; it is not citizen guidance.')


def run_child(mode,spec,tmp):
    path=tmp/(mode+'_'+str(hashlib.sha256(json.dumps(spec,sort_keys=True).encode()).hexdigest())[:8]+'.json')
    path.write_text(json.dumps(spec),encoding='utf-8')
    env=dict(os.environ,PYTHONPATH=str(ROOT/'src')+os.pathsep+str(ROOT),PYTHONUTF8='1',PYTHONIOENCODING='utf-8')
    child=subprocess.run([sys.executable,str(ROOT/'tests/agentic_fixture_worker.py'),mode,str(path)],
        env=env,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=120)
    assert child.returncode==0, child.stdout[-1500:]+child.stderr[-3000:]


@pytest.fixture
def runtime(tmp_path,monkeypatch):
    load_stage4(S4);load_stage6(S6)
    config=Settings(root=ROOT,corpus_dir=ROOT/'data/corpus',source_registry=ROOT/'config/sources.json',
        rag_backend='stage6',enable_web_search=False,stage4_package=S4,stage6_package=S6,
        research_registry=ROOT/'config/research_sources.json',research_output_root=tmp_path/'research',
        stage6_workspace=tmp_path/'workspace')
    spec={'package':str(S6),'stage4_package':str(S4),'registry':str(config.research_registry),
        'workspace':str(config.stage6_workspace),'project':str(ROOT),
        'fixture_evidence_data':str(tmp_path/'evidence_data')}
    run_child('prepare',spec,tmp_path);run_child('seal',spec,tmp_path)
    monkeypatch.setenv('STAGE2_EVIDENCE_DATA',str(tmp_path/'evidence_data'))
    from stage6.generations import active,generation
    from stage6.common import tree
    original=active(config.stage6_workspace)
    hashes=tree(generation(config.stage6_workspace,original['generation']))
    yield config,spec,original,hashes
    assert tree(generation(config.stage6_workspace,original['generation']))==hashes


class FixtureUpdater(ControlledUpdater):
    def _run(self,mode,specfile,entry):
        run_child(mode,json.loads(Path(specfile).read_text(encoding='utf-8')),Path(entry['review_dir']))


class FixtureBackend(Stage6Backend):
    def _run_query(self,question):
        from stage6.generations import active,generation,verify_generation
        pointer=active(self.workspace)
        with tempfile.TemporaryDirectory(prefix='unmochon_test_query_') as directory:
            directory=Path(directory);snapshot=directory/'index'
            source=generation(self.workspace,pointer['generation'])
            shutil.copytree(source/'index',snapshot)
            output=directory/'result.json'
            spec={'package':str(S6),'stage4_package':str(S4),'registry':str(ROOT/'config/research_sources.json'),
                'workspace':str(self.workspace),'project':str(ROOT),'question':question,'output':str(output),
                'snapshot':str(snapshot),'pointer':pointer,'evidence_root':str(source/'evidence')}
            run_child('query-copy',spec,directory)
            result=json.loads(output.read_text(encoding='utf-8'))
        verify_generation(self.workspace,pointer['generation'],pointer['manifest_sha256'])
        return result


def transport(pdf=False,bad=False):
    from stage3.transport import Fixture,FixtureTransport
    body=('<html><title>Synthetic NID process</title><main><h1>NID application</h1><p>'+TEXT+
          ('\ufffd' if bad else '')+'</p>'+
          ('<a href="https://www.nidw.gov.bd/test-process.pdf">NID application form process PDF</a>' if pdf else '')+
          '</main></html>').encode()
    fixtures={
        'https://www.nidw.gov.bd/robots.txt':Fixture(404,b'','text/plain'),
        'https://ecs.gov.bd/robots.txt':Fixture(404,b'','text/plain'),
        'https://www.nidw.gov.bd/enroll_obtaining.php':Fixture(200,body),
        'https://ecs.gov.bd/':Fixture(200,b'<html><main>Unrelated synthetic election news.</main></html>')}
    if pdf:
        import pymupdf
        doc=pymupdf.open();page=doc.new_page();page.insert_textbox(pymupdf.Rect(40,50,550,750),TEXT,fontsize=12)
        fixtures['https://www.nidw.gov.bd/test-process.pdf']=Fixture(200,doc.tobytes(),'application/pdf');doc.close()
    return FixtureTransport(fixtures)


def make_flow(config,tx,*,updater=None,execute=None):
    async def never_web(*a,**k):raise AssertionError('Legacy web must never run')
    engine=Orchestrator(config,rag=FixtureBackend(config),live=SimpleNamespace(retrieve=never_web))
    flow=ResearchFlow(config,execute=execute or engine.ask,updater=updater or FixtureUpdater(config),transport_factory=lambda:tx)
    return flow,engine


def test_full_consented_html_pdf_to_pair_to_original_requery(runtime):
    config,spec,before,hashes=runtime
    tx=transport(pdf=True)
    async def scenario():
        flow,engine=make_flow(config,tx)
        existing=await engine.ask(Query(question='২০১৩ সালের বয়স্ক ভাতায় পুরুষ ও মহিলার বয়স কত?'))
        assert existing.status=='EVIDENCE_FOUND' and tx.calls==0
        response=await engine.ask(Query(question=QUESTION))
        assert response.action=='REQUEST_RESEARCH_PERMISSION' and tx.calls==0
        offer=flow.offer(response,'browser');assert offer['ministry']=='Election Commission'
        assert flow.decide(offer['ticket'],'browser','approve',True)['status']=='crawling'
        e=flow.requests[offer['ticket']]
        with pytest.raises(ResearchFlowError):flow.decide(offer['ticket'],'browser','approve',True)
        await e['task']
        status=flow.status(offer['ticket'],'browser')
        assert status['status']=='answer_ready',status
        assert status['index_writes']>=2 and status['result']['question']==QUESTION
        assert status['result']['generation']!=before['generation']
        assert 'First fill in the application form with fictional test data.' in status['result']['answer']
        assert status['result']['overview']['method']=='retrieved_source_sentences'
        assert status['result']['research_offer'] is None
        assert {'crawling','processing','verifying','updating','activating','requerying','answer_ready'} <= {h['status'] for h in status['history']}
        receipt=validate_receipt(Path(e['review_dir'])/'verification_receipt.json')
        assert any(r['metadata']['page_number']==1 for r in receipt['index_items'])
        from stage6.generations import active,generation
        target=generation(config.stage6_workspace,active(config.stage6_workspace)['generation'])
        reopened=json.loads((target/'evidence/reopen_validation.json').read_text(encoding='utf-8'))
        assert reopened['passed'] and reopened['dense_queries_executed']>=2
        assert list((target/'evidence/research_sources').glob('*.pdf'))
        # Later independent questions now find stored evidence; no repeat crawl.
        calls=tx.calls
        again=await engine.ask(Query(question=QUESTION))
        assert again.status=='EVIDENCE_FOUND' and tx.calls==calls
    asyncio.run(scenario())


@pytest.mark.parametrize('mode',['deny','bad_text','build_fail','requery_fail','cancel','no_update_consent','deadline','reopen_fail'])
def test_failures_keep_previous_pair(runtime,mode):
    config,spec,before,hashes=runtime
    tx=transport(bad=mode=='bad_text')
    if mode=='unclear_date':
        from stage3.transport import Fixture
        for url,fixture in list(tx.fixtures.items()):
            tx.fixtures[url]=Fixture(fixture.status,fixture.body.replace(b'Date: 19/10/2026. ',b''),fixture.content_type)
    class FailingUpdater(FixtureUpdater):
        def build(self,*args):raise ValueError('Injected candidate failure')
    class ReopenFailure(FixtureUpdater):
        def _run(self,mode,specfile,entry):
            if mode=='reopen':raise ValueError('Injected fresh-process verification failure')
            return super()._run(mode,specfile,entry)
    async def fail_query(query):raise ValueError('Injected original re-query failure')
    async def scenario():
        flow,engine=make_flow(config,tx,updater=FailingUpdater(config) if mode=='build_fail' else
                              ReopenFailure(config) if mode=='reopen_fail' else None,
                              execute=fail_query if mode=='requery_fail' else None)
        response=await engine.ask(Query(question=QUESTION));offer=flow.offer(response,'browser')
        if mode=='deny':
            assert flow.decide(offer['ticket'],'browser','deny')['network_calls']==0
            assert tx.calls==0;return
        flow.decide(offer['ticket'],'browser','approve',mode!='no_update_consent')
        if mode=='cancel':flow.cancel(offer['ticket'],'browser')
        e=flow.requests[offer['ticket']]
        if mode=='deadline':e['deadline']=0
        await e['task']
        state=flow.status(offer['ticket'],'browser')
        assert state['index_writes']==0
        if mode in ('bad_text','no_update_consent'):assert state['status']=='no_usable_evidence',state
        elif mode=='cancel':assert state['status']=='cancelled',state
        else:assert state['status']=='failed',state
        from stage6.generations import active
        assert active(config.stage6_workspace)['generation']==before['generation']
        if mode=='requery_fail':assert state['detail']['rollback_performed']
    asyncio.run(scenario())


def test_registry_and_consent_scope_fail_closed(runtime):
    config,*_=runtime
    from unmochon_live.research_registry import make_registry,match_scope
    from stage3.scope import in_scope
    registry=make_registry(config.research_registry)
    assert len(registry.entries)==7
    plan=registry.make_plan(QUESTION,'nid','Election Commission','test gap')
    assert in_scope('https://www.nidw.gov.bd/enroll_obtaining.php',plan)
    for url in ['https://nidw.gov.bd.evil.test/','https://example.gov.bd/','https://asset.ecs.gov.bd/','http://ecs.gov.bd/']:
        assert not in_scope(url,plan)
    assert match_scope('How to apply for passport?',config.research_registry)==[('passport','Department of Immigration and Passports')]
    flow,_=make_flow(config,transport())
    r=Response(request_id='fixture',question=QUESTION,route='LIVE_SERVICE',status='NEEDS_VERIFICATION',
        answer='test',backend='stage6_fixture',elapsed_ms=1,action='REQUEST_RESEARCH_PERMISSION',generation='reviewed_c02a1b74041d',
        research_trigger={'program':'nid','ministry':'Election Commission','reason':'fixture gap'})
    offer=flow.offer(r,'a')
    with pytest.raises(ResearchFlowError):flow.decide(offer['ticket'],'b','approve',True)
    e=flow.requests[offer['ticket']];e['controller']._clock=lambda:e['request'].expires_at+1
    assert flow.status(offer['ticket'],'a')['status']=='expired'
    assert not config.research_output_root.exists()


def test_undated_ocr_content_indexes_without_human_review(runtime):
    config,spec,before,hashes=runtime
    tx=transport(pdf=True)
    from stage3.transport import Fixture
    for url,fixture in list(tx.fixtures.items()):
        if 'text/html' in fixture.content_type:
            tx.fixtures[url]=Fixture(fixture.status,fixture.body.replace(b'Date: 19/10/2026. ',b''),fixture.content_type)
    async def scenario():
        flow,engine=make_flow(config,tx)
        real_process=flow._process
        def simulated_ocr_output(entry):
            real_process(entry)
            # Captured successful OCR text fixture; no OCR accuracy claim.
            for path in (Path(entry['processed'])/'pdf/pages').glob('*.json'):
                doc=json.loads(path.read_text(encoding='utf-8'));doc['route']='bengali_ocr_fallback'
                path.write_text(json.dumps(doc),encoding='utf-8')
        flow._process=simulated_ocr_output
        offer=flow.offer(await engine.ask(Query(question=QUESTION)),'browser')
        flow.decide(offer['ticket'],'browser','approve',True)
        entry=flow.requests[offer['ticket']];await entry['task']
        state=flow.status(offer['ticket'],'browser')
        assert state['status']=='answer_ready',state
        receipt=validate_receipt(Path(entry['review_dir'])/'verification_receipt.json')
        assert receipt['human_review_required'] is False
        assert receipt['human_decisions']=={}
        assert any(not r['metadata']['date_value'] for r in receipt['index_items'])
        assert any(r['metadata']['extraction_route']=='bengali_ocr_fallback' for r in receipt['index_items'])
        assert not (Path(entry['review_dir'])/'content_review_record.json').exists()
        assert 'review_required' not in [h['status'] for h in state['history']]
    asyncio.run(scenario())


def test_all_readable_crawled_pages_stored_and_original_answers_need_no_pilot_catalog(runtime,monkeypatch):
    config,spec,before,hashes=runtime
    tx=transport()
    from stage3.transport import Fixture
    news='A synthetic election-office announcement with unrelated descriptive text mentioning a captcha field. This page must be stored as a source chunk even though it does not answer the application process question.'
    tx.fixtures['https://ecs.gov.bd/']=Fixture(200,('<html><main>'+news+'</main></html>').encode())
    monkeypatch.setenv('STAGE2_EVIDENCE_DATA',str(config.research_output_root/'missing-pilot-catalog'))
    async def scenario():
        flow,engine=make_flow(config,tx)
        old=await engine.ask(Query(question='২০১৩ সালের বয়স্ক ভাতায় পুরুষ ও মহিলার বয়স কত?'))
        assert old.status=='EVIDENCE_FOUND' and '৬৫' in old.answer and '৬২' in old.answer
        assert old.evidence[0].extracted and tx.calls==0
        offer=flow.offer(await engine.ask(Query(question=QUESTION)),'browser')
        flow.decide(offer['ticket'],'browser','approve',True)
        entry=flow.requests[offer['ticket']];await entry['task']
        state=flow.status(offer['ticket'],'browser')
        assert state['status']=='answer_ready',state
        receipt=validate_receipt(Path(entry['review_dir'])/'verification_receipt.json')
        assert any(news in row['text'] for row in receipt['index_items'])
        assert all(row['metadata']['agentic_ingested'] and not row['metadata']['agentic_verified'] for row in receipt['index_items'])
        assert not any('review' in h['status'] for h in state['history'])
        # Newly gathered application instructions must not answer a fee query.
        fees=await engine.ask(Query(question='What is the NID fee?'))
        assert fees.action=='REQUEST_RESEARCH_PERMISSION' and fees.status!='EVIDENCE_FOUND'
    asyncio.run(scenario())


def test_readable_sources_remain_indexed_even_if_they_do_not_answer(runtime):
    config,spec,before,hashes=runtime
    tx=transport()
    from stage3.transport import Fixture
    text='Synthetic election office announcement. This is a readable unrelated notice with no application process or requested procedural instructions.'
    for url,fixture in list(tx.fixtures.items()):
        if fixture.status==200:
            tx.fixtures[url]=Fixture(200,('<html><main>'+text+'</main></html>').encode())
    async def scenario():
        flow,engine=make_flow(config,tx)
        offer=flow.offer(await engine.ask(Query(question=QUESTION)),'browser')
        flow.decide(offer['ticket'],'browser','approve',True)
        entry=flow.requests[offer['ticket']];await entry['task']
        state=flow.status(offer['ticket'],'browser')
        assert state['status']=='research_complete',state
        assert state['index_writes']>0 and state['result']['status']=='NEEDS_VERIFICATION'
        assert state['result']['action']=='RESEARCH_COMPLETE_NO_ANSWER'
        assert state['result']['evidence'] and state['result']['evidence'][0]['source_url']
        receipt=validate_receipt(Path(entry['review_dir'])/'verification_receipt.json')
        assert any(len(json.loads(r['metadata']['source_urls']))==2 for r in receipt['index_items'])
        from stage6.generations import active
        assert active(config.stage6_workspace)['generation']!=before['generation']
    asyncio.run(scenario())


def test_repeat_capture_deduplicates_without_switching_the_pair(runtime):
    config,spec,before,hashes=runtime
    async def scenario():
        flow,engine=make_flow(config,transport())
        missing=await engine.ask(Query(question=QUESTION))
        offer=flow.offer(missing,'browser')
        flow.decide(offer['ticket'],'browser','approve',True)
        await flow.requests[offer['ticket']]['task']
        first=flow.status(offer['ticket'],'browser')
        assert first['status']=='answer_ready',first
        from stage6.generations import active
        pointer=active(config.stage6_workspace)
        # Explicitly exercise a second fresh consent, as opposed to the normal
        # repeat-query path which immediately finds the stored answer.
        another,_=make_flow(config,transport())
        offer2=another.offer(missing.model_copy(update={'generation':pointer['generation']}),'browser')
        another.decide(offer2['ticket'],'browser','approve',True)
        e=another.requests[offer2['ticket']];await e['task']
        state=another.status(offer2['ticket'],'browser')
        assert state['status']=='answer_ready',state
        assert state['index_writes']==0 and e['built']['noop']
        assert active(config.stage6_workspace)==pointer
    asyncio.run(scenario())


def test_http_permission_progress_answer_and_verified_pdf(runtime,monkeypatch):
    config,spec,before,hashes=runtime
    from unmochon_live.api import create_app
    import unmochon_live.research_flow as module
    import re
    tx=transport(pdf=True)
    flow,engine=make_flow(config,tx)
    def factory(settings,execute):
        flow.execute=execute
        return flow
    monkeypatch.setattr(module,'ResearchFlow',factory)
    with TestClient(create_app(config,engine),client=('127.0.0.1',9001)) as c:
        shell=c.get('/results')
        token=re.search('name="ui-csrf" content="([^"]+)"',shell.text).group(1)
        headers={'X-CSRF-Token':token}
        body=c.post('/ui/query',headers=headers,json={'question':QUESTION}).json()
        ticket=body['research_offer']['ticket']
        assert tx.calls==0
        assert c.post('/ui/research/decision',json={'ticket':ticket,'decision':'approve'}).status_code==403
        assert c.post('/ui/research/decision',headers=headers,json={'ticket':ticket,'decision':'approve',
            'allow_conditional_update':True}).status_code==200
        async def complete():await flow.requests[ticket]['task']
        c.portal.call(complete)
        state=c.post('/ui/research/status',headers=headers,json={'ticket':ticket}).json()
        assert state['status']=='answer_ready',state
        card=next(e for e in state['result']['evidence'] if e['page']==1)
        assert '/verified-pdf/' in card['viewer_url']
        sha=card['metadata']['source_raw_sha256']
        pdf=c.get('/verified-pdf/'+sha+'.pdf')
        assert pdf.status_code==200 and hashlib.sha256(pdf.content).hexdigest()==sha
        assert c.get('/verified-pdf/'+'f'*64+'.pdf').status_code==404


def test_partial_dense_writer_failure_is_never_sealed_or_activated(runtime,tmp_path):
    config,spec,before,hashes=runtime
    run_child('partial-failure',spec,tmp_path)
    result=json.loads((config.stage6_workspace/'partial_failure_result.json').read_text(encoding='utf-8'))
    assert result['passed'] and result['partial_dense_items']==32
    assert result['active_generation']==before['generation']


def test_stale_concurrent_pointer_rejected_and_damaged_candidate_rollback(runtime):
    config,spec,before,hashes=runtime
    from stage6.generations import generation,seal,active
    base=generation(config.stage6_workspace,before['generation'])
    for name in ('candidate_one','candidate_two'):
        target=generation(config.stage6_workspace,name)
        shutil.copytree(base/'index',target/'index')
        seal(config.stage6_workspace,name,{'role':'candidate','validation_passed':True,
            'benchmark_passed':True,'restart_check_passed':True})
    current=compare_switch(config.stage6_workspace,before,'candidate_one')
    with pytest.raises(ValueError,match='changed'):
        compare_switch(config.stage6_workspace,before,'candidate_two')
    damaged=generation(config.stage6_workspace,'candidate_one')/'index/build_report.json'
    damaged.write_text('damaged candidate fixture',encoding='utf-8')
    with pytest.raises(ValueError):active(config.stage6_workspace)
    env=dict(os.environ,PYTHONPATH=str(ROOT/'src')+os.pathsep+str(ROOT),
        RAG_BACKEND='stage6',APP_ENV='local',STAGE4_PACKAGE=str(S4),STAGE6_PACKAGE=str(S6),
        STAGE6_WORKSPACE=str(config.stage6_workspace),RESEARCH_SOURCE_REGISTRY=str(config.research_registry))
    command=[sys.executable,str(ROOT/'scripts/agentic_diagnostic.py'),'--rollback']
    result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=30)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)['status']=='EXPLICIT_PAIRED_ROLLBACK_COMPLETE'
    assert active(config.stage6_workspace)['generation']==before['generation']


def test_source_bytes_tampering_blocks_stage5_to_stage6(runtime):
    config,spec,before,hashes=runtime
    class StopAtBuild(FixtureUpdater):
        def build(self,*a):raise ValueError('Stop before any candidate write')
    async def scenario():
        flow,engine=make_flow(config,transport(),updater=StopAtBuild(config))
        offer=flow.offer(await engine.ask(Query(question=QUESTION)),'browser')
        flow.decide(offer['ticket'],'browser','approve',True)
        entry=flow.requests[offer['ticket']];await entry['task']
        receipt=Path(entry['review_dir'])/'verification_receipt.json'
        assert validate_receipt(receipt)['status']=='verified_eligible'
        raw=next(Path(entry['output']).glob('runs/*/raw/*.html'))
        raw.write_bytes(raw.read_bytes()+b'tampered')
        with pytest.raises(ValueError):validate_receipt(receipt)
    asyncio.run(scenario())


def test_genuine_oos_invalid_dates_and_infrastructure_error_never_crawl():
    load_stage4(S4)
    from stage2.evaluator import evaluate
    from unmochon_live.schemas import RagResult
    settings=Settings(root=ROOT,corpus_dir=ROOT/'data/corpus',source_registry=ROOT/'config/sources.json',
        rag_backend='stage6',enable_web_search=False)
    class NoWeb:
        async def retrieve(self,*a,**k):raise AssertionError('No permission; no crawl')
    class FixedRag:
        def __init__(self,result):self.result=result
        async def search(self,*a):return self.result
    async def scenario():
        assessment=evaluate('Write a birthday greeting',[])
        assert assessment.action=='DECLINE_OUT_OF_DOMAIN'
        engine=Orchestrator(settings,rag=FixedRag(RagResult(backend='stage6_fixture',
            action=assessment.action,generation='verified_fixture')),live=NoWeb())
        response=await engine.ask(Query(question='Write a birthday greeting'))
        assert response.action=='DECLINE_OUT_OF_DOMAIN' and response.research_offer is None
        engine=Orchestrator(settings,rag=FixedRag(RagResult(backend='stage6_fixture',action='ASK_CLARIFICATION',
            reason='multiple_versions_or_dates',generation='verified_fixture')),live=NoWeb())
        response=await engine.ask(Query(question='NID 2025 and 2026 application rules'))
        assert response.status=='CLARIFICATION_REQUIRED' and response.research_offer is None
        engine=Orchestrator(settings,rag=FixedRag(RagResult(backend='stage6_fixture',
            reason='Failed closed: verified query could not be completed')),live=NoWeb())
        response=await engine.ask(Query(question=QUESTION))
        assert response.action is None and response.generation is None and response.research_offer is None
    asyncio.run(scenario())


def test_verified_bangla_query_under_windows_legacy_text_default(runtime,monkeypatch):
    """Regression: CP1252 must not break UTF8 JSON returned by the query child."""
    config,spec,before,hashes=runtime
    original_read=Path.read_text
    def cp1252_default(path,encoding=None,errors=None):
        return original_read(path,encoding=encoding or 'cp1252',errors=errors)
    monkeypatch.setattr(Path,'read_text',cp1252_default)
    result=asyncio.run(FixtureBackend(config).search('২০১৩ সালের বয়স্ক ভাতায় পুরুষ ও মহিলার বয়স কত?',3))
    assert result.sufficient and result.generation==before['generation'],result.model_dump()
    assert any('৬৫' in item.text and '৬২' in item.text for item in result.evidence),result.model_dump()
