"""Unmochon Flask app.

Live retrieval via two-stage pipeline: bilingual translation, hybrid
BM25+dense fusion, intent classification, extractor verification with
confidence tiers. No hardcoded answers, no lookup tables - every
answer comes from live search against the ChromaDB corpus.

Endpoints:
  /                    home page
  /results             results page (renders template only)
  /ask                 JSON API: takes a question, returns ranked
                       clauses with confidence tier + PDF viewer URL
                       + human-readable display name + official URL
                       + plain-language explanation + conflict groups
  /pdfjs/<path>        serves PDF.js viewer assets
  /pdf/<ministry>/<f>  serves raw PDF files
  /logo/<name>         serves logo images
"""

import os
import sys
import json
import time
import traceback
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor

from flask import (Flask, jsonify, render_template, request,
                   send_from_directory)

# Wire pipeline modules
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts", "retrieval"))
sys.path.insert(0, os.path.join(HERE, "..", "chatbot", "scripts"))

from scripts.retrieval.search              import HybridRetriever
from scripts.retrieval.translator          import Translator
from scripts.retrieval.two_stage           import two_stage_search
from scripts.retrieval.extractor_map       import EXTRACTORS_FOR_INTENT
from chatbot.scripts.intent              import detect_intents
from chatbot.scripts.explainer           import build_plain_explanation


# ---------------------------------------------------------------
# App setup
# ---------------------------------------------------------------

app = Flask(__name__)

# Paths
from original_paths import PROJECT_ROOT, PDF_ROOT, METADATA_PATH
PROJECT_ROOT = str(PROJECT_ROOT)
PDF_ROOT = str(PDF_ROOT)
PDFJS_ROOT   = os.path.join(HERE, "static", "pdfjs")
LOGO_ROOT    = os.path.join(HERE, "static", "logo")
META_PATH = str(METADATA_PATH)

# Loaded once by the Live adapter (or lazily by original Flask /ask).
retriever = None
translator = None
DOC_METADATA = {}


def initialize(retriever_instance=None, translator_instance=None):
    global retriever, translator, DOC_METADATA
    retriever = retriever_instance or HybridRetriever()
    translator = translator_instance or Translator()
    from original_paths import METADATA_PATH
    if METADATA_PATH.exists():
        DOC_METADATA = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    else:
        DOC_METADATA = {}


# ---------------------------------------------------------------
# Ministry -> folder name mapping
# ---------------------------------------------------------------
MINISTRY_FOLDER = {
    "Social Welfare":       "social_welfare",
    "Agriculture":          "Agriculture",
    "Disaster Management":  "Disaster Management",
}


# ---------------------------------------------------------------
# Ministry inference from query keywords
# ---------------------------------------------------------------
MINISTRY_KEYWORDS = {
    "Social Welfare": [
        "বয়স্ক", "বিধবা", "প্রতিবন্ধী", "চা-শ্রমিক", "চা শ্রমিক",
        "বেদে", "দলিত", "হরিজন", "ভাতা", "সমাজকল্যাণ",
        "পিতা-মাতা", "পরিচর্যা",
        "widow", "old age", "disability", "tea worker", "allowance",
        "bede", "dalit", "harijan",
    ],
    "Agriculture": [
        "সার", "বীজ", "কৃষি", "কৃষক", "ডিলার", "উৎপাদনকারী",
        "fertilizer", "seed", "agriculture", "dealer", "farmer",
        "producer",
    ],
    "Disaster Management": [
        "দুর্যোগ", "ত্রাণ", "শিশুখাদ্য", "শিশু খাদ্য",
        "শুকনা খাবার", "শুকনা খাদ্য", "বরাদ্দ", "কমিটি গঠন",
        "disaster", "relief", "allocation", "baby food",
    ],
}


def _infer_ministry(query):
    q = query.lower()
    scores = {}
    for m, keywords in MINISTRY_KEYWORDS.items():
        s = sum(1 for kw in keywords if kw.lower() in q)
        if s > 0:
            scores[m] = s
    if not scores:
        return None
    return max(scores, key=scores.get)


# ---------------------------------------------------------------
# Metadata lookup
# ---------------------------------------------------------------

def _lookup_metadata(doc_id):
    """Guaranteed to return a dict with display_name and source_url."""
    result = {"display_name": doc_id or "", "source_url": None}
    if not doc_id:
        return result
    try:
        entry = DOC_METADATA.get(doc_id)
        if not entry:
            entry = DOC_METADATA.get(doc_id.rsplit(".pdf", 1)[0])
        if entry:
            result["display_name"] = entry.get("display_name") or doc_id
            result["source_url"]   = entry.get("source_url")
    except Exception as e:
        print(f"[_lookup_metadata] error for {doc_id}: {e}")
    return result


