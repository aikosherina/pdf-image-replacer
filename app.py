from fastapi import FastAPI, Request
import base64
import fitz  # PyMuPDF
import io

app = FastAPI(title="PDF Image Replace API")

# -----------------------
# /list-images endpoint
# -----------------------
@app.post("/list-images")
async def list_images(request: Request):
    try:
        # read JSON manually to avoid Pydantic ASCII issues
        body = await request.json()
        pdf_base64 = body.get("pdf_base64")
        if not pdf_base64:
            return {"error": "pdf_base64 missing"}

        # decode Base64 to binary
        pdf_bytes = base64.b64decode(pdf_base64)

        # quick PDF sanity check
        if not pdf_bytes.startswith(b"%PDF"):
            return {"error": "Not a valid PDF"}

        # open PDF
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
        page_number = body.get("page_number")
        image_xref = body.get("image_xref")
        new_image_base64 = body.get("new_image_base64")

        if not all([pdf_base64, page_number is not None, image_xref is not None, new_image_base64]):
            return {"error": "Missing required fields"}

        pdf_bytes = base64.b64decode(pdf_base64)
        new_image_bytes = base64.b64decode(new_image_base64)

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[page_number]

        page.replace_image(image_xref, stream=new_image_bytes)

        output = io.BytesIO()
        doc.save(output)
        doc.close()

        return {"pdf_base64": base64.b64encode(output.getvalue()).decode()}

    except Exception as e:
        return {"error": str(e)}
