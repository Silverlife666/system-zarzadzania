"""Widok modułu 12: Centrum zlecenia i koordynacja dokumentów."""
import json
import os
import secrets
from datetime import datetime



def render_order_center_screen(st, deps):
    pd = deps["pd"]
    json = deps["json"]
    os = deps["os"]
    secrets = deps["secrets"]
    datetime = deps["datetime"]
    get_current_order_id = deps["get_current_order_id"]
    load_document_registry = deps["load_document_registry"]
    create_new_order = deps["create_new_order"]
    render_dashboard = deps["render_dashboard"]
    load_order_contexts = deps["load_order_contexts"]
    update_order_lifecycle_status = deps["update_order_lifecycle_status"]
    activate_order_context = deps["activate_order_context"]
    order_requirement_profiles = deps["order_requirement_profiles"]
    order_requirement_labels = deps["order_requirement_labels"]
    save_shared_state = deps["save_shared_state"]
    document_registry_file = deps["document_registry_file"]
    module_label_for_id = deps["module_label_for_id"]
    module_options = deps["module_options"]
    group_for_module_id = deps["group_for_module_id"]
    module_groups = deps["module_groups"]
    get_order_flow_map = deps["get_order_flow_map"]
    get_order_data_quality = deps["get_order_data_quality"]
    build_order_audit_report = deps["build_order_audit_report"]
    get_order_end_to_end_checks = deps["get_order_end_to_end_checks"]
    render_document_statuses = deps["render_document_statuses"]
    render_document_files = deps["render_document_files"]
    store_order_pdf = deps["store_order_pdf"]
    document_files_dir = deps["document_files_dir"]
    document_archive_dir = deps["document_archive_dir"]
    restore_order_pdf_version = deps["restore_order_pdf_version"]
    archive_order_pdf_file = deps["archive_order_pdf_file"]
    delete_order_pdf_file = deps["delete_order_pdf_file"]
    clear_pdf_version_history = deps["clear_pdf_version_history"]
    inspect_pdf_visually = deps["inspect_pdf_visually"]
    is_path_in_directory = deps["is_path_in_directory"]
    generate_short_order_id = deps["generate_short_order_id"]
    create_order_copy_record = deps["create_order_copy_record"]
    copy_order_context = deps["copy_order_context"]
    order_context_file = deps["order_context_file"]
    render_actions = deps["render_actions"]
    delete_order_permanently = deps["delete_order_permanently"]
    st.title("📁 Centrum zlecenia")
    current_id = get_current_order_id()
    registry = load_document_registry()
    if not registry:
        st.info("Rejestr jest pusty. Utwórz pierwsze zlecenie, aby rozpocząć pracę.")
        if st.button("➕ Utwórz pierwsze zlecenie", type="primary", key="create_first_order"):
            new_order_id = create_new_order()
            st.session_state["pending_order_center_selection"] = new_order_id
            st.success(f"Utworzono nowe zlecenie: {new_order_id}.")
            st.rerun()
    if registry:
        selected_id, lifecycle, record = render_dashboard(
            current_id,
            registry,
            create_order=create_new_order,
            load_registry=load_document_registry,
            load_contexts=load_order_contexts,
            update_lifecycle=update_order_lifecycle_status,
            activate_order=activate_order_context,
        )
        registry = load_document_registry()
        order_statuses = ["robocze", "w produkcji", "gotowe do wysyłki", "wysłane", "zamknięte"]
        record.setdefault("order_status", "robocze")
        if record["order_status"] not in order_statuses:
            record["order_status"] = "robocze"
        record.setdefault("order_history", [])

        with st.expander("✏️ Nazwa zlecenia", expanded=not str(record.get("order_name", "")).strip()):
            with st.form(f"order_name_form_{selected_id}"):
                order_name = st.text_input(
                    "Nazwa zlecenia",
                    value=str(record.get("order_name", "")),
                    placeholder="np. Rolls Ritual – druk wrzesień",
                    max_chars=120,
                    key=f"order_name_{selected_id}",
                )
                save_order_name = st.form_submit_button("💾 Zapisz nazwę")
            if save_order_name:
                new_order_name = order_name.strip()
                previous_order_name = str(record.get("order_name", "")).strip()
                if new_order_name != previous_order_name:
                    now = datetime.now().isoformat(timespec="seconds")
                    record["order_name"] = new_order_name
                    record["updated_at"] = now
                    record["order_history"].append({
                        "at": now, "action": "zmieniono nazwę zlecenia",
                        "by": st.session_state.get("user_name", ""),
                        "from": previous_order_name, "to": new_order_name,
                    })
                    registry[selected_id] = record
                    save_shared_state("document_registry", document_registry_file, registry)
                    st.success("Nazwę zlecenia zapisano.")
                    st.rerun()
                st.info("Nazwa zlecenia nie uległa zmianie.")

        with st.expander("⚙️ Wymagana dokumentacja zlecenia", expanded=False):
            current_profile = record.get("order_requirement_profile", "Standard produkcyjny")
            if current_profile not in order_requirement_profiles:
                current_profile = "Własny"
            requirement_profile = st.selectbox(
                "Profil dokumentacji", list(order_requirement_profiles),
                index=list(order_requirement_profiles).index(current_profile),
                key=f"order_requirement_profile_{selected_id}",
            )
            default_requirements = record.get("required_documents") or order_requirement_profiles[requirement_profile]
            required_documents = st.multiselect(
                "Dokumenty wymagane przed wysyłką",
                list(order_requirement_labels),
                default=[key for key in default_requirements if key in order_requirement_labels],
                format_func=lambda key: order_requirement_labels[key],
                key=f"order_required_documents_{selected_id}",
            )
            if st.button("💾 Zapisz checklistę dokumentacji", key=f"save_order_requirements_{selected_id}"):
                record["order_requirement_profile"] = requirement_profile
                record["required_documents"] = required_documents
                record["updated_at"] = datetime.now().isoformat(timespec="seconds")
                record["order_history"].append({
                    "at": record["updated_at"], "action": "zaktualizowano wymaganą dokumentację",
                    "by": st.session_state.get("user_name", ""), "requirements": required_documents,
                })
                registry[selected_id] = record
                save_shared_state("document_registry", document_registry_file, registry)
                st.success("Checklistę zapisano.")
                st.rerun()

        def open_source_module(module_id):
            target_label = module_label_for_id(module_options, module_id)
            if target_label:
                st.session_state["main_module_selector"] = target_label
                st.session_state["sidebar_navigation_group"] = group_for_module_id(
                    module_groups, module_id, st.session_state.get("sidebar_navigation_group", "📋 Zlecenie i dane"),
                )

        # Dane bieżącego zlecenia są pobierane z modułów; przy starszych wpisach
        # wyświetlane jest ostatnie zapisane podsumowanie w rejestrze.
        live_palletization = st.session_state.get("sug_layout_result") or st.session_state.get("pal_calc_result") or {}
        live_packing = st.session_state.get("packing_document", {})
        live_bct = st.session_state.get("bct_last_result", {})
        use_live_data = selected_id == current_id
        saved_summary = record.get("summary", {})
        packing_items = live_packing.get("items", []) if use_live_data else saved_summary.get("products", [])
        product_names = [str(item.get("Produkt", "")).strip() for item in packing_items if str(item.get("Produkt", "")).strip()]
        if use_live_data and live_palletization.get("Produkt"):
            product_names.append(str(live_palletization["Produkt"]))
        product_names = list(dict.fromkeys(product_names))
        pallet_count = (
            len(live_packing.get("pallets", [])) if use_live_data and live_packing.get("pallets")
            else int(live_palletization.get("Liczba palet", saved_summary.get("pallet_count", 0)) or 0)
        )
        cartons_count = sum(float(item.get("Kartony", 0) or 0) for item in packing_items)
        document_types = [str(item.get("type", "")) for item in record.get("documents", [])]
        bct_for_view = live_bct if use_live_data and live_bct else saved_summary.get("bct", {})
        bct_value = float(bct_for_view.get("bct", 0) or 0)
        bct_approval = "zatwierdzony" if lifecycle["bct_approved"] else bct_for_view.get("approval", "brak analizy")
        ppwr_state = "gotowy" if lifecycle["ppwr_ready"] else "brak dokumentu"
        qa_documents = [item for item in record.get("documents", []) if "QA" in str(item.get("type", "")).upper()]
        qa_state = qa_documents[-1].get("status", "wygenerowany") if lifecycle["qa_ready"] else "brak raportu"

        st.markdown("### Przebieg zlecenia")
        process_col, status_col, action_col = st.columns([2, 2, 1])
        with process_col:
            st.select_slider(
                "Etap procesu",
                options=order_statuses,
                value=record["order_status"],
                disabled=True,
            )
        with status_col:
            st.caption("Status jest wyznaczany automatycznie przez komplet dokumentów oraz historię wysyłki.")
            st.write(f"**Aktualnie:** {record['order_status']}")
            st.caption(f"Reguła: {lifecycle['reason']}.")
        with action_col:
            manual_status = st.selectbox(
                "Zmień status", order_statuses,
                index=order_statuses.index(record["order_status"]),
                key=f"manual_order_status_{selected_id}",
            )
            if st.button("💾 Zapisz status", key=f"save_manual_order_status_{selected_id}"):
                if manual_status != record["order_status"]:
                    now = datetime.now().isoformat(timespec="seconds")
                    previous_status = record["order_status"]
                    record["order_status"] = manual_status
                    record["manual_status_override"] = True
                    record["updated_at"] = now
                    record["order_history"].append({
                        "at": now, "action": "ręczna zmiana statusu zlecenia",
                        "by": st.session_state.get("user_name", ""),
                        "from": previous_status, "to": manual_status,
                    })
                    registry[selected_id] = record
                    save_shared_state("document_registry", document_registry_file, registry)
                    st.success(f"Zmieniono status na: {manual_status}.")
                    st.rerun()
            if st.button("🔄 Odśwież status", key=f"refresh_order_process_{selected_id}"):
                record["manual_status_override"] = False
                registry[selected_id] = record
                save_shared_state("document_registry", document_registry_file, registry)
                update_order_lifecycle_status(selected_id)
                st.rerun()
            if record["order_status"] == "wysłane" and st.button("🔒 Zamknij", key=f"close_order_process_{selected_id}"):
                now = datetime.now().isoformat(timespec="seconds")
                record["order_history"].append({"at": now, "action": "zamknięto zlecenie ręcznie", "by": st.session_state.get("user_name", ""), "from": "wysłane", "to": "zamknięte"})
                record["order_status"] = "zamknięte"
                record["updated_at"] = now
                registry[selected_id] = record
                save_shared_state("document_registry", document_registry_file, registry)
                st.rerun()

        gate_cols = st.columns(4)
        gate_cols[0].metric("BCT zatwierdzone", "✅" if lifecycle["bct_approved"] else "⏳")
        gate_cols[1].metric("Raport PPWR", "✅" if lifecycle["ppwr_ready"] else "⏳")
        gate_cols[2].metric("Raport QA", "✅" if lifecycle["qa_ready"] else "⏳")
        gate_cols[3].metric("E-mail wysłany", "✅" if lifecycle["email_sent"] else "—")
        required_document_checks = [
            (order_requirement_labels[key], lifecycle["requirement_checks"].get(key, False))
            for key in lifecycle["requirements"]
        ]
        completed_document_checks = sum(1 for _, is_ready in required_document_checks if is_ready)
        missing_document_checks = [label for label, is_ready in required_document_checks if not is_ready]
        if not required_document_checks:
            st.info("Brak dokumentów wymaganych w wybranym profilu. Dodaj je w checkliście przed użyciem statusu wysyłki.")
        elif missing_document_checks:
            st.warning(
                f"Kompletność dokumentacji: {completed_document_checks}/{len(required_document_checks)}. Brakuje: "
                + ", ".join(missing_document_checks) + "."
            )
        else:
            st.success(f"Kompletność dokumentacji: {completed_document_checks}/{len(required_document_checks)}. Zlecenie może zostać wysłane.")

        summary_cols = st.columns(5)
        summary_cols[0].metric("Produkty", len(product_names), ", ".join(product_names[:2]) or "brak danych")
        summary_cols[1].metric("Palety", pallet_count, f"kartony: {cartons_count:g}")
        summary_cols[2].metric("BCT", f"{bct_value:.1f} kg" if bct_value else "brak", str(bct_approval))
        summary_cols[3].metric("PPWR", ppwr_state)
        summary_cols[4].metric("QA drukarni", qa_state)
        if product_names:
            st.caption("Produkty: " + ", ".join(product_names))

        with st.expander("🗺️ Mapa przepływu danych", expanded=True):
            st.caption("Mapa pokazuje, które dane zostały już zapisane i przekazane pomiędzy modułami dla tego zlecenia.")
            flow_map = get_order_flow_map(selected_id, record)
            st.dataframe(pd.DataFrame(flow_map), hide_index=True, width="stretch")
            st.caption(" → ".join(row["Etap"] for row in flow_map))

        with st.expander("🧹 Jakość danych zlecenia", expanded=True):
            quality_issues = get_order_data_quality(selected_id, record)
            quality_errors = sum(item["Poziom"] == "BŁĄD" for item in quality_issues)
            quality_warnings = sum(item["Poziom"] == "UWAGA" for item in quality_issues)
            quality_cols = st.columns(3)
            quality_cols[0].metric("Błędy blokujące", quality_errors)
            quality_cols[1].metric("Ostrzeżenia", quality_warnings)
            quality_cols[2].metric("Informacje", len(quality_issues) - quality_errors - quality_warnings)
            if quality_issues:
                st.dataframe(pd.DataFrame(quality_issues), hide_index=True, width="stretch")
            else:
                st.success("Nie wykryto braków ani niespójności w zapisanych danych zlecenia.")

        with st.expander("📜 Raport audytowy zlecenia", expanded=False):
            st.caption("Raport zawiera status, wymagania dokumentacyjne, przepływ danych, kontrolę jakości i historię zmian. Nie zmienia danych zlecenia.")
            audit_report = build_order_audit_report(selected_id, record)
            audit_json = json.dumps(audit_report, ensure_ascii=False, indent=2, default=str)
            audit_quality_lines = [
                f"- [{item['Poziom']}] {item['Obszar']}: {item['Problem']} | {item['Zalecenie']}"
                for item in audit_report["data_quality"]
            ] or ["- Brak uwag."]
            audit_text = "\n".join([
                f"RAPORT AUDYTOWY ZLECENIA: {audit_report['order_id']}",
                f"Wygenerowano: {audit_report['generated_at']}",
                f"Status: {audit_report['order_status']} ({audit_report['lifecycle_reason']})",
                "",
                "KONTROLA JAKOŚCI:",
                *audit_quality_lines,
                "",
                "PRZEPŁYW DANYCH:",
                *[f"- {item['Status']} {item['Etap']}: {item['Źródło / wynik']}" for item in audit_report['flow']],
            ])
            report_col1, report_col2 = st.columns(2)
            with report_col1:
                st.download_button(
                    "⬇️ Pobierz raport audytowy JSON", data=audit_json,
                    file_name=f"raport_audytowy_{selected_id}.json", mime="application/json",
                    key=f"download_audit_json_{selected_id}",
                )
            with report_col2:
                st.download_button(
                    "⬇️ Pobierz raport audytowy TXT", data=audit_text.encode("utf-8"),
                    file_name=f"raport_audytowy_{selected_id}.txt", mime="text/plain",
                    key=f"download_audit_txt_{selected_id}",
                )

        with st.expander("🧪 Kontrola scenariuszy końcowych", expanded=False):
            st.caption("Kontrola nie generuje ani nie zmienia dokumentów; pokazuje gotowość danych do czterech podstawowych scenariuszy pracy.")
            st.dataframe(pd.DataFrame(get_order_end_to_end_checks(selected_id, record)), hide_index=True, width="stretch")

        production_summary = saved_summary.get("production", {})
        if production_summary:
            st.markdown("#### Realizacja produkcji z Karty Pracy")
            production_cols = st.columns(5)
            production_cols[0].metric("Zlecenie produkcyjne", production_summary.get("production_order_no", "—"))
            production_cols[1].metric("Plan", production_summary.get("planned", 0))
            production_cols[2].metric("Wykonano", production_summary.get("made", 0))
            production_cols[3].metric("Odpady", production_summary.get("waste", 0))
            production_cols[4].metric("Maszyna / zmiana", f"{production_summary.get('machine', '—')} / {production_summary.get('shift', '—')}")
            if production_summary.get("operator"):
                st.caption(f"Operator: {production_summary['operator']} | Czas planowany: {production_summary.get('planned_time_hours', 0)} h")

        st.markdown("### Szybkie przejście do modułu źródłowego")
        source_modules = [
            ("📐 Paletyzacja", 2, "palet"),
            ("⚖️ BCT kartonu", 8, "BCT"),
            ("📦 Zamówienie / TDS / Karta Pracy", 9, "Zamówienie"),
            ("📊 PPWR i deklaracje", 10, "PPWR"),
            ("✅ QA drukarni", 11, "QA"),
        ]
        source_cols = st.columns(len(source_modules))
        for column, (label, module_id, _) in zip(source_cols, source_modules):
            with column:
                st.button(label, key=f"go_to_source_{selected_id}_{module_id}", on_click=open_source_module, args=(module_id,))

        st.caption(f"Utworzono: {record.get('created_at','-')} | Zaktualizowano: {record.get('updated_at','-')}")
        if record.get("source_order_id"):
            source_types = ", ".join(item.get("type", "Dokument") for item in record.get("source_documents", [])) or "brak"
            st.info(
                f"To jest {'reprint' if record.get('order_header', {}).get('priority') == 'reprint' else 'kopia'} "
                f"zlecenia {record['source_order_id']}. Dokumenty źródłowe: {source_types}. "
                "Dla tego zlecenia wygeneruj własne PDF-y."
            )
        documents = record.get("documents", [])
        for document in documents:
            document.setdefault("status", "wygenerowany")
            document.setdefault("approved_by", "")
            document.setdefault("file_name", "")
            document.setdefault("file_path", "")
            document.setdefault("history", [])
        def save_document_statuses(edited_view):
            for index, row in edited_view.iterrows():
                before = documents[index]
                new_status, new_approver = row["status"], row["approved_by"]
                if before.get("status") != new_status or before.get("approved_by") != new_approver:
                    before.setdefault("history", []).append({"at": datetime.now().isoformat(timespec="seconds"), "action": "aktualizacja statusu", "by": st.session_state.get("user_name", ""), "status": new_status})
                before.update(row.to_dict())
            registry[selected_id]["documents"] = documents
            registry[selected_id]["updated_at"] = datetime.now().isoformat(timespec="seconds")
            save_shared_state("document_registry", document_registry_file, registry)
            st.success("Zapisano statusy i historię dokumentów.")

        render_document_statuses(
            selected_id, documents, save_changes=save_document_statuses
        )
        order_document_directory = os.path.join(document_files_dir, selected_id)
        order_document_directories = [
            order_document_directory,
            os.path.join(document_archive_dir, selected_id),
        ]
        def restore_document_version(document_index, version_path):
            try:
                restore_order_pdf_version(selected_id, document_index, version_path)
                st.success("Przywrócono wcześniejszą wersję jako nową wersję bieżącą.")
                st.rerun()
            except (OSError, ValueError, IndexError) as error:
                st.error(f"Nie udało się przywrócić wersji: {error}")

        def archive_document_file(document_index, file_path):
            try:
                archived_path = archive_order_pdf_file(selected_id, file_path)
                document = documents[document_index]
                document["file_path"] = archived_path
                document["status"] = "zarchiwizowany"
                document.setdefault("history", []).append({
                    "at": datetime.now().isoformat(timespec="seconds"), "action": "przeniesiono plik do archiwum",
                    "by": st.session_state.get("user_name", ""), "status": "zarchiwizowany", "file_path": archived_path,
                })
                registry[selected_id]["documents"] = documents
                registry[selected_id]["updated_at"] = datetime.now().isoformat(timespec="seconds")
                save_shared_state("document_registry", document_registry_file, registry)
                st.success("Plik przeniesiono do archiwum.")
                st.rerun()
            except (OSError, ValueError) as error:
                st.error(f"Nie udało się zarchiwizować pliku: {error}")

        def delete_document_file(document_index, file_path):
            try:
                delete_order_pdf_file(file_path)
                document = documents[document_index]
                document["file_path"] = ""
                document["status"] = "usunięty"
                document.setdefault("history", []).append({
                    "at": datetime.now().isoformat(timespec="seconds"), "action": "usunięto plik PDF",
                    "by": st.session_state.get("user_name", ""), "status": "usunięty", "file_path": file_path,
                })
                registry[selected_id]["documents"] = documents
                registry[selected_id]["updated_at"] = datetime.now().isoformat(timespec="seconds")
                save_shared_state("document_registry", document_registry_file, registry)
                st.success("Plik został usunięty.")
                st.rerun()
            except (OSError, ValueError) as error:
                st.error(f"Nie udało się usunąć pliku: {error}")

        def clear_order_pdf_history():
            try:
                removed_count = clear_pdf_version_history(documents, order_document_directories)
                registry[selected_id]["documents"] = documents
                registry[selected_id]["updated_at"] = datetime.now().isoformat(timespec="seconds")
                save_shared_state("document_registry", document_registry_file, registry)
                st.success(f"Wyczyszczono historię PDF oraz usunięto {removed_count} wcześniejszych plików wersji.")
                st.rerun()
            except OSError as error:
                st.error(f"Nie udało się wyczyścić historii PDF: {error}")

        render_document_files(
            selected_id, documents, order_document_directories,
            inspect_pdf=inspect_pdf_visually,
            restore_version=restore_document_version,
            archive_file=archive_document_file,
            delete_file=delete_document_file,
            clear_pdf_history=clear_order_pdf_history,
            can_archive=lambda path: is_path_in_directory(path, document_files_dir),
            store_uploaded_pdf=lambda document_type, pdf_bytes, file_name: store_order_pdf(
                document_type, pdf_bytes, file_name,
                {"source": "dodano ręcznie po kontroli wizualnej"}, order_id=selected_id,
            ),
        )
        def copy_order_from_center(is_reprint=False):
            """Tworzy nową roboczą kopię albo kolejne wydanie reprintu."""
            new_order_id = generate_short_order_id(datetime.now().strftime("%y%m%d"), registry, secrets.token_hex)
            created_at = datetime.now().isoformat(timespec="seconds")
            copied = create_order_copy_record(
                selected_id, record, new_order_id, created_at,
                st.session_state.get("user_name", ""), is_reprint=is_reprint,
            )
            registry[new_order_id] = copied
            save_shared_state("document_registry", document_registry_file, registry)
            # Kopia dostaje również własną kopię danych roboczych modułów.
            contexts = load_order_contexts()
            if selected_id in contexts:
                contexts = copy_order_context(contexts, selected_id, new_order_id, copied, created_at)
                save_shared_state("order_contexts", order_context_file, contexts)
            activate_order_context(new_order_id)
            st.session_state["pending_order_center_selection"] = new_order_id
            st.session_state["order_copy_source"] = selected_id
            st.success(f"Utworzono {'reprint' if is_reprint else 'kopię'} zlecenia: {new_order_id}.")
            st.rerun()

        def prepare_order_email(chosen, recipient, subject, body):
            st.session_state["email_order_bundle"] = {
                "order_id": selected_id, "recipient": recipient, "subject": subject, "body": body, "documents": chosen,
            }
            record.setdefault("email_history", []).append({
                "at": datetime.now().isoformat(timespec="seconds"), "action": "przygotowano komplet dokumentów do e-maila",
                "by": st.session_state.get("user_name", ""), "recipient": recipient,
                "documents": [item.get("type") for item in chosen],
            })
            registry[selected_id] = record
            save_shared_state("document_registry", document_registry_file, registry)
            st.success("Komplet dokumentów przekazano do modułu E-mail.")

        def delete_order_from_center(order_id_to_delete, delete_files):
            try:
                removed_paths = delete_order_permanently(order_id_to_delete, delete_files=delete_files)
                remaining_orders = load_document_registry()
                # Nie zapisujemy ponownie kontekstu usuniętego zlecenia podczas przełączenia.
                st.session_state.pop("order_id", None)
                st.session_state.pop("_loaded_order_context_id", None)
                if st.session_state.get("email_order_bundle", {}).get("order_id") == order_id_to_delete:
                    st.session_state.pop("email_order_bundle", None)
                if remaining_orders:
                    next_order_id = next(iter(remaining_orders))
                    activate_order_context(next_order_id)
                else:
                    next_order_id = create_new_order()
                st.session_state["pending_order_center_selection"] = next_order_id
                # Po rerunie pozostań w Centrum zlecenia; aktywacja kontekstu
                # nie może wrócić do ostatnio zapamiętanego modułu operacyjnego.
                st.session_state["pending_module_id"] = 12
                files_message = f" Usunięto katalogi plików: {len(removed_paths)}." if delete_files else " Pliki pozostawiono na dysku."
                st.success(f"Usunięto zlecenie {order_id_to_delete}.{files_message}")
                st.rerun()
            except (OSError, ValueError) as error:
                st.error(f"Nie udało się usunąć zlecenia: {error}")

        render_actions(
            selected_id,
            documents,
            deletable_order_ids=list(registry),
            create_copy=copy_order_from_center,
            prepare_email=prepare_order_email,
            delete_order=delete_order_from_center,
        )
