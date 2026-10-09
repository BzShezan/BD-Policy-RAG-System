# UI integration validation — 8 October 2026

Reference environment: Python 3.12.14, same pinned runtime dependencies as Week 1.
45 automated tests passed: previous 35 plus 10 UI/session cases covering loopback
sessions, unchanged API-key enforcement, CSRF, origin rejection, remote login,
production secure cookies, expiry/forgery, input bounds and static/template serving.
Production tests use synthetic keys. Dependency check, Python compilation and
JavaScript syntax check passed.

Actual Uvicorn + HTTP client: home 200, signed UI session + CSRF query 200. The real
old-age query returned three archived clause records through RAG. NID/Passport
routed to live retrieval but returned UNAVAILABLE here. See UI_HTTP_SMOKE.json.
Live-service success is unverified. Browser and v1 API use one execution path.

Structural checks: UTF-8 templates, search input, script, CSRF metadata, language
controls and local Bengali font present. PNG logo bytes match supplied UI.zip.
Wheel packaging includes templates/resources/font. No new runtime dependency.

Rendered browser review was not completed: cloud browser could not reach this
container's loopback server and its URL policy rejects local-file previews. No
screenshot or desktop/mobile pixel-layout verification is claimed. Responsive CSS
awaits user-browser verification. Offline fixtures are not shipped in this patch.

No reconstruction of the missing original hybrid retriever, policy-currentness
claims, semantic contradictions or old PDF.js/raw-PDF integration is included.
Those remain under the existing project plan. Tests emit one Starlette TestClient
HTTPX deprecation warning; no failed tests.
