"""Local HTTP checks: session, CSRF, consent offer, PDF routes (offline)."""
import re
import shutil
import sys
from dataclasses import replace
from pathlib import Path
import os
from types import ModuleType

from fastapi.testclient import TestClient
from unmochon_live.api import create_app
from unmochon_live.config import Settings
from unmochon_live.schemas import Response

ROOT=Path(__file__).resolve().parents[1]
STAGE4=Path(os.getenv('STAGE4_PACKAGE', str(ROOT.parent/'Unmochon_Stage4_Evidence_Processing')))
if not STAGE4.exists():
    STAGE4=ROOT/'reference_pipelines/stage4'


class FakeOrchestrator:
    async def ask(self, body):
        return Response(request_id='test-1',question=body.question,route='RAG',
            status='NEEDS_VERIFICATION',answer='Fixture: missing current evidence',evidence=[],
            warnings=[],trace=['RAG_INSUFFICIENT'],backend='stage6_original_hybrid_verified_pair',
            elapsed_ms=10, action='REQUEST_RESEARCH_PERMISSION',generation='reviewed_fixture',
            research_trigger={'ministry':'Disaster Management','program':'vgf','reason':'Evidence gap'})


def test_endpoints_consent_and_pdf(tmp_path, monkeypatch):
    import pytest
    if not STAGE4.is_dir():
        pytest.skip('Stage 3/4 package absent; configure STAGE4_PACKAGE')
    pdfroot=tmp_path/'pdf';pdfroot.mkdir()
    (pdfroot/'local-test.pdf').write_bytes(b'%PDF-1.4\n%%EOF\n')
    original=tmp_path/'original';(original/'UI/static/pdfjs/web').mkdir(parents=True)
    (original/'UI/static/pdfjs/web/viewer.html').write_text('<title>Local PDF.js fixture</title>')
    import unmochon_live.ui as ui_mod
    fake_ui=tmp_path/'ui'
    shutil.copytree(ROOT/'src/unmochon_live/ui',fake_ui)
    (fake_ui/'static/logo').mkdir(exist_ok=True)
    monkeypatch.setattr(ui_mod,'UI_ROOT',fake_ui)
    module=ModuleType('original_paths');module.PDF_ROOT=pdfroot;module.PROJECT_ROOT=original
    monkeypatch.setitem(sys.modules,'original_paths',module)
    cfg=Settings(root=ROOT,corpus_dir=ROOT/'data/corpus',source_registry=ROOT/'config/sources.json',
        rag_backend='stage6',stage4_package=STAGE4,research_output_root=tmp_path/'research')
    app=create_app(settings=cfg,orchestrator=FakeOrchestrator())
    with TestClient(app,client=('127.0.0.1',9001)) as client:
        assert client.get('/health/live').status_code==200
        assert client.get('/pdf/local-test.pdf').content.startswith(b'%PDF-1.4')
        assert client.get('/pdfjs/web/viewer.html').status_code==200
        assert client.get('/pdf/../secret').status_code in (400,404)
        shell=client.get('/results')
        assert shell.status_code==200
        match=re.search(r'<meta name="ui-csrf" content="([^"]+)"',shell.text)
        assert match
        assert client.post('/ui/query',json={'question':'VGF question'}).status_code==403
        headers={'X-CSRF-Token': match.group(1)}
        result=client.post('/ui/query',json={'question':'2026 VGF details'},headers=headers)
        assert result.status_code==200
        offer=result.json()['research_offer']
        assert offer['available'] and offer['ministry']=='Disaster Management'
        # Explicit denial path never executes a crawler.
        denied=client.post('/ui/research/decision',headers=headers,
            json={'ticket':offer['ticket'],'decision':'deny'})
        assert denied.status_code==200 and denied.json()['network_calls']==0
        repeat=client.post('/ui/research/decision',headers=headers,
            json={'ticket':offer['ticket'],'decision':'approve'})
        assert repeat.status_code==409
        state=client.post('/ui/research/status',headers=headers,json={'ticket':offer['ticket']})
        assert state.json()['status']=='denied'
    assert not (tmp_path/'research').exists()
