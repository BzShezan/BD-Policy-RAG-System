"""Rule-based entity extraction for policy clauses.

Contextual, not naive keyword matching - a bare টাকা/taka regex pulls
noise from budget allocation tables, not actual policy rules. Every
pattern here requires the number to sit near specific trigger words
that indicate it's stating a rule, not a disbursement figure.

Different ministries use genuinely different vocabulary and clause
structure, confirmed against real text from each:
  - Social Welfare: age thresholds, income limits, benefit amounts
  - Agriculture: required documents for dealer/producer registration
  - Disaster Management: district-level relief allocation amounts

Age extraction goes one step further: after matching a number near
বয়স/বছর, it checks for eligibility markers ("বা তদুর্ধ", "বয়সের পুরুষ")
vs narrative markers ("বছর বয়স্ক <name>", "বলেন") and adjusts
confidence accordingly. This distinguishes a policy rule from a
biographical mention of someone's age - a real failure mode observed
when the tea worker case study report ranked above the actual old-age
allowance policy for age eligibility queries.

Returns entities with a confidence score, feeding directly into the
confidence-gated fallback layer - low-confidence extractions should
never be presented as a fact.
"""

import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from chatbot.scripts.normalize import to_ascii_digits


# ---- AGE (Social Welfare) ----
# Base pattern: number near "বয়স" and "বছর" in either order, within
# a short window. Matches liberally by design - the eligibility /
# narrative check below is what separates rules from mentions.
AGE_PATTERN = re.compile(
    r'বয়স[^\d]{0,15}(\d{1,3})[^\d]{0,10}বছর'
    r'|(\d{1,3})[^\d]{0,10}বছর[^\d]{0,15}বয়স'
    r'|\bage\b[^\d]{0,15}(\d{1,3})[^\w]{0,10}years?'
)

# Eligibility markers: appear in policy rule clauses stating who is
# entitled to something. Presence near the matched age = strong signal
# that this is a rule, not a biographical mention.
ELIGIBILITY_MARKERS = [
    "বা তদুর্ধ", "বা তদূর্ধ্ব", "বা তার বেশি", "বা তার উর্ধে",
    "বছরের উর্ধে", "বছরের ঊর্ধ্বে",     # NEW - matches widow 2025 phrasing
    "সর্বনিম্ন", "নির্ধারিত বয়সের", "বয়সের পুরুষ", "বয়সের মহিলা",
    "or above", "or older", "minimum age",
]

# Narrative markers: signal this clause is a story, quote, or case
# study - not a rule. Presence should demote confidence sharply.
NARRATIVE_MARKERS = [
    "বছর বয়স্ক ",   # "X-year-old <name>" - biographical
    "বছর বয়সী ",
    "বলেন",           # "said" - direct quote context
    "প্রবন্ধে",       # "in the article"
    "case study", "case Study", "কেস স্টাডি",
]


# ---- INCOME LIMIT (Social Welfare) ----
# Requires the amount to sit near a limit/ceiling word - অনূর্ধ্ব
# (not exceeding), ন্যুনতম (minimum), আয়সীমা (income limit) - not
# just any amount near the word "income". Gap widened to 30 chars to
# bridge parenthetical word-form explanations, e.g. "৩৬,০০০ (ছত্রিশ
# হাজার) টাকা".
INCOME_PATTERN = re.compile(
    r'(?:অনূর্ধ্ব|আয়সীমা|আয়[^\d]{0,10}(?:অনূর্ধ্ব|সীমা))[^\d]{0,15}([\d,]{3,})[^\d]{0,30}টাকা'
    r'|income[^\d]{0,20}(?:limit|ceiling|not exceed(?:ing)?)[^\d]{0,15}([\d,]{3,})'
)