def _get_doc_date(doc_id):
    if not doc_id:
        return (None, None)
    entry = DOC_METADATA.get(doc_id) or \
            DOC_METADATA.get(doc_id.rsplit(".pdf", 1)[0])
    if not entry:
        return (None, None)
    return (entry.get("date_sortable"), entry.get("date_display"))


def _get_program(doc_id):
    if not doc_id:
        return None
    entry = DOC_METADATA.get(doc_id) or \
            DOC_METADATA.get(doc_id.rsplit(".pdf", 1)[0])
    if not entry:
        return None
    return entry.get("program")


def _normalize_value_for_comparison(value):
    if isinstance(value, list):
        return tuple(_normalize_value_for_comparison(v) for v in value)
    BN_TO_LATIN = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
    s = str(value).translate(BN_TO_LATIN)
    s = s.replace(",", "").replace(" ", "").strip()
    return s


# ---------------------------------------------------------------
# PDF helpers
# ---------------------------------------------------------------

def _find_pdf_for_doc(doc_id, ministry):
    folder = MINISTRY_FOLDER.get(ministry)
    search_roots = []
    if folder:
        search_roots.append(os.path.join(PDF_ROOT, folder))
    search_roots.append(PDF_ROOT)

    for root in search_roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _, files in os.walk(root):
            for fname in files:
                if not fname.lower().endswith(".pdf"):
                    continue
                base = fname.rsplit(".pdf", 1)[0]
                if base.startswith(doc_id) or doc_id.startswith(base):
                    rel = os.path.relpath(
                        os.path.join(dirpath, fname), PDF_ROOT
                    )
                    return rel.replace("\\", "/")
    return None


def _viewer_url(clause_id, doc_id, ministry, page, highlight_text,
                extracted=None):
    """PDF.js viewer URL with sentence-boundary highlighting."""
    pdf_rel = _find_pdf_for_doc(doc_id, ministry)
    if not pdf_rel:
        return None

    pdf_url = "/pdf/" + quote(pdf_rel, safe="/")

    hl = ""
    if extracted and highlight_text:
        for entry in extracted:
            val = str(entry.get("value", "")).strip()
            if not val:
                continue
            val_clean = val.split(",")[0] if "," in val else val
            idx = highlight_text.find(val_clean)
            if idx < 0:
                continue

            sentence_start = 0
            for i in range(idx - 1, -1, -1):
                if highlight_text[i] in ("।", ".", "\n"):
                    sentence_start = i + 1
                    break

            sentence_end = len(highlight_text)
            for i in range(idx + len(val_clean), len(highlight_text)):
                if highlight_text[i] in ("।", ".", "\n"):
                    sentence_end = i + 1
                    break

            hl = highlight_text[sentence_start:sentence_end].strip()
            hl = " ".join(hl.split())
            hl = _clean_ocr_artifacts(hl)

            if len(hl) > 120:
                v_idx = hl.find(val_clean)
                if v_idx >= 0:
                    trim_start = max(0, v_idx - 50)
                    trim_end = min(len(hl), v_idx + len(val_clean) + 50)
                    hl = hl[trim_start:trim_end].strip()
            break

    if not hl:
        import re
        text = " ".join((highlight_text or "").split())
        clean = re.sub(r"^[\d\.\)\(\s]+", "", text)
        hl = clean[:80]

    viewer = f"/pdfjs/web/viewer.html?file={pdf_url}"
    fragment = f"#page={page}"
    if hl:
        fragment += f"&search={quote(hl)}&phrase=true&highlight=true"
    return viewer + fragment


