"""Dokumenty PDF dla wyników Box Rightsizing, niezależne od Streamlit."""

from __future__ import annotations

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def build_mastercase_2d_pdf(result, top_view_png: bytes, vertical_view_png: bytes, *, font_regular="Helvetica", font_bold="Helvetica-Bold") -> bytes:
    """Buduje kartę Master Case z rzutem z góry i przekrojem pionowym warstw."""
    result = result or {}
    mastercase = result.get("MasterCase", {}) or {}
    layout = result.get("layout", {}) or {}
    display = result.get("Display", {}) or {}
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=28, rightMargin=28, topMargin=26, bottomMargin=24)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("MastercaseTitle", parent=styles["Title"], fontName=font_bold, fontSize=15, leading=18, textColor=colors.HexColor("#123B69"))
    body = ParagraphStyle("MastercaseBody", parent=styles["Normal"], fontName=font_regular, fontSize=7.8, leading=9.5)

    def value(number, suffix=""):
        return f"{float(number or 0):.1f}{suffix}"

    rows = [
        ["Parametr", "Wartość"],
        ["Źródło / produkt", str(result.get("source_product") or result.get("Nazwa") or "Master Case")],
        ["Układ displayów", f"{layout.get('length', 0)} × {layout.get('width', 0)} × {layout.get('height', 0)}"],
        ["Displayów w Master Case", str(result.get("displays_per_mastercase", 0))],
        ["Wymiary wewnętrzne", " × ".join(value(mastercase.get(key), " mm") for key in ("Dlugosc_wewnetrzna", "Szerokosc_wewnetrzna", "Wysokosc_wewnetrzna"))],
        ["Wymiary zewnętrzne", " × ".join(value(mastercase.get(key), " mm") for key in ("Dlugosc_zewnetrzna", "Szerokosc_zewnetrzna", "Wysokosc_zewnetrzna"))],
        ["Wymiary displaya", " × ".join(value(display.get(key), " mm") for key in ("Dlugosc", "Szerokosc", "Wysokosc"))],
        ["Tektura / fala", f"{mastercase.get('Tektura', '—')} / {mastercase.get('Fala', '—')}"],
        ["FEFCO / zamknięcie", f"{mastercase.get('FEFCO', '—')} / {mastercase.get('Zamkniecie', '—')}"],
        ["Paleta", str(result.get("pallet", "—"))],
        ["Kartonów w warstwie palety", str(result.get("boxes_per_layer", 0))],
    ]
    table = Table([[Paragraph(escape(cell), body) for cell in row] for row in rows], colWidths=[155, 382])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#123B69")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), font_regular),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 3.5),
    ]))
    top_image = Image(BytesIO(top_view_png))
    top_image._restrictSize(258, 200)
    vertical_image = Image(BytesIO(vertical_view_png))
    vertical_image._restrictSize(258, 200)
    diagram_table = Table([
        [Paragraph("Rzut z góry pojedynczej warstwy", body), Paragraph("Przekrój pionowy warstw", body)],
        [top_image, vertical_image],
    ], colWidths=[268, 268])
    diagram_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    doc.build([
        Paragraph("Karta Master Case - Box Rightsizing", title), Spacer(1, 7), table,
        Spacer(1, 8), Paragraph("Wizualizacje 2D", body), Spacer(1, 3), diagram_table,
        Spacer(1, 5), Paragraph("Dokument wygenerowano przez Kalkulator. Wymiary należy zweryfikować przed produkcją.", body),
    ])
    return buffer.getvalue()