# ---- BENEFIT AMOUNT (Social Welfare) ----
# Amount near ভাতা (allowance) / সহায়তা (assistance) / প্রদেয় (payable) /
# পাবে (will receive) - distinguishes a benefit rate from a budget figure.
AMOUNT_PATTERN = re.compile(
    r'(?:মাসিক|প্রতি\s?মাসে)?[^\d]{0,10}(?:ন্যুনতম|সর্বোচ্চ)?[^\d]{0,10}'
    r'([\d,]{2,})[^\d]{0,25}টাকা[^\d]{0,20}(?:ভাতা|সহায়তা|প্রদেয়|পাবে|প্রদান)'
    r'|(?:ভাতা|সহায়তা|প্রদেয়|পাবে)[^\d]{0,20}([\d,]{2,})[^\d]{0,25}টাকা'
)

# ---- REQUIRED DOCUMENTS (Agriculture) ----
# Matches mentions of specific documents commonly required for
# dealer/producer registration - Trade License, TIN, VAT registration,
# bank solvency certificate. Confirmed against real Fertilizer Act text.
DOCUMENT_LIST_PATTERN = re.compile(
    r'ট্রেড লাইসেন্স|টি,?\s?আই,?\s?এন|TIN Certificate|মূল্য সংযোজন কর|VAT Registration|'
    r'ব্যাংকের সনদপত্র|আর্থিক স্বচ্ছলতা'
)

# ---- DISTRICT ALLOCATION (Disaster Management) ----
# Matches "district name + amount + টাকা" pattern common in DM relief
# allocation orders - e.g. "রংপুর ১,০০,০০০/- (একলক্ষ) টাকা". Confirmed
# against real baby-food procurement allocation orders.
DISTRICT_ALLOCATION_PATTERN = re.compile(
    r'([\u0980-\u09FF]{2,15})\s+([\d,]{3,})\s*/?-?\s*\([^)]{0,20}\)?\s*টাকা'
)

# All 64 Bangladesh district names in Bengali. Used to filter out
# false-positive matches where the regex captures any 2-15 char
# Bengali word before an amount+টাকা - words like "বাবদ" (for),
# "মর্মে" (regarding), "অতিরিক্ত" (additional), or dates like "জুন"
# are NOT districts and must be rejected.
BD_DISTRICTS = {
    "ঢাকা", "চট্টগ্রাম", "রংপুর", "রাজশাহী", "খুলনা", "বরিশাল",
    "সিলেট", "ময়মনসিংহ", "কুমিল্লা", "নোয়াখালী", "ফেনী", "দিনাজপুর",
    "নীলফামারী", "গাইবান্ধা", "কুড়িগ্রাম", "লালমনিরহাট", "পঞ্চগড়",
    "ঠাকুরগাঁও", "বগুড়া", "জয়পুরহাট", "নওগাঁ", "নাটোর", "সিরাজগঞ্জ",
    "চাঁপাইনবাবগঞ্জ", "পাবনা", "কুষ্টিয়া", "মেহেরপুর", "চুয়াডাঙ্গা",
    "ঝিনাইদহ", "যশোর", "মাগুরা", "নড়াইল", "বাগেরহাট", "সাতক্ষীরা",
    "পটুয়াখালী", "বরগুনা", "ভোলা", "পিরোজপুর", "ঝালকাঠি",
    "টাঙ্গাইল", "জামালপুর", "শেরপুর", "নেত্রকোনা", "কিশোরগঞ্জ",
    "মানিকগঞ্জ", "মুন্সিগঞ্জ", "নরসিংদী", "গাজীপুর", "রাজবাড়ী",
    "ফরিদপুর", "গোপালগঞ্জ", "মাদারীপুর", "শরীয়তপুর", "সুনামগঞ্জ",
    "হবিগঞ্জ", "মৌলভীবাজার", "ব্রাহ্মণবাড়িয়া", "চাঁদপুর", "লক্ষ্মীপুর",
    "কক্সবাজার", "বান্দরবান", "রাঙ্গামাটি", "খাগড়াছড়ি", "নারায়ণগঞ্জ",
    "বিনাইদহ",   # OCR variant of ঝিনাইদহ seen in the DM baby food doc
}


