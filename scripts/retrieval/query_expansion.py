"""Expand user queries with Bengali policy-domain synonyms.

The synonym table is deliberately narrow. Over-expansion dilutes the
dense embedding and degrades retrieval on lean queries - a lesson
learned from watching the Bede/Dalit/Harijan query regress from rank
6 to MISS when a broad expansion added 10+ tokens.

Rules that keep it safe:
  1. Groups are intent-scoped. An "age" query does not get "benefit
     amount" synonyms, even if both share the word "ভাতা".
  2. A group only fires if its OWN specific trigger term is present,
     not on generic words like "ভাতা" or "ভাতার".
  3. Additions capped at 4 tokens total across all fired groups.
"""

SYNONYM_GROUPS = [
    {
        "name":     "age",
        "triggers": ["বয়সসীমা", "বয়সের সীমা", "কত বছর", "কত বয়স"],
        "synonyms": ["বয়স", "বছর", "বৎসর", "যোগ্যতা"],
    },
    {
        "name":     "income",
        "triggers": ["আয়সীমা", "আয়ের সীমা", "বার্ষিক আয়"],
        "synonyms": ["আয়", "উপার্জন", "বার্ষিক"],
    },
    {
        "name":     "amount",
        "triggers": ["ভাতার পরিমাণ", "কত টাকা", "মাসিক ভাতা"],
        "synonyms": ["টাকা", "মাসিক", "পরিমাণ"],
    },
    {
        "name":     "eligibility",
        "triggers": ["যোগ্যতা", "শর্ত", "কে পাবে", "কারা পাবে"],
        "synonyms": ["মানদন্ড", "প্রার্থী নির্বাচন", "শর্তাবলী"],
    },
    {
        "name":     "documents",
        "triggers": ["কাগজপত্র", "দলিল", "কী কী লাগবে", "কী প্রয়োজন"],
        "synonyms": ["সনদ", "প্রমাণ", "নথি"],
    },
    {
        "name":     "allocation",
        "triggers": ["বরাদ্দ", "বণ্টন"],
        "synonyms": ["প্রদান", "বিতরণ"],
    },
    # DM-specific: district allocation queries. Triggers when the
    # query asks about food/relief being allocated ACROSS districts,
    # which is the distinctive shape of DM allocation orders.
    # Synonyms are drawn from actual clause vocabulary in the DM
    # allocation documents (baby food, dry food, cash, districts).
    {
        "name":     "district_allocation",
        "triggers": ["জেলায় কত", "কোন জেলায়", "জেলায় বরাদ্দ",
                     "শিশুখাদ্য", "শুকনা খাবার", "শুকনা খাদ্য"],
        "synonyms": ["জেলা", "শিশুখাদ্য", "শুকনা", "খাবার",
                     "একলক্ষ", "প্রদান"],
    },
]

MAX_ADDITIONS = 4


def expand(query):
    additions = []
    for group in SYNONYM_GROUPS:
        if any(t in query for t in group["triggers"]):
            for syn in group["synonyms"]:
                if syn not in query and syn not in additions:
                    additions.append(syn)

    additions = additions[:MAX_ADDITIONS]
    if not additions:
        return query

    return query + " " + " ".join(additions)