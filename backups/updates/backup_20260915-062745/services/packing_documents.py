"""Generowanie profesjonalnej Packing List niezależne od Streamlit."""

from __future__ import annotations

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def build_packing_list_pdf(document, *, font_regular="Helvetica", font_bold="Helvetica-Bold"):
    """Tworzy Packing List w układzie A4 dla PL, EN lub dokumentu dwujęzycznego."""
    document = document or {}
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=30, rightMargin=30, topMargin=34, bottomMargin=34)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("PLTitle", parent=styles["Title"], fontName=font_bold, fontSize=18, textColor=colors.HexColor("#123B69"))
    normal = ParagraphStyle("PLNormal", parent=styles["Normal"], fontName=font_regular, fontSize=8, leading=10)
    bold = ParagraphStyle("PLBold", parent=normal, fontName=font_bold)
    labels = {"PL": ("LISTA PAKOWANIA", "Nadawca", "Odbiorca", "Podsumowanie", "Podpis wydającego", "Podpis odbierającego"), "EN": ("PACKING LIST", "Sender", "Recipient", "Summary", "Released by", "Received by")}
    language = document.get("language", "PL")
    languages = ["PL", "EN"] if language == "PL/EN" else [language if language in labels else "PL"]
    title_text = " / ".join(labels[item][0] for item in languages)
    story = [Paragraph(title_text, title), Spacer(1, 7), Paragraph(f"<b>Nr:</b> {escape(str(document.get('number', '')))} &nbsp;&nbsp; <b>Status:</b> {escape(str(document.get('status', '')))} &nbsp;&nbsp; <b>Data utworzenia:</b> {escape(str(document.get('created_at', '')))}", normal), Spacer(1, 9)]
    header = [[Paragraph(f"<b>{labels['PL'][1]} / {labels['EN'][1]}</b><br/>{escape(str(document.get('sender', '')))}", normal), Paragraph(f"<b>{labels['PL'][2]} / {labels['EN'][2]}</b><br/>{escape(str(document.get('recipient', '')))}<br/>{escape(str(document.get('delivery_place', '')))}", normal)]]
    header_table = Table(header, colWidths=[260, 275])
    header_table.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), .5, colors.HexColor("#C8D4E3")), ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("PADDING", (0, 0), (-1, -1), 8)]))
    story.extend([header_table, Spacer(1, 10)])
    columns = ["Produkt / SKU", "EAN-y poziomów / LOT", "Szt.", "Kart.", "Paleta", "Masa kg"]
    rows = [[Paragraph(value, bold) for value in columns]]
    for item in document.get("items", []):
        eans = f"Produkt: {escape(str(item.get('EAN produktu', '—') or '—'))}<br/>Display: {escape(str(item.get('EAN displaya', '—') or '—'))}<br/>Master Case: {escape(str(item.get('EAN Master Case', '—') or '—'))}<br/>Poziom: {escape(str(item.get('Poziom opakowania', '—')))} | użyty: {escape(str(item.get('EAN/GTIN', '')))}<br/>LOT: {escape(str(item.get('LOT', '')))}"
        rows.append([Paragraph(f"{escape(str(item.get('Produkt', '')))}<br/>{escape(str(item.get('SKU', '')))}", normal), Paragraph(eans, normal), str(item.get("Sztuki", 0)), str(item.get("Kartony", 0)), escape(str(item.get("Paleta", ""))), str(item.get("Masa kg", 0))])
    table = Table(rows, colWidths=[120, 180, 42, 42, 80, 60], repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#123B69")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTNAME", (0, 0), (-1, -1), font_regular), ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#D7DEE8")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("PADDING", (0, 0), (-1, -1), 5)]))
    summary = document.get("summary", {}) or {}
    story.extend([table, Spacer(1, 10), Paragraph(f"<b>{labels['PL'][3]} / {labels['EN'][3]}:</b> palety: {summary.get('pallets', 0)} | kartony: {summary.get('cartons', 0)} | sztuki: {summary.get('pieces', 0)} | kg: {summary.get('weight', 0)} | m³: {summary.get('m3', 0)} | LDM: {summary.get('ldm', 0)}", normal), Spacer(1, 25), Paragraph(f"{labels['PL'][4]} / {labels['EN'][4]}: ____________________ &nbsp;&nbsp;&nbsp; {labels['PL'][5]} / {labels['EN'][5]}: ____________________", normal)])
    doc.build(story)
    return buffer.getvalue()


def build_basic_packing_list_pdf(dataframe, *, font_regular="Helvetica", font_bold="Helvetica-Bold"):
    """Tworzy prostą tabelaryczną Packing List dla kompatybilności ze starszym widokiem."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("PackingBasicTitle", parent=styles["Heading1"], fontName=font_bold, fontSize=14, textColor=colors.HexColor("#1A202C"), spaceAfter=12)
    cell = ParagraphStyle("PackingBasicCell", parent=styles["Normal"], fontName=font_regular, fontSize=9, textColor=colors.HexColor("#2D3748"))
    cell_bold = ParagraphStyle("PackingBasicBold", parent=styles["Normal"], fontName=font_bold, fontSize=9, textColor=colors.HexColor("#1A202C"))
    columns = list(getattr(dataframe, "columns", []))
    rows = [[Paragraph(escape(str(column)), cell_bold) for column in columns]]
    for _, row in getattr(dataframe, "iterrows", lambda: [])():
        rows.append([Paragraph(escape(str(value)), cell) for value in row])
    if not columns:
        rows.append([Paragraph("Brak pozycji / No items", cell)])
        widths = [515]
    else:
        widths = [520 / len(columns)] * len(columns)
    table = Table(rows, colWidths=widths, repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ED8936")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("ALIGN", (0, 0), (-1, -1), "LEFT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 5), ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("GRID", (0, 0), (-1, -1), .5, colors.HexColor("#CBD5E0")), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7FAFC")])]))
    doc.build([Paragraph("Zbiorcza Lista Pakowania (Packing List)", title), Spacer(1, 10), table])
    return buffer.getvalue()
