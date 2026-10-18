"""PDF-y PPWR niezależne od Streamlit i trwałego rejestru dokumentów."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Flowable, Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from services.production_documents import DeepLTranslationError, _deepl_translate_texts


PPWR_EN_TRANSLATIONS = {
    "Komponent opakowania": {
        "okładka": "Cover", "kartonik do bibułki": "Tissue paper box",
        "zestaw filtrów": "Filter tip set", "zestaw filtrow": "Filter tip set",
        "etykieta kartonu zbiorczego": "Master case label", "pusta paleta": "Empty pallet",
        "przekładka": "Layer pad", "przekładki": "Layer pads",
        "folia stretch": "Stretch film", "płyta wiórowa": "Particleboard sheet",
        "folia kapturowa spodnia": "Bottom hood film", "taśma spinająca paletę": "Pallet strapping tape",
        "etykieta paletowa": "Pallet label", "paleta drewniana": "Wooden pallet",
        "pusty display": "Empty display", "laminacja boxa": "Box lamination",
        "taśma klejąca na displayu": "Display sealing tape",
        "pusty karton zbiorczy": "Empty master case",
        "taśma do zaklejania kartonu zbiorczego": "Master case sealing tape",
        "narożniki / kaptur": "Corner protectors / hood",
    },
    "Poziom opakowania": {
        "opakowanie jednostkowe": "Primary packaging", "opakowanie zbiorcze": "Secondary packaging",
        "opakowanie ekspozycyjne (display)": "Display packaging",
        "sekcja transportowa": "Transport packaging", "sprzedażowe / primary": "Primary packaging",
        "wtórne / secondary": "Secondary packaging", "transportowe / pallet": "Transport packaging",
    },
    "Materiał główny": {
        "papier": "Paper", "plastik": "Plastic", "drewno": "Wood", "metal": "Metal",
        "szkło": "Glass", "inny": "Other",
    },
    "Surowiec": {
        "tektura gładka / lita (pap 21)": "Solid board (PAP 21)",
        "tektura falista (pap 20)": "Corrugated board (PAP 20)",
        "tektura falista": "Corrugated board", "inny papier (pap 22)": "Other paper (PAP 22)",
        "c/pap 81": "Composite paper (C/PAP 81)", "pp 05": "Polypropylene (PP 05)",
        "other 07": "Other 07", "ldpe 04": "LDPE 04", "pet 01": "PET 01",
    },
    "Kolor / druk / uwagi": {
        "brak": "None", "czarny": "Black", "biały": "White", "brązowy": "Brown",
        "transparent": "Transparent",
    },
}

PPWR_CUSTOM_TRANSLATABLE_COLUMNS = (
    "Komponent opakowania", "Poziom opakowania", "Materiał główny", "Surowiec", "Kolor / druk / uwagi",
)


def ppwr_translation_key(column, value):
    """Stabilny klucz ręcznej korekty dla własnej wartości PPWR."""
    return f"{column}\x1f{str(value).strip()}"


def _ppwr_needs_custom_translation(column, value):
    text = str(value or "").strip()
    if not text or column not in PPWR_CUSTOM_TRANSLATABLE_COLUMNS:
        return False
    return text.casefold() not in PPWR_EN_TRANSLATIONS.get(column, {})


def ppwr_translation_rows(dataframe, translation_overrides=None):
    """Zwraca tylko nazwy własne, które wymagają DeepL lub ręcznej korekty EN."""
    overrides = translation_overrides or {}
    rows, seen = [], set()
    for _, record in getattr(dataframe, "iterrows", lambda: [])():
        for column in PPWR_CUSTOM_TRANSLATABLE_COLUMNS:
            value = record.get(column, "")
            if not _ppwr_needs_custom_translation(column, value):
                continue
            key = ppwr_translation_key(column, value)
            if key not in seen:
                seen.add(key)
                rows.append({"key": key, "Pole": column, "Polski": str(value).strip(), "English version": overrides.get(key, "")})
    return rows


def ppwr_deepl_translation_overrides(dataframe, deepl_api_key, translation_overrides=None):
    """Tłumaczy wyłącznie niewypełnione własne nazwy PPWR i zwraca komplet korekt."""
    overrides = dict(translation_overrides or {})
    rows = ppwr_translation_rows(dataframe, overrides)
    texts = [row["Polski"] for row in rows if not str(overrides.get(row["key"], "")).strip()]
    translated = _deepl_translate_texts(texts, deepl_api_key) if texts else {}
    for row in rows:
        if not str(overrides.get(row["key"], "")).strip() and row["Polski"] in translated:
            overrides[row["key"]] = translated[row["Polski"]]
    return overrides

def translate_ppwr_value(value, column, translation_overrides=None):
    """Zwraca angielski odpowiednik wartości PPWR, bez zmiany danych źródłowych."""
    if value is None:
        return ""
    text = str(value)
    manual_value = str((translation_overrides or {}).get(ppwr_translation_key(column, text), "")).strip()
    return PPWR_EN_TRANSLATIONS.get(column, {}).get(text.strip().casefold(), manual_value or text)


def ppwr_table_for_language(dataframe, language, translation_overrides=None):
    """Tworzy kopię tabeli przetłumaczoną wyłącznie na potrzeby raportu."""
    if language == "pl" or not hasattr(dataframe, "copy"):
        return dataframe
    translated = dataframe.copy()
    for column in PPWR_EN_TRANSLATIONS:
        if column in translated.columns:
            translated[column] = translated[column].map(
                lambda value: translate_ppwr_value(value, column, translation_overrides)
            )
    return translated


def format_ppwr_number(value, digits=3):
    """Formatuje liczbę PPWR ze spacją jako separatorem tysięcy."""
    try:
        return f"{float(value or 0):,.{digits}f}".replace(",", " ")
    except (TypeError, ValueError):
        return "0"


def _diagram_component_type(component_name):
    """Rozpoznaje typ komponentu używany do przypisania obrazu na diagramie."""
    normalized = str(component_name or "").strip().casefold()
    normalized = (normalized.replace("ł", "l").replace("ó", "o").replace("ś", "s")
                 .replace("ć", "c").replace("ż", "z").replace("ź", "z")
                 .replace("ą", "a").replace("ę", "e").replace("ń", "n"))
    rules = (
        ("etykieta", ("etykiet", "label")), ("display", ("display",)),
        ("karton", ("karton", "box", "master case", "mastercase")),
        ("paleta", ("palet", "pallet")), ("folia_stretch", ("stretch",)),
        ("folia", ("folia", "film")), ("tasma", ("tasma", "tape")),
        ("narozniki", ("naroznik", "corner")), ("przekladka", ("przeklad", "separator")),
    )
    for component_type, tokens in rules:
        if any(token in normalized for token in tokens):
            return component_type
    return normalized or "pozostale"


class _PPWRProcessDiagram(Flowable):
    """Rysuje jeden, czytelny diagram procesu: maks. osiem etapów w wierszu."""

    blue = colors.HexColor("#1479EE")
    ink = colors.HexColor("#111827")
    muted = colors.HexColor("#64748B")

    def __init__(self, positions, diagram_images, diagram_steps, font_regular, font_bold, language, start_number=1):
        super().__init__()
        self.positions = positions[:30]
        self.start_number = start_number
        self.diagram_images = diagram_images or {}
        self.diagram_steps = diagram_steps or {}
        self.font_regular = font_regular
        self.font_bold = font_bold
        self.language = language
        self.width = 742
        self.height = 405 if len(self.positions) > 20 else 420 if len(self.positions) > 10 else 210

    def wrap(self, available_width, available_height):
        self.width = min(self.width, available_width)
        return self.width, self.height

    def _image_payload(self, position, index):
        step = self.diagram_steps.get(str(index), self.diagram_steps.get(index, {}))
        if isinstance(step, dict) and step.get("bytes"):
            return step.get("bytes")
        name = str(position.get("Komponent opakowania") or "")
        component_type = _diagram_component_type(name)
        legacy = self.diagram_images.get(component_type)
        return legacy.get("bytes") if isinstance(legacy, dict) else legacy

    def _draw_arrow(self, canvas, x1, y1, x2, y2):
        canvas.setStrokeColor(self.blue)
        canvas.setFillColor(self.blue)
        canvas.setLineWidth(1.7)
        canvas.line(x1, y1, x2, y2)
        if abs(y2 - y1) < 1:
            angle = 0 if x2 >= x1 else 180
        else:
            angle = 90 if y2 > y1 else -90
        canvas.saveState(); canvas.translate(x2, y2); canvas.rotate(angle)
        canvas.line(-6, 4, 0, 0); canvas.line(-6, -4, 0, 0)
        canvas.restoreState()

    def _draw_step(self, canvas, position, number, x, y, stage_width):
        name = str(position.get("Komponent opakowania") or "-").strip()
        image_size = min(46 if len(self.positions) > 20 else 58, stage_width - 12)
        image_x = x + (stage_width - image_size) / 2
        image_y = y + 16
        marker_x = x + stage_width / 2
        marker_y = y + (102 if len(self.positions) > 20 else 142)
        if number is not None:
            canvas.setFont(self.font_bold, 14)
            canvas.setFillColor(colors.black)
            canvas.drawCentredString(marker_x, marker_y + 18, str(number))
            canvas.setStrokeColor(self.blue); canvas.setFillColor(self.blue); canvas.setLineWidth(1.25)
            canvas.line(marker_x + 2, marker_y + 13, marker_x - 5, image_y + image_size + 8)
            canvas.circle(marker_x - 5, image_y + image_size + 8, 2.4, stroke=0, fill=1)
        image_bytes = self._image_payload(position, position.get("_diagram_position", number or 0))
        if image_bytes:
            try:
                stream = BytesIO(image_bytes)
                image_width, image_height = ImageReader(stream).getSize()
                scale = min(image_size / image_width, image_size / image_height)
                draw_width, draw_height = image_width * scale, image_height * scale
                canvas.drawImage(ImageReader(BytesIO(image_bytes)), image_x + (image_size - draw_width) / 2, image_y + (image_size - draw_height) / 2, draw_width, draw_height, mask="auto")
                return
            except Exception:
                pass
        canvas.setStrokeColor(colors.HexColor("#94A3B8")); canvas.setDash(2, 2)
        canvas.roundRect(image_x, image_y, image_size, image_size, 4, stroke=1, fill=0); canvas.setDash()
        canvas.setFont(self.font_regular, 5.8); canvas.setFillColor(self.muted)
        short_name = name if len(name) <= 20 else f"{name[:18]}..."
        canvas.drawCentredString(marker_x, image_y + image_size / 2, short_name)

    def draw(self):
        canvas = self.canv
        steps_per_row = 10
        rows = [
            self.positions[:steps_per_row],
            self.positions[steps_per_row:steps_per_row * 2],
            self.positions[steps_per_row * 2:steps_per_row * 3],
        ]
        stage_width = self.width / steps_per_row
        row_y = [self.height - 145, 140, 12] if len(self.positions) > 20 else [self.height - 200, 16, 0]
        for row_index, row in enumerate(rows):
            if not row:
                continue
            y = row_y[row_index]
            for offset, position in enumerate(row):
                x = offset * stage_width
                number = position.get("_ppwr_number")
                self._draw_step(canvas, position, number, x, y, stage_width)
                if offset < len(row) - 1:
                    self._draw_arrow(canvas, x + stage_width - 7, y + 40, x + stage_width + 7, y + 40)
        for row_index in range(len(rows) - 1):
            if not rows[row_index + 1]:
                continue
            right = self.width - 6
            current_y = row_y[row_index] + 40
            next_y = row_y[row_index + 1] + 40
            # Płynny, "wężowy" łącznik między wierszami; poziomy odcinek jest
            # umieszczony niżej od numerów kolejnego rzędu.
            bridge_y = row_y[row_index + 1] + (84 if len(self.positions) > 20 else 118)
            canvas.setStrokeColor(self.blue); canvas.setFillColor(self.blue); canvas.setLineWidth(1.8)
            canvas.setLineCap(1)
            path = canvas.beginPath()
            path.moveTo(right, current_y)
            path.curveTo(right, current_y - 14, right, bridge_y + 14, right - 12, bridge_y)
            path.lineTo(20, bridge_y)
            path.curveTo(8, bridge_y, 8, bridge_y - 12, 8, next_y + 9)
            canvas.drawPath(path, stroke=1, fill=0)
            self._draw_arrow(canvas, 8, next_y + 9, 8, next_y)


def _ppwr_packing_diagram_story(metadata, components, *, language, body, section, font_regular, font_bold):
    """Buduje stronę diagramu procesu ze zdjęciami, wzorowaną na ustalonym układzie PPWR."""
    positions = list(metadata.get("diagram_positions", []) or getattr(components, "to_dict", lambda **_: [])(orient="records"))
    if not positions:
        return []
    pl = language == "pl"
    title = "5. Diagram procesu pakowania" if pl else "5. Packaging process diagram"
    note = (
        "Pozycje wyłączone z PPWR są pokazane w przebiegu bez numeru; numerowane są wyłącznie komponenty PPWR."
        if pl else "Goods excluded from PPWR remain visible in the flow without a number; only PPWR components are numbered."
    )
    numbered_positions = []
    ppwr_number = 0
    for diagram_position, raw_position in enumerate(positions, start=1):
        position = dict(raw_position or {})
        included = position.get("Uwzględniać jako opakowanie PPWR", True)
        if isinstance(included, str):
            included = included.strip().lower() not in {"false", "0", "nie", "no", "off"}
        if included is not False:
            ppwr_number += 1
            position["_ppwr_number"] = ppwr_number
        else:
            position["_ppwr_number"] = None
        position["_diagram_position"] = diagram_position
        numbered_positions.append(position)
    positions = numbered_positions
    story = []
    # Pierwsza strona zawiera pełny przebieg 10 + 10 + 10. Każda następna mieści kolejne 10 etapów.
    start = 0
    first_page = True
    while start < len(positions):
        limit = 30 if first_page else 10
        if first_page:
            page_title = title
        else:
            page_title = f"{title} - {'ciąg dalszy' if pl else 'continued'}"
        shown_positions = positions[start:start + limit]
        diagram = _PPWRProcessDiagram(
            shown_positions, metadata.get("diagram_images", {}), metadata.get("diagram_steps", {}),
            font_regular, font_bold, language, start_number=start + 1,
        )
        story.extend([PageBreak(), Paragraph(page_title, section), Paragraph(note, body), Spacer(1, 6), diagram])
        start += limit
        first_page = False
    return story


def build_ppwr_mass_specification_pdf(metadata, components, material_summary, *, language="en", font_regular="Helvetica", font_bold="Helvetica-Bold", bct_flowables=(), canvasmaker=None):
    """Buduje raport PPWR z tabelą komponentów i podziałem według materiału."""
    metadata = metadata or {}
    requirement_keys = set(metadata.get("report_requirement_keys", []) or [])
    pl = language == "pl"
    translation_overrides = metadata.get("ppwr_translation_overrides", {}) or {}
    components = ppwr_table_for_language(components, language, translation_overrides)
    material_summary = ppwr_table_for_language(material_summary, language, translation_overrides)
    if language != "pl" and metadata.get("diagram_positions"):
        translated_diagram_positions = []
        for raw_position in metadata.get("diagram_positions", []):
            position = dict(raw_position or {})
            for column in PPWR_CUSTOM_TRANSLATABLE_COLUMNS:
                if column in position:
                    position[column] = translate_ppwr_value(position[column], column, translation_overrides)
            translated_diagram_positions.append(position)
        metadata = {**metadata, "diagram_positions": translated_diagram_positions}
    labels = {
        "title": "SPECYFIKACJA MASY I MATERIAŁÓW OPAKOWAŃ" if pl else "PACKAGING MASS AND MATERIAL SPECIFICATION",
        "subtitle": "PPWR B2B — zestawienie techniczne z rejestru komponentów" if pl else "PPWR B2B — technical statement from the component register",
        "components": "1. Rejestr komponentów opakowania" if pl else "1. Packaging component register",
        "materials": "2. Podział masy według materiałów" if pl else "2. Material mass split",
        "excluded": "Towary i przesyłki wyłączone z obliczeń PPWR" if pl else "Goods and shipments excluded from PPWR calculations",
        "basis": "3. Podstawa obliczeń i dokumentacja techniczna" if pl else "3. Calculation basis and technical-file note",
        "product": "Produkt / pozycja" if pl else "Product / item", "client": "Klient / marka" if pl else "Client / brand",
        "date": "Data wystawienia" if pl else "Issue date", "vat": "NIP / VAT ID wystawcy" if pl else "Issuer VAT ID / NIP",
        "order_units": "Liczba SKU w zamówieniu" if pl else "SKU units in order",
        "order_pallets": "Liczba palet w zamówieniu" if pl else "Pallets in order",
        "calculated_at": "Kalkulacja" if pl else "Calculation time",
        "sku_mass": "MASA / 1 SKU" if pl else "MASS PER 1 SKU", "pallet_mass": "MASA / PALETĘ" if pl else "MASS PER PALLET", "order_mass": "MASA / ZAMÓWIENIE" if pl else "MASS FOR THE ORDER",
        "appendix": "4. Schemat komponentów opakowania" if pl else "4. Packaging component diagram",
        "appendix_note": "Ilustracja pomocnicza do numerów pozycji z tabeli komponentów." if pl else "Reference illustration for the numbered component rows in the table.",
    }
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=25, rightMargin=25, topMargin=48, bottomMargin=42)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("PPWRTitle", parent=styles["Heading1"], fontName=font_bold, fontSize=18, leading=22, textColor=colors.HexColor("#123B66"), spaceAfter=4)
    subtitle = ParagraphStyle("PPWRSubtitle", parent=styles["Normal"], fontName=font_regular, fontSize=8.5, leading=11, textColor=colors.HexColor("#475569"), spaceAfter=12)
    body = ParagraphStyle("PPWRBody", parent=styles["Normal"], fontName=font_regular, fontSize=7, leading=8.5, textColor=colors.HexColor("#0F172A"))
    header = ParagraphStyle("PPWRHeader", parent=body, fontName=font_bold, fontSize=6.8, leading=8, textColor=colors.white, alignment=1)
    section = ParagraphStyle("PPWRSection", parent=styles["Heading2"], fontName=font_bold, fontSize=10.5, leading=13, textColor=colors.HexColor("#123B66"), spaceBefore=11, spaceAfter=6)

    def number(value, digits=3):
        return format_ppwr_number(value, digits)

    def cell(value, style=body):
        return Paragraph(escape(str(value if value not in (None, "") else "-")), style)

    story = [Paragraph(labels["title"], title), Paragraph(labels["subtitle"], subtitle)]
    info_rows = [
        [cell(labels["product"]), cell(metadata.get("product_name", "-")), cell("SKU / EAN"), cell(metadata.get("sku", "-"))],
        [cell(labels["client"]), cell(metadata.get("client", "-")), cell(labels["date"]), cell(datetime.now().strftime("%d.%m.%Y"))],
        [cell(labels["vat"]), cell(metadata.get("nip", "-")), cell("Wersja dokumentu" if pl else "Document version"), cell("1.0")],
        [cell(labels["order_units"]), cell(format_ppwr_number(metadata.get("units_per_order", 0), 0)), cell("SKU / paletę" if pl else "SKU / pallet"), cell(format_ppwr_number(metadata.get("units_per_pallet", 0), 0))],
        [cell(labels["order_pallets"]), cell(format_ppwr_number(metadata.get("pallets_per_order", 0), 0)), cell(labels["calculated_at"]), cell(datetime.now().strftime("%d.%m.%Y %H:%M:%S"))],
    ]
    info = Table(info_rows, colWidths=[115, 280, 115, 272])
    info.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E8F0F8")), ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#E8F0F8")), ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#CBD5E1")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("PADDING", (0, 0), (-1, -1), 5)]))
    totals = Table([
        [cell(labels["sku_mass"], header), cell(labels["pallet_mass"], header), cell(labels["order_mass"], header)],
        [cell(f"{number(metadata.get('total_sku_g'))} g"), cell(f"{number(metadata.get('total_pallet_kg'))} kg"), cell(f"{number(metadata.get('total_order_kg'))} kg")],
    ], colWidths=[260, 260, 262])
    totals.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#123B66")), ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#F1F5F9")), ("GRID", (0, 0), (-1, -1), .4, colors.HexColor("#94A3B8")), ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("PADDING", (0, 0), (-1, -1), 7)]))
    story.extend([info, Spacer(1, 10), totals, Paragraph(labels["components"], section)])
    component_headers = ["Lp." if pl else "No.", "Komponent opakowania" if pl else "Packaging component", "Poziom" if pl else "Level", "Materiał" if pl else "Material", "Surowiec" if pl else "Raw material", "Masa jedn. (g)" if pl else "Unit mass (g)", "Ilość / SKU" if pl else "Qty / SKU", "Ilość / paletę" if pl else "Qty / pallet", "Masa / zamówienie (kg)" if pl else "Mass / order (kg)", "Uwagi" if pl else "Notes"]
    component_rows = [[cell(value, header) for value in component_headers]]
    for index, (_, row) in enumerate(getattr(components, "iterrows", lambda: [])(), start=1):
        component_rows.append([cell(index), cell(row.get("Komponent opakowania", "")), cell(row.get("Poziom opakowania", "")), cell(row.get("Materiał główny", "")), cell(row.get("Surowiec", "")), cell(number(row.get("Masa jednostkowa (g)", 0))), cell(number(row.get("Ilość / 1 SKU", 0), 2)), cell(number(row.get("Ilość / 1 paletę", 0), 2)), cell(number(row.get("Masa / zamówienie (kg)", 0))), cell(row.get("Kolor / druk / uwagi", ""))])
    component_table = Table(component_rows, colWidths=[22, 110, 65, 70, 70, 57, 52, 57, 75, 170], repeatRows=1)
    component_style = [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#123B66")), ("GRID", (0, 0), (-1, -1), .25, colors.HexColor("#CBD5E1")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("PADDING", (0, 0), (-1, -1), 3)]
    for index in range(1, len(component_rows)):
        if index % 2 == 0:
            component_style.append(("BACKGROUND", (0, index), (-1, index), colors.HexColor("#F8FAFC")))
    component_table.setStyle(TableStyle(component_style))
    story.extend([component_table, Paragraph(labels["materials"], section)])
    material_headers = ["Materiał" if pl else "Material", "Masa / SKU (g)" if pl else "Mass / SKU (g)", "Udział / SKU (%)" if pl else "Share / SKU (%)", "Masa / paletę (kg)" if pl else "Mass / pallet (kg)", "Masa / zamówienie (kg)" if pl else "Mass / order (kg)"]
    material_rows = [[cell(value, header) for value in material_headers]]
    for _, row in getattr(material_summary, "iterrows", lambda: [])():
        material_rows.append([cell(row.get("Materiał główny", "")), cell(number(row.get("Masa / 1 SKU (g)", 0))), cell(number(row.get("Udział / 1 SKU (%)", 0), 1)), cell(number(row.get("Masa / 1 paletę (kg)", 0))), cell(number(row.get("Masa / zamówienie (kg)", 0)))])
    material_table = Table(material_rows, colWidths=[190, 130, 130, 150, 170], repeatRows=1)
    material_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#123B66")), ("GRID", (0, 0), (-1, -1), .3, colors.HexColor("#CBD5E1")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("PADDING", (0, 0), (-1, -1), 5)]))
    note = "Masa dla SKU, palety i zamówienia wynika z masy jednostkowej oraz ilości komponentów. Raport należy przechowywać z dokumentacją dostawców." if pl else "Mass per SKU, pallet and order is calculated from component unit mass and quantities. Retain this report with supplier documentation."
    story.extend([material_table, Paragraph(labels["basis"], section), Paragraph(note, body)])
    if "excluded_goods" in requirement_keys:
        excluded_components = list(metadata.get("excluded_components", []) or [])
        excluded_headers = [
            "Lp." if pl else "No.",
            "Towar / przesyłka" if pl else "Goods / shipment",
            "Poziom" if pl else "Level",
            "Materiał" if pl else "Material",
            "Powód wyłączenia" if pl else "Reason for exclusion",
            "Masa jednostkowa (g)" if pl else "Unit mass (g)",
            "Ilość / SKU" if pl else "Qty / SKU",
            "Ilość / paletę" if pl else "Qty / pallet",
        ]
        excluded_rows = [[cell(value, header) for value in excluded_headers]]
        if excluded_components:
            for index, row in enumerate(excluded_components, start=1):
                component_name = row.get("Komponent opakowania", "")
                packaging_level = row.get("Poziom opakowania", "")
                material_name = row.get("Materiał główny", "")
                if not pl:
                    component_name = translate_ppwr_value(component_name, "Komponent opakowania", translation_overrides)
                    packaging_level = translate_ppwr_value(packaging_level, "Poziom opakowania", translation_overrides)
                    material_name = translate_ppwr_value(material_name, "Materiał główny", translation_overrides)
                excluded_rows.append([
                    cell(index), cell(component_name), cell(packaging_level), cell(material_name),
                    cell("Nie jest opakowaniem PPWR" if pl else "Not PPWR packaging"),
                    cell(number(row.get("Masa jednostkowa (g)", 0))),
                    cell(number(row.get("Ilość / 1 SKU", 0), 2)),
                    cell(number(row.get("Ilość / 1 paletę", 0), 2)),
                ])
        else:
            excluded_rows.append([
                cell("-"),
                cell("Brak pozycji wyłączonych z obliczeń PPWR." if pl else "No items are excluded from PPWR calculations."),
                cell(""), cell(""), cell(""), cell(""), cell(""), cell(""),
            ])
        excluded_table = Table(excluded_rows, colWidths=[32, 170, 100, 75, 120, 90, 80, 95], repeatRows=1)
        excluded_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7C2D12")),
            ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#FFF7ED")),
            ("GRID", (0, 0), (-1, -1), .3, colors.HexColor("#CBD5E1")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("PADDING", (0, 0), (-1, -1), 5),
        ]))
        story.extend([Paragraph(labels["excluded"], section), excluded_table])
    if "bct" in requirement_keys:
        story.extend(list(bct_flowables or ()))
    appendix_image = metadata.get("appendix_image")
    if isinstance(appendix_image, (bytes, bytearray)) and appendix_image:
        try:
            image_buffer = BytesIO(appendix_image)
            image_width, image_height = ImageReader(image_buffer).getSize()
            scale = min(760 / image_width, 440 / image_height, 1)
            story.extend([
                PageBreak(), Paragraph(labels["appendix"], section), Paragraph(labels["appendix_note"], body), Spacer(1, 10),
                Image(image_buffer, width=image_width * scale, height=image_height * scale),
            ])
        except Exception:
            # Nie blokujemy raportu, jeśli przekazany plik nie jest poprawnym obrazem.
            pass
    if "diagram" in requirement_keys:
        story.extend(_ppwr_packing_diagram_story(
            metadata, components, language=language, body=body, section=section,
            font_regular=font_regular, font_bold=font_bold,
        ))
    if canvasmaker:
        doc.build(story, canvasmaker=canvasmaker)
    else:
        doc.build(story)
    return buffer.getvalue()
