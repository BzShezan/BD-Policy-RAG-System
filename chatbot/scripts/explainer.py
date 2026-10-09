"""Plain-language explanation of retrieved clauses.

Combines three optimizations for defense-day reliability:
  1. Multi-key rotation: reads all keys from .gemini_keys, tries
     next one when current is rate-limited (429).
  2. Disk cache: caches (clause_hash + extracted_hash) -> explanation.
     Repeat queries are instant, no API call needed.
  3. Parallel calls: designed to be called concurrently from Flask
     via ThreadPoolExecutor (see app.py).

Design principle unchanged: extractor-verified facts drive the
explanation. LLM refines phrasing but is constrained to those facts.
LLM output must contain all extracted values or is rejected.
"""

import os
import json
import hashlib
import re
import time

# ---------------------------------------------------------------
# API key loading - supports multiple keys for quota rotation
# ---------------------------------------------------------------

def _load_api_keys():
    """Load all API keys from .gemini_keys (one per line) or
    .gemini_key (single key). Returns list of keys."""
    # First, try .gemini_keys (plural, multi-key file)
    multi_path = os.path.join(
        os.path.dirname(__file__), "..", "..", ".gemini_keys"
    )
    if os.path.exists(multi_path):
        with open(multi_path, "r") as f:
            keys = [line.strip() for line in f
                    if line.strip() and not line.startswith("#")]
        if keys:
            print(f"[explainer] loaded {len(keys)} API keys")
            return keys

    # Fallback: single-key file
    single_path = os.path.join(
        os.path.dirname(__file__), "..", "..", ".gemini_key"
    )
    if os.path.exists(single_path):
        with open(single_path, "r") as f:
            key = f.read().strip()
        if key:
            return [key]

    # Fallback: environment variable
    env_key = os.environ.get("GEMINI_API_KEY", "")
    if env_key:
        return [env_key]

    return []


API_KEYS = _load_api_keys()
# Track which keys are currently rate-limited (429).
# Reset if all become exhausted (chance quota reset happened).
_KEY_FAILURES = {i: 0 for i in range(len(API_KEYS))}
_CURRENT_KEY_IDX = 0


def _get_next_available_key():
    """Return (index, key) of next key with fewer than 3 failures.
    If all keys have failed, resets counters and returns first key."""
    global _CURRENT_KEY_IDX
    if not API_KEYS:
        return None, None

    for attempt in range(len(API_KEYS)):
        idx = (_CURRENT_KEY_IDX + attempt) % len(API_KEYS)
        if _KEY_FAILURES[idx] < 3:
            _CURRENT_KEY_IDX = idx
            return idx, API_KEYS[idx]

    # All keys have failed >=3 times, reset and try again from key 0
    print("[explainer] all keys rate-limited, resetting counters")
    for k in _KEY_FAILURES:
        _KEY_FAILURES[k] = 0
    _CURRENT_KEY_IDX = 0
    return 0, API_KEYS[0]


# ---------------------------------------------------------------
# Disk-based cache
# ---------------------------------------------------------------
# Cached explanations survive across restarts. Cache key is a hash
# of the clause + extracted values, so identical requests return
# instantly without hitting the API.

CACHE_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "explanation_cache"
)
os.makedirs(CACHE_DIR, exist_ok=True)


def _cache_key(clause_text, extracted):
    """Deterministic hash of the inputs. Same inputs -> same key."""
    # Sort extracted keys for stable hashing regardless of dict order
    ext_repr = json.dumps(
        {k: str(v.get("value", "")) for k, v in sorted(extracted.items())},
        ensure_ascii=False,
    )
    text_hash = hashlib.sha256(
        (clause_text[:500] + "||" + ext_repr).encode("utf-8")
    ).hexdigest()
    return text_hash[:16]   # short prefix is enough


def _cache_get(cache_key):
    """Read cached explanation, or None if not present."""
    path = os.path.join(CACHE_DIR, cache_key + ".txt")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    return None


def _cache_set(cache_key, explanation):
    """Persist explanation to disk cache."""
    path = os.path.join(CACHE_DIR, cache_key + ".txt")
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(explanation)
    except Exception as e:
        print(f"[explainer] cache write failed: {e}")


# ---------------------------------------------------------------
# Digit normalization helpers
# ---------------------------------------------------------------

LATIN_TO_BN = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
BN_TO_LATIN = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")


def _normalize_digits(s):
    return str(s).translate(BN_TO_LATIN)


# ---------------------------------------------------------------
# Template fallback (guaranteed safe)
# ---------------------------------------------------------------

TEMPLATES_BN = {
    "extract_age":
        "এই ভাতা পাওয়ার জন্য আবেদনকারীর বয়স কমপক্ষে {value} বছর হতে হবে।",
    "extract_income_limit":
        "এই ভাতা পেতে হলে আবেদনকারীর বছরের মোট আয় {value} টাকার বেশি হওয়া যাবে না।",
    "extract_benefit_amount":
        "সরকার থেকে {value} টাকা ভাতা প্রদান করা হয়।",
    "extract_document_requirements":
        "আবেদনের সময় এই কাগজপত্র জমা দিতে হবে: {value}।",
    "extract_district_allocations":
        "বিভিন্ন জেলার জন্য নির্ধারিত বরাদ্দ: {value}।",
    "extract_office_authority":
        "এই বিষয়ে দায়িত্বপ্রাপ্ত কর্তৃপক্ষ হলো {value}।",
    "extract_deadline_date":
        "এই কাজের সময়সীমা: {value}।",
    "extract_frequency":
        "এই সুবিধা {value} প্রদান করা হয়।",
    "extract_duration_period":
        "এই সুবিধার মেয়াদ {value}।",
    "extract_penalty_fine":
        "নিয়ম লঙ্ঘন করলে {value} হতে পারে।",
}


