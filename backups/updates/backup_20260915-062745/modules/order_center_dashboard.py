"""Górna część ekranu Centrum zlecenia: dashboard, filtry i wybór zlecenia."""

from __future__ import annotations

import json
from typing import Any, Callable

import pandas as pd
import streamlit as st


def render_order_center_dashboard(
    current_order_id: str,
    registry: dict[str, dict[str, Any]],
    *,
    create_order: Callable[[], str],
    load_registry: Callable[[], dict[str, dict[str, Any]]],
    load_contexts: Callable[[], dict[str, Any]],
    update_lifecycle: Callable[[str], dict[str, Any]],
    activate_order: Callable[[str], None],
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """Wyświetla wspólny nagłówek Centrum i zwraca wybrane zlecenie.

    Funkcje zapisu/przełączania są przekazywane z aplikacji, więc ekran nie ma
    ukrytej zależności od plików danych ani globalnego stanu `app.py`.
    """
    order_header_col, new_order_col = st.columns([4, 1])
    with order_header_col:
        st.info(f"Bieżące zlecenie: {current_order_id}")
    with new_order_col:
        if st.button("➕ Nowe zlecenie", type="primary", key="create_new_order"):
            new_order_id = create_order()
            st.session_state["pending_order_center_selection"] = new_order_id
            st.success(f"Utworzono nowe zlecenie: {new_order_id}.")
            st.rerun()

    dashboard_rows: list[dict[str, Any]] = []
    for order_id, record in registry.items():
        lifecycle = update_lifecycle(order_id)
        header = record.get("order_header", {})
        recipient = header.get("recipient", {})
        recipient = recipient if isinstance(recipient, dict) else {}
        products = record.get("summary", {}).get("products", [])
        product_names = ", ".join(
            str(item.get("Produkt", "")).strip()
            for item in products
            if str(item.get("Produkt", "")).strip()
        )
        dashboard_rows.append({
            "Nazwa zlecenia": str(record.get("order_name", "")).strip() or "—",
            "Numer zlecenia": header.get("order_number") or order_id,
            "Status": lifecycle.get("status", "robocze"),
            "Klient": header.get("client", recipient.get("company", "")),
            "Produkty": product_names or "—",
            "Dokumenty": len(record.get("documents", [])),
            "Aktualizacja": record.get("updated_at", record.get("created_at", "")),
            "order_id": order_id,
        })
    dashboard_statuses = [row["Status"] for row in dashboard_rows]
    with st.expander("📊 Przegląd zleceń", expanded=True):
        metrics = st.columns(5)
        metrics[0].metric("Wszystkie", len(dashboard_rows))
        metrics[1].metric("W produkcji", dashboard_statuses.count("w produkcji"))
        metrics[2].metric("Gotowe do wysyłki", dashboard_statuses.count("gotowe do wysyłki"))
        metrics[3].metric("Wysłane", dashboard_statuses.count("wysłane"))
        metrics[4].metric("Zamknięte", dashboard_statuses.count("zamknięte"))
        st.dataframe(pd.DataFrame(dashboard_rows), hide_index=True, width="stretch")

    st.markdown("### 🔎 Wyszukiwanie i kompletność dokumentacji")
    filter_col1, filter_col2, filter_col3 = st.columns([3, 2, 2])
    with filter_col1:
        query = st.text_input(
            "Szukaj po numerze, SKU, EAN, kliencie, drukarni lub produkcie",
            key="order_center_search_query",
        ).strip().lower()
    with filter_col2:
        status_filter = st.selectbox(
            "Status zlecenia",
            ["Wszystkie", "robocze", "w produkcji", "gotowe do wysyłki", "wysłane", "zamknięte"],
            key="order_center_status_filter",
        )
    with filter_col3:
        awaiting_approval_only = st.checkbox(
            "Tylko oczekujące na akceptację",
            key="order_center_awaiting_approval_filter",
        )

    contexts = load_contexts()
    order_ids: list[str] = []
    for order_id, record in registry.items():
        update_lifecycle(order_id)
        status = str(load_registry().get(order_id, record).get("order_status", "robocze"))
        documents = record.get("documents", [])
        header = record.get("order_header", {})
        awaits_approval = (
            str(header.get("status", "")).lower() == "do akceptacji"
            or any(str(item.get("status", "")).lower() in {"do akceptacji", "wymaga akceptacji"} for item in documents)
        )
        search_blob = json.dumps({"order_id": order_id, "record": record, "context": contexts.get(order_id, {})}, ensure_ascii=False).lower()
        if query and query not in search_blob:
            continue
        if status_filter != "Wszystkie" and status != status_filter:
            continue
        if awaiting_approval_only and not awaits_approval:
            continue
        order_ids.append(order_id)

    registry = load_registry()
    if not order_ids:
        st.warning("Nie znaleziono zleceń spełniających wybrane kryteria.")
        st.stop()
    if st.session_state.get("order_center_selected_id") not in order_ids:
        st.session_state["order_center_selected_id"] = current_order_id if current_order_id in order_ids else order_ids[0]
    pending_selection = st.session_state.pop("pending_order_center_selection", None)
    if pending_selection in order_ids:
        # Wartość pola wyboru wolno zmieniać przed utworzeniem widgetu.
        st.session_state["order_center_selected_id"] = pending_selection
    def order_option_label(order_id: str) -> str:
        selected_record = registry.get(order_id, {})
        order_name = str(selected_record.get("order_name") or "").strip()
        header = selected_record.get("order_header", {}) or {}
        order_number = str(header.get("order_number") or order_id)
        return " — ".join(part for part in [order_name, order_number] if part)

    order_option_labels = {order_id: order_option_label(order_id) for order_id in order_ids}
    selected_id = st.selectbox(
        "Wybierz zlecenie", order_ids, key="order_center_selected_id",
        format_func=lambda order_id: order_option_labels[order_id],
    )
    if selected_id != current_order_id:
        activate_order(selected_id)
        st.rerun()
    lifecycle = update_lifecycle(selected_id)
    registry = load_registry()
    return selected_id, lifecycle, registry[selected_id]
