import os
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv

@dataclass(frozen=True)
class Settings:
    root: Path
    corpus_dir: Path
    source_registry: Path
    rag_backend: str = "original"
    rag_api_url: str = "http://127.0.0.1:8101/v1/search"
    rag_api_key: str = ""
    rag_timeout: float = 20
    web_timeout: float = 10
    web_total: float = 40
    web_max_pages: int = 4
    web_max_bytes: int = 2000000
    enable_web_search: bool = True
    app_env: str = "local"
    api_key: str = ""
    # Only used when RAG_BACKEND=stage6; original backend remains the default.
    stage6_package: Path | None = None
    stage6_workspace: Path | None = None
    stage6_model_cache: Path | None = None
    stage6_python: str = ""
    stage6_timeout: float = 180
    stage4_package: Path | None = None
    research_output_root: Path | None = None
    stage4_tesseract: Path | None = None
    research_registry: Path | None = None
    research_job_seconds: int = 2400
    research_max_jobs: int = 2

    @classmethod
    def load(cls):
        root = Path(os.getenv("UNMOCHON_HOME", Path(__file__).resolve().parents[2])).resolve()
        load_dotenv(root / ".env", override=False)
        def path(key, default):
            p = Path(os.getenv(key, default)).expanduser()
            return p.resolve() if p.is_absolute() else (root / p).resolve()
        s = cls(root=root, corpus_dir=path("CORPUS_DIR", "data/corpus"),
            source_registry=path("SOURCE_REGISTRY", "config/sources.json"),
            rag_backend=os.getenv("RAG_BACKEND", "original"),
            rag_api_url=os.getenv("RAG_API_URL", "http://127.0.0.1:8101/v1/search"),
            rag_api_key=os.getenv("RAG_API_KEY", ""),
            rag_timeout=float(os.getenv("RAG_TIMEOUT_SECONDS", "20")),
            web_timeout=float(os.getenv("WEB_TIMEOUT_SECONDS", "10")),
            web_total=float(os.getenv("WEB_TOTAL_SECONDS", "40")),
            web_max_pages=int(os.getenv("WEB_MAX_PAGES", "4")),
            web_max_bytes=int(os.getenv("WEB_MAX_BYTES", "2000000")),
            enable_web_search=os.getenv("ENABLE_WEB_SEARCH", "false").lower() == "true",
            app_env=os.getenv("APP_ENV", "local"), api_key=os.getenv("API_KEY", ""),
            stage6_package=path("STAGE6_PACKAGE", "reference_pipelines/stage6"),
            stage6_workspace=path("STAGE6_WORKSPACE", "data/stage6_workspace"),
            stage6_model_cache=path("STAGE6_MODEL_CACHE", "model_cache"),
            stage6_python=os.getenv("STAGE6_PYTHON", ""),
            stage6_timeout=float(os.getenv("STAGE6_TIMEOUT_SECONDS", "180")),
            stage4_package=path("STAGE4_PACKAGE", "reference_pipelines/stage4"),
            research_output_root=path("RESEARCH_OUTPUT_ROOT", "data/research_runs"),
            research_registry=path("RESEARCH_SOURCE_REGISTRY", "config/research_sources.json"),
            research_job_seconds=int(os.getenv("RESEARCH_JOB_SECONDS", "2400")),
            research_max_jobs=int(os.getenv("RESEARCH_MAX_JOBS", "2")),
            stage4_tesseract=path("STAGE4_TESSERACT", os.getenv("STAGE4_TESSERACT")) if os.getenv("STAGE4_TESSERACT") else None)
        if s.rag_backend not in {"original", "corpus", "http", "stage6"}:
            raise ValueError("RAG_BACKEND must be original, corpus, http or stage6")
        if not 60 <= s.research_job_seconds <= 3600 or not 1 <= s.research_max_jobs <= 4:
            raise ValueError('Research job limits are out of bounds')
        if not (1 <= s.web_max_pages <= 10 and 1024 <= s.web_max_bytes <= 5000000):
            raise ValueError("web limits are out of bounds")
        if min(s.web_timeout, s.web_total, s.rag_timeout, s.stage6_timeout) <= 0:
            raise ValueError("timeouts must be positive")
        if s.app_env not in {"local", "production"}:
            raise ValueError("APP_ENV must be local or production")
        if s.app_env == "production" and len(s.api_key) < 32:
            raise ValueError("Production requires API_KEY with at least 32 characters")
        return s
