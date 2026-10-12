"""Historia, wersje i pliki PDF w Centrum zlecenia."""

from __future__ import annotations

import base64
import os
from collections.abc import Callable
from typing import Any

import pandas as pd
import streamlit as st

from core.document_safety import document_file_is_ready
from services.document_bundle import build_order_documents_zip, order_document_files


def render_order_center_document_files(
    order_id: str,
    documents: list[dict[str, Any]],
    order_directories: list[str],
    *,
    inspect_pdf: Callable[[str], dict[str, Any]],
    restore_version: Callable[[int, str], None],
    archive_file: Callable[[int, str], None],
    delete_file: Callable[[int, str], None],
    clear_pdf_history: Callable[[], None],
    can_archive: Callable[[str], bool],
    store_uploaded_pdf: Callable[[str, bytes, str], None],
) -> None:
    """Renderuje historię i pliki; modyfikacje przekazuje do usług aplikacji."""
    with st.expander("🕓 Historia dokumentów", expanded=False):
        for document in documents:
            st.write(f"**{document.get('type', 'Dokument')}**")
            st.dataframe(pd.DataFrame(document.get("history", [])), hide_index=True, width="stretch")

    with st.expander("↩️ Wersje PDF i przywracanie", expanded=False):
        found_versions = False
        for document_index, document in enumerate(documents):
            previous_versions = [
                event for event in document.get("history", [])
                if document_file_is_ready(event.get("previous_file_path", ""), order_directories)
            ]
            if not previous_versions:
                continue
            found_versions = True
            st.write(f"**{document.get('type', 'Dokument')} — bieżąca wersja v{document.get('version', 1)}**")
            for event in previous_versions:
                version_number = event.get("previous_version", "?")
                version_path = event["previous_file_path"]
                with open(version_path, "rb") as version_file:
                    version_bytes = version_file.read()
                version_col1, version_col2 = st.columns(2)
                with version_col1:
                    st.download_button(
                        f"⬇️ Pobierz wersję v{version_number}", version_bytes,
                        file_name=os.path.basename(version_path), mime="application/pdf",
                        key=f"download_old_pdf_{order_id}_{document_index}_{version_number}_{event.get('at', '')}",
                    )
                with version_col2:
                    if st.button(
                        f"↩️ Przywróć wersję v{version_number}",
                        key=f"restore_old_pdf_{order_id}_{document_index}_{version_number}_{event.get('at', '')}",
                    ):
                        restore_version(document_index, version_path)
        if not found_versions:
            st.info("Nie ma jeszcze wcześniejszych wersji PDF dla tego zlecenia.")

    with st.expander("🧹 Czyszczenie historii i wersji PDF", expanded=False):
        st.warning("Usuwa wcześniejsze wersje PDF i historię wersjonowania. Bieżące pliki PDF pozostają bez zmian.")
        with st.form(f"clear_pdf_history_{order_id}"):
            confirmed = st.checkbox("Potwierdzam czyszczenie historii PDF", key=f"confirm_clear_pdf_history_{order_id}")
            submitted = st.form_submit_button("🧹 Wyczyść historię i wersje PDF", type="primary")
        if submitted:
            if confirmed:
                clear_pdf_history()
            else:
                st.error("Zaznacz potwierdzenie czyszczenia.")

    with st.expander("📥 Pliki dokumentów", expanded=False):
        with st.expander("➕ Dodaj plik po kontroli wizualnej", expanded=False):
            upload_type = st.text_input("Typ dokumentu", placeholder="np. Zamówienie od klienta", key=f"upload_doc_type_{order_id}")
            uploaded_pdf = st.file_uploader("Plik PDF", type=["pdf"], key=f"upload_order_pdf_{order_id}")
            if st.button("➕ Dodaj plik do zlecenia", key=f"save_uploaded_order_pdf_{order_id}"):
                if not upload_type.strip() or uploaded_pdf is None:
                    st.error("Podaj typ dokumentu i wybierz plik PDF.")
                else:
                    store_uploaded_pdf(upload_type.strip(), uploaded_pdf.getvalue(), uploaded_pdf.name)
                    st.success("Dodano plik do zlecenia.")
                    st.rerun()
        files = order_document_files(documents, order_directories)
        files_by_index = {item["index"]: item for item in files}
        zip_bytes = build_order_documents_zip(files)
        if st.button("🧪 Sprawdź wizualnie wszystkie dostępne PDF-y", key=f"inspect_all_order_docs_{order_id}"):
            checked_files = 0
            for index, document in enumerate(documents):
                path = str(document.get("file_path", ""))
                if document_file_is_ready(path, order_directories):
                    st.session_state[f"pdf_review_{order_id}_{index}"] = inspect_pdf(path)
                    checked_files += 1
            if checked_files:
                st.success(f"Wykonano kontrolę wizualną: {checked_files} plików PDF.")
            else:
                st.warning("Brak dostępnych plików PDF do sprawdzenia.")

        for index, document in enumerate(documents):
            path = str(document.get("file_path", ""))
            file_info = files_by_index.get(index)
            exists = file_info is not None
            st.write(f"**{document.get('type', 'Dokument')}** — {'✅ plik dostępny' if exists else '⚠️ brak pliku'}")
            if not exists:
                continue
            file_bytes = file_info["bytes"]
            file_name = file_info["file_name"]
            file_col1, file_col2, file_col3, file_col4 = st.columns([1.3, 1.4, 1.3, 1.4])
            with file_col1:
                st.download_button("⬇️ Pobierz PDF", file_bytes, file_name=file_name, mime="application/pdf", key=f"download_order_doc_{order_id}_{index}")
            with file_col2:
                if st.button("👁️ Kontrola wizualna", key=f"inspect_order_doc_{order_id}_{index}"):
                    st.session_state[f"pdf_review_{order_id}_{index}"] = inspect_pdf(path)
            with file_col3:
                if st.button("🗄️ Archiwizuj plik", key=f"archive_order_file_{order_id}_{index}", disabled=not can_archive(path)):
                    archive_file(index, path)
            with file_col4:
                confirmed_delete = st.checkbox("Potwierdzam usunięcie", key=f"confirm_delete_order_file_{order_id}_{index}")
                if st.button("🗑️ Usuń plik", key=f"delete_order_file_{order_id}_{index}", disabled=not confirmed_delete):
                    delete_file(index, path)

            review = st.session_state.get(f"pdf_review_{order_id}_{index}")
            if review:
                if review.get("ok"):
                    pages_label = f" | stron: {review['pages']}" if review.get("pages") else ""
                    st.success(f"Kontrola wizualna: OK - {review.get('message', '')}{pages_label}")
                    st.image(review["preview"], caption=f"Podgląd pierwszej strony: {file_name}", width="stretch")
                    if st.checkbox("Pokaż pełny PDF w przeglądarce", key=f"embed_order_pdf_{order_id}_{index}"):
                        encoded_pdf = base64.b64encode(file_bytes).decode("ascii")
                        st.components.v1.html(
                            f'<iframe src="data:application/pdf;base64,{encoded_pdf}" width="100%" height="720" style="border: 1px solid #CBD5E1;"></iframe>',
                            height=730,
                        )
                else:
                    st.warning(f"Kontrola wizualna niedostępna: {review.get('message', 'nieznany błąd')}")
        if files:
            st.download_button("🗜️ Pobierz komplet jako ZIP", zip_bytes, file_name=f"{order_id}_dokumenty.zip", mime="application/zip")
