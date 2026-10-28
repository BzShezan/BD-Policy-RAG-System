# quality.py — text quality scoring and detection helpers

import re

# Real Bijoy ASCII markers. The old list was mojibake (UTF-8 read as cp437)
# and matched nothing, which is why Bijoy detection never fired.
BIJOY_MARKERS = ['Avgvi', 'evsjv', '†mvbvi', 'g‡a¨', '‡', '¨', '„', 'wb', 'Kv']

# Pre-base vowel signs. In correct Unicode these NEVER start a word -
# they always attach after a consonant. If one appears at the start of
# a word, the text is stored in visual order instead of logical order.
PRE_BASE_VOWELS = 'িেৈোৌ'

# Latin letters fused directly to Bengali characters. Broken legacy fonts
# map conjuncts like ন্ট or ক্ষ to Latin codepoints such as D, K, R, X, #, ^
STRAY_LATIN = re.compile(
    r'[\u0980-\u09FF][A-Za-z#^]|[A-Za-z#^][\u0980-\u09FF]'
)

# All dependent vowel signs, pre-base and post-base
ALL_VOWEL_SIGNS = '\u09BE-\u09CC\u09D7'

# Two vowel signs in a row - never legal Bengali, always means the text
# is in visual order. Catches নীিতমালা (should be নীতিমালা).
#
# Note: a hasant-followed-by-vowel rule was tried here and removed.
# It fired on every legitimate conjunct like কার্যালয় and pushed false
# alarms from 60 to 528.
INVALID_VOWEL_SEQ = re.compile(
    r'[' + ALL_VOWEL_SIGNS + r'][' + ALL_VOWEL_SIGNS + r']'
)


def bengali_ratio(text):
    """How much of the text is Bengali versus English. Used for language
    detection only - this is NOT a quality measure."""
    if not text.strip():
        return 0.0
    bengali = sum(1 for c in text if '\u0980' <= c <= '\u09FF')
    english = sum(1 for c in text if c.isascii() and c.isalpha())
    total = bengali + english
    if total == 0:
        return 0.0
    return round(bengali / total, 3)


def detect_language(text):
    if not text.strip():
        return "Unknown"
    ratio = bengali_ratio(text)
    if ratio > 0.75:
        return "Bangla"
    elif ratio < 0.25:
        return "English"
    return "Mixed"


def is_bijoy(text):
    """True if the text looks like ASCII Bijoy encoding."""
    return any(m in text for m in BIJOY_MARKERS)


def is_broken_bengali(text):
    """Detect legacy-font corruption in Bengali text.

    This is NOT ASCII Bijoy - the text is already in Bengali codepoints
    but stored in visual order rather than logical order, with conjuncts
    dropped or replaced by Latin glyphs.

    Examples caught:
      সমাজেসবা   should be  সমাজসেবা
      গণজাতী     should be  গণপ্রজাতন্ত্রী
      নীিতমালা   should be  নীতিমালা
      অধKR       should be  অধ্যক্ষ

    Returns True if the page should be re-OCR'd from an image instead
    of trusting the PDF text layer.
    """
    if not text:
        return False

    # Only meaningful on pages with real Bengali content.
    # Floor is low so short page headers still get checked.
    bengali_chars = len(re.findall(r'[\u0980-\u09FF]', text))
    if bengali_chars < 10:
        return False

    # A vowel sign at the start of a word never happens in correct
    # Unicode. One occurrence is proof of visual-order storage.
    if re.search(r'(?:^|\s)[' + PRE_BASE_VOWELS + r']', text):
        return True

    # Latin letters fused to Bengali characters - dropped conjuncts
    if STRAY_LATIN.search(text):
        return True

    # Two vowel signs adjacent
    if INVALID_VOWEL_SEQ.search(text):
        return True

    return False


def quality_score(text):
    """Score how usable a block of extracted text is, 0.0 to 1.0.

    Language-neutral: clean English scores as well as clean Bengali.
    The old version returned bengali_ratio(), which meant garbled Bengali
    scored 1.0 and clean English scored 0.0.

    Penalises the failure modes we actually see in this corpus -
    replacement characters, stray Latin glyphs inside Bengali words,
    and legacy-font corruption.
    """
    if not text or not text.strip():
        return 0.0

    stripped = text.strip()
    total = len(stripped)

    # Real letters in either script
    letters = sum(
        1 for c in stripped
        if ('\u0980' <= c <= '\u09FF') or (c.isascii() and c.isalpha())
    )

    # Digits, whitespace and normal punctuation are expected, not junk
    ok_other = sum(
        1 for c in stripped
        if c.isdigit() or c.isspace() or c in '।,.-()/:;%|৳'
    )

    usable = (letters + ok_other) / total

    # Hard failure signals
    if '\ufffd' in text:          # replacement character - decode failure
        usable -= 0.3
    if is_broken_bengali(text):   # legacy-font corruption
        usable -= 0.5

    # Very short fragments are unreliable regardless of content
    if len(stripped) < 15:
        usable -= 0.2

    return round(max(0.0, min(1.0, usable)), 3)


def is_empty_page(text):
    return len(text.strip()) < 20


def is_table_page(text):
    return text.count('|') > 10