def _clean_ocr_artifacts(text):
    """Remove OCR errors that break PDF.js search."""
    import re
    text = re.sub(r"\s[A-Za-z]{2,4}\s", " ", text)
    text = re.sub(r"[£$€¥@#~`^]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _format_extracted(extracted):
    """Turn extractor output into user-facing dict."""
    LABELS = {
        "extract_age":                  "বয়স",
        "extract_income_limit":         "বার্ষিক আয়সীমা",
        "extract_benefit_amount":       "ভাতার পরিমাণ",
        "extract_document_requirements":"প্রয়োজনীয় কাগজপত্র",
        "extract_district_allocations": "জেলা বরাদ্দ",
        "extract_office_authority":     "কর্তৃপক্ষ",
        "extract_deadline_date":        "সময়সীমা / তারিখ",
        "extract_frequency":            "ফ্রিকোয়েন্সি",
        "extract_duration_period":      "মেয়াদ",
        "extract_penalty_fine":         "জরিমানা / শাস্তি",
    }
    out = []
    for extractor_name, entry in extracted.items():
        label = LABELS.get(extractor_name, extractor_name)
        value = entry.get("value")

        if isinstance(value, list):
            if value and isinstance(value[0], tuple):
                display = ", ".join(f"{d}: {a}" for d, a in value)
            else:
                display = ", ".join(str(v) for v in value)
        else:
            display = str(value)

        out.append({
            "label":      label,
            "value":      display,
            "confidence": entry.get("confidence", 0.0),
        })
    return out


# ---------------------------------------------------------------
# Date-aware conflict detection
# ---------------------------------------------------------------

def detect_conflicts(results):
    """Scan results for same extractor + different values across
    documents WITHIN THE SAME PROGRAM."""
    labels = {
        "extract_age":                   "\u09ac\u09df\u09b8",
        "extract_income_limit":          "\u09ac\u09be\u09b0\u09cd\u09b7\u09bf\u0995 \u0986\u09df\u09b8\u09c0\u09ae\u09be",
        "extract_benefit_amount":        "\u09ad\u09be\u09a4\u09be\u09b0 \u09aa\u09b0\u09bf\u09ae\u09be\u09a3",
        "extract_document_requirements": "\u09aa\u09cd\u09b0\u09df\u09cb\u099c\u09a8\u09c0\u09df \u0995\u09be\u0997\u099c\u09aa\u09a4\u09cd\u09b0",
        "extract_district_allocations":  "\u099c\u09c7\u09b2\u09be \u09ac\u09b0\u09be\u09a6\u09cd\u09a6",
        "extract_office_authority":      "\u0995\u09b0\u09cd\u09a4\u09c3\u09aa\u0995\u09cd\u09b7",
        "extract_deadline_date":         "\u09b8\u09ae\u09df\u09b8\u09c0\u09ae\u09be",
        "extract_frequency":             "\u09ab\u09cd\u09b0\u09bf\u0995\u09cb\u09df\u09c7\u09a8\u09cd\u09b8\u09bf",
        "extract_duration_period":       "\u09ae\u09c7\u09df\u09be\u09a6",
        "extract_penalty_fine":          "\u099c\u09b0\u09bf\u09ae\u09be\u09a8\u09be",
    }

    by_group = {}
    for rec in results:
        program = _get_program(rec["doc_id"])
        if not program:
            continue

        for ext_name, entry in rec.get("extracted", {}).items():
            value = entry.get("value")
            conf  = entry.get("confidence", 0.0)
            if not value or conf < 0.85:
                continue
            norm_val = _normalize_value_for_comparison(value)
            sortable, display = _get_doc_date(rec["doc_id"])
            meta = _lookup_metadata(rec["doc_id"])

            group_key = (program, ext_name)
            by_group.setdefault(group_key, []).append({
                "value":         value,
                "norm_value":    norm_val,
                "doc_id":        rec["doc_id"],
                "display_name":  meta["display_name"],
                "date_sortable": sortable,
                "date_display":  display,
            })

    conflicts = []
    for (program, ext_name), records in by_group.items():
        unique_docs = {rec["doc_id"] for rec in records}
        if len(unique_docs) < 2:
            continue

        unique_values = set()
        for rec in records:
            nv = rec["norm_value"]
            unique_values.add(nv if not isinstance(nv, tuple) else nv)
        if len(unique_values) < 2:
            continue

        by_value = {}
        for rec in records:
            nv = rec["norm_value"]
            key_val = nv if not isinstance(nv, tuple) else str(nv)
            existing = by_value.get(key_val)
            if existing is None or \
               (rec["date_sortable"] or "") > (existing["date_sortable"] or ""):
                by_value[key_val] = rec
        unique_records = list(by_value.values())

        unique_records.sort(
            key=lambda x: x["date_sortable"] or "",
            reverse=True,
        )

        if len(unique_records) < 2:
            continue

        conflict_values = []
        for i, rec in enumerate(unique_records):
            display_val = rec["value"]
            if isinstance(display_val, list):
                if display_val and isinstance(display_val[0], tuple):
                    display_val = "; ".join(
                        f"{d}: {a}" for d, a in display_val[:3]
                    )
                else:
                    display_val = ", ".join(str(v) for v in display_val[:5])
            else:
                display_val = str(display_val)

            conflict_values.append({
                "value":        display_val,
                "doc_id":       rec["doc_id"],
                "display_name": rec["display_name"],
                "date_display": rec["date_display"] or
                                "\u09a4\u09be\u09b0\u09bf\u0996 \u0985\u099c\u09be\u09a8\u09be",
                "is_current":   i == 0,
            })

        conflicts.append({
            "extractor": ext_name,
            "label":     labels.get(ext_name, ext_name),
            "program":   program,
            "values":    conflict_values,
        })

    return conflicts


# ---------------------------------------------------------------
# Routes
# ---------------------------------------------------------------

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/results")
def results_page():
    return render_template("results.html")


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json(force=True) or {}
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "empty question"}), 400
    if retriever is None:
        initialize()
    return jsonify(search_question(question))


