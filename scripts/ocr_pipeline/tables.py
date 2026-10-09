# tables.py — structured table extraction using PyMuPDF

import re
from .quality import detect_language, quality_score, is_bijoy, is_broken_bengali

# bijoy2unicode has no top-level convert(). The real API is
# converter.Unicode().convertBijoyToUnicode(). The old import always failed
# silently, which meant no table cell was ever converted.
try:
    from bijoy2unicode import converter as _bijoy_converter
    _bijoy = _bijoy_converter.Unicode()
    BIJOY_AVAILABLE = True
except Exception as e:
    _bijoy = None
    BIJOY_AVAILABLE = False
    print(f"bijoy2unicode not available: {e}")


def strip_control_chars(text):
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)


def fix_encoding(text):
    """Clean up a cell. Converts real ASCII Bijoy to Unicode.

    Note: this cannot repair legacy-font corruption where the text is
    already in Bengali codepoints but in visual order with conjuncts
    dropped. Those pages must be re-OCR'd from an image instead -
    is_broken_bengali() flags them for review.
    """
    text = strip_control_chars(text)
    if is_bijoy(text) and BIJOY_AVAILABLE:
        try:
            converted = _bijoy.convertBijoyToUnicode(text)
            if converted and converted.strip():
                return converted.strip()
        except Exception as e:
            print(f"bijoy convert failed: {e}")
    return text.strip()


def clean_cell(cell):
    if not cell:
        return ""
    return fix_encoding(str(cell))


def extract_tables(page, doc_id, page_num, ministry_tag):
    rows = []
    try:
        tabs = page.find_tables()
        if not tabs or not tabs.tables:
            return rows

        for t_idx, table in enumerate(tabs.tables):
            try:
                extracted = table.extract()
                if not extracted:
                    continue

                for r_idx, row in enumerate(extracted):
                    if not row:
                        continue

                    cells = [clean_cell(c) for c in row]
                    if not any(cells):
                        continue

                    real_cells = [c for c in cells if len(c) > 1]
                    if not real_cells:
                        continue

                    row_text = " | ".join(c for c in cells if c)
                    q = quality_score(row_text)
                    bijoy_detected = any(is_bijoy(c) for c in cells)
                    broken = is_broken_bengali(row_text)

                    rows.append({
                        "table_row_id":   f"{doc_id}_P{page_num}_T{t_idx+1}_R{r_idx+1:03d}",
                        "doc_id":         doc_id,
                        "page_number":    page_num,
                        "tag":            ministry_tag,
                        "table_index":    t_idx + 1,
                        "row_index":      r_idx,
                        "is_header":      r_idx == 0,
                        "cells":          cells,
                        "raw_text":       row_text,
                        "language":       detect_language(row_text),
                        "quality_score":  q,
                        "bijoy_detected": bijoy_detected,
                        "broken_text":    broken,
                        "needs_review":   q < 0.3 or bijoy_detected or broken,
                    })
            except Exception as e:
                print(f"table row failed on {doc_id} p{page_num}: {e}")
                continue
    except Exception as e:
        print(f"table extraction failed on {doc_id} p{page_num}: {e}")

    return rows


def has_tables(page):
    try:
        tabs = page.find_tables()
        return bool(tabs and tabs.tables)
    except:
        return False