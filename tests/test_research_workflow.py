"""Offline tests. No live government requests, no index writes."""
import asyncio
from dataclasses import replace
from pathlib import Path
import os
from types import SimpleNamespace

import pytest
from unmochon_live.config import Settings
from unmochon_live.research_flow import ResearchFlow, ResearchFlowError

APP = Path(__file__).resolve().parents[1]
STAGE4 = Path(os.getenv('STAGE4_PACKAGE', str(APP.parent / 'Unmochon_Stage4_Evidence_Processing')))
if not STAGE4.exists():
    STAGE4 = APP / 'reference_pipelines/stage4'


def config(tmp_path):
    if not STAGE4.is_dir():
        pytest.skip('Stage 3/4 package absent; configure STAGE4_PACKAGE before live research')
    return Settings(root=APP, corpus_dir=APP/'data/corpus', source_registry=APP/'config/sources.json',
                    rag_backend='stage6', app_env='local', stage4_package=STAGE4,
                    research_output_root=tmp_path/'research_runs')


def response():
    return SimpleNamespace(action='REQUEST_RESEARCH_PERMISSION', generation='reviewed_test',
                           question='৩ মে ২০২৬-এর ভিজিএফ বরাদ্দ কত?',
                           research_trigger={'ministry':'Disaster Management',
                                             'program':'vgf', 'reason':'Local top3 insufficient'})


def test_missing_trigger_never_requests_permission(tmp_path):
    flow = ResearchFlow(config(tmp_path))
    value = response()
    value.research_trigger = {'ministry':'Disaster Management'}
    result = flow.offer(value, 'cookie')
    assert result['available'] is False and flow.requests == {}
    value = response(); value.action='SHOW_SOURCE_VERSIONS'
    assert flow.offer(value,'cookie') is None
    assert not (tmp_path/'research_runs').exists()


def test_offline_scoped_offer_and_deny(tmp_path):
    flow = ResearchFlow(config(tmp_path))
    offer = flow.offer(response(), 'session-cookie-a')
    assert offer['available'] and offer['max_http_requests'] <= 12
    assert offer['ministry']=='Disaster Management' and offer['program']=='vgf'
    assert offer['hosts'] and all(host.endswith('.gov.bd') for host in offer['hosts'])
    assert flow.status(offer['ticket'],'session-cookie-a')['status']=='pending'
    assert flow.decide(offer['ticket'], 'session-cookie-a', 'deny')['network_calls'] == 0
    assert flow.status(offer['ticket'],'session-cookie-a')['status']=='denied'
    with pytest.raises(ResearchFlowError):flow.decide(offer['ticket'],'session-cookie-a','approve')
    assert not (tmp_path/'research_runs').exists()


def test_session_mismatch_replay_and_supersession(tmp_path):
    flow = ResearchFlow(config(tmp_path))
    first = flow.offer(response(), 'session-1')
    with pytest.raises(ResearchFlowError):flow.decide(first['ticket'],'session-2','approve')
    second=flow.offer(response(),'session-1')
    assert flow.status(first['ticket'],'session-1')['status']=='denied'
    assert flow.status(second['ticket'],'session-1')['status']=='pending'
    with pytest.raises(ResearchFlowError):flow.process(second['ticket'],'session-1')


def test_expired_one_use_permission(tmp_path):
    flow = ResearchFlow(config(tmp_path))
    offer = flow.offer(response(),'browser')
    entry = flow.requests[offer['ticket']]
    # Expiry enforced by original Stage2/3 permission controller, even if UI keeps a stale ticket.
    entry['controller']._clock = lambda: entry['request'].expires_at + 1
    assert flow.status(offer['ticket'],'browser')['status']=='expired'
    with pytest.raises(ResearchFlowError):flow.decide(offer['ticket'],'browser','approve')


def test_no_index_write_api(tmp_path):
    flow=ResearchFlow(config(tmp_path)); offer=flow.offer(response(),'browser')
    entry=flow.requests[offer['ticket']]
    assert entry['generation']=='reviewed_test'
    assert 'index_writes' not in flow.status(offer['ticket'],'browser') or flow.status(offer['ticket'],'browser')['index_writes']==0
    assert not hasattr(flow, 'activate_generation')


def test_stage6_ui_and_pdf_link_contract():
    js=(APP/'src/unmochon_live/ui/static/app.js').read_text(encoding='utf-8')
    css=(APP/'src/unmochon_live/ui/static/style.css').read_text(encoding='utf-8')
    ui=(APP/'src/unmochon_live/ui.py').read_text(encoding='utf-8')
    assert 'data-research-action="approve"' in js
    assert 'data-research-action="deny"' in js
    assert '#page=' in js
    assert 'stage6-clause-text' in css
    assert '/ui/research/decision' in ui and '/ui/research/status' in ui
    assert 'app.mount("/pdfjs"' in ui and 'app.mount("/pdf"' in ui
    assert 'current_policy_verified' in js


def test_fresh_approval_consumed_once_without_network(tmp_path):
    async def scenario():
        flow=ResearchFlow(config(tmp_path))
        offered=flow.offer(response(),'same-browser')
        entry=flow.requests[offered['ticket']]
        def fake_crawl(record, permit):
            record['controller'].consume_permit(permit,question=record['question'],plan=record['plan'])
            record['status']='staged_unverified'
        flow._crawl=fake_crawl
        assert flow.decide(offered['ticket'],'same-browser','approve')['status']=='crawling'
        await entry['task']
        assert entry['controller'].status(entry['request'].request_id)=='consumed'
        assert flow.status(offered['ticket'],'same-browser')['index_writes']==0
        with pytest.raises(ResearchFlowError):flow.decide(offered['ticket'],'same-browser','approve')
        assert not list((tmp_path/'research_runs').glob('raw_*'))
    asyncio.run(scenario())