def search_question(question, return_k=5):
    """Original UI query pipeline, reused verbatim by Live's adapter."""
    t_start = time.time()
    # ---- translation ----
    t0 = time.time()
    translated = translator.to_bengali(question)
    print(f"[timing] translate: {time.time()-t0:.2f}s")

    # ---- intent + ministry ----
    t0 = time.time()
    intents = detect_intents(translated)
    ministry = _infer_ministry(translated)
    print(f"[timing] intent+ministry: {time.time()-t0:.2f}s")

    # ---- retrieval ----
    t0 = time.time()
    results = two_stage_search(
        retriever             = retriever,
        question              = translated,
        intents               = intents,
        extractors_for_intent = EXTRACTORS_FOR_INTENT,
        ministry              = ministry,
        stage1_k              = 100,
        top_docs              = 3,
        return_k              = return_k,
    )
    print(f"[timing] search: {time.time()-t0:.2f}s")

    if not results:
        print(f"[timing] TOTAL: {time.time()-t_start:.2f}s")
        return {
            "question":   question,
            "translated": translated if translated != question else None,
            "intents":    intents,
            "ministry":   ministry,
            "results":    [],
            "conflicts":  [],
            "note":       "কোনো ফলাফল পাওয়া যায়নি।",
        }

    if results[0].get("confidence_tier") == "out_of_scope":
        return {"question": question, "translated": translated if translated != question else None,
                "intents": intents, "ministry": ministry, "results": results, "conflicts": [],
                "note": results[0].get("note", "")}

    # Build viewer URLs and metadata for each result (fast, no I/O)
    t0 = time.time()
    result_data = []
    for r in results:
        extracted = r.get("extracted", {})
        result_data.append({
            "r":         r,
            "extracted": extracted,
            "tier":      r.get("confidence_tier", "medium"),
            "viewer":    _viewer_url(
                clause_id      = r["id"],
                doc_id         = r["doc_id"],
                ministry       = r["ministry"],
                page           = r.get("page", 1),
                highlight_text = r["text"],
                extracted      = _format_extracted(extracted),
            ),
            "meta":      _lookup_metadata(r["doc_id"]),
        })
    print(f"[timing] prepare: {time.time()-t0:.2f}s")

    # ---- explanations (parallel) ----
    t0 = time.time()

    def _explain_one(item):
        try:
            return build_plain_explanation(item["r"]["text"], item["extracted"])
        except Exception as e:
            print(f"[ask] explanation error: {e}")
            return None

    with ThreadPoolExecutor(max_workers=5) as executor:
        explanations = list(executor.map(_explain_one, result_data))
    print(f"[timing] explanations: {time.time()-t0:.2f}s")

    response_results = []
    for item, explanation in zip(result_data, explanations):
        r = item["r"]
        response_results.append({
            "clause_id":       r["id"],
            "doc_id":          r["doc_id"],
            "display_name":    item["meta"]["display_name"],
            "source_url":      item["meta"]["source_url"],
            "ministry":        r["ministry"],
            "page":            r.get("page", 1),
            "confidence_tier": item["tier"],
            "clause_text":     r["text"],
            "extracted":       _format_extracted(item["extracted"]),
            "viewer_url":      item["viewer"],
            "explanation":     explanation,
            "note":            r.get("note"),
            "bbox":            r.get("bbox", ""),
            "metadata":        retriever.collection.get(ids=[r["id"]], include=["metadatas"])["metadatas"][0],
            "document_metadata": dict(DOC_METADATA.get(r["doc_id"]) or DOC_METADATA.get(r["doc_id"].removesuffix(".pdf")) or {}),
        })

    # ---- conflicts ----
    t0 = time.time()
    try:
        conflicts = detect_conflicts(results)
    except Exception as e:
        print(f"[ask] detect_conflicts error: {e}")
        traceback.print_exc()
        conflicts = []
    print(f"[timing] conflicts: {time.time()-t0:.2f}s")

    print(f"[timing] TOTAL: {time.time()-t_start:.2f}s")

    return {
        "question":   question,
        "translated": translated if translated != question else None,
        "intents":    intents,
        "ministry":   ministry,
        "results":    response_results,
        "conflicts":  conflicts,
    }


# ---------------------------------------------------------------
# Static assets
# ---------------------------------------------------------------

@app.route("/pdfjs/<path:filename>")
def pdfjs_asset(filename):
    return send_from_directory(PDFJS_ROOT, filename)


@app.route("/pdf/<path:pdf_rel>")
def serve_pdf(pdf_rel):
    return send_from_directory(PDF_ROOT, pdf_rel)


@app.route("/logo/<path:name>")
def serve_logo(name):
    return send_from_directory(LOGO_ROOT, name)


# ---------------------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)