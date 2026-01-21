from fastapi import FastAPI
from pydantic import BaseModel
import base64
import fitz  # PyMuPDF
import io

app = FastAPI()

class RequestData(BaseModel):
    pdf_base64: str
    page_number: int
    image_xref: int
    new_image_base64: str

@app.post("/replace-image")
def replace_image(data: RequestData):
    pdf_bytes = base64.b64decode(data.pdf_base64)
    new_image_bytes = base64.b64decode(data.new_image_base64)

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[data.page_number]

    # Replace embedded image
    page.replace_image(data.image_xref, stream=new_image_bytes)

    output = io.BytesIO()
    doc.save(output)
    doc.close()

    return {
        "pdf_base64": base64.b64encode(output.getvalue()).decode()
    }
