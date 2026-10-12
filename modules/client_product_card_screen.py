"""Moduł 23: klientowska karta produktu budowana z TDS i zlecenia."""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _text(value) -> str:
    return str(value or "").strip()


def _source_values(record: dict, item: dict) -> dict:
    header = record.get("order_header", {}) or {}
    pdf_data = item.get("pdf_data", {}) or {}
    basics = pdf_data.get("Sekcja I: Parametry Podstawowe & Materiały", {}) or {}
    catalog = item.get("catalog_snapshot", {}) or {}
    product_level = catalog.get("Produkt", {}) if isinstance(catalog, dict) else {}
    packaging = item.get("packaging_calculation", {}) or {}
    return {
        "name": _text(item.get("name")),
        "sku": _text(item.get("sku")),
        "ean": _text(item.get("ean_product")),
        "client": _text(header.get("recipient", {}).get("company") if isinstance(header.get("recipient"), dict) else header.get("client")),
        "product_type": _text(basics.get("Produkt") or product_level.get("Typ") or product_level.get("Rodzaj")),
        "dimensions": _text(basics.get("Wymiary") or product_level.get("Wymiary")),
        "material": _text(basics.get("Kolor papieru w boxie") or basics.get("Inne kryteria")),
        "packaging": _text(item.get("packaging_level")),
        "quantity": _text(basics.get("Ilość do wysyłki") or packaging.get("qty_shipping")),
        "print_info": _text(basics.get("Druk")),
        "description": "",
        "customer_notes": "",
    }


def build_client_product_card_pdf(values: dict, *, font_regular: str, font_bold: str) -> bytes:
    """Tworzy zwięzłą kartę dla klienta, bez danych wewnętrznych produkcji."""
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=17 * mm, bottomMargin=17 * mm)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("ClientCardTitle", parent=styles["Title"], fontName=font_bold, fontSize=22, leading=27, alignment=TA_CENTER, textColor=colors.HexColor("#173B69"), spaceAfter=5 * mm)
    subtitle = ParagraphStyle("ClientCardSubtitle", parent=styles["Normal"], fontName=font_regular, fontSize=10, leading=14, alignment=TA_CENTER, textColor=colors.HexColor("#52616B"), spaceAfter=7 * mm)
    heading = ParagraphStyle("ClientCardHeading", parent=styles["Heading2"], fontName=font_bold, fontSize=13, leading=17, textColor=colors.HexColor("#173B69"), spaceBefore=5 * mm, spaceAfter=3 * mm)
    body = ParagraphStyle("ClientCardBody", parent=styles["Normal"], fontName=font_regular, fontSize=10, leading=14)
    story = [
        Paragraph("KARTA PRODUKTU", title),
        Paragraph(values.get("client") or "Informacja produktowa", subtitle),
        Paragraph(values.get("name") or "Produkt", heading),
    ]
    rows = []
    fields = [("SKU", "sku"), ("EAN", "ean"), ("Typ produktu", "product_type"), ("Wymiary", "dimensions"), ("Materiał / wariant", "material"), ("Pakowanie", "packaging"), ("Informacja ilościowa", "quantity"), ("Druk / wykończenie", "print_info")]
    for label, key in fields:
        value = _text(values.get(key)) or "—"
        rows.append([Paragraph(f"<b>{escape(label)}</b>", body), Paragraph(escape(value), body)])
    table = Table(rows, colWidths=[53 * mm, 111 * mm], repeatRows=0)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EEF3F8")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#C9D2DB")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(table)
    if _text(values.get("description")):
        story.extend([Paragraph("Opis produktu", heading), Paragraph(escape(_text(values["description"])).replace("\n", "<br/>"), body)])
    if _text(values.get("customer_notes")):
        story.extend([Paragraph("Dodatkowe informacje", heading), Paragraph(escape(_text(values["customer_notes"])).replace("\n", "<br/>"), body)])
    story.extend([Spacer(1, 12 * mm), Paragraph(f"Wygenerowano: {datetime.now():%Y-%m-%d %H:%M}", subtitle)])
    document.build(story)
    return buffer.getvalue()


