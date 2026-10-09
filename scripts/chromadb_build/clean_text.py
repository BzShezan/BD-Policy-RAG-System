"""Clean up messy OCR text before indexing, mostly for review files."""
import re


def clean_ocr_text(text):
    """Remove obvious OCR garbage, keep readable content."""
    if not text:
        return ""

    # Remove weird symbol runs like ০!০।০০' that OCR produces
    text = re.sub(r'[০-৯]*[!।\'’]{2,}[০-৯]*', ' ', text)

    # Collapse multiple spaces and newlines into single space
    text = re.sub(r'\s+', ' ', text)

    # Strip leading/trailing junk
    text = text.strip()

    return text


def is_worth_keeping(text, min_length=50):
    """Decide if a cleaned review clause is readable enough to index."""
    if len(text) < min_length:
        return False

    # Count how much of the text is actual letters (Bengali or English)
    letters = len(re.findall(r'[অ-হa-zA-Z]', text))
    total = len(text.replace(' ', ''))

    if total == 0:
        return False

    # If less than 50% is real letters, it's probably garbage
    letter_ratio = letters / total
    if letter_ratio < 0.5:
        return False

    return True