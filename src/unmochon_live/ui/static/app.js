// Original Unmochon visual shell, connected to the existing v1 orchestration data.
// Browser sessions and CSRF protect requests; the API key never lives in this file.
(function () {
  "use strict";
  let language = "bn";
  let lastResult = null;
  let activeController = null;
  let researchPoll = null;
  let researchJob = null;
  const labels = {
    bn: {
      loading: "অনুসন্ধান চলছে...", rag: "নথিভিত্তিক অনুসন্ধান", live: "সরকারি ওয়েব অনুসন্ধান", clarify: "আরও তথ্য প্রয়োজন",
      EVIDENCE_FOUND: "উৎসের তথ্য পাওয়া গেছে", UNAVAILABLE: "সরকারি উৎস এখন পড়া যায়নি",
      NEEDS_VERIFICATION: "আরও যাচাই প্রয়োজন", CLARIFICATION_REQUIRED: "একটি service বেছে প্রশ্ন করুন",
      foundNote: "এগুলো উৎসের প্রাসঙ্গিক উদ্ধৃতি। আপনার ক্ষেত্রে প্রযোজ্য শর্ত মূল উৎসে মিলিয়ে দেখুন।",
      unavailableNote: "সরকারি ওয়েবসাইট থেকে যাচাইযোগ্য তথ্য পড়া যায়নি। আবার চেষ্টা করুন; এটিকে সফল উত্তর ধরা হচ্ছে না।",
      verifyNote: "প্রশ্নের সম্পূর্ণ উত্তর যাচাই করার মতো তথ্য পাওয়া যায়নি।",
      clause: "সংরক্ষিত নথি", web: "সরকারি ওয়েব পৃষ্ঠা", original: "সম্পূর্ণ মূল লেখা", source: "উৎসের লিংক খুলুন ↗",
      published: "প্রকাশকাল", checked: "সরকারি উৎস পড়ার সময়", page: "পৃষ্ঠা", unknown: "উল্লেখ নেই",
      notChecked: "এই নথির সর্বশেষ সংস্করণ live যাচাই করা হয়নি।",
      fetched: "পৃষ্ঠা পড়া হয়েছে; সর্বশেষ কার্যকর সংস্করণ নিশ্চিত করা হয়নি।",
      candidate: "সম্পর্কিত সংরক্ষিত উদ্ধৃতি — প্রশ্নের পর্যাপ্ততা / freshness নিশ্চিত নয়।",
      diagnostics: "অনুসন্ধানের বিবরণ", backend: "Backend", baseline: "BM25 baseline · original hybrid retriever নয়",
      elapsed: "সময়", error: "অনুসন্ধানে সমস্যা হয়েছে। Server চলছে কি না দেখুন এবং আবার চেষ্টা করুন।",
      retry: "আবার চেষ্টা করুন", signIn: "এই deployment-এ প্রবেশ করতে access key দিন।",
      wrongKey: "Access key সঠিক নয়।", invalid: "২ থেকে ২০০০ অক্ষরের একটি প্রশ্ন লিখুন।",
      expired: "Browser session শেষ হয়েছে। Page reload করে আবার চেষ্টা করুন।",
      rate: "Server এখন ব্যস্ত। কিছুক্ষণ পরে আবার চেষ্টা করুন।"
    },
    en: {
      loading: "Searching...", rag: "Indexed policy search", live: "Official web search", clarify: "More context needed",
      EVIDENCE_FOUND: "Source evidence found", UNAVAILABLE: "Official source unavailable",
      NEEDS_VERIFICATION: "Verification needed", CLARIFICATION_REQUIRED: "Choose one service",
      foundNote: "These are relevant source excerpts. Check the original source for conditions that apply to you.",
      unavailableNote: "Official pages could not be read. Please retry; this is not a successful service answer.",
      verifyNote: "There is not enough evidence to verify a complete answer.",
      clause: "Stored policy document", web: "Official web page", original: "Full original text", source: "Open source ↗",
      published: "Published", checked: "Official page read at", page: "Page", unknown: "Not recorded",
      notChecked: "The latest version of this stored document has not been verified live.",
      fetched: "Page fetched; latest effective version not established.",
      candidate: "Related stored candidate — sufficiency / freshness not established.",
      diagnostics: "Search details", backend: "Backend", baseline: "BM25 baseline · not the original hybrid retriever",
      elapsed: "Time", error: "Search failed. Check that the server is running and retry.",
      retry: "Retry", signIn: "Sign in to this deployment with its access key.",
      wrongKey: "Incorrect access key.", invalid: "Enter a question between 2 and 2000 characters.",
      expired: "Browser session expired. Reload this page and retry.", rate: "The server is busy. Please retry shortly."
    }
  };
  const text = (key) => labels[language][key] || key;
  function escapeHTML(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, c => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"}[c]));
  }
  function csrf() { return document.querySelector('meta[name="ui-csrf"]').content; }
  function safeURL(raw) {
    try {
      const url = new URL(raw);
      if (!raw || !["https:", "http:"].includes(url.protocol) || url.username || url.password) return null;
      return url.href;
    } catch (_) { return null; }
  }
  function dateText(value) {
    if (!value) return text("unknown");
    if (!String(value).includes("T")) return String(value);
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString(language === "bn" ? "bn-BD" : "en-GB");
  }
  function excerpt(evidence, question) {
    const raw = evidence.text || "";
    if (/বয়স|বয়স|\bage\b/i.test(question)) {
      const lines = raw.split("\n");
      const index = lines.findIndex(line => /বয়স|বয়স|\bage\b/i.test(line));
      if (index >= 0) return lines.slice(Math.max(0, index - 1), index + 2).join("\n").slice(0, 1600);
    }
    return raw.length > 1000 ? raw.slice(0, 1000) + "…" : raw;
  }
  function viewerURL(raw) {
    if (!raw) return null;
    try {
      const url = new URL(raw, location.origin);
      return url.origin === location.origin && url.pathname === "/pdfjs/web/viewer.html" ? url.href : null;
    } catch (_) { return null; }
  }
  function sourceViewer(evidence) {
    const internal = viewerURL(evidence.viewer_url);
    if (internal) return internal;
    const source = safeURL(evidence.source_url);
    return source && /\.pdf(?:[?#]|$)/i.test(source) && Number(evidence.page) > 0
      ? source.split('#')[0] + '#page=' + Number(evidence.page) : null;
  }
  function renderExtracted(extracted) {
    // Original UI's extracted-values markup, using the original pipeline output.
    if (!extracted || !extracted.length) return "";
    return `<div class="extracted-values">${extracted.map(e => `<div class="extracted-row"><span class="ex-label">${escapeHTML(e.label)}:</span><span class="ex-value">${escapeHTML(e.value)}</span></div>`).join("")}</div>`;
  }
  function renderCard(evidence, index, data) {
    const url = safeURL(evidence.source_url);
    const viewer = sourceViewer(evidence);
    const isWeb = evidence.source_kind === "official_web";
    const candidate = data.status !== "EVIDENCE_FOUND" && !isWeb;
    return `<article id="clause-${index}" class="result-card${index === 0 ? " result-card-top" : ""}">
      <div class="card-header"><span class="badge ${isWeb ? "badge-high" : "badge-" + (evidence.confidence_tier || "low")}">${escapeHTML(evidence.confidence_tier ? ({high:"নিশ্চিত তথ্য",medium:"সম্ভাব্য উত্তর",low:"মূল লেখা দেখুন",source:"সরকারি উৎসের তথ্য"}[evidence.confidence_tier] || text("clause")) : text(isWeb ? "web" : "clause"))}</span>${evidence.page != null ? `<span class="ministry">${escapeHTML(text("page"))} ${escapeHTML(evidence.page)}</span>` : ""}</div>
      <h2 class="card-title">${escapeHTML(evidence.title || evidence.document_id || evidence.source_url || evidence.id)}</h2>
      ${candidate ? `<p class="low-note">${escapeHTML(text("candidate"))}</p>` : ""}
      ${evidence.explanation ? `<div class="explanation-box"><div class="explanation-label">সহজ ভাষায়:</div><div class="explanation-text">${escapeHTML(evidence.explanation)}</div></div>` : ""}
      ${renderExtracted(evidence.extracted)}
      ${!evidence.explanation ? `<p class="evidence-excerpt">${escapeHTML(excerpt(evidence, data.question))}</p>` : ""}
      <details class="source-block"><summary>${escapeHTML(text("original"))}</summary><p class="clause-text">${escapeHTML(evidence.text)}</p></details>
      <div class="provenance">
        <span>${escapeHTML(text("published"))}: ${escapeHTML(dateText(evidence.published_at))}</span>
        ${evidence.metadata && evidence.metadata.verification_method ? `<span>Verification: ${escapeHTML(evidence.metadata.verification_method)} · ${escapeHTML(evidence.metadata.date_status || "")}</span>` : ""}
        ${isWeb && evidence.checked_at ? `<span>${escapeHTML(text("checked"))}: ${escapeHTML(dateText(evidence.checked_at))}</span>` : ""}
        <span>${escapeHTML(text(isWeb ? "fetched" : "notChecked"))}</span>
      </div>
      <div class="citation"><span class="doc-id">${escapeHTML(evidence.document_id || evidence.title || "")}</span><div class="citation-links">${url ? `<a href="${escapeHTML(url)}" target="_blank" rel="noopener noreferrer" class="source-link">${escapeHTML(text("source"))}</a>` : ""}${viewer ? `<a href="${escapeHTML(viewer)}" target="_blank" rel="noopener noreferrer" class="view-link">${escapeHTML(language === "bn" ? "পিডিএফ দেখুন (পৃষ্ঠা " + evidence.page + ")" : "View PDF (page " + evidence.page + ")")}</a>` : (data.backend === "original_hybrid_two_stage" ? `<span class="no-pdf">${escapeHTML(language === "bn" ? "পিডিএফ উপলব্ধ নয়" : "PDF unavailable")}</span>` : "")}</div></div>
    </article>`;
  }
  function renderConflictCard(conflict) {
    const valuesHTML = conflict.values.map(v => `
      <div class="conflict-value ${v.is_current ? 'is-current' : 'is-superseded'}">
        <div class="conflict-value-main">
          <span class="conflict-value-text">${escapeHTML(v.value)}</span>
          <span class="conflict-value-date">(${escapeHTML(v.date_display)})</span>
        </div>
        <div class="conflict-value-doc">${escapeHTML(v.display_name || v.doc_id)}</div>
        ${v.is_current
          ? '<div class="conflict-badge conflict-current">নতুন তারিখের উৎস</div>'
          : '<div class="conflict-badge conflict-superseded">আগের তারিখের উৎস</div>'}
      </div>
    `).join('');

    return `
      <div class="conflict-card">
        <div class="conflict-header">
          <span class="conflict-icon">⚠</span>
          <div>
            <div class="conflict-title">সময়ের সাথে পরিবর্তন সনাক্ত হয়েছে</div>
            <div class="conflict-subtitle">${escapeHTML(conflict.label)} - এই তথ্যের একাধিক মান পাওয়া গেছে</div>
          </div>
        </div>
        <div class="conflict-values">
          ${valuesHTML}
        </div>
        <div class="conflict-note">
          তারিখ অনুযায়ী উৎস সাজানো হয়েছে; কোনটি আইনগতভাবে প্রযোজ্য তা এখনও যাচাই করা হয়নি।
        </div>
      </div>`;
  }


  function renderOverview(data) {
    const overview = data.overview || {};
    if (!(overview.blocks || []).length) return "";
    const all = data.evidence || [];
    const citations = ids => ids.map(id => {
      const index = all.findIndex(e => e.id === id);
      if (index < 0) return "";
      const e = all[index];
      const url = sourceViewer(e) || safeURL(e.source_url);
      const name = e.ministry || e.title || (language === "bn" ? "মূল উৎস" : "Source");
      return `<a class="source-chip" href="${escapeHTML(url || "#clause-" + index)}" ${url ? 'target="_blank" rel="noopener noreferrer"' : ""}>${escapeHTML(name)} <span>[${index + 1}]</span></a>`;
    }).join(" ");
    return `<section class="answer-overview"><h1>${language === "bn" ? "উৎসভিত্তিক ব্যাখ্যা" : "Answer from sources"}</h1>
      <p class="overview-intro">${escapeHTML(overview.intro)}</p>
      <ul class="overview-points">${overview.blocks.map(b => `<li><span>${escapeHTML(b.text)}</span> ${citations(b.evidence_ids || [])}</li>`).join("")}</ul>
      <div class="overview-foot">${language === "bn" ? "নিচে মূল clause, নথির বিবরণ ও উৎসের লিংক দেখুন।" : "Original clauses, document details and source links are below."}</div></section>`;
  }
  function renderStage6Sources(data) {
    if (data.action !== "REQUEST_RESEARCH_PERMISSION") return "";
    const offer = data.research_offer;
    let html = `<section class="status-panel status-warning"><h2>নতুন গবেষণার অনুমতি প্রয়োজন</h2><p>এই প্রশ্নের যথেষ্ট তথ্য জ্ঞানভান্ডারে নেই। সরকারি উৎস থেকে খুঁজে তথ্য যোগ করতে অনুমতি দিন।</p>`;
    if (offer && offer.available) {
      html += `<p><strong>দপ্তর:</strong> ${escapeHTML(offer.ministry)} · <strong>বিষয়:</strong> ${escapeHTML(offer.program)}</p>
        <p>${escapeHTML(offer.conditional_update_disclosure)}</p>
        <details><summary>অনুসন্ধানের পরিসর</summary><p>${escapeHTML((offer.hosts || []).join(", "))}</p><p>সর্বোচ্চ ${escapeHTML(offer.max_http_requests)} HTTP request · ${escapeHTML(offer.max_pages)} পৃষ্ঠা</p></details>
        <div class="research-controls" data-research-ticket="${escapeHTML(offer.ticket)}">
          <label><input type="checkbox" id="research-ack"> সরকারি উৎসে গবেষণা, পাওয়া readable content জ্ঞানভান্ডারে যোগ করা এবং প্রশ্নটি আবার চালানোর অনুমতি দিচ্ছি।</label>
          <div><button type="button" data-research-action="approve" disabled>গবেষণা শুরু করুন</button><button type="button" data-research-action="deny">বাতিল করুন</button></div><p class="research-state" role="status"></p></div>`;
    } else html += `<p>${escapeHTML((offer && offer.reason) || "এই বিষয়ের সরকারি উৎসের পরিসর নির্ধারণ করা যায়নি।")}</p>`;
    return html + "</section>";
  }
  function renderResults(data) {
    const route = data.route === "RAG" ? "rag" : data.route === "CLARIFY" ? "clarify" : "live";
    const found = data.status === "EVIDENCE_FOUND";
    let note = text(found ? "foundNote" : data.status === "UNAVAILABLE" ? "unavailableNote" : "verifyNote");
    if (data.status === "CLARIFICATION_REQUIRED") note = data.answer;
    let html = found ? renderOverview(data) : `<section class="status-panel status-warning"><div class="route-row"><span class="badge badge-low">${escapeHTML(text(route))}</span></div><h1>${escapeHTML(data.action === "REQUEST_RESEARCH_PERMISSION" ? "নতুন তথ্য অনুসন্ধান প্রয়োজন" : text(data.status))}</h1><p>${escapeHTML(note)}</p></section>`;
    if (data.translated) html += `<div class="translation-note"><span class="label">অনুবাদিত প্রশ্ন:</span><span class="value">${escapeHTML(data.translated)}</span></div>`;
    (data.conflicts || []).forEach(conflict => { html += renderConflictCard(conflict); });
    html += renderStage6Sources(data);
    if (!(data.overview && (data.overview.blocks || []).length) && (data.evidence || []).length && data.answer) html += `<section class="result-card"><h2 class="card-title">${language === "bn" ? "উত্তর ও সমর্থনকারী উদ্ধৃতি" : "Answer and supporting quote"}</h2><p class="stage6-clause-text">${escapeHTML(data.answer)}</p></section>`;
    if (!(data.evidence || []).length && data.answer) html += `<div class="no-results"><p>${escapeHTML(data.answer)}</p></div>`;
    (data.evidence || []).forEach((item, index) => { html += renderCard(item, index, data); });
    html += `<details class="diagnostics"><summary>${escapeHTML(text("diagnostics"))}</summary>
      <p>Generation: ${escapeHTML(data.generation || "")} · Current applicability verified: ${Boolean(data.current_policy_verified)}</p>
      <p>${escapeHTML(text("backend"))}: ${escapeHTML(data.backend)}${String(data.backend).includes("corpus_bm25") ? `<br>${escapeHTML(text("baseline"))}` : ""}</p>
      <p>${escapeHTML(text("elapsed"))}: ${escapeHTML(data.elapsed_ms)} ms</p>
      <ul>${(data.warnings || []).map(w => `<li>${escapeHTML(w)}</li>`).join("")}</ul>
      <pre>${escapeHTML((data.trace || []).join(" → "))}</pre>
    </details>`;
    document.getElementById("results-container").innerHTML = html;
    const controls = document.querySelector(".research-controls");
    if (controls) {
      const ack = controls.querySelector("#research-ack");
      const allow = controls.querySelector('[data-research-action="approve"]');
      ack.addEventListener("change", () => { allow.disabled = !ack.checked; });
      controls.querySelectorAll("[data-research-action]").forEach(button => {
        button.addEventListener("click", () => researchDecision(controls, button.dataset.researchAction));
      });
      if (researchJob && researchJob.ticket === controls.dataset.researchTicket) {
        controls.querySelectorAll("[data-research-action]").forEach(b => b.disabled = true);
        pollResearch(controls, researchJob.ticket);
      }
    }
  }
  async function researchPost(path, ticket, extra) {
    const res = await fetch(path, {method:"POST", credentials:"same-origin",
      headers:{"Content-Type":"application/json", "X-CSRF-Token":csrf()},
      body:JSON.stringify(Object.assign({ticket}, extra || {}))});
    if (!res.ok) throw new Error("Research action rejected (HTTP " + res.status + ")");
    return res.json();
  }
  async function researchDecision(controls, decision) {
    const ticket = controls.dataset.researchTicket;
    const status = controls.querySelector(".research-state");
    controls.querySelectorAll("button").forEach(b => b.disabled = true);
    try {
      const result = await researchPost("/ui/research/decision", ticket,
        {decision, allow_conditional_update:decision === "approve" && controls.querySelector("#research-ack").checked});
      status.textContent = decision === "deny" ? "অনুমতি বাতিল হয়েছে। কোনো crawl বা update হয়নি।" : "অনুমোদিত গবেষণা শুরু হয়েছে…";
      if (result.status === "crawling") {
        researchJob = {ticket};
        pollResearch(controls, ticket);
      }
    } catch (err) { status.textContent = err.message; }
  }
  function cancelControl(controls, ticket) {
    if (controls.querySelector("[data-research-cancel]")) return;
    const button = document.createElement("button");
    button.type = "button"; button.dataset.researchCancel = "1";
    button.textContent = "চলমান গবেষণা বাতিল করুন";
    button.addEventListener("click", async () => {
      button.disabled = true;
      try { await researchPost("/ui/research/cancel", ticket); pollResearch(controls, ticket); }
      catch (err) { controls.querySelector(".research-state").textContent = err.message; }
    });
    controls.appendChild(button);
  }
  function pollResearch(controls, ticket) {
    if (researchPoll) clearTimeout(researchPoll);
    const progress = {crawling:"সরকারি উৎস অনুসন্ধান",staged_unverified:"Evidence সংগ্রহ হয়েছে",processing:"HTML/PDF/OCR processing",
      verifying:"উৎসের লেখা chunk করার প্রস্তুতি",updating:"নতুন তথ্য জ্ঞানভান্ডারে যোগ হচ্ছে",activating:"জ্ঞানভান্ডার সক্রিয় হচ্ছে",
      requerying:"মূল প্রশ্ন আবার অনুসন্ধান",answer_ready:"উত্তর প্রস্তুত",research_complete:"তথ্য যোগ ও অনুসন্ধান সম্পন্ন",no_usable_evidence:"পড়ার উপযোগী তথ্য পাওয়া যায়নি",
      failed:"গবেষণা থেকে উত্তর তৈরি হয়নি",crawl_failed:"সরকারি evidence সংগ্রহ হয়নি",cancelled:"গবেষণা বাতিল হয়েছে",cancelling:"গবেষণা বন্ধ হচ্ছে",
      expired:"অনুমতির মেয়াদ শেষ",recovery_required:"Index recovery diagnostic প্রয়োজন"};
    const update = async () => {
      if (!document.contains(controls)) return;
      const status = controls.querySelector(".research-state");
      try {
        const state = await researchPost("/ui/research/status", ticket);
        const detail = state.detail || {};
        status.textContent = (progress[state.status] || state.status) + " · active index-এ নতুন item: " + state.index_writes +
          (detail.message_bn || detail.message ? " · " + (detail.message_bn || detail.message) : "");
        if (detail.issues) status.textContent += " · " + detail.issues.map(i => (i.reasons || []).join(", ")).join("; ");
        if (state.can_cancel) cancelControl(controls, ticket);
        if (["answer_ready","research_complete"].includes(state.status) && state.result) {
          researchJob = null; lastResult = state.result; renderResults(lastResult); return;
        }
        if (["crawling","processing","processed","verifying","updating","activating","requerying","cancelling","staged_unverified"].includes(state.status)) {
          researchPoll = setTimeout(update, 2000);
        } else {
          if (detail.error_type) status.textContent += " · " + detail.error_type + ": " + (detail.message || "");
          const cancel = controls.querySelector("[data-research-cancel]");
          if (cancel && !state.can_cancel) cancel.disabled = true;
        }
      } catch (err) { status.textContent = err.message; }
    };
    update();
  }
  function showLogin() {
    document.getElementById("login-panel").hidden = false;
  }
  function showError(message, question) {
    const container = document.getElementById("results-container");
    container.innerHTML = `<div class="error" role="alert"><p>${escapeHTML(message)}</p><button type="button" class="retry-button">${escapeHTML(text("retry"))}</button></div>`;
    container.querySelector("button").addEventListener("click", () => runSearch(question));
  }
  async function runSearch(question) {
    const loading = document.getElementById("loading");
    if (!loading) return;
    if (question.trim().length < 2 || question.length > 2000) { showError(text("invalid"), question); return; }
    if (!csrf()) { showLogin(); showError(text("signIn"), question); return; }
    if (activeController) activeController.abort();
    const controller = new AbortController(); activeController = controller;
    loading.textContent = text("loading"); loading.hidden = false;
    document.getElementById("results-container").innerHTML = "";
    const timeout = setTimeout(() => controller.abort(), 210000); // Stage 6 verifies the pair in a separate process
    try {
      const response = await fetch("/ui/query", {
        method: "POST", credentials: "same-origin", signal: controller.signal,
        headers: {"Content-Type":"application/json", "X-CSRF-Token":csrf()},
        body: JSON.stringify({question: question.trim(), top_k:5})
      });
      if (response.status === 401) { showLogin(); throw new Error(text("expired")); }
      if (response.status === 503) throw new Error(text("rate"));
      if (!response.ok) throw new Error(text("error"));
      lastResult = await response.json(); renderResults(lastResult);
    } catch (error) {
      if (activeController === controller) showError(error.name === "AbortError" ? text("error") : error.message, question);
    } finally {
      clearTimeout(timeout);
      if (activeController === controller) { loading.hidden = true; activeController = null; }
    }
  }
  function applyLanguage() {
    document.documentElement.lang = language;
    document.querySelectorAll("[data-bn][data-en]").forEach(el => { el.textContent = el.getAttribute("data-" + language); });
    const input = document.getElementById("question-input");
    input.placeholder = input.getAttribute("data-" + language + "-placeholder") || text("invalid");
    input.setAttribute("aria-label", language === "bn" ? "আপনার প্রশ্ন" : "Your question");
    document.getElementById("lang-toggle-link").textContent = language === "bn" ? "English" : "বাংলা";
    if (lastResult) renderResults(lastResult);
  }
  document.addEventListener("DOMContentLoaded", () => {
    const overviewStyles = document.createElement('link');
    overviewStyles.rel = 'stylesheet'; overviewStyles.href = '/static/overview.css';
    document.head.appendChild(overviewStyles);
    try { language = localStorage.getItem("unmochon-language") === "en" ? "en" : "bn"; } catch (_) {}
    applyLanguage();
    document.getElementById("lang-toggle-link").addEventListener("click", event => {
      event.preventDefault(); language = language === "bn" ? "en" : "bn";
      try { localStorage.setItem("unmochon-language", language); } catch (_) {}
      applyLanguage();
    });
    document.getElementById("search-form").addEventListener("submit", event => {
      const q = document.getElementById("question-input").value.trim();
      if (q.length < 2 || q.length > 2000) { event.preventDefault(); document.getElementById("question-input").setCustomValidity(text("invalid")); document.getElementById("question-input").reportValidity(); }
    });
    document.getElementById("question-input").addEventListener("input", event => { event.target.setCustomValidity(""); });
    if (!csrf()) showLogin();
    document.getElementById("login-form").addEventListener("submit", async event => {
      event.preventDefault(); const input = document.getElementById("access-key");
      try {
        const response = await fetch("/ui/login", {method:"POST", credentials:"same-origin", headers:{"Content-Type":"application/json"}, body:JSON.stringify({key:input.value})});
        input.value = "";
        if (!response.ok) throw new Error(text("wrongKey"));
        const result = await response.json(); document.querySelector('meta[name="ui-csrf"]').content = result.csrf;
        document.getElementById("login-panel").hidden = true;
        document.getElementById("login-error").textContent = "";
        const q = new URLSearchParams(location.search).get("q"); if (q) runSearch(q);
      } catch (error) { input.value = ""; document.getElementById("login-error").textContent = error.message; }
    });
    const q = new URLSearchParams(location.search).get("q");
    if (q && document.getElementById("results-container")) {
      document.getElementById("question-input").value = q;
      runSearch(q);
    }
  });
}());
