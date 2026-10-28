"""Extractive explanations: every displayed statement has a retrieved clause.

No language model, remote API, invented value, or cached generated answer is
used here. Formatting and sentence selection never change the source words.
"""
import re
import unicodedata


STOP = {'the','a','an','to','for','how','what','is','are','of','and','in','i','do',
        'কত','কী','কি','কিভাবে','কীভাবে','জন্য','এবং','সালের','ও','করতে','হবে'}
FACETS = (
    (r'\bage\b|বয়স|বয়স', r'বয়স|বয়স|বছর|\bage\b|years?'),
    (r'fees?|cost|ফি|খরচ', r'fees?|cost|ফি|খরচ|টাকা'),
    (r'documents?|কাগজপত্র|দলিল', r'documents?|কাগজপত্র|দলিল|সনদ|সংযুক্ত'),
    (r'income|আয়সীমা|আয়সীমা|বার্ষিক আ', r'income|আয়|আয়'),
    (r'correct|সংশোধন', r'correct|সংশোধন'),
    (r'renew|নবায়ন|নবায়ন', r'renew|নবায়ন|নবায়ন'),
)


def normalize(text):
    return unicodedata.normalize('NFC', str(text)).casefold()


def relevant(question, text, *, same_program=False):
    """A matching service name alone cannot answer an unrelated fee/age query."""
    q, t = normalize(question), normalize(text)
    for trigger, source in FACETS:
        if re.search(trigger, q) and not re.search(source, t):
            return False
    if re.search(r'how|apply|application|কিভাবে|কীভাবে|আবেদন|করার নিয়ম|করার নিয়ম', q):
        if not re.search(r'apply|application|form|submit|register|আবেদন|ফরম|ফর্ম|পূরণ|নিবন্ধন|জমা', t):
            return False
    words = {w for w in re.findall(r'[\w\u0980-\u09ff]+', q) if len(w) > 2 and w not in STOP}
    overlap = sum(w in t for w in words)
    return overlap >= min(2, len(words)) if not same_program else bool(overlap or re.search(
        r'ভোটার|পরিচয়|পরিচয়|পাসপোর্ট|নিবন্ধন|লাইসেন্স|\bnid\b|passport|registration|license', t))


def source_sentences(question, text, limit=3):
    # Split at actual sentence/line boundaries; keep numeric/conditional text.
    parts = [p.strip() for p in re.split(r'(?<=[।!?])\s*|(?<=\.)\s+(?=[A-Z\u0980-\u09ff])|\n+', text) if p.strip()]
    q = normalize(question)
    words = [w for w in re.findall(r'[\w\u0980-\u09ff]+', q) if len(w) > 2 and w not in STOP]
    patterns = [source for trigger, source in FACETS if re.search(trigger, q)]
    if re.search(r'how|apply|application|কিভাবে|কীভাবে|আবেদন', q):
        patterns.append(r'form|fill|submit|collect|register|visit|আবেদন|পূরণ|জমা|দাখিল|ফরম|সংযুক্ত|নিবন্ধন')
    scored = []
    for i, part in enumerate(parts):
        if len(part) < 15:
            continue
        t = normalize(part)
        score = sum(w in t for w in words) + 4 * sum(bool(re.search(p, t)) for p in patterns)
        scored.append((score, i, part))
    ranked = sorted(scored, key=lambda p: (-p[0], p[1]))[:limit]
    # Preserve the order of procedural steps from the page, not score order.
    if re.search(r'how|apply|application|কিভাবে|কীভাবে|আবেদন', q):
        ranked.sort(key=lambda p: p[1])
    return [part for _, _, part in ranked]


def clause_explanation(question, text, extracted=None):
    return ' '.join(source_sentences(question, text, 2)) or text.strip()


def build_overview(question, evidence, sufficient=True):
    blocks, seen = [], set()
    for e in evidence:
        for sentence in source_sentences(question, e.text, 3):
            key = normalize(re.sub(r'\s+', ' ', sentence))
            if key in seen:
                existing = next(b for b in blocks if normalize(re.sub(r'\s+', ' ', b['text'])) == key)
                if e.id not in existing['evidence_ids']:
                    existing['evidence_ids'].append(e.id)
                continue
            seen.add(key)
            blocks.append({'text': sentence, 'evidence_ids': [e.id]})
        if len(blocks) >= 6:
            break
    blocks = blocks[:6]
    lead = 'উদ্ধার করা উৎসে বলা হয়েছে:' if sufficient else 'পাওয়া উৎসে প্রশ্নের সম্পূর্ণ উত্তর নেই। সম্পর্কিত মূল তথ্য:'
    answer = lead + ('\n\n' + '\n\n'.join(
        b['text'] + ' [' + ', '.join(str(next(i for i, e in enumerate(evidence, 1) if e.id == eid))
                                   for eid in b['evidence_ids']) + ']' for b in blocks) if blocks else '')
    return {'intro': lead, 'blocks': blocks, 'method': 'retrieved_source_sentences'}, answer
