"""Offline regression tests for non-destructive current Live + Stage 6 merge."""
import asyncio
from pathlib import Path
from dataclasses import replace
from unmochon_live.config import Settings
from unmochon_live.schemas import Query, RagResult, Evidence
from unmochon_live.orchestrator import Orchestrator
from unmochon_live.stage6_bridge import Stage6Backend, convert_stage6_result, Stage6BridgeError

ROOT = Path(__file__).resolve().parents[1]

def base_settings(backend='stage6'):
    return Settings(root=ROOT, corpus_dir=ROOT/'data/corpus',
                    source_registry=ROOT/'config/sources.json',
                    rag_backend=backend, enable_web_search=False)

def test_original_mode_default_preserved():
    assert Settings.__dataclass_fields__['rag_backend'].default == 'original'
    assert 'original' in Settings.load.__code__.co_consts
    assert hasattr(Evidence(id='c', text='Quote', source_kind='corpus_clause'), 'viewer_url')
    assert hasattr(RagResult(backend='fixture'), 'original_results')
    assert hasattr(RagResult(backend='fixture'), 'intents')

def test_stage6_path_is_separate_and_keeps_original_settings():
    s=base_settings()
    assert s.rag_backend == 'stage6' and s.stage6_python == ''
    assert s.app_env == 'local'
    assert not s.enable_web_search

def test_stage6_live_service_does_not_fetch_any_web():
    class MockWeb:
        called=0
        async def retrieve(self, *args, **kwargs):
            self.called+=1
            raise AssertionError('Must not retrieve without Stage 2/3 consent')
    class MockRag:
        called=0
        async def search(self, *args):
            self.called+=1
            return RagResult(backend='stage6_fixture',generation='verified_test',
                             action='ASK_CLARIFICATION',sufficient=False)
    w=MockWeb();r=MockRag()
    response=asyncio.run(Orchestrator(base_settings(),rag=r,live=w).ask(Query(question='নতুন NID করার নিয়ম কী?')))
    assert response.route == 'LIVE_SERVICE'
    assert response.status == 'NEEDS_VERIFICATION'
    assert response.backend == 'stage6_fixture'
    assert response.action == 'REQUEST_RESEARCH_PERMISSION'
    assert response.research_trigger['program'] == 'nid'
    assert not w.called and r.called == 1

def test_legacy_original_web_path_remains_available_for_opt_in_legacy_backend():
    class StubWeb:
        called=0
        async def retrieve(self, *args, **kwargs):
            self.called+=1
            return [], ['Offline synthetic'], [], 'UNAVAILABLE'
    w=StubWeb()
    response=asyncio.run(Orchestrator(base_settings('corpus'), rag=object(),live=w).ask(Query(question='নতুন NID করার নিয়ম কী?')))
    assert response.route == 'LIVE_SERVICE' and response.status == 'UNAVAILABLE' and w.called==1

def test_original_ui_features_still_in_static_file():
    js=(ROOT/'src/unmochon_live/ui/static/app.js').read_text(encoding='utf-8')
    for symbol in ('function viewerURL','function renderExtracted','function renderConflictCard',
                   'function renderStage6Sources', 'renderStage6Sources(data)', 'evidence.viewer_url'):
        assert symbol in js
    assert 'সবচেয়ে সাম্প্রতিক ডকুমেন্ট অনুযায়ী "বর্তমান" মান প্রযোজ্য' not in js

def test_source_quote_and_hash_metadata_preserved():
    version={'review_group':'H01', 'printed_order_date':'2021-05-03',
             'source_url':'https://example.gov.bd/x.pdf', 'document_subject':'Historical order',
             'clauses':[{'index_id':'s1','source_quote':'Synthetic quote',
                         'source':{'page':4, 'raw_sha256':'a'*64, 'source_url':'https://example.gov.bd/x.pdf'}}]}
    row=convert_stage6_result({'action':'SHOW_SOURCE_VERSIONS','source_versions':[version],
                               'automatic_winner_selected':False,'generation':'fake-stage6'},3)
    assert row.source_versions[0]['clauses'][0]['source']['raw_sha256']=='a'*64
    assert row.evidence[0].page==4 and row.evidence[0].published_at=='2021-05-03'
    assert row.evidence[0].text=='Synthetic quote'
    assert not row.automatic_winner_selected


def test_stage6_disables_legacy_mutating_dataset_update(monkeypatch, tmp_path):
    import sys
    import pytest
    from unmochon_live import cli
    monkeypatch.setattr(cli.Settings, 'load', lambda: base_settings('stage6'))
    monkeypatch.setattr(sys, 'argv', ['unmochon_live', 'update-dataset', str(tmp_path)])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2
