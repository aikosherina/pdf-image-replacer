from fastapi import FastAPI, Request
import fitz
import base64

app = FastAPI()

@app.post("/list-images")
async def list_images(request: Request):
    try:
        body = await request.json()
        pdf_base64 = body.get("pdf_base64")  # match the key sent from Power Automate


        if not pdf_base64:
            return {"error": "pdf_base64 missing"}

        # decode Base64 directly, no .decode() or cleaning
        try:
            pdf_bytes = base64.b64decode(pdf_base64)
        except Exception as e:
            return {"error": "Base64 decode failed", "exception": str(e)}

        # verify PDF header
        if not pdf_bytes.startswith(b"%PDF"):
            return {
                "error": "Not a valid PDF after Base64 decode",
                "first_bytes": pdf_bytes[:20].hex()
            }

        # open PDF and list images
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
        return {"error": "Unexpected error", "exception": str(e)}

    
# -----------------------
# /replace-image endpoint
# -----------------------
@app.post("/replace-image")
def replace_image(payload: dict):
    try:
        pdf_base64 = payload.get("pdf_base64")
        page_number = payload.get("page_number")
        image_xref = payload.get("image_xref")
        new_image_base64 = payload.get("new_image_base64")

        # Decode PDF Base64 to bytes
        pdf_bytes = base64.b64decode(pdf_base64)
        
        # Open PDF from bytes
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[page_number]

        # Decode new image
        new_image_bytes = base64.b64decode(new_image_base64)
        # Replace image (simplified)
        page.replace_image(image_xref, stream=new_image_bytes)

        # Save modified PDF to bytes
        out_bytes = doc.write()
        doc.close()

        # Return Base64
        return {"pdf_base64": base64.b64encode(out_bytes).decode()}

    except Exception as e:
        return {"error": "Unexpected error", "exception": str(e)}

@app.get("/health")
def health():
    return {"status": "ok", "version": "debug-2026-01-22-v1"}

