"""Bilingual query translation for cross-lingual retrieval.

Direct cross-lingual retrieval using multilingual embeddings failed
on English queries against this Bengali policy corpus - the domain
vocabulary gap is too wide for MiniLM to bridge. We translate the
query into the corpus language BEFORE search, so BM25 gets lexical
matches and dense retrieval sees in-domain Bengali tokens.

Uses NLLB-200-distilled (Costa-jussà et al. 2022, Meta AI), which
was specifically designed for low-resource language translation
including Bengali.

Pipeline:
  1. Full NLLB translation on the natural English sentence
  2. Bengali paraphrase normalization (canonicalize NLLB's variance)
  3. Reverse-dictionary override to guarantee canonical policy terms

Step 2 is important: NLLB translates the same English concept
slightly differently on different runs (e.g. "income limit" becomes
both "আয়সীমা" and "আয়ের সীমা"), and these variants retrieve
different documents. Normalization forces a single canonical form
so retrieval behavior is consistent.

Step 3 handles NLLB's tendency to translate programme names
literally (e.g. "বৃদ্ধকাল ভাতা") rather than using the specific
policy vocabulary ("বয়স্ক ভাতা"). If the canonical form is
missing after translation, it's appended.
"""

import os


MODEL_NAME = os.getenv("TRANSLATION_MODEL", "facebook/nllb-200-distilled-600M")


# Force-map known policy terms to their canonical Bengali form.
# Applied AFTER NLLB translation - if the English original contained
# a known term but the Bengali translation didn't use the canonical
# form, we append the canonical form to guarantee it's in the query.
POLICY_TERM_MAP = {
    "minimum age and annual income limit":  "সর্বনিম্ন বয়স এবং বার্ষিক আয়সীমা",
    "age and annual income limit":          "বয়স এবং বার্ষিক আয়সীমা",
    "age and income limit":                 "বয়স এবং আয়সীমা",
    "annual income limit":       "বার্ষিক আয়সীমা",
    "annual income":             "বার্ষিক আয়",
    "annual average income":     "বার্ষিক গড় আয়",
    "old age allowance":         "বয়স্ক ভাতা",
    "widow allowance":           "বিধবা ভাতা",
    "widow's allowance":         "বিধবা ভাতা",
    "disability allowance":      "প্রতিবন্ধী ভাতা",
    "fertilizer dealer":         "সার ডিলার",
    "fertilizer producer":       "সার উৎপাদনকারী",
    "seed dealer":               "বীজ ডিলার",
    "tea worker":                "চা-শ্রমিক",
    "family card":               "ফ্যামিলি কার্ড",
    "income limit":              "আয়সীমা",
    "age limit":                 "বয়সসীমা",
    "minimum age":               "সর্বনিম্ন বয়স",
    "required documents":        "প্রয়োজনীয় কাগজপত্র",
    "trade license":             "ট্রেড লাইসেন্স",
    "tin certificate":           "টিআইএন সনদপত্র",
}


# Bengali paraphrase normalization. Applied AFTER NLLB translation
# to canonicalize common paraphrases NLLB produces for the same
# concept. Ensures retrieval sees consistent vocabulary regardless
# of translation variance. Longer variants come first so multi-word
# phrases match before their constituent words.
BENGALI_NORMALIZATION = {
    "বার্ষিক আয়ের সীমা":  "বার্ষিক আয়সীমা",
    "বার্ষিক আয়ের":       "বার্ষিক আয়",
    "আয়ের সীমা":          "আয়সীমা",
    "বয়সের সীমা":         "বয়সসীমা",
    "বয়সসীমা কত":         "বয়সসীমা",
}


class Translator:
    """Lazy-loaded so import is cheap; model loads on first use only."""

    def __init__(self):
        self._model     = None
        self._tokenizer = None

    def _load(self):
        if self._model is None:
            print("loading translator (nllb-200-distilled-600M) ...")
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
            self._tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
            self._model     = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)
            print("  translator ready")

    def is_english(self, text):
        """Heuristic: >60% ASCII letters means English. Bengali
        script is outside ASCII so this is a clean signal without
        needing langdetect. Numbers and punctuation don't count."""
        letters = [c for c in text if c.isalpha()]
        if not letters:
            return False
        ascii_letters = sum(1 for c in letters if ord(c) < 128)
        return ascii_letters / len(letters) > 0.6

    def _normalize_bengali(self, text):
        """Canonicalize common Bengali paraphrases so retrieval sees
        consistent vocabulary. NLLB sometimes produces "আয়ের সীমা"
        and sometimes "আয়সীমা" for the same concept - both valid
        Bengali, but they retrieve different documents. Force one
        canonical form.

        Longer variants matched first so multi-word phrases don't
        get partially replaced (e.g. "বার্ষিক আয়ের সীমা" must match
        before "আয়ের সীমা" alone)."""
        for variant in sorted(BENGALI_NORMALIZATION.keys(),
                              key=len, reverse=True):
            canonical = BENGALI_NORMALIZATION[variant]
            text = text.replace(variant, canonical)
        return text

    def _apply_reverse_dictionary(self, english_original, bengali_translation):
        """If the original English contained a known policy term but
        the Bengali translation doesn't include the canonical Bengali
        form, append it. This handles NLLB's tendency to translate
        programme names literally rather than using specific policy
        vocabulary."""
        english_lower = english_original.lower()
        for en_term in sorted(POLICY_TERM_MAP.keys(), key=len, reverse=True):
            bn_term = POLICY_TERM_MAP[en_term]
            if en_term in english_lower and bn_term not in bengali_translation:
                bengali_translation = bengali_translation + " " + bn_term
        return bengali_translation

    def to_bengali(self, text):
        """Translate English text to Bengali. Returns original text
        unchanged if input is not English.

        Full pipeline:
          1. NLLB translation for fluent Bengali output
          2. Normalize Bengali paraphrases to canonical forms
          3. Reverse-dictionary override for policy terminology
        """
        if not self.is_english(text):
            return text

        self._load()
        self._tokenizer.src_lang = "eng_Latn"
        inputs = self._tokenizer(text, return_tensors="pt")
        outputs = self._model.generate(
            **inputs,
            forced_bos_token_id=self._tokenizer.convert_tokens_to_ids("ben_Beng"),
            max_length=128,
        )
        translated = self._tokenizer.decode(outputs[0], skip_special_tokens=True)

        translated = self._normalize_bengali(translated)
        translated = self._apply_reverse_dictionary(text, translated)
        return translated