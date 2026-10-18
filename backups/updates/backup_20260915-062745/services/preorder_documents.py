"""Pionowy, czytelny PDF dla niezależnych Pre-Orderów."""

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image as RLImage, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def build_preorder_pdf(items, meta, *, font_regular="Helvetica", font_bold="Helvetica-Bold", language="pl", logo_path=""):
    """Buduje PDF Pre-Orderu w pionie, po jednej czytelnej karcie na pozycję."""
    is_english = language.lower() == "en"
    labels = {
        "title": "E-Order - Elektroniczne Potwierdzenie Zamówienia" if not is_english else "E-Order - Electronic Order Confirmation",
        "order": "Numer Pre-Orderu" if not is_english else "Pre-Order No.",
        "order_date": "Data zamowienia" if not is_english else "Order date",
        "delivery": "Planowana data dostawy" if not is_english else "Planned delivery date",
        "recipient": "Odbiorca" if not is_english else "Recipient",
        "address": "Adres dostawy" if not is_english else "Delivery address",
        "item": "POZYCJA" if not is_english else "ITEM",
        "customer": "Klient" if not is_english else "Customer",
        "product": "Produkt / typ" if not is_english else "Product / type",
        "sku": "SKU / EAN", "filters": "Kolor filtrow" if not is_english else "Filter color", "leaves": "Ilosc listkow" if not is_english else "Leaf count",
        "series": "Seria" if not is_english else "Series", "batch": "Partia" if not is_english else "Batch / LOT",
        "dimensions": "Wymiary filtrow" if not is_english else "Filter dimensions",
        "paper": "Kolor / nazwa papieru" if not is_english else "Paper color / name",
        "criteria": "Inne kryteria" if not is_english else "Other criteria",
        "net": "Ilosc" if not is_english else "Quantity",
        "order_cartons": "Ilosc kartonow z zamowienia" if not is_english else "Order cartons",
        "display": "Ilosc w display" if not is_english else "Qty in display",
        "carton": "Ilosc w kartonie" if not is_english else "Qty in carton",
        "cartons_palette": "Kartony na palecie" if not is_english else "Cartons on pallet",
        "displays_palette": "Displaye na palecie" if not is_english else "Displays on pallet",
        "pallets": "Rozbicie paletowe" if not is_english else "Pallet breakdown",
        "pallet_summary": "PODSUMOWANIE PALET" if not is_english else "PALLET SUMMARY",
        "notes": "Uwagi" if not is_english else "Notes",
    }
    meta = meta or {}

    def pallet_breakdown(item):
        try:
            cartons = float(item.get("qty_net", 0) or 0) / float(item.get("qty_carton", 0) or 0)
            capacity = float(item.get("qty_cartons_palette", 0) or 0)
        except (TypeError, ValueError, ZeroDivisionError):
            return str(item.get("pallet_breakdown", "-"))
        if cartons <= 0 or capacity <= 0:
            return str(item.get("pallet_breakdown", "-"))
        full_pallets = int(cartons // capacity)
        remaining_cartons = cartons - full_pallets * capacity
        number = lambda value: f"{value:g}" if is_english else f"{value:g}".replace(".", ",")
        if is_english:
            if full_pallets and remaining_cartons:
                return f"{full_pallets} pallet{'s' if full_pallets != 1 else ''} + {number(remaining_cartons)} cartons"
            if full_pallets:
                return f"{full_pallets} pallet{'s' if full_pallets != 1 else ''}"
            return f"{number(remaining_cartons)} cartons"
        return str(item.get("pallet_breakdown", "-"))
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=17 * mm, bottomMargin=17 * mm)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("PreOrderTitle", parent=styles["Title"], fontName=font_bold, fontSize=17, leading=21, textColor=colors.HexColor("#173B7A"))
    section = ParagraphStyle("PreOrderSection", parent=styles["Normal"], fontName=font_bold, fontSize=10, leading=13, textColor=colors.white, alignment=TA_CENTER)
    label = ParagraphStyle("PreOrderLabel", parent=styles["Normal"], fontName=font_bold, fontSize=8, leading=10, textColor=colors.HexColor("#173B7A"))
    value = ParagraphStyle("PreOrderValue", parent=styles["Normal"], fontName=font_regular, fontSize=8, leading=10)
    recipient = meta.get("recipient", {}) or {}
    address = meta.get("delivery_address", {}) or {}
    recipient_text = recipient.get("company") or recipient.get("name") or "-"
    contact = recipient.get("contact") or recipient.get("email", "")
    if contact:
        recipient_text += f" ({contact})"
    address_text = ", ".join(part for part in [address.get("street", ""), " ".join(part for part in [address.get("postal_code", ""), address.get("city", "")] if part), address.get("country", "")] if part) or "-"
    title_paragraph = Paragraph(labels["title"], title)
    if logo_path:
        try:
            logo = RLImage(logo_path, width=30 * mm, height=10 * mm)
            title_table = Table([[title_paragraph, logo]], colWidths=[134 * mm, 30 * mm])
            title_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (1, 0), (1, 0), "RIGHT"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
            story = [title_table, Spacer(1, 4 * mm)]
        except Exception:
            story = [title_paragraph, Spacer(1, 4 * mm)]
    else:
        story = [title_paragraph, Spacer(1, 4 * mm)]
    included_header = meta.get("included_header_fields", {}) or {}
    header_fields = [("order_no", labels["order"], meta.get("order_no", "-")), ("order_date", labels["order_date"], meta.get("order_date", "-")), ("delivery_date", labels["delivery"], meta.get("delivery_date", "-")), ("recipient", labels["recipient"], recipient_text), ("delivery_address", labels["address"], address_text)]
    visible_header = [(field, field_label, field_value) for field, field_label, field_value in header_fields if included_header.get(field, True)]
    header_rows = []
    for position in range(0, len(visible_header), 2):
        first = visible_header[position]
        second = visible_header[position + 1] if position + 1 < len(visible_header) else None
        row = [Paragraph(first[1], label), Paragraph(escape(str(first[2])), value)]
        row.extend([Paragraph(second[1], label), Paragraph(escape(str(second[2])), value)] if second else ["", ""])
        header_rows.append(row)
    if header_rows:
        header_table = Table(header_rows, colWidths=[35 * mm, 52 * mm, 35 * mm, 42 * mm])
        header_table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")), ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EFF6FF")), ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#EFF6FF")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
        story.extend([header_table, Spacer(1, 7 * mm)])
    for index, item in enumerate(items or [], start=1):
        product = escape(str(item.get("product_name", "-")))
        included = item.get("included_fields", {}) or {}
        show = lambda field_name: included.get(field_name, True)
        rows = [[Paragraph(f"{labels['item']} {index}: {product}", section), "", "", ""]]
        order_cartons = item.get("order_cartons", 0)
        try:
            order_cartons = f"{float(order_cartons):g}"
        except (TypeError, ValueError):
            pass
        fields = [("order_channel", labels["customer"], item.get("order_channel", "-")), ("product_type", labels["product"], item.get("product_type", "-")), ("sku", labels["sku"], item.get("sku", "-")), ("series", labels["series"], item.get("series", "-")), ("batch", labels["batch"], item.get("batch", "-")), ("filter_color", labels["filters"], item.get("filter_color", "-")), ("leaf_count", labels["leaves"], item.get("leaf_count", 0)), ("dimensions", labels["dimensions"], item.get("dimensions", "-")), ("box_paper_color", labels["paper"], item.get("box_paper_color", "-")), ("other_criteria", labels["criteria"], item.get("other_criteria", "-")), ("qty_net", labels["net"], item.get("qty_net", 0)), ("qty_display_pieces", labels["display"], item.get("qty_display_pieces", 0)), ("qty_carton", labels["carton"], item.get("qty_carton", 0)), ("order_cartons", labels["order_cartons"], order_cartons), ("qty_cartons_palette", labels["cartons_palette"], item.get("qty_cartons_palette", 0)), ("qty_displays_palette", labels["displays_palette"], item.get("qty_displays_palette", 0)), ("pallet_breakdown", labels["pallets"], pallet_breakdown(item))]
        visible_fields = [(field, field_label, field_value) for field, field_label, field_value in fields if show(field)]
        for position in range(0, len(visible_fields), 2):
            first = visible_fields[position]
            second = visible_fields[position + 1] if position + 1 < len(visible_fields) else None
            row = [Paragraph(first[1], label), Paragraph(escape(str(first[2])), value)]
            row.extend([Paragraph(second[1], label), Paragraph(escape(str(second[2])), value)] if second else ["", ""])
            rows.append(row)
        show_order_notes = included_header.get("confirmation_note", True) and any((entry.get("included_fields", {}) or {}).get("other_criteria", True) for entry in (items or []))
        if show_order_notes and str(meta.get("confirmation_note", "") or "").strip():
            rows.append([Paragraph(labels["notes"], label), Paragraph(escape(str(meta.get("confirmation_note", ""))), value), "", ""])
        item_table = Table(rows, colWidths=[35 * mm, 52 * mm, 35 * mm, 42 * mm])
        item_style = [("SPAN", (0, 0), (-1, 0)), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#173B7A")), ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#F8FAFC")), ("BACKGROUND", (2, 1), (2, -1), colors.HexColor("#F8FAFC")), ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]
        item_table.setStyle(TableStyle(item_style))
        story.append(item_table)
        if index < len(items): story.append(Spacer(1, 4 * mm))
    if items:
        pallet_groups = {}
        for item in items:
            try:
                cartons = float(item.get("qty_net", 0) or 0) / float(item.get("qty_carton", 0) or 0)
                capacity = float(item.get("qty_cartons_palette", 0) or 0)
            except (TypeError, ValueError, ZeroDivisionError):
                continue
            if capacity > 0:
                pallet_groups[capacity] = pallet_groups.get(capacity, 0) + cartons
        summary_rows = [[Paragraph(text, section) for text in (("Kartony / paleta", "Kartony lacznie", "Pelne palety", "Pozostale kartony", "Palety do wysylki") if not is_english else ("Cartons / pallet", "Total cartons", "Full pallets", "Remaining cartons", "Pallets to dispatch"))]]
        for capacity, cartons in sorted(pallet_groups.items()):
            full_pallets = int(cartons // capacity)
            remaining_cartons = cartons - full_pallets * capacity
            pallets_to_dispatch = full_pallets + (1 if remaining_cartons > 0 else 0)
            summary_rows.append([Paragraph(f"{capacity:g}", value), Paragraph(f"{cartons:g}", value), Paragraph(str(full_pallets), value), Paragraph(f"{remaining_cartons:g}", value), Paragraph(str(pallets_to_dispatch), value)])
        story.extend([Spacer(1, 6 * mm), Paragraph(labels["pallet_summary"], title), Spacer(1, 3 * mm)])
        summary_table = Table(summary_rows, colWidths=[33 * mm, 33 * mm, 33 * mm, 33 * mm, 32 * mm], repeatRows=1)
        summary_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#173B7A")), ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#173B7A")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
        story.append(summary_table)
    doc.build(story)
    return buffer.getvalue()
