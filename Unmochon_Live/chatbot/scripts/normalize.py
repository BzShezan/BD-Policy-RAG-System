"""Bengali digit normalization, shared across the project.

Same logic used in date extraction - Bengali numerals (০-৯) get
converted to standard ASCII digits (0-9) so downstream code (regex,
NER, comparisons) only has to handle one digit format.
"""

BN_DIGITS = str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789')


def to_ascii_digits(text):
    """Convert Bengali digits in a string to ASCII digits.
    English text and Bengali letters pass through unchanged."""
    if not text:
        return text
    return text.translate(BN_DIGITS)