def extract_age(text):
    """Returns (value, confidence) or (None, 0.0).

    Confidence tiers:
      0.95  eligibility marker present, no narrative marker
      0.75  both markers present (edge case, policy summary in a report)
      0.60  neither marker present (ambiguous - number matched but no
            context clue for rule vs mention)
      0.30  narrative marker present, no eligibility marker
            (biographical mention - should rank below any real rule)
    """
    text_ascii = to_ascii_digits(text)
    m = AGE_PATTERN.search(text_ascii)
    if not m:
        return None, 0.0
    value = next(g for g in m.groups() if g)
    if not (1 <= int(value) <= 120):
        return None, 0.0

    # Check markers against the ORIGINAL text (Bengali script), not
    # the ASCII-digit-normalized version - normalization only affects
    # numbers, not Bengali marker words, but be explicit.
    has_eligibility = any(mk in text for mk in ELIGIBILITY_MARKERS)
    has_narrative   = any(mk in text for mk in NARRATIVE_MARKERS)

    if has_eligibility and not has_narrative:
        confidence = 0.95
    elif has_eligibility and has_narrative:
        confidence = 0.75
    elif has_narrative and not has_eligibility:
        confidence = 0.30
    else:
        confidence = 0.60

    return value, confidence


def extract_income_limit(text):
    text = to_ascii_digits(text)
    m = INCOME_PATTERN.search(text)
    if not m:
        return None, 0.0
    value = next(g for g in m.groups() if g)
    value_clean = value.replace(",", "")
    if not value_clean.isdigit():
        return None, 0.0
    return value, 0.8


def extract_benefit_amount(text):
    text = to_ascii_digits(text)
    m = AMOUNT_PATTERN.search(text)
    if not m:
        return None, 0.0
    value = next(g for g in m.groups() if g)
    value_clean = value.replace(",", "")
    if not value_clean.isdigit():
        return None, 0.0
    return value, 0.75


def extract_document_requirements(text):
    """Finds mentions of specific required documents (Trade License,
    TIN, VAT registration, bank certificate) - common in Agriculture
    registration/licensing clauses.

    Returns (list_of_matches, confidence) or (None, 0.0)."""
    matches = DOCUMENT_LIST_PATTERN.findall(text)
    if not matches:
        return None, 0.0
    seen = []
    for m in matches:
        if m not in seen:
            seen.append(m)
    return seen, 0.7


def extract_district_allocations(text):
    """Finds district-name + amount pairs, common in Disaster
    Management relief allocation orders.

    Only accepts matches where the captured "district" is a real
    Bangladesh district name. Without this whitelist, the pattern
    captures any Bengali word 2-15 chars before an amount+টাকা,
    producing false positives on procedural words (বাবদ, মর্মে,
    অতিরিক্ত) and dates (জুন, অর্থবছর) - which broke the earlier
    corpus scan.

    Returns (list of (district, amount) tuples, confidence) or (None, 0.0).
    """
    text = to_ascii_digits(text)
    matches = DISTRICT_ALLOCATION_PATTERN.findall(text)
    if not matches:
        return None, 0.0

    cleaned = []
    for district, amount in matches:
        district = district.strip()
        if district not in BD_DISTRICTS:
            continue
        amount_clean = amount.replace(",", "")
        if amount_clean.isdigit() and len(amount_clean) >= 3:
            cleaned.append((district, amount))

    if not cleaned:
        return None, 0.0

    # Higher confidence than before - we're now certain about districts
    return cleaned, 0.85


