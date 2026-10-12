"""Narzędzia do generowania kodów, etykiet i numerów partii."""
from __future__ import annotations

from datetime import datetime
from io import BytesIO

from reportlab.graphics import renderPDF, renderSVG
from reportlab.graphics.barcode import createBarcodeDrawing
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def _ean13_value(value: str) -> str:
    digits = "".join(character for character in value if character.isdigit())
    if len(digits) == 12:
        return digits
    if len(digits) == 13:
        weights = (1, 3) * 6
        check = (10 - sum(int(item) * weight for item, weight in zip(digits[:12], weights)) % 10) % 10
        if check != int(digits[-1]):
            raise ValueError("Podany EAN-13 ma nieprawidłową cyfrę kontrolną.")
        return digits[:12]
    raise ValueError("EAN wymaga 12 cyfr (cyfra kontrolna zostanie dodana) lub prawidłowych 13 cyfr.")


def _drawing(code_type: str, value: str) -> Drawing:
    if code_type == "EAN-13":
        return createBarcodeDrawing("EAN13", value=_ean13_value(value), barHeight=52, humanReadable=True)
    if code_type == "Code 128":
        return createBarcodeDrawing("Code128", value=value, barHeight=52, barWidth=1.05, humanReadable=True)
    widget = QrCodeWidget(value)
    x1, y1, x2, y2 = widget.getBounds()
    size = 58
    drawing = Drawing(size, size, transform=[size / (x2 - x1), 0, 0, size / (y2 - y1), 0, 0])
    drawing.add(widget)
    return drawing


def _code_svg(code_type: str, value: str) -> str:
    return renderSVG.drawToString(_drawing(code_type, value))


