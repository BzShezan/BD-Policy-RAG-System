# ocr.py — OCR with word-level bounding boxes

import os
from PIL import Image
import pytesseract
from .quality import quality_score, is_bijoy, is_empty_page, is_broken_bengali

RENDER_DPI = 300
PX_TO_PT   = 72.0 / RENDER_DPI

TMP_IMG = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', 'tmp_ocr.png')

try:
    from apsisocr import ApsisOCR
    _apsis = ApsisOCR()
    APSIS_AVAILABLE = True
    print("ApsisOCR loaded (CPU mode)")
except Exception as e:
    _apsis = None
    APSIS_AVAILABLE = False
    print(f"ApsisOCR not available: {e}")


def run_tesseract(img):
    """Single Tesseract call. Returns (text_with_newlines, quality, word_boxes)."""
    try:
        data = pytesseract.image_to_data(img, lang='ben+eng', output_type=pytesseract.Output.DICT)

        boxes = []
        lines = {}  # (block, line) -> list of words

        n = len(data['text'])
        for i in range(n):
            word = str(data['text'][i]).strip()
            conf = int(data['conf'][i])
            if not word or conf < 0:
                continue

            block = data['block_num'][i]
            line  = data['line_num'][i]
            key   = (block, line)

            if key not in lines:
                lines[key] = []
            lines[key].append(word)

            x = float(data['left'][i])   * PX_TO_PT
            y = float(data['top'][i])    * PX_TO_PT
            w = float(data['width'][i])  * PX_TO_PT
            h = float(data['height'][i]) * PX_TO_PT
            boxes.append((round(x, 2), round(y, 2), round(x + w, 2), round(y + h, 2), word))

        # rebuild text with newlines between lines
        sorted_keys = sorted(lines.keys())
        text_lines = []
        for key in sorted_keys:
            text_lines.append(' '.join(lines[key]))
        text = '\n'.join(text_lines)

        q = quality_score(text)
        return text, q, boxes

    except Exception:
        return "", 0.0, []


def run_apsisocr(img_path):
    """Run ApsisOCR. Returns (text, quality, word_boxes in PDF points)."""
    if not APSIS_AVAILABLE:
        return "", 0.0, []
    try:
        result = _apsis(img_path)
        if not result or 'text' not in result:
            return "", 0.0, []

        text = result['text']
        q    = quality_score(text)

        boxes = []
        for item in result.get('result', []):
            word = str(item.get('text', '')).strip()
            poly = item.get('poly', [])
            if not word or not poly:
                continue
            xs = [p[0] for p in poly]
            ys = [p[1] for p in poly]
            x1 = min(xs) * PX_TO_PT
            y1 = min(ys) * PX_TO_PT
            x2 = max(xs) * PX_TO_PT
            y2 = max(ys) * PX_TO_PT
            boxes.append((round(x1, 2), round(y1, 2), round(x2, 2), round(y2, 2), word))

        return text, q, boxes
    except Exception:
        return "", 0.0, []


def get_digital_boxes(page):
    """Word boxes from digital PDF. Already in PDF points."""
    try:
        words = page.get_text("words")
        return [(round(w[0], 2), round(w[1], 2), round(w[2], 2), round(w[3], 2), w[4]) for w in words]
    except:
        return []


def extract_page_text(page):
    """Extract text + word boxes from one PDF page. All coords in PDF points."""
    empty = {"text": "", "ocr_method": "failed", "quality": 0.0, "needs_review": True, "word_boxes": []}

    # step 1: digital text layer - only trust it if the text is actually clean
    try:
        text = page.get_text("text")
    except:
        text = ""

    if (not is_empty_page(text)
            and not is_bijoy(text)
            and not is_broken_bengali(text)):
        q = quality_score(text)
        if q >= 0.6:
            boxes = get_digital_boxes(page)
            return {"text": text, "ocr_method": "digital", "quality": q, "needs_review": False, "word_boxes": boxes}

    # step 2: render
    try:
        pix = page.get_pixmap(dpi=RENDER_DPI)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        img.save(TMP_IMG)
    except:
        return empty

    # step 3: tesseract
    tess_text, tess_q, tess_boxes = run_tesseract(img)
    if tess_q >= 0.5:
        return {"text": tess_text, "ocr_method": "tesseract", "quality": tess_q, "needs_review": False, "word_boxes": tess_boxes}

    # step 4: apsisocr
    apsis_text, apsis_q, apsis_boxes = run_apsisocr(TMP_IMG)
    if apsis_q >= 0.5:
        return {"text": apsis_text, "ocr_method": "apsisocr", "quality": apsis_q, "needs_review": False, "word_boxes": apsis_boxes}

    # step 5: both poor
    if apsis_q > tess_q:
        return {"text": apsis_text, "ocr_method": "apsisocr_low", "quality": apsis_q, "needs_review": True, "word_boxes": apsis_boxes}
    else:
        return {"text": tess_text, "ocr_method": "tesseract_low", "quality": tess_q, "needs_review": True, "word_boxes": tess_boxes}


def cleanup_tmp():
    if os.path.exists(TMP_IMG):
        try:
            os.remove(TMP_IMG)
        except:
            pass