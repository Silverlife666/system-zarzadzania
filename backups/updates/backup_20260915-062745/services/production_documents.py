"""Wspólne generatory PDF dokumentów produkcyjnych.

Nie znają Streamlit ani rejestru dokumentów: aplikacja przekazuje im jedynie
dane, czcionki i opcjonalną dekorację strony.
"""

from __future__ import annotations

from io import BytesIO
from datetime import datetime
from xml.sax.saxutils import escape

import requests
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def included_value(item: dict, key: str, default=""):
    """Zwraca wartość tylko wtedy, gdy pole zostało zaznaczone do dokumentu."""
    included = item.get("included_fields", {}) or {}
    return item.get(key, default) if included.get(key, True) else ""


def included_meta_value(data: dict, key: str, default=""):
    """Zwraca wartość nagłówka dokumentu tylko wtedy, gdy jest uwzględniona."""
    data = data or {}
    included = data.get("included_fields", {}) or {}
    return data.get(key, default) if included.get(key, True) else ""


PRINTER_COPY_EXCLUDED_SECTIONS = frozenset({
    "Nagłówek zlecenia",
    "TDS: identyfikacja",
    "TDS: Produkt",
    "TDS: Display",
    "TDS: Master Case",
    "TDS: Paleta",
    "TDS: relacje pakowania",
    "Przeliczenie pozycji: Produkt → Display → Master Case → Paleta",
})


def printer_copy_data(data):
    """Zwraca dane PDF dla drukarni, bez wewnętrznych danych TDS i przeliczeń."""
    return {
        section_title: fields
        for section_title, fields in (data or {}).items()
        if section_title not in PRINTER_COPY_EXCLUDED_SECTIONS
    }


PRINTER_COPY_EN_SECTIONS = {
    "Informacje Ogólne": "General information",
    "Sekcja I: Parametry Podstawowe & Materiały": "Section I: Core parameters and materials",
    "Specyfikacja projektu dla drukarni": "Artwork specification for printer",
    "SEKCJA II: SPECYFIKACJA": "Section II: Print specification",
    "Sekcja III: Display": "Section III: Display packaging",
    "SEKCJA IV: INNE ISTOTNE INFORMACJE": "Section IV: Additional requirements",
}

PRINTER_COPY_EN_FIELDS = {
    "Numer wewnętrzny": "Internal reference", "Plik": "File reference", "Produkt": "Product",
    "Nazwa produktu": "Product name", "Inne kryteria": "Other requirements", "Wymiary": "Dimensions",
    "Kolor filtra": "Filter colour", "Kolor papieru w boxie": "Box paper colour",
    "Druk": "Printing process", "Zamówienie/klient": "Customer / order reference", "Numer partii / LOT": "Batch / LOT number",
    "Ilość netto": "Net quantity", "Ilość z zapasem": "Quantity incl. allowance", "Ilość do produkcji": "Production quantity",
    "Ilość do wysyłki": "Dispatch quantity", "Ilość box": "Box quantity", "Ilość cover": "Cover quantity",
    "Ilość display": "Display quantity", "Ilość w kartonie zbiorczym": "Units per master case",
    "Numer projektu": "Artwork number", "Wersja projektu": "Artwork revision", "Link do pliku źródłowego": "Source file link",
    "Załącznik projektu": "Artwork attachment", "Rozmiar załącznika": "Attachment size", "Wgrano": "Uploaded on", "Wgrał": "Uploaded by",
    "Okładka - Gramatura": "Cover - substrate grammage", "Okładka - Zadruk": "Cover - print specification",
    "Okładka - Rozbarwienie": "Cover - colour separation", "Okładka - Druk": "Cover - printing process",
    "Okładka - Lakier": "Cover - varnish", "Okładka - Foliowanie/Lakierowanie awers": "Cover - front-side finishing",
    "Okładka - Foliowanie/Lakierowanie rewers": "Cover - reverse-side finishing", "Okładka - Wykrojnik": "Cover - die-cutting tool",
    "Box rolls - Gramatura": "Roll box - substrate grammage", "Box rolls - Zadruk": "Roll box - print specification",
    "Box rolls - Rozbarwienie": "Roll box - colour separation", "Box rolls - Druk": "Roll box - printing process",
    "Box rolls - Lakier": "Roll box - varnish", "Box rolls - Foliowanie front": "Roll box - front-side finishing",
    "Box rolls - Foliowanie tył": "Roll box - reverse-side finishing", "Box rolls - Wykrojnik": "Roll box - die-cutting tool",
    "Bletka - Gramatura": "Rolling paper booklet - substrate grammage", "Bletka - Zadruk": "Rolling paper booklet - print specification",
    "Bletka - Rozbarwienie": "Rolling paper booklet - colour separation", "Bletka - Druk": "Rolling paper booklet - printing process",
    "Bletka - Lakier": "Rolling paper booklet - varnish", "Bletka - Foliowanie front": "Rolling paper booklet - front-side finishing",
    "Bletka - Foliowanie tył": "Rolling paper booklet - reverse-side finishing", "Bletka - Wykrojnik": "Rolling paper booklet - die-cutting tool",
    "Arkusz filtra - Gramatura": "Filter sheet - substrate grammage", "Arkusz filtra - Zadruk": "Filter sheet - print specification",
    "Arkusz filtra - Rozbarwienie": "Filter sheet - colour separation", "Arkusz filtra - Druk": "Filter sheet - printing process",
    "Arkusz filtra - Lakier": "Filter sheet - varnish", "Arkusz filtra - Foliowanie front": "Filter sheet - front-side finishing",
    "Arkusz filtra - Foliowanie tył": "Filter sheet - reverse-side finishing", "Arkusz filtra - Wykrojnik": "Filter sheet - die-cutting tool",
    "Ilość perforacji": "Number of perforations", "Dodatkowa perforacja": "Additional perforation",
    "Ilość listków": "Number of leaves", "Ilość w Display": "Units per display", "Ilość w kartonie": "Units per master case",
    "Nadruk na kartonie": "Print on master case", "Display": "Display type", "Gramatura (Display)": "Display - substrate grammage",
    "Zadruk (Display)": "Display - print specification", "Rozbarwienie (Display)": "Display - colour separation",
    "Lakier (Display)": "Display - varnish", "Wykrojnik (Display)": "Display - die-cutting tool",
    "Foliowanie/lakierowanie (Display)": "Display - finishing", "Uwagi do zamówienia": "Order notes",
}

