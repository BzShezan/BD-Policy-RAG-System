# OpenCV table verification on a rendered page region.
# A region is a TABLE if it has enough horizontal + vertical ruled lines.

import cv2
import numpy as np


def region_is_table(page_bgr, box_pt, page_w_pt, page_h_pt,
                    min_h_lines=3, min_v_lines=2):
    """
    page_bgr: full page image (numpy BGR) rendered at some DPI.
    box_pt:   [x1,y1,x2,y2] in PDF points.
    Returns True if the cropped region looks like a ruled table.
    """
    img_h, img_w = page_bgr.shape[:2]
    sx = img_w / page_w_pt
    sy = img_h / page_h_pt

    x1 = max(0, int(box_pt[0] * sx))
    y1 = max(0, int(box_pt[1] * sy))
    x2 = min(img_w, int(box_pt[2] * sx))
    y2 = min(img_h, int(box_pt[3] * sy))
    if x2 - x1 < 20 or y2 - y1 < 20:
        return False

    crop = page_bgr[y1:y2, x1:x2]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                               cv2.THRESH_BINARY_INV, 15, 10)

    w = bw.shape[1]
    h = bw.shape[0]

    # horizontal lines
    hk = cv2.getStructuringElement(cv2.MORPH_RECT, (max(10, w // 10), 1))
    horiz = cv2.morphologyEx(bw, cv2.MORPH_OPEN, hk)
    h_count = _count_lines(horiz, axis="h")

    # vertical lines
    vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(10, h // 10)))
    vert = cv2.morphologyEx(bw, cv2.MORPH_OPEN, vk)
    v_count = _count_lines(vert, axis="v")

    return h_count >= min_h_lines and v_count >= min_v_lines


def _count_lines(mask, axis):
    proj = mask.sum(axis=1 if axis == "h" else 0)
    thresh = proj.max() * 0.5 if proj.max() > 0 else 1
    runs = 0
    prev = False
    for v in proj:
        on = v >= thresh
        if on and not prev:
            runs += 1
        prev = on
    return runs