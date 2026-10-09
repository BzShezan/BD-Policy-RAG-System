// Unmochon frontend.
// Reads the search query from the URL, hits /ask, renders the ranked
// results with confidence-tier badges and PDF viewer links. Handles
// three response shapes: normal results, empty results, and out-of-
// scope (query is unrelated to the corpus).
//
// Also renders conflict summary cards at the top when the pipeline
// detects the same extractable fact with different values across
// documents (date-aware supersession, previews PT-NLI logic).

(function () {
  "use strict";

  // ---- On load, run the search if there's a query in the URL ----
  document.addEventListener("DOMContentLoaded", function () {
    const params = new URLSearchParams(window.location.search);
    const q = params.get("q");
    if (q) {
      document.getElementById("question-input").value = q;
      runSearch(q);
    }
    wireLangToggle();
  });


  // ---- Search execution ----
  function runSearch(question) {
    const loading   = document.getElementById("loading");
    const container = document.getElementById("results-container");
    loading.style.display = "block";
    container.innerHTML   = "";

    fetch("/ask", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ question: question }),
    })
    .then(r => r.json())
    .then(data => {
      loading.style.display = "none";
      renderResults(data);
    })
    .catch(err => {
      loading.style.display = "none";
      container.innerHTML =
        `<div class="error">অনুসন্ধানে সমস্যা হয়েছে: ${err}</div>`;
    });
  }


  // ---- Rendering ----
  function renderResults(data) {
    const container = document.getElementById("results-container");

    // Case 1: empty result set
    if (!data.results || data.results.length === 0) {
      container.innerHTML = `
        <div class="no-results">
          <p>${escapeHTML(data.note || "কোনো ফলাফল পাওয়া যায়নি।")}</p>
        </div>`;
      return;
    }

    // Case 2: out-of-scope guard fired
    if (data.results.length === 1
        && data.results[0].confidence_tier === "out_of_scope") {
      container.innerHTML = `
        <div class="out-of-scope-card">
          <h3>প্রাসঙ্গিক তথ্য পাওয়া যায়নি</h3>
          <p>${escapeHTML(data.results[0].note || '')}</p>
        </div>`;
      return;
    }

    // Case 3: normal results
    let html = "";

    // Optional translation notice for English queries
    if (data.translated) {
      html += `
        <div class="translation-note">
          <span class="label">অনুবাদিত প্রশ্ন:</span>
          <span class="value">${escapeHTML(data.translated)}</span>
        </div>`;
    }

    // Conflict summary cards - shown when top results contain
    // different values for the same extractable fact across
    // different-dated documents. Renders above regular result cards.
    if (data.conflicts && data.conflicts.length > 0) {
      for (const conflict of data.conflicts) {
        html += renderConflictCard(conflict);
      }
    }

    // Regular result cards
    data.results.forEach((res, i) => {
      html += renderCard(res, i === 0);
    });

    container.innerHTML = html;
  }


  function renderCard(res, isTop) {
    const tier      = res.confidence_tier || "medium";
    const tierLabel = tierText(tier);
    const badgeCls  = `badge badge-${tier}`;
    const cardCls   = "result-card" + (isTop ? " result-card-top" : "");

    // Ministry logo based on which ministry the source doc belongs to
    const ministryLogo = ministryLogoFile(res.ministry);
    const logoHTML     = ministryLogo
      ? `<img src="/logo/${ministryLogo}" class="ministry-logo" alt="${escapeHTML(res.ministry || '')}">`
      : "";

    // Extracted values as a list
    let extractedHTML = "";
    if (res.extracted && res.extracted.length > 0) {
      extractedHTML =
        `<div class="extracted-values">` +
        res.extracted.map(e =>
          `<div class="extracted-row">
             <span class="ex-label">${escapeHTML(e.label)}:</span>
             <span class="ex-value">${escapeHTML(e.value)}</span>
           </div>`
        ).join("") +
        `</div>`;
    } else if (tier === "low") {
      extractedHTML =
        `<div class="low-note">
           কোনো নির্দিষ্ট তথ্য নিষ্কাশন করা যায়নি। মূল লেখা দেখুন।
         </div>`;
    }

    // Plain-language explanation from the pipeline
    let explanationHTML = "";
    if (res.explanation) {
      explanationHTML = `
        <div class="explanation-box">
          <div class="explanation-label">সহজ ভাষায়:</div>
          <div class="explanation-text">${escapeHTML(res.explanation)}</div>
        </div>`;
    }

    const cluePreview = escapeHTML((res.clause_text || "").slice(0, 300));
    const source = `
      <details class="source-block">
        <summary>মূল লেখা</summary>
        <p class="clause-text">${cluePreview}...</p>
      </details>`;

    const viewerLink = res.viewer_url
      ? `<a href="${res.viewer_url}" target="_blank" class="view-link">
           পিডিএফ দেখুন (পৃষ্ঠা ${res.page})
         </a>`
      : `<span class="no-pdf">পিডিএফ উপলব্ধ নয়</span>`;

    return `
      <div class="${cardCls}">
        ${logoHTML}
        <div class="card-header">
          <span class="${badgeCls}">${tierLabel}</span>
          <span class="ministry">${escapeHTML(res.ministry || "")}</span>
        </div>

        ${explanationHTML}
        ${extractedHTML}
        ${source}

        <div class="citation">
          <span class="doc-id">${escapeHTML(res.display_name || res.doc_id || "")}</span>
          <div class="citation-links">
            ${res.source_url
              ? `<a href="${escapeHTML(res.source_url)}" target="_blank" rel="noopener" class="source-link">সরকারি লিঙ্ক ↗</a>`
              : ""}
            ${viewerLink}
          </div>
        </div>
      </div>`;
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


  function tierText(tier) {
    switch (tier) {
      case "high":   return "নিশ্চিত তথ্য";
      case "medium": return "সম্ভাব্য উত্তর";
      case "low":    return "মূল লেখা দেখুন";
      default:       return "";
    }
  }


  function ministryLogoFile(ministry) {
    if (!ministry) return null;
    const m = ministry.toLowerCase();
    if (m.includes("social")   || m.includes("সমাজ"))   return "ministry_sw.png";
    if (m.includes("agri")     || m.includes("কৃষি"))   return "ministry_ag.png";
    if (m.includes("disaster") || m.includes("দুর্যোগ")) return "ministry_dm.png";
    return null;
  }


  function escapeHTML(s) {
    if (s === null || s === undefined) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }


  // ---- Bilingual toggle ----
  function wireLangToggle() {
    const link = document.getElementById("lang-toggle-link");
    if (!link) return;

    let lang = localStorage.getItem("unmochon_lang") || "bn";
    applyLang(lang);

    link.addEventListener("click", function (e) {
      e.preventDefault();
      lang = (lang === "bn") ? "en" : "bn";
      localStorage.setItem("unmochon_lang", lang);
      applyLang(lang);
    });
  }


  function applyLang(lang) {
    document.querySelectorAll("[data-bn]").forEach(el => {
      const bn = el.getAttribute("data-bn");
      const en = el.getAttribute("data-en");
      if (bn && en) el.textContent = (lang === "bn") ? bn : en;
    });

    document.querySelectorAll("[data-bn-placeholder]").forEach(el => {
      const bn = el.getAttribute("data-bn-placeholder");
      const en = el.getAttribute("data-en-placeholder");
      if (bn && en) el.setAttribute("placeholder", (lang === "bn") ? bn : en);
    });

    const link = document.getElementById("lang-toggle-link");
    if (link) link.textContent = (lang === "bn") ? "English" : "বাংলা";
  }

})();