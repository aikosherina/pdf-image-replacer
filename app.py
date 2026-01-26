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
# /list-images-with-position endpoint
# -----------------------
@app.post("/list-images-with-position")
async def list_images_with_position(request: Request):
    try:
        body = await request.json()
        pdf_base64 = body.get("pdf_base64")

        if not pdf_base64:
            return {"error": "pdf_base64 missing"}

        try:
            doc = open_pdf_from_base64(pdf_base64)
        except Exception as e:
            return {"error": "PDF open failed", "exception": str(e)}

        images = []

        for page_index in range(len(doc)):
            page = doc[page_index]

            try:
                imgs = page.get_images(full=True)
            except Exception as e:
                doc.close()
                return {
                    "error": "get_images failed",
                    "page_number": page_index,
                    "exception": str(e)
                }

            for img in imgs:
                xref = img[0]

                try:
                    rects = page.get_image_rects(xref)
                except Exception as e:
                    images.append({
                        "page_number": page_index,
                        "image_xref": xref,
                        "error": f"get_image_rects failed: {e}"
                    })
                    continue

                for rect in rects:
                    images.append({
                        "page_number": page_index,
                        "image_xref": xref,
                        "width": rect.width,
                        "height": rect.height
                    })

        doc.close()
        return {"images": images}

    except Exception as e:
        return {"error": "Unexpected server error", "exception": str(e)}

# -----------------------
# /overlay-vector-logo endpoint
# -----------------------
@app.post("/overlay-vector-logo")
async def overlay_vector_logo(request: Request):
    try:
        body = await request.json()
        pdf_base64 = body.get("pdf_base64")
        logo_base64 = body.get("logo_base64")

        if not pdf_base64 or not logo_base64:
            return {"error": "pdf_base64 or logo_base64 missing"}

        try:
            doc = open_pdf_from_base64(pdf_base64)
        except Exception as e:
            return {"error": "PDF open failed", "exception": str(e)}

        try:
            logo_bytes = base64.b64decode(logo_base64)
        except Exception as e:
            doc.close()
            return {"error": "Logo base64 decode failed", "exception": str(e)}

        try:
            page = doc[0]
        except Exception as e:
            doc.close()
            return {"error": "Page access failed", "exception": str(e)}

        try:
            drawings = page.get_drawings()
            if not drawings:
                doc.close()
                return {"error": "No vector drawings found"}
        except Exception as e:
            doc.close()
            return {"error": "get_drawings failed", "exception": str(e)}

        try:
            min_x = min(d["rect"].x0 for d in drawings)
            min_y = min(d["rect"].y0 for d in drawings)
            max_x = max(d["rect"].x1 for d in drawings)
            max_y = max(d["rect"].y1 for d in drawings)
            logo_rect = fitz.Rect(min_x, min_y, max_x, max_y)
        except Exception as e:
            doc.close()
            return {"error": "Vector bounds calculation failed", "exception": str(e)}

        try:
            page.insert_image(
                logo_rect,
                stream=logo_bytes,
                overlay=True
            )
        except Exception as e:
            doc.close()
            return {"error": "insert_image failed", "exception": str(e)}

        try:
            out_bytes = doc.tobytes()
        except Exception as e:
            doc.close()
            return {"error": "PDF serialization failed", "exception": str(e)}

        doc.close()

        return {
            "pdf_base64": base64.b64encode(out_bytes).decode("ascii")
        }

    except Exception as e:
        return {"error": "Unexpected server error", "exception": str(e)}

    
# -----------------------
# /detect-artwork endpoint
# -----------------------
def open_pdf_from_base64(pdf_base64: str):
    try:
        pdf_bytes = base64.b64decode(pdf_base64)
    except Exception as e:
        raise ValueError(f"Base64 decode failed: {e}")

    if not pdf_bytes.startswith(b"%PDF"):
        raise ValueError("Not a valid PDF")

    return fitz.open(stream=pdf_bytes, filetype="pdf")


