"""Moduł 15: import i analiza inwentaryzacji tacek."""

from __future__ import annotations

import io
import json
from datetime import datetime

import pandas as pd

from services.inventory import (
    build_inventory_report_pdf,
    build_stock_comparison_pdf,
    build_tray_labels_pdf,
    build_tray_labels_zpl,
    compare_inventory_to_stock,
    enrich_inventory_records,
    mobile_catalog_rows,
    new_session,
    normalize_ean,
    normalize_tray_id,
    parse_inventory_csv,
    parse_comparison_inventory_csv,
    parse_stock_csv,
    session_summary,
    stock_comparison_summary,
    update_inventory_record,
)


def _session_label(session: dict) -> str:
    return f"{session.get('name', 'Inwentaryzacja')} · {session.get('created_at', '')}"


def _report_frame(records: list[dict]) -> pd.DataFrame:
    columns = {
        "timestamp": "Data/czas", "operator": "Operator", "tray_id": "ID tacki",
        "ean": "EAN/GTIN", "product_name": "Nazwa produktu", "actual_quantity": "Ilość rzeczywista",
        "nominal_quantity": "Ilość nominalna", "difference": "Różnica", "recognized": "Rozpoznano produkt",
        "duplicate_tray": "Duplikat tacki", "issue": "Uwagi",
    }
    frame = pd.DataFrame(records)
    return frame.rename(columns=columns).reindex(columns=list(columns.values()), fill_value="")


def _comparison_frame(records: list[dict]) -> pd.DataFrame:
    columns = {
        "ean": "EAN/GTIN", "product_name": "Nazwa produktu", "inventory_quantity": "Inwentaryzacja",
        "stock_quantity": "Stan magazynowy", "difference": "Różnica", "status": "Wynik",
    }
    frame = pd.DataFrame(records)
    return frame.rename(columns=columns).reindex(columns=list(columns.values()), fill_value="")


def _stock_frame(records: list[dict]) -> pd.DataFrame:
    columns = {"ean": "EAN/GTIN", "product_name": "Nazwa produktu", "actual_quantity": "Ilość rzeczywista"}
    frame = pd.DataFrame(records)
    return frame.rename(columns=columns).reindex(columns=list(columns.values()), fill_value="")


