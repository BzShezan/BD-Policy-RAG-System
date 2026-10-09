// Original Unmochon visual shell, connected to the existing v1 orchestration data.
// Browser sessions and CSRF protect requests; the API key never lives in this file.
(function () {
  "use strict";
  let language = "bn";
  let lastResult = null;
  let activeController = null;
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
  function renderExtracted(extracted) {
    // Original UI's extracted-values markup, using the original pipeline output.
    if (!extracted || !extracted.length) return "";
    return `<div class="extracted-values">${extracted.map(e => `<div class="extracted-row"><span class="ex-label">${escapeHTML(e.label)}:</span><span class="ex-value">${escapeHTML(e.value)}</span></div>`).join("")}</div>`;
  }
  function renderCard(evidence, index, data) {
    const url = safeURL(evidence.source_url);
    const viewer = viewerURL(evidence.viewer_url);
    const isWeb = evidence.source_kind === "official_web";
    const candidate = data.status !== "EVIDENCE_FOUND" && !isWeb;
    return `<article class="result-card${index === 0 ? " result-card-top" : ""}">
      <div class="card-header"><span class="badge ${isWeb ? "badge-high" : "badge-" + (evidence.confidence_tier || "low")}">${escapeHTML(evidence.confidence_tier ? ({high:"নিশ্চিত তথ্য",medium:"সম্ভাব্য উত্তর",low:"মূল লেখা দেখুন"}[evidence.confidence_tier] || text("clause")) : text(isWeb ? "web" : "clause"))}</span>${evidence.page != null ? `<span class="ministry">${escapeHTML(text("page"))} ${escapeHTML(evidence.page)}</span>` : ""}</div>
      <h2 class="card-title">${escapeHTML(evidence.title || evidence.document_id || evidence.source_url || evidence.id)}</h2>
      ${candidate ? `<p class="low-note">${escapeHTML(text("candidate"))}</p>` : ""}
      ${evidence.explanation ? `<div class="explanation-box"><div class="explanation-label">সহজ ভাষায়:</div><div class="explanation-text">${escapeHTML(evidence.explanation)}</div></div>` : ""}
      ${renderExtracted(evidence.extracted)}
      <p class="evidence-excerpt">${escapeHTML(excerpt(evidence, data.question))}</p>
      <details class="source-block"><summary>${escapeHTML(text("original"))}</summary><p class="clause-text">${escapeHTML(evidence.text)}</p></details>
      <div class="provenance">
        <span>${escapeHTML(text("published"))}: ${escapeHTML(dateText(evidence.published_at))}</span>
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
          ? '<div class="conflict-badge conflict-current">বর্তমান</div>'
          : '<div class="conflict-badge conflict-superseded">পুরাতন</div>'}
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
          সবচেয়ে সাম্প্রতিক ডকুমেন্ট অনুযায়ী "বর্তমান" মান প্রযোজ্য।
        </div>
      </div>`;
  }


  function renderResults(data) {
    const route = data.route === "RAG" ? "rag" : data.route === "CLARIFY" ? "clarify" : "live";
    const found = data.status === "EVIDENCE_FOUND";
    let note = text(found ? "foundNote" : data.status === "UNAVAILABLE" ? "unavailableNote" : "verifyNote");
    if (data.status === "CLARIFICATION_REQUIRED") note = data.answer;
    let html = `<section class="status-panel${found ? "" : " status-warning"}">
      <div class="route-row"><span class="badge badge-low">${escapeHTML(text(route))}</span>${data.service ? `<span class="ministry">${escapeHTML(data.service)}</span>` : ""}</div>
      <h1>${escapeHTML(text(data.status))}</h1><p>${escapeHTML(note)}</p>
    </section>`;
    if (data.translated) html += `<div class="translation-note"><span class="label">অনুবাদিত প্রশ্ন:</span><span class="value">${escapeHTML(data.translated)}</span></div>`;
    (data.conflicts || []).forEach(conflict => { html += renderConflictCard(conflict); });
    if (!(data.evidence || []).length && data.answer) html += `<div class="no-results"><p>${escapeHTML(data.answer)}</p></div>`;
    (data.evidence || []).forEach((item, index) => { html += renderCard(item, index, data); });
    html += `<details class="diagnostics"><summary>${escapeHTML(text("diagnostics"))}</summary>
      <p>${escapeHTML(text("backend"))}: ${escapeHTML(data.backend)}${String(data.backend).includes("corpus_bm25") ? `<br>${escapeHTML(text("baseline"))}` : ""}</p>
      <p>${escapeHTML(text("elapsed"))}: ${escapeHTML(data.elapsed_ms)} ms</p>
      <ul>${(data.warnings || []).map(w => `<li>${escapeHTML(w)}</li>`).join("")}</ul>
      <pre>${escapeHTML((data.trace || []).join(" → "))}</pre>
    </details>`;
    document.getElementById("results-container").innerHTML = html;
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
    const timeout = setTimeout(() => controller.abort(), 75000);
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
