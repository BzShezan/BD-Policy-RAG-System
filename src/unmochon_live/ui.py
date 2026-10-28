"""Serve the original Unmochon UI against the existing orchestration contract.

Local loopback users receive a signed UI session. Public/production access needs
an API-key login. The API key is never injected into page HTML or JavaScript.
"""
import base64
import hashlib
import hmac
import ipaddress
import json
import secrets
import re
import time
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .schemas import Query, Response

UI_ROOT = Path(__file__).with_name("ui")
COOKIE = "unmochon_ui"
SESSION_SECONDS = 3600

class Login(BaseModel):
    key: str = Field(min_length=1, max_length=512)

class Sessions:
    def __init__(self, key: str):
        self.secret = (key or secrets.token_urlsafe(48)).encode()

    def issue(self):
        payload = {"expires": int(time.time()) + SESSION_SECONDS,
                   "csrf": secrets.token_urlsafe(32)}
        raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
        signature = hmac.new(self.secret, raw.encode(), hashlib.sha256).hexdigest()
        return raw + "." + signature, payload

    def read(self, cookie):
        if not cookie or len(cookie) > 1024:
            return None
        try:
            raw, signature = cookie.rsplit(".", 1)
            expected = hmac.new(self.secret, raw.encode(), hashlib.sha256).hexdigest()
            if not secrets.compare_digest(signature, expected):
                return None
            payload = json.loads(base64.urlsafe_b64decode(raw))
            if not isinstance(payload.get("expires"), int) or payload["expires"] <= time.time():
                return None
            if not isinstance(payload.get("csrf"), str):
                return None
            return payload
        except (ValueError, TypeError, KeyError):
            return None


def check_origin(request: Request):
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(403, "Cross-site requests are not allowed")
    origin = request.headers.get("origin")
    if origin:
        parsed = urlsplit(origin)
        if (parsed.scheme, parsed.netloc) != (request.url.scheme, request.url.netloc):
            raise HTTPException(403, "Origin mismatch")


def local_client(request: Request):
    try:
        return ipaddress.ip_address(request.client.host).is_loopback
    except (ValueError, AttributeError):
        return False


