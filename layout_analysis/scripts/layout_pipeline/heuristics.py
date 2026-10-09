# Rule-based correction layer for HEADER / FOOTER.
# Applied AFTER LiLT prediction: geometric certainty overrides model where rules fire.

def apply_header_footer_rules(clause_bbox_pt, page_h_pt, text,
                              header_frac=0.12, footer_frac=0.90):
    """
    clause_bbox_pt: [x1,y1,x2,y2] in PDF points, or None.
    page_h_pt: page height in points.
    text: clause text (used to keep title-like lines out of HEADER).
    Returns "HEADER" / "FOOTER" / None (None = leave LiLT's label).
    """
    if not clause_bbox_pt or not page_h_pt:
        return None

    y_top = clause_bbox_pt[1]
    y_bot = clause_bbox_pt[3]

    # FOOTER: bottom of the region sits in the bottom 10% of the page
    if y_bot >= footer_frac * page_h_pt:
        return "FOOTER"

    # HEADER: top of the region sits in the top 12% AND it's short
    # (long text near the top is usually a title/clause, not letterhead)
    if y_top <= header_frac * page_h_pt and len(text.strip()) < 120:
        return "HEADER"

    return None