PRINTER_COPY_EN_VALUES = {
    "tak": "Yes", "nie": "No", "brak": "None", "mat": "Matt", "połysk": "Gloss", "awers": "Front side", "rewers": "Reverse side",
    "4+0": "4/0 CMYK", "4+4": "4/4 CMYK", "1+0": "1/0", "1+1": "1/1", "pantone": "Pantone",
}

PRINTER_COPY_EN_UNTRANSLATED_FIELDS = {
    "Produkt", "Nazwa produktu", "Zamówienie/klient", "Numer partii / LOT",
    "Numer wewnętrzny", "Plik", "Numer projektu", "Wersja projektu",
    "Link do pliku źródłowego", "Załącznik projektu", "SHA-256", "Wgrano", "Wgrał",
}

DEEPL_PRINTING_CONTEXT = (
    "This is a packaging and print-production specification. Use established British English "
    "printing terminology, including substrate grammage, colour separation, printing process, "
    "varnish, lamination, finishing and die-cutting. Preserve dimensions, product codes, "
    "brand names and technical abbreviations exactly."
)


class DeepLTranslationError(RuntimeError):
    """Błąd tłumaczenia, po którym można przejść na wpisy ręczne."""


def _manual_translation_key(section_title, field_name):
    """Tworzy stabilny, niewidoczny dla użytkownika identyfikator pola."""
    return f"{section_title}\x1f{field_name}"


def _is_custom_translatable_value(field, value):
    return (
        isinstance(value, str)
        and field not in PRINTER_COPY_EN_UNTRANSLATED_FIELDS
        and value.strip()
        and value.strip().casefold() not in PRINTER_COPY_EN_VALUES
    )


def printer_copy_translation_rows(data, translation_overrides=None):
    """Zwraca opisy własne, które można ręcznie wpisać po angielsku."""
    overrides = translation_overrides or {}
    rows = []
    for section_title, fields in printer_copy_data(data).items():
        for field, value in (fields or {}).items():
            if _is_custom_translatable_value(field, value):
                key = _manual_translation_key(section_title, field)
                rows.append({
                    "key": key,
                    "Polski": value,
                    "English version": overrides.get(key, ""),
                })
    return rows