def render_client_product_card_screen(st, deps: dict) -> None:
    pd = deps["pd"]
    get_current_order_id = deps["get_current_order_id"]
    load_document_registry = deps["load_document_registry"]
    load_database = deps["load_database"]
    save_database = deps["save_database"]
    update_order_snapshot = deps["update_order_snapshot"]
    save_order_context = deps["save_order_context"]
    font_regular = deps["font_regular"]
    font_bold = deps["font_bold"]

    st.title("🪪 Karta produktu dla klienta")
    st.caption("Karta pobiera dane z TDS i zlecenia, ale edycja tutaj nie zmienia dokumentu produkcyjnego.")
    order_id = get_current_order_id()
    record = load_document_registry().get(order_id, {})
    snapshot = record.get("shared_snapshot", {}) or {}
    tds_section = (snapshot.get("sections", {}) or {}).get("tds", {}) or {}
    items = (tds_section.get("data", {}) or {}).get("items", []) or []
    if not items:
        st.warning("Brak zapisanej pozycji TDS dla aktywnego zlecenia. Otwórz moduł 9, zapisz kartę produktu w TDS, a następnie wróć tutaj.")
        return

    labels = [f"{item.get('name', 'Pozycja bez nazwy')} · {item.get('sku', 'bez SKU')} · {item.get('packaging_level', '')}" for item in items]
    selected_index = st.selectbox("Pozycja źródłowa z TDS", range(len(items)), format_func=lambda index: labels[index], key=f"client_card_source_{order_id}")
    item = items[int(selected_index)]
    source = _source_values(record, item)
    card_id = f"{order_id}|{item.get('sku') or item.get('name')}|{item.get('packaging_level')}"
    database = load_database()
    cards = database.setdefault("client_product_cards", [])
    saved_card = next((card for card in cards if card.get("card_id") == card_id), {})
    values = {**source, **(saved_card.get("fields", {}) or {})}

    with st.expander("📥 Dane pobrane ze źródła", expanded=False):
        st.write({"Zlecenie": order_id, "Produkt": source["name"], "SKU": source["sku"], "EAN": source["ean"], "Poziom opakowania": source["packaging"]})
        st.caption("Brakujące pola można uzupełnić ręcznie poniżej; ich wartość zostanie przypisana tylko do tej karty klientowskiej.")

    st.markdown("### Edycja karty klientowskiej")
    with st.form(f"client_product_card_form_{order_id}_{selected_index}"):
        col1, col2, col3 = st.columns(3)
        with col1:
            name = st.text_input("Nazwa produktu", value=values["name"])
            sku = st.text_input("SKU", value=values["sku"])
            ean = st.text_input("EAN", value=values["ean"])
        with col2:
            client = st.text_input("Klient / marka", value=values["client"])
            product_type = st.text_input("Typ produktu", value=values["product_type"])
            dimensions = st.text_input("Wymiary", value=values["dimensions"])
        with col3:
            material = st.text_input("Materiał / wariant", value=values["material"])
            packaging = st.text_input("Pakowanie", value=values["packaging"])
            quantity = st.text_input("Informacja ilościowa", value=values["quantity"])
        print_info = st.text_input("Druk / wykończenie", value=values["print_info"])
        description = st.text_area("Opis dla klienta", value=values["description"], placeholder="Krótki opis handlowo-techniczny, bez informacji wewnętrznych.")
        customer_notes = st.text_area("Dodatkowe informacje dla klienta", value=values["customer_notes"])
        submitted = st.form_submit_button("💾 Zapisz kartę produktu", type="primary")

    if submitted:
        fields = {"name": name.strip(), "sku": sku.strip(), "ean": ean.strip(), "client": client.strip(), "product_type": product_type.strip(), "dimensions": dimensions.strip(), "material": material.strip(), "packaging": packaging.strip(), "quantity": quantity.strip(), "print_info": print_info.strip(), "description": description.strip(), "customer_notes": customer_notes.strip()}
        card = {"card_id": card_id, "order_id": order_id, "source_item": {"name": item.get("name", ""), "sku": item.get("sku", ""), "packaging_level": item.get("packaging_level", "")}, "fields": fields, "updated_at": datetime.now().isoformat(timespec="seconds")}
        cards = [existing for existing in cards if existing.get("card_id") != card_id]
        cards.insert(0, card)
        database["client_product_cards"] = cards
        save_database(database)
        update_order_snapshot("client_product_card", card, order_id)
        save_order_context(order_id)
        st.success("Kartę klientowską zapisano. Dane źródłowe TDS pozostały bez zmian.")
        values = fields

    st.markdown("### 👁️ Podgląd klientowski")
    with st.container(border=True):
        st.subheader(values["name"] or "Produkt")
        st.caption("Karta produktu — informacje dla klienta")
        preview_rows = [
            ("SKU", values["sku"]), ("EAN", values["ean"]), ("Typ produktu", values["product_type"]),
            ("Wymiary", values["dimensions"]), ("Materiał / wariant", values["material"]),
            ("Pakowanie", values["packaging"]), ("Informacja ilościowa", values["quantity"]), ("Druk / wykończenie", values["print_info"]),
        ]
        st.dataframe(pd.DataFrame([{"Parametr": label, "Wartość": value or "—"} for label, value in preview_rows]), hide_index=True, use_container_width=True)
        if values["description"]:
            st.write(values["description"])
        if values["customer_notes"]:
            st.info(values["customer_notes"])
    pdf = build_client_product_card_pdf(values, font_regular=font_regular, font_bold=font_bold)
    safe_name = "_".join(part for part in (values["name"] or "karta_produktu").split() if part)[:60]
    st.download_button("📄 Pobierz kartę produktu PDF", pdf, file_name=f"karta_produktu_{safe_name}.pdf", mime="application/pdf", type="primary")
