"""Moduł 27: centralny katalog wiernych kopii istniejących backupów."""
from pathlib import Path

from services.backup_center import central_copies, copy_records_to_center, discover_backup_sources


def _table(st, records):
    if records:
        st.dataframe([{"Typ": item["label"], "Plik": item["relative"], "Rozmiar (MB)": round(item["size"] / 1024 / 1024, 2), "Data": item["modified"]} for item in records], width="stretch", hide_index=True)
    else:
        st.info("Brak znalezionych plików w tej kategorii.")


def render_backup_center_screen(st, deps):
    app_root = Path(deps["app_root"])
    st.title("🛡️ Centrum kopii bezpieczeństwa")
    st.caption("Moduł tworzy osobne, wierne kopie istniejących backupów. Nie scala danych i nie zmienia plików źródłowych.")
    records = discover_backup_sources(app_root)
    tabs = st.tabs(["Kopie danych", "Kopie bazy produktów", "Historia / wersje dokumentów", "Paczki aktualizacji"])
    for tab, category in zip(tabs, ("data", "products", "documents", "updates")):
        with tab:
            selected = [item for item in records if item["category"] == category]
            _table(st, selected)
            total = sum(item["size"] for item in selected)
            st.caption(f"Źródła: {len(selected)} plików · {total / 1024 / 1024:.2f} MB")
            confirm = st.checkbox("Rozumiem: zostaną utworzone osobne kopie wskazanych plików.", key=f"backup_center_confirm_{category}")
            if st.button("📋 Utwórz centralne kopie tej kategorii", key=f"backup_center_copy_{category}", disabled=not selected or not confirm, width="stretch"):
                copied, skipped = copy_records_to_center(app_root, selected)
                st.success(f"Utworzono kopie: {copied} · pominięto istniejące lub niedostępne: {skipped}.")
            copies = central_copies(app_root, category)
            if copies:
                with st.expander(f"Centralne kopie ({len(copies)})"):
                    _table(st, copies)
                    for item in copies:
                        st.download_button(f"⬇️ {item['name']}", Path(item["path"]).read_bytes(), item["name"], "application/octet-stream", key=f"backup_center_download_{item['id']}")