def extract_entities(text):
    """Run all extractors on one clause, return a dict of what was found."""
    entities = {}

    age, age_conf = extract_age(text)
    if age:
        entities["age"] = {"value": age, "confidence": age_conf}

    income, income_conf = extract_income_limit(text)
    if income:
        entities["income_limit"] = {"value": income, "confidence": income_conf}

    amount, amount_conf = extract_benefit_amount(text)
    if amount:
        entities["benefit_amount"] = {"value": amount, "confidence": amount_conf}

    documents, doc_conf = extract_document_requirements(text)
    if documents:
        entities["required_documents"] = {"value": documents, "confidence": doc_conf}

    allocations, alloc_conf = extract_district_allocations(text)
    if allocations:
        entities["district_allocation"] = {"value": allocations, "confidence": alloc_conf}

    return entities

    # ================================================================
# Extractor 6: extract_office_authority
# ================================================================
# Extracts offices, ministries, directorates, and officer titles
# mentioned in a policy clause. Answers "which office handles X?"
# questions.
#
# Handles three levels of specificity:
#   0.9 - explicit office/ministry/directorate ("উপজেলা সমাজসেবা 
#         কার্যালয়", "সমাজকল্যাণ মন্ত্রণালয়")
#   0.7 - officer designation with location context
#   0.5 - generic officer reference

# High-confidence patterns: explicit named offices/ministries
OFFICE_PATTERNS_HIGH = [
    # Ministry names
    r"([\u0980-\u09FF]+\s*মন্ত্রণালয়)",
    # Directorates
    r"([\u0980-\u09FF]+\s*অধিদপ্তর)",
    # Government offices with location prefix
    r"((?:উপজেলা|জেলা|বিভাগীয়|শহর)\s*[\u0980-\u09FF]+\s*কার্যালয়)",
    # Standalone named offices
    r"([\u0980-\u09FF]+\s*কার্যালয়)",
]

# Medium-confidence: officer designations with context
OFFICE_PATTERNS_MEDIUM = [
    # Officer with location
    r"((?:উপজেলা|জেলা|বিভাগীয়)\s*[\u0980-\u09FF]+\s*কর্মকর্তা)",
    # Executive officers
    r"([\u0980-\u09FF]+\s*নির্বাহী\s*(?:অফিসার|কর্মকর্তা))",
    # Program officers
    r"([\u0980-\u09FF]+\s*পরিচালক)",
]

# Blacklist: generic terms that aren't real offices, filter these out
# from results even if they match the patterns
OFFICE_BLACKLIST = {
    "সরকার", "কর্মকর্তা", "কর্মচারী", "ব্যক্তি",
    "সদস্য", "সভাপতি", "প্রার্থী",
}

# ================================================================
# Extractor 6: extract_office_authority
# ================================================================
# Extracts offices, ministries, directorates, and officer titles.
# Answers "which office handles X?" questions.
#
# Confidence tiers:
#   0.9 - explicit office/ministry/directorate names
#   0.7 - officer designation with location context
#   0.5 - generic officer reference
#
# Non-greedy patterns and word-count cap prevent long concatenations
# like "গণপ্রজাতন্ত্রী বাংলাদেশ সরকারের সমাজকল্যাণ মন্ত্রণালয়
# সমাজসেবা অধিদপ্তর নিয়ন্ত্রণাধীন" - we split these into distinct
# offices instead of returning as one blob.

# One Bengali "word" = run of Bengali chars, no whitespace
BN_WORD = r"[\u0980-\u09FF]+"