def _deepl_translate_texts(texts, api_key):
    """Tłumaczy wolne opisy przez DeepL Free/Pro, zachowując branżowy kontekst."""
    unique_texts = list(dict.fromkeys(text for text in texts if str(text).strip()))
    if not unique_texts:
        return {}
    endpoint = "https://api-free.deepl.com/v2/translate" if str(api_key).endswith(":fx") else "https://api.deepl.com/v2/translate"
    translated = {}
    for start in range(0, len(unique_texts), 50):
        batch = unique_texts[start:start + 50]
        try:
            response = requests.post(
                endpoint,
                data={
                    "text": batch,
                    "source_lang": "PL",
                    "target_lang": "EN-GB",
                    "formality": "prefer_more",
                    "context": DEEPL_PRINTING_CONTEXT,
                },
                headers={"Authorization": f"DeepL-Auth-Key {api_key}"},
                timeout=30,
            )
            response.raise_for_status()
            translations = response.json()["translations"]
        except requests.HTTPError as error:
            if error.response is not None and error.response.status_code == 456:
                raise DeepLTranslationError("Wykorzystano limit tłumaczeń DeepL.") from error
            raise DeepLTranslationError("Nie udało się przetłumaczyć opisów przez DeepL.") from error
        except (KeyError, ValueError, requests.RequestException) as error:
            raise DeepLTranslationError("Nie udało się przetłumaczyć opisów przez DeepL.") from error
        if len(translations) != len(batch):
            raise DeepLTranslationError("DeepL zwrócił niepełne tłumaczenie opisów.")
        translated.update({source: item["text"] for source, item in zip(batch, translations)})
    return translated


def printer_copy_data_en(data, deepl_api_key="", translation_overrides=None):
    """Tworzy angielską kopię dla drukarni, tłumacząc opisy własne przez DeepL."""
    source_data = printer_copy_data(data)
    overrides = translation_overrides or {}
    free_texts = [
        value
        for section_title, fields in source_data.items()
        for field, value in (fields or {}).items()
        if _is_custom_translatable_value(field, value)
        and not str(overrides.get(_manual_translation_key(section_title, field), "")).strip()
    ]
    deepl_translations = _deepl_translate_texts(free_texts, deepl_api_key) if deepl_api_key else {}
    translated = {}
    for section_title, fields in source_data.items():
        translated_fields = {}
        for field, value in (fields or {}).items():
            translated_value = value
            if isinstance(value, str):
                manual_value = str(overrides.get(_manual_translation_key(section_title, field), "")).strip()
                translated_value = PRINTER_COPY_EN_VALUES.get(
                    value.strip().casefold(), manual_value or deepl_translations.get(value, value),
                )
            translated_fields[PRINTER_COPY_EN_FIELDS.get(field, field)] = translated_value
        translated[PRINTER_COPY_EN_SECTIONS.get(section_title, section_title)] = translated_fields
    return translated


