from fastapi import FastAPI, Request
import base64
import fitz
import re

app = FastAPI()

BASE64_CLEAN_RE = re.compile(r'[^A-Za-z0-9+/=]')

@app.post("/list-images")
async def list_images(request: Request):
    try:
        body = await request.json()
        pdf_base64 = body.get("pdf_base64")

        if not pdf_base64:
            return {"error": "pdf_base64 missing"}

        # 🔥 CRITICAL FIX: clean invalid characters
        if isinstance(pdf_base64, str):
            pdf_base64 = BASE64_CLEAN_RE.sub('', pdf_base64)

        # decode Base64 safely
        pdf_bytes = base64.b64decode(pdf_base64, validate=False)

        # sanity check
        if not pdf_bytes.startswith(b"%PDF"):
            return {"error": "Not a valid PDF after Base64 cleaning"}

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
        return {"images": images}

    except Exception as e:
        return {"error": str(e)}
        
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