# High-confidence: explicit named offices/ministries
# Pattern: 1-3 preceding Bengali words + suffix (মন্ত্রণালয়/অধিদপ্তর/কার্যালয়)
# The {1,3} on words prevents concatenating multiple institutions.
OFFICE_PATTERNS_HIGH = [
    # Ministries: "সমাজকল্যাণ মন্ত্রণালয়", "কৃষি মন্ত্রণালয়"
    r"((?:" + BN_WORD + r"\s+){0,2}" + BN_WORD + r"\s*মন্ত্রণালয়)",
    # Directorates: "সমাজসেবা অধিদপ্তর"
    r"((?:" + BN_WORD + r"\s+){0,2}" + BN_WORD + r"\s*অধিদপ্তর)",
    # Location-prefixed offices: "উপজেলা সমাজসেবা কার্যালয়"
    r"((?:উপজেলা|জেলা|বিভাগীয়|শহর)\s+" + BN_WORD + r"(?:\s+" + BN_WORD + r")?\s*কার্যালয়)",
    # Standalone kaajalaya: "সমাজসেবা কার্যালয়"
    r"(" + BN_WORD + r"(?:\s+" + BN_WORD + r")?\s*কার্যালয়)",
]

# Medium-confidence: officer designations
OFFICE_PATTERNS_MEDIUM = [
    r"((?:উপজেলা|জেলা|বিভাগীয়)\s+" + BN_WORD + r"\s*কর্মকর্তা)",
    r"(" + BN_WORD + r"\s*নির্বাহী\s*(?:অফিসার|কর্মকর্তা))",
    r"(" + BN_WORD + r"\s*পরিচালক)",
]

# Blacklist: generic terms, filter these out
OFFICE_BLACKLIST = {
    "সরকার", "কর্মকর্তা", "কর্মচারী", "ব্যক্তি",
    "সদস্য", "সভাপতি", "প্রার্থী",
}

# Maximum words per extracted office (prevents crazy concatenations)
MAX_OFFICE_WORDS = 5


def _clean_office(name):
    """Normalize whitespace and cap word count."""
    name = re.sub(r"\s+", " ", name).strip()
    words = name.split()
    if len(words) > MAX_OFFICE_WORDS:
        return None
    return name


def extract_office_authority(text):
    """Extract office/authority mentions from a policy clause.

    Returns (list_of_offices, confidence) or (None, 0.0). Deduplicates
    within a clause and removes blacklisted or overly-long matches.
    """
    if not text or len(text) < 20:
        return None, 0.0

    found_high   = set()
    found_medium = set()

    # High-confidence pass
    for pattern in OFFICE_PATTERNS_HIGH:
        for match in re.finditer(pattern, text):
            raw = match.group(1)
            cleaned = _clean_office(raw)
            if not cleaned:
                continue
            if cleaned in OFFICE_BLACKLIST or len(cleaned) < 5:
                continue
            found_high.add(cleaned)

    # Medium-confidence pass (only if no high-conf hits)
    if not found_high:
        for pattern in OFFICE_PATTERNS_MEDIUM:
            for match in re.finditer(pattern, text):
                raw = match.group(1)
                cleaned = _clean_office(raw)
                if not cleaned:
                    continue
                if cleaned in OFFICE_BLACKLIST or len(cleaned) < 5:
                    continue
                found_medium.add(cleaned)

    if found_high:
        return sorted(found_high), 0.9
    if found_medium:
        return sorted(found_medium), 0.7
    return None, 0.0

 # ================================================================
# Extractor 7: extract_deadline_date  (v2 - tightened)
# ================================================================

BENGALI_MONTHS = [
    "জানুয়ারি", "ফেব্রুয়ারি", "মার্চ", "এপ্রিল", "মে", "জুন",
    "জুলাই", "আগস্ট", "সেপ্টেম্বর", "অক্টোবর", "নভেম্বর", "ডিসেম্বর",
    "বৈশাখ", "জ্যৈষ্ঠ", "আষাঢ়", "শ্রাবণ", "ভাদ্র", "আশ্বিন",
    "কার্তিক", "অগ্রহায়ণ", "পৌষ", "মাঘ", "ফাল্গুন", "চৈত্র",
]

# Bengali digits: ০-৯
BN_DIGIT = r"[০-৯]"

# Word-boundary version to prevent "৩" bleeding into "৩২"
# In Bengali, we use whitespace or non-digit chars as boundary
_MONTH_ALT = "|".join(BENGALI_MONTHS)

