"""Moduł 25: niezależne Pre-Ordery z wieloma pozycjami."""

from datetime import date, datetime
from math import ceil
from uuid import uuid4

from services.production_documents import DeepLTranslationError, _deepl_translate_texts
from services.preorder_documents import build_preorder_pdf


def _save(deps, archive):
    deps["save_json"](deps["archive_file"], archive)


def _parse_saved_date(value):
    """Obsługuje bieżący format ISO i starszy format widoczny w PDF."""
    for date_format in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(str(value), date_format).date()
        except (TypeError, ValueError):
            pass
    return date.today()


def _new_preorder():
    return {"id": uuid4().hex[:8], "created_at": datetime.now().isoformat(timespec="seconds"), "meta": {}, "items": []}


def _calculate_pallets(quantity, quantity_per_carton, cartons_per_pallet):
    """Wylicza liczbę pełnych/rozpoczętych palet z ilości netto."""
    try:
        quantity, quantity_per_carton, cartons_per_pallet = float(quantity), float(quantity_per_carton), float(cartons_per_pallet)
    except (TypeError, ValueError):
        return 0
    return int(ceil(quantity / (quantity_per_carton * cartons_per_pallet))) if quantity > 0 and quantity_per_carton > 0 and cartons_per_pallet > 0 else 0


