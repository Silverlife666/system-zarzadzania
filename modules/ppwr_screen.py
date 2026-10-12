"""Widok modułu 10: specyfikacja masy i dokumenty PPWR."""
import json
from datetime import datetime



def render_ppwr_screen(st, deps):
    pd = deps["pd"]
    datetime = deps["datetime"]
    calculate_ppwr_masses = deps["calculate_ppwr_masses"]
    migrate_legacy_order_units = deps["migrate_legacy_order_units"]
    format_ppwr_number = deps["format_ppwr_number"]
    get_current_order_id = deps["get_current_order_id"]
    load_document_registry = deps["load_document_registry"]
    deserialize_order_context_value = deps["deserialize_order_context_value"]
    update_order_snapshot = deps["update_order_snapshot"]
    save_order_context = deps["save_order_context"]
    load_database = deps["load_database"]
    save_database = deps["save_database"]
    generate_ppwr_mass_specification_pdf = deps["generate_ppwr_mass_specification_pdf"]
    generate_eu_declaration_of_conformity_pdf = deps["generate_eu_declaration_of_conformity_pdf"]
    generate_production_date_declaration_pdf = deps["generate_production_date_declaration_pdf"]
    normalize_vat_identifier = deps["normalize_vat_identifier"]
    load_products = deps["load_products"]
    render_packing_diagram = deps["render_packing_diagram"]
    ppwr_deepl_translation_overrides = deps["ppwr_deepl_translation_overrides"]
    ppwr_translation_rows = deps["ppwr_translation_rows"]
    deepl_api_key = deps.get("deepl_api_key", "")
    deepl_translation_error = deps["deepl_translation_error"]
    st.title("📊 Mass Specification PPWR")
    bct_ppwr_view = st.session_state.get("bct_for_ppwr") or st.session_state.get("bct_last_result")
    if bct_ppwr_view:
        st.info(f"BCT: {bct_ppwr_view.get('bct',0):.1f} kg | bezpieczne BCT: {bct_ppwr_view.get('safe_bct',0):.1f} kg | materiał: {bct_ppwr_view.get('material','-')} | fala: {bct_ppwr_view.get('flute','-')} | status: {bct_ppwr_view.get('approval','-')}")
    st.caption("Robocza specyfikacja masy i materiałów opakowaniowych dla produktu B2B.")
    st.info(
        "Wprowadź wszystkie komponenty opakowania: jednostkowe, displayowe, zbiorcze i transportowe. "
        "Moduł przelicza ich masę na 1 SKU, 1 paletę oraz całe zamówienie."
    )

    ppwr_product_scale_keys = (
        "ppwr_product_name", "ppwr_sku", "ppwr_nip", "ppwr_client",
        "ppwr_units_per_display", "ppwr_displays_per_pallet", "ppwr_pallets_per_order",
        "ppwr_units_per_order", "ppwr_displays_per_pallet_values",
    )

    def load_saved_ppwr_product_scale():
        """Wczytuje trwałą migawkę skali wyłącznie dla aktualnego zlecenia."""
        active_order_id = get_current_order_id()
        record = load_document_registry().get(active_order_id, {})
        section = (record.get("shared_snapshot", {}).get("sections", {}) or {}).get("ppwr_product_scale", {})
        saved_values = deserialize_order_context_value(section.get("data", {}))
        if not saved_values:
            st.session_state["ppwr_product_scale_message"] = ("warning", "Brak zapisanego zestawu danych dla bieżącego zlecenia.")
            return
        for key in ppwr_product_scale_keys:
            if key in saved_values:
                st.session_state[key] = saved_values[key]
        for index, value in enumerate(saved_values.get("ppwr_displays_per_pallet_values", []), start=1):
            st.session_state[f"ppwr_displays_per_pallet_{index}"] = value
        st.session_state["ppwr_product_scale_message"] = ("success", "Wczytano zapisane dane produktu i skalę zamówienia.")

    with st.expander("Dane produktu i skala zamówienia", expanded=True):
        meta_col1, meta_col2, meta_col3 = st.columns(3)
        with meta_col1:
            ppwr_product_name = st.text_input("Nazwa produktu / Item", value="Nowy produkt", key="ppwr_product_name")
            ppwr_sku = st.text_input("SKU / EAN", value="", key="ppwr_sku")
            ppwr_nip = st.text_input("NIP / VAT ID wystawcy", value="PL 649221915", key="ppwr_nip")
        with meta_col2:
            ppwr_client = st.text_input("Klient / marka", value="", key="ppwr_client")
            ppwr_units_per_display = st.number_input(
                "Sztuk w displayu", min_value=1, value=16, step=1, key="ppwr_units_per_display"
            )
        with meta_col3:
            ppwr_pallets_per_order = st.number_input(
                "Liczba palet w zamówieniu", min_value=1, value=1, step=1, key="ppwr_pallets_per_order"
            )

    # Każda paleta może mieć inną liczbę displayów, np. ostatnia paleta niepełna.
    previous_display_values = st.session_state.get("ppwr_displays_per_pallet_values", [])
    legacy_display_default = int(st.session_state.get("ppwr_displays_per_pallet", 72))
    ppwr_display_counts = []
    st.markdown("#### Displaye na poszczególnych paletach")
    for start_index in range(0, int(ppwr_pallets_per_order), 4):
        display_columns = st.columns(min(4, int(ppwr_pallets_per_order) - start_index))
        for column_offset, display_column in enumerate(display_columns):
            pallet_index = start_index + column_offset
            default_display_count = int(
                previous_display_values[pallet_index]
                if pallet_index < len(previous_display_values) else legacy_display_default
            )
            with display_column:
                ppwr_display_counts.append(st.number_input(
                    f"Displayów na palecie {pallet_index + 1}", min_value=0, value=default_display_count,
                    step=1, key=f"ppwr_displays_per_pallet_{pallet_index + 1}",
                ))
    st.session_state["ppwr_displays_per_pallet_values"] = [int(value) for value in ppwr_display_counts]
    ppwr_displays_per_pallet = ppwr_display_counts[0]
    total_displays_in_order = sum(ppwr_display_counts)
    units_by_pallet = [int(ppwr_units_per_display * count) for count in ppwr_display_counts]
    units_per_pallet = sum(units_by_pallet) / max(int(ppwr_pallets_per_order), 1)
    suggested_units_per_order = sum(units_by_pallet)
    if len(units_by_pallet) == 1:
        st.caption(f"Automatycznie wyliczono: **{units_by_pallet[0]:,} SKU na palecie**.")
    else:
        st.caption(
            f"Łącznie: **{total_displays_in_order:,} displayów** i **{suggested_units_per_order:,} SKU**. "
            f"Średnio: **{units_per_pallet:,.0f} SKU na paletę**."
        )

    # W starszych zapisach pole SKU mogło zawierać samą liczbę displayów.
    # Korekta jest wykonywana tylko raz dla aktualnego zlecenia, zanim Streamlit
    # utworzy widget; późniejsza ręczna zmiana liczby SKU pozostaje nienaruszona.
    units_migration_key = f"_ppwr_units_per_order_migrated_{get_current_order_id()}"
    stored_units_per_order = st.session_state.get("ppwr_units_per_order")
    corrected_units_per_order, was_corrected = migrate_legacy_order_units(
        stored_units_per_order, total_displays_in_order, ppwr_units_per_display,
    )
    if stored_units_per_order is not None and not st.session_state.get(units_migration_key) and was_corrected:
        st.session_state["ppwr_units_per_order"] = corrected_units_per_order
        st.session_state[units_migration_key] = True
        st.info(
            "Poprawiono historyczną skalę zamówienia: liczba displayów została błędnie "
            f"zapisana jako SKU. Ustawiono **{corrected_units_per_order:,} SKU**."
        )
    ppwr_units_per_order = st.number_input(
        "Liczba SKU w zamówieniu (dokładna)", min_value=1,
        value=suggested_units_per_order, step=1,
        key="ppwr_units_per_order",
        help="Podaj faktyczną liczbę produktów, np. 49 944. Dzięki temu masa całego zamówienia uwzględni niepełną ostatnią paletę.",
    )
    save_scale_col, load_scale_col = st.columns(2)
    with save_scale_col:
        if st.button("💾 Zapisz dane produktu i skalę", type="primary", key="save_ppwr_product_scale"):
            ppwr_product_scale = {
                "ppwr_product_name": ppwr_product_name, "ppwr_sku": ppwr_sku, "ppwr_nip": ppwr_nip,
                "ppwr_client": ppwr_client, "ppwr_units_per_display": ppwr_units_per_display,
                "ppwr_displays_per_pallet": ppwr_displays_per_pallet,
                "ppwr_displays_per_pallet_values": st.session_state["ppwr_displays_per_pallet_values"],
                "ppwr_pallets_per_order": ppwr_pallets_per_order, "ppwr_units_per_order": ppwr_units_per_order,
            }
            active_ppwr_order_id = get_current_order_id()
            update_order_snapshot("ppwr_product_scale", ppwr_product_scale, active_ppwr_order_id)
            save_order_context(active_ppwr_order_id)
            st.success("Dane produktu i skala zamówienia zostały zapisane trwale dla tego zlecenia.")
    with load_scale_col:
        st.button("↩ Wczytaj zapisane dane", key="load_ppwr_product_scale", on_click=load_saved_ppwr_product_scale)
    if ppwr_product_scale_message := st.session_state.pop("ppwr_product_scale_message", None):
        getattr(st, ppwr_product_scale_message[0])(ppwr_product_scale_message[1])

    ppwr_packaging_flag = "Uwzględniać jako opakowanie PPWR"
    ppwr_component_columns = [
        ppwr_packaging_flag,
        "Komponent opakowania", "Poziom opakowania", "Materiał główny", "Surowiec",
        "Masa jednostkowa (g)", "Ilość / 1 SKU", "Ilość / 1 paletę", "Kolor / druk / uwagi",
    ]
    ppwr_database = load_database()
    if "ppwr_components_editor_version" not in st.session_state:
        st.session_state["ppwr_components_editor_version"] = 0

    def ppwr_component_dataframe(records):
        dataframe = pd.DataFrame(records, columns=ppwr_component_columns)
        dataframe[ppwr_packaging_flag] = dataframe[ppwr_packaging_flag].fillna(True).astype(bool)
        return dataframe

    if "ppwr_components" not in st.session_state:
        st.session_state["ppwr_components"] = ppwr_component_dataframe(
            ppwr_database["ppwr_component_library"]
        )
    elif ppwr_packaging_flag not in st.session_state["ppwr_components"].columns:
        # Aktualizacja tabel utworzonych przed dodaniem pola PPWR.
        st.session_state["ppwr_components"][ppwr_packaging_flag] = True
        st.session_state["ppwr_components_editor_version"] += 1

    def ppwr_template_component(name, level, material, raw_material, mass_g, per_sku=0.0, per_pallet=0.0, notes=""):
        return {
            ppwr_packaging_flag: True,
            "Komponent opakowania": name,
            "Poziom opakowania": level,
            "Materiał główny": material,
            "Surowiec": raw_material,
            "Masa jednostkowa (g)": mass_g,
            "Ilość / 1 SKU": per_sku,
            "Ilość / 1 paletę": per_pallet,
            "Kolor / druk / uwagi": notes,
        }

    # Wbudowane szablony są punktem startowym. Masy pozostają edytowalne,
    # ponieważ mogą się różnić pomiędzy dostawami i wariantami produktu.
    standard_ppwr_templates = {
        "Rolls": [
            ppwr_template_component("Papier Rolls", "Sprzedażowe / primary", "Paper", "Paper / cardboard", 0.0, 1.0, notes="Uzupełnij rzeczywistą masę papieru."),
            ppwr_template_component("Filtr Rolls", "Sprzedażowe / primary", "Other", "Other", 0.0, 1.0),
            ppwr_template_component("Box / paper", "Sprzedażowe / primary", "Paper", "Paper / cardboard", 2.13, 1.0, notes="CMYK"),
            ppwr_template_component("Laminacja boxa", "Sprzedażowe / primary", "Plastics", "PP film", 0.30, 1.0, notes="transparent"),
            ppwr_template_component("Pusty display", "Wtórne / secondary", "Paper", "Paper / cardboard", 18.66, per_pallet=0.0, notes="Uzupełnij liczbę displayów na palecie."),
            ppwr_template_component("Master Case Rolls", "Wtórne / secondary", "Paper", "Paper / cardboard", 0.0, per_pallet=1.0),
            ppwr_template_component("Paleta drewniana", "Transportowe / pallet", "Wood", "Wood", 8500.0, per_pallet=1.0),
            ppwr_template_component("Folia stretch", "Transportowe / pallet", "Plastics", "LDPE / other plastic", 700.0, per_pallet=1.0, notes="transparent"),
        ],
        "Bletki": [
            ppwr_template_component("Papier bletkowy", "Sprzedażowe / primary", "Paper", "Paper / cardboard", 0.0, 1.0, notes="Uzupełnij rzeczywistą masę papieru."),
            ppwr_template_component("Gumka / klej do bletek", "Sprzedażowe / primary", "Other", "Other", 0.0, 1.0),
            ppwr_template_component("Booklet / okładka", "Sprzedażowe / primary", "Paper", "Paper / cardboard", 0.0, 1.0, notes="CMYK"),
            ppwr_template_component("Folia flow-pack", "Sprzedażowe / primary", "Plastics", "PP film", 0.0, 1.0, notes="transparent"),
            ppwr_template_component("Pusty display", "Wtórne / secondary", "Paper", "Paper / cardboard", 18.66, per_pallet=0.0, notes="Uzupełnij liczbę displayów na palecie."),
            ppwr_template_component("Master Case Bletki", "Wtórne / secondary", "Paper", "Paper / cardboard", 0.0, per_pallet=1.0),
            ppwr_template_component("Paleta drewniana", "Transportowe / pallet", "Wood", "Wood", 8500.0, per_pallet=1.0),
            ppwr_template_component("Folia stretch", "Transportowe / pallet", "Plastics", "LDPE / other plastic", 700.0, per_pallet=1.0, notes="transparent"),
        ],
    }
    ppwr_templates = ppwr_database.setdefault("ppwr_templates", {})
    templates_seeded = False
    if not ppwr_database.get("ppwr_templates_initialized", False):
        for template_name, components in standard_ppwr_templates.items():
            ppwr_templates[template_name] = {"components": components, "built_in": True}
        ppwr_database["ppwr_templates_initialized"] = True
        templates_seeded = True
    for template_data in ppwr_templates.values():
        for component in template_data.get("components", []):
            for database_key, component_key in (
                ("ppwr_component_names", "Komponent opakowania"),
                ("ppwr_packaging_levels", "Poziom opakowania"),
                ("ppwr_main_materials", "Materiał główny"),
                ("ppwr_raw_materials", "Surowiec"),
                ("ppwr_colour_notes", "Kolor / druk / uwagi"),
            ):
                value = str(component.get(component_key, "") or "").strip()
                if value and value not in ppwr_database[database_key]:
                    ppwr_database[database_key].append(value)
                    templates_seeded = True
    if templates_seeded:
        save_database(ppwr_database)

    st.markdown("### 📚 Szablony składowych PPWR")
    st.caption("Wczytanie szablonu zastępuje roboczą listę składowych dla bieżącego zlecenia. Następnie możesz dowolnie zmienić masy i ilości.")
    template_names = sorted(ppwr_templates, key=str.lower)
    if template_names:
        selected_template_name = st.selectbox("Wybierz szablon", template_names, key="ppwr_selected_template")
        selected_template_components = ppwr_component_dataframe(
            ppwr_templates[selected_template_name].get("components", [])
        )
        with st.expander("👁️ Szybki podgląd wybranego szablonu", expanded=False):
            st.dataframe(
                selected_template_components.reindex(columns=[
                    "Komponent opakowania", "Poziom opakowania", "Materiał główny",
                    "Surowiec", "Masa jednostkowa (g)", "Ilość / 1 SKU", "Ilość / 1 paletę",
                ]),
                width="stretch", hide_index=True,
            )
        template_action_col, template_info_col, template_delete_col = st.columns([1, 2, 1])
        with template_action_col:
            if st.button("📥 Wczytaj szablon", type="primary", key="load_ppwr_template"):
                template_data = ppwr_templates[selected_template_name]
                st.session_state["ppwr_components"] = ppwr_component_dataframe(template_data.get("components", []))
                st.session_state["ppwr_components_editor_version"] += 1
                st.success(f"Wczytano szablon „{selected_template_name}”. Zweryfikuj masy oznaczone jako 0 g.")
                st.rerun()
        with template_info_col:
            component_count = len(ppwr_templates[selected_template_name].get("components", []))
            st.info(f"Szablon zawiera {component_count} składowych. Nie zapisuje zmian w bibliotece komponentów.")
        with template_delete_col:
            confirm_delete_template = st.checkbox("Potwierdzam usunięcie", key=f"confirm_ppwr_template_delete_{selected_template_name}")
            if st.button("🗑️ Usuń szablon", key="delete_ppwr_template", disabled=not confirm_delete_template):
                del ppwr_templates[selected_template_name]
                save_database(ppwr_database)
                st.success(f"Usunięto szablon „{selected_template_name}”.")
                st.rerun()
    else:
        st.info("Brak zapisanych szablonów PPWR.")
        if st.button("↩️ Przywróć szablony Rolls i Bletki", key="restore_default_ppwr_templates"):
            ppwr_templates.update({
                name: {"components": components, "built_in": True}
                for name, components in standard_ppwr_templates.items()
            })
            save_database(ppwr_database)
            st.rerun()

    with st.expander("➕ Zapisz lub zarządzaj własnymi szablonami", expanded=False):
        with st.form("save_ppwr_template_form"):
            template_name_to_save = st.text_input("Nazwa własnego szablonu", placeholder="np. Rolls Slim Pink")
            save_template_submitted = st.form_submit_button("💾 Zapisz aktualne składowe jako szablon")
        if save_template_submitted:
            clean_name = template_name_to_save.strip()
            if not clean_name:
                st.warning("Wpisz nazwę szablonu.")
            else:
                template_records = st.session_state["ppwr_components"][ppwr_component_columns].fillna("").to_dict(orient="records")
                ppwr_templates[clean_name] = {"components": template_records, "built_in": False}
                save_database(ppwr_database)
                st.success(f"Zapisano szablon „{clean_name}” z {len(template_records)} składowymi.")
                st.rerun()
        st.caption("Usunięcie wybranego szablonu jest dostępne obok jego wyboru. W razie potrzeby możesz później przywrócić standardowe Rolls i Bletki.")

    ppwr_dictionary_labels = {
        "ppwr_component_names": "Komponent opakowania",
        "ppwr_packaging_levels": "Poziom opakowania",
        "ppwr_main_materials": "Materiał główny",
        "ppwr_raw_materials": "Surowiec",
        "ppwr_colour_notes": "Kolor / druk / uwagi",
    }
    ppwr_column_config = {
        ppwr_packaging_flag: st.column_config.CheckboxColumn(
            "Liczyć jako opakowanie PPWR", default=True,
            help="Odznacz element, który nie jest opakowaniem. Nie wejdzie do obliczeń, podsumowań ani raportu PDF."
        ),
        "Komponent opakowania": st.column_config.SelectboxColumn(
            "Komponent opakowania", options=ppwr_database["ppwr_component_names"], required=True
        ),
        "Poziom opakowania": st.column_config.SelectboxColumn(
            "Poziom opakowania", options=ppwr_database["ppwr_packaging_levels"], required=True
        ),
        "Materiał główny": st.column_config.SelectboxColumn(
            "Materiał główny", options=ppwr_database["ppwr_main_materials"], required=True
        ),
        "Surowiec": st.column_config.SelectboxColumn(
            "Surowiec", options=ppwr_database["ppwr_raw_materials"], required=True
        ),
        "Kolor / druk / uwagi": st.column_config.SelectboxColumn(
            "Kolor / druk / uwagi", options=ppwr_database["ppwr_colour_notes"]
        ),
        "Masa jednostkowa (g)": st.column_config.NumberColumn(min_value=0.0, step=0.01, format="%.2f g"),
        "Ilość / 1 SKU": st.column_config.NumberColumn(min_value=0.0, step=1.0, format="%.2f"),
        "Ilość / 1 paletę": st.column_config.NumberColumn(min_value=0.0, step=1.0, format="%.2f"),
    }

    with st.expander("📚 Baza komponentów opakowań PPWR", expanded=False):
        st.caption(
            "Trwała baza zapisuje wszystkie parametry komponentu. Edytuj ją, dodawaj wiersze "
            "i wybieraj komponenty do aktualnej specyfikacji."
        )
        with st.expander("⚙️ Zarządzanie listami wyboru", expanded=False):
            selected_ppwr_dictionary = st.selectbox(
                "Wybierz listę do edycji",
                options=list(ppwr_dictionary_labels),
                format_func=lambda key: ppwr_dictionary_labels[key],
                key="ppwr_selected_dictionary",
            )
            new_ppwr_option_col, add_ppwr_option_col = st.columns([4, 1])
            with new_ppwr_option_col:
                new_ppwr_option = st.text_input(
                    "Nowa pozycja", key=f"ppwr_new_option_{selected_ppwr_dictionary}"
                )
            with add_ppwr_option_col:
                st.write("")
                if st.button("➕ Dodaj", key=f"ppwr_add_option_{selected_ppwr_dictionary}"):
                    new_ppwr_option = new_ppwr_option.strip()
                    if new_ppwr_option and new_ppwr_option not in ppwr_database[selected_ppwr_dictionary]:
                        ppwr_database[selected_ppwr_dictionary].append(new_ppwr_option)
                        save_database(ppwr_database)
                        st.rerun()
                    if not new_ppwr_option:
                        st.warning("Wpisz wartość do dodania.")
            for option_index, option_value in enumerate(ppwr_database[selected_ppwr_dictionary]):
                option_text_col, option_remove_col = st.columns([5, 1])
                with option_text_col:
                    st.write(f"• {option_value}")
                with option_remove_col:
                    if st.button("🗑️ Usuń", key=f"ppwr_remove_option_{selected_ppwr_dictionary}_{option_index}"):
                        ppwr_database[selected_ppwr_dictionary].pop(option_index)
                        save_database(ppwr_database)
                        st.rerun()
        library_editor_data = ppwr_component_dataframe(ppwr_database["ppwr_component_library"])
        library_editor_data.insert(0, "Dodaj do specyfikacji", False)
        edited_library = st.data_editor(
            library_editor_data,
            num_rows="dynamic",
            width="stretch",
            hide_index=True,
            # Klucz wersjonowany: poprzedni był błędnie utrwalany jako kontekst zlecenia.
            key="ppwr_component_library_editor_v2",
            column_config={
                "Dodaj do specyfikacji": st.column_config.CheckboxColumn(
                    "Dodaj do specyfikacji", default=False
                ),
                **ppwr_column_config,
            },
        )
        library_actions_left, library_actions_right = st.columns(2)
        with library_actions_left:
            if st.button("💾 Zapisz bazę komponentów", key="ppwr_save_component_library"):
                library_to_save = edited_library[ppwr_component_columns].copy()
                library_to_save[ppwr_packaging_flag] = library_to_save[ppwr_packaging_flag].fillna(True).astype(bool)
                library_to_save = library_to_save.fillna("")
                ppwr_database["ppwr_component_library"] = library_to_save.to_dict(orient="records")
                save_database(ppwr_database)
                st.success("Baza komponentów PPWR została zapisana.")
                st.rerun()
        with library_actions_right:
            if st.button("➕ Dodaj zaznaczone do specyfikacji", key="ppwr_add_library_components"):
                selected_components = edited_library.loc[
                    edited_library["Dodaj do specyfikacji"] == True, ppwr_component_columns
                ]
                if selected_components.empty:
                    st.warning("Zaznacz co najmniej jeden komponent w pierwszej kolumnie.")
                else:
                    st.session_state["ppwr_components"] = pd.concat(
                        [st.session_state["ppwr_components"], selected_components], ignore_index=True
                    )
                    st.session_state["ppwr_components_editor_version"] += 1
                    st.success(f"Dodano do specyfikacji: {len(selected_components)} komponent(y).")
                    st.rerun()

    st.markdown("### Komponenty opakowania")
    st.caption(
        "Dodawaj gotowe pozycje z bazy — wpisujesz tylko ilość w odpowiednim miejscu. "
        "Pełna edycja tabeli pozostaje dostępna niżej."
    )

    def ppwr_component_group(component):
        """Ustala, w którym miejscu użytkownik podaje ilość komponentu."""
        description = " ".join(
            str(component.get(field, ""))
            for field in ("Komponent opakowania", "Poziom opakowania")
        ).lower()
        if any(token in description for token in ("jednostk", "primary", "sprzedaż")):
            return "Na 1 SKU"
        if any(token in description for token in ("display", "zbiorcz", "wtórn", "secondary")):
            return "Na 1 paletę (display / karton zbiorczy)"
        return "Na 1 paletę (transport)"

    component_library = ppwr_component_dataframe(ppwr_database["ppwr_component_library"])
    quick_add_labels = {
        "Na 1 SKU": "Opakowanie jednostkowe — np. okładka, etykieta, worek",
        "Na 1 paletę (display / karton zbiorczy)": "Display / karton zbiorczy",
        "Na 1 paletę (transport)": "Transport — np. paleta, folia, taśma",
    }
    with st.container(border=True):
        st.markdown("#### Szybkie dodawanie")
        selected_quick_group = st.segmented_control(
            "Rodzaj komponentu",
            options=list(quick_add_labels),
            format_func=lambda group: quick_add_labels[group],
            default="Na 1 SKU",
            key="ppwr_quick_component_group",
        )
        quick_candidates = component_library.loc[
            component_library.apply(ppwr_component_group, axis=1) == selected_quick_group
        ].reset_index(drop=True)

        if quick_candidates.empty:
            st.info("W bazie nie ma jeszcze komponentu tego rodzaju. Dodaj go w sekcji „Baza komponentów opakowań PPWR”.")
        else:
            quick_names = [
                f"{row['Komponent opakowania']} · {row['Materiał główny']} · {row['Masa jednostkowa (g)']} g"
                for _, row in quick_candidates.iterrows()
            ]
            quick_index = st.selectbox(
                "Komponent z bazy", options=range(len(quick_candidates)),
                format_func=lambda index: quick_names[index], key=f"ppwr_quick_component_{selected_quick_group}",
            )
            quick_component = quick_candidates.iloc[int(quick_index)].to_dict()
            is_unit_component = selected_quick_group == "Na 1 SKU"
            configured_quantity = pd.to_numeric(
                quick_component["Ilość / 1 SKU"] if is_unit_component else quick_component["Ilość / 1 paletę"],
                errors="coerce",
            )
            default_quantity = float(configured_quantity) if pd.notna(configured_quantity) else 0.0
            if default_quantity <= 0:
                default_quantity = 1.0
            quantity_label = "Ile sztuk na 1 SKU" if is_unit_component else "Ile sztuk na 1 paletę"
            quantity_help = (
                "Dla elementu jednostkowego zwykle wpisz 1."
                if is_unit_component
                else "Dla displayu wpisz liczbę displayów na palecie; dla palety, folii lub taśmy zwykle 1."
            )
            add_quantity_col, add_action_col = st.columns([3, 1])
            with add_quantity_col:
                quick_quantity = st.number_input(
                    quantity_label, min_value=0.0, value=default_quantity, step=1.0,
                    help=quantity_help, key=f"ppwr_quick_quantity_{selected_quick_group}_{quick_index}",
                )
            with add_action_col:
                st.write("")
                if st.button("➕ Dodaj komponent", key=f"ppwr_quick_add_{selected_quick_group}_{quick_index}"):
                    component_to_add = quick_component.copy()
                    component_to_add["Ilość / 1 SKU"] = quick_quantity if is_unit_component else 0.0
                    component_to_add["Ilość / 1 paletę"] = 0.0 if is_unit_component else quick_quantity
                    st.session_state["ppwr_components"] = pd.concat(
                        [st.session_state["ppwr_components"], pd.DataFrame([component_to_add])],
                        ignore_index=True,
                    )
                    st.session_state["ppwr_components_editor_version"] += 1
                    st.rerun()

    with st.expander("🛡️ Kalkulator materiałów zabezpieczających", expanded=False):
        st.caption("Oblicz stretch, taśmę/pasek lub elementy sztukowe. Wynik możesz dodać bezpośrednio jako komponent transportowy PPWR.")
        security_type = st.radio(
            "Metoda obliczenia", ["Powierzchnia (stretch / folia)", "Długość (pasek / taśma)", "Sztuki (narożniki / zapinki)"],
            horizontal=True, key="ppwr_security_type",
        )
        security_name = st.text_input("Nazwa materiału", value="Folia stretch", key="ppwr_security_name")
        material_col, raw_col, count_col = st.columns(3)
        with material_col:
            security_material = st.selectbox("Materiał główny", ppwr_database["ppwr_main_materials"], index=ppwr_database["ppwr_main_materials"].index("Plastics") if "Plastics" in ppwr_database["ppwr_main_materials"] else 0, key="ppwr_security_material")
        with raw_col:
            security_raw = st.selectbox("Surowiec", ppwr_database["ppwr_raw_materials"], index=ppwr_database["ppwr_raw_materials"].index("LDPE / other plastic") if "LDPE / other plastic" in ppwr_database["ppwr_raw_materials"] else 0, key="ppwr_security_raw")
        with count_col:
            security_uses = st.number_input("Liczba użyć na 1 paletę", min_value=0.0, value=1.0, step=1.0, key="ppwr_security_uses")

        security_mass_g = 0.0
        calculation_note = ""
        if security_type.startswith("Powierzchnia"):
            ref_col1, ref_col2, ref_col3 = st.columns(3)
            with ref_col1:
                reference_width = st.number_input("Szerokość próbki [m]", min_value=0.001, value=1.0, step=0.01, key="ppwr_stretch_ref_width")
                used_width = st.number_input("Szerokość zużytego kawałka [m]", min_value=0.001, value=1.0, step=0.01, key="ppwr_stretch_used_width")
            with ref_col2:
                reference_length = st.number_input("Długość próbki [m]", min_value=0.001, value=1.0, step=0.01, key="ppwr_stretch_ref_length")
                used_length = st.number_input("Długość zużytego kawałka [m]", min_value=0.001, value=1.0, step=0.01, key="ppwr_stretch_used_length")
            with ref_col3:
                reference_mass = st.number_input("Masa próbki [g]", min_value=0.0, value=3.0, step=0.01, key="ppwr_stretch_ref_mass")
            security_mass_g = reference_mass * (used_width * used_length) / (reference_width * reference_length)
            calculation_note = f"{used_width:g} m × {used_length:g} m; wzorzec {reference_width:g} m × {reference_length:g} m = {reference_mass:g} g"
        elif security_type.startswith("Długość"):
            ref_col1, ref_col2, ref_col3 = st.columns(3)
            with ref_col1:
                reference_length = st.number_input("Długość próbki [cm]", min_value=0.001, value=10.0, step=0.1, key="ppwr_strip_ref_length")
            with ref_col2:
                reference_mass = st.number_input("Masa próbki [g]", min_value=0.0, value=0.1, step=0.01, key="ppwr_strip_ref_mass")
            with ref_col3:
                used_length = st.number_input("Długość jednego użycia [cm]", min_value=0.001, value=200.0, step=1.0, key="ppwr_strip_used_length")
            security_mass_g = reference_mass * used_length / reference_length
            calculation_note = f"{used_length:g} cm; wzorzec {reference_length:g} cm = {reference_mass:g} g"
        else:
            unit_col, label_col = st.columns(2)
            with unit_col:
                security_mass_g = st.number_input("Masa jednego elementu [g]", min_value=0.0, value=1.0, step=0.01, key="ppwr_piece_mass")
            with label_col:
                st.caption("Przykłady: narożnik, zapinka, worek, przekładka lub etykieta.")
            calculation_note = "Masa podana ręcznie dla jednej sztuki."

        total_per_pallet = security_mass_g * security_uses
        result_col, add_col = st.columns([3, 1])
        with result_col:
            st.success(f"Wynik: **{security_mass_g:.3f} g / użycie** · **{total_per_pallet:.3f} g / 1 paletę**")
            st.caption(calculation_note)
        with add_col:
            st.write("")
            if st.button("➕ Dodaj do PPWR", type="primary", key="ppwr_add_security_material"):
                clean_name = security_name.strip()
                if not clean_name:
                    st.warning("Podaj nazwę materiału.")
                else:
                    if clean_name not in ppwr_database["ppwr_component_names"]:
                        ppwr_database["ppwr_component_names"].append(clean_name)
                        save_database(ppwr_database)
                    component_to_add = ppwr_template_component(
                        clean_name, "Transportowe / pallet", security_material, security_raw,
                        float(security_mass_g), per_pallet=float(security_uses), notes=f"Kalkulator zabezpieczeń: {calculation_note}",
                    )
                    st.session_state["ppwr_components"] = pd.concat(
                        [st.session_state["ppwr_components"], pd.DataFrame([component_to_add])], ignore_index=True,
                    )
                    active_order_id = get_current_order_id()
                    snapshot_records = st.session_state.get("ppwr_security_materials", [])
                    snapshot_records.append({"name": clean_name, "mass_g": float(security_mass_g), "uses_per_pallet": float(security_uses), "total_per_pallet_g": float(total_per_pallet), "calculation": calculation_note})
                    st.session_state["ppwr_security_materials"] = snapshot_records
                    update_order_snapshot("ppwr_security_materials", snapshot_records, active_order_id)
                    save_order_context(active_order_id)
                    st.session_state["ppwr_components_editor_version"] += 1
                    st.success(f"Dodano „{clean_name}” do składowych PPWR.")
                    st.rerun()

    with st.expander("✏️ Edytuj wszystkie składowe ręcznie", expanded=False):
        st.caption(
            "Tu możesz poprawić masę, materiał, ilości albo usunąć wiersz. "
            "Dla displayu i kartonu zbiorczego używaj pola „Ilość / 1 paletę”; "
            "dla elementu jednostkowego — „Ilość / 1 SKU”."
        )
        edited_components = st.data_editor(
            st.session_state["ppwr_components"],
            num_rows="dynamic",
            width="stretch",
            hide_index=True,
            key=f"ppwr_components_editor_{st.session_state['ppwr_components_editor_version']}",
            column_config=ppwr_column_config,
        )

    # Edytor jest zwinięty dla wygody, ale jego bieżąca zawartość nadal zasila obliczenia.
    if "edited_components" not in locals():
        edited_components = st.session_state["ppwr_components"].copy()
    if not edited_components.equals(st.session_state["ppwr_components"]):
        # Zmiany ręczne pozostają w roboczej specyfikacji także po dodaniu kolejnego komponentu.
        st.session_state["ppwr_components"] = edited_components.copy()

    ppwr_calculation = calculate_ppwr_masses(
        edited_components.to_dict(orient="records"), units_per_pallet, ppwr_pallets_per_order,
        ppwr_packaging_flag, units_per_order=ppwr_units_per_order,
    )
    if redundant_pallet_quantities := ppwr_calculation["redundant_pallet_quantities"]:
        st.warning(
            "Usunięto podwójne liczenie w obliczeniu PPWR dla: "
            f"**{', '.join(redundant_pallet_quantities)}**. Ilość „/ paletę” odpowiadała już "
            "ilości „/ SKU”; w raporcie została pominięta. Dwa różne komponenty dodaj jako dwa wiersze."
        )
    calculated_components = pd.DataFrame(
        ppwr_calculation["components"],
        columns=ppwr_component_columns + ["Masa / 1 SKU (g)", "Masa / 1 paletę (kg)", "Masa / zamówienie (kg)"],
    )
    excluded_components_count = ppwr_calculation["excluded_components_count"]
    excluded_components = [
        row for row in ppwr_calculation["all_components"]
        if not bool(row.get(ppwr_packaging_flag, True))
    ]
    if excluded_components_count:
        st.info(
            f"Poza obliczeniami i raportem PPWR pozostaje: {excluded_components_count} element(y) "
            "oznaczone jako niebędące opakowaniem."
        )

    total_sku_g = ppwr_calculation["total_sku_g"]
    total_pallet_kg = ppwr_calculation["total_pallet_kg"]
    total_order_kg = ppwr_calculation["total_order_kg"]

    st.markdown("### Podsumowanie masy")
    summary_col1, summary_col2, summary_col3 = st.columns(3)
    summary_col1.metric("1 SKU", f"{format_ppwr_number(total_sku_g)} g")
    summary_col2.metric("1 paleta", f"{format_ppwr_number(total_pallet_kg)} kg")
    summary_col3.metric("Całe zamówienie", f"{format_ppwr_number(total_order_kg)} kg")

    component_view = calculated_components[
        [
            "Komponent opakowania",
            "Poziom opakowania",
            "Materiał główny",
            "Masa / 1 SKU (g)",
            "Masa / 1 paletę (kg)",
            "Masa / zamówienie (kg)",
        ]
    ].copy()
    component_view.insert(0, "Nr", range(1, len(component_view) + 1))
    for column in ["Masa / 1 SKU (g)", "Masa / 1 paletę (kg)", "Masa / zamówienie (kg)"]:
        component_view[column] = component_view[column].round(3)

    st.markdown("### Tabela obliczeniowa")
    if len(edited_components) > 1:
        reorder_options = [
            f"{index + 1}. {row.get('Komponent opakowania', 'Bez nazwy')}"
            for index, (_, row) in enumerate(edited_components.iterrows())
        ]
        reorder_select_col, reorder_up_col, reorder_down_col = st.columns([4, 1, 1])
        with reorder_select_col:
            selected_reorder_label = st.selectbox(
                "Zmień kolejność pozycji", reorder_options, key="ppwr_reorder_component",
                help="Numeracja w tabeli i na schemacie odpowiada tej kolejności.",
            )
        selected_reorder_index = reorder_options.index(selected_reorder_label)
        with reorder_up_col:
            st.write("")
            move_up = st.button("↑ Góra", key="ppwr_move_component_up", disabled=selected_reorder_index == 0)
        with reorder_down_col:
            st.write("")
            move_down = st.button("↓ Dół", key="ppwr_move_component_down", disabled=selected_reorder_index == len(reorder_options) - 1)
        if move_up or move_down:
            swap_index = selected_reorder_index - 1 if move_up else selected_reorder_index + 1
            order = list(range(len(edited_components)))
            order[selected_reorder_index], order[swap_index] = order[swap_index], order[selected_reorder_index]
            st.session_state["ppwr_components"] = edited_components.iloc[order].reset_index(drop=True)
            st.session_state["ppwr_components_editor_version"] += 1
            st.rerun()
    st.dataframe(component_view, width="stretch", hide_index=True)

    st.markdown("### Towary i przesyłki wyłączone z obliczeń PPWR")
    st.caption(
        "Pozycje odznaczone w kolumnie „Liczyć jako opakowanie PPWR”. Nie wpływają na masy ani podział materiałów."
    )
    if excluded_components:
        excluded_view = pd.DataFrame(excluded_components)
        excluded_view.insert(0, "Nr", range(1, len(excluded_view) + 1))
        excluded_view["Powód wyłączenia"] = "Nie jest opakowaniem PPWR"
        excluded_columns = [
            "Nr", "Komponent opakowania", "Poziom opakowania", "Materiał główny",
            "Surowiec", "Powód wyłączenia",
        ]
        st.dataframe(
            excluded_view.reindex(columns=excluded_columns, fill_value="-"),
            width="stretch", hide_index=True,
        )
    else:
        st.caption("Brak towarów lub przesyłek wyłączonych z bieżących obliczeń PPWR.")

    st.markdown("### Schemat komponentów do raportu (opcjonalnie)")
    st.caption("Dodaj PNG lub JPG z oznaczeniami 1, 2, 3… zgodnymi z kolejnością tabeli. Obraz trafi na ostatnią stronę PDF.")
    st.session_state.setdefault("ppwr_appendix_uploader_version", 0)
    uploaded_ppwr_appendix = st.file_uploader(
        "Obraz objaśniający komponenty", type=["png", "jpg", "jpeg"],
        key=f"ppwr_appendix_uploader_{st.session_state['ppwr_appendix_uploader_version']}",
    )
    if uploaded_ppwr_appendix is not None:
        st.session_state["ppwr_appendix_image"] = uploaded_ppwr_appendix.getvalue()
        st.session_state["ppwr_appendix_image_name"] = uploaded_ppwr_appendix.name
    ppwr_appendix_image = st.session_state.get("ppwr_appendix_image")
    if ppwr_appendix_image:
        st.caption(f"Dołączony obraz: {st.session_state.get('ppwr_appendix_image_name', 'schemat')}")
        st.image(ppwr_appendix_image, caption="Podgląd strony końcowej raportu")
        if st.button("🗑️ Usuń obraz z raportu", key="remove_ppwr_appendix_image"):
            st.session_state.pop("ppwr_appendix_image", None)
            st.session_state.pop("ppwr_appendix_image_name", None)
            st.session_state["ppwr_appendix_uploader_version"] += 1
            saved_calculation = st.session_state.get("ppwr_saved_calculation")
            if isinstance(saved_calculation, dict):
                saved_calculation["appendix_image"] = None
                saved_calculation["appendix_image_name"] = ""
            active_ppwr_order_id = get_current_order_id()
            update_order_snapshot("ppwr", saved_calculation or {"appendix_image": None}, active_ppwr_order_id)
            save_order_context(active_ppwr_order_id)
            st.success("Obraz usunięto z bieżącego raportu PPWR.")
            st.rerun()

    if st.button("💾 Zapisz składowe", type="primary", key="save_ppwr_components"):
        active_ppwr_order_id = get_current_order_id()
        # Zapis dotyczy wyłącznie bieżącego zlecenia; nie nadpisuje wspólnej biblioteki PPWR.
        st.session_state["ppwr_components"] = edited_components.copy()
        ppwr_saved_data = {
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "components": edited_components.to_dict(orient="records"),
            "calculation_table": component_view.to_dict(orient="records"),
            "appendix_image": ppwr_appendix_image,
            "appendix_image_name": st.session_state.get("ppwr_appendix_image_name", ""),
            "totals": {
                "total_sku_g": total_sku_g,
                "total_pallet_kg": total_pallet_kg,
                "total_order_kg": total_order_kg,
            },
        }
        st.session_state["ppwr_saved_calculation"] = ppwr_saved_data
        update_order_snapshot("ppwr", ppwr_saved_data, active_ppwr_order_id)
        save_order_context(active_ppwr_order_id)
        st.success("Komponenty opakowania i tabela obliczeniowa zostały zapisane dla bieżącego zlecenia.")

    material_summary = pd.DataFrame(
        ppwr_calculation["material_summary"],
        columns=["Materiał główny", "Masa / 1 SKU (g)", "Udział / 1 SKU (%)", "Masa / 1 paletę (kg)", "Udział / 1 paleta (%)", "Masa / zamówienie (kg)", "Udział / zamówienie (%)"],
    ).round(3)

    st.markdown("### Podział masy według materiałów")
    st.dataframe(material_summary, width="stretch", hide_index=True)
    st.bar_chart(material_summary.set_index("Materiał główny")["Masa / 1 SKU (g)"])

    translation_state_key = f"ppwr_translation_overrides_{get_current_order_id()}"
    translation_overrides = st.session_state.setdefault(translation_state_key, {})
    st.markdown("### Tłumaczenie nazw własnych do raportu EN")
    st.caption("Nazwy znane ze słownika są tłumaczone automatycznie. Własne opisy możesz przetłumaczyć przez DeepL lub poprawić ręcznie.")
    translate_col, manual_col = st.columns(2)
    with translate_col:
        if st.button(
            "Przetłumacz nazwy własne przez DeepL", icon=":material/translate:",
            key="ppwr_translate_custom_names", disabled=not bool(deepl_api_key),
        ):
            try:
                st.session_state[translation_state_key] = ppwr_deepl_translation_overrides(
                    edited_components, deepl_api_key, translation_overrides,
                )
                st.success("Nazwy własne zostały przetłumaczone. Możesz je jeszcze poprawić ręcznie.")
                st.rerun()
            except deepl_translation_error as error:
                st.warning(f"{error} Uzupełnij ręczne wersje angielskie poniżej.")
    with manual_col:
        if not deepl_api_key:
            st.caption("DeepL jest niedostępny — użyj ręcznej korekty EN.")

    manual_translation_rows = ppwr_translation_rows(edited_components, translation_overrides)
    if manual_translation_rows:
        with st.expander("Ręczna korekta angielskich nazw", expanded=not bool(deepl_api_key)):
            st.caption("Wpisy ręczne mają pierwszeństwo nad DeepL i są używane w tabelach oraz diagramie raportu EN.")
            editable_translations = pd.DataFrame([
                {"Pole PPWR": row["Pole"], "Opis PL": row["Polski"], "English version": row.get("English version", "")}
                for row in manual_translation_rows
            ])
            edited_translations = st.data_editor(
                editable_translations, hide_index=True, disabled=["Pole PPWR", "Opis PL"],
                column_config={
                    "Pole PPWR": st.column_config.TextColumn("Pole PPWR"),
                    "Opis PL": st.column_config.TextColumn("Opis PL"),
                    "English version": st.column_config.TextColumn("English version"),
                },
                key=f"ppwr_manual_translation_editor_{get_current_order_id()}",
            )
            if st.button("Zapisz ręczne tłumaczenia EN", icon=":material/save:", key="save_ppwr_manual_translations"):
                st.session_state[translation_state_key] = {
                    row["key"]: str(edited_translations.iloc[index]["English version"]).strip()
                    for index, row in enumerate(manual_translation_rows)
                    if str(edited_translations.iloc[index]["English version"]).strip()
                }
                st.success("Ręczne tłumaczenia zapisano dla bieżącego zlecenia. Wygeneruj raport EN ponownie.")

    active_diagram_order_id = get_current_order_id()
    active_diagram_record = load_document_registry().get(active_diagram_order_id, {})
    active_diagram_header = active_diagram_record.get("order_header", {}) or st.session_state.get("tab9_order_header", {})
    report_requirement_options = {
        "order_data": "Dane identyfikacyjne zlecenia i produktu",
        "excluded_goods": "Towary i przesyłki wyłączone z obliczeń PPWR",
        "components": "Rejestr komponentów opakowania",
        "masses": "Podsumowanie mas dla SKU, palety i zamówienia",
        "materials": "Podział masy według materiałów",
        "diagram": "Diagram procesu pakowania ze zdjęciami",
    }
    st.markdown("### Lista wymagań raportu PDF")
    st.caption("Zaznacz elementy, które mają widnieć jako wymagane w spisie kontrolnym na końcu raportu.")
    requirement_columns = st.columns(2)
    selected_report_requirements = []
    selected_report_requirement_keys = []
    for index, (requirement_key, requirement_label) in enumerate(report_requirement_options.items()):
        with requirement_columns[index % 2]:
            if st.checkbox(
                requirement_label,
                value=True,
                key=f"ppwr_pdf_requirement_{active_diagram_order_id}_{requirement_key}",
            ):
                selected_report_requirements.append(requirement_label)
                selected_report_requirement_keys.append(requirement_key)

    ppwr_pdf_metadata = {
        "product_name": ppwr_product_name,
        "sku": ppwr_sku,
        "client": ppwr_client,
        "nip": ppwr_nip,
        "units_per_display": ppwr_units_per_display,
        "displays_per_pallet": ppwr_displays_per_pallet,
        "displays_per_pallet_values": st.session_state["ppwr_displays_per_pallet_values"],
        "units_per_pallet": units_per_pallet,
        "units_per_order": ppwr_units_per_order,
        "pallets_per_order": ppwr_pallets_per_order,
        "total_sku_g": total_sku_g,
        "total_pallet_kg": total_pallet_kg,
        "total_order_kg": total_order_kg,
        "excluded_components": excluded_components,
        "ppwr_translation_overrides": st.session_state.get(translation_state_key, {}),
        "diagram_positions": ppwr_calculation["all_components"],
        "appendix_image": ppwr_appendix_image,
        "diagram_images": st.session_state.get(f"ppwr_diagram_images_{active_diagram_order_id}", {}),
        "diagram_steps": st.session_state.get(f"ppwr_diagram_steps_{active_diagram_order_id}", {}),
        "diagram_label": {
            "order_number": active_diagram_header.get("order_number", active_diagram_order_id),
            "product_name": ppwr_product_name,
            "sku": ppwr_sku,
        },
        "report_requirements": selected_report_requirements,
        "report_requirement_keys": selected_report_requirement_keys,
        "bct_summary": {
            "available": bool(bct_ppwr_view),
            "bct_kg": (bct_ppwr_view or {}).get("bct", 0),
            "safe_bct_kg": (bct_ppwr_view or {}).get("safe_bct", 0),
            "material": (bct_ppwr_view or {}).get("material", "-"),
            "flute": (bct_ppwr_view or {}).get("flute", "-"),
            "approval": (bct_ppwr_view or {}).get("approval", "brak analizy"),
        },
    }
    ppwr_pdf_bytes_pl = generate_ppwr_mass_specification_pdf(
        ppwr_pdf_metadata,
        calculated_components,
        material_summary,
        language="pl",
    )
    ppwr_pdf_bytes_en = generate_ppwr_mass_specification_pdf(
        ppwr_pdf_metadata,
        calculated_components,
        material_summary,
        language="en",
    )
    ppwr_download_pl, ppwr_download_en = st.columns(2)
    with ppwr_download_pl:
        st.download_button(
            "📄 Pobierz profesjonalny raport PPWR — PL",
            data=ppwr_pdf_bytes_pl,
            file_name=f"PPWR_Specyfikacja_Masy_PL_{ppwr_sku or 'produkt'}.pdf",
            mime="application/pdf",
            key="ppwr_download_pdf_pl",
        )
        if st.button("💾 Zapisz raport PPWR — PL", key="store_ppwr_pdf_pl"):
            generate_ppwr_mass_specification_pdf(ppwr_pdf_metadata, calculated_components, material_summary, language="pl", store_document=True)
            st.success("Raport PPWR PL zapisano w Centrum zlecenia.")
    with ppwr_download_en:
        st.download_button(
            "📄 Download professional PPWR report — EN",
            data=ppwr_pdf_bytes_en,
            file_name=f"PPWR_Mass_Specification_EN_{ppwr_sku or 'product'}.pdf",
            mime="application/pdf",
            key="ppwr_download_pdf_en",
        )
        if st.button("💾 Save PPWR report — EN", key="store_ppwr_pdf_en"):
            generate_ppwr_mass_specification_pdf(ppwr_pdf_metadata, calculated_components, material_summary, language="en", store_document=True)
            st.success("Raport PPWR EN zapisano w Centrum zlecenia.")

    with st.expander("Jak liczone są wartości?"):
        st.markdown(
            "- **Masa / 1 SKU** = masa jednostkowa × (ilość na SKU + ilość na paletę / SKU na palecie).\n"
            "- **Masa / 1 paletę** = masa / 1 SKU × SKU na palecie.\n"
            "- **Masa / zamówienie** = masa / 1 paletę × liczba palet.\n"
            "- Procenty pokazują udział każdego materiału w masie opakowań dla wskazanej skali."
        )

    st.markdown("---")
    st.markdown("## Dokumenty PPWR")
    st.caption("Dodaj produkty albo komponenty magazynowe z Bazy produktów lub ręcznie, a następnie wybierz właściwy dokument.")

    issuer_col1, issuer_col2 = st.columns(2)
    with issuer_col1:
        declaration_company = st.text_input("Nazwa wystawcy", value="Emburn Tobacco S.C.", key="ppwr_declaration_company")
        declaration_address = st.text_area(
            "Adres wystawcy", value="ul. Myśliwska 100, 42-400 Zawiercie, Poland", key="ppwr_declaration_address"
        )
    with issuer_col2:
        declaration_nip = st.text_input("NIP / VAT ID", value=ppwr_nip, key="ppwr_declaration_nip")
        declaration_contact = st.text_input("Osoba upoważniona", value="", key="ppwr_declaration_contact")
        declaration_place = st.text_input("Miejsce wystawienia", value="Zawiercie", key="ppwr_declaration_place")
        declaration_issue_date = st.date_input("Data wystawienia", value=datetime.now().date(), key="ppwr_declaration_issue_date")

    # ----- DODANO DANE KLIENTA / ODBIORCY -----
    st.markdown("### Dane Klienta / Odbiorcy (do deklaracji)")
    
    def fetch_customer_data_callback():
        nip_val = st.session_state.get("ppwr_customer_nip_input", "")
        if not nip_val:
            st.session_state["ppwr_cust_error"] = "Podaj numer NIP/VAT przed pobraniem."
            return
            
        import urllib.request
        import json
        import re
        import ssl

        # Python z Microsoft Store/embeddable bywa pozbawiony pełnego magazynu CA.
        # certifi dostarcza aktualny, zweryfikowany zestaw certyfikatów - nie wyłączamy SSL.
        try:
            import certifi
            verified_ssl_context = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            verified_ssl_context = ssl.create_default_context()

        country_code, vat_number = normalize_vat_identifier(nip_val)

        if country_code == "PL":
            # Polish MF API (Biała Lista)
            if len(vat_number) != 10 or not vat_number.isdigit():
                st.session_state["ppwr_cust_error"] = "Nieprawidłowy format NIP dla Polski (wymagane 10 cyfr)."
                return
                
            today = datetime.now().strftime("%Y-%m-%d")
            url = f"https://wl-api.mf.gov.pl/api/search/nip/{vat_number}?date={today}"
            
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=5, context=verified_ssl_context) as response:
                    if response.status == 200:
                        data = json.loads(response.read().decode('utf-8'))
                        subject = data.get("result", {}).get("subject")
                        if subject:
                            st.session_state["ppwr_cust_company"] = subject.get("name", "")
                            addr = subject.get("workingAddress") or subject.get("residenceAddress") or ""
                            st.session_state["ppwr_cust_address"] = addr
                            st.session_state["ppwr_cust_error"] = None
                        else:
                            st.session_state["ppwr_cust_error"] = "Nie znaleziono podmiotu w bazie Ministerstwa Finansów."
                    else:
                        st.session_state["ppwr_cust_error"] = f"Błąd API MF: {response.status}"
            except ssl.SSLCertVerificationError:
                st.session_state["ppwr_cust_error"] = (
                    "Nie udało się zweryfikować certyfikatu API MF. "
                    "Zainstaluj lub zaktualizuj pakiet certifi w środowisku aplikacji."
                )
            except Exception as e:
                st.session_state["ppwr_cust_error"] = f"Błąd połączenia z API MF: {str(e)}"
        else:
            # European Commission VIES API
            url = "https://ec.europa.eu/taxation_customs/vies/rest-api/check-vat-number"
            data = json.dumps({"countryCode": country_code, "vatNumber": vat_number}).encode('utf-8')
            try:
                req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=5, context=verified_ssl_context) as response:
                    if response.status == 200:
                        result = json.loads(response.read().decode('utf-8'))
                        if result.get("valid"):
                            name = result.get("name", "")
                            addr = result.get("address", "")
                            addr = addr.replace("\n", ", ") if addr else ""
                            if name == "---": name = ""
                            if addr == "---": addr = ""
                            
                            st.session_state["ppwr_cust_company"] = name
                            st.session_state["ppwr_cust_address"] = addr
                            st.session_state["ppwr_cust_error"] = None
                        else:
                            st.session_state["ppwr_cust_error"] = f"Numer VAT {country_code}{vat_number} jest nieaktywny lub nie istnieje w systemie VIES."
                    else:
                        st.session_state["ppwr_cust_error"] = f"Błąd API VIES: {response.status}"
            except ssl.SSLCertVerificationError:
                st.session_state["ppwr_cust_error"] = (
                    "Nie udało się zweryfikować certyfikatu API VIES. "
                    "Zainstaluj lub zaktualizuj pakiet certifi w środowisku aplikacji."
                )
            except Exception as e:
                st.session_state["ppwr_cust_error"] = f"Błąd połączenia z API VIES: {str(e)}"

    col_cnip, col_cbtn = st.columns([2, 1])
    with col_cnip:
        st.text_input("NIP Klienta", key="ppwr_customer_nip_input")
    with col_cbtn:
        st.write("")
        st.write("")
        st.button("🔍 Pobierz z bazy (GUS/MF)", on_click=fetch_customer_data_callback)

    if st.session_state.get("ppwr_cust_error"):
        st.error(st.session_state["ppwr_cust_error"])

    if "ppwr_cust_company" not in st.session_state: st.session_state["ppwr_cust_company"] = ""
    if "ppwr_cust_address" not in st.session_state: st.session_state["ppwr_cust_address"] = ""

    col_cc1, col_cc2 = st.columns(2)
    with col_cc1:
        st.text_input("Nazwa firmy klienta", key="ppwr_cust_company")
    with col_cc2:
        st.text_area("Adres klienta", key="ppwr_cust_address")

    customer_details = {
        "company": st.session_state["ppwr_cust_company"],
        "address": st.session_state["ppwr_cust_address"],
        "nip": st.session_state.get("ppwr_customer_nip_input", "")
    }
    # -------------------------------------------

    if "ppwr_declaration_items" not in st.session_state:
        st.session_state["ppwr_declaration_items"] = pd.DataFrame(columns=[
            "Produkt / komponent", "SKU / EAN", "Partia / dowód", "Data produkcji", "Źródło"
        ])

    db_products = load_products()
    db_names = list(db_products.keys())
    add_col1, add_col2 = st.columns(2)
    with add_col1:
        selected_db_product = st.selectbox(
            "Dodaj produkt z Bazy produktów", ["— wybierz produkt —"] + db_names, key="ppwr_declaration_db_product"
        )
        db_batch = st.text_input("Partia / dowód dla produktu z bazy", value="", key="ppwr_declaration_db_batch")
        db_production_date = st.date_input(
            "Data produkcji produktu z bazy", value=datetime(2026, 8, 11).date(), key="ppwr_declaration_db_date"
        )
        if st.button("➕ Dodaj z bazy", key="ppwr_add_declaration_db") and selected_db_product != "— wybierz produkt —":
            product_data = db_products.get(selected_db_product, {})
            row = pd.DataFrame([{
                "Produkt / komponent": selected_db_product,
                "SKU / EAN": str(product_data.get("EAN", "")),
                "Partia / dowód": db_batch,
                "Data produkcji": db_production_date,
                "Źródło": "Baza produktów",
            }])
            st.session_state["ppwr_declaration_items"] = pd.concat(
                [st.session_state["ppwr_declaration_items"], row], ignore_index=True
            )
            st.rerun()
    with add_col2:
        manual_product = st.text_input("Produkt lub komponent magazynowy", value="", key="ppwr_declaration_manual_product")
        manual_ean = st.text_input("SKU / EAN (opcjonalnie)", value="", key="ppwr_declaration_manual_ean")
        manual_batch = st.text_input("Partia / dowód", value="", key="ppwr_declaration_manual_batch")
        manual_production_date = st.date_input(
            "Data produkcji komponentu", value=datetime(2026, 8, 11).date(), key="ppwr_declaration_manual_date"
        )
        if st.button("➕ Dodaj ręcznie", key="ppwr_add_declaration_manual") and manual_product.strip():
            row = pd.DataFrame([{
                "Produkt / komponent": manual_product.strip(),
                "SKU / EAN": manual_ean.strip(),
                "Partia / dowód": manual_batch.strip(),
                "Data produkcji": manual_production_date,
                "Źródło": "Wpis ręczny",
            }])
            st.session_state["ppwr_declaration_items"] = pd.concat(
                [st.session_state["ppwr_declaration_items"], row], ignore_index=True
            )
            st.rerun()

    declaration_items = st.data_editor(
        st.session_state["ppwr_declaration_items"],
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        key="ppwr_declaration_items_editor",
    )
    issuer = {
        "company": declaration_company,
        "address": declaration_address,
        "nip": declaration_nip,
        "contact": declaration_contact or "Authorised person",
        "place": declaration_place,
        "issue_date": declaration_issue_date,
    }

    eu_declaration_tab, production_date_tab = st.tabs([
        "📜 EU Declaration of Conformity (PPWR)",
        "📅 Declaration of Production Date",
    ])
    with eu_declaration_tab:
        st.markdown("### Deklaracja zgodności UE")
        st.caption("Statusy potwierdzeń można umieścić w deklaracji; dokument jest dostępny osobno po polsku i angielsku.")
        compliance_confirmations = {
            "Heavy metals: Pb, Cd, Hg and Cr(VI) within applicable limits": st.checkbox(
                "Potwierdzono wymagania dotyczące metali ciężkich", key="ppwr_confirm_heavy_metals"
            ),
            "Chemical safety: supplier evidence for relevant substances is available": st.checkbox(
                "Potwierdzono dokumentację bezpieczeństwa chemicznego", key="ppwr_confirm_chemical"
            ),
            "PFAS status has been verified for relevant packaging components": st.checkbox(
                "Potwierdzono status PFAS", key="ppwr_confirm_pfas"
            ),
            "Recyclability assessment and material specification have been reviewed": st.checkbox(
                "Potwierdzono ocenę recyklingowalności", key="ppwr_confirm_recyclability"
            ),
        }
        if declaration_items.empty:
            st.info("Dodaj co najmniej jeden produkt lub komponent, aby wygenerować deklarację.")
        else:
            eu_declaration_pdf_pl = generate_eu_declaration_of_conformity_pdf(
                issuer, customer_details, declaration_items, compliance_confirmations, language="pl"
            )
            eu_declaration_pdf_en = generate_eu_declaration_of_conformity_pdf(
                issuer, customer_details, declaration_items, compliance_confirmations, language="en"
            )
            download_pl, download_en = st.columns(2)
            with download_pl:
                st.download_button(
                    "📄 Pobierz deklarację zgodności PPWR — PL",
                    data=eu_declaration_pdf_pl,
                    file_name="Deklaracja_Zgodnosci_PPWR_PL.pdf",
                    mime="application/pdf",
                    key="ppwr_download_eu_declaration_pl",
                )
                if st.button("💾 Zapisz deklarację — PL", key="store_ppwr_declaration_pl"):
                    generate_eu_declaration_of_conformity_pdf(issuer, customer_details, declaration_items, compliance_confirmations, language="pl", store_document=True)
                    st.success("Deklarację PL zapisano w Centrum zlecenia.")
            with download_en:
                st.download_button(
                    "📄 Download PPWR Declaration of Conformity — EN",
                    data=eu_declaration_pdf_en,
                    file_name="EU_Declaration_of_Conformity_PPWR_EN.pdf",
                    mime="application/pdf",
                    key="ppwr_download_eu_declaration_en",
                )
                if st.button("💾 Save declaration — EN", key="store_ppwr_declaration_en"):
                    generate_eu_declaration_of_conformity_pdf(issuer, customer_details, declaration_items, compliance_confirmations, language="en", store_document=True)
                    st.success("Deklarację EN zapisano w Centrum zlecenia.")

    with production_date_tab:
        st.markdown("### Declaration of Packaging Production Date / Deklaracja daty produkcji")
        cutoff_date = st.date_input(
            "Data graniczna produkcji", value=datetime(2026, 8, 12).date(), key="ppwr_production_cutoff_date"
        )
        declaration_dates = pd.to_datetime(declaration_items["Data produkcji"], errors="coerce") if not declaration_items.empty else pd.Series(dtype="datetime64[ns]")
        eligible_items = declaration_items.loc[declaration_dates.dt.date < cutoff_date].copy() if not declaration_items.empty else declaration_items
        excluded_count = len(declaration_items) - len(eligible_items)
        st.caption(f"Pozycje kwalifikujące się do deklaracji: **{len(eligible_items)}**.")
        if excluded_count:
            st.warning(f"Pomijam {excluded_count} pozycji z datą produkcji równą lub późniejszą od daty granicznej.")
        if eligible_items.empty:
            st.info("Dodaj produkt lub komponent z datą produkcji wcześniejszą niż data graniczna.")
        else:
            production_date_pdf_pl = generate_production_date_declaration_pdf(
                issuer, customer_details, eligible_items, cutoff_date, language="pl"
            )
            production_date_pdf_en = generate_production_date_declaration_pdf(
                issuer, customer_details, eligible_items, cutoff_date, language="en"
            )
            download_pl, download_en = st.columns(2)
            with download_pl:
                st.download_button(
                    "📄 Pobierz deklarację daty produkcji — PL",
                    data=production_date_pdf_pl,
                    file_name="Deklaracja_Daty_Produkcji_Opakowan_PL.pdf",
                    mime="application/pdf",
                    key="ppwr_download_production_date_pl",
                )
                if st.button("💾 Zapisz deklarację daty — PL", key="store_ppwr_date_pl"):
                    generate_production_date_declaration_pdf(issuer, customer_details, eligible_items, cutoff_date, language="pl", store_document=True)
                    st.success("Deklarację daty PL zapisano w Centrum zlecenia.")
            with download_en:
                st.download_button(
                    "📄 Download production-date declaration — EN",
                    data=production_date_pdf_en,
                    file_name="Declaration_of_Packaging_Production_Date_EN.pdf",
                    mime="application/pdf",
                    key="ppwr_download_production_date_en",
                )
                if st.button("💾 Save production-date declaration — EN", key="store_ppwr_date_en"):
                    generate_production_date_declaration_pdf(issuer, customer_details, eligible_items, cutoff_date, language="en", store_document=True)
                    st.success("Deklarację daty EN zapisano w Centrum zlecenia.")

    active_ppwr_order_id = get_current_order_id()
    active_ppwr_record = load_document_registry().get(active_ppwr_order_id, {})
    active_ppwr_order = {
        **active_ppwr_record,
        "order_id": active_ppwr_order_id,
        "order_header": active_ppwr_record.get("order_header", {})
        or st.session_state.get("tab9_order_header", {}),
        "product_name": ppwr_product_name,
        "sku": ppwr_sku,
    }
    render_packing_diagram(
        ppwr_positions=pd.DataFrame(ppwr_calculation["all_components"]),
        order=active_ppwr_order,
    )
