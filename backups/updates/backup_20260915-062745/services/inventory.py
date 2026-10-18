"""Czysta logika importu i raportowania inwentaryzacji tacek."""

from __future__ import annotations

import csv
import io
import re
import json
import base64
import os
from collections import Counter
from datetime import datetime


FIELD_ALIASES = {
    "timestamp": {"data", "data czas", "data/czas", "data i czas", "czas", "timestamp", "datetime"},
    "operator": {"operator", "uzytkownik", "user"},
    "ean": {"ean", "gtin", "ean/gtin", "kod ean", "kod"},
    "tray_id": {"id tacki", "tacka", "tray", "tray id", "qr tacki", "id tray"},
    "product_name": {"nazwa produktu", "produkt", "nazwa", "product name"},
    "actual_quantity": {"ilosc rzeczywista", "ilość rzeczywista", "ilosc", "ilość", "actual quantity", "qty"},
    "nominal_quantity": {"ilosc nominalna", "ilość nominalna", "ilosc domyslna", "ilość domyślna", "nominal quantity", "default quantity"},
}


def _normalized(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().casefold().replace("_", " "))


def _number(value, default=0):
    try:
        return int(float(str(value or default).strip().replace(",", ".")))
    except (TypeError, ValueError):
        return default


def normalize_ean(value) -> str:
    return "".join(character for character in str(value or "") if character.isdigit())


def canonical_column_name(name: str) -> str | None:
    normalized = _normalized(name)
    for canonical, aliases in FIELD_ALIASES.items():
        if normalized in aliases:
            return canonical
    return None


def parse_inventory_csv(payload: bytes) -> list[dict]:
    """Czyta CSV z telefonu (UTF-8/UTF-8 BOM) i ujednolica jego kolumny."""
    content = payload.decode("utf-8-sig", errors="replace")
    sample = content[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(content), dialect=dialect)
    if not reader.fieldnames:
        raise ValueError("Plik CSV nie zawiera nagłówków.")
    columns = {column: canonical_column_name(column) for column in reader.fieldnames}
    if not columns.get(next((key for key, value in columns.items() if value == "tray_id"), "")):
        raise ValueError("CSV musi zawierać kolumnę ID tacki / QR tacki.")
    records = []
    for row_number, row in enumerate(reader, start=2):
        item = {canonical: str(row.get(source, "") or "").strip()
                for source, canonical in columns.items() if canonical}
        if not any(item.values()):
            continue
        item["source_row"] = row_number
        item["ean"] = normalize_ean(item.get("ean"))
        item["tray_id"] = normalize_tray_id(item.get("tray_id"))
        item["actual_quantity"] = _number(item.get("actual_quantity"))
        item["nominal_quantity"] = _number(item.get("nominal_quantity"))
        records.append(item)
    return records