def _label_pdf(code_type: str, value: str, title: str, description: str) -> bytes:
    buffer = BytesIO()
    width, height = 100 * mm, 65 * mm
    pdf = canvas.Canvas(buffer, pagesize=(width, height))
    pdf.setStrokeColorRGB(0.2, 0.2, 0.25)
    pdf.roundRect(3 * mm, 3 * mm, width - 6 * mm, height - 6 * mm, 2 * mm)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(8 * mm, height - 12 * mm, (title or "ETYKIETA")[:48])
    pdf.setFont("Helvetica", 8)
    pdf.drawString(8 * mm, height - 18 * mm, (description or "")[:72])
    drawing = _drawing(code_type, value)
    scale = min((width - 16 * mm) / drawing.width, 32 * mm / drawing.height)
    pdf.saveState()
    pdf.translate(8 * mm, 11 * mm)
    pdf.scale(scale, scale)
    renderPDF.draw(drawing, pdf, 0, 0)
    pdf.restoreState()
    pdf.setFont("Helvetica", 7)
    pdf.drawRightString(width - 8 * mm, 7 * mm, f"{code_type}: {value}")
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def render_generators_screen(st, deps: dict) -> None:
    st.title("🧰 Generatory")
    code_tab, label_tab, batch_tab = st.tabs(["▥ Kody", "🏷️ Etykiety", "# Numery partii"])

    with code_tab:
        st.subheader("Generator kodów")
        code_type = st.selectbox("Rodzaj kodu", ["Code 128", "EAN-13", "QR"], key="generator_code_type")
        placeholder = "np. SKU lub numer zlecenia" if code_type == "Code 128" else ("12 lub 13 cyfr" if code_type == "EAN-13" else "tekst, link lub numer zlecenia")
        value = st.text_input("Zawartość kodu", placeholder=placeholder, key="generator_code_value")
        if value.strip():
            try:
                svg = _code_svg(code_type, value.strip())
                st.components.v1.html(svg, height=145, scrolling=False)
                st.download_button("⬇️ Pobierz kod SVG", svg.encode("utf-8"), file_name=f"kod_{code_type}_{value.strip()}.svg", mime="image/svg+xml")
            except Exception as error:
                st.error(f"Nie można wygenerować kodu: {error}")
        else:
            st.caption("Dostępne typy: Code 128, EAN-13 i QR.")

    with label_tab:
        st.subheader("Generator etykiety PDF")
        left, right = st.columns(2)
        with left:
            label_type = st.selectbox("Rodzaj kodu na etykiecie", ["Code 128", "EAN-13", "QR"], key="label_code_type")
            label_value = st.text_input("Zawartość kodu", key="label_code_value")
        with right:
            label_title = st.text_input("Tytuł etykiety", value="ETYKIETA PRODUKTU", key="label_title")
            label_description = st.text_input("Opis", placeholder="np. nazwa produktu / klient", key="label_description")
        if label_value.strip():
            try:
                label = _label_pdf(label_type, label_value.strip(), label_title, label_description)
                st.download_button("⬇️ Pobierz etykietę PDF", label, file_name="etykieta.pdf", mime="application/pdf", type="primary")
            except Exception as error:
                st.error(f"Nie można wygenerować etykiety: {error}")
        else:
            st.caption("Wpisz zawartość kodu, aby przygotować etykietę do pobrania.")

    with batch_tab:
        st.subheader("Rejestr partii")
        st.caption("Wpisujesz pełną zawartość partii: produkt, zlecenie, ilość oraz materiały użyte do jej wykonania.")
        left, middle, right = st.columns(3)
        with left:
            prefix = st.text_input("Prefiks propozycji", value="PARTIA", key="batch_prefix")
        with middle:
            sequence = st.number_input("Numer kolejny propozycji", min_value=1, value=1, step=1, key="batch_sequence")
        with right:
            include_date = st.checkbox("Data w propozycji", value=True, key="batch_include_date")
        date_part = datetime.now().strftime("%Y%m%d") if include_date else ""
        proposed_number = "-".join(part for part in [prefix.strip().upper(), date_part, f"{int(sequence):04d}"] if part)
        proposal_col, use_col = st.columns([4, 1])
        with proposal_col:
            st.code(f"Propozycja: {proposed_number}")
        with use_col:
            if st.button("Użyj propozycji", key="use_batch_proposal"):
                st.session_state["batch_number"] = proposed_number
                st.rerun()

        details_left, details_right = st.columns(2)
        with details_left:
            batch_number = st.text_input("Numer partii", key="batch_number", placeholder="Wpisz własny numer lub użyj propozycji")
            product = st.text_input("Produkt / artykuł", key="batch_product")
            order_number = st.text_input("Zlecenie / projekt", key="batch_order_number")
        with details_right:
            production_date = st.date_input("Data produkcji", value=datetime.now().date(), key="batch_production_date")
            customer = st.text_input("Klient", key="batch_customer")
            status = st.selectbox("Status partii", ["W toku", "Zakończona", "Zablokowana", "Zużyta"], key="batch_status")
        quantity_col, unit_col = st.columns([2, 1])
        with quantity_col:
            quantity = st.number_input("Ilość wyprodukowana", min_value=0.0, step=1.0, key="batch_quantity")
        with unit_col:
            unit = st.selectbox("Jednostka", ["szt.", "kg", "m", "rolki", "kartony", "palety"], key="batch_unit")
        notes = st.text_area("Uwagi do partii", key="batch_notes", placeholder="np. wynik kontroli jakości, odchylenia, informacja o magazynowaniu")

        st.markdown("#### Skład partii")
        st.caption("Dodaj każdy materiał, półprodukt lub wcześniejszą partię wykorzystaną do produkcji.")
        component_seed = st.session_state.setdefault("batch_components_seed", [
            {"Materiał / komponent": "", "Nr partii materiału": "", "Ilość": 0.0, "Jednostka": "kg", "Uwagi": ""}
        ])
        component_table = st.data_editor(
            component_seed,
            num_rows="dynamic",
            hide_index=True,
            use_container_width=True,
            key="batch_components_editor",
            column_config={
                "Materiał / komponent": st.column_config.TextColumn(required=True),
                "Nr partii materiału": st.column_config.TextColumn(),
                "Ilość": st.column_config.NumberColumn(min_value=0.0, step=0.001, format="%.3f"),
                "Jednostka": st.column_config.SelectboxColumn(options=["kg", "m", "szt.", "rolki", "kartony"]),
                "Uwagi": st.column_config.TextColumn(),
            },
        )
        if hasattr(component_table, "to_dict"):
            components = component_table.to_dict("records")
        else:
            components = list(component_table)
        components = [item for item in components if str(item.get("Materiał / komponent", "")).strip()]

        if st.button("➕ Zapisz pełną partię", type="primary", key="save_generated_batch"):
            if not batch_number.strip():
                st.error("Podaj numer partii.")
            elif not product.strip():
                st.error("Podaj produkt lub artykuł.")
            else:
                database = deps["load_database"]()
                records = database.get("batch_registry", [])
                if any(record.get("batch_number") == batch_number.strip() for record in records):
                    st.error("Partia o takim numerze już istnieje. Zmień numer albo edytuj istniejący wpis w kolejnym etapie.")
                    return
                records.insert(0, {
                    "batch_number": batch_number.strip(), "product": product.strip(), "order_number": order_number.strip(),
                    "production_date": production_date.isoformat(), "customer": customer.strip(), "status": status,
                    "quantity": float(quantity), "unit": unit, "notes": notes.strip(), "components": components,
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                })
                database["batch_registry"] = records[:1000]
                deps["save_database"](database)
                st.session_state["batch_components_seed"] = [{"Materiał / komponent": "", "Nr partii materiału": "", "Ilość": 0.0, "Jednostka": "kg", "Uwagi": ""}]
                st.success(f"Zapisano partię {batch_number.strip()} wraz z {len(components)} pozycjami składu.")

        records = deps["load_database"]().get("batch_registry", [])
        if records:
            st.markdown("#### Ostatnio zapisane partie")
            for record in records[:20]:
                summary = f"{record.get('batch_number', '—')} · {record.get('product', '—')} · {record.get('status', '—')}"
                with st.expander(summary):
                    st.write({
                        "Data produkcji": record.get("production_date", "—"), "Zlecenie / projekt": record.get("order_number", "—"),
                        "Klient": record.get("customer", "—"), "Ilość": f"{record.get('quantity', 0)} {record.get('unit', '')}",
                        "Uwagi": record.get("notes", "—"),
                    })
                    st.caption("Skład partii")
                    st.dataframe(record.get("components", []), use_container_width=True, hide_index=True)
