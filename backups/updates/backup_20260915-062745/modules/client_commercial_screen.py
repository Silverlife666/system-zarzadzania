"""Moduł 19: relacje handlowe z klientem."""
from io import BytesIO
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _table(st, pd, records, columns, empty_message):
    if not records:
        st.info(empty_message)
        return
    st.dataframe(pd.DataFrame(records).reindex(columns=columns, fill_value=""), width="stretch", hide_index=True)


def _number(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def build_sales_offer_pdf(offer_records, generated_at):
    """Tworzy pojedynczą lub zbiorczą ofertę handlową do pobrania."""
    regular_font, bold_font = "Helvetica", "Helvetica-Bold"
    try:
        if "OfferDejaVu" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("OfferDejaVu", os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "DejaVuSans.ttf")))
            pdfmetrics.registerFont(TTFont("OfferDejaVuBold", os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "DejaVuSans-Bold.ttf")))
        regular_font, bold_font = "OfferDejaVu", "OfferDejaVuBold"
    except Exception:
        pass
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=16 * mm, bottomMargin=16 * mm)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("SalesOfferTitle", parent=styles["Title"], fontName=bold_font, fontSize=18, leading=22, textColor=colors.HexColor("#123B66"), spaceAfter=5)
    subtitle = ParagraphStyle("SalesOfferSubtitle", parent=styles["Normal"], fontName=regular_font, fontSize=9, leading=12, textColor=colors.HexColor("#475569"), spaceAfter=12)
    section = ParagraphStyle("SalesOfferSection", parent=styles["Heading2"], fontName=bold_font, fontSize=11, leading=14, textColor=colors.HexColor("#123B66"), spaceBefore=9, spaceAfter=5)
    normal = ParagraphStyle("SalesOfferNormal", parent=styles["Normal"], fontName=regular_font, fontSize=8.5, leading=11)
    story = [
        Paragraph("OFERTA HANDLOWA" if len(offer_records) == 1 else "ZBIORCZA OFERTA HANDLOWA", title),
        Paragraph(f"Wygenerowano: {generated_at.strftime('%d.%m.%Y %H:%M')} | Pozycji ofertowych: {len(offer_records)}", subtitle),
    ]
    total_by_currency = {}
    for index, offer in enumerate(offer_records, start=1):
        net_value = _number(offer.get("Wartość netto", 0))
        currency = str(offer.get("Waluta", "PLN") or "PLN")
        total_by_currency[currency] = total_by_currency.get(currency, 0.0) + net_value
        story.append(Paragraph(f"{index}. {offer.get('Nr oferty', 'Oferta')} - {offer.get('Klient', '—')}", section))
        rows = [
            ["Produkt / zakres", str(offer.get("Produkt / zakres", "—")), "Status", str(offer.get("Status", "Robocza"))],
            ["Ilość", f"{offer.get('Ilość', 0)} {offer.get('Jednostka', '')}", "Ważna do", str(offer.get("Ważna do", "—"))],
            ["Cena netto / jedn.", f"{_number(offer.get('Cena jedn.', 0)):.2f} {currency}", "Rabat", f"{_number(offer.get('Rabat %', 0)):g} %"],
            ["Wartość netto", f"{net_value:.2f} {currency}", "Uwagi", str(offer.get("Uwagi", "—") or "—")],
        ]
        table = Table([[Paragraph(f"<b>{cell}</b>", normal) if column in (0, 2) else Paragraph(cell, normal) for column, cell in enumerate(row)] for row in rows], colWidths=[34 * mm, 66 * mm, 30 * mm, 52 * mm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EAF1F8")),
            ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#EAF1F8")),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.extend([table, Spacer(1, 6)])
    if len(offer_records) > 1:
        summary = " | ".join(f"{value:.2f} {currency}" for currency, value in total_by_currency.items())
        story.extend([Paragraph("Podsumowanie", section), Paragraph(f"Łączna wartość netto: <b>{summary}</b>", normal)])
    story.extend([Spacer(1, 18), Paragraph("Warunki oferty wymagają potwierdzenia przez klienta. Dokument wygenerowany z Systemu Zarządzania Produkcją.", subtitle)])
    document.build(story)
    return buffer.getvalue()


def build_price_list_pdf(price_records, group_name, generated_at):
    """Tworzy PDF cennika z wybranymi pozycjami jednej grupy."""
    buffer = BytesIO()
    regular_font, bold_font = "Helvetica", "Helvetica-Bold"
    try:
        if "OfferDejaVu" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("OfferDejaVu", os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "DejaVuSans.ttf")))
            pdfmetrics.registerFont(TTFont("OfferDejaVuBold", os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "DejaVuSans-Bold.ttf")))
        regular_font, bold_font = "OfferDejaVu", "OfferDejaVuBold"
    except Exception:
        pass
    document = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=14 * mm, rightMargin=14 * mm, topMargin=16 * mm, bottomMargin=16 * mm)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("PriceListTitle", parent=styles["Title"], fontName=bold_font, fontSize=18, leading=22, textColor=colors.HexColor("#123B66"), spaceAfter=5)
    subtitle = ParagraphStyle("PriceListSubtitle", parent=styles["Normal"], fontName=regular_font, fontSize=9, leading=12, textColor=colors.HexColor("#475569"), spaceAfter=12)
    cell = ParagraphStyle("PriceListCell", parent=styles["Normal"], fontName=regular_font, fontSize=8, leading=10)
    header = ParagraphStyle("PriceListHeader", parent=cell, fontName=bold_font, textColor=colors.white)
    story = [
        Paragraph("CENNIK KLIENTA", title),
        Paragraph(f"Grupa cennika: <b>{group_name}</b><br/>Wygenerowano: {generated_at.strftime('%d.%m.%Y %H:%M')}", subtitle),
    ]
    columns = ["Produkt / usługa", "SKU / kod", "Jednostka", "Min. ilość", "Cena netto", "Waluta", "Ważny do", "Uwagi"]
    rows = [[Paragraph(label, header) for label in columns]]
    for record in price_records:
        values = [
            record.get("Produkt / usługa", "—"), record.get("SKU / kod", "—") or "—", record.get("Jednostka", "—"),
            f"{_number(record.get('Minimalna ilość', 0)):g}", f"{_number(record.get('Cena netto', 0)):.2f}",
            record.get("Waluta", "PLN"), record.get("Ważny do", "—"), record.get("Uwagi", "") or "—",
        ]
        rows.append([Paragraph(str(value), cell) for value in values])
    table = Table(rows, colWidths=[35 * mm, 24 * mm, 20 * mm, 18 * mm, 20 * mm, 14 * mm, 22 * mm, 29 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#123B66")),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.extend([table, Spacer(1, 14), Paragraph("Ceny są cenami netto. Cennik ma charakter informacyjny i wymaga potwierdzenia w ofercie lub zamówieniu.", subtitle)])
    document.build(story)
    return buffer.getvalue()


def render_client_commercial_screen(st, deps):
    pd = deps["pd"]
    datetime = deps["datetime"]
    secrets = deps["secrets"]
    load_database = deps["load_database"]
    save_database = deps["save_database"]

    st.title("🤝 Relacje handlowe z klientami")
    st.caption("Cenniki, oferty oraz reklamacje w jednym miejscu. Każda zakładka zapisuje dane trwale.")
    database = load_database()
    price_lists = database.setdefault("client_price_lists", [])
    offers = database.setdefault("sales_offers", [])
    complaints = database.setdefault("customer_complaints", [])
    customer_names = sorted({str(value).strip() for value in database.get("orders_clients", []) if str(value).strip()})
    customer_options = customer_names or ["— wpisz ręcznie —"]

    prices_tab, offers_tab, complaints_tab = st.tabs(["💰 Cenniki klientów", "📝 Oferty handlowe", "⚠️ Reklamacje klientów"])

    with prices_tab:
        st.subheader("Cenniki klientów")
        existing_groups = sorted({str(row.get("Grupa cennika", row.get("Klient", ""))).strip() for row in price_lists if str(row.get("Grupa cennika", row.get("Klient", ""))).strip()}, key=str.lower)
        with st.form("add_client_price_form", clear_on_submit=True):
            first, second, third = st.columns(3)
            with first:
                customer_choice = st.selectbox("Klient", customer_options, key="price_customer_choice")
                customer_manual = st.text_input("Klient — nazwa ręczna", disabled=customer_choice != "— wpisz ręcznie —")
                product = st.text_input("Produkt / usługa")
            with second:
                price_group_mode = st.selectbox("Grupa cennika", ["Automatycznie: klient"] + existing_groups + ["Nowa grupa ręcznie"])
                price_group_manual = st.text_input("Nazwa nowej grupy", disabled=price_group_mode != "Nowa grupa ręcznie")
                code = st.text_input("SKU / kod")
                unit = st.selectbox("Jednostka", ["szt.", "kg", "m", "bobina", "usługa"])
                minimum_qty = st.number_input("Minimalna ilość", min_value=0.0, step=1.0)
            with third:
                unit_price = st.number_input("Cena netto / jednostkę", min_value=0.0, step=0.01)
                currency = st.selectbox("Waluta", ["PLN", "EUR", "USD"])
                valid_to = st.date_input("Ważny do")
            notes = st.text_input("Uwagi do ceny")
            if st.form_submit_button("➕ Dodaj pozycję cennika", type="primary"):
                customer = customer_manual.strip() if customer_choice == "— wpisz ręcznie —" else customer_choice
                group = customer if price_group_mode == "Automatycznie: klient" else price_group_manual.strip() if price_group_mode == "Nowa grupa ręcznie" else price_group_mode
                if not customer or not product.strip():
                    st.error("Podaj klienta i produkt/usługę.")
                elif not group:
                    st.error("Podaj nazwę grupy cennika.")
                else:
                    price_lists.append({
                        "id": secrets.token_hex(6), "Grupa cennika": group, "Klient": customer, "Produkt / usługa": product.strip(), "SKU / kod": code.strip(),
                        "Jednostka": unit, "Minimalna ilość": minimum_qty, "Cena netto": unit_price, "Waluta": currency,
                        "Ważny do": valid_to.isoformat(), "Status": "Aktywny", "Uwagi": notes.strip(),
                        "Zmieniono": datetime.now().isoformat(timespec="seconds"),
                    })
                    save_database(database)
                    st.success("Dodano pozycję cennika.")
                    st.rerun()
        if price_lists:
            # Starsze pozycje bez grupy przypisujemy automatycznie do grupy klienta.
            for row in price_lists:
                row.setdefault("Grupa cennika", row.get("Klient", "Pozostałe"))
            grouped_names = sorted({row.get("Grupa cennika", "Pozostałe") for row in price_lists}, key=str.lower)
            selected_group = st.selectbox("Pokaż grupę cennika", grouped_names)
            group_records = [row for row in price_lists if row.get("Grupa cennika") == selected_group]
            selectable = pd.DataFrame(group_records).copy()
            selectable.insert(0, "Wybierz do PDF", False)
            price_preview_columns = ["Wybierz do PDF", "Klient", "Produkt / usługa", "SKU / kod", "Jednostka", "Minimalna ilość", "Cena netto", "Waluta", "Ważny do", "Status", "Uwagi"]
            selected_rows = st.data_editor(
                selectable.reindex(columns=price_preview_columns, fill_value=""),
                disabled=price_preview_columns[1:],
                width="stretch", hide_index=True, key=f"price_list_select_{selected_group}",
            )
            selected_pdf_indices = set(selected_rows.index[selected_rows["Wybierz do PDF"] == True].tolist())
            chosen_price_records = [row for index, row in enumerate(group_records) if index in selected_pdf_indices]
            if chosen_price_records:
                price_pdf = build_price_list_pdf(chosen_price_records, selected_group, datetime.now())
                st.download_button(
                    f"📄 Pobierz cennik PDF ({len(chosen_price_records)} pozycji)", data=price_pdf,
                    file_name=f"cennik_{selected_group.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf", key="download_price_list_pdf",
                )
            else:
                st.caption("Zaznacz checkbox przy co najmniej jednej pozycji, aby wygenerować PDF cennika.")

            price_labels = [f"{row.get('Grupa cennika')} · {row.get('Klient')} · {row.get('Produkt / usługa')}" for row in price_lists]
            selected_price = st.selectbox("Edytuj lub usuń pozycję", range(len(price_lists)), format_func=lambda i: price_labels[i])
            current_price = price_lists[selected_price]
            with st.expander("✏️ Edycja wybranej pozycji cennika", expanded=False):
                with st.form("edit_client_price_form"):
                    e1, e2, e3 = st.columns(3)
                    with e1:
                        edit_group = st.text_input("Grupa cennika", value=current_price.get("Grupa cennika", ""))
                        edit_client = st.text_input("Klient", value=current_price.get("Klient", ""))
                        edit_product = st.text_input("Produkt / usługa", value=current_price.get("Produkt / usługa", ""))
                    with e2:
                        edit_code = st.text_input("SKU / kod", value=current_price.get("SKU / kod", ""))
                        edit_unit = st.selectbox("Jednostka", ["szt.", "kg", "m", "bobina", "usługa"], index=["szt.", "kg", "m", "bobina", "usługa"].index(current_price.get("Jednostka", "szt.") if current_price.get("Jednostka", "szt.") in ["szt.", "kg", "m", "bobina", "usługa"] else "szt."))
                        edit_minimum = st.number_input("Minimalna ilość", min_value=0.0, value=_number(current_price.get("Minimalna ilość", 0)), step=1.0)
                    with e3:
                        edit_price = st.number_input("Cena netto", min_value=0.0, value=_number(current_price.get("Cena netto", 0)), step=0.01)
                        edit_currency = st.selectbox("Waluta", ["PLN", "EUR", "USD"], index=["PLN", "EUR", "USD"].index(current_price.get("Waluta", "PLN") if current_price.get("Waluta", "PLN") in ["PLN", "EUR", "USD"] else "PLN"))
                        edit_status = st.selectbox("Status", ["Aktywny", "Wstrzymany", "Wygasły"], index=["Aktywny", "Wstrzymany", "Wygasły"].index(current_price.get("Status", "Aktywny") if current_price.get("Status", "Aktywny") in ["Aktywny", "Wstrzymany", "Wygasły"] else "Aktywny"))
                    edit_notes = st.text_input("Uwagi", value=current_price.get("Uwagi", ""))
                    if st.form_submit_button("💾 Zapisz zmiany pozycji"):
                        current_price.update({"Grupa cennika": edit_group.strip() or edit_client.strip(), "Klient": edit_client.strip(), "Produkt / usługa": edit_product.strip(), "SKU / kod": edit_code.strip(), "Jednostka": edit_unit, "Minimalna ilość": edit_minimum, "Cena netto": edit_price, "Waluta": edit_currency, "Status": edit_status, "Uwagi": edit_notes.strip(), "Zmieniono": datetime.now().isoformat(timespec="seconds")})
                        save_database(database); st.success("Zapisano zmiany."); st.rerun()
            confirm_price_delete = st.checkbox("Potwierdzam usunięcie wybranej pozycji cennika")
            if st.button("🗑️ Usuń wybraną pozycję", disabled=not confirm_price_delete):
                price_lists.pop(selected_price); save_database(database); st.rerun()
        else:
            st.info("Brak pozycji w cennikach.")

    with offers_tab:
        st.subheader("Oferty handlowe")
        active_prices = [row for row in price_lists if row.get("Status", "Aktywny") == "Aktywny"]
        with st.form("add_sales_offer_form", clear_on_submit=True):
            offer_col1, offer_col2, offer_col3 = st.columns(3)
            with offer_col1:
                offer_customer = st.selectbox("Klient", customer_options, key="offer_customer_choice")
                offer_customer_manual = st.text_input("Klient — nazwa ręczna", disabled=offer_customer != "— wpisz ręcznie —")
                offer_product = st.text_input("Produkt / zakres oferty")
            with offer_col2:
                offer_quantity = st.number_input("Ilość", min_value=1.0, step=1.0)
                offer_unit = st.selectbox("Jednostka", ["szt.", "kg", "m", "bobina", "usługa"], key="offer_unit")
                offer_price = st.number_input("Cena netto / jednostkę", min_value=0.0, step=0.01)
            with offer_col3:
                offer_currency = st.selectbox("Waluta", ["PLN", "EUR", "USD"], key="offer_currency")
                discount = st.number_input("Rabat [%]", min_value=0.0, max_value=100.0, step=0.5)
                valid_until = st.date_input("Oferta ważna do")
            offer_notes = st.text_area("Uwagi / warunki handlowe")
            if st.form_submit_button("➕ Utwórz ofertę", type="primary"):
                customer = offer_customer_manual.strip() if offer_customer == "— wpisz ręcznie —" else offer_customer
                if not customer or not offer_product.strip():
                    st.error("Podaj klienta oraz produkt lub zakres oferty.")
                else:
                    gross = offer_quantity * offer_price
                    net = round(gross * (1 - discount / 100), 2)
                    offers.append({
                        "id": secrets.token_hex(6), "Nr oferty": f"OF/{datetime.now().strftime('%Y%m%d')}/{len(offers)+1:03d}",
                        "Klient": customer, "Produkt / zakres": offer_product.strip(), "Ilość": offer_quantity, "Jednostka": offer_unit,
                        "Cena jedn.": offer_price, "Rabat %": discount, "Wartość netto": net, "Waluta": offer_currency,
                        "Ważna do": valid_until.isoformat(), "Status": "Robocza", "Uwagi": offer_notes.strip(),
                        "Utworzono": datetime.now().isoformat(timespec="seconds"),
                    })
                    save_database(database); st.success("Utworzono ofertę."); st.rerun()
        _table(st, pd, offers, ["Nr oferty", "Klient", "Produkt / zakres", "Ilość", "Jednostka", "Cena jedn.", "Rabat %", "Wartość netto", "Waluta", "Ważna do", "Status"], "Brak ofert handlowych.")
        if offers:
            offer_labels = [f"{row.get('Nr oferty')} · {row.get('Klient')}" for row in offers]
            selected_offer = st.selectbox("Zmień status oferty", range(len(offers)), format_func=lambda i: offer_labels[i])
            new_offer_status = st.selectbox("Status", ["Robocza", "Wysłana", "Zaakceptowana", "Odrzucona", "Wygasła"], key="offer_status")
            if st.button("💾 Zapisz status oferty"):
                offers[selected_offer]["Status"] = new_offer_status
                offers[selected_offer]["Zmieniono"] = datetime.now().isoformat(timespec="seconds")
                save_database(database); st.success("Status oferty zapisany."); st.rerun()
            current_offer = offers[selected_offer]
            with st.expander("✏️ Edycja wybranej oferty", expanded=False):
                with st.form("edit_sales_offer_form"):
                    e1, e2, e3 = st.columns(3)
                    with e1:
                        edit_offer_customer = st.text_input("Klient", value=current_offer.get("Klient", ""))
                        edit_offer_product = st.text_input("Produkt / zakres", value=current_offer.get("Produkt / zakres", ""))
                        edit_offer_quantity = st.number_input("Ilość", min_value=1.0, value=_number(current_offer.get("Ilość", 1)), step=1.0)
                    with e2:
                        unit_options = ["szt.", "kg", "m", "bobina", "usługa"]
                        current_unit = current_offer.get("Jednostka", "szt.")
                        edit_offer_unit = st.selectbox("Jednostka", unit_options, index=unit_options.index(current_unit) if current_unit in unit_options else 0)
                        edit_offer_price = st.number_input("Cena netto / jednostkę", min_value=0.0, value=_number(current_offer.get("Cena jedn.", 0)), step=0.01)
                        edit_offer_discount = st.number_input("Rabat [%]", min_value=0.0, max_value=100.0, value=_number(current_offer.get("Rabat %", 0)), step=0.5)
                    with e3:
                        currency_options = ["PLN", "EUR", "USD"]
                        current_currency = current_offer.get("Waluta", "PLN")
                        edit_offer_currency = st.selectbox("Waluta", currency_options, index=currency_options.index(current_currency) if current_currency in currency_options else 0)
                        status_options = ["Robocza", "Wysłana", "Zaakceptowana", "Odrzucona", "Wygasła"]
                        current_status = current_offer.get("Status", "Robocza")
                        edit_offer_status = st.selectbox("Status oferty", status_options, index=status_options.index(current_status) if current_status in status_options else 0)
                        edit_offer_valid_until = st.text_input("Ważna do", value=str(current_offer.get("Ważna do", "")))
                    edit_offer_notes = st.text_area("Uwagi / warunki handlowe", value=current_offer.get("Uwagi", ""))
                    if st.form_submit_button("💾 Zapisz zmiany oferty"):
                        updated_net_value = round(edit_offer_quantity * edit_offer_price * (1 - edit_offer_discount / 100), 2)
                        current_offer.update({
                            "Klient": edit_offer_customer.strip(), "Produkt / zakres": edit_offer_product.strip(),
                            "Ilość": edit_offer_quantity, "Jednostka": edit_offer_unit, "Cena jedn.": edit_offer_price,
                            "Rabat %": edit_offer_discount, "Wartość netto": updated_net_value, "Waluta": edit_offer_currency,
                            "Ważna do": edit_offer_valid_until.strip(), "Status": edit_offer_status,
                            "Uwagi": edit_offer_notes.strip(), "Zmieniono": datetime.now().isoformat(timespec="seconds"),
                        })
                        save_database(database); st.success("Zapisano zmiany oferty."); st.rerun()
            confirm_offer_delete = st.checkbox("Potwierdzam usunięcie wybranej oferty", key="confirm_offer_delete")
            if st.button("🗑️ Usuń wybraną ofertę", disabled=not confirm_offer_delete):
                offers.pop(selected_offer)
                save_database(database)
                st.success("Usunięto ofertę.")
                st.rerun()
            st.markdown("#### PDF oferty")
            single_offer = offers[selected_offer]
            single_pdf = build_sales_offer_pdf([single_offer], datetime.now())
            st.download_button(
                "📄 Pobierz wybraną ofertę PDF", data=single_pdf,
                file_name=f"{single_offer.get('Nr oferty', 'oferta').replace('/', '_')}.pdf",
                mime="application/pdf", key="download_single_offer_pdf",
            )
            selected_offer_indices = st.multiselect(
                "Połącz oferty w jeden PDF", range(len(offers)),
                format_func=lambda i: offer_labels[i], key="combine_offer_pdf_indices",
                help="Zaznacz co najmniej dwie oferty, aby utworzyć jeden dokument zbiorczy.",
            )
            if len(selected_offer_indices) >= 2:
                combined_records = [offers[index] for index in selected_offer_indices]
                combined_pdf = build_sales_offer_pdf(combined_records, datetime.now())
                st.download_button(
                    f"📄 Pobierz zbiorczą ofertę PDF ({len(combined_records)})", data=combined_pdf,
                    file_name=f"oferta_zbiorcza_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                    mime="application/pdf", key="download_combined_offer_pdf",
                )
            elif selected_offer_indices:
                st.caption("Zaznacz jeszcze co najmniej jedną ofertę, aby utworzyć dokument zbiorczy.")

    with complaints_tab:
        st.subheader("Reklamacje klientów")
        with st.form("add_customer_complaint_form", clear_on_submit=True):
            complaint_col1, complaint_col2, complaint_col3 = st.columns(3)
            with complaint_col1:
                complaint_customer = st.selectbox("Klient", customer_options, key="complaint_customer_choice")
                complaint_customer_manual = st.text_input("Klient — nazwa ręczna", disabled=complaint_customer != "— wpisz ręcznie —")
                complaint_order = st.text_input("Nr zlecenia")
            with complaint_col2:
                complaint_product = st.text_input("Produkt")
                complaint_type = st.selectbox("Rodzaj", ["Jakość", "Ilość", "Uszkodzenie transportowe", "Dokumentacja", "Inne"])
                severity = st.selectbox("Priorytet", ["Niski", "Średni", "Wysoki", "Krytyczny"])
            with complaint_col3:
                owner = st.text_input("Osoba odpowiedzialna")
                due_date = st.date_input("Termin odpowiedzi")
                complaint_description = st.text_area("Opis reklamacji")
            if st.form_submit_button("➕ Zarejestruj reklamację", type="primary"):
                customer = complaint_customer_manual.strip() if complaint_customer == "— wpisz ręcznie —" else complaint_customer
                if not customer or not complaint_description.strip():
                    st.error("Podaj klienta oraz opis reklamacji.")
                else:
                    complaints.append({
                        "id": secrets.token_hex(6), "Nr reklamacji": f"RKL/{datetime.now().strftime('%Y%m%d')}/{len(complaints)+1:03d}",
                        "Klient": customer, "Nr zlecenia": complaint_order.strip(), "Produkt": complaint_product.strip(),
                        "Rodzaj": complaint_type, "Priorytet": severity, "Status": "Nowa", "Odpowiedzialny": owner.strip(),
                        "Termin odpowiedzi": due_date.isoformat(), "Opis": complaint_description.strip(), "Działania korygujące": "",
                        "Utworzono": datetime.now().isoformat(timespec="seconds"),
                    })
                    save_database(database); st.success("Reklamacja została zarejestrowana."); st.rerun()
        _table(st, pd, complaints, ["Nr reklamacji", "Klient", "Nr zlecenia", "Produkt", "Rodzaj", "Priorytet", "Status", "Odpowiedzialny", "Termin odpowiedzi", "Opis"], "Brak zarejestrowanych reklamacji.")
        if complaints:
            complaint_labels = [f"{row.get('Nr reklamacji')} · {row.get('Klient')} · {row.get('Status')}" for row in complaints]
            selected_complaint = st.selectbox("Obsłuż reklamację", range(len(complaints)), format_func=lambda i: complaint_labels[i])
            selected_record = complaints[selected_complaint]
            update_col1, update_col2 = st.columns(2)
            with update_col1:
                complaint_status = st.selectbox("Status reklamacji", ["Nowa", "W analizie", "Oczekuje na klienta", "Uznana", "Odrzucona", "Zamknięta"], key="complaint_status")
            with update_col2:
                corrective_action = st.text_area("Działania korygujące", value=selected_record.get("Działania korygujące", ""))
            if st.button("💾 Zapisz obsługę reklamacji"):
                selected_record["Status"] = complaint_status
                selected_record["Działania korygujące"] = corrective_action.strip()
                selected_record["Zmieniono"] = datetime.now().isoformat(timespec="seconds")
                save_database(database); st.success("Zapisano obsługę reklamacji."); st.rerun()