def _xlsx_bytes(frame: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        frame.to_excel(writer, index=False, sheet_name="Inwentaryzacja")
    return output.getvalue()


def render_inventory_screen(st, deps):
    """Renderuje widok bez bezpośredniego importowania app.py."""
    load_json = deps["load_json"]
    save_json = deps["save_json"]
    inventory_file = deps["inventory_file"]
    products = deps["load_products"]()
    operator = deps["current_operator"]()

    sessions = load_json(inventory_file, [])
    if not isinstance(sessions, list):
        sessions = []

    st.title("📦 Inwentaryzacja")
    st.caption("Importuj odczyty z telefonu, wykrywaj różnice i twórz raporty oraz etykiety QR dla tacek.")

    manual_tab, import_tab, history_tab, comparison_tab, catalog_tab, labels_tab = st.tabs([
        "Dodaj wpis ręcznie", "Import CSV", "Historia i raport", "Porównaj ze stanem magazynowym", "Katalog do telefonu", "Etykiety QR",
    ])

    with manual_tab:
        st.subheader("Dodaj pojedynczy wpis do historii")
        st.caption("Wpisz dane ręcznie albo użyj skanera USB działającego jak klawiatura. Wpis zostanie zapisany w wybranej sesji i od razu pojawi się w raporcie.")
        session_options = {"➕ Nowa sesja": None}
        session_options.update({_session_label(session): session.get("id") for session in sessions})
        with st.form("inventory_manual_entry_form", clear_on_submit=True):
            target_label = st.selectbox("Zapisz wpis do sesji", list(session_options))
            target_id = session_options[target_label]
            session_name = st.text_input("Nazwa nowej sesji", value="Inwentaryzacja ręczna", disabled=target_id is not None)
            operator_name = st.text_input("Operator", value=operator)
            tray_id = st.text_input("ID tacki / QR", placeholder="np. TRAY|000145")
            ean = st.text_input("EAN / GTIN (opcjonalnie)", placeholder="np. 5901234567890")
            product_name = st.text_input("Nazwa produktu")
            actual_col, nominal_col = st.columns(2)
            with actual_col:
                actual_quantity = st.number_input("Ilość rzeczywista", min_value=0, step=1)
            with nominal_col:
                nominal_quantity = st.number_input("Ilość nominalna", min_value=0, step=1)
            submitted = st.form_submit_button("Dodaj wpis do historii")

        if submitted:
            normalized_tray_id = normalize_tray_id(tray_id)
            if not normalized_tray_id:
                st.error("ID tacki nie może być puste.")
            elif not product_name.strip():
                st.error("Podaj nazwę produktu.")
            else:
                draft = {
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "operator": operator_name.strip(), "ean": normalize_ean(ean),
                    "tray_id": normalized_tray_id, "product_name": product_name.strip(),
                    "actual_quantity": int(actual_quantity), "nominal_quantity": int(nominal_quantity),
                }
                target_session = next((session for session in sessions if session.get("id") == target_id), None)
                existing_records = target_session.get("records", []) if target_session else []
                updated_records = enrich_inventory_records(existing_records + [draft], products)
                if target_session:
                    target_session["records"] = updated_records
                    target_session["summary"] = session_summary(updated_records)
                else:
                    target_session = new_session(session_name.strip() or "Inwentaryzacja ręczna", updated_records, operator_name.strip())
                    sessions.insert(0, target_session)
                save_json(inventory_file, sessions)
                st.session_state["inventory_selected_session"] = target_session["id"]
                st.success(f"Dodano tackę {normalized_tray_id}: {product_name.strip()} — {int(actual_quantity)} szt.")
                st.rerun()

    with import_tab:
        st.subheader("Import odczytów z aplikacji mobilnej")
        st.caption("Obsługiwane są nagłówki: data/czas, operator, EAN/GTIN, ID tacki / QR tacki, nazwa produktu, ilość rzeczywista i ilość nominalna.")
        with st.form("inventory_import_form"):
            session_name = st.text_input("Nazwa sesji", value="Inwentaryzacja", key="inventory_session_name")
            upload = st.file_uploader("CSV z telefonu", type=["csv"], key="inventory_csv_upload")
            submitted = st.form_submit_button("Zaimportuj jako nową sesję")
        if submitted:
            if upload is None:
                st.warning("Wybierz plik CSV z aplikacji mobilnej.")
            else:
                try:
                    records = enrich_inventory_records(parse_inventory_csv(upload.getvalue()), products)
                    session = new_session(session_name, records, operator)
                    sessions.insert(0, session)
                    save_json(inventory_file, sessions)
                    st.session_state["inventory_selected_session"] = session["id"]
                    st.success(f"Zaimportowano {len(records)} pozycji do sesji „{session['name']}”.")
                except ValueError as error:
                    st.error(str(error))

    with history_tab:
        st.subheader("Historia sesji inwentaryzacyjnych")
        if not sessions:
            st.info("Brak zapisanych sesji. Zaimportuj pierwszy plik CSV.")
        else:
            by_label = {_session_label(session): session for session in sessions}
            labels = list(by_label)
            selected_id = st.session_state.get("inventory_selected_session")
            selected_index = next((index for index, label in enumerate(labels) if by_label[label].get("id") == selected_id), 0)
            selected_label = st.selectbox("Sesja", labels, index=selected_index, key="inventory_session_selector")
            selected = by_label[selected_label]
            st.session_state["inventory_selected_session"] = selected.get("id")
            records = selected.get("records", [])
            summary = selected.get("summary") or session_summary(records)
            metrics = st.columns(5)
            metrics[0].metric("Tacki", summary["trays"])
            metrics[1].metric("SKU", summary["sku"])
            metrics[2].metric("Sztuki", summary["pieces"])
            metrics[3].metric("Różnica", summary["difference"])
            metrics[4].metric("Duplikaty", summary["duplicates"])
            if summary["shortages"] or summary["surpluses"] or summary["unknown_products"]:
                st.warning(f"Braki: {summary['shortages']} · Nadwyżki: {summary['surpluses']} · Nierozpoznane EAN: {summary['unknown_products']}")
            report = _report_frame(records)
            st.dataframe(report, hide_index=True, width="stretch")

            st.markdown("#### Popraw wybrany wpis")
            record_index = st.selectbox(
                "Wpis do edycji",
                options=list(range(len(records))),
                format_func=lambda index: (
                    f"#{index + 1} · {records[index].get('tray_id', 'brak tacki')} · "
                    f"{records[index].get('product_name', 'brak produktu')} · "
                    f"{records[index].get('timestamp', '')}"
                ),
                key=f"inventory_record_editor_{selected.get('id')}",
            )
            record = records[record_index]
            field_key = f"inventory_edit_{selected.get('id')}_{record_index}"
            with st.form(f"{field_key}_form"):
                edit_operator = st.text_input("Operator", value=str(record.get("operator", "")), key=f"{field_key}_operator")
                edit_ean = st.text_input("EAN / GTIN", value=str(record.get("ean", "")), key=f"{field_key}_ean")
                edit_tray = st.text_input("ID tacki / QR", value=str(record.get("tray_id", "")), key=f"{field_key}_tray")
                edit_product = st.text_input("Nazwa produktu", value=str(record.get("product_name", "")), key=f"{field_key}_product")
                quantity_col, nominal_col = st.columns(2)
                with quantity_col:
                    edit_actual = st.number_input("Ilość rzeczywista", min_value=0, step=1, value=int(record.get("actual_quantity", 0) or 0), key=f"{field_key}_actual")
                with nominal_col:
                    edit_nominal = st.number_input("Ilość nominalna", min_value=0, step=1, value=int(record.get("nominal_quantity", 0) or 0), key=f"{field_key}_nominal")
                save_record = st.form_submit_button("Zapisz poprawkę wpisu")
            if save_record:
                if not normalize_tray_id(edit_tray):
                    st.error("ID tacki nie może być puste.")
                elif not edit_product.strip():
                    st.error("Nazwa produktu nie może być pusta.")
                else:
                    updated_records = update_inventory_record(records, record_index, {
                        "operator": edit_operator.strip(), "ean": edit_ean, "tray_id": edit_tray,
                        "product_name": edit_product.strip(), "actual_quantity": edit_actual,
                        "nominal_quantity": edit_nominal,
                    }, products)
                    selected["records"] = updated_records
                    selected["summary"] = session_summary(updated_records)
                    save_json(inventory_file, sessions)
                    st.success("Poprawka została zapisana i raport został przeliczony.")
                    st.rerun()

            csv_bytes = report.to_csv(index=False).encode("utf-8-sig")
            session_bytes = json.dumps(selected, ensure_ascii=False, indent=2).encode("utf-8")
            download_col, xlsx_col, pdf_col, session_col, delete_col = st.columns(5)
            with download_col:
                st.download_button("Pobierz raport CSV", csv_bytes, "raport_inwentaryzacji.csv", "text/csv", key="inventory_csv_report")
            with xlsx_col:
                st.download_button("Pobierz raport XLSX", _xlsx_bytes(report), "raport_inwentaryzacji.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="inventory_xlsx_report")
            with pdf_col:
                st.download_button(
                    "Pobierz raport PDF",
                    build_inventory_report_pdf(selected, deps["font_regular"], deps["font_bold"]),
                    "raport_inwentaryzacji.pdf",
                    "application/pdf",
                    key="inventory_pdf_report",
                )
            with session_col:
                st.download_button(
                    "Zapisz sesję do pliku",
                    session_bytes,
                    f"sesja_inwentaryzacji_{selected.get('id', 'eksport')}.json",
                    "application/json",
                    key="inventory_session_export",
                )
            with delete_col:
                if st.button("Usuń tę sesję", key="inventory_delete_session"):
                    save_json(inventory_file, [session for session in sessions if session.get("id") != selected.get("id")])
                    st.session_state.pop("inventory_selected_session", None)
                    st.rerun()

    with comparison_tab:
        st.subheader("Porównaj inwentaryzację ze stanem magazynowym")
        st.caption("Wczytaj raport inwentaryzacji i plik stanu magazynowego. System porówna sumy ilości po EAN/GTIN i wskaże braki oraz nadwyżki.")
        with st.expander("Otwórz zapisane porównanie JSON"):
            saved_comparison = st.file_uploader("Plik porównania JSON", type=["json"], key="inventory_stock_saved_file")
            if st.button("Otwórz porównanie z pliku", key="inventory_stock_open_file") and saved_comparison:
                try:
                    loaded = json.loads(saved_comparison.getvalue().decode("utf-8-sig"))
                    if not isinstance(loaded.get("records"), list):
                        raise ValueError("Plik nie zawiera listy wyników porównania.")
                    st.session_state["inventory_stock_comparison_result"] = loaded["records"]
                    st.success("Wczytano zapisane porównanie.")
                except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
                    st.error(f"Nie można otworzyć pliku: {error}")
        with st.form("inventory_stock_comparison_upload"):
            inventory_upload = st.file_uploader("Raport inwentaryzacji CSV", type=["csv"], key="inventory_comparison_upload")
            stock_upload = st.file_uploader("Stan magazynowy CSV", type=["csv"], key="stock_comparison_upload")
            st.caption("Stan magazynowy musi mieć kolumny: EAN/GTIN, Nazwa produktu, Ilość rzeczywista.")
            uploaded = st.form_submit_button("Wgraj i pokaż podgląd")
        if uploaded:
            if inventory_upload is None or stock_upload is None:
                st.warning("Wybierz oba pliki CSV.")
            else:
                try:
                    st.session_state["inventory_comparison_records"] = parse_comparison_inventory_csv(inventory_upload.getvalue())
                    st.session_state["stock_comparison_records"] = parse_stock_csv(stock_upload.getvalue())
                    st.session_state.pop("inventory_stock_comparison_result", None)
                except ValueError as error:
                    st.error(str(error))

        uploaded_inventory = st.session_state.get("inventory_comparison_records", [])
        uploaded_stock = st.session_state.get("stock_comparison_records", [])
        if uploaded_inventory and uploaded_stock:
            left_preview, right_preview = st.columns(2)
            with left_preview:
                st.markdown("#### Podgląd raportu inwentaryzacji")
                st.dataframe(_report_frame(uploaded_inventory), hide_index=True, width="stretch")
            with right_preview:
                st.markdown("#### Podgląd stanu magazynowego")
                st.dataframe(_stock_frame(uploaded_stock), hide_index=True, width="stretch")
            if st.button("Porównaj pliki", key="inventory_stock_compare"):
                st.session_state["inventory_stock_comparison_result"] = compare_inventory_to_stock(uploaded_inventory, uploaded_stock)

        comparison = st.session_state.get("inventory_stock_comparison_result", [])
        if comparison:
            st.markdown("#### Raport porównania")
            summary = stock_comparison_summary(comparison)
            metrics = st.columns(4)
            metrics[0].metric("Pozycje", summary["items"])
            metrics[1].metric("Zgodne", summary["matching"])
            metrics[2].metric("Nadwyżki", summary["surpluses"])
            metrics[3].metric("Braki", summary["shortages"])
            statuses = st.multiselect("Pokaż wyniki", ["Zgodne", "Nadwyżka", "Brak"], default=["Zgodne", "Nadwyżka", "Brak"], key="inventory_stock_statuses")
            search = st.text_input("Szukaj EAN lub produktu", key="inventory_stock_search").casefold().strip()
            filtered = [item for item in comparison if item.get("status") in statuses and (not search or search in f"{item.get('ean', '')} {item.get('product_name', '')}".casefold())]
            comparison_report = _comparison_frame(filtered)
            st.dataframe(comparison_report, hide_index=True, width="stretch")
            comparison_file = json.dumps({"created_at": datetime.now().isoformat(timespec="seconds"), "summary": summary, "records": comparison}, ensure_ascii=False, indent=2).encode("utf-8")
            csv_col, xlsx_col, pdf_col, file_col = st.columns(4)
            with csv_col:
                st.download_button("Pobierz raport porównania CSV", comparison_report.to_csv(index=False).encode("utf-8-sig"), "porownanie_inwentaryzacji_magazynu.csv", "text/csv", key="inventory_stock_csv")
            with xlsx_col:
                st.download_button("Pobierz raport porównania XLSX", _xlsx_bytes(comparison_report), "porownanie_inwentaryzacji_magazynu.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="inventory_stock_xlsx")
            with pdf_col:
                st.download_button("Pobierz raport porównania PDF", build_stock_comparison_pdf(comparison, deps["font_regular"], deps["font_bold"]), "porownanie_inwentaryzacji_magazynu.pdf", "application/pdf", key="inventory_stock_pdf")
            with file_col:
                st.download_button("Zapisz porównanie do pliku", comparison_file, "porownanie_inwentaryzacji_magazynu.json", "application/json", key="inventory_stock_file")

    with catalog_tab:
        st.subheader("Katalog produktów do telefonu")
        catalog = pd.DataFrame(mobile_catalog_rows(products))
        if catalog.empty:
            st.info("Kartoteka produktów nie zawiera jeszcze EAN/GTIN.")
        else:
            st.caption(f"Eksport obejmuje {len(catalog)} kodów EAN/GTIN. Telefon może używać go całkowicie offline.")
            st.dataframe(catalog, hide_index=True, width="stretch")
            st.download_button("Pobierz katalog CSV", catalog.to_csv(index=False).encode("utf-8-sig"), "katalog_produktow_mobilny.csv", "text/csv", key="inventory_mobile_catalog")

    with labels_tab:
        st.subheader("Etykiety QR dla tacek")
        st.caption("Kod QR przechowuje wyłącznie trwały identyfikator tacki, np. `TRAY|000145`.")
        left, right = st.columns(2)
        with left:
            start = st.number_input("Pierwszy numer tacki", min_value=1, value=1, step=1, key="inventory_tray_start")
        with right:
            end = st.number_input("Ostatni numer tacki", min_value=int(start), value=max(int(start), 10), step=1, key="inventory_tray_end")
        tray_name = st.text_input("Indywidualna nazwa tacki", placeholder="np. Rolls Biały 12,5 — stanowisko 1")
        product_name = st.text_input("Produkt na tackę", placeholder="np. Rolls Biały 12,5")
        quantity = st.number_input("Ilość na tackę [szt.]", min_value=0, value=0, step=1)
        current_operator = deps.get("current_operator", "")
        operator = st.text_input("Operator", value=str(current_operator() if callable(current_operator) else current_operator))
        status = "do oznaczenia ręcznego"
        zebra_dpi = st.selectbox("Rozdzielczość Zebra", [203, 300], index=0)
        zebra_orientation = st.selectbox("Orientacja Zebra", ["Pionowa", "Pozioma"], index=0)
        if end - start > 499:
            st.warning("Jednorazowo można wygenerować maksymalnie 500 etykiet.")
        else:
            tray_ids = [{"tray_id": f"{number:06d}", "tray_name": tray_name,
                         "product_name": product_name, "actual_quantity": quantity,
                         "operator": operator, "status": status}
                        for number in range(int(start), int(end) + 1)]
            st.download_button(
                "Pobierz etykiety QR PDF",
                build_tray_labels_pdf(tray_ids, deps["font_regular"], deps["font_bold"]),
                f"etykiety_tacek_{int(start):06d}-{int(end):06d}.pdf",
                "application/pdf",
                key="inventory_tray_labels_pdf",
            )
            st.download_button(
                "Pobierz etykiety Zebra ZPL",
                build_tray_labels_zpl(tray_ids, zebra_dpi, zebra_orientation),
                f"etykiety_tacek_{int(start):06d}-{int(end):06d}.zpl",
                "text/plain",
                key="inventory_tray_labels_zpl",
            )
