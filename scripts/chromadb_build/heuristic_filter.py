"""Heuristic noise filter for ministries without a trained layout model.

Agriculture and Disaster Management were never annotated for layout
classification, so their clauses have no layout_label to filter on.
This catches the most obvious noise instead - very short chunks and
known boilerplate phrases that repeat on every page of every document,
the same kind of memo-header content that dominated Social Welfare
search results before the LiLT filter was applied there.

This is a stopgap, not a replacement for real layout classification -
it will miss subtler noise (a short SECTION_TITLE line, for instance)
and won't distinguish METADATA from CLAUSE the way a trained model can.
"""

# Chunks shorter than this are very unlikely to be real policy content -
# real clauses discuss rules, criteria, amounts; memo headers and cover
# pages are usually just a few words.
MIN_WORD_COUNT = 15

# Phrases that appear on nearly every page of nearly every government
# document, carrying no policy content of their own. If a chunk is
# MOSTLY made of these phrases, it's boilerplate, not a real clause.
BOILERPLATE_PHRASES = [
    "গণপ্রজাতন্ত্রী বাংলাদেশ সরকার",
    "গণপ্রজাতন্ত্রী বাংলাদেশ",
    "কৃষি মন্ত্রণালয়",
    "সমাজকল্যাণ মন্ত্রণালয়",
    "দুর্যোগ ব্যবস্থাপনা ও ত্রাণ মন্ত্রণালয়",
    "বাংলাদেশ সচিবালয়",
    "www.moa.gov.bd",
    "www.msw.gov.bd",
    "www.dss.gov.bd",
    "Government of the People's Republic of Bangladesh",
    "Ministry of Agriculture",
    "Ministry of Social Welfare",
]


def word_count(text):
    """Rough word count - splits on whitespace, works for both
    Bengali and English since both use spaces between words."""
    return len(text.split())


def boilerplate_ratio(text):
    """What fraction of the text is made up of known boilerplate
    phrases. A chunk that's mostly letterhead scores high here."""
    if not text.strip():
        return 0.0

    total_len = len(text)
    boilerplate_len = 0

    for phrase in BOILERPLATE_PHRASES:
        boilerplate_len += len(phrase) * text.count(phrase)

    return min(boilerplate_len / total_len, 1.0)


def is_likely_noise(text):
    """True if this chunk is probably a memo header, cover page
    fragment, or other non-content boilerplate rather than a real
    policy clause.

    Two checks, either one is enough to flag it:
      - too short to be real content
      - mostly made of known letterhead/boilerplate phrases
    """
    if not text or not text.strip():
        return True

    if word_count(text) < MIN_WORD_COUNT:
        return True

    if boilerplate_ratio(text) > 0.4:
        return True

    return False