def _format_extracted_value(value):
    if isinstance(value, list):
        if value and isinstance(value[0], tuple):
            return "; ".join(f"{d}: {a} টাকা" for d, a in value[:3])
        return ", ".join(str(v) for v in value[:5])
    return str(value)


def _build_template_explanation(extracted):
    if not extracted:
        return None
    parts = []
    for ext_name, entry in extracted.items():
        value = entry.get("value")
        if not value:
            continue
        template = TEMPLATES_BN.get(ext_name)
        if not template:
            continue
        val_str = _format_extracted_value(value)
        if len(val_str) > 100:
            val_str = val_str[:97] + "..."
        parts.append(template.format(value=val_str))
    return " ".join(parts) if parts else None


# ---------------------------------------------------------------
# LLM refinement with multi-key rotation
# ---------------------------------------------------------------
def _refine_with_llm(clause_text, extracted, template_text):
    import time
    t_start = time.time()
    ...
    # at end, before return
    print(f"[explainer] LLM call took {time.time()-t_start:.2f}s")
    return refined



def _refine_with_llm(clause_text, extracted, template_text):
    """Try each available API key on rate-limit failure. Returns
    None only if all keys are exhausted or refined output fails
    validation."""
    if not API_KEYS:
        return None

    try:
        import google.generativeai as genai
    except ImportError:
        return None

    # Build the prompt once (same for all keys)
    facts_bn = []
    for ext_name, entry in extracted.items():
        val = _format_extracted_value(entry.get("value"))
        val_bn = val.translate(LATIN_TO_BN)
        facts_bn.append(val_bn)
    facts_bn_str = " | ".join(facts_bn)

    prompt = f"""নিচের বাক্যটিকে আরো সহজ ও সাবলীল বাংলায় লেখ। মূল সংখ্যা এবং তথ্য অপরিবর্তিত রাখো।

তথ্য: {facts_bn_str}

বাক্য: {template_text}

সহজ ভাষায় ২ বাক্যে লেখ। শুধু বাংলা বাক্য, কোনো ভূমিকা বা মন্তব্য নয়।"""

    # Try each key up to 3 times (some 429s are transient)
    max_attempts = min(len(API_KEYS) * 2, 6)
    for attempt in range(max_attempts):
        key_idx, api_key = _get_next_available_key()
        if not api_key:
            return None

        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(os.getenv("GEMINI_MODEL", "gemini-3.6-flash"))
            response = model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.2,
                    "max_output_tokens": 400,
                },
            )
            refined = response.text.strip()

            # Reset failure counter on success
            _KEY_FAILURES[key_idx] = 0

            # Clean scaffolding markers
            cleanup_markers = [
                "*", "Let's", "Draft", "Note:", "নোট:", "Explanation:",
                "ব্যাখ্যা:", "উত্তর:", "Response:", "Refine",
            ]
            lines = refined.split("\n")
            clean_lines = []
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    continue
                if any(stripped.lstrip("*# ").startswith(m) for m in cleanup_markers):
                    break
                clean_lines.append(stripped)
            refined = " ".join(clean_lines).strip()
            refined = refined.strip("*#\"' \n")

            # Strip inline meta labels like (Simple)
            refined = re.sub(
                r"\s*\(\s*(Simple|Explanation|Note|Draft|Refined|Version)\s*\)\s*$",
                "",
                refined,
                flags=re.IGNORECASE,
            ).strip()

            # Validate all extracted values appear
            refined_normalized = _normalize_digits(refined)
            for entry in extracted.values():
                val = entry.get("value")
                if isinstance(val, list):
                    if val and not any(
                        _normalize_digits(v) in refined_normalized
                        for v in val[:3]
                    ):
                        return None
                elif val and _normalize_digits(val) not in refined_normalized:
                    return None

            if len(refined) < 20 or len(refined) > 600:
                return None

            return refined

        except Exception as e:
            err_str = str(e).lower()
            # Rate-limit signal: mark this key as failed, try next
            if "429" in err_str or "quota" in err_str or "rate" in err_str:
                _KEY_FAILURES[key_idx] += 1
                # Move to next key
                global _CURRENT_KEY_IDX
                _CURRENT_KEY_IDX = (key_idx + 1) % len(API_KEYS)
                print(f"[explainer] key {key_idx} rate-limited, trying next")
                continue
            # Other error: log and give up
            print(f"[explainer] LLM refinement failed: {e}")
            return None

    return None


# ---------------------------------------------------------------
# Public API
# ---------------------------------------------------------------

def build_plain_explanation(clause_text, extracted):
    """Build a plain-language explanation of the retrieved clause.

    Optimized flow:
      1. Check disk cache first (instant if hit)
      2. Try LLM refinement (multi-key rotation on rate limit)
      3. Fall back to safe template if LLM unavailable
      4. Cache successful outputs

    Returns None if no extractors fired (nothing to explain)."""
    if not extracted:
        return None

    # Check cache first - this is the fastest path
    cache_key = _cache_key(clause_text, extracted)
    cached = _cache_get(cache_key)
    if cached:
        return cached

    template = _build_template_explanation(extracted)
    if not template:
        return None

    # Try LLM refinement
    refined = _refine_with_llm(clause_text, extracted, template)
    result = refined if refined else template

    # Cache the result (both LLM-refined and template outputs)
    _cache_set(cache_key, result)

    return result