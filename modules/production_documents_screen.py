"""Widoki Streamlit dokumentów produkcyjnych (moduł 9)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st


def render_production_documents_intro(*, bct_for_order: dict[str, Any] | None,
                                      bct_for_tds: dict[str, Any] | None) -> None:
    """Renderuje stały nagłówek i informacyjne statusy BCT modułu 9."""
    st.subheader("📄 Karta Produktu / Specyfikacja Techniczna Zamówienia Offset, E-Order & Karta Pracy")
    st.markdown("Formularz zintegrowany z trwałym słownikiem, eksportem PDF oraz modułami zbiorczymi **E-Order** i **Karta Pracy** wraz z pełnym archiwum bazy danych.")
    bct_order_status = (bct_for_order or {}).get("approval")
    if bct_order_status and bct_order_status != "zatwierdzony":
        st.warning(f"⚠️ Powiązany karton ma status BCT: „{bct_order_status}”. Zweryfikuj konstrukcję przed wydaniem zamówienia.")
    if bct_for_tds:
        st.info(
            f"BCT w TDS/Karcie Pracy: {bct_for_tds.get('bct', 0):.1f} kg | "
            f"bezpieczne: {bct_for_tds.get('safe_bct', 0):.1f} kg | "
            f"warstwy: {bct_for_tds.get('max_safe_layers', '-')} | "
            f"status: {bct_for_tds.get('approval', '-')}"
        )


def prepare_production_documents_state(*, session_state: Any, active_order_id: str,
                                       registry_header: dict[str, Any] | None,
                                       default_order_header: Any, priorities: list[str],
                                       document_statuses: list[str], languages: list[str]) -> dict[str, Any]:
    """Normalizuje stan sesji modułu 9 bez dostępu do trwałego magazynu."""
    order_header = dict(registry_header or session_state.get("tab9_order_header") or default_order_header(active_order_id))
    order_header["order_id"] = active_order_id
    for key, default_value in default_order_header(active_order_id).items():
        order_header.setdefault(key, default_value)
    if order_header["priority"] not in priorities:
        order_header["priority"] = priorities[0]
    if order_header["document_status"] not in document_statuses:
        order_header["document_status"] = document_statuses[0]
    if order_header["language"] not in languages:
        order_header["language"] = languages[0]
    session_state["tab9_order_header"] = order_header
    session_state.setdefault("e_order_items", [])
    session_state.setdefault("work_sheet_items", [])
    return order_header


def restore_production_document_state(session_state: Any) -> None:
    """Przywraca stan formularza modułu 9 przed utworzeniem jego widgetów."""
    if "tab9_order_to_restore" in session_state:
        for state_key, state_value in session_state.pop("tab9_order_to_restore").items():
            session_state[state_key] = state_value
        session_state["tab9_restore_notice"] = "Przywołano zamówienie z archiwum. Możesz zmienić ilości i inne parametry, a następnie zapisać nową wersję."
    if "tab9_catalog_snapshot_to_restore" in session_state:
        snapshot = session_state.pop("tab9_catalog_snapshot_to_restore")
        session_state["tab9_catalog_snapshot"] = snapshot
        session_state["tab9_catalog_product"] = snapshot.get("Nazwa produktu", "")
        session_state["tab9_catalog_applied_name"] = snapshot.get("Nazwa produktu", "")
    if "tab9_project_attachment_to_restore" in session_state:
        session_state["tab9_project_attachment"] = session_state.pop("tab9_project_attachment_to_restore")
    if "product_to_order" in session_state:
        product = session_state.pop("product_to_order")
        session_state["val_product_name"] = product.get("name", "")
        session_state["tab9_catalog_product"] = product.get("name", "")
        session_state.pop("tab9_catalog_applied_name", None)
        session_state["tab9_product_notice"] = f"Załadowano produkt z bazy: {product.get('name', '')}."


def render_tds_form_intro(session_state: Any) -> None:
    """Renderuje stałe komunikaty formularza TDS i konsumuje komunikaty jednorazowe."""
    st.markdown("### Konfiguracja pól formularza i eksportu")
    st.info("Przy każdym polu znajduje się checkbox 'Uwzględnij', a poniżej możesz zapisać specyfikację, wygenerować PDF lub dodać pozycję bezpośrednio do **E-Order** lub **Karty Pracy**.")
    if session_state.pop("tab9_restore_notice", None):
        st.success("Przywołano zamówienie z archiwum. Możesz je teraz zmienić i zapisać jako nową wersję.")
    product_notice = session_state.pop("tab9_product_notice", None)
    if product_notice:
        st.success(product_notice)


def render_catalog_snapshot_preview(snapshot: dict[str, Any]) -> None:
    """Pokazuje w TDS tylko niepuste dane pobrane z kartoteki."""
    if not snapshot:
        return
    with st.expander("Dane pobrane z kartoteki: Produkt / Display / Master Case", expanded=True):
        rows = []
        for level in ("Produkt", "Display", "Master Case", "Paleta"):
            for parameter, value in snapshot.get(level, {}).items():
                if value not in (None, ""):
                    rows.append({"Poziom": level, "Parametr": parameter, "Wartość": value})
        for parameter, value in snapshot.get("Relacje pakowania", {}).items():
            if value not in (None, ""):
                rows.append({"Poziom": "Relacje", "Parametr": parameter, "Wartość": value})
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def render_tds_materials_section(*, database: dict[str, Any], render_field: Any, render_master_checkbox: Any) -> dict[str, Any]:
    """Renderuje podsekcję materiałów głównego formularza TDS."""
    with st.expander("Podsekcja I: Materiały", expanded=True):
        render_master_checkbox("Uwzględnij całą podsekcję", ["product_type", "product_name", "other_criteria", "dimensions", "filter_color", "custom_filter_color", "box_paper_color", "print_type", "order_channel"], "master_Podsekcja_I_Materialy")
        st.markdown("---")
        fields = {
            "product_type": render_field("Produkt", "select", options=database["products"], key_prefix="product_type"),
            "product_name": render_field("Nazwa produktu *", "text", default_value="KSS Rolling Papers", key_prefix="product_name"),
            "other_criteria": render_field("Inne kryteria", "select", options=database["other_criteria"], key_prefix="other_criteria"),
            "dimensions": render_field("Rozmiar/typ filtra (szer. x wys. w mm)", "select", options=database["dimensions"], key_prefix="dimensions"),
            "filter_color": render_field("Kolor filtra", "select", options=database["filter_colors"], key_prefix="filter_color"),
            "custom_filter_color": render_field("Wpisz kolor (jeśli wybrano 'Inny')", "text", default_value="", key_prefix="custom_filter_color"),
            "box_paper_color": render_field("Kolor papieru w boxie", "select", options=database["box_paper_colors"], key_prefix="box_paper_color"),
            "print_type": render_field("Druk", "select", options=database["print_types"], key_prefix="print_type"),
            "order_channel": render_field("Zamówienie/klient", "select", options=database["orders_clients"], key_prefix="order_channel"),
        }
    return fields


def render_tds_quantities_section(*, render_field: Any, render_master_checkbox: Any) -> dict[str, Any]:
    """Renderuje ilości zamówienia i bufory dla TDS/E-Order."""
    with st.expander("Podsekcja I: Ilości zamówienia & E-Order", expanded=True):
        render_master_checkbox("Uwzględnij całą podsekcję", ["lot_number", "qty_net", "qty_buffer", "qty_production", "qty_shipping", "qty_box", "qty_cover", "qty_display", "qty_carton", "qty_display_pieces", "qty_cartons_palette", "qty_displays_palette"], "master_Podsekcja_I_Ilosci_zamowienia")
        st.markdown("---")
        fields = {key: render_field(label, kind, default_value=default, key_prefix=key) for key, label, kind, default in [
            ("lot_number", "Numer partii / LOT", "text", ""), ("qty_net", "Ilość zamówienia netto", "number", 0),
            ("qty_buffer", "Zapas [szt.]", "number", 0), ("qty_production", "Ilość do produkcji (0 = netto + zapas)", "number", 0),
            ("qty_shipping", "Ilość do wysyłki (0 = ilość netto)", "number", 0), ("qty_display_pieces", "Ilość sztuk w display", "number", 50),
            ("qty_carton", "Ilość sztuk w karton zbiorczy", "number", 1200), ("qty_cartons_palette", "Ilość kartonów na palecie", "number", 10),
            ("qty_displays_palette", "Ilość displayów na palecie", "number", 240),
        ]}
        for key, label, buffer_key in (("qty_box", "Ilość zamówienia box", "buff_box"), ("qty_cover", "Ilość zamówienia cover", "buff_cover"), ("qty_display", "Ilość zamówienia display", "buff_disp")):
            first, second = st.columns(2)
            with first:
                fields[key] = render_field(label, "number", default_value=0, key_prefix=key)
            with second:
                fields[buffer_key] = st.number_input(f"Zapas ({label.split()[-1].capitalize()})", value=0, key=buffer_key)
    return fields


def render_tds_artwork_section(*, render_field: Any, render_master_checkbox: Any,
                               existing_attachment: dict[str, Any]) -> tuple[tuple[Any, Any], tuple[Any, Any], tuple[Any, Any], Any]:
    """Renderuje dane projektu dla drukarni oraz opcjonalny plik źródłowy."""
    with st.expander("Podsekcja I: Projekt dla drukarni", expanded=True):
        render_master_checkbox("Uwzględnij dane projektu", ["artwork_number", "artwork_version", "artwork_link"], "master_Podsekcja_I_Projekt_drukarni")
        st.markdown("---")
        number = render_field("Numer projektu graficznego", "text", default_value="", key_prefix="artwork_number")
        version = render_field("Wersja projektu graficznego", "text", default_value="", key_prefix="artwork_version")
        link = render_field("Link do pliku źródłowego", "text", default_value="", key_prefix="artwork_link")
        uploaded = st.file_uploader("Załącz plik źródłowy projektu (opcjonalnie)", type=["pdf", "ai", "eps", "psd", "cdr", "zip", "jpg", "jpeg", "png"], key="tab9_artwork_source_upload", help="Plik jest przechowywany z archiwalnym zleceniem i można go później pobrać.")
        if existing_attachment and uploaded is None:
            st.caption(f"Zachowany załącznik: {existing_attachment.get('name', 'plik')} ({existing_attachment.get('size', 0) / 1024 / 1024:.2f} MB).")
            if existing_attachment.get("sha256"):
                st.caption(f"SHA-256: {existing_attachment['sha256'][:16]}… | wgrano: {existing_attachment.get('uploaded_at', 'brak daty')} | autor: {existing_attachment.get('uploaded_by', 'brak')} | starsze wersje: {len(existing_attachment.get('versions', []))}")
    return number, version, link, uploaded


def render_tds_specification_section(*, database: dict[str, Any], render_field: Any,
                                     render_master_checkbox: Any) -> dict[str, tuple[Any, Any]]:
    """Renderuje sekcje II–IV formularza TDS z zachowaniem historycznych kluczy pól."""
    sections = (
        ("Podsekcja II:Okładka", "master_Podsekcja_II_Okładka", [
            ("ok_gram", "Gramatura (okładka)", "select", "grammages", None), ("ok_print", "Zadruk (okładka)", "select", "print_covers", None), ("ok_rozb", "Rozbarwienie (okładka)", "select", "color_spaces", None), ("ok_druk", "Druk (okładka)", "select", "press_combinations", None), ("ok_lakier", "Folia/Lakier na okładce - Rodzaj", "select", "varnishes", None), ("ok_awers", "Foliowanie/Lakierowanie awers (okładka)", "select", "foil_options", None), ("ok_rewers", "Foliowanie/Lakierowanie rewers (okładka)", "select", "foil_options", None), ("ok_wyk", "Numer wykrojnika (okładka)", "text", None, "-")]),
        ("Podsekcja II:Box rolls", "master_Podsekcja_II_Box_rolls", [
            ("br_gram", "Gramatura (Box rolls)", "select", "grammages", None), ("br_zadruk", "Zadruk (Box rolls)", "select", "print_covers", None), ("br_rozb", "Rozbarwienie (Box rolls)", "select", "color_spaces", None), ("br_druk", "Druk (Box rolls)", "select", "press_combinations", None), ("br_lakier", "Folia/Lakier - Rodzaj (Box rolls)", "select", "varnishes", None), ("br_front", "Foliowanie / lakierowanie front (Box rolls)", "select", "foil_options", None), ("br_tyl", "Foliowanie / lakierowanie tył (Box rolls)", "select", "foil_options", None), ("br_wyk", "Numer wykrojnika (Box rolls)", "number", None, 594)]),
        ("Podsekcja II:Bletka", "master_Podsekcja_II_Bletka", [
            ("bl_gram", "Gramatura (Bletka)", "select", "grammages", None), ("bl_zadruk", "Zadruk (Bletka)", "select", "print_covers", None), ("bl_rozb", "Rozbarwienie (Bletka)", "select", "color_spaces", None), ("bl_druk", "Druk (Bletka)", "select", "press_combinations", None), ("bl_lakier", "Folia/Lakier - Rodzaj (Bletka)", "select", "varnishes", None), ("bl_front", "Foliowanie / lakierowanie front (Bletka)", "select", "foil_options", None), ("bl_tyl", "Foliowanie / lakierowanie tył (Bletka)", "select", "foil_options", None), ("bl_wyk", "Numer wykrojnika (Bletka)", "number", None, 594)]),
        ("Podsekcja II:Arkusz filtra", "master_Podsekcja_II_Arkusz_filtra", [
            ("af_gram", "Gramatura (Arkusz filtra)", "select", "grammages", None), ("af_zadruk", "Zadruk (Arkusz filtra)", "select", "print_covers", None), ("af_rozb", "Rozbarwienie (Arkusz filtra)", "select", "color_spaces", None), ("af_druk", "Druk (Arkusz filtra)", "select", "press_combinations", None), ("af_lakier", "Folia/Lakier - Rodzaj (Arkusz filtra)", "select", "varnishes", None), ("af_front", "Foliowanie / lakierowanie front (Arkusz filtra)", "select", "foil_options", None), ("af_tyl", "Foliowanie / lakierowanie tył (Arkusz filtra)", "select", "foil_options", None), ("af_wyk", "Numer wykrojnika (Arkusz filtra)", "number", None, 594)]),
        ("Podsekcja II:Dodatkowe informacje", "master_Podsekcja_II_Dodatkowe_informacje", [
            ("perf_count", "Ilość perforacji", "select", "perforations", None), ("add_perf", "Dodatkowa perforacja pozioma", "select", "yes_no", None), ("sheets_count", "Ilość listków", "text", None, "-"), ("pack_display", "Ilość pakowana w Display", "text", None, "-"), ("pack_carton", "Ilość pakowana do kartonu zbiorczego", "text", None, "-"), ("carton_print", "Nadruk na kartonie zbiorczym", "select", "yes_no", None)]),
        ("Podsekcja III: Specyfikacja – Display", "master_Podsekcja_III_Display", [
            ("dsp_type", "Display", "select", "print_types", None), ("dsp_gram", "Gramatura (Display)", "select", "grammages", None), ("dsp_zadruk", "Zadruk (Display)", "select", "display_prints", None), ("dsp_rozb", "Rozbarwienie (Display)", "select", "color_spaces", None), ("dsp_lakier", "Folia/Lakier - Rodzaj (Display)", "select", "varnishes", None), ("dsp_wyk", "Numer wykrojnika (Display)", "number", None, 578), ("dsp_lakierowanie", "Foliowanie/lakierowanie (Display)", "select", "foil_options", None)]),
        ("Podsekcja IV: Informacje dodatkowe", "master_Podsekcja_IV_Inne_informacje", [("other_notes", "Uwagi do zamówienia", "area", None, "Papier powierzony na bletki")]),
    )
    values: dict[str, tuple[Any, Any]] = {}
    for title, master_key, fields in sections:
        if title.startswith("Podsekcja III"):
            st.markdown("---")
            st.markdown("### SEKCJA III: SPECYFIKACJA – DISPLAY")
        elif title.startswith("Podsekcja IV"):
            st.markdown("### SEKCJA IV: INNE ISTOTNE INFORMACJE")
        with st.expander(title, expanded=True):
            render_master_checkbox("Uwzględnij całą podsekcję", [field[0] for field in fields], master_key)
            st.markdown("---")
            for key, label, kind, option_key, default in fields:
                kwargs = {"key_prefix": key}
                if option_key:
                    kwargs["options"] = database[option_key]
                if default is not None:
                    kwargs["default_value"] = default
                values[key] = render_field(label, kind, **kwargs)
    return values


def apply_catalog_selection(*, session_state: Any, selected_product: str, empty_option: str,
                            build_snapshot: Any, packaging_calculation: Any,
                            order_clients: list[str]) -> dict[str, Any]:
    """Aktualizuje stan TDS po zmianie produktu wybranego z kartoteki."""
    if selected_product == empty_option:
        session_state.pop("tab9_catalog_snapshot", None)
        session_state.pop("tab9_catalog_applied_name", None)
        return {}
    if session_state.get("tab9_catalog_applied_name") != selected_product:
        snapshot = build_snapshot(selected_product)
        session_state["tab9_catalog_snapshot"] = snapshot
        session_state["tab9_catalog_applied_name"] = selected_product
        session_state["val_product_name"] = selected_product
        client = str(snapshot.get("Klient", "")).strip()
        if client and client in order_clients:
            session_state["val_order_channel"] = client
        relations = packaging_calculation(snapshot, "Produkt", 1)
        session_state["val_qty_display_pieces"] = relations["produktow_w_displayu"]
        session_state["val_qty_carton"] = relations["produktow_w_mastercase"]
    return session_state.get("tab9_catalog_snapshot", {})


def render_order_header_form(*, active_order_id: str, order_header: dict[str, Any], priorities: list[str],
                             document_statuses: list[str], languages: list[str], save_order_header: Any) -> dict[str, Any]:
    """Renderuje i zapisuje nagłówek zlecenia; zwraca bieżący nagłówek."""
    with st.expander("Nagłówek zlecenia", expanded=True):
        st.caption(f"Trwały identyfikator zlecenia: `{active_order_id}`")
        try:
            delivery_default = datetime.fromisoformat(str(order_header.get("delivery_date", ""))).date()
        except (TypeError, ValueError):
            delivery_default = datetime.now().date()
        with st.form(f"tab9_order_header_form_{active_order_id}"):
            col_one, col_two, col_three = st.columns(3)
            with col_one:
                number = st.text_input("Numer zlecenia *", value=order_header["order_number"], key=f"tab9_header_order_number_{active_order_id}")
                priority = st.selectbox("Priorytet", priorities, index=priorities.index(order_header["priority"]), key=f"tab9_header_priority_{active_order_id}")
                delivery_date = st.date_input("Planowana data dostawy", value=delivery_default, key=f"tab9_header_delivery_date_{active_order_id}")
            with col_two:
                status = st.selectbox("Status dokumentu", document_statuses, index=document_statuses.index(order_header["document_status"]), key=f"tab9_header_status_{active_order_id}")
                language = st.selectbox("Język dokumentów", languages, index=languages.index(order_header["language"]), key=f"tab9_header_language_{active_order_id}")
            with col_three:
                version = st.text_input("Wersja dokumentu", value=order_header["document_version"], key=f"tab9_header_version_{active_order_id}", help="Np. v1, v2 lub v2.1.")
                change_reason = st.text_input("Powód zmiany", value=order_header["change_reason"], key=f"tab9_header_change_reason_{active_order_id}")
            submitted = st.form_submit_button("💾 Zapisz nagłówek zlecenia")
        if submitted:
            normalized_version = version.strip() or "v1"
            if not normalized_version.lower().startswith("v"):
                normalized_version = f"v{normalized_version}"
            if not number.strip():
                st.error("Uzupełnij numer zlecenia.")
            else:
                order_header = {"order_id": active_order_id, "order_number": number.strip(), "priority": priority,
                                "document_status": status, "language": language, "document_version": normalized_version,
                                "delivery_date": delivery_date.isoformat(), "recipient": order_header.get("recipient", {}),
                                "delivery_address": order_header.get("delivery_address", {}), "change_reason": change_reason.strip()}
                save_order_header(order_header)
                st.success("Nagłówek zlecenia zapisano i powiązano z bieżącym Order ID.")
    return order_header


def render_catalog_selector(*, session_state: Any, catalog_products: dict[str, Any], order_clients: list[str],
                            build_snapshot: Any, packaging_calculation: Any, selected_ean: Any) -> tuple[dict[str, Any], str]:
    """Renderuje wybór produktu TDS i zwraca migawkę katalogu oraz poziom opakowania."""
    empty_option = "— wybierz produkt z kartoteki —"
    options = [empty_option] + sorted(catalog_products.keys(), key=str.lower)
    previous = session_state.get("tab9_catalog_product", empty_option)
    if previous not in options:
        previous = empty_option
    selected_product = st.selectbox(
        "Produkt z kartoteki Produkt / Display / Master Case", options=options, index=options.index(previous),
        key="tab9_catalog_product", help="Wybór wypełnia nazwę produktu, klienta oraz relacje pakowania i zapisuje migawkę danych w zleceniu.",
    )
    snapshot = apply_catalog_selection(
        session_state=session_state, selected_product=selected_product, empty_option=empty_option,
        build_snapshot=build_snapshot, packaging_calculation=packaging_calculation, order_clients=order_clients,
    )
    level = st.selectbox("Poziom pozycji dla E‑Order i Karty Pracy", ["Produkt", "Display", "Master Case"], key="tab9_document_packaging_level", help="Ten wybór decyduje, który EAN zostanie pokazany w pozycji i na PDF.")
    if snapshot:
        st.caption(f"SKU: {snapshot.get('SKU') or 'brak'}  |  EAN Produkt: {selected_ean(snapshot, 'Produkt') or 'brak'}  |  EAN Display: {selected_ean(snapshot, 'Display') or 'brak'}  |  EAN Master Case: {selected_ean(snapshot, 'Master Case') or 'brak'}")
    return snapshot, level