# High-confidence: date + deadline phrase (single match, not chained)
# Require whitespace/start-of-string before the digit to avoid fragment
DEADLINE_PATTERNS = [
    r"(?:^|\s)(" + BN_DIGIT + r"{1,2}\s+(?:" + _MONTH_ALT + r")\s+" + BN_DIGIT + r"{4})\s*(?:তারিখের\s*মধ্যে|পর্যন্ত)",
]

# Fiscal year
FISCAL_YEAR_PATTERN = r"(" + BN_DIGIT + r"{4}\s*[-–]\s*" + BN_DIGIT + r"{2,4})\s*অর্থবছর"

# Standalone dates - REQUIRE 4-digit year and word boundaries
STANDALONE_DATE_PATTERNS = [
    r"(?:^|\s)(" + BN_DIGIT + r"{1,2}\s+(?:" + _MONTH_ALT + r")\s+" + BN_DIGIT + r"{4})(?:\s|$|[।,])",
]

# Relative deadlines (kept separate, 0.5 confidence)
RELATIVE_DEADLINE_PATTERN = (
    r"(" + BN_DIGIT + r"{1,3}\s*(?:দিন|কর্মদিবস|মাস|বছর|সপ্তাহ)ের\s*মধ্যে)"
)


def extract_deadline_date(text):
    """Extract dates, deadlines, and fiscal year references.

    Returns (list_of_dates, confidence) or (None, 0.0).
    Highest-priority match wins the confidence score. Relative
    deadlines are only returned if no absolute dates are found."""
    if not text or len(text) < 15:
        return None, 0.0

    found_high     = []
    found_fiscal   = []
    found_standalone = []
    found_relative = []

    # High confidence: explicit deadlines
    for pattern in DEADLINE_PATTERNS:
        for match in re.finditer(pattern, text):
            date_str = re.sub(r"\s+", " ", match.group(1)).strip()
            if date_str not in found_high and len(date_str) >= 8:
                found_high.append(date_str)

    # Fiscal year references
    for match in re.finditer(FISCAL_YEAR_PATTERN, text):
        fy = re.sub(r"\s+", " ", match.group(1)).strip() + " অর্থবছর"
        if fy not in found_fiscal:
            found_fiscal.append(fy)

    # Standalone dates (only if no high-conf found)
    if not found_high:
        for pattern in STANDALONE_DATE_PATTERNS:
            for match in re.finditer(pattern, text):
                date_str = re.sub(r"\s+", " ", match.group(1)).strip()
                if date_str not in found_standalone and len(date_str) >= 8:
                    found_standalone.append(date_str)

    # Relative deadlines (only if nothing absolute found)
    if not found_high and not found_fiscal and not found_standalone:
        for match in re.finditer(RELATIVE_DEADLINE_PATTERN, text):
            rd = re.sub(r"\s+", " ", match.group(1)).strip()
            if rd not in found_relative:
                found_relative.append(rd)

    # Return highest-priority group
    if found_high:
        return found_high, 0.9
    if found_fiscal:
        return found_fiscal, 0.8
    if found_standalone:
        return found_standalone, 0.7
    if found_relative:
        return found_relative, 0.5
    return None, 0.0


# ================================================================
# Extractor 8: extract_frequency
# ================================================================
# Extracts payment/review/action frequency from a policy clause.
# Answers "how often is X done?" questions.
#
# Confidence tiers:
#   0.9 - explicit "প্রতি" phrase ("প্রতি মাসে")
#   0.7 - standalone frequency word ("মাসিক", "বার্ষিক")
#   0.5 - numeric frequency ("বছরে ২ বার")