def _pallet_breakdown(quantity, quantity_per_carton, cartons_per_pallet):
    try:
        cartons = float(quantity) / float(quantity_per_carton)
        capacity = float(cartons_per_pallet)
    except (TypeError, ValueError, ZeroDivisionError):
        return "Brak danych do wyliczenia"
    if cartons <= 0 or capacity <= 0:
        return "Brak danych do wyliczenia"
    full_pallets = int(cartons // capacity)
    remaining_cartons = cartons - full_pallets * capacity
    format_number = lambda value: f"{value:g}".replace(".", ",")
    pallet_word = "paleta" if full_pallets == 1 else ("palety" if full_pallets % 10 in {2, 3, 4} and full_pallets % 100 not in {12, 13, 14} else "palet")
    if full_pallets and remaining_cartons:
        return f"{full_pallets} {pallet_word} + {format_number(remaining_cartons)} kartonów"
    if full_pallets:
        return f"{full_pallets} {pallet_word}"
    return f"{format_number(remaining_cartons)} kartonów"


def _order_cartons(quantity, quantity_per_carton):
    try:
        result = float(quantity) / float(quantity_per_carton)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0
    if result <= 0:
        return 0
    return int(result) if result.is_integer() else result


def _deepl_preorder_data(items, meta, api_key):
    """Tłumaczy własne opisy do kopii EN, bez zmiany polskiego archiwum."""
    item_fields = ("product_name", "product_type", "other_criteria", "filter_color", "dimensions", "box_paper_color")
    texts = [str(meta.get("confirmation_note", "")).strip()]
    texts.extend(str(item.get(field, "")).strip() for item in items for field in item_fields)
    texts = list(dict.fromkeys(text for text in texts if text and text != "—"))
    translated = _deepl_translate_texts(texts, api_key) if texts else {}
    english_meta = {**meta, "confirmation_note": translated.get(str(meta.get("confirmation_note", "")).strip(), meta.get("confirmation_note", ""))}
    english_items = []
    for item in items:
        copied = dict(item)
        for field in item_fields:
            value = str(item.get(field, "")).strip()
            copied[field] = translated.get(value, item.get(field, "")) if value else item.get(field, "")
        english_items.append(copied)
    return english_items, english_meta


def render_preorder_screen(st, deps):
    archive = deps["load_json"](deps["archive_file"], {"preorders": []})
    if not isinstance(archive, dict):
        archive = {"preorders": []}
    preorders = archive.setdefault("preorders", [])
    current_id = st.session_state.get("preorder_current_id")
    current = next((item for item in preorders if item.get("id") == current_id), None)
    if current is None:
        current = _new_preorder(); preorders.append(current); st.session_state["preorder_current_id"] = current["id"]; _save(deps, archive)
    recalculated = False
    for existing_item in current.get("items", []):
        pallets = _calculate_pallets(existing_item.get("qty_net", 0), existing_item.get("qty_carton", 0), existing_item.get("qty_cartons_palette", 0))
        order_cartons = _order_cartons(existing_item.get("qty_net", 0), existing_item.get("qty_carton", 0))
        breakdown = _pallet_breakdown(existing_item.get("qty_net", 0), existing_item.get("qty_carton", 0), existing_item.get("qty_cartons_palette", 0))
        if existing_item.get("qty_pallets") != pallets or existing_item.get("order_cartons") != order_cartons or type(existing_item.get("order_cartons")) is not type(order_cartons) or existing_item.get("pallet_breakdown") != breakdown:
            existing_item["qty_pallets"] = pallets
            existing_item["order_cartons"] = order_cartons
            existing_item["pallet_breakdown"] = breakdown
            recalculated = True
    if recalculated:
        _save(deps, archive)

    st.header("Pre-Order")
    st.caption("Niezależny formularz wstępnego zamówienia. Dodawaj dowolną liczbę pozycji, a potem pobierz zbiorczy PDF.")
    with st.expander("Nagłówek Pre-Orderu", expanded=True):
        meta = current.setdefault("meta", {})
        with st.form("preorder_meta"):
            one, two, three = st.columns(3)
            with one:
                order_no = st.text_input("Numer Pre-Orderu", value=meta.get("order_no", f"PRE-{current['id']}"))
                order_date = st.date_input("Data zamówienia", value=_parse_saved_date(meta.get("order_date")))
            with two:
                company = st.text_input("Odbiorca / firma", value=(meta.get("recipient", {}) or {}).get("company", ""))
                recipient_name = st.text_input("Osoba kontaktowa", value=(meta.get("recipient", {}) or {}).get("name", ""))
                contact = st.text_input("Kontakt (e-mail/telefon)", value=(meta.get("recipient", {}) or {}).get("contact", (meta.get("recipient", {}) or {}).get("email", "")))
            with three:
                delivery_date = st.date_input("Planowana data dostawy", value=_parse_saved_date(meta.get("delivery_date")))
                priority = st.selectbox("Priorytet", ("normalny", "wysoki", "pilny"), index=("normalny", "wysoki", "pilny").index(meta.get("priority", "normalny")) if meta.get("priority") in ("normalny", "wysoki", "pilny") else 0)
                address = st.text_input("Ulica i numer", value=(meta.get("delivery_address", {}) or {}).get("street", ""))
                postal_code = st.text_input("Kod pocztowy", value=(meta.get("delivery_address", {}) or {}).get("postal_code", ""))
                city = st.text_input("Miasto", value=(meta.get("delivery_address", {}) or {}).get("city", ""))
                country = st.text_input("Kraj", value=(meta.get("delivery_address", {}) or {}).get("country", ""))
            note = st.text_area("Uwagi do Pre-Orderu", value=meta.get("confirmation_note", ""))
            header_fields = meta.get("included_header_fields", {}) or {}
            st.markdown("#### Pola nagłówka uwzględniane w PDF")
            header_a, header_b, header_c = st.columns(3)
            with header_a:
                include_order_no = st.checkbox("Numer Pre-Orderu — PDF", value=header_fields.get("order_no", True))
                include_order_date = st.checkbox("Data zamówienia — PDF", value=header_fields.get("order_date", True))
            with header_b:
                include_delivery_date = st.checkbox("Planowana data dostawy — PDF", value=header_fields.get("delivery_date", True))
                include_recipient = st.checkbox("Odbiorca / kontakt — PDF", value=header_fields.get("recipient", True))
            with header_c:
                include_address = st.checkbox("Adres dostawy — PDF", value=header_fields.get("delivery_address", True))
                include_notes = st.checkbox("Uwagi do Pre-Orderu — PDF", value=header_fields.get("confirmation_note", True))
            save_meta = st.form_submit_button("💾 Zapisz nagłówek", width="stretch")
        if save_meta:
            meta.clear()
            meta.update({"order_no": order_no.strip() or f"PRE-{current['id']}", "order_date": order_date.strftime("%d.%m.%Y"), "delivery_date": delivery_date.strftime("%d.%m.%Y"), "priority": priority, "recipient": {"company": company.strip(), "name": recipient_name.strip(), "contact": contact.strip()}, "delivery_address": {"street": address.strip(), "postal_code": postal_code.strip(), "city": city.strip(), "country": country.strip()}, "confirmation_note": note.strip(), "included_header_fields": {"order_no": include_order_no, "order_date": include_order_date, "delivery_date": include_delivery_date, "recipient": include_recipient, "delivery_address": include_address, "confirmation_note": include_notes}, "confirmation_label": "Uwagi", "response_status": "roboczy", "document_version": "v1", "lang": "pl", "hide_reprint": True, "hide_response_status": True, "hide_confirmation": False, "hide_empty_confirmation": True})
            _save(deps, archive)
            st.session_state["preorder_header_saved"] = True
            st.rerun()

    if st.session_state.pop("preorder_header_saved", False):
        st.success("Zapisano nagłówek Pre-Orderu. PDF użyje numeru i daty dostawy z formularza.")

    st.subheader("Dodaj pozycję")
    with st.form("preorder_add_item", clear_on_submit=True):
        a, b, c = st.columns(3)
        with a:
            product_name = st.text_input("Nazwa towaru / usługi")
            product_type = st.text_input("Produkt / typ", placeholder="np. Box")
            client = st.text_input("Klient")
            sku = st.text_input("SKU/EAN")
            series = st.text_input("Seria")
            batch = st.text_input("Partia")
        with b:
            quantity = st.number_input("Ilość", min_value=0, step=1)
            qty_display = st.number_input("Ilość w display", min_value=0, step=1)
            qty_carton = st.number_input("Ilość w kartonie", min_value=0, step=1)
            qty_cartons_palette = st.number_input("Kartony na palecie", min_value=0, step=1)
            qty_displays_palette = st.number_input("Displaye na palecie", min_value=0, step=1)
            qty_pallets = _calculate_pallets(quantity, qty_carton, qty_cartons_palette)
            order_cartons = _order_cartons(quantity, qty_carton)
            pallet_breakdown = _pallet_breakdown(quantity, qty_carton, qty_cartons_palette)
            st.info(f"Ilość kartonów z zamówienia: {str(f'{order_cartons:g}').replace('.', ',')}")
            st.info(f"Rozbicie paletowe: {pallet_breakdown}")
            paper = st.text_input("Kolor / nazwa papieru")
        with c:
            filter_color = st.text_input("Kolor filtrów")
            leaf_count = st.number_input("Ilość listków", min_value=0, step=1)
            dimensions = st.text_input("Wymiary filtrów")
            criteria = st.text_input("Inne kryteria")
            item_notes = st.text_input("Uwagi pozycji")
        st.markdown("#### Pola uwzględniane w PDF")
        pdf_a, pdf_b, pdf_c, pdf_d = st.columns(4)
        with pdf_a:
            pdf_client = st.checkbox("Klient", value=True)
            pdf_type = st.checkbox("Produkt / typ", value=True)
            pdf_sku = st.checkbox("SKU/EAN", value=True)
            pdf_series = st.checkbox("Seria", value=True)
        with pdf_b:
            pdf_batch = st.checkbox("Partia", value=True)
            pdf_filter_color = st.checkbox("Kolor filtrów", value=True)
            pdf_leaves = st.checkbox("Ilość listków", value=True)
            pdf_dimensions = st.checkbox("Wymiary filtrów", value=True)
        with pdf_c:
            pdf_paper = st.checkbox("Kolor / nazwa papieru", value=True)
            pdf_criteria = st.checkbox("Inne kryteria / uwagi", value=True)
            pdf_net = st.checkbox("Ilość", value=True)
            pdf_display = st.checkbox("Ilość w display", value=True)
        with pdf_d:
            pdf_carton = st.checkbox("Ilość w kartonie", value=True)
            pdf_order_cartons = st.checkbox("Ilość kartonów z zamówienia", value=True)
            pdf_cartons_pallet = st.checkbox("Kartony na palecie", value=True)
            pdf_displays_pallet = st.checkbox("Displaye na palecie", value=True)
            pdf_pallet_breakdown = st.checkbox("Rozbicie paletowe", value=True)
        add_item = st.form_submit_button("➕ Dodaj pozycję do Pre-Orderu", width="stretch")
    if add_item:
        if not product_name.strip() or quantity <= 0:
            st.error("Podaj nazwę pozycji i ilość netto większą od zera.")
        else:
            current["items"].append({"product_name": product_name.strip(), "product_type": product_type.strip() or "—", "order_channel": client.strip() or "—", "sku": sku.strip(), "series": series.strip(), "batch": batch.strip(), "qty_net": quantity, "qty_display_pieces": qty_display, "qty_carton": qty_carton, "order_cartons": order_cartons, "qty_cartons_palette": qty_cartons_palette, "qty_displays_palette": qty_displays_palette, "qty_pallets": qty_pallets, "pallet_breakdown": pallet_breakdown, "box_paper_color": paper.strip() or "—", "filter_color": filter_color.strip() or "—", "leaf_count": leaf_count, "dimensions": dimensions.strip() or "—", "other_criteria": " · ".join(value for value in (criteria.strip(), item_notes.strip()) if value) or "—", "included_fields": {"order_channel": pdf_client, "product_type": pdf_type, "sku": pdf_sku, "series": pdf_series, "batch": pdf_batch, "filter_color": pdf_filter_color, "leaf_count": pdf_leaves, "dimensions": pdf_dimensions, "box_paper_color": pdf_paper, "other_criteria": pdf_criteria, "qty_net": pdf_net, "qty_display_pieces": pdf_display, "qty_carton": pdf_carton, "order_cartons": pdf_order_cartons, "qty_cartons_palette": pdf_cartons_pallet, "qty_displays_palette": pdf_displays_pallet, "pallet_breakdown": pdf_pallet_breakdown}})
            _save(deps, archive); st.success("Dodano pozycję. Możesz teraz dodać kolejną.")

    st.subheader(f"Pozycje Pre-Orderu ({len(current['items'])})")
    if current["items"]:
        preview = deps["pd"].DataFrame(current["items"]).reindex(columns=["product_name", "product_type", "order_channel", "sku", "series", "batch", "leaf_count", "dimensions", "qty_net", "qty_display_pieces", "qty_carton", "order_cartons", "qty_cartons_palette", "qty_displays_palette", "pallet_breakdown", "box_paper_color"], fill_value=0)
        preview.columns = ["Nazwa", "Typ", "Klient", "SKU/EAN", "Seria", "Partia", "Ilość listków", "Wymiary filtrów", "Ilość", "Ilość w display", "Ilość w kartonie", "Ilość kartonów z zamówienia", "Kartony na palecie", "Displaye na palecie", "Rozbicie paletowe", "Papier"]
        st.dataframe(preview, width="stretch", hide_index=True)
        duplicate_index = st.selectbox("Powiel pozycję", range(len(current["items"])), key="preorder_duplicate_item", format_func=lambda i: f"{i + 1}. {current['items'][i]['product_name']}")
        duplicate_name = st.text_input("Nowa nazwa powielonej pozycji", placeholder="np. JOQ Violant")
        if st.button("📑 Powiel pozycję", width="stretch"):
            if not duplicate_name.strip():
                st.error("Podaj nową nazwę pozycji.")
            else:
                copied_item = dict(current["items"][duplicate_index])
                copied_item["product_name"] = duplicate_name.strip()
                current["items"].append(copied_item)
                _save(deps, archive); st.success("Powielono pozycję z nową nazwą."); st.rerun()
        with st.expander("✏️ Edytuj pozycję"):
            edit_index = st.selectbox("Pozycja do edycji", range(len(current["items"])), key="preorder_edit_item", format_func=lambda i: f"{i + 1}. {current['items'][i]['product_name']}")
            item = current["items"][edit_index]
            with st.form("preorder_edit_item_form"):
                left, middle, right = st.columns(3)
                with left:
                    edit_name = st.text_input("Nazwa towaru / usługi — edycja", value=item.get("product_name", ""))
                    edit_type = st.text_input("Produkt / typ — edycja", value=item.get("product_type", ""))
                    edit_client = st.text_input("Klient — edycja", value=item.get("order_channel", ""))
                    edit_sku = st.text_input("SKU/EAN — edycja", value=item.get("sku", ""))
                    edit_series = st.text_input("Seria — edycja", value=item.get("series", ""))
                    edit_batch = st.text_input("Partia — edycja", value=item.get("batch", ""))
                with middle:
                    edit_qty = st.number_input("Ilość — edycja", min_value=0, value=int(item.get("qty_net", 0)), step=1)
                    edit_display = st.number_input("Ilość w display — edycja", min_value=0, value=int(item.get("qty_display_pieces", 0)), step=1)
                    edit_carton = st.number_input("Ilość w kartonie — edycja", min_value=0, value=int(item.get("qty_carton", 0)), step=1)
                    edit_cartons_palette = st.number_input("Kartony na palecie — edycja", min_value=0, value=int(item.get("qty_cartons_palette", 0)), step=1)
                    edit_displays_palette = st.number_input("Displaye na palecie — edycja", min_value=0, value=int(item.get("qty_displays_palette", 0)), step=1)
                    edit_pallets = _calculate_pallets(edit_qty, edit_carton, edit_cartons_palette)
                    edit_order_cartons = _order_cartons(edit_qty, edit_carton)
                    edit_breakdown = _pallet_breakdown(edit_qty, edit_carton, edit_cartons_palette)
                    st.info(f"Ilość kartonów z zamówienia: {str(f'{edit_order_cartons:g}').replace('.', ',')}")
                    st.info(f"Rozbicie paletowe: {edit_breakdown}")
                    edit_paper = st.text_input("Kolor / nazwa papieru — edycja", value=item.get("box_paper_color", ""))
                with right:
                    edit_filter = st.text_input("Kolor filtrów — edycja", value=item.get("filter_color", ""))
                    edit_leaf_count = st.number_input("Ilość listków — edycja", min_value=0, value=int(item.get("leaf_count", 0)), step=1)
                    edit_dimensions = st.text_input("Wymiary filtrów — edycja", value=item.get("dimensions", ""))
                    edit_criteria = st.text_input("Inne kryteria — edycja", value=item.get("other_criteria", ""))
                included = item.get("included_fields", {}) or {}
                edit_pdf_a, edit_pdf_b, edit_pdf_c, edit_pdf_d = st.columns(4)
                with edit_pdf_a:
                    edit_pdf_client = st.checkbox("Klient — PDF", value=included.get("order_channel", True))
                    edit_pdf_type = st.checkbox("Produkt / typ — PDF", value=included.get("product_type", True))
                    edit_pdf_sku = st.checkbox("SKU/EAN — PDF", value=included.get("sku", True))
                    edit_pdf_series = st.checkbox("Seria — PDF", value=included.get("series", True))
                with edit_pdf_b:
                    edit_pdf_batch = st.checkbox("Partia — PDF", value=included.get("batch", True))
                    edit_pdf_filter_color = st.checkbox("Kolor filtrów — PDF", value=included.get("filter_color", True))
                    edit_pdf_leaves = st.checkbox("Ilość listków — PDF", value=included.get("leaf_count", True))
                    edit_pdf_dimensions = st.checkbox("Wymiary filtrów — PDF", value=included.get("dimensions", True))
                with edit_pdf_c:
                    edit_pdf_paper = st.checkbox("Kolor / nazwa papieru — PDF", value=included.get("box_paper_color", True))
                    edit_pdf_criteria = st.checkbox("Inne kryteria / uwagi — PDF", value=included.get("other_criteria", True))
                    edit_pdf_net = st.checkbox("Ilość — PDF", value=included.get("qty_net", True))
                    edit_pdf_display = st.checkbox("Ilość w display — PDF", value=included.get("qty_display_pieces", True))
                with edit_pdf_d:
                    edit_pdf_carton = st.checkbox("Ilość w kartonie — PDF", value=included.get("qty_carton", True))
                    edit_pdf_order_cartons = st.checkbox("Ilość kartonów z zamówienia — PDF", value=included.get("order_cartons", True))
                    edit_pdf_cartons_pallet = st.checkbox("Kartony na palecie — PDF", value=included.get("qty_cartons_palette", True))
                    edit_pdf_displays_pallet = st.checkbox("Displaye na palecie — PDF", value=included.get("qty_displays_palette", True))
                    edit_pdf_pallet_breakdown = st.checkbox("Rozbicie paletowe — PDF", value=included.get("pallet_breakdown", True))
                save_item = st.form_submit_button("💾 Zapisz zmiany pozycji", width="stretch")
            if save_item:
                if not edit_name.strip() or edit_qty <= 0:
                    st.error("Podaj nazwę pozycji i ilość netto większą od zera.")
                else:
                    item.update({"product_name": edit_name.strip(), "product_type": edit_type.strip() or "—", "order_channel": edit_client.strip() or "—", "sku": edit_sku.strip(), "series": edit_series.strip(), "batch": edit_batch.strip(), "qty_net": edit_qty, "qty_display_pieces": edit_display, "qty_carton": edit_carton, "order_cartons": edit_order_cartons, "qty_cartons_palette": edit_cartons_palette, "qty_displays_palette": edit_displays_palette, "qty_pallets": edit_pallets, "pallet_breakdown": edit_breakdown, "box_paper_color": edit_paper.strip() or "—", "filter_color": edit_filter.strip() or "—", "leaf_count": edit_leaf_count, "dimensions": edit_dimensions.strip() or "—", "other_criteria": edit_criteria.strip() or "—", "included_fields": {"order_channel": edit_pdf_client, "product_type": edit_pdf_type, "sku": edit_pdf_sku, "series": edit_pdf_series, "batch": edit_pdf_batch, "filter_color": edit_pdf_filter_color, "leaf_count": edit_pdf_leaves, "dimensions": edit_pdf_dimensions, "box_paper_color": edit_pdf_paper, "other_criteria": edit_pdf_criteria, "qty_net": edit_pdf_net, "qty_display_pieces": edit_pdf_display, "qty_carton": edit_pdf_carton, "order_cartons": edit_pdf_order_cartons, "qty_cartons_palette": edit_pdf_cartons_pallet, "qty_displays_palette": edit_pdf_displays_pallet, "pallet_breakdown": edit_pdf_pallet_breakdown}})
                    _save(deps, archive); st.success("Zapisano zmiany pozycji."); st.rerun()
        remove_index = st.selectbox("Usuń pozycję", range(len(current["items"])), format_func=lambda i: f"{i + 1}. {current['items'][i]['product_name']}")
        if st.button("🗑️ Usuń wybraną pozycję"):
            current["items"].pop(remove_index); _save(deps, archive); st.rerun()
    else:
        st.info("Dodaj pierwszą pozycję do Pre-Orderu.")

    meta = {"order_no": f"PRE-{current['id']}", "order_date": date.today().strftime("%d.%m.%Y"), "delivery_date": "", "priority": "normalny", "hide_reprint": True, "hide_response_status": True, "hide_confirmation": False, "hide_empty_confirmation": True, **current.get("meta", {})}
    pdf = build_preorder_pdf(current["items"], meta, font_regular=deps["font_regular"], font_bold=deps["font_bold"], language="pl", logo_path=deps["logo_path"])
    translation_state_key = f"preorder_deepl_en_{current['id']}"
    if st.button("🌐 Przetłumacz opisy Pre-Orderu przez DeepL", disabled=not bool(deps.get("deepl_api_key")), width="stretch"):
        try:
            st.session_state[translation_state_key] = _deepl_preorder_data(current["items"], meta, deps["deepl_api_key"])
            st.success("Przetłumaczono opisy własne przez DeepL.")
        except DeepLTranslationError as error:
            st.error(f"Nie udało się przetłumaczyć przez DeepL: {error}")
    english_items, english_meta = st.session_state.get(translation_state_key, (current["items"], meta))
    pdf_en = build_preorder_pdf(english_items, english_meta, font_regular=deps["font_regular"], font_bold=deps["font_bold"], language="en", logo_path=deps["logo_path"])
    left, middle, third, right = st.columns(4)
    with left:
        st.download_button("📄 Pobierz Pre-Order PDF (PL)", pdf, f"preorder_PL_{meta.get('order_no', current['id']).replace('/', '_')}.pdf", "application/pdf", disabled=not current["items"], width="stretch")
    with middle:
        st.download_button("📄 Pobierz Pre-Order PDF (EN)", pdf_en, f"preorder_EN_{meta.get('order_no', current['id']).replace('/', '_')}.pdf", "application/pdf", disabled=not current["items"], width="stretch")
        if not deps.get("deepl_api_key"):
            st.caption("Brak skonfigurowanego klucza DeepL — PDF EN zawiera angielskie nagłówki, ale opisy własne nie są tłumaczone.")
        else:
            st.caption("Kliknij „Przetłumacz opisy Pre-Orderu przez DeepL”, aby użyć tłumaczeń w PDF EN.")
    with third:
        if st.button("➕ Utwórz kolejny Pre-Order", width="stretch"):
            new = _new_preorder(); preorders.append(new); st.session_state["preorder_current_id"] = new["id"]; _save(deps, archive); st.rerun()
    with right:
        st.caption(f"Archiwum: {len(preorders)} dokumentów · bieżący ID: {current['id']}")

    st.divider(); st.subheader("Archiwum Pre-Orderów")
    for item in reversed(preorders):
        item_meta = item.get("meta", {})
        with st.expander(f"{item_meta.get('order_no', 'Pre-Order roboczy')} · pozycji: {len(item.get('items', []))} · {item.get('created_at', '')}"):
            if st.button("Otwórz ten Pre-Order", key=f"open_preorder_{item['id']}"):
                st.session_state["preorder_current_id"] = item["id"]; st.rerun()
