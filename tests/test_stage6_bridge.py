"""Offline contract/safety regression tests; NOT a real-index benchmark."""
import asyncio
from pathlib import Path
from dataclasses import replace
from unmochon_live.config import Settings
from unmochon_live.schemas import Query
from unmochon_live.stage6_bridge import Stage6Backend, convert_stage6_result
from unmochon_live.orchestrator import Orchestrator

ROOT = Path(__file__).resolve().parents[1]


def cfg():
    return Settings(root=ROOT, corpus_dir=ROOT/'data/corpus',
                    source_registry=ROOT/'config/sources.json',
                    rag_backend='stage6', enable_web_search=False)


def version():
    return {'review_group':'H01','printed_order_date':'2021-05-03','document_subject':'Synthetic order',
            'source_url':'https://example.gov.bd/order.pdf', 'clauses':[
                {'proposal_id':'H01-01','index_id':'id-1','source_quote':'Fixture clause only',
                 'source':{'page':2, 'source_url':'https://example.gov.bd/order.pdf'}}]}


def test_versions_preserved_no_winner():
    v=version()
    p={'action':'SHOW_SOURCE_VERSIONS','source_versions':[v,{**v,'review_group':'H02','printed_order_date':'2023-05-04'}],
       'automatic_winner_selected':False,'generation':'reviewed_fake','resolution':'pending_teammate_update_show_all'}
    r=convert_stage6_result(p,3)
    assert r.sufficient and len(r.source_versions)==2 and r.evidence[0].text=='Fixture clause only'
    assert r.automatic_winner_selected is False


def test_research_permission_does_not_execute():
    p={'action':'REQUEST_RESEARCH_PERMISSION','historical_reference_only':[version()],
       'research_trigger':{'permission_granted':False, 'execution_called':False},
       'automatic_winner_selected':False,'generation':'fake'}
    r=convert_stage6_result(p,3)
    assert not r.sufficient and not r.evidence and r.research_trigger['permission_granted'] is False


def test_unknown_or_automatic_winner_rejected():
    import pytest
    from unmochon_live.stage6_bridge import Stage6BridgeError
    with pytest.raises(Stage6BridgeError):convert_stage6_result({'action':'NEW_ACTION'})
    with pytest.raises(Stage6BridgeError):convert_stage6_result({'action':'SHOW_SOURCE_VERSIONS','automatic_winner_selected':True})


def test_offline_orchestrator_uses_stage6_without_web_fallback():
    class MockWeb:
        called=False
        async def retrieve(self,*args,**kwargs):
            self.called=True
            raise AssertionError('Old web fallback must not run')
    web=MockWeb()
    backend=Stage6Backend(cfg(), run_query=lambda q: {
        'action':'REQUEST_RESEARCH_PERMISSION','historical_reference_only':[version()],
        'research_trigger':{'permission_granted':False},'generation':'accepted_test','automatic_winner_selected':False})
    app=Orchestrator(cfg(),rag=backend,live=web)
    result=asyncio.run(app.ask(Query(question='ভিজিএফ ২০২৬ আদেশের তথ্য কী?')))
    assert result.status=='NEEDS_VERIFICATION' and result.route=='RAG'
    assert result.action=='REQUEST_RESEARCH_PERMISSION' and result.generation=='accepted_test'
    assert result.historical_reference_only and not web.called


def test_fail_closed_never_promote_old_backend():
    def crash(_): raise RuntimeError('broken child output')
    r=asyncio.run(Stage6Backend(cfg(),run_query=crash).search('test question',3))
    assert not r.sufficient and not r.evidence and r.backend.startswith('stage6_')


def test_integration_response_contains_all_versions():
    versions=[{**version(),'review_group':'H'+str(i),'printed_order_date':f'202{i}-05-03'} for i in range(1,4)]
    backend=Stage6Backend(cfg(),run_query=lambda q:{'action':'SHOW_SOURCE_VERSIONS',
         'source_versions':versions,'generation':'fake','automatic_winner_selected':False})
    class BlockWeb:
        async def retrieve(self,*a,**kw):raise AssertionError('no automatic crawl')
    response=asyncio.run(Orchestrator(cfg(),rag=backend,live=BlockWeb()).ask(Query(question='ভিজিএফ যোগ্যতার শর্ত কী?')))
    assert response.status=='EVIDENCE_FOUND' and len(response.source_versions)==3


def test_legacy_service_route_preserved_but_no_automatic_web():
    class NoNetwork:
        called=False
        async def retrieve(self,*a,**kw):
            self.called=True
            raise AssertionError('No crawl without fresh consent')
    live=NoNetwork()
    backend=Stage6Backend(cfg(),run_query=lambda _: {'action':'ASK_CLARIFICATION','generation':'verified_test'})
    result=asyncio.run(Orchestrator(cfg(),rag=backend,live=live).ask(Query(question='NID document requirements')))
    assert result.route=='LIVE_SERVICE' and result.status=='NEEDS_VERIFICATION'
    assert not live.called and result.action == 'REQUEST_RESEARCH_PERMISSION'
