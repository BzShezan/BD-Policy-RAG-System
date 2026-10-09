"""Parsing Bengali dates out of government document headers.

Documents carry two calendars side by side:
    তারিখ ২ শ্রাবণ ১৪৩২ বঙ্গাব্দ ... ১৭ জুলাই ২০২৫ খ্রিস্টাব্দ

The Gregorian one is what we want. Bengali calendar years do not map
onto Gregorian years by a constant offset - the year turns in mid-April -
so converting from বঙ্গাব্দ is a last resort, not a first choice.

Note on what is deliberately NOT parsed: numeric dates like ০৩/০২/২০০৫.
Every allocation order in this corpus cites a 2005 finance ministry memo
in that format. Matching it would date a 2025 circular as 2005 and
silently corrupt every temporal comparison downstream.
"""

import re

BN_DIGITS = str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789')

# Gregorian month names as they appear in Bengali documents.
# Spelling varies between documents, so several forms map to one month.
GREGORIAN_MONTHS = {
    'জানুয়ারি': 1, 'জানুয়ারী': 1, 'january': 1,
    'ফেব্রুয়ারি': 2, 'ফেব্রুয়ারী': 2, 'february': 2,
    'মার্চ': 3, 'march': 3,
    'এপ্রিল': 4, 'april': 4,
    'মে': 5, 'may': 5,
    'জুন': 6, 'june': 6,
    'জুলাই': 7, 'july': 7,
    'আগস্ট': 8, 'আগষ্ট': 8, 'august': 8,
    'সেপ্টেম্বর': 9, 'সেপ্টেম্বার': 9, 'september': 9,
    'অক্টোবর': 10, 'অক্টোবার': 10, 'october': 10,
    'নভেম্বর': 11, 'নভেম্বার': 11, 'november': 11,
    'ডিসেম্বর': 12, 'ডিসেম্বার': 12, 'december': 12,
}

# Bengali calendar months, in order from Boishakh
BANGLA_MONTHS = {
    'বৈশাখ': 1, 'জ্যৈষ্ঠ': 2, 'আষাঢ়': 3, 'শ্রাবণ': 4,
    'ভাদ্র': 5, 'আশ্বিন': 6, 'কার্তিক': 7, 'অগ্রহায়ণ': 8,
    'পৌষ': 9, 'মাঘ': 10, 'ফাল্গুন': 11, 'চৈত্র': 12,
}


def to_ascii_digits(text):
    """Bengali numerals to ASCII so the regexes only deal with 0-9."""
    return text.translate(BN_DIGITS)


def find_gregorian(text):
    """Find a Gregorian date written as day, month name, year.

    Matches:
        ১৭ জুলাই ২০২৫ খ্রিস্টাব্দ
        ১৩ আগস্ট ২০২৫
        04 February 2014

    The খ্রিস্টাব্দ suffix is never used as an anchor. OCR mangles it
    into খরিস্টাব্দ, খরস্টাব্দ, খিস্টাব্দ and once into 'RBH', so
    matching on it would lose most of the dates in the corpus.
    """
    if not text:
        return None

    t = to_ascii_digits(text)
    month_alt = '|'.join(GREGORIAN_MONTHS.keys())

    pattern = rf'(\d{{1,2}})\s*({month_alt})\s*,?\s*((?:19|20)\d{{2}})'
    m = re.search(pattern, t, re.IGNORECASE)
    if m:
        day = int(m.group(1))
        month = GREGORIAN_MONTHS.get(m.group(2).lower())
        year = int(m.group(3))
        if month and 1 <= day <= 31:
            return f"{year:04d}-{month:02d}-{day:02d}"

    return None


def find_bangla_calendar(text):
    """Fall back to the Bengali calendar date when no Gregorian one exists.

    Returns year and month only, never a day. The Bangla year turns in
    mid-April, so mapping a Bangla day onto a Gregorian one needs a real
    calendar library. Month precision is enough to decide which of two
    circulars came first, which is all the supersession check needs.
    """
    if not text:
        return None

    t = to_ascii_digits(text)
    month_alt = '|'.join(BANGLA_MONTHS.keys())

    m = re.search(rf'(\d{{1,2}})\s*({month_alt})\s*(\d{{4}})', t)
    if not m:
        return None

    bn_month = BANGLA_MONTHS[m.group(2)]
    bn_year = int(m.group(3))

    # Boishakh starts mid April. Months 1-9 (Boishakh..Poush) fall in the
    # Gregorian year bn_year + 593. Months 10-12 fall in the next one.
    greg_year = bn_year + 593 if bn_month <= 9 else bn_year + 594

    # Boishakh lines up roughly with April, so shift by three
    greg_month = ((bn_month + 2) % 12) + 1

    return f"{greg_year:04d}-{greg_month:02d}-01"


def from_doc_id(doc_id):
    """Some doc_ids start with the date: 2025.07.17-495-...

    Most reliable source available, because it came from the filename
    rather than from OCR.
    """
    if not doc_id:
        return None

    m = re.match(r'((?:19|20)\d{2})[\.\-_](\d{1,2})[\.\-_](\d{1,2})', doc_id)
    if m:
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= month <= 12 and 1 <= day <= 31:
            return f"{year:04d}-{month:02d}-{day:02d}"

    return None


def from_filename_convention(doc_id):
    """Pull year and month from the project naming convention:
        SW_OAA_2014_02_Gazette_v1  ->  2014-02-01

    The day is unknown so the first of the month stands in. Month 00
    appears in the convention when the month itself is unknown, in which
    case only the year survives.
    """
    if not doc_id:
        return None

    m = re.search(r'_((?:19|20)\d{2})_(\d{2})_', doc_id)
    if m:
        year, month = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12:
            return f"{year:04d}-{month:02d}-01"
        if month == 0:
            return f"{year:04d}-01-01"

    # Year with no month
    m = re.search(r'_((?:19|20)\d{2})_', doc_id)
    if m:
        return f"{int(m.group(1)):04d}-01-01"

    return None