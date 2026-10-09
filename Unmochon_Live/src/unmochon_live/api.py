import asyncio
import secrets
from contextlib import asynccontextmanager
from fastapi import FastAPI,Header,HTTPException
from .config import Settings
from .orchestrator import Orchestrator
from .base_orchestrator import BaseOrchestrator
from .schemas import Query,Response

def create_app(settings=None,orchestrator=None):
    settings=settings or Settings.load()
    @asynccontextmanager
    async def lifespan(app):
        from filelock import FileLock
        database_lock = FileLock(str(settings.root / ".database.lock"), timeout=0)
        if settings.rag_backend == "original" and orchestrator is None:
            database_lock.acquire()
        try:
            app.state.orchestrator=orchestrator or await asyncio.to_thread(BaseOrchestrator if settings.rag_backend == "original" else Orchestrator,settings)
            app.state.capacity=asyncio.Semaphore(4)
            yield
        finally:
            database_lock.release()
    app=FastAPI(title="Unmochon Live",version="0.1.1",lifespan=lifespan,
        docs_url="/docs" if settings.app_env=="local" else None,
        redoc_url=None,openapi_url="/openapi.json" if settings.app_env=="local" else None)
    @app.get("/health/live")
    def live():return {"status":"alive"}
    @app.get("/health/ready")
    def ready():return {"status":"initialized", "rag_backend":settings.rag_backend,
        "upstream_verified":False}
    async def execute(body:Query):
        # Shared execution path for the browser and versioned API.
        # Bound in-flight work; ingress must also enforce request rate / body size.
        try:await asyncio.wait_for(app.state.capacity.acquire(),timeout=.1)
        except TimeoutError:raise HTTPException(status_code=503,detail="Capacity reached; retry shortly")
        try:return await app.state.orchestrator.ask(body)
        finally:app.state.capacity.release()
    @app.post("/v1/query",response_model=Response)
    async def query(body:Query,x_api_key:str|None=Header(default=None)):
        if settings.api_key and not secrets.compare_digest((x_api_key or "").encode(),settings.api_key.encode()):
            raise HTTPException(status_code=401,detail="Invalid API key")
        return await execute(body)

    from .ui import install_ui
    install_ui(app, settings, execute)
    return app