def install_ui(app, settings, execute):
    sessions = Sessions(settings.api_key)
    from .research_flow import ResearchFlow, ResearchFlowError
    research = ResearchFlow(settings, execute=execute)
    app.state.research = research

    def require_session(request):
        check_origin(request)
        cookie = request.cookies.get(COOKIE) or ""
        payload = sessions.read(cookie)
        if not payload:
            raise HTTPException(401, "Browser session expired; reload or sign in")
        if not secrets.compare_digest(request.headers.get("x-csrf-token", ""), payload["csrf"]):
            raise HTTPException(403, "Invalid browser request token; reload this page")
        return cookie
    app.mount("/static", StaticFiles(directory=UI_ROOT / "static"), name="static")
    # Code-only archives omit binary logos. Existing local assets are preserved.
    if (UI_ROOT / 'static/logo').is_dir():
        app.mount("/logo", StaticFiles(directory=UI_ROOT / "static" / "logo"), name="logo")
    from original_paths import PDF_ROOT, PROJECT_ROOT
    PDF_ROOT.mkdir(parents=True, exist_ok=True)
    app.mount("/pdf", StaticFiles(directory=PDF_ROOT), name="pdf")
    app.mount("/pdfjs", StaticFiles(directory=PROJECT_ROOT / "UI" / "static" / "pdfjs"), name="pdfjs")


    def set_cookie(response, value):
        response.set_cookie(COOKIE, value, max_age=SESSION_SECONDS, httponly=True,
                            secure=settings.app_env == "production", samesite="strict", path="/")

    def shell(request, filename):
        payload = sessions.read(request.cookies.get(COOKIE))
        cookie = None
        # Production and remote local binds do not get an automatic privileged session.
        if not payload and settings.app_env == "local" and local_client(request):
            cookie, payload = sessions.issue()
        csrf = payload["csrf"] if payload else ""
        html = (UI_ROOT / "templates" / filename).read_text(encoding="utf-8")
        response = HTMLResponse(html.replace("__UI_CSRF__", csrf))
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; "
            "font-src 'self'; connect-src 'self'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        )
        if cookie:
            set_cookie(response, cookie)
        return response

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def home(request: Request):
        return shell(request, "index.html")

    @app.get("/results", response_class=HTMLResponse, include_in_schema=False)
    async def results(request: Request):
        return shell(request, "results.html")

    @app.post("/ui/login", include_in_schema=False)
    async def login(body: Login, request: Request):
        check_origin(request)
        if not settings.api_key or not secrets.compare_digest(body.key.encode(), settings.api_key.encode()):
            raise HTTPException(401, "Invalid access key")
        cookie, payload = sessions.issue()
        from fastapi.responses import JSONResponse
        response = JSONResponse({"csrf": payload["csrf"]}, headers={"Cache-Control": "no-store"})
        set_cookie(response, cookie)
        return response

    @app.post("/ui/query", response_model=Response, include_in_schema=False)
    async def browser_query(body: Query, request: Request):
        cookie = require_session(request)
        result = await execute(body)
        if settings.rag_backend == "stage6" and result.action == "REQUEST_RESEARCH_PERMISSION":
            try:
                offer = research.offer(result, cookie)
            except (ResearchFlowError, ValueError, ImportError, OSError) as ex:
                offer = {"available": False, "reason": type(ex).__name__ + ": local Stage 3 setup needs review"}
            return result.model_copy(update={"research_offer": offer})
        return result

    class ResearchDecision(BaseModel):
        ticket: str = Field(min_length=20, max_length=100)
        decision: str
        allow_conditional_update: bool = False

    class ResearchTicket(BaseModel):
        ticket: str = Field(min_length=20, max_length=100)

    @app.post("/ui/research/decision", include_in_schema=False)
    async def research_decision(body: ResearchDecision, request: Request):
        cookie = require_session(request)
        try:
            return research.decide(body.ticket, cookie, body.decision, body.allow_conditional_update)
        except ResearchFlowError as ex:
            raise HTTPException(409, str(ex)) from ex
        except Exception as ex:
            raise HTTPException(409, "Permission denied, expired or invalid") from ex

    @app.post("/ui/research/process", include_in_schema=False)
    async def research_process(body: ResearchTicket, request: Request):
        cookie = require_session(request)
        try:
            return research.process(body.ticket, cookie)
        except ResearchFlowError as ex:
            raise HTTPException(409, str(ex)) from ex

    @app.post("/ui/research/status", include_in_schema=False)
    async def research_status(body: ResearchTicket, request: Request):
        cookie = require_session(request)
        try:
            return research.status(body.ticket, cookie)
        except ResearchFlowError as ex:
            raise HTTPException(404, str(ex)) from ex

    @app.post('/ui/research/cancel', include_in_schema=False)
    async def research_cancel(body: ResearchTicket, request: Request):
        cookie = require_session(request)
        try:
            return research.cancel(body.ticket, cookie)
        except ResearchFlowError as ex:
            raise HTTPException(409, str(ex)) from ex

    @app.post('/ui/research/review', include_in_schema=False)
    async def research_review(body: ResearchTicket, request: Request):
        cookie = require_session(request)
        try:
            return research.review(body.ticket, cookie)
        except ResearchFlowError as ex:
            raise HTTPException(409, str(ex)) from ex

    class ContentReview(ResearchTicket):
        reviewer: str = Field(min_length=1, max_length=160)
        decisions: list[dict] = Field(min_length=1, max_length=200)

    @app.post('/ui/research/review/submit', include_in_schema=False)
    async def submit_content_review(body: ContentReview, request: Request):
        cookie = require_session(request)
        try:
            return await research.submit_review(body.ticket, cookie, body.reviewer, body.decisions)
        except (ValueError, OSError, KeyError) as ex:
            raise HTTPException(409, str(ex)) from ex

    @app.get('/verified-pdf/{raw_sha}.pdf', include_in_schema=False)
    async def verified_research_pdf(raw_sha: str, request: Request):
        check_origin(request)
        if not sessions.read(request.cookies.get(COOKIE)):
            raise HTTPException(401, 'Browser session required')
        if settings.rag_backend != 'stage6' or not re.fullmatch('[0-9a-f]{64}', raw_sha):
            raise HTTPException(404, 'Unknown PDF')
        def locate():
            from .runtime import load_stage6
            load_stage6(settings.stage6_package or settings.root/'reference_pipelines/stage6')
            from stage6.generations import active, generation
            workspace = settings.stage6_workspace or settings.root/'data/stage6_workspace'
            pointer = active(workspace)
            root = generation(workspace,pointer['generation'])
            path = root/'evidence/research_sources'/(raw_sha+'.pdf')
            if not path.is_file():
                manifest = json.loads((root/'generation_manifest.json').read_text(encoding='utf-8'))
                names = [n for n,h in manifest['files'].items()
                         if n.startswith('evidence/') and n.lower().endswith('.pdf') and h == raw_sha]
                if names:
                    path = root/names[0]
            if not path.is_file() or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != raw_sha:
                raise HTTPException(404,'Verified PDF is not available in this generation')
            return path
        import asyncio
        from fastapi.responses import FileResponse
        return FileResponse(await asyncio.to_thread(locate),media_type='application/pdf',
                            headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
