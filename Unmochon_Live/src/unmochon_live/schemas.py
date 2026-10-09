from datetime import datetime, timezone
from typing import Literal, Any
from pydantic import BaseModel, Field, model_validator

def now():
    return datetime.now(timezone.utc).isoformat()

class Query(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    top_k: int = Field(default=3, ge=1, le=10)
    @model_validator(mode="after")
    def nonblank(self):
        self.question = self.question.strip()
        if len(self.question) < 2:
            raise ValueError("question must contain at least two non-space characters")
        return self

class Evidence(BaseModel):
    id: str
    text: str = Field(min_length=1, max_length=50000)
    source_kind: Literal["corpus_clause", "official_web"]
    title: str = ""
    source_url: str | None = None
    document_id: str | None = None
    page: int | None = None
    published_at: str | None = None
    checked_at: str | None = None
    content_sha256: str | None = None
    verification: Literal["corpus_only", "official_fetched"] = "corpus_only"
    # A fetched page is not proof that it is the latest policy.
    freshness: Literal["not_checked", "checked_now_version_unknown"] = "not_checked"

    ministry: str | None = None
    viewer_url: str | None = None
    confidence_tier: str | None = None
    extracted: list[dict[str, Any]] = Field(default_factory=list)
    explanation: str | None = None
    bbox: Any = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    document_metadata: dict[str, Any] = Field(default_factory=dict)

class RagResult(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    backend: str
    translated: str | None = None
    intents: list[str] = Field(default_factory=list)
    ministry: str | None = None
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    original_results: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list, max_length=10)
    sufficient: bool = False
    reason: str = ""
    # Teammate owns calibrated sufficiency and conflict/supersession decisions.
    warnings: list[str] = Field(default_factory=list)

class Response(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    request_id: str
    question: str
    route: Literal["RAG", "LIVE_SERVICE", "CLARIFY"]
    service: str | None = None
    status: Literal["EVIDENCE_FOUND", "NEEDS_VERIFICATION", "UNAVAILABLE", "CLARIFICATION_REQUIRED"]
    answer: str
    evidence: list[Evidence] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    trace: list[str] = Field(default_factory=list)
    backend: str
    translated: str | None = None
    intents: list[str] = Field(default_factory=list)
    ministry: str | None = None
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    original_results: list[dict[str, Any]] = Field(default_factory=list)
    elapsed_ms: int
    created_at: str = Field(default_factory=now)
