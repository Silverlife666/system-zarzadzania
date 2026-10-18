"""Generator PDF zlecenia transportowego, bez dostępu do Streamlit i rejestru."""

from __future__ import annotations

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def build_transport_order_pdf(document, *, font_regular="Helvetica", font_bold="Helvetica-Bold", canvasmaker=None):
    """Buduje profesjonalne, dwujęzyczne zlecenie transportowe i zwraca bajty PDF."""
    document = document or {}
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=34, rightMargin=34, topMargin=46, bottomMargin=46, title=f"Zlecenie transportowe {document.get('number', '')}")
    styles = getSampleStyleSheet()
    title = ParagraphStyle("TransportTitle", parent=styles["Title"], fontName=font_bold, fontSize=18, leading=22, textColor=colors.HexColor("#123B69"), spaceAfter=10)
    heading = ParagraphStyle("TransportHeading", parent=styles["Heading2"], fontName=font_bold, fontSize=11, textColor=colors.HexColor("#123B69"), spaceBefore=12, spaceAfter=6)
    body = ParagraphStyle("TransportBody", parent=styles["Normal"], fontName=font_regular, fontSize=9, leading=13, textColor=colors.HexColor("#1F2937"))
    bold = ParagraphStyle("TransportBold", parent=body, fontName=font_bold)
    requirements = document.get("requirements", {}) or {}
    dimensions = (list(document.get("dimensions_cm", []) or []) + [0, 0, 0])[:3]
    number, status = str(document.get("number", "—")), str(document.get("status", "robocze"))
    story = [Paragraph("ZLECENIE TRANSPORTOWE / TRANSPORT ORDER", title), Paragraph(f"<b>Nr / No.:</b> {escape(number)} &nbsp;&nbsp;&nbsp; <b>Status:</b> {escape(status)} &nbsp;&nbsp;&nbsp; <b>Data:</b> {escape(str(document.get('saved_at', ''))[:10])}", body), Spacer(1, 12)]
    def number_value(value):
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0
    shipment_rows = [
        [Paragraph("<b>Przewoźnik / Carrier</b>", bold), Paragraph(escape(str(document.get("carrier", "—"))), body)],
        [Paragraph("<b>Rodzaj ładunku / Cargo</b>", bold), Paragraph(escape(str(document.get("cargo_type", "—"))), body)],
        [Paragraph("<b>Ilość / Quantity</b>", bold), Paragraph(str(document.get("quantity", 0)), body)],
        [Paragraph("<b>Waga brutto / Gross weight</b>", bold), Paragraph(f"{number_value(document.get('total_weight')):.2f} kg", body)],
        [Paragraph("<b>Wymiary 1 sztuki / Dimensions</b>", bold), Paragraph(f"{number_value(dimensions[0]):.1f} × {number_value(dimensions[1]):.1f} × {number_value(dimensions[2]):.1f} cm", body)],
        [Paragraph("<b>Metry ładunkowe / LDM</b>", bold), Paragraph(f"{number_value(document.get('ldm')):.2f}", body)],
    ]
    shipment = Table(shipment_rows, colWidths=[190, 330])
    shipment.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EAF1FB")), ("GRID", (0, 0), (-1, -1), .45, colors.HexColor("#C8D4E3")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("PADDING", (0, 0), (-1, -1), 7)]))
    requirement_rows = [
        [Paragraph("<b>Winda samochodowa / Tail lift</b>", bold), Paragraph("TAK / YES" if requirements.get("tail_lift") else "NIE / NO", body)],
        [Paragraph("<b>Piętrowanie / Stacking</b>", bold), Paragraph("ZABRONIONE / DO NOT STACK" if requirements.get("no_stacking") else "DOZWOLONE / ALLOWED", body)],
        [Paragraph("<b>Awizacja telefoniczna / Phone notice</b>", bold), Paragraph("TAK / YES" if requirements.get("phone_notice") else "NIE / NO", body)],
    ]
    requirement_table = Table(requirement_rows, colWidths=[250, 270])
    requirement_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#FFF7E8")), ("GRID", (0, 0), (-1, -1), .45, colors.HexColor("#E6CF9C")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("PADDING", (0, 0), (-1, -1), 7)]))
    notes = str(document.get("notes", "")).strip() or "Brak dodatkowych uwag / No additional notes."
    story.extend([Paragraph("Dane ładunku / Shipment data", heading), shipment, Spacer(1, 12), Paragraph("Wymagania przewozu / Transport requirements", heading), requirement_table, Spacer(1, 12), Paragraph("Uwagi dla przewoźnika / Carrier notes", heading), Paragraph(escape(notes).replace("\n", "<br/>"), body), Spacer(1, 22), Paragraph("Zlecił / Ordered by: ______________________________", body), Spacer(1, 16), Paragraph("Potwierdzenie przewoźnika / Carrier confirmation: ______________________________", body)])
    if canvasmaker:
        doc.build(story, canvasmaker=canvasmaker)
    else:
        doc.build(story)
    return buffer.getvalue()
