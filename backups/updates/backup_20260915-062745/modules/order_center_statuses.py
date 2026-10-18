"""Edycja statusów i zatwierdzeń dokumentów w Centrum zlecenia."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pandas as pd
import streamlit as st


def render_order_center_document_statuses(
    order_id: str, documents: list[dict[str, Any]], *, save_changes: Callable[[pd.DataFrame], None]
) -> None:
    """Wyświetla tabelę statusów; trwały zapis jest przekazany do warstwy aplikacji."""
    view = pd.DataFrame([
        {key: item.get(key, "") for key in ["type", "created_at", "status", "approved_by", "file_name", "file_path"]}
        for item in documents
    ])
    st.caption("PPWR, deklaracje i raport QA muszą otrzymać status „zatwierdzony”, aby zlecenie mogło być gotowe do wysyłki.")
    edited_view = st.data_editor(
        view, width="stretch", hide_index=True, key=f"order_center_documents_{order_id}",
        column_config={
            "status": st.column_config.SelectboxColumn(
                "status", options=["robocze", "wygenerowany", "do akceptacji", "zatwierdzony", "wysłany", "anulowany"],
                required=True,
            ),
            "type": st.column_config.TextColumn(disabled=True),
            "created_at": st.column_config.TextColumn(disabled=True),
            "file_name": st.column_config.TextColumn(disabled=True),
            "file_path": st.column_config.TextColumn(disabled=True),
        },
    )
    if st.button("💾 Zapisz statusy i zatwierdzenia", key=f"save_order_document_statuses_{order_id}"):
        save_changes(edited_view)
