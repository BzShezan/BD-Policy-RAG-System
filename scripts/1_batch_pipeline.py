import json
import re
import os
import fitz  # PyMuPDF
from PIL import Image
import pytesseract

# --- TEAM MEMBERS: CHANGE THESE SETTINGS ---
MINISTRY_TAG = "Social Welfare" # Change to "Agriculture" or "Disaster Management"
INPUT_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'raw_pdfs')
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'processed_jsonl', f"{MINISTRY_TAG.replace(' ', '_')}_clauses.jsonl")

# --- SMART EXTRACTOR (Handles Digital + Scanned + Bijoy Gibberish) ---
def extract_text_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    full_text = ""
    
    for i, page in enumerate(doc):
        # 1. Try to get embedded digital text first (Fast)
        text = page.get_text("text")
        
        # 2. If digital text is very short or contains Bijoy gibberish, fallback to OCR
        # (We check for common gibberish patterns like ‡, ©, or ` which indicate legacy fonts)
        if len(text.strip()) < 20 or "‡" in text or "©" in text or "`" in text:
            # Run OCR (Slow but accurate Unicode)
            try:
                pix = page.get_pixmap(dpi=300)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                text = pytesseract.image_to_string(img, lang='ben+eng')
            except Exception as e:
                print(f"      [OCR Error on page {i+1}: {e}]")
        
        full_text += text + "\n"
        
    doc.close()
    return full_text

# --- CHUNKING LOGIC ---
def chunk_document(text, doc_id):
    # Split by numbered sections (e.g., "01. ", "1. ", "02. ")
    sections = re.split(r'\n(?=\d+\.\s)', text)
    chunks = []
    chunk_counter = 1

    for section in sections:
        section = section.strip()
        if not section or len(section) < 20: # Skip empty/tiny fragments
            continue
        
        match = re.match(r'(\d+)\.', section)
        section_num = match.group(1) if match else "0"
        
        chunks.append({
            "clause_id": f"{doc_id}_C{chunk_counter:04d}",
            "text": section,
            "doc_id": doc_id,
            "section": section_num,
            "tag": MINISTRY_TAG
        })
        chunk_counter += 1
    return chunks

# --- MAIN BATCH PROCESSOR ---
def process_all_pdfs():
    print(f"🏢 Ministry: {MINISTRY_TAG}")
    all_chunks = []
    
    if not os.path.exists(INPUT_FOLDER):
        os.makedirs(INPUT_FOLDER)
        print(f"❌ Folder not found: {INPUT_FOLDER}. Created empty folder. Put PDFs inside and run again.")
        return

    pdf_files = [f for f in os.listdir(INPUT_FOLDER) if f.lower().endswith('.pdf')]
    if not pdf_files:
        print("❌ No PDF files found in the raw_pdfs folder!")
        return

    print(f"📂 Found {len(pdf_files)} PDFs in {INPUT_FOLDER}\n")

    for pdf_file in pdf_files:
        pdf_path = os.path.join(INPUT_FOLDER, pdf_file)
        doc_id = os.path.splitext(pdf_file)[0] # Use filename as Doc ID
        
        print(f"📄 Processing: {pdf_file}...")
        try:
            raw_text = extract_text_from_pdf(pdf_path)
            chunks = chunk_document(raw_text, doc_id)
            all_chunks.extend(chunks)
            print(f"   ✅ Extracted {len(chunks)} clauses.")
        except Exception as e:
            print(f"   ❌ Error processing {pdf_file}: {e}")

    # Save all chunks to a single JSONL file
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for chunk in all_chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + '\n')
            
    print(f"\n🎉 BATCH COMPLETE! Saved {len(all_chunks)} total clauses to {os.path.basename(OUTPUT_FILE)}")
    print("👉 Next step: Commit this .jsonl file to Git and push it.")

if __name__ == "__main__":
    process_all_pdfs()