# Explicit frequency phrases with "প্রতি"
FREQUENCY_PATTERNS_HIGH = [
    # "প্রতি মাসে", "প্রতি মাসের", "প্রতি ৩ মাস অন্তর"
    r"(প্রতি\s*(?:" + BN_DIGIT + r"+\s*)?(?:মাস|বছর|সপ্তাহ|দিন)(?:ে|ের|্ত্র)?)",
    # "প্রত্যেক মাসে"
    r"(প্রত্যেক\s*(?:মাস|বছর|সপ্তাহ|দিন)(?:ে|ের)?)",
]

# Standalone frequency words
FREQUENCY_WORDS = [
    "মাসিক", "বার্ষিক", "সাপ্তাহিক", "ত্রৈমাসিক",
    "ষান্মাসিক", "দৈনিক", "পাক্ষিক",
]

# Numeric frequency: "বছরে ২ বার", "মাসে ১ বার"
FREQUENCY_NUMERIC_PATTERN = (
    r"((?:বছর|মাস|সপ্তাহ|দিন)ে\s+" + BN_DIGIT + r"+\s*বার)"
)


def extract_frequency(text):
    """Extract frequency/periodicity from a policy clause.

    Returns (list_of_frequencies, confidence) or (None, 0.0).
    Highest-priority group wins."""
    if not text or len(text) < 15:
        return None, 0.0

    found_high    = set()
    found_word    = set()
    found_numeric = set()

    # High-confidence: explicit "প্রতি" phrases
    for pattern in FREQUENCY_PATTERNS_HIGH:
        for match in re.finditer(pattern, text):
            freq = re.sub(r"\s+", " ", match.group(1)).strip()
            if len(freq) >= 5:
                found_high.add(freq)

    # Standalone frequency words
    for word in FREQUENCY_WORDS:
        if re.search(r"(?:^|[\s।,])" + word + r"(?:[\s।,]|$)", text):
            found_word.add(word)

    # Numeric frequency
    for match in re.finditer(FREQUENCY_NUMERIC_PATTERN, text):
        freq = re.sub(r"\s+", " ", match.group(1)).strip()
        found_numeric.add(freq)

    if found_high:
        return sorted(found_high), 0.9
    if found_word:
        return sorted(found_word), 0.7
    if found_numeric:
        return sorted(found_numeric), 0.5
    return None, 0.0

# ================================================================
# Extractor 9: extract_duration_period
# ================================================================
# Extracts benefit duration, validity periods, terms.
# Answers "for how long?" / "what's the term?" questions.
#
# Confidence tiers:
#   0.9 - duration with explicit context ("মেয়াদে", "পর্যন্ত")
#   0.7 - standalone duration with unit
#   0.5 - ambiguous duration reference

# High-confidence: duration + explicit period context
DURATION_PATTERNS_HIGH = [
    # "৩ বছর মেয়াদে", "৬ মাসের মেয়াদ"
    r"(" + BN_DIGIT + r"+\s*(?:মাস|বছর|সপ্তাহ|দিন|কর্মদিবস)(?:ের|ে)?\s*মেয়াদ(?:ে|ের)?)",
    # "৩ বছর পর্যন্ত", "৬ মাস পর্যন্ত"
    r"(" + BN_DIGIT + r"+\s*(?:মাস|বছর|সপ্তাহ|দিন|কর্মদিবস)(?:ের|ে)?\s*পর্যন্ত)",
    # "৩ বছরের জন্য"
    r"(" + BN_DIGIT + r"+\s*(?:মাস|বছর|সপ্তাহ|দিন|কর্মদিবস)ের\s*জন্য)",
]

# Medium: standalone duration (bare "৩ বছর" without validity context)
DURATION_PATTERNS_MEDIUM = [
    r"(?:^|\s)(" + BN_DIGIT + r"{1,3}\s*(?:মাস|বছর|সপ্তাহ|কর্মদিবস))(?:\s|$|[।,])",
]


