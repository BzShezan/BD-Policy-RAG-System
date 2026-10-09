"""Build a lookup JSON from the Policies_Metadata Excel file.

Maps each doc_id (as it appears in ChromaDB) to:
  - display_name:  human-readable program name for the UI
  - source_url:    official government URL (if available)
  - date_sortable: comparable date string (YYYYMMDD or YYYYMM) for
                   sorting docs by recency. Used for date-aware
                   conflict resolution.
  - date_display:  human-readable date string ("2013" or "2025 গেজেট")
  - program:       program name for grouping related docs
"""

import json
import os
import re
import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

EXCEL_PATH = os.path.join(PROJECT_ROOT, "data", "Policies Metadata.xlsx")
OUTPUT_PATH = os.path.join(PROJECT_ROOT, "data", "doc_metadata.json")


def normalize_doc_id(doc_id):
    if not doc_id:
        return None
    doc_id = str(doc_id).strip()
    doc_id = re.sub(r"\.pdf$", "", doc_id, flags=re.IGNORECASE)
    return doc_id


def parse_date_to_sortable(circular_date, budget_yr):
    """Return (sortable_str, display_str) for a doc.

    sortable_str: YYYYMMDD-like string for chronological comparison.
    display_str: human-readable version for UI ('2025 গেজেট', '2013').

    Prefers circular_date if present and parseable. Falls back to
    budget year. Returns (None, None) if nothing parseable."""
    from datetime import datetime

    # Try circular_date first (may be datetime object or string)
    if circular_date:
        if isinstance(circular_date, datetime):
            return (
                circular_date.strftime("%Y%m%d"),
                circular_date.strftime("%Y"),
            )
        s = str(circular_date).strip()
        # Match "2013", "2025", "13th October 2025", etc.
        year_match = re.search(r"\b(19|20)\d{2}\b", s)
        if year_match:
            year = year_match.group()
            # Try to find month for finer sort
            month_map = {
                "january": "01", "february": "02", "march": "03",
                "april": "04", "may": "05", "june": "06",
                "july": "07", "august": "08", "september": "09",
                "october": "10", "november": "11", "december": "12",
            }
            month = "01"   # default to Jan if unknown
            for m_name, m_num in month_map.items():
                if m_name in s.lower():
                    month = m_num
                    break
            return (f"{year}{month}01", year)

    # Fall back to budget year: "2013-14" -> use first year
    if budget_yr:
        s = str(budget_yr).strip()
        year_match = re.search(r"\b(19|20)\d{2}\b", s)
        if year_match:
            year = year_match.group()
            return (f"{year}0101", year)

    return (None, None)


def build_display_name(program, doc_type, year):
    parts = [str(program).strip()] if program else []
    extras = []
    if doc_type:
        extras.append(str(doc_type).strip())
    if year:
        extras.append(str(year).strip())
    if extras:
        parts.append(f"({', '.join(extras)})")
    return " ".join(parts) if parts else None


def main():
    wb = openpyxl.load_workbook(EXCEL_PATH)
    ws = wb["Metadata"]

    lookup = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        doc_id_raw, program, doc_type, cir_date, budget_yr, source_url = row[:6]
        if not doc_id_raw:
            continue

        doc_id = normalize_doc_id(doc_id_raw)
        if not doc_id:
            continue

        url = None
        if source_url and str(source_url).strip().startswith(("http://", "https://")):
            url = str(source_url).strip()

        sortable, display = parse_date_to_sortable(cir_date, budget_yr)

        display_name = build_display_name(program, doc_type, budget_yr)

        lookup[doc_id] = {
            "display_name":  display_name,
            "source_url":    url,
            "program":       str(program).strip() if program else None,
            "date_sortable": sortable,
            "date_display":  display,
        }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(lookup, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(lookup)} entries to {OUTPUT_PATH}")
    print(f"  with source_url: {sum(1 for v in lookup.values() if v['source_url'])}")
    print(f"  with date:       {sum(1 for v in lookup.values() if v['date_sortable'])}")


if __name__ == "__main__":
    main()