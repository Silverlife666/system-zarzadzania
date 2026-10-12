"""Panel tworzenia i bezpiecznego wdrażania aktualizacji lokalnej aplikacji."""
from __future__ import annotations

import json
from pathlib import Path

from services.update_manager import (
    create_update_package,
    next_incremental_version,
    read_pending_update,
    read_source_state,
    read_version,
    source_token,
    stage_update_package,
    validate_update_package,
)
from services.data_backup_manager import create_data_backup, stage_data_restore, validate_data_backup


def _read_history(app_root: Path) -> list[dict]:
    try:
        value = json.loads((app_root / "dane_aplikacji" / "update_history.json").read_text(encoding="utf-8"))
        return value if isinstance(value, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def render_update_screen(st, deps: dict) -> None:
    app_root = Path(deps["app_root"])
    current = read_version(app_root)
    token = source_token(app_root)
    st.title("🔄 Aktualizacje systemu")
    st.caption("Paczka aktualizacji zawiera wyłącznie kod aplikacji. Dane magazynowe, zamówienia i konfiguracja nie są nadpisywane.")
    left, middle, right = st.columns(3)
    left.metric("Wersja", current["version"])
    middle.metric("Build", current["build_id"])
    right.metric("Token kodu", token)

    tab_create, tab_upload, tab_backup, tab_history = st.tabs(["Utwórz paczkę", "Wgraj aktualizację", "Backup danych", "Historia"])
    with tab_create:
        st.info("Twórz paczkę na komputerze z nowszą wersją, a potem przenieś plik ZIP na drugi komputer.")
        if not read_source_state(app_root):
            st.warning("To pierwszy punkt wersjonowania. Najpierw utwórz paczkę całkowitą 1.00; dopiero potem dostępne będą paczki przyrostowe 1.01, 1.02 itd.")
        package_type_label = st.radio("Typ paczki", ["Całkowita — pełny kod", "Przyrostowa — tylko zmienione pliki"], horizontal=True)
        package_type = "incremental" if package_type_label.startswith("Przyrostowa") else "full"
        if package_type == "full":
            target_version = st.text_input("Wersja pełnej paczki", value=current["version"], key="update_target_version")
            st.caption("Pełną paczkę można wdrożyć niezależnie od wersji na drugim komputerze.")
        else:
            try:
                target_version = next_incremental_version(current["version"])
                st.text_input("Kolejny indeks paczki przyrostowej", value=target_version, disabled=True)
                st.caption(f"Ta paczka będzie działała wyłącznie po wersji {current['version']} z identycznym tokenem kodu.")
            except ValueError as error:
                target_version = ""
                st.error(str(error))
        st.caption("Utworzenie paczki zapisuje jej wersję jako aktualną na tym komputerze i nie nadpisuje istniejących paczek.")
        if st.button("📦 Utwórz paczkę aktualizacji", type="primary", key="create_update_package"):
            if not target_version.strip():
                st.error("Podaj numer wersji.")
            else:
                package, manifest = create_update_package(app_root, app_root / "dane_aplikacji" / "update_packages", target_version, package_type)
                st.session_state["created_update_package"] = str(package)
                st.success(f"Utworzono paczkę {('przyrostową' if package_type == 'incremental' else 'całkowitą')}: {package.name} · token: {manifest['token']}")
        created = st.session_state.get("created_update_package")
        if created and Path(created).is_file():
            st.download_button("⬇️ Pobierz paczkę ZIP", data=Path(created).read_bytes(), file_name=Path(created).name, mime="application/zip")

    with tab_upload:
        pending = read_pending_update(app_root)
        if pending:
            manifest = pending.get("manifest", {})
            st.warning(f"Oczekuje paczka {manifest.get('target_version', '—')} (token {manifest.get('token', '—')}). Zamknij aplikację, następnie uruchom plik Zastosuj_aktualizacje.bat.")
        uploaded = st.file_uploader("Wybierz paczkę aktualizacji ZIP (maks. 500 MB)", type=["zip"], key="update_package_uploader")
        if uploaded:
            temp_path = app_root / "dane_aplikacji" / "pending_updates" / f"check_{Path(uploaded.name).name}"
            temp_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.write_bytes(uploaded.getvalue())
            valid, message, manifest = validate_update_package(temp_path)
            temp_path.unlink(missing_ok=True)
            if valid:
                st.success(message)
                st.write({"typ": "przyrostowa" if manifest.get("package_type") == "incremental" else "całkowita", "wersja": manifest.get("target_version"), "wymaga wersji": manifest.get("base_version") or "dowolnej", "build": manifest.get("build_id"), "token": manifest.get("token"), "liczba plików": len(manifest.get("files", [])), "usuwane pliki": len(manifest.get("deleted_files", []))})
                confirm = st.checkbox("Potwierdzam przygotowanie tej aktualizacji do wdrożenia po zamknięciu aplikacji.", key="stage_update_confirm")
                if st.button("Przygotuj aktualizację", disabled=not confirm, key="stage_update"):
                    ok, staged_message, staged_manifest, _ = stage_update_package(app_root, uploaded.getvalue(), uploaded.name)
                    if ok:
                        st.success(f"{staged_message} Wersja: {staged_manifest.get('target_version')}.")
                        st.rerun()
                    else:
                        st.error(staged_message)
            else:
                st.error(message)

    with tab_backup:
        st.subheader("Pełny backup danych systemu")
        st.caption("Eksport obejmuje bazę danych, zlecenia, dokumenty, szablony, magazyny, ustawienia oraz konta użytkowników. Nie obejmuje kodu aplikacji ani wcześniejszych backupów/paczek aktualizacji.")
        if st.button("🗜️ Utwórz pełny backup ZIP", type="primary", key="create_full_data_backup"):
            package, manifest = create_data_backup(app_root)
            st.session_state["created_data_backup"] = str(package)
            st.success(f"Utworzono backup: {package.name} · {len(manifest['files'])} plików · token {manifest['token']}")
        data_backup = st.session_state.get("created_data_backup")
        if data_backup and Path(data_backup).is_file():
            st.download_button("⬇️ Pobierz backup danych ZIP", Path(data_backup).read_bytes(), file_name=Path(data_backup).name, mime="application/zip")

        st.markdown("### Przywracanie danych")
        st.warning("Przywrócenie nadpisze dane systemu. Przed wykonaniem zostanie automatycznie utworzona kopia obecnego stanu w katalogu backups.")
        source_mode = st.radio("Źródło backupu", ["Wgraj ZIP", "Wskaż lokalną ścieżkę ZIP (bez limitu formularza)"], horizontal=True, key="data_restore_source_mode")
        restore_source = None
        if source_mode == "Wgraj ZIP":
            uploaded_backup = st.file_uploader("Backup danych ZIP (maks. 2 GB)", type=["zip"], key="data_restore_upload")
            if uploaded_backup:
                temporary = app_root / "dane_aplikacji" / "pending_data_restore" / f"check_{Path(uploaded_backup.name).name}"
                temporary.parent.mkdir(parents=True, exist_ok=True)
                temporary.write_bytes(uploaded_backup.getvalue())
                valid, message, manifest = validate_data_backup(temporary)
                temporary.unlink(missing_ok=True)
                if valid:
                    st.success(f"{message} · {len(manifest.get('files', []))} plików")
                    restore_source = (uploaded_backup.name, uploaded_backup.getvalue())
                else:
                    st.error(message)
        else:
            local_path = st.text_input("Pełna ścieżka do ZIP", placeholder=r"np. D:\Backup\backup_danych_20260902.zip", key="data_restore_local_path")
            if local_path.strip():
                candidate = Path(local_path.strip().strip('"'))
                valid, message, manifest = validate_data_backup(candidate) if candidate.is_file() else (False, "Nie znaleziono wskazanego pliku ZIP.", {})
                if valid:
                    st.success(f"{message} · {len(manifest.get('files', []))} plików")
                    restore_source = candidate
                else:
                    st.error(message)
        confirm_restore = st.checkbox("Rozumiem, że przywracanie zastąpi bieżące dane systemu.", key="confirm_data_restore")
        if restore_source and st.button("Przygotuj przywrócenie danych", disabled=not confirm_restore, key="stage_data_restore"):
            if isinstance(restore_source, tuple):
                stage_file = app_root / "dane_aplikacji" / "pending_data_restore" / restore_source[0]
                stage_file.parent.mkdir(parents=True, exist_ok=True)
                stage_file.write_bytes(restore_source[1])
                ok, message, _ = stage_data_restore(app_root, stage_file)
            else:
                ok, message, _ = stage_data_restore(app_root, restore_source)
            if ok:
                st.success(f"{message} Zamknij aplikację i uruchom plik Przywroc_dane.bat.")
            else:
                st.error(message)

    with tab_history:
        history = _read_history(app_root)
        if history:
            st.dataframe(history, use_container_width=True, hide_index=True)
        else:
            st.info("Brak wdrożonych aktualizacji.")
