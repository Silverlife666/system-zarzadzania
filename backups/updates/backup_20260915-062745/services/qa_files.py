"""Odczyt plików źródłowych dla modułu kontroli QA."""

from __future__ import annotations

import base64
import re
from io import BytesIO

import numpy as np


def render_validation_bytes(file_bytes, filename, page_number, dpi):
    """Zwraca obraz RGB z PDF lub pliku graficznego jako tablicę NumPy."""
    from PIL import Image

    if str(filename or "").lower().endswith(".pdf"):
        import fitz
        document = fitz.open(stream=file_bytes, filetype="pdf")
        try:
            page_index = min(max(int(page_number) - 1, 0), len(document) - 1)
            page = document.load_page(page_index)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(float(dpi) / 72), alpha=False)
            image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
        finally:
            document.close()
    else:
        image = Image.open(BytesIO(file_bytes)).convert("RGB")
    return np.array(image)


def inspect_pdf_separations(file_bytes, filename):
    """Odczytuje deklarowane DeviceCMYK, DeviceN i separacje dodatkowe PDF."""
    if not str(filename or "").lower().endswith(".pdf"):
        return {"type": "plik graficzny", "cmyk": False, "pantone": []}
    spots = sorted(set(match.decode("latin-1", errors="replace") for match in re.findall(rb"/Separation\s*/([^\s/\[\]()<>]+)", file_bytes)))
    return {"type": "PDF", "cmyk": b"/DeviceCMYK" in file_bytes or b"/DeviceN" in file_bytes, "pantone": spots}


def image_slider_html(before_image, after_image):
    """Zwraca samodzielny HTML interaktywnego porównania przed/po."""
    from PIL import Image

    def to_data_url(image_array):
        image_buffer = BytesIO()
        Image.fromarray(image_array).save(image_buffer, format="PNG")
        return base64.b64encode(image_buffer.getvalue()).decode("ascii")

    before_data, after_data = to_data_url(before_image), to_data_url(after_image)
    return f'''<div style="position:relative;max-width:900px;margin:auto;overflow:hidden">
<img src="data:image/png;base64,{after_data}" style="width:100%;display:block">
<div id="before" style="position:absolute;left:0;top:0;width:50%;height:100%;overflow:hidden"><img src="data:image/png;base64,{before_data}" style="width:100%;max-width:none;height:100%;object-fit:fill"></div>
<input id="slider" type="range" min="0" max="100" value="50" style="position:absolute;left:0;bottom:10px;width:100%">
</div><script>document.getElementById('slider').oninput=function(){{document.getElementById('before').style.width=this.value+'%';}}</script>'''
