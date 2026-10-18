"""Jednostronicowy raport PDF układu palety dla modułu 4."""

from __future__ import annotations

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def build_pallet_layout_2d_pdf(result, visualization_png: bytes, *, font_regular="Helvetica", font_bold="Helvetica-Bold") -> bytes:
    """Zwraca jednostronicowy raport z rzutem z góry i przekrojem pionowym palety."""
    result = result or {}
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=28, rightMargin=28, topMargin=26, bottomMargin=24)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("PalletLayoutTitle", parent=styles["Title"], fontName=font_bold, fontSize=15, leading=18, textColor=colors.HexColor("#123B69"))
    body = ParagraphStyle("PalletLayoutBody", parent=styles["Normal"], fontName=font_regular, fontSize=7.8, leading=9.5)
    dimensions = result.get("Wymiary palety mm", []) or []
    dimensions_text = " × ".join(f"{float(value):.0f} mm" for value in dimensions[:3]) if dimensions else "—"
    cargo_dimensions = result.get("Wymiary ładunku XYZ mm", []) or []
    cargo_dimensions_text = " × ".join(f"{float(value):.0f} mm" for value in cargo_dimensions[:3]) if cargo_dimensions else "—"
    rows = [
        ["Parametr", "Wartość"],
        ["Produkt / SKU", f"{result.get('Produkt', '—')} / {result.get('SKU', '—')}"],
        ["Paleta / orientacja", f"{result.get('Paleta', '—')} / {result.get('Orientacja', '—')}"],
        ["Kartonów na warstwę / warstw", f"{result.get('Kartonów/warstwę', 0)} / {result.get('Warstw wizualizowanej palety', result.get('Pełnych warstw', 0))}"],
        ["Kartonów na pełnej palecie", str(result.get("Kartonów na pełnej palecie", 0))],
        ["Kartonów na palecie w raporcie", str(result.get("Kartonów na wizualizowanej palecie", result.get("Kartonów na ostatniej palecie", 0)))],
        ["Wymiary całkowite palety", dimensions_text],
        ["Wymiary ładunku X × Y × Z", cargo_dimensions_text],
        ["Masa brutto palety", f"{result.get('Masa brutto/paleta kg', 0)} kg"],
        ["Stabilność", f"{result.get('Stabilność /100', 0)} / 100 - {result.get('Ocena stabilności', '—')}"],
    ]
    table = Table([[Paragraph(escape(str(cell)), body) for cell in row] for row in rows], colWidths=[165, 372])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#123B69")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 3.5),
    ]))
    image = Image(BytesIO(visualization_png))
    image._restrictSize(530, 390)
    doc.build([
        Paragraph("Raport paletyzacji - układ 2D", title), Spacer(1, 7), table,
        Spacer(1, 8), Paragraph("Rzut z góry jednej warstwy i przekrój pionowy pełnej palety", body), Spacer(1, 3), image,
        Spacer(1, 5), Paragraph("Dokument wygenerowano przez Kalkulator. Układ należy zweryfikować przed przygotowaniem wysyłki.", body),
    ])
    return buffer.getvalue()
