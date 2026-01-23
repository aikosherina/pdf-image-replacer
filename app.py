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
    try:
        body = await request.json()
        pdf_input = body["pdf_base64"]

        # 🔥 KEY FIX: detect Base64 vs binary-text
        if isinstance(pdf_input, str) and pdf_input.strip().startswith("%PDF"):
            # Power Automate already decoded it
            pdf_bytes = pdf_input.encode("latin1")
        else:
            # True Base64
            pdf_bytes = base64.b64decode(pdf_input.encode("ascii"))

        if not pdf_bytes.startswith(b"%PDF"):
            return {
                "error": "Not a valid PDF",
                "first_bytes": pdf_bytes[:20].hex()
            }

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        page = doc[body["page_number"]]

        new_image_b64 = body["new_image_base64"]
        new_image_bytes = base64.b64decode(new_image_b64.encode("ascii"))

        page.replace_image(body["image_xref"], stream=new_image_bytes)

        out_bytes = doc.write()
        doc.close()

        return {
            "pdf_base64": base64.b64encode(out_bytes).decode("ascii")
        }

    except Exception as e:
        return {
            "error": "Unexpected error",
            "exception": str(e)
        }

@app.get("/health")
def health():
    return {"status": "ok", "version": "debug-2026-01-22-v1"}

