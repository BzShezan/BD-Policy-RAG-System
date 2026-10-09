# chunker.py — split page text into clauses with bbox

import re
from .quality import detect_language

CLAUSE_SPLIT = re.compile(r'\n(?=\d+\.\s|[০-৯]+\.\s)')


def find_clause_bbox(clause_text, word_boxes):
    """
    Find bounding box for a clause by matching its words against word_boxes.
    word_boxes = list of (x1, y1, x2, y2, word) in PDF points.
    Returns [x1, y1, x2, y2] or None.
    """
    if not word_boxes or not clause_text:
        return None

    clause_words = clause_text.split()
    if len(clause_words) < 2:
        return None

    page_words = [w[4] for w in word_boxes]
    search     = clause_words[:min(8, len(clause_words))]

    # find best starting position
    best_start = -1
    best_len   = 0

    for i in range(len(page_words)):
        count = 0
        for j, sw in enumerate(search):
            if i + j < len(page_words) and sw.strip() == page_words[i + j].strip():
                count += 1
            else:
                break
        if count > best_len:
            best_len   = count
            best_start = i

    if best_len < 2 or best_start < 0:
        return None

    # estimate end based on clause word count
    end = min(best_start + len(clause_words), len(word_boxes) - 1)
    matched = word_boxes[best_start:end + 1]

    if not matched:
        return None

    return [
        round(min(w[0] for w in matched), 2),
        round(min(w[1] for w in matched), 2),
        round(max(w[2] for w in matched), 2),
        round(max(w[3] for w in matched), 2),
    ]


def chunk_text(text, doc_id, page_num, ocr_method, quality, needs_review, ministry_tag, word_boxes, counter_start=1):
    """
    Split page text into clause chunks with bbox.
    Returns (list of clause dicts, next counter value).
    """
    chunks  = []
    counter = counter_start

    sections = CLAUSE_SPLIT.split(text)

    for section in sections:
        section = section.strip()
        if not section or len(section) < 20:
            continue

        match = re.match(r'([০-৯\d]+)\.', section)
        section_num = match.group(1) if match else "0"

        bbox = find_clause_bbox(section, word_boxes)

        chunks.append({
            "clause_id":     f"{doc_id}_C{counter:04d}",
            "text":          section,
            "doc_id":        doc_id,
            "section":       section_num,
            "tag":           ministry_tag,
            "page_number":   page_num,
            "ocr_method":    ocr_method,
            "quality_score": quality,
            "language":      detect_language(section),
            "needs_review":  needs_review,
            "is_table":      False,
            "bbox":          bbox,
        })
        counter += 1

    return chunks, counter