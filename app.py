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
async def replace_image(request: Request):
    """
    JSON body should include:
    {
        "pdf_base64": "JVBERi0x...",
        "page_number": 0,
        "image_xref": 10,
        "new_image_base64": "/9j/4AAQSkZJRgABAQAAAQABAAD..." 
    }
    """
    try:
        body = await request.json()
        pdf_base64 = body.get("pdf_base64")
        page_number = body.get("page_number")
        image_xref = body.get("image_xref")
        new_image_base64 = body.get("new_image_base64")

        if not all([pdf_base64, page_number is not None, image_xref, new_image_base64]):
            return {"error": "Missing required fields"}

        # Decode PDF bytes
        pdf_bytes = base64.b64decode(pdf_base64)
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        if page_number >= len(doc):
            return {"error": "page_number out of range"}

        page = doc[page_number]

        # Decode new image bytes
        new_image_bytes = base64.b64decode(new_image_base64)

        # Replace image
        page.replace_image(image_xref, stream=new_image_bytes)

        # Save new PDF
        new_pdf_bytes = doc.write()
        doc.close()

        # Encode PDF to Base64
        new_pdf_base64 = base64.b64encode(new_pdf_bytes).decode("ascii")

        return {"pdf_base64": new_pdf_base64}

    except Exception as e:
        return {"error": "Unexpected error", "exception": str(e)}

@app.get("/health")
def health():
    return {"status": "ok", "version": "debug-2026-01-22-v1"}

