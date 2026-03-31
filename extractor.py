import fitz  
# PyMuPDF

def extract_text_blocks(pdf_path):
    doc = fitz.open(pdf_path)
    blocks = []

    for page_num, page in enumerate(doc):
        for b in page.get_text("blocks"):
            x0, y0, x1, y1, text, *_ = b

            if text.strip():
                blocks.append({
                    "page": page_num,
                    "text": text.strip(),
                    "y": y0
                })

    return blocks
