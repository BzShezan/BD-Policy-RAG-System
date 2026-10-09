import dataclasses
import re
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from unmochon_live.api import create_app
from unmochon_live.config import Settings
from unmochon_live.schemas import Response,Evidence
from unmochon_live.ui import COOKIE,Sessions

ROOT=Path(__file__).resolve().parents[1]
KEY='synthetic-ui-test-key-that-must-not-appear-in-html'
class Engine:
    def __init__(self):self.calls=0
    async def ask(self,query):
        self.calls+=1
        return Response(request_id='synthetic-test',question=query.question,route='RAG',status='EVIDENCE_FOUND',
            answer='Synthetic test answer',evidence=[Evidence(id='synthetic-clause',text='Synthetic test clause',source_kind='corpus_clause')],backend='synthetic-test',elapsed_ms=1)

@pytest.fixture
def settings():return Settings(root=ROOT,corpus_dir=ROOT/'data/corpus',source_registry=ROOT/'config/sources.json',api_key=KEY,enable_web_search=False)

def token(html):return re.search(r'name="ui-csrf" content="([^"]*)"',html).group(1)

def test_local_browser_session_does_not_disclose_key(settings):
    engine=Engine()
    with TestClient(create_app(settings,engine),client=('127.0.0.1',45000)) as c:
        home=c.get('/')
        assert home.status_code==200 and KEY not in home.text
        assert token(home.text)
        assert 'httponly' in home.headers['set-cookie'].lower()
        assert 'samesite=strict' in home.headers['set-cookie'].lower()
        assert home.headers['cache-control']=='no-store'
        assert "script-src 'self'" in home.headers['content-security-policy']
        result=c.post('/ui/query',json={'question':'test question'},headers={'x-csrf-token':token(home.text)})
        assert result.status_code==200 and engine.calls==1
        # UI session does not substitute for the API key on the versioned endpoint.
        assert c.post('/v1/query',json={'question':'test question'}).status_code==401

@pytest.mark.parametrize('headers',[{}, {'x-csrf-token':'wrong'}])
def test_ui_csrf_required(settings,headers):
    with TestClient(create_app(settings,Engine()),client=('127.0.0.1',45000)) as c:
        c.get('/')
        assert c.post('/ui/query',json={'question':'test question'},headers=headers).status_code==403

@pytest.mark.parametrize('headers',[{'origin':'https://evil.example'},{'sec-fetch-site':'cross-site'}])
def test_ui_cross_origin_rejected(settings,headers):
    with TestClient(create_app(settings,Engine()),client=('127.0.0.1',45000)) as c:
        home=c.get('/');headers['x-csrf-token']=token(home.text)
        assert c.post('/ui/query',json={'question':'test question'},headers=headers).status_code==403

def test_remote_client_must_login_even_in_local_config(settings):
    with TestClient(create_app(settings,Engine()),client=('203.0.113.5',45000)) as c:
        home=c.get('/')
        assert token(home.text)=='' and COOKIE not in c.cookies
        assert c.post('/ui/query',json={'question':'test question'}).status_code==401
        assert c.post('/ui/login',json={'key':'wrong'}).status_code==401
        assert c.post('/ui/login',json={'key':'বাংলা ভুল key'}).status_code==401
        login=c.post('/ui/login',json={'key':KEY})
        assert login.status_code==200
        assert c.post('/ui/query',json={'question':'test question'},headers={'x-csrf-token':login.json()['csrf']}).status_code==200

def test_production_never_autologins_loopback(settings):
    s=dataclasses.replace(settings,app_env='production')
    with TestClient(create_app(s,Engine()),base_url='https://testserver',client=('127.0.0.1',45000)) as c:
        assert token(c.get('/').text)==''
        login=c.post('/ui/login',json={'key':KEY})
        assert 'secure' in login.headers['set-cookie'].lower()
        assert c.post('/ui/query',json={'question':'test question'},headers={'x-csrf-token':login.json()['csrf']}).status_code==200
        assert c.get('/docs').status_code==404

def test_session_forgery_and_expiry(monkeypatch):
    sessions=Sessions('synthetic-key')
    cookie,data=sessions.issue()
    assert sessions.read(cookie)['csrf']==data['csrf']
    assert sessions.read(cookie+'0') is None
    assert sessions.read('not.a.valid.cookie') is None
    monkeypatch.setattr(time,'time',lambda:data['expires']+1)
    assert sessions.read(cookie) is None

def test_results_and_assets_are_served_without_template_reflection(settings):
    with TestClient(create_app(settings,Engine()),client=('127.0.0.1',45000)) as c:
        r=c.get('/results',params={'q':'<script>alert(1)</script>'})
        assert r.status_code==200 and '<script>alert(1)</script>' not in r.text
        assert '<meta charset="UTF-8">' in r.text
        for path in ['/logo/unmochon_icon.png','/logo/unmochon_word.png','/static/style.css','/static/app.js','/static/fonts/NotoSansBengali.ttf']:
            assert c.get(path).status_code==200
        assert c.get('/static/../config.py').status_code==404
        assert c.get('/.env').status_code==404

def test_ui_input_limits_and_shared_result_contract(settings):
    with TestClient(create_app(settings,Engine()),client=('127.0.0.1',45000)) as c:
        headers={'x-csrf-token':token(c.get('/').text)}
        assert c.post('/ui/query',json={'question':'  '},headers=headers).status_code==422
        body={'question':'test question','top_k':3}
        ui=c.post('/ui/query',json=body,headers=headers).json()
        api=c.post('/v1/query',json=body,headers={'x-api-key':KEY}).json()
        for field in ['schema_version','route','status','backend','evidence']:
            assert ui[field]==api[field]
