"""Przyciski operacyjne Centrum zlecenia: kopia, e-mail i usuwanie."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import streamlit as st


def render_order_center_actions(
    order_id: str,
    documents: list[dict[str, Any]],
    *,
    deletable_order_ids: list[str],
    create_copy: Callable[[bool], None],
    prepare_email: Callable[[list[dict[str, Any]], str, str, str], None],
    delete_order: Callable[[str, bool], None],
) -> None:
    """Renderuje operacje, pozostawiając zapis i uprawnienia aplikacji w przekazanych callbackach."""
    copy_col, reprint_col = st.columns(2)
    with copy_col:
        if st.button("📋 Przywołaj całe zlecenie jako kopię", key=f"copy_order_{order_id}"):
            create_copy(False)
    with reprint_col:
        if st.button("🖨️ Utwórz reprint", key=f"reprint_order_{order_id}"):
            create_copy(True)

    with st.expander("📧 Wyślij komplet dokumentów e-mailem", expanded=False):
        document_names = [f"{index + 1}. {item.get('type', 'Dokument')}" for index, item in enumerate(documents)]
        selected_names = st.multiselect(
            "Dokumenty do wysłania", document_names, default=document_names, key=f"email_documents_{order_id}"
        )
        recipient = st.text_input("Odbiorca", key=f"order_center_email_recipient_{order_id}")
        subject = st.text_input("Temat", value=f"Komplet dokumentów - {order_id}", key=f"order_center_email_subject_{order_id}")
        body = st.text_area(
            "Treść",
            value=f"Dzień dobry,\n\nW załączeniu przekazujemy komplet dokumentów dla zlecenia {order_id}.\n\nPozdrawiamy,",
            key=f"order_center_email_body_{order_id}",
        )
        if st.button("➡️ Przekaż do modułu E-mail", key=f"prepare_order_email_{order_id}"):
            chosen = [documents[document_names.index(name)] for name in selected_names]
            prepare_email(chosen, recipient, subject, body)

    with st.expander("🗑️ Usuń zlecenie", expanded=False):
        st.error("Operacja jest nieodwracalna. Usunie dane zlecenia, jego historię i kontekst modułów.")
        with st.form(f"delete_order_form_{order_id}"):
            target_order_id = st.selectbox(
                "Zlecenie do usunięcia", deletable_order_ids,
                index=deletable_order_ids.index(order_id) if order_id in deletable_order_ids else 0,
                key=f"delete_order_target_{order_id}",
            )
            delete_files = st.checkbox(
                "Usuń również pliki PDF i archiwalne", value=True, key=f"delete_order_files_{order_id}",
                help="Odznacz tylko wtedy, gdy chcesz zachować PDF-y na dysku poza Centrum zlecenia.",
            )
            confirmed = st.checkbox(
                "Rozumiem, że tej operacji nie można cofnąć", key=f"confirm_delete_order_{order_id}"
            )
            submitted = st.form_submit_button("🗑️ Usuń zlecenie", type="primary")
        if submitted:
            if not confirmed:
                st.error("Zaznacz potwierdzenie, aby usunąć zlecenie.")
                return
            if not delete_files:
                st.warning("PDF-y pozostaną na dysku, ale nie będą już widoczne w Centrum zlecenia.")
            delete_order(target_order_id, delete_files)
