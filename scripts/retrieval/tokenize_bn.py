"""Tokenizer for BM25 over mixed Bengali and English policy text.

BM25 needs the text split into terms. Bengali is space separated so
whitespace splitting mostly works, but government documents are full of
danda, memo numbers and bracketed clause markers that need stripping
first or they end up glued to real words.
"""

import re

# Punctuation that appears in Bengali government documents.
# Danda and double danda are sentence enders, the rest are ordinary.
PUNCT = re.compile(r'[।॥,\.\-\(\)\[\]\{\}:;"\'\|/\\!\?\*\u2013\u2014]')

# Bengali digits mapped to ASCII so "৬০০" and "600" match each other.
# Amounts and ages appear both ways across documents.
BN_DIGITS = str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789')


def tokenize(text):
    """Split text into lowercase terms for BM25.

    Returns a list of tokens. Single characters are dropped - they are
    almost always list markers like (ক) or stray punctuation, and they
    add noise without helping any query.
    """
    if not text:
        return []

    text = text.translate(BN_DIGITS)
    text = PUNCT.sub(' ', text)
    text = text.lower()

    return [t for t in text.split() if len(t) > 1]