@app.post("/detect-artwork")
async def detect_artwork(request: Request):
    try:
        body = await request.json()
        pdf_base64 = body.get("pdf_base64")
        if not pdf_base64:
            return {"error": "pdf_base64 missing"}

        try:
            doc = open_pdf_from_base64(pdf_base64)
        except Exception as e:
            return {"error": "PDF open failed", "exception": str(e)}

        pages = []

        for page_index in range(len(doc)):
            page = doc[page_index]

            # -----------------------
            # 1️⃣ Raster images
            # -----------------------
            try:
                raster_images = page.get_images(full=True)
                raster_info = [
                    {
                        "image_xref": img[0],
                        "width": img[2],
                        "height": img[3]
                    } for img in raster_images
                ]
            except Exception as e:
                raster_images = []
                raster_info = []
                raster_error = str(e)
            else:
                raster_error = None

            # -----------------------
            # 2️⃣ Form XObjects (vector graphics inside the PDF)
            # -----------------------
            try:
                xobject_list = []
                # Iterate all XObjects
                for xref in doc.get_xref_objects():
                    if xref[1] == "XObject":
                        # Check subtype
                        subtype = doc.xref_object(xref[0], compressed=False)
                        if b"/Subtype /Form" in subtype:
                            # Form XObject detected
                            bbox_start = subtype.find(b"/BBox [")
                            if bbox_start != -1:
                                bbox_end = subtype.find(b"]", bbox_start)
                                bbox_str = subtype[bbox_start+7:bbox_end].decode("ascii").strip()
                                try:
                                    x0, y0, x1, y1 = map(float, bbox_str.split())
                                    xobject_list.append({
                                        "xref": xref[0],
                                        "x0": x0,
                                        "y0": y0,
                                        "x1": x1,
                                        "y1": y1,
                                        "width": x1 - x0,
                                        "height": y1 - y0
                                    })
                                except:
                                    continue
            except Exception as e:
                xobject_list = []
                xobject_error = str(e)
            else:
                xobject_error = None

            pages.append({
                "page_number": page_index,
                "has_raster_images": len(raster_images) > 0,
                "raster_image_count": len(raster_images),
                "vector_logo_candidates": xobject_list,
                "vector_count": len(xobject_list)
            })

        doc.close()
        return {"pages": pages}

    except Exception as e:
        return {"error": "Unexpected error", "exception": str(e)}

    
# -----------------------
# /list-drawings endpoint
# -----------------------
from typing import List, Dict

def rect_union(rects: List[fitz.Rect]) -> fitz.Rect:
    """Return the union rectangle covering all input rectangles."""
    if not rects:
        return None
    r = rects[0]
    for rr in rects[1:]:
        r |= rr  # union operator in PyMuPDF
    return r

def group_nearby_shapes(shapes: List[Dict], max_distance=10) -> List[Dict]:
    """
    Group shapes that are close to each other (within max_distance in points)
    to form combined candidates (useful for logos made of multiple small parts).
    """
    groups = []
    for shape in shapes:
        rect = fitz.Rect(shape['rect'])
        placed = False
        for group in groups:
            group_rect = fitz.Rect(group['rect'])
            # If distance between group and shape is small, merge
            if (rect.intersects(group_rect) or
                rect.distance_to_rect(group_rect) < max_distance):
                # Merge rects
                new_rect = rect_union([group_rect, rect])
                group['rect'] = [new_rect.x0, new_rect.y0, new_rect.x1, new_rect.y1]
                # Keep track of all shape types combined (optional)
                group['types'].add(shape['type'])
                placed = True
                break
        if not placed:
            groups.append({
                'rect': shape['rect'],
                'types': {shape['type']}
            })
    # Flatten types set back to string or join if needed
    for group in groups:
        group['type'] = ','.join(sorted(group['types']))
        del group['types']
    return groups

@app.post("/list-drawings")
async def list_drawings(request: Request):
    try:
        data = await request.json()
        pdf_base64 = data.get('pdf_base64')
        if not pdf_base64:
            return {"error": "Missing pdf_base64 in request"}

        pdf_bytes = base64.b64decode(pdf_base64)
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        all_shapes = []

        # Extract vector drawings from all pages
        for page_num in range(len(doc)):
            page = doc[page_num]
            drawings = page.get_drawings()
            for d in drawings:
                # d['type'] can be 'f', 's', 'fs' etc
                # Capture only relevant types
                if d['type'].lower() in ('f', 'fs', 's'):
                    rect = d.get('rect', None)
                    if rect:
                        # rect is a fitz.Rect, convert to list [x0, y0, x1, y1]
                        rect_list = [rect.x0, rect.y0, rect.x1, rect.y1]
                        all_shapes.append({
                            'page_number': page_num,
                            'type': d['type'].lower(),
                            'rect': rect_list
                        })

        # Group nearby shapes to combine fragmented logos
        grouped_shapes = group_nearby_shapes(all_shapes, max_distance=15)

        return {"drawings": grouped_shapes}

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

