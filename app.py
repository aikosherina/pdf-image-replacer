from fastapi import FastAPI, Request
import base64
import fitz
import re

app = FastAPI()

BASE64_CLEAN_RE = re.compile(r'[^A-Za-z0-9+/=]')

@app.post("/list-images")
async def list_images(request: Request):
    body = await request.json()
    pdf_base64 = body.get("pdf_base64")

    if not pdf_base64:
        return {"error": "pdf_base64 missing"}

    # Clean Base64 (Power Automate Unicode fix)
    cleaned_base64 = BASE64_CLEAN_RE.sub('', pdf_base64)

    try:
        pdf_bytes = base64.b64decode(cleaned_base64, validate=False)
    except Exception as e:
        return {
            "error": "Base64 decode failed",
            "exception": str(e),
            "base64_length": len(cleaned_base64)
        }

    # 🔍 TEMP DEBUG — REMOVE AFTER TESTING
    debug_info = {
        "original_base64_length": len(pdf_base64),
        "cleaned_base64_length": len(cleaned_base64),
        "pdf_bytes_length": len(pdf_bytes),
        "starts_with_pdf": pdf_bytes.startswith(b"%PDF"),
        "first_20_bytes_hex": pdf_bytes[:20].hex()
    }

    if not pdf_bytes.startswith(b"%PDF"):
        return {
            "error": "Not a valid PDF after Base64 cleaning",
            "debug": debug_info
        }

    # Normal logic (will run only if PDF is valid)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    images = []
    for page_index in range(len(doc)):
        page = doc[page_index]
        for img in page.get_images(full=True):
            images.append({
                "page_number": page_index,
                "image_xref": img[0],
                "width": img[2],
                "height": img[3]
            })

    doc.close()

    # Return images + debug (remove debug later)
    return {
        "images": images,
        "debug": debug_info
    }
    
# -----------------------
# /replace-image endpoint
# -----------------------
@app.post("/replace-image")
async def replace_image(request: Request):
    try:
        body = await request.json()

        pdf_base64 = body.get("pdf_base64")
        new_image_base64 = body.get("new_image_base64")
        page_number = body.get("page_number")
        image_xref = body.get("image_xref")

        if pdf_base64 is None or new_image_base64 is None:
            return {"error": "pdf_base64 and new_image_base64 are required"}

        if page_number is None or image_xref is None:
            return {"error": "page_number and image_xref are required"}

        # 🔥 Clean Base64 (SAME AS /list-images)
        pdf_base64 = BASE64_CLEAN_RE.sub('', pdf_base64)
        new_image_base64 = BASE64_CLEAN_RE.sub('', new_image_base64)

        # Decode Base64
        pdf_bytes = base64.b64decode(pdf_base64, validate=False)
        image_bytes = base64.b64decode(new_image_base64, validate=False)

        if not pdf_bytes.startswith(b"%PDF"):
            return {"error": "Invalid PDF data after Base64 cleaning"}

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        if page_number < 0 or page_number >= len(doc):
            return {"error": "Invalid page_number"}

        page = doc[page_number]

        # Replace the image returned by /list-images
        page.replace_image(image_xref, stream=image_bytes)

        output = io.BytesIO()
        doc.save(output)
        doc.close()

        return {
            "pdf_base64": base64.b64encode(output.getvalue()).decode("ascii")
        }

    except Exception as e:
        return {"error": str(e)}
