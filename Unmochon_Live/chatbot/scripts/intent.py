"""Multi-intent question classification.

Detects which entity types a question is asking about, using keyword
scoring - not a single winner-takes-all match, since real questions
often ask about more than one thing at once ("what's the age AND
income limit"). Bilingual (Bengali/English/mixed).

Suppression rules apply after keyword scoring to handle cases where
a more specific intent overrides a general one. For example, "কত
টাকা বরাদ্দ" triggers both benefit_amount (via "কত টাকা") and
district_allocation (via "বরাদ্দ"), but the query is really about
allocation - benefit_amount would pull in noisy allowance-payment
clauses that dilute the actual allocation answer.
"""

INTENT_KEYWORDS = {
    "age": [
        "বয়স", "বয়সসীমা", "কত বছর", "বছর বয়স",
        "age", "years old", "eligibility age",
    ],
    "income_limit": [
        "আয়সীমা", "আয়ের সীমা", "অনূর্ধ্ব আয়",
        "income limit", "income ceiling", "annual income",
    ],
    "benefit_amount": [
        "ভাতা কত", "কত টাকা", "মাসিক ভাতা", "পাবে",
        "benefit amount", "allowance amount", "monthly payment",
    ],
    "eligibility_criteria": [
        "যোগ্যতা", "শর্ত", "যোগ্য",
        "eligibility", "criteria", "qualify", "eligible",
    ],
    "application_procedure": [
        "আবেদন", "আবেদন পদ্ধতি", "কোথায় আবেদন",
        "apply", "application", "how to apply", "procedure",
    ],
    "required_documents": [
        "কাগজপত্র", "প্রয়োজনীয় কাগজ", "নথি",
        "নিবন্ধনের জন্য কী",
        "নিবন্ধনের জন্য প্রয়োজন",
        "নিয়োগের জন্য কী",
        "লাইসেন্সের জন্য",
        "documents required", "required documents", "papers needed",
        "what is needed for registration", "for registration",
    ],
    "district_allocation": [
        "বরাদ্দ", "জেলা", "কত টাকা বরাদ্দ",
        "allocation", "district allocation", "how much allocated",
    ],

    "office_authority": [
    "কোন অফিস", "কোন কার্যালয়", "কোথায় আবেদন",
    "কোন মন্ত্রণালয়", "কোন অধিদপ্তর", "কোন কর্মকর্তা",
    "কে দায়িত্বপ্রাপ্ত", "কর্তৃপক্ষ কে",
    "which office", "which ministry", "which authority",
    "where to apply",
],

"deadline_date": [
    "কবে", "তারিখ", "সময়সীমা", "কতদিন", "কখন",
    "অর্থবছর", "মেয়াদ", "তারিখের মধ্যে",
    "when", "deadline", "date", "fiscal year", "by when",
],

"frequency": [
    "কতবার", "কত ঘন ঘন", "কত সময় পরপর", "কত বার",
    "প্রতি মাসে", "প্রতি বছর", "প্রতি সপ্তাহে",
    "how often", "how frequently", "frequency",
    "monthly payment", "yearly payment", "how many times",
],

"duration_period": [
    "কতদিন", "কতদিনের", "কত বছর", "মেয়াদ", "কতদিনের জন্য",
    "how long", "duration", "period", "term", "for how many",
],

"penalty_fine": [
    "জরিমানা", "শাস্তি", "দণ্ড", "কারাদণ্ড", "বাতিল",
    "লাইসেন্স বাতিল", "শাস্তির পরিমাণ", "দণ্ডনীয়",
    "penalty", "fine", "punishment", "imprisonment", "cancellation",
],

}


# Suppression rules: when the first intent is present, drop the
# second because the first is a more specific interpretation of
# the query. Applied AFTER keyword scoring.
SUPPRESSION_RULES = [
    # District-allocation queries about money should NOT also
    # trigger benefit_amount - the query is fundamentally about
    # allocation, not general per-person benefit payments.
    ("district_allocation", "benefit_amount"),
]


def detect_intents(query):
    """Returns a list of detected intent types, in order of how many
    keyword matches each got. Empty list means no intent matched -
    caller should fall back to a generic response.

    Applies suppression rules to prevent overlapping intents from
    firing extractors that pull in noise on questions about a more
    specific topic.
    """
    query_lower = query.lower()

    scores = {}
    for intent, keywords in INTENT_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw.lower() in query_lower)
        if count > 0:
            scores[intent] = count

    ranked = [intent for intent, _ in
              sorted(scores.items(), key=lambda x: -x[1])]

    # Apply suppression rules
    for keep, drop in SUPPRESSION_RULES:
        if keep in ranked and drop in ranked:
            ranked.remove(drop)

    return ranked