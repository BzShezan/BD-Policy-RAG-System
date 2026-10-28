"""Offline Stage4 dynamic adapter tests (no web, no index writes)."""
from dataclasses import asdict
from pathlib import Path
import json
import os
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
STAGE4 = Path(os.getenv('STAGE4_PACKAGE', str(ROOT.parent / 'Unmochon_Stage4_Evidence_Processing')))
if STAGE4.is_dir():
    sys.path.insert(0, str(STAGE4))

from unmochon_live.stage4_dynamic import validate_app_snapshot, process_dynamic


@pytest.fixture
def captured(tmp_path):
    if not (STAGE4/'data/captured_live_snapshot/stage3_live_summary.json').is_file():
        pytest.skip('Original Stage4 snapshot absent; set STAGE4_PACKAGE')
    from stage3.scope import Registry
    snapshot = tmp_path/'raw'
    shutil.copytree(STAGE4/'data/captured_live_snapshot', snapshot)
    live = json.loads((snapshot/'stage3_live_summary.json').read_text(encoding='utf-8'))
    cases = json.loads((STAGE4/'data/research_cases.json').read_text(encoding='utf-8'))
    case = next(c for c in cases if c['query_id'] == live['query_id'])
    plan = Registry().make_plan(case['question'],case['program'],case['ministry'],case['reason'])
    (snapshot/'stage3_app_summary.json').write_text(json.dumps({
        'schema_version': 1, 'status': 'staged_unverified',
        'request_id': live['request_id'], 'source_approval': False,
        'current_policy_verified': False, 'index_writes': 0, 'scope': asdict(plan),
        'result': live['result'], 'network_request_attempts': live['network_request_attempts'],
        'generation_at_consent': 'reviewed_fake'},ensure_ascii=False), encoding='utf-8')
    run = next((snapshot/'runs').iterdir())
    shutil.copy2(run/'consent_audit.json', snapshot/'latest_consent_audit.json')
    return snapshot


def test_valid_user_consented_app_snapshot(captured, tmp_path):
    parsed = validate_app_snapshot(captured)
    assert len(parsed['result'].artifacts) == 5
    report = process_dynamic(captured, tmp_path/'processed', STAGE4)
    assert report['status'] == 'review_required'
    assert report['html_artifacts_processed'] == 5
    assert report['pdf_artifacts_processed'] == 0
    assert report['index_writes'] == 0 and report['current_policy_verified'] is False
    assert report['source_snapshot_unchanged']
    assert (tmp_path/'processed/stage4_dynamic_summary.json').is_file()


@pytest.mark.parametrize('change', ['scope','permission','raw','receipt','network'])
def test_refuses_invalid_provenance(captured, change):
    summary = captured/'stage3_app_summary.json'
    obj = json.loads(summary.read_text(encoding='utf-8'))
    if change == 'scope':
        obj['scope']['max_http_requests'] = 50
    elif change == 'permission':
        audit_file=captured/'latest_consent_audit.json'
        audit=json.loads(audit_file.read_text(encoding='utf-8'))
        audit[1]['state']='denied'
        audit_file.write_text(json.dumps(audit),encoding='utf-8')
    elif change == 'raw':
        artifact=next(captured.glob('runs/*/raw/*.html'))
        artifact.write_bytes(artifact.read_bytes()+b'changed')
    elif change == 'receipt':
        receipt=next(captured.glob('runs/*/crawl_receipt.json'))
        data=json.loads(receipt.read_text(encoding='utf-8'))
        data['artifacts']=[]
        receipt.write_text(json.dumps(data),encoding='utf-8')
    elif change == 'network':
        obj['network_request_attempts']=50
    summary.write_text(json.dumps(obj,ensure_ascii=False),encoding='utf-8')
    with pytest.raises((ValueError, KeyError)):
        validate_app_snapshot(captured)


def test_cannot_write_inside_raw_snapshot(captured):
    with pytest.raises(ValueError):
        process_dynamic(captured,captured/'processed',STAGE4)
    assert not (captured/'processed').exists()


def test_no_overwrite_of_preexisting_output(captured,tmp_path):
    dst=tmp_path/'existing'
    dst.mkdir()
    (dst/'chroma.sqlite3').write_bytes(b'index')
    with pytest.raises(ValueError):
        process_dynamic(captured,dst,STAGE4)
    assert (dst/'chroma.sqlite3').read_bytes()==b'index'


def test_research_flow_uses_dynamic_adapter_without_auto_index():
    flow=(ROOT/'src/unmochon_live/research_flow.py').read_text(encoding='utf-8')
    assert 'unmochon_live.stage4_dynamic' in flow
    assert "('html', 'run_stage4_html.py')" not in flow
    assert 'activate_generation' not in flow
