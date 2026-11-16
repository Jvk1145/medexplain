"""Turn an uploaded file into AI message content blocks.

- Text PDFs  -> extract text locally, redact personal info, send TEXT only (most private).
- Scanned PDFs -> render pages to images (AI reads them with vision), max 5 pages.
- Photos     -> resize/compress, send as an image (AI vision).
"""
import base64
import io

import pdfplumber
from PIL import Image

from .redact import redact

MAX_SIDE = 2000  # px – keeps images small and fast
MAX_PAGES = 5    # free vision models accept up to ~5 images per request


def _b64(data: bytes) -> str:
    return base64.standard_b64encode(data).decode()


def _image_block(img: Image.Image) -> dict:
    img = img.convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return {"type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": _b64(buf.getvalue())}}


def _pdf_page_images(data: bytes) -> list:
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        return [_image_block(page.to_image(resolution=150).original) for page in pdf.pages[:MAX_PAGES]]


def _pdf_text(data: bytes) -> str:
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            return "\n".join((page.extract_text() or "") for page in pdf.pages)
    except Exception:
        return ""


def build_source(data: bytes, filename: str) -> dict:
    name = filename.lower()

    if name.endswith(".pdf"):
        text = _pdf_text(data)
        if len(text.strip()) > 200:  # real text layer exists
            clean, n = redact(text)
            return {
                "kind": "text",
                "redactions": n,
                "blocks": [{"type": "text", "text": f"<lab_report>\n{clean}\n</lab_report>"}],
            }
        return {"kind": "pdf", "redactions": 0, "blocks": _pdf_page_images(data)}

    # Image
    return {"kind": "image", "redactions": 0, "blocks": [_image_block(Image.open(io.BytesIO(data)))]}
