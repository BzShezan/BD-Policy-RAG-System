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
    app.mount("/static", StaticFiles(directory=UI_ROOT / "static"), name="static")
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
        check_origin(request)
        payload = sessions.read(request.cookies.get(COOKIE))
        if not payload:
            raise HTTPException(401, "Browser session expired; reload or sign in")
        if not secrets.compare_digest(request.headers.get("x-csrf-token", ""), payload["csrf"]):
            raise HTTPException(403, "Invalid browser request token; reload this page")
        return await execute(body)