def extract_duration_period(text):
    """Extract duration/period from a policy clause.

    Returns (list_of_durations, confidence) or (None, 0.0).
    Highest-priority group wins."""
    if not text or len(text) < 15:
        return None, 0.0

    found_high = set()
    found_med  = set()

    for pattern in DURATION_PATTERNS_HIGH:
        for match in re.finditer(pattern, text):
            dur = re.sub(r"\s+", " ", match.group(1)).strip()
            if len(dur) >= 4:
                found_high.add(dur)

    # Only look for standalone durations if no high-conf hits
    if not found_high:
        for pattern in DURATION_PATTERNS_MEDIUM:
            for match in re.finditer(pattern, text):
                dur = re.sub(r"\s+", " ", match.group(1)).strip()
                if len(dur) >= 4:
                    found_med.add(dur)

    if found_high:
        return sorted(found_high), 0.9
    if found_med:
        return sorted(found_med), 0.7
    return None, 0.0


# ================================================================
# Extractor 10: extract_penalty_fine
# ================================================================
# Extracts fines, penalties, and license cancellation clauses.
# Answers "what is the penalty for violation?" questions.
#
# Confidence tiers:
#   0.9 - monetary fine with amount
#   0.8 - named specific penalty (license cancellation, imprisonment)
#   0.7 - generic penalty term

# Bengali number with commas: "৫,০০০"
BN_NUMBER = r"[০-৯,]+"

# High-confidence: fine with amount
FINE_AMOUNT_PATTERNS = [
    # "৫,০০০ টাকা জরিমানা", "১০,০০০ টাকা পর্যন্ত জরিমানা"
    r"(" + BN_NUMBER + r"\s*টাকা\s*(?:পর্যন্ত\s*)?জরিমানা)",
    # "জরিমানা ৫,০০০ টাকা"
    r"(জরিমানা\s*" + BN_NUMBER + r"\s*টাকা)",
]

# Named specific penalties
NAMED_PENALTY_PATTERNS = [
    # License cancellation variants
    r"(লাইসেন্স\s*বাতিল)",
    r"(নিবন্ধন\s*বাতিল)",
    r"(অনুমোদন\s*বাতিল)",
    # Imprisonment with term
    r"(" + BN_DIGIT + r"+\s*(?:মাস|বছর)\s*কারাদণ্ড)",
    r"(কারাদণ্ড\s*" + BN_DIGIT + r"+\s*(?:মাস|বছর))",
    # Standalone imprisonment
    r"(কারাদণ্ড)",
]

# Generic penalty words
PENALTY_WORDS = [
    "জরিমানা", "শাস্তি", "দণ্ডনীয়", "শাস্তিযোগ্য",
]


def extract_penalty_fine(text):
    """Extract fines, penalties, and disciplinary actions.

    Returns (list_of_penalties, confidence) or (None, 0.0).
    Highest-priority group wins."""
    if not text or len(text) < 15:
        return None, 0.0

    found_amount = set()
    found_named  = set()
    found_generic = set()

    # High-confidence: monetary fines
    for pattern in FINE_AMOUNT_PATTERNS:
        for match in re.finditer(pattern, text):
            fine = re.sub(r"\s+", " ", match.group(1)).strip()
            found_amount.add(fine)

    # Medium: named penalties (only if no amounts found)
    if not found_amount:
        for pattern in NAMED_PENALTY_PATTERNS:
            for match in re.finditer(pattern, text):
                penalty = re.sub(r"\s+", " ", match.group(1)).strip()
                if len(penalty) >= 4:
                    found_named.add(penalty)

    # Low: generic penalty words (only if nothing more specific)
    if not found_amount and not found_named:
        for word in PENALTY_WORDS:
            if re.search(r"(?:^|[\s।,])" + word + r"(?:[\s।,]|$)", text):
                found_generic.add(word)

    if found_amount:
        return sorted(found_amount), 0.9
    if found_named:
        return sorted(found_named), 0.8
    if found_generic:
        return sorted(found_generic), 0.7
    return None, 0.0