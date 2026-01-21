from fastapi import FastAPI
from pydantic import BaseModel
import base64
import fitz  # PyMuPDF
import io

app = FastAPI()

# ---------- MODELS ----------

class PdfBase64(BaseModel):
    pdf_base64: str

class ReplaceImageRequest(BaseModel):
    pdf_base64: str
    page_number: int
    image_xref: int
    new_image_base64: str

# ---------- ENDPOINTS ----------

@app.post("/list-images")
def list_images(data: PdfBase64):
    pdf_bytes = base64.b64decode(data.pdf_base64)
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


@app.post("/replace-image")
def replace_image(data: ReplaceImageRequest):
    pdf_bytes = base64.b64decode(data.pdf_base64)
    new_image_bytes = base64.b64decode(data.new_image_base64)

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[data.page_number]

    page.replace_image(data.image_xref, stream=new_image_bytes)

    output = io.BytesIO()
    doc.save(output)
    doc.close()

    return {
        "pdf_base64": base64.b64encode(output.getvalue()).decode()
    }