def parse_stock_csv(payload: bytes) -> list[dict]:
    """Czyta stan magazynowy: EAN/GTIN, nazwa produktu i ilość rzeczywista."""
    content = payload.decode("utf-8-sig", errors="replace")
    try:
        dialect = csv.Sniffer().sniff(content[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(content), dialect=dialect)
    if not reader.fieldnames:
        raise ValueError("Plik stanu magazynowego nie zawiera nagłówków.")
    columns = {column: canonical_column_name(column) for column in reader.fieldnames}
    required = {"ean", "product_name", "actual_quantity"}
    if not required.issubset({value for value in columns.values() if value}):
        raise ValueError("CSV stanu magazynowego musi zawierać: EAN/GTIN, Nazwa produktu, Ilość rzeczywista.")
    records = []
    for row_number, row in enumerate(reader, start=2):
        item = {canonical: str(row.get(source, "") or "").strip() for source, canonical in columns.items() if canonical}
        if not any(item.values()):
            continue
        item.update({"source_row": row_number, "ean": normalize_ean(item.get("ean")), "product_name": str(item.get("product_name", "")).strip(), "actual_quantity": _number(item.get("actual_quantity"))})
        records.append(item)
    return records


def parse_comparison_inventory_csv(payload: bytes) -> list[dict]:
    """Czyta raport inwentaryzacji z tackami albo prosty plik EAN/produkt/ilość."""
    try:
        return parse_inventory_csv(payload)
    except ValueError:
        return parse_stock_csv(payload)


def compare_inventory_to_stock(inventory_records: list[dict], stock_records: list[dict]) -> list[dict]:
    """Porównuje sumy ilości z inwentaryzacji i stanu magazynowego po EAN."""
    aggregated = {}

    def add(records, side):
        for record in records or []:
            ean = normalize_ean(record.get("ean"))
            name = str(record.get("product_name") or record.get("catalog_product") or "").strip()
            key = ean or f"name:{_normalized(name)}"
            if key == "name:":
                continue
            item = aggregated.setdefault(key, {"ean": ean, "product_name": name, "inventory_quantity": 0, "stock_quantity": 0})
            if name and not item["product_name"]:
                item["product_name"] = name
            item[side] += _number(record.get("actual_quantity"))

    add(inventory_records, "inventory_quantity")
    add(stock_records, "stock_quantity")
    compared = []
    for item in aggregated.values():
        difference = item["inventory_quantity"] - item["stock_quantity"]
        item["difference"] = difference
        item["status"] = "Zgodne" if difference == 0 else ("Nadwyżka" if difference > 0 else "Brak")
        compared.append(item)
    return sorted(compared, key=lambda item: (item["status"] == "Zgodne", item["product_name"].casefold(), item["ean"]))


def stock_comparison_summary(comparison: list[dict]) -> dict:
    return {
        "items": len(comparison or []),
        "matching": sum(item.get("status") == "Zgodne" for item in comparison or []),
        "surpluses": sum(item.get("status") == "Nadwyżka" for item in comparison or []),
        "shortages": sum(item.get("status") == "Brak" for item in comparison or []),
    }


def build_stock_comparison_pdf(comparison: list[dict], font_regular="Helvetica", font_bold="Helvetica-Bold") -> bytes:
    """Tworzy raport PDF niezależnego porównania ze stanem magazynowym."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    if font_regular == "Helvetica" and os.path.exists("C:/Windows/Fonts/arial.ttf") and os.path.exists("C:/Windows/Fonts/arialbd.ttf"):
        try:
            if "InventoryComparisonFont" not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont("InventoryComparisonFont", "C:/Windows/Fonts/arial.ttf"))
                pdfmetrics.registerFont(TTFont("InventoryComparisonFont-Bold", "C:/Windows/Fonts/arialbd.ttf"))
            font_regular, font_bold = "InventoryComparisonFont", "InventoryComparisonFont-Bold"
        except Exception:
            pass
    summary = stock_comparison_summary(comparison)
    output = io.BytesIO()
    document = SimpleDocTemplate(output, pagesize=landscape(A4), leftMargin=10 * mm, rightMargin=10 * mm, topMargin=10 * mm, bottomMargin=10 * mm)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("comparison_title", parent=styles["Title"], fontName=font_bold, fontSize=16, leading=20)
    normal = ParagraphStyle("comparison_normal", parent=styles["BodyText"], fontName=font_regular, fontSize=8, leading=10)
    header = ParagraphStyle("comparison_header", parent=normal, fontName=font_bold, textColor=colors.white, alignment=TA_CENTER)
    story = [Paragraph("Porównanie inwentaryzacji ze stanem magazynowym", title), Spacer(1, 4 * mm)]
    summary_table = Table([
        [Paragraph("Pozycje", header), Paragraph("Zgodne", header), Paragraph("Nadwyżki", header), Paragraph("Braki", header)],
        [str(summary["items"]), str(summary["matching"]), str(summary["surpluses"]), str(summary["shortages"])],
    ], colWidths=[38 * mm] * 4, hAlign="LEFT")
    summary_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")), ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#B7C9D6")), ("ALIGN", (0, 1), (-1, -1), "CENTER"), ("FONTNAME", (0, 1), (-1, -1), font_regular), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    story.extend([summary_table, Spacer(1, 5 * mm)])
    rows = [[Paragraph(value, header) for value in ("EAN/GTIN", "Nazwa produktu", "Inwentaryzacja", "Stan magazynowy", "Różnica", "Wynik")]]
    for item in comparison or []:
        rows.append([Paragraph(str(item.get(key, "")), normal) for key in ("ean", "product_name", "inventory_quantity", "stock_quantity", "difference", "status")])
    table = Table(rows, colWidths=[35 * mm, 75 * mm, 31 * mm, 38 * mm, 25 * mm, 30 * mm], repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C5D0D8")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (2, 1), (-1, -1), "CENTER"), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F8FB")]), ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    story.append(table)
    document.build(story)
    return output.getvalue()


def normalize_tray_id(value) -> str:
    return tray_qr_data(value).get("tray_id", "")


def tray_qr_data(value) -> dict:
    text = str(value or "").strip()
    if text.upper().startswith("TRAY|"):
        parts = text.split("|", 2)
        tray_id = parts[1].strip().upper()
        if len(parts) == 3:
            try:
                payload = json.loads(base64.urlsafe_b64decode(parts[2] + "=" * (-len(parts[2]) % 4)).decode("utf-8"))
                if isinstance(payload, dict):
                    payload["tray_id"] = tray_id
                    return payload
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
                pass
        return {"tray_id": tray_id}
    return {"tray_id": text.strip().upper()}


def tray_qr_payload(tray) -> str:
    item = tray if isinstance(tray, dict) else {"tray_id": tray}
    tray_id = tray_qr_data(item.get("tray_id")).get("tray_id", "")
    data = {key: item.get(key, "") for key in ("tray_name", "product_name", "actual_quantity", "nominal_quantity", "operator")}
    encoded = base64.urlsafe_b64encode(json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).decode("ascii").rstrip("=")
    return f"TRAY|{tray_id}|{encoded}"


def _product_eans(product: dict) -> set[str]:
    values = [product.get("EAN"), product.get("ean")]
    for level in ("Produkt", "Display", "MasterCase"):
        if isinstance(product.get(level), dict):
            values.append(product[level].get("EAN"))
    return {normalize_ean(value) for value in values if normalize_ean(value)}


def product_index(products: dict) -> dict[str, dict]:
    index = {}
    for name, raw_data in (products or {}).items():
        data = raw_data if isinstance(raw_data, dict) else {}
        for ean in _product_eans(data):
            index.setdefault(ean, {"name": name, "data": data})
    return index


def default_tray_quantity(product: dict) -> int:
    for key in ("Ilość domyślna w tacce", "Ilosc domyslna w tacce", "default_tray_quantity", "pcs_in_box"):
        quantity = _number((product or {}).get(key), 0)
        if quantity > 0:
            return quantity
    return 0


def enrich_inventory_records(records: list[dict], products: dict) -> list[dict]:
    """Łączy import z katalogiem i oblicza różnice dla każdej zeskanowanej tacki."""
    index = product_index(products)
    tray_counts = Counter(record.get("tray_id", "") for record in records if record.get("tray_id"))
    enriched = []
    for record in records:
        item = dict(record)
        matched = index.get(item.get("ean", ""))
        if matched:
            item["catalog_product"] = matched["name"]
            item["product_name"] = item.get("product_name") or matched["name"]
            if not item.get("nominal_quantity"):
                item["nominal_quantity"] = default_tray_quantity(matched["data"])
            item["recognized"] = True
        else:
            item["catalog_product"] = ""
            item["recognized"] = False
        item["difference"] = _number(item.get("actual_quantity")) - _number(item.get("nominal_quantity"))
        item["duplicate_tray"] = bool(item.get("tray_id")) and tray_counts[item["tray_id"]] > 1
        item["issue"] = "; ".join(filter(None, [
            "brak ID tacki" if not item.get("tray_id") else "",
            "nieznany EAN" if item.get("ean") and not item["recognized"] else "",
            "duplikat tacki" if item["duplicate_tray"] else "",
            "brak" if item["difference"] < 0 else "",
            "nadwyżka" if item["difference"] > 0 else "",
        ]))
        enriched.append(item)
    return enriched


def update_inventory_record(records: list[dict], record_index: int, changes: dict, products: dict) -> list[dict]:
    """Zapisuje poprawkę jednego wpisu i przelicza całą sesję inwentaryzacji."""
    if record_index < 0 or record_index >= len(records):
        raise IndexError("Wybrany wpis inwentaryzacji nie istnieje.")
    updated = [dict(record) for record in records]
    item = updated[record_index]
    item.update(changes or {})
    item["ean"] = normalize_ean(item.get("ean"))
    item["tray_id"] = normalize_tray_id(item.get("tray_id"))
    item["actual_quantity"] = _number(item.get("actual_quantity"))
    item["nominal_quantity"] = _number(item.get("nominal_quantity"))
    return enrich_inventory_records(updated, products)


def session_summary(records: list[dict]) -> dict:
    unique_trays = {record.get("tray_id") for record in records if record.get("tray_id")}
    skus = {record.get("product_name") or record.get("catalog_product") for record in records if record.get("product_name") or record.get("catalog_product")}
    differences = [_number(record.get("difference")) for record in records]
    return {
        "trays": len(unique_trays),
        "sku": len(skus),
        "pieces": sum(_number(record.get("actual_quantity")) for record in records),
        "difference": sum(differences),
        "duplicates": sum(1 for record in records if record.get("duplicate_tray")),
        "shortages": sum(1 for value in differences if value < 0),
        "surpluses": sum(1 for value in differences if value > 0),
        "unknown_products": sum(1 for record in records if record.get("ean") and not record.get("recognized")),
    }


def new_session(name: str, records: list[dict], operator: str = "") -> dict:
    created_at = datetime.now().isoformat(timespec="seconds")
    return {
        "id": f"INV-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "name": str(name or "Inwentaryzacja").strip() or "Inwentaryzacja",
        "created_at": created_at,
        "operator": str(operator or "").strip(),
        "records": records,
        "summary": session_summary(records),
    }


def mobile_catalog_rows(products: dict) -> list[dict]:
    rows = []
    for name, raw_data in sorted((products or {}).items(), key=lambda item: item[0].casefold()):
        data = raw_data if isinstance(raw_data, dict) else {}
        for ean in sorted(_product_eans(data)):
            rows.append({
                "EAN": ean,
                "SKU": data.get("SKU", data.get("sku", "")),
                "Nazwa produktu": name,
                "Ilość domyślna w tacce": default_tray_quantity(data),
                "Poziom opakowania": "Produkt / Display / Master Case",
            })
    return rows


def build_inventory_report_pdf(session: dict, font_regular="Helvetica", font_bold="Helvetica-Bold") -> bytes:
    """Tworzy drukowalny raport wybranej sesji inwentaryzacji."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    if font_regular == "Helvetica":
        arial_regular = "C:/Windows/Fonts/arial.ttf"
        arial_bold = "C:/Windows/Fonts/arialbd.ttf"
        if os.path.exists(arial_regular) and os.path.exists(arial_bold):
            try:
                if "InventoryReportFont" not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont("InventoryReportFont", arial_regular))
                    pdfmetrics.registerFont(TTFont("InventoryReportFont-Bold", arial_bold))
                font_regular, font_bold = "InventoryReportFont", "InventoryReportFont-Bold"
            except Exception:
                pass

    records = list((session or {}).get("records", []))
    summary = (session or {}).get("summary") or session_summary(records)
    output = io.BytesIO()
    document = SimpleDocTemplate(
        output, pagesize=landscape(A4), leftMargin=10 * mm, rightMargin=10 * mm,
        topMargin=10 * mm, bottomMargin=12 * mm,
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle("inventory_title", parent=styles["Title"], fontName=font_bold, fontSize=16, leading=20)
    normal = ParagraphStyle("inventory_normal", parent=styles["BodyText"], fontName=font_regular, fontSize=7, leading=9)
    header = ParagraphStyle("inventory_header", parent=normal, fontName=font_bold, alignment=TA_CENTER, textColor=colors.white)
    story = [
        Paragraph("Raport inwentaryzacji", title),
        Paragraph(
            f"Sesja: {session.get('name', 'Inwentaryzacja')} &nbsp;&nbsp; "
            f"Utworzono: {session.get('created_at', '')} &nbsp;&nbsp; "
            f"Operator: {session.get('operator', '') or '—'}",
            normal,
        ),
        Spacer(1, 5 * mm),
    ]
    summary_data = [
        [Paragraph("Tacki", header), Paragraph("SKU", header), Paragraph("Sztuki", header), Paragraph("Różnica", header), Paragraph("Duplikaty", header)],
        [str(summary["trays"]), str(summary["sku"]), str(summary["pieces"]), str(summary["difference"]), str(summary["duplicates"])],
    ]
    summary_table = Table(summary_data, colWidths=[35 * mm] * 5, hAlign="LEFT")
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
        ("FONTNAME", (0, 1), (-1, -1), font_regular),
        ("ALIGN", (0, 1), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B7C9D6")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.extend([summary_table, Spacer(1, 5 * mm)])

    rows = [[
        Paragraph(text, header) for text in ("Lp.", "Data/czas", "Operator", "ID tacki", "Produkt", "EAN/GTIN", "Rzecz.", "Nom.", "Różnica", "Uwagi")
    ]]
    for index, record in enumerate(records, start=1):
        rows.append([
            Paragraph(str(index), normal), Paragraph(str(record.get("timestamp", "")), normal),
            Paragraph(str(record.get("operator", "")), normal), Paragraph(str(record.get("tray_id", "")), normal),
            Paragraph(str(record.get("product_name", record.get("catalog_product", ""))), normal), Paragraph(str(record.get("ean", "")), normal),
            Paragraph(str(record.get("actual_quantity", 0)), normal), Paragraph(str(record.get("nominal_quantity", 0)), normal),
            Paragraph(str(record.get("difference", 0)), normal), Paragraph(str(record.get("issue", "")), normal),
        ])
    table = Table(rows, colWidths=[9 * mm, 27 * mm, 25 * mm, 19 * mm, 55 * mm, 28 * mm, 14 * mm, 14 * mm, 16 * mm, 35 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C5D0D8")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 1), (0, -1), "CENTER"),
        ("ALIGN", (6, 1), (8, -1), "CENTER"),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F8FB")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(table)
    document.build(story)
    return output.getvalue()


def build_tray_labels_pdf(tray_ids: list, font_regular="Helvetica", font_bold="Helvetica-Bold") -> bytes:
    """Generuje etykiety Zebra: jedna tacka na stronę 40 x 60 mm."""
    from reportlab.graphics import renderPDF
    from reportlab.graphics.barcode import qr
    from reportlab.graphics.shapes import Drawing
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas

    if font_regular == "Helvetica":
        arial_regular = "C:/Windows/Fonts/arial.ttf"
        arial_bold = "C:/Windows/Fonts/arialbd.ttf"
        if os.path.exists(arial_regular) and os.path.exists(arial_bold):
            try:
                if "InventoryLabelFont" not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont("InventoryLabelFont", arial_regular))
                    pdfmetrics.registerFont(TTFont("InventoryLabelFont-Bold", arial_bold))
                font_regular, font_bold = "InventoryLabelFont", "InventoryLabelFont-Bold"
            except Exception:
                pass

    output = io.BytesIO()
    width, height = 40 * mm, 60 * mm
    pdf = canvas.Canvas(output, pagesize=(width, height))
    valid_items = []
    for raw_item in tray_ids:
        item = raw_item if isinstance(raw_item, dict) else {"tray_id": raw_item}
        tray_id = normalize_tray_id(item.get("tray_id"))
        if not tray_id:
            continue
        valid_items.append((item, tray_id))
    for index, (item, tray_id) in enumerate(valid_items):
        if index:
            pdf.showPage()
        margin = 2 * mm
        pdf.setLineWidth(0.5)
        pdf.rect(margin, margin, width - 2 * margin, height - 2 * margin)
        title = str(item.get("tray_name") or "TACKA")[:28]
        product = str(item.get("product_name") or "—")[:46]
        quantity = item.get("actual_quantity", item.get("nominal_quantity", "—"))
        operator = str(item.get("operator") or "—")[:22]
        status = str(item.get("status") or "W produkcji")[:18]
        pdf.setFont(font_bold, 7)
        pdf.drawCentredString(width / 2, height - 6 * mm, title)
        pdf.setFont(font_bold, 13)
        pdf.drawCentredString(width / 2, height - 12 * mm, f"TRAY-{tray_id}")
        pdf.setFont(font_regular, 6.5)
        product_lines = [product[position:position + 26] for position in range(0, len(product), 26)] or ["—"]
        for line_number, line in enumerate(product_lines[:2]):
            pdf.drawCentredString(width / 2, height - (17 + line_number * 3) * mm, line)
        pdf.setFont(font_bold, 7)
        pdf.drawCentredString(width / 2, height - 24 * mm, f"Ilość: {quantity} szt.")
        pdf.setFont(font_regular, 6)
        pdf.drawCentredString(width / 2, height - 27 * mm, f"Status: {status}")
        pdf.drawString(4 * mm, 29 * mm, "[ ] Policzone")
        pdf.drawString(4 * mm, 26 * mm, f"Operator: {operator}")
        widget = qr.QrCodeWidget(tray_qr_payload(item))
        bounds = widget.getBounds()
        size = 22 * mm
        drawing = Drawing(size, size, transform=[size / (bounds[2] - bounds[0]), 0, 0, size / (bounds[3] - bounds[1]), 0, 0])
        drawing.add(widget)
        renderPDF.draw(drawing, pdf, (width - size) / 2, 2.5 * mm)
    pdf.save()
    return output.getvalue()


def build_tray_labels_zpl(tray_ids: list, dpi=203, orientation="Pionowa") -> bytes:
    """ZPL dla Zebra: etykieta 40 x 60 mm, jedna definicja na tackę."""
    dots_per_mm = 12 if int(dpi) == 203 else 18
    width, height = 40 * dots_per_mm, 60 * dots_per_mm
    direction = "N" if orientation == "Pionowa" else "B"

    def clean(value):
        return str(value or "—").replace("^", " ").replace("~", " ").replace("\r", " ").replace("\n", " ")[:38]

    labels = []
    for raw_item in tray_ids:
        item = raw_item if isinstance(raw_item, dict) else {"tray_id": raw_item}
        tray_id = normalize_tray_id(item.get("tray_id"))
        if not tray_id:
            continue
        product = clean(item.get("product_name"))
        quantity = clean(item.get("actual_quantity", item.get("nominal_quantity", "")))
        operator = clean(item.get("operator"))
        payload = tray_qr_payload(item)
        labels.append(
            f"^XA^PW{width}^LL{height}^FW{direction}"
            f"^FO35,30^A0N,26,26^FD{clean(item.get('tray_name') or 'TACKA')}^FS"
            f"^FO35,65^A0N,48,48^FDTRAY-{tray_id}^FS"
            f"^FO35,125^A0N,24,24^FD{product}^FS"
            f"^FO35,160^A0N,28,28^FDIlosc: {quantity} szt.^FS"
            f"^FO35,198^A0N,22,22^FD[ ] Policzone^FS"
            f"^FO35,228^A0N,20,20^FDOperator: {operator}^FS"
            f"^FO{int(width * 0.27)},270^BQN,2,5^FDLA,{payload}^FS^XZ"
        )
    return "\n".join(labels).encode("utf-8")