def build_structured_document_pdf(data, *, document_title, font_regular="Helvetica", font_bold="Helvetica-Bold", attachment_image_bytes=None, visual_attachments=(), extra_flowables=(), canvasmaker=None):
    """Buduje uniwersalny PDF z sekcjami klucz → wartość i zwraca bajty."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=45, bottomMargin=45)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("ProductionTitle", parent=styles["Heading1"], fontName=font_bold, fontSize=15, spaceAfter=12, textColor=colors.HexColor("#1E3A8A"))
    section_style = ParagraphStyle("ProductionSection", parent=styles["Heading2"], fontName=font_bold, fontSize=11, spaceBefore=12, spaceAfter=6, textColor=colors.HexColor("#0F172A"))
    normal_style = ParagraphStyle("ProductionNormal", parent=styles["Normal"], fontName=font_regular, fontSize=9, leading=12, spaceAfter=2)
    story = [Paragraph(escape(str(document_title)), title_style), Spacer(1, 4)]
    for section_title, fields in (data or {}).items():
        if not fields:
            continue
        story.append(Paragraph(escape(str(section_title)), section_style))
        table_data = [[Paragraph(escape(str(key)), normal_style), Paragraph(escape(str(value)), normal_style)] for key, value in fields.items()]
        table = Table(table_data, colWidths=[200, 345])
        style = [
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]
        for index in range(len(table_data)):
            style.append(("BACKGROUND", (0, index), (-1, index), colors.HexColor("#F8FAFC") if index % 2 == 0 else colors.white))
        table.setStyle(TableStyle(style))
        story.extend([table, Spacer(1, 6)])
    if attachment_image_bytes:
        try:
            image = RLImage(BytesIO(attachment_image_bytes))
            image._restrictSize(350, 350)
            story.extend([Paragraph("ZAŁĄCZNIK GRAFICZNY", section_style), image, Spacer(1, 6)])
        except Exception:
            story.append(Paragraph("Załącznik graficzny nie mógł zostać osadzony w PDF.", normal_style))
    for attachment in visual_attachments or ():
        label = str(attachment.get("label", "Załącznik graficzny"))
        file_name = str(attachment.get("name", "plik"))
        image_bytes = attachment.get("bytes")
        if not image_bytes:
            continue
        story.append(Paragraph(escape(label.upper()), section_style))
        try:
            image = RLImage(BytesIO(image_bytes))
            image._restrictSize(350, 350)
            story.extend([image, Spacer(1, 6)])
        except Exception:
            story.append(Paragraph(escape(f"Załącznik: {file_name}"), normal_style))
    story.extend(list(extra_flowables or ()))
    if canvasmaker:
        doc.build(story, canvasmaker=canvasmaker)
    else:
        doc.build(story)
    return buffer.getvalue()


def build_eorder_bilingual_pdf(items_list, meta_info, *, font_regular="Helvetica", font_bold="Helvetica-Bold", canvasmaker=None):
    """Buduje dwujęzyczny E-Order i zwraca jego bajty, bez zapisu do rejestru."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=30, leftMargin=30, topMargin=45, bottomMargin=40)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("EOrderBilingualTitle", parent=styles["Heading1"], fontName=font_bold, fontSize=16, spaceAfter=7, textColor=colors.HexColor("#1E3A8A"))
    meta_style = ParagraphStyle("EOrderBilingualMeta", parent=styles["Normal"], fontName=font_regular, fontSize=9, leading=13, textColor=colors.HexColor("#0F172A"))
    header_style = ParagraphStyle("EOrderBilingualHeader", parent=styles["Normal"], fontName=font_bold, fontSize=7.5, leading=9, textColor=colors.white)
    cell_style = ParagraphStyle("EOrderBilingualCell", parent=styles["Normal"], fontName=font_regular, fontSize=7.5, leading=9, textColor=colors.HexColor("#0F172A"))
    recipient = meta_info.get("recipient", {}) or {}
    recipient = recipient if isinstance(recipient, dict) else {}
    address = meta_info.get("delivery_address", {}) or {}
    address = address if isinstance(address, dict) else {}
    recipient_name = recipient.get("company") or recipient.get("name") or "—"
    address_text = ", ".join(part for part in [
        address.get("street", ""), " ".join(part for part in [address.get("postal_code", ""), address.get("city", "")] if part), address.get("country", ""),
    ] if part) or "—"
    story = [
        Paragraph("E-Order - Elektroniczne Potwierdzenie Zamówienia / Electronic Order Confirmation", title_style),
        Paragraph(
            "<b>Nr zlecenia / Order No.:</b> " + escape(str(meta_info.get("order_no", "—")))
            + " &nbsp; | &nbsp; <b>Data zamówienia / Order date:</b> " + escape(str(meta_info.get("order_date", datetime.now().strftime("%d.%m.%Y"))))
            + " &nbsp; | &nbsp; <b>Data dostawy / Delivery date:</b> " + escape(str(meta_info.get("delivery_date", "—")))
            + " &nbsp; | &nbsp; <b>Priorytet / Priority:</b> " + escape(str(meta_info.get("priority", "normalny")))
            + " &nbsp; | &nbsp; <b>Wersja / Version:</b> " + escape(str(meta_info.get("document_version", "v1"))), meta_style,
        ), Spacer(1, 5),
        Paragraph(
            "<b>Odbiorca / Recipient:</b> " + escape(str(recipient_name))
            + "<br/><b>Adres dostawy / Delivery address:</b> " + escape(str(address_text))
            + "<br/><b>Status odpowiedzi / Response status:</b> " + escape(str(meta_info.get("response_status", "wysłano")))
            + " &nbsp; | &nbsp; <b>Potwierdzenie / Confirmation:</b> " + escape(str(meta_info.get("confirmation_note", "—") or "—")), meta_style,
        ), Spacer(1, 10),
    ]
    headers = ["Poz.<br/>Pos.", "Klient<br/>Customer", "Produkt / Product", "Poziom / Level", "SKU / EAN / LOT", "Ilość netto<br/>Net qty", "Produkcja<br/>Production", "Wysyłka<br/>Shipping", "Pakowanie / Packaging"]
    table_data = [[Paragraph(label, header_style) for label in headers]]
    for index, item in enumerate(items_list, start=1):
        packaging = item.get("packaging_calculation", {}) or {}
        identifiers = "<br/>".join(part for part in [
            f"SKU: {escape(str(item.get('sku', '')))}" if item.get("sku") else "",
            f"EAN {escape(str(item.get('packaging_level', 'Produkt')))}: {escape(str(item.get('ean_selected', '')))}" if item.get("ean_selected") else "",
            f"LOT: {escape(str(included_value(item, 'lot_number', '')))}" if included_value(item, "lot_number", "") else "",
        ] if part) or "—"
        packaging_text = f"Display: {packaging.get('displayow', 0)}<br/>Master Case: {packaging.get('mastercase', 0)}<br/>Palety / Pallets: {packaging.get('palet', 0)}"
        table_data.append([
            Paragraph(str(index), cell_style), Paragraph(escape(str(included_value(item, "order_channel", "—"))), cell_style),
            Paragraph(escape(str(included_value(item, "product_name", "—"))), cell_style), Paragraph(escape(str(included_value(item, "product_type", item.get("packaging_level", "—")))), cell_style),
            Paragraph(identifiers, cell_style), Paragraph(str(included_value(item, "qty_net", 0)), cell_style),
            Paragraph(str(included_value(item, "qty_production", item.get("qty_with_buffer", 0))), cell_style), Paragraph(str(included_value(item, "qty_shipping", item.get("qty_net", 0))), cell_style), Paragraph(packaging_text, cell_style),
        ])
    table = Table(table_data, colWidths=[28, 75, 120, 75, 145, 58, 62, 58, 105], repeatRows=1)
    style = [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A8A")), ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]
    for row_index in range(1, len(table_data)):
        style.append(("BACKGROUND", (0, row_index), (-1, row_index), colors.HexColor("#F8FAFC") if row_index % 2 else colors.white))
    table.setStyle(TableStyle(style))
    story.append(table)
    if canvasmaker:
        doc.build(story, canvasmaker=canvasmaker)
    else:
        doc.build(story)
    return buffer.getvalue()


def build_eorder_pdf(items_list, meta_info, *, font_regular="Helvetica", font_bold="Helvetica-Bold", logo_path="", canvasmaker=None):
    """Buduje jednojęzyczny E-Order; zapis i wersjonowanie zostają w aplikacji."""
    lang = str((meta_info or {}).get("lang", "pl")).lower()
    if lang not in {"pl", "en"}:
        lang = "pl"
    translations = {
        "pl": {
            "title": "E-Order – Elektroniczne Potwierdzenie Zamówienia", "order_date": "Data zamówienia",
            "delivery_date": "Data dostawy", "order_no": "Nr zlecenia", "priority": "Priorytet", "version": "Wersja",
            "recipient": "Odbiorca", "delivery_address": "Adres dostawy", "response": "Status odpowiedzi",
            "confirmation": "Potwierdzenie terminu i ilości", "reprint": "Reprint", "yes": "TAK", "no": "NIE",
            "headers": ["Poz.", "Klient", "Nazwa towaru lub usługi", "Produkt", "Inne kryteria", "Kolor filtrów", "Wymiar filtrów", "Kolor papieru", "Ilość netto", "Ilość w display", "Ilość w karton", "Kartony na palecie", "Displaye na palecie", "Ilość palet"],
        },
        "en": {
            "title": "E-Order – Electronic Order Confirmation", "order_date": "Order date",
            "delivery_date": "Delivery date", "order_no": "Order No.", "priority": "Priority", "version": "Version",
            "recipient": "Recipient", "delivery_address": "Delivery address", "response": "Response status",
            "confirmation": "Delivery date and quantity confirmation", "reprint": "Reprint", "yes": "YES", "no": "NO",
            "headers": ["Pos.", "Customer", "Product or service name", "Product", "Other criteria", "Filter color", "Dimensions Filter Tips", "Box paper color", "Net quantity", "Qty in display", "Qty in carton", "Cartons on palette", "Displays on palette", "Pallet quantity"],
        },
    }
    text = translations[lang]
    meta_info = meta_info or {}
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=30, leftMargin=30, topMargin=45, bottomMargin=40)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("EOrderTitle", parent=styles["Heading1"], fontName=font_bold, fontSize=16, spaceAfter=6, textColor=colors.HexColor("#1E3A8A"))
    meta_style = ParagraphStyle("EOrderMeta", parent=styles["Normal"], fontName=font_regular, fontSize=9, leading=14, textColor=colors.HexColor("#0F172A"))
    th_style = ParagraphStyle("EOrderTH", parent=styles["Normal"], fontName=font_bold, fontSize=8, leading=10, textColor=colors.white)
    td_style = ParagraphStyle("EOrderTD", parent=styles["Normal"], fontName=font_regular, fontSize=8, leading=10, textColor=colors.HexColor("#1E3A8A"))
    order_date = meta_info.get("order_date", datetime.now().strftime("%d.%m.%Y"))
    recipient = meta_info.get("recipient", {}) or {}
    address = meta_info.get("delivery_address", {}) or {}
    raw_reprint = str(meta_info.get("reprint", "NIE")).upper()
    reprint = text["yes"] if raw_reprint in {"TAK", "YES", "TRUE"} else text["no"]
    reprint_part = f"&nbsp;&nbsp;|&nbsp;&nbsp; <b>{text['reprint']}:</b> {reprint} " if not meta_info.get("hide_reprint") else " "
    meta_text = (
        f"<b>{text['order_date']}:</b> {order_date} &nbsp;&nbsp;|&nbsp;&nbsp; <b>{text['delivery_date']}:</b> {meta_info.get('delivery_date', '')} "
        f"&nbsp;&nbsp;|&nbsp;&nbsp; <b>{text['order_no']}:</b> {meta_info.get('order_no', '—')} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"{reprint_part}&nbsp;&nbsp;|&nbsp;&nbsp; <b>{text['priority']}:</b> {escape(str(meta_info.get('priority', 'normalny')))} "
        f"&nbsp;&nbsp;|&nbsp;&nbsp; <b>{text['version']}:</b> {escape(str(meta_info.get('document_version', 'v1')))}"
    )
    header = [Paragraph(text["title"], title_style), Spacer(1, 2), Paragraph(meta_text, meta_style)]
    if logo_path:
        try:
            logo = RLImage(logo_path, width=100, height=32)
            header_table = Table([[header, logo]], colWidths=[doc.width - 110, 110])
            header_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (1, 0), (1, 0), "RIGHT"), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
            story = [header_table]
        except Exception:
            story = list(header)
    else:
        story = list(header)
    recipient_name = recipient.get("company") or recipient.get("name") or "—"
    recipient_email = recipient.get("email", "")
    address_label = ", ".join(part for part in [address.get("street", ""), " ".join(part for part in [address.get("postal_code", ""), address.get("city", "")] if part), address.get("country", "")] if part) or "—"
    response_part = "" if meta_info.get("hide_response_status") else f"<b>{text['response']}:</b> {escape(str(meta_info.get('response_status', 'wysłano')))} &nbsp;&nbsp;|&nbsp;&nbsp; "
    confirmation_value = str(meta_info.get("confirmation_note", "") or "").strip()
    confirmation_label = str(meta_info.get("confirmation_label", "") or text["confirmation"])
    confirmation_part = "" if meta_info.get("hide_confirmation") or (meta_info.get("hide_empty_confirmation") and not confirmation_value) else f"<b>{escape(confirmation_label)}:</b> {escape(confirmation_value or '—')}"
    story.extend([Spacer(1, 4), Paragraph(
        f"<b>{text['recipient']}:</b> {escape(str(recipient_name))}{(' (' + escape(str(recipient_email)) + ')') if recipient_email else ''}<br/>"
        f"<b>{text['delivery_address']}:</b> {escape(str(address_label))}<br/>{response_part}"
        f"{confirmation_part}", meta_style), Spacer(1, 10)])
    table_data = [[Paragraph(header_text, th_style) for header_text in text["headers"]]]
    for index, item in enumerate(items_list or [], start=1):
        sku, selected_ean = str(item.get("sku", "")).strip(), str(item.get("ean_selected", "")).strip()
        level, lot = str(item.get("packaging_level", "Produkt")).strip(), str(included_value(item, "lot_number", "")).strip()
        label = escape(str(included_value(item, "product_name", "-")))
        identifier = " | ".join(value for value in [f"SKU: {escape(sku)}" if sku else "", f"EAN {escape(level)}: {escape(selected_ean)}" if selected_ean else ""] if value)
        if identifier:
            label += f"<br/><font size=7>{identifier}</font>"
        planning = " | ".join(value for value in [f"LOT: {escape(lot)}" if lot else "", f"Z zapasem: {included_value(item, 'qty_with_buffer', '')}" if included_value(item, "qty_buffer", "") else "", f"Produkcja: {included_value(item, 'qty_production', '')}" if included_value(item, "qty_production", "") else "", f"Wysyłka: {included_value(item, 'qty_shipping', '')}" if included_value(item, "qty_shipping", "") else ""] if value)
        if planning:
            label += f"<br/><font size=7>{planning}</font>"
        packaging = item.get("packaging_calculation", {}) or {}
        if packaging:
            label += f"<br/><font size=7>Pakowanie: {packaging.get('displayow', 0)} displaye | {packaging.get('mastercase', 0)} MC | {packaging.get('palet', 0)} palet</font>"
        values = [index, included_value(item, "order_channel", "-"), label, included_value(item, "product_type", "-"), included_value(item, "other_criteria", "-"), included_value(item, "filter_color", "-"), included_value(item, "dimensions", "-"), included_value(item, "box_paper_color", "-"), included_value(item, "qty_net", 0), included_value(item, "qty_display_pieces", 0), included_value(item, "qty_carton", 0), included_value(item, "qty_cartons_palette", 0), included_value(item, "qty_displays_palette", 0), included_value(item, "qty_pallets", 0)]
        table_data.append([Paragraph(str(value), td_style) for value in values])
    table = Table(table_data, colWidths=[20, 45, 75, 65, 48, 52, 57, 52, 52, 52, 52, 52, 52, 52], repeatRows=1)
    style = [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A8A")), ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]
    for row_index in range(1, len(table_data)):
        style.append(("BACKGROUND", (0, row_index), (-1, row_index), colors.HexColor("#F8FAFC") if row_index % 2 else colors.white))
    table.setStyle(TableStyle(style))
    story.append(table)
    if canvasmaker:
        doc.build(story, canvasmaker=canvasmaker)
    else:
        doc.build(story)
    return buffer.getvalue()


def build_worksheet_pdf(items_list, meta_info, *, font_regular="Helvetica", font_bold="Helvetica-Bold", logo_path="", bct_flowables=(), canvasmaker=None):
    """Buduje Kartę Pracy; status i zapis dokumentu pozostają w warstwie aplikacji."""
    meta_info = meta_info or {}
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=20, leftMargin=20, topMargin=45, bottomMargin=40)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("WorksheetTitle", parent=styles["Heading1"], fontName=font_bold, fontSize=16, spaceAfter=4, textColor=colors.HexColor("#1E3A8A"))
    meta_style = ParagraphStyle("WorksheetMeta", parent=styles["Normal"], fontName=font_regular, fontSize=9, leading=14, textColor=colors.HexColor("#0F172A"))
    th_style = ParagraphStyle("WorksheetTH", parent=styles["Normal"], fontName=font_bold, fontSize=7, leading=9, textColor=colors.white)
    td_style = ParagraphStyle("WorksheetTD", parent=styles["Normal"], fontName=font_regular, fontSize=7, leading=9, textColor=colors.HexColor("#1E3A8A"))
    title = Paragraph("KARTA PRACY – ZBIORCZE ZESTAWIENIE PRODUKCYJNE", title_style)
    meta = Paragraph(f"<b>Data:</b> {included_meta_value(meta_info, 'order_date', datetime.now().strftime('%d.%m.%Y'))} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Nr zlecenia:</b> {included_meta_value(meta_info, 'order_no', '14/2026')} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Priorytet:</b> {escape(str(meta_info.get('priority', 'normalny')))} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Wersja:</b> {escape(str(meta_info.get('document_version', 'v1')))}", meta_style)
    header = [title, Spacer(1, 2), meta]
    if logo_path:
        try:
            logo = RLImage(logo_path, width=282, height=52)
            header_table = Table([[header, logo]], colWidths=[doc.width - 110, 110])
            header_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (1, 0), (1, 0), "RIGHT"), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
            story = [header_table]
        except Exception:
            story = list(header)
    else:
        story = list(header)
    production = meta_info.get("production_meta", {}) or {}
    detail_text = " | ".join(f"<b>{label}:</b> {escape(str(value))}" for label, value in [("Nr produkcyjny", included_meta_value(production, "production_order_no", "—")), ("Stanowisko / maszyna", included_meta_value(production, "machine", "—")), ("Operator", included_meta_value(production, "operator", "—")), ("Zmiana", included_meta_value(production, "shift", "—")), ("Czas planowany", f"{included_meta_value(production, 'planned_time_hours', '—')} h")])
    story.extend([Paragraph(detail_text, meta_style), Spacer(1, 10)])
    headers = ["Poz.", "Klient", "Nazwa towaru lub usługi", "Inne kryteria", "Display", "Kolor papieru", "Kolor filtrów", "Wymiar", "Ilość netto", "Ilość box", "Ilość cover", "Ilość display", "Uwagi do zamówienia", "Wystawiony dokument Faktura"]
    table_data = [[Paragraph(header_text, th_style) for header_text in headers]]
    prepared_items = [worksheet_item_data(item) for item in (items_list or [])]
    for index, item_data in enumerate(prepared_items, start=1):
        table_data.append([Paragraph(str(index), td_style), Paragraph(str(item_data["order_values"][0]), td_style), Paragraph(item_data["product_label"], td_style), *[Paragraph(str(value), td_style) for value in item_data["order_values"][1:]]])
    table = Table(table_data, colWidths=[22, 55, 95, 55, 50, 55, 55, 50, 45, 45, 45, 45, 90, 94], repeatRows=1)
    style = [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A8A")), ("GRID", (0, 0), (-1, -1), .5, colors.HexColor("#CBD5E1")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]
    for row_index in range(1, len(table_data)):
        style.append(("BACKGROUND", (0, row_index), (-1, row_index), colors.HexColor("#F8FAFC") if row_index % 2 else colors.white))
    table.setStyle(TableStyle(style))
    story.append(table)
    if meta_info.get("include_production_realization", True):
        production_rows = [[Paragraph("REALIZACJA PRODUKCJI", th_style), "", "", "", ""], [Paragraph("Poz.", th_style), Paragraph("Plan", th_style), Paragraph("Wykonano", th_style), Paragraph("Odpady", th_style), Paragraph("Przyczyna odpadu", th_style)]]
        for index, item_data in enumerate(prepared_items, start=1):
            production_rows.append([Paragraph(str(index), td_style), *[Paragraph(str(value), td_style) for value in item_data["production_values"]]])
        production_table = Table(production_rows, colWidths=[35, 80, 80, 70, doc.width - 265], repeatRows=2)
        production_table.setStyle(TableStyle([("SPAN", (0, 0), (-1, 0)), ("BACKGROUND", (0, 0), (-1, 1), colors.HexColor("#123B69")), ("TEXTCOLOR", (0, 0), (-1, 1), colors.white), ("GRID", (0, 0), (-1, -1), .5, colors.HexColor("#CBD5E1")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]))
        story.extend([Spacer(1, 10), production_table])
    story.extend(list(bct_flowables or ()))
    if canvasmaker:
        doc.build(story, canvasmaker=canvasmaker)
    else:
        doc.build(story)
    return buffer.getvalue()


def worksheet_item_data(item):
    """Przygotowuje bezpieczne dane jednej pozycji Karty Pracy."""
    item = item or {}
    sku, selected_ean = str(item.get("sku", "")).strip(), str(item.get("ean_selected", "")).strip()
    selected_level, lot_number = str(item.get("packaging_level", "Produkt")).strip(), str(included_value(item, "lot_number", "")).strip()
    product_label = escape(str(included_value(item, "product_name", "-")))
    identifiers = " | ".join(part for part in [
        f"SKU: {escape(sku)}" if sku else "", f"EAN {escape(selected_level)}: {escape(selected_ean)}" if selected_ean else "",
    ] if part)
    if identifiers:
        product_label += f"<br/><font size=6>{identifiers}</font>"
    planning = " | ".join(part for part in [
        f"LOT: {escape(lot_number)}" if lot_number else "",
        f"Z zapasem: {included_value(item, 'qty_with_buffer', '')}" if included_value(item, "qty_buffer", "") else "",
        f"Produkcja: {included_value(item, 'qty_production', '')}" if included_value(item, "qty_production", "") else "",
        f"Wysyłka: {included_value(item, 'qty_shipping', '')}" if included_value(item, "qty_shipping", "") else "",
    ] if part)
    if planning:
        product_label += f"<br/><font size=6>{planning}</font>"
    packaging = item.get("packaging_calculation", {}) or {}
    if packaging:
        product_label += f"<br/><font size=6>Pakowanie: {packaging.get('displayow', 0)} displaye | {packaging.get('mastercase', 0)} MC | {packaging.get('palet', 0)} palet</font>"
    return {
        "product_label": product_label,
        "order_values": [included_value(item, key, default) for key, default in (
            ("order_channel", "-"), ("other_criteria", "-"), ("display_type", "-"), ("box_paper_color", "-"),
            ("filter_color", "-"), ("dimensions", "-"), ("qty_net", 0), ("qty_box", 0), ("qty_cover", 0),
            ("qty_display", 0), ("order_notes", "-"), ("invoice_status", "Brak"),
        )],
        "production_values": [
            included_value(item, "production_planned", item.get("qty_production", 0)), included_value(item, "production_made", 0),
            included_value(item, "production_waste", 0), escape(str(included_value(item, "waste_reason", "—") or "—")),
        ],
    }
