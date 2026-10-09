# Validation — 7 October 2026

Reference: clean CPython 3.12.14 virtual environment, Linux.
Installed the exact `requirements-dev.lock`, then the editable package without
extra dependency resolution. `pip check`: no broken requirements.

35 automated tests passed. These cover routing (policy, NID, Passport, birth
registration, driving licence, ambiguity), corpus-gap/freshness escalation,
real archived clause retrieval, metadata linkage, authority-domain spoofing,
redirect validation, private-address rejection, byte/content-type limits,
HTML navigation/script exclusion, maintenance rejection, document-vs-fee intent,
source passage preservation, HTTP contract validation/key/size/failure handling,
API authentication/input validation, production-key guard and relocatable paths.
Teammate HTTP tests use mocks; the real missing hybrid retriever was not tested.
The test runner emits one Starlette HTTPX deprecation warning; no failed tests.
Python 3.13/3.14 and Windows were not executed in this environment.

Corpus baseline: 15,981 archived JSONL rows; 15,918 usable unique non-review rows.
This is distinct from the older ChromaDB collection count. Original gzip corpus
files and metadata are bundled; ChromaDB and original project files stay untouched.
The old-age query returns real clauses containing the age provision, with document
ID, page and inherited official source URL. No latest-version validity is asserted.

Actual local Uvicorn process: `/health/live` 200, unauthenticated `/v1/query` 401,
authenticated old-age query 200 with RAG evidence. See `API_SMOKE.json`.
`setup.py` was run twice: created settings once, preserved existing settings later.
Python source compilation completed. Docker engine was unavailable; container
build/runtime and external deployment remain unverified.

Real network probe: old-age corpus query EVIDENCE_FOUND; NID and Passport routed
to LIVE_SERVICE but official pages could not be fetched from this execution
environment, returning UNAVAILABLE with zero evidence. These are NOT successful
live-service answers. See `LIVE_SMOKE.jsonl`. Run `scripts/smoke_live.py` on the user
PC; source blocking, TLS/DNS, maintenance, JavaScript-only content and insufficient
passages require diagnosis before claiming the NID/Passport demo is validated.
The implementation does not circumvent site blocking or disable TLS verification.

Week 1 completion is code + reproducible package + tested local corpus/API + live
failure handling. Outstanding acceptance checks: successful real NID/Passport
source retrieval on the deployment network, full teammate retriever connection,
service-answer relevance/completeness assessment and actual container deployment.
These limits are explicit; this package is not a completed production service.
