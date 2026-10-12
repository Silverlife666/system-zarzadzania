"""Widok wydzielony z app.py; przejściowy most zależności."""

def render_catalog_import_screen(st, deps):
    for _bridge_name, _bridge_value in deps.items():
        if not _bridge_name.startswith("__"):
            globals()[_bridge_name] = _bridge_value
    del _bridge_name, _bridge_value
    
    st.subheader("📥 Import i Wizualizacja (CSV, XLSX, ODS)")
    st.markdown("Wgraj plik z zamówieniem lub bazą danych w formacie CSV, Excel lub ODS.")
    template_columns = [
        "Nazwa", "Dlugosc", "Szerokosc", "Wysokosc", "Waga", "EAN", "Typ_Palety",
        "Max_Wysokosc", "Max_Waga", "displays_in_mc", "boxes_in_display", "pcs_in_box",
        "SKU", "Producent", "Klient", "Aktywny", "Data_ostatniej_weryfikacji",
        "EAN_Produkt", "EAN_Display", "EAN_MasterCase",
        "Produkt_Dlugosc", "Produkt_Szerokosc", "Produkt_Wysokosc", "Produkt_Masa_netto_kg",
        "Display_Dlugosc", "Display_Szerokosc", "Display_Wysokosc", "Display_Masa_pustego_kg", "Display_Masa_pelnego_kg",
        "MC_Dlugosc_wewnetrzna", "MC_Szerokosc_wewnetrzna", "MC_Wysokosc_wewnetrzna",
        "MC_Dlugosc_zewnetrzna", "MC_Szerokosc_zewnetrzna", "MC_Wysokosc_zewnetrzna",
        "MC_Tara_kg", "MC_Masa_brutto_max_kg", "MC_FEFCO", "MC_Tektura", "MC_Fala",
    ]
    template_example = {
        "Nazwa": "Przykładowy karton", "Dlugosc": 400, "Szerokosc": 300, "Wysokosc": 250,
        "Waga": 4.5, "EAN": "5056134535500", "Typ_Palety": "EURO", "Max_Wysokosc": 2000,
        "Max_Waga": 500, "displays_in_mc": 1, "boxes_in_display": 1, "pcs_in_box": 1,
        "SKU": "SKU-001", "Producent": "Przykładowy producent", "Klient": "Przykładowy klient",
        "Aktywny": "Tak", "Data_ostatniej_weryfikacji": datetime.now().date().isoformat(),
        "EAN_Produkt": "5901234123457", "EAN_Display": "5901234123464", "EAN_MasterCase": "5901234123471",
        "Produkt_Dlugosc": 200, "Produkt_Szerokosc": 120, "Produkt_Wysokosc": 80, "Produkt_Masa_netto_kg": 0.25,
        "Display_Dlugosc": 400, "Display_Szerokosc": 300, "Display_Wysokosc": 240,
        "Display_Masa_pustego_kg": 0.35, "Display_Masa_pelnego_kg": 4.35,
        "MC_Dlugosc_wewnetrzna": 610, "MC_Szerokosc_wewnetrzna": 410, "MC_Wysokosc_wewnetrzna": 290,
        "MC_Dlugosc_zewnetrzna": 620, "MC_Szerokosc_zewnetrzna": 420, "MC_Wysokosc_zewnetrzna": 300,
        "MC_Tara_kg": 0.6, "MC_Masa_brutto_max_kg": 15, "MC_FEFCO": "0201", "MC_Tektura": "5-warstwowa", "MC_Fala": "BC",
    }
    template_csv = pd.DataFrame([template_example], columns=template_columns).to_csv(index=False).encode("utf-8-sig")
    with st.expander("📄 Pobierz szablon importu", expanded=False):
        st.caption("Szablon zawiera wymagane pola do obliczeń oraz opcjonalne dane kartoteki produktu.")
        download_col1, download_col2 = st.columns(2)
        with download_col1:
            st.download_button("⬇️ Pobierz CSV", data=template_csv, file_name="szablon_importu_produktow.csv", mime="text/csv")
        with download_col2:
            st.download_button(
                "⬇️ Pobierz Excel", data=build_import_template_xlsx(),
                file_name="szablon_importu_produktow.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    if "imported_data" not in st.session_state:
        st.session_state["imported_data"] = None

    import_fields = {
        "Nazwa": {"required": True, "aliases": ["nazwa", "produkt", "towar", "nazwa produktu"]},
        "Dlugosc": {"required": True, "aliases": ["dlugosc", "długość", "length", "dl"]},
        "Szerokosc": {"required": True, "aliases": ["szerokosc", "szerokość", "width", "szer"]},
        "Wysokosc": {"required": True, "aliases": ["wysokosc", "wysokość", "height", "wys"]},
        "Waga": {"required": True, "aliases": ["waga", "masa", "weight", "masa netto"]},
        "SKU": {"required": False, "aliases": ["sku", "kod produktu", "indeks", "symbol"]},
        "EAN": {"required": False, "aliases": ["ean", "kod kreskowy", "barcode", "kod"]},
        "EAN_Produkt": {"required": False, "aliases": ["ean produkt", "ean produktu", "ean_produkt"]},
        "EAN_Display": {"required": False, "aliases": ["ean display", "ean displaya", "ean_display"]},
        "EAN_MasterCase": {"required": False, "aliases": ["ean master case", "ean mastercase", "ean_mastercase"]},
        "Produkt_Dlugosc": {"required": False, "aliases": ["produkt dlugosc", "produkt długość"]},
        "Produkt_Szerokosc": {"required": False, "aliases": ["produkt szerokosc", "produkt szerokość"]},
        "Produkt_Wysokosc": {"required": False, "aliases": ["produkt wysokosc", "produkt wysokość"]},
        "Produkt_Masa_netto_kg": {"required": False, "aliases": ["produkt masa netto", "masa netto produktu"]},
        "Display_Dlugosc": {"required": False, "aliases": ["display dlugosc", "display długość"]},
        "Display_Szerokosc": {"required": False, "aliases": ["display szerokosc", "display szerokość"]},
        "Display_Wysokosc": {"required": False, "aliases": ["display wysokosc", "display wysokość"]},
        "Display_Masa_pustego_kg": {"required": False, "aliases": ["masa pustego displaya", "display masa pusta"]},
        "Display_Masa_pelnego_kg": {"required": False, "aliases": ["masa pelnego displaya", "display masa pełna"]},
        "MC_Dlugosc_wewnetrzna": {"required": False, "aliases": ["mc dlugosc wewnetrzna", "master case długość wewnętrzna"]},
        "MC_Szerokosc_wewnetrzna": {"required": False, "aliases": ["mc szerokosc wewnetrzna", "master case szerokość wewnętrzna"]},
        "MC_Wysokosc_wewnetrzna": {"required": False, "aliases": ["mc wysokosc wewnetrzna", "master case wysokość wewnętrzna"]},
        "MC_Dlugosc_zewnetrzna": {"required": False, "aliases": ["mc dlugosc zewnetrzna", "master case długość zewnętrzna"]},
        "MC_Szerokosc_zewnetrzna": {"required": False, "aliases": ["mc szerokosc zewnetrzna", "master case szerokość zewnętrzna"]},
        "MC_Wysokosc_zewnetrzna": {"required": False, "aliases": ["mc wysokosc zewnetrzna", "master case wysokość zewnętrzna"]},
        "MC_Tara_kg": {"required": False, "aliases": ["mc tara", "tara master case"]},
        "MC_Masa_brutto_max_kg": {"required": False, "aliases": ["mc masa brutto max", "maks masa brutto master case"]},
        "MC_FEFCO": {"required": False, "aliases": ["mc fefco", "fefco master case"]},
        "MC_Tektura": {"required": False, "aliases": ["mc tektura", "tektura master case"]},
        "MC_Fala": {"required": False, "aliases": ["mc fala", "fala master case"]},
        "Max_Wysokosc": {"required": False, "aliases": ["max wysokosc", "max wysokość", "limit wysokosci"]},
        "Max_Waga": {"required": False, "aliases": ["max waga", "max masa", "limit wagi"]},
        "Typ_Palety": {"required": False, "aliases": ["typ palety", "paleta"]},
        "displays_in_mc": {"required": False, "aliases": ["displays in mc", "display w master case"]},
        "boxes_in_display": {"required": False, "aliases": ["boxes in display", "pudelek w displayu", "pudełek w displayu"]},
        "pcs_in_box": {"required": False, "aliases": ["pcs in box", "sztuk w pudelku", "sztuk w pudełku"]},
    }

    def reset_import_state():
        st.session_state["imported_data"] = None
        for field_name in import_fields:
            st.session_state.pop(f"import_map_{field_name}", None)

    # --- WIDOK 1: USTAWIENIA IMPORTU (Gdy plik nie jest jeszcze załadowany) ---
    if st.session_state["imported_data"] is None:
        uploaded_file = st.file_uploader("Wgraj plik z danymi (CSV, XLS, XLSX, ODS)", type=["csv", "xls", "xlsx", "ods"], key="main_file_uploader")

        if uploaded_file is not None:
            file_ext = uploaded_file.name.split(".")[-1].lower()
            file_bytes = uploaded_file.getvalue()
            
            col_s1, col_s2 = st.columns(2)
            with col_s1:
                header_row = st.number_input("Wiersz nagłówka (0 = pierwszy)", min_value=0, value=0, step=1)
            with col_s2:
                sheet_name = None
                if file_ext in ["xlsx", "xls", "ods"]:
                    try:
                        sheets = get_excel_sheets(file_bytes, uploaded_file.name)
                        sheet_name = st.selectbox("Wybierz arkusz", sheets)
                    except Exception as e:
                        st.error(f"Nie udało się odczytać arkuszy: {e}")

            if st.button("📥 Zaimportuj plik", type="primary", width="stretch"):
                try:
                    df, dropped_cols, duplicates_count = process_data(
                        file_bytes, uploaded_file.name, file_ext, header_row, sheet_name
                    )
                    st.session_state["imported_data"] = df
                    
                    if dropped_cols > 0:
                        st.warning(f"🧹 Usunięto całkowicie puste kolumny: {dropped_cols}")
                    if duplicates_count > 0:
                        st.warning(f"⚠️ Wykryto powielone wiersze (duplikaty): {duplicates_count}")
                        
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Błąd podczas odczytu: {e}")

    # --- WIDOK 2: PRZETWARZANIE DANYCH (Gdy plik jest załadowany) ---
    else:
        df_import = st.session_state["imported_data"]
        
        col_info, col_reset = st.columns([3, 1])
        with col_info:
            st.success(f"📊 Załadowano dane: **{df_import.shape[0]}** wierszy | **{df_import.shape[1]}** kolumn")
        with col_reset:
            if st.button("🗑️ Wyczyść plik", width="stretch"):
                reset_import_state()
                st.rerun()
                
        with st.expander("🔍 Podgląd zaimportowanych danych", expanded=False):
            st.dataframe(df_import, width="stretch")

        st.divider()
        st.markdown("#### 1. Mapowanie kolumn i walidacja")
        st.caption("Wskaż, z których kolumn pliku pobrać dane. Pola oznaczone * są wymagane do obliczenia.")
        source_columns = list(df_import.columns)
        options = ["— nie mapuj —"] + source_columns
        mapping = {}
        map_columns = st.columns(2)
        for position, (field_name, field_info) in enumerate(import_fields.items()):
            recommended = next(
                (column for column in source_columns
                 if canonical_column_name(column) in {canonical_column_name(a) for a in field_info["aliases"]}),
                None,
            )
            default_index = options.index(recommended) if recommended in options else 0
            with map_columns[position % 2]:
                selected_column = st.selectbox(
                    f"{field_name}{' *' if field_info['required'] else ''}",
                    options,
                    index=default_index,
                    key=f"import_map_{field_name}",
                )
                mapping[field_name] = None if selected_column == options[0] else selected_column

        missing_mappings = [field for field, info in import_fields.items() if info["required"] and not mapping[field]]
        prepared = pd.DataFrame({
            field: (df_import[column] if column else pd.Series([None] * len(df_import), index=df_import.index))
            for field, column in mapping.items()
        })

        validation_rows = []
        if not missing_mappings:
            for index, row in prepared.iterrows():
                errors = []
                warnings = []
                name = str(row.get("Nazwa", "")).strip()
                _, name_error = validate_product_text(name, "Nazwa produktu", required=True)
                if name_error:
                    errors.append(name_error)
                _, sku_error = validate_product_text(row.get("SKU", ""), "SKU")
                if sku_error:
                    errors.append(sku_error)
                for field in ("Dlugosc", "Szerokosc", "Wysokosc", "Waga"):
                    if safe_float(row.get(field), 0) <= 0:
                        errors.append(f"nieprawidłowe pole {field}")
                ean_levels = {}
                for level, field in (("produkt", "EAN_Produkt"), ("display", "EAN_Display"), ("Master Case", "EAN_MasterCase")):
                    raw_ean = row.get(field, "")
                    # Stary szablon z jedną kolumną EAN oznacza EAN produktu.
                    if field == "EAN_Produkt" and (pd.isna(raw_ean) or not str(raw_ean or "").strip()):
                        raw_ean = row.get("EAN", "")
                    ean_value, ean_error = validate_ean(raw_ean)
                    if ean_error:
                        errors.append(f"EAN {level}: {ean_error}")
                    elif ean_value:
                        ean_levels[level] = ean_value
                duplicate_levels = [code for code in set(ean_levels.values()) if list(ean_levels.values()).count(code) > 1]
                if duplicate_levels:
                    errors.append("ten sam EAN przypisano do więcej niż jednego poziomu: " + ", ".join(duplicate_levels))
                pal_typ = str(row.get("Typ_Palety") or "EURO").strip().upper()
                if pal_typ not in PALLET_TYPES:
                    warnings.append(f"nieznany typ palety „{pal_typ}” — użyta będzie EURO")
                    pal_typ = "EURO"
                pallet = PALLET_TYPES[pal_typ]
                dl, szer = safe_float(row.get("Dlugosc")), safe_float(row.get("Szerokosc"))
                wys, waga = safe_float(row.get("Wysokosc")), safe_float(row.get("Waga"))
                if waga > 0 and waga <= 0.05:
                    warnings.append("bardzo niska masa (≤ 0,05 kg) — sprawdź jednostkę")
                relation_values = [safe_int(row.get(field), 1) for field in ("displays_in_mc", "boxes_in_display", "pcs_in_box")]
                relation_description = ""
                if any(value <= 0 for value in relation_values):
                    errors.append("relacja Master Case → display → sztuki musi zawierać wartości większe od 0")
                else:
                    relation_description = f"1 MC = {relation_values[0]} × {relation_values[1]} × {relation_values[2]} = {relation_values[0] * relation_values[1] * relation_values[2]} szt."
                # Jeśli import zawiera szczegółowe wymiary trzech poziomów,
                # sprawdzamy, czy rzeczywiście mieszczą się jeden w drugim.
                product_dims = [safe_float(row.get(field)) for field in ("Produkt_Dlugosc", "Produkt_Szerokosc", "Produkt_Wysokosc")]
                display_dims = [safe_float(row.get(field)) for field in ("Display_Dlugosc", "Display_Szerokosc", "Display_Wysokosc")]
                mc_inner_dims = [safe_float(row.get(field)) for field in ("MC_Dlugosc_wewnetrzna", "MC_Szerokosc_wewnetrzna", "MC_Wysokosc_wewnetrzna")]
                mc_outer_dims = [safe_float(row.get(field), fallback) for field, fallback in zip(("MC_Dlugosc_zewnetrzna", "MC_Szerokosc_zewnetrzna", "MC_Wysokosc_zewnetrzna"), (dl, szer, wys))]
                physical_relation = "brak pełnych wymiarów do kontroli"
                if all(product_dims) and all(display_dims):
                    if any(product_dim > display_dim for product_dim, display_dim in zip(product_dims, display_dims)):
                        errors.append("produkt nie mieści się w zadeklarowanych wymiarach displaya")
                    else:
                        physical_relation = "produkt mieści się w displayu"
                if all(display_dims) and all(mc_inner_dims):
                    if any(display_dim > mc_dim for display_dim, mc_dim in zip(display_dims, mc_inner_dims)):
                        errors.append("display nie mieści się w wymiarach wewnętrznych Master Case")
                    else:
                        physical_relation = (physical_relation + "; " if physical_relation != "brak pełnych wymiarów do kontroli" else "") + "display mieści się w Master Case"
                if all(mc_inner_dims) and all(mc_outer_dims):
                    if any(inner_dim > outer_dim for inner_dim, outer_dim in zip(mc_inner_dims, mc_outer_dims)):
                        errors.append("wymiary wewnętrzne Master Case nie mogą być większe od zewnętrznych")
                display_empty_mass = safe_float(row.get("Display_Masa_pustego_kg"))
                display_full_mass = safe_float(row.get("Display_Masa_pelnego_kg"))
                master_gross_limit = safe_float(row.get("MC_Masa_brutto_max_kg"))
                if display_empty_mass and display_full_mass and display_full_mass < display_empty_mass:
                    errors.append("masa pełnego displaya nie może być mniejsza od masy pustego")
                if master_gross_limit and display_full_mass and relation_values[0] > 0 and display_full_mass * relation_values[0] > master_gross_limit:
                    errors.append("maksymalna masa brutto Master Case jest mniejsza od masy zadeklarowanych displayów")
                if dl > 0 and szer > 0 and not ((dl <= pallet["L"] and szer <= pallet["W"]) or (dl <= pallet["W"] and szer <= pallet["L"])):
                    warnings.append(f"podstawa kartonu nie mieści się na palecie {pal_typ}")
                max_height = safe_float(row.get("Max_Wysokosc"), 2000.0) or 2000.0
                max_weight = safe_float(row.get("Max_Waga"), 500.0) or 500.0
                if wys > 0 and wys + pallet["H"] > max_height:
                    warnings.append("wysokość pojedynczego kartonu przekracza limit palety")
                if waga > 0 and waga + pallet["WEIGHT"] > max_weight:
                    warnings.append("masa pojedynczego kartonu przekracza limit palety")
                validation_rows.append({
                    "Wiersz": index + 1, "EAN": ean_levels.get("Master Case") or ean_levels.get("display") or ean_levels.get("produkt") or "—",
                    "EAN-y poziomów": " | ".join(f"{level}: {code}" for level, code in ean_levels.items()) or "—",
                    "_ean_codes": list(ean_levels.values()), "Status": "Błąd" if errors else "OK",
                    "Uwagi": "; ".join(errors), "Ostrzeżenia": "; ".join(warnings), "Relacja MC": relation_description, "Kontrola fizyczna": physical_relation,
                })

            valid_eans = {}
            for item in validation_rows:
                if item["Status"] == "OK":
                    for code in item.get("_ean_codes", []):
                        valid_eans.setdefault(code, []).append(item["Wiersz"])
            for ean, rows in valid_eans.items():
                if len(rows) > 1:
                    for item in validation_rows:
                        if item["Wiersz"] in rows:
                            item["Status"] = "Błąd"
                            item["Uwagi"] = (item["Uwagi"] + "; " if item["Uwagi"] else "") + f"duplikat EAN {ean} (wiersze {', '.join(map(str, rows))})"

        if missing_mappings:
            st.error("Przed obliczeniem zmapuj pola wymagane: " + ", ".join(missing_mappings))
        else:
            validation_df = pd.DataFrame(validation_rows)
            validation_view = validation_df.drop(columns=["_ean_codes"], errors="ignore")
            invalid_count = int((validation_df["Status"] == "Błąd").sum())
            warning_count = int(validation_df["Ostrzeżenia"].astype(bool).sum())
            if invalid_count:
                st.warning(f"Walidacja wykryła {invalid_count} niepoprawnych wierszy. Nie zostaną policzone.")
                st.dataframe(validation_view[validation_df["Status"] == "Błąd"], width="stretch")
            else:
                st.success("Wszystkie wiersze przeszły walidację.")
            if warning_count:
                st.warning(f"Walidacja logiczna zgłasza ostrzeżenia dla {warning_count} wierszy. Możesz je policzyć, ale sprawdź dane.")
                st.dataframe(validation_view[validation_df["Ostrzeżenia"] != ""], width="stretch")

            duplicate_name_count = int(prepared["Nazwa"].astype(str).str.strip().duplicated(keep=False).sum())
            if duplicate_name_count:
                st.info(f"Wykryto {duplicate_name_count} wierszy z powtórzoną nazwą. Wszystkie zostaną zachowane, jeśli mają różne EAN.")

            if st.button("🚀 Oblicz poprawne palety jednorodne", type="primary"):
                valid_indexes = [row["Wiersz"] - 1 for row in validation_rows if row["Status"] == "OK"]
                if not valid_indexes:
                    st.error("Brak poprawnych wierszy do obliczenia.")
                else:
                    st.success(f"Rozpoczęto obliczenia dla {len(valid_indexes)} poprawnych pozycji.")
                    for index in valid_indexes:
                        row = prepared.iloc[index]
                        nazwa = str(row["Nazwa"]).strip()
                        dl, szer = safe_float(row["Dlugosc"]), safe_float(row["Szerokosc"])
                        wys, waga = safe_float(row["Wysokosc"]), safe_float(row["Waga"])
                        ean, _ = validate_ean(row.get("EAN_MasterCase", ""))
                        if not ean:
                            ean, _ = validate_ean(row.get("EAN_Display", ""))
                        if not ean:
                            raw_product_ean = row.get("EAN_Produkt", "")
                            if pd.isna(raw_product_ean) or not str(raw_product_ean).strip():
                                raw_product_ean = row.get("EAN", "")
                            ean, _ = validate_ean(raw_product_ean)
                        max_total_h = safe_float(row.get("Max_Wysokosc"), 2000.0) or 2000.0
                        max_total_weight = safe_float(row.get("Max_Waga"), 500.0) or 500.0
                        pal_typ = str(row.get("Typ_Palety") or "EURO").strip().upper()
                        if pal_typ not in PALLET_TYPES:
                            pal_typ = "EURO"
                        wykonaj_obliczenia_i_wyswietl(
                            nazwa, dl, szer, wys, waga, ean or "Brak", pal_typ,
                            max_total_h, max_total_weight,
                            safe_int(row.get("displays_in_mc"), 1) or 1,
                            safe_int(row.get("boxes_in_display"), 1) or 1,
                            safe_int(row.get("pcs_in_box"), 1) or 1,
                            f"file_{index}",
                        )

            if st.button("💾 Zapisz poprawne pozycje w bazie Produkt / Display / Master Case"):
                valid_indexes = [row["Wiersz"] - 1 for row in validation_rows if row["Status"] == "OK"]
                saved, failed = 0, []
                for index in valid_indexes:
                    row = prepared.iloc[index]
                    name = str(row.get("Nazwa", "")).strip()
                    def import_text(field, default=""):
                        value = row.get(field, default)
                        return "" if pd.isna(value) else str(value).strip()
                    raw_product_ean = row.get("EAN_Produkt", "")
                    if pd.isna(raw_product_ean) or not str(raw_product_ean).strip():
                        raw_product_ean = row.get("EAN", "")
                    product_ean, _ = validate_ean(raw_product_ean)
                    display_ean, _ = validate_ean(row.get("EAN_Display", ""))
                    master_ean, _ = validate_ean(row.get("EAN_MasterCase", ""))
                    legacy_l, legacy_w, legacy_h, legacy_mass = (safe_float(row.get(field), 0) for field in ("Dlugosc", "Szerokosc", "Wysokosc", "Waga"))
                    imported_record = {
                        "Dlugosc": legacy_l, "Szerokosc": legacy_w, "Wysokosc": legacy_h, "Waga": legacy_mass,
                        "EAN": product_ean, "SKU": import_text("SKU"), "Producent": import_text("Producent"), "Klient": import_text("Klient"),
                        "Typ_Palety": import_text("Typ_Palety", "EURO").upper() or "EURO",
                        "Max_Wysokosc": safe_float(row.get("Max_Wysokosc"), 2000) or 2000,
                        "Max_Waga": safe_float(row.get("Max_Waga"), 500) or 500,
                        "displays_in_mc": safe_int(row.get("displays_in_mc"), 1) or 1,
                        "boxes_in_display": safe_int(row.get("boxes_in_display"), 1) or 1,
                        "pcs_in_box": safe_int(row.get("pcs_in_box"), 1) or 1,
                        "Aktywny": import_text("Aktywny", "Tak").casefold() not in ("nie", "false", "0"), "Status": "Aktywny",
                        "Data_ostatniej_weryfikacji": import_text("Data_ostatniej_weryfikacji", datetime.now().date().isoformat()),
                        "Produkt": {"Dlugosc": safe_float(row.get("Produkt_Dlugosc"), legacy_l), "Szerokosc": safe_float(row.get("Produkt_Szerokosc"), legacy_w), "Wysokosc": safe_float(row.get("Produkt_Wysokosc"), legacy_h), "Masa_netto_kg": safe_float(row.get("Produkt_Masa_netto_kg"), legacy_mass), "EAN": product_ean},
                        "Display": {"Dlugosc": safe_float(row.get("Display_Dlugosc")), "Szerokosc": safe_float(row.get("Display_Szerokosc")), "Wysokosc": safe_float(row.get("Display_Wysokosc")), "Masa_pustego_kg": safe_float(row.get("Display_Masa_pustego_kg")), "Masa_pelnego_kg": safe_float(row.get("Display_Masa_pelnego_kg")), "EAN": display_ean, "Pudelka_w_displayu": safe_int(row.get("boxes_in_display"), 1) or 1},
                        "MasterCase": {"Dlugosc_wewnetrzna": safe_float(row.get("MC_Dlugosc_wewnetrzna")), "Szerokosc_wewnetrzna": safe_float(row.get("MC_Szerokosc_wewnetrzna")), "Wysokosc_wewnetrzna": safe_float(row.get("MC_Wysokosc_wewnetrzna")), "Dlugosc_zewnetrzna": safe_float(row.get("MC_Dlugosc_zewnetrzna"), legacy_l), "Szerokosc_zewnetrzna": safe_float(row.get("MC_Szerokosc_zewnetrzna"), legacy_w), "Wysokosc_zewnetrzna": safe_float(row.get("MC_Wysokosc_zewnetrzna"), legacy_h), "Tara_kg": safe_float(row.get("MC_Tara_kg")), "Masa_brutto_max_kg": safe_float(row.get("MC_Masa_brutto_max_kg")), "EAN": master_ean, "FEFCO": import_text("MC_FEFCO"), "Tektura": import_text("MC_Tektura"), "Fala": import_text("MC_Fala"), "Displayow_w_mastercase": safe_int(row.get("displays_in_mc"), 1) or 1},
                    }
                    try:
                        zapisz_produkt_w_db(name, imported_record)
                        saved += 1
                    except ValueError as error:
                        failed.append(f"wiersz {index + 1}: {error}")
                st.session_state["database_products"] = wczytaj_produkty_z_db()
                if saved:
                    st.success(f"Zapisano w bazie: {saved} pozycji.")
                if failed:
                    st.error("Nie zapisano części pozycji: " + " | ".join(failed))

    # --- ZARZĄDZANIE BAZĄ PRODUKTÓW ---
    st.markdown("---")
    st.subheader("🗄️ Zarządzanie Bazą Produktów")
    custom_field_names = get_product_custom_fields()
    with st.expander("🔎 Wyszukiwanie rozszerzone produktów", expanded=False):
        advanced_query = st.text_input("Szukaj po SKU, EAN, nazwie, kliencie, producencie lub tagach", key="advanced_product_search")
        if advanced_query.strip():
            query = advanced_query.strip().casefold()
            found_products = []
            for product_name, product_data in wczytaj_produkty_z_db().items():
                ean_data = product_ean_levels(product_data)
                searchable = " ".join(str(product_data.get(field, "")) for field in ("SKU", "Klient", "Producent", "Tagi")) + " " + " ".join(ean_data.values()) + " " + product_name
                if query in searchable.casefold():
                    found_products.append({
                        "Nazwa": product_name, "SKU": product_data.get("SKU", ""), "EAN produktu": ean_data.get("produkt", ""), "EAN displaya": ean_data.get("display", ""), "EAN Master Case": ean_data.get("master_case", ""),
                        "Klient": product_data.get("Klient", ""), "Producent": product_data.get("Producent", ""),
                        "Tagi": product_data.get("Tagi", ""), "Status": product_data.get("Status", "Aktywny"),
                    })
            if found_products:
                st.dataframe(pd.DataFrame(found_products), width="stretch")
            else:
                st.info("Nie znaleziono aktywnych produktów.")
    sub_tab1, sub_tab2, sub_tab3, sub_tab4, sub_tab5 = st.tabs([
        "➕ Dodaj nowy produkt", 
        "✏️ Edytuj / Usuń produkt", 
        "🔍 Wybierz i oblicz", "📁 Archiwum i historia", "⚙️ Pola i kopie bazy"
    ])
    
    with sub_tab1:
        with st.form("add_product_form"):
            with st.expander("1. Dane identyfikacyjne i status", expanded=True):
                new_name = st.text_input("Nazwa produktu", key="add_name")
                info_col1, info_col2 = st.columns(2)
                with info_col1:
                    new_sku = st.text_input("Kod produktu / SKU", key="add_sku")
                    new_producer = st.text_input("Producent", key="add_producer")
                with info_col2:
                    new_client = st.text_input("Klient", key="add_client")
                    new_status = st.selectbox("Status", ["Roboczy", "Aktywny", "Wycofany", "Oczekuje na weryfikację"], index=1, key="add_status")
                new_tags = st.text_input("Tagi (oddziel przecinkami)", key="add_tags")
                new_verified = st.date_input("Data ostatniej weryfikacji danych", value=datetime.now().date(), key="add_verified")
                new_custom_values = {}
                if custom_field_names:
                    st.caption("Pola dodatkowe administratora")
                    for field_name in custom_field_names:
                        new_custom_values[field_name] = st.text_input(field_name, key=f"add_custom_{field_name}")
            with st.expander("2. Zdjęcia i załączniki", expanded=False):
                new_image = st.file_uploader("Zdjęcie produktu / kartonu / etykiety", type=["jpg", "jpeg", "png", "gif"], key="add_product_image")
                new_attachments = st.file_uploader("Załączniki (specyfikacja, karta techniczna, certyfikat, PDF)", type=["pdf", "jpg", "jpeg", "png", "gif"], accept_multiple_files=True, key="add_product_attachments")
            with st.expander("3. Domyślne parametry paletyzacji", expanded=False):
                new_pal = st.selectbox("Domyślny typ palety", list(PALLET_TYPES.keys()), key="add_pal")
                new_max_h = st.number_input("Limit Wysokości [mm]", value=2000.0, key="add_max_h")
                new_max_w = st.number_input("Limit Wagi [kg]", value=500.0, key="add_max_w")
            with st.expander("4. Relacje pakowania", expanded=False):
                new_disp_mc = st.number_input("Displays w Master Case", value=24, step=1, key="add_disp_mc")
                new_boxes_disp = st.number_input("Pudełek w displayu", value=16, step=1, key="add_boxes_disp")
                new_pcs_box = st.number_input("Sztuk w pudełku", value=1, step=1, key="add_pcs_box")

            with st.expander("5. Parametry fizyczne produktu", expanded=False):
                new_dl = st.number_input("Produkt - długość [mm]", min_value=1.0, value=200.0, key="add_dl")
                new_szer = st.number_input("Produkt - szerokość [mm]", min_value=1.0, value=470.0, key="add_szer")
                new_wys = st.number_input("Produkt - wysokość [mm]", min_value=1.0, value=280.0, key="add_wys")
                new_waga = st.number_input("Produkt - masa netto [g]", min_value=0.0, value=8000.0, key="add_waga")
                new_ean_product = st.text_input("EAN produktu", value="5056134535500", key="add_ean_product")

            with st.expander("6. Parametry fizyczne displaya", expanded=True):
                display_col1, display_col2, display_col3 = st.columns(3)
                with display_col1:
                    new_display_l = st.number_input("Display - długość [mm]", min_value=0.0, value=0.0, key="add_display_l")
                    new_display_w = st.number_input("Display - szerokość [mm]", min_value=0.0, value=0.0, key="add_display_w")
                with display_col2:
                    new_display_h = st.number_input("Display - wysokość [mm]", min_value=0.0, value=0.0, key="add_display_h")
                    new_display_empty_mass = st.number_input("Masa pustego displaya [g]", min_value=0.0, value=0.0, key="add_display_empty_mass")
                with display_col3:
                    new_display_full_mass = st.number_input("Masa pełnego displaya [g]", min_value=0.0, value=0.0, key="add_display_full_mass")
                    new_ean_display = st.text_input("EAN displaya", key="add_ean_display")
                    new_display_rotation = st.checkbox("Display można obracać", value=True, key="add_display_rotation")
                    new_display_position = st.selectbox("Dozwolona pozycja displaya", ["Poziomo", "Pionowo", "Na boku"], key="add_display_position")

            with st.expander("7. Parametry fizyczne kartonu / Master Case", expanded=False):
                master_col1, master_col2, master_col3 = st.columns(3)
                with master_col1:
                    new_mc_inner_l = st.number_input("Master Case - długość wewnętrzna [mm]", min_value=0.0, value=0.0, key="add_mc_inner_l")
                    new_mc_inner_w = st.number_input("Master Case - szerokość wewnętrzna [mm]", min_value=0.0, value=0.0, key="add_mc_inner_w")
                    new_mc_inner_h = st.number_input("Master Case - wysokość wewnętrzna [mm]", min_value=0.0, value=0.0, key="add_mc_inner_h")
                with master_col2:
                    new_mc_outer_l = st.number_input("Master Case - długość zewnętrzna [mm]", min_value=0.0, value=0.0, key="add_mc_outer_l")
                    new_mc_outer_w = st.number_input("Master Case - szerokość zewnętrzna [mm]", min_value=0.0, value=0.0, key="add_mc_outer_w")
                    new_mc_outer_h = st.number_input("Master Case - wysokość zewnętrzna [mm]", min_value=0.0, value=0.0, key="add_mc_outer_h")
                with master_col3:
                    new_mc_tare = st.number_input("Tara Master Case [kg]", min_value=0.0, value=0.0, key="add_mc_tare")
                    new_mc_gross_max = st.number_input("Maks. masa brutto Master Case [kg]", min_value=0.0, value=0.0, key="add_mc_gross_max")
                    new_ean_mastercase = st.text_input("EAN Master Case", key="add_ean_mastercase")
                    new_mc_fefco = st.selectbox("FEFCO Master Case", ["0201", "0215", "0427", "0470", "Inny"], key="add_mc_fefco")
                    new_mc_closure = st.selectbox("Zamknięcie Master Case", ["Klapy standardowe", "Automatyczne dno", "Tacka", "Obwoluta"], key="add_mc_closure")
                    new_mc_board = st.selectbox("Tektura Master Case", ["3-warstwowa", "4-warstwowa", "5-warstwowa", "7-warstwowa"], key="add_mc_board")
                    new_mc_flute = st.selectbox("Fala Master Case", ["E", "F", "B", "C", "EB", "BC", "EE", "AC"], key="add_mc_flute")
            
            if st.form_submit_button("💾 Zapisz do bazy"):
                new_ean_product_clean, new_ean_product_error = validate_ean(new_ean_product)
                new_ean_display_clean, new_ean_display_error = validate_ean(new_ean_display)
                new_ean_mastercase_clean, new_ean_mastercase_error = validate_ean(new_ean_mastercase)
                new_name_clean, new_name_error = validate_product_text(new_name, "Nazwa produktu", required=True)
                new_sku_clean, new_sku_error = validate_product_text(new_sku, "SKU")
                if new_name_error:
                    st.error(new_name_error)
                elif new_sku_error:
                    st.error(new_sku_error)
                elif new_ean_product_error or new_ean_display_error or new_ean_mastercase_error:
                    st.error(new_ean_product_error or new_ean_display_error or new_ean_mastercase_error)
                else:
                    image_data = None
                    if new_image is not None:
                        image_data = {"name": new_image.name, "mime": new_image.type, "b64": base64.b64encode(new_image.getvalue()).decode("ascii")}
                    attachment_data = [
                        {"name": item.name, "mime": item.type, "b64": base64.b64encode(item.getvalue()).decode("ascii")}
                        for item in new_attachments
                    ]
                    dane_prod = {
                        'Dlugosc': new_dl, 'Szerokosc': new_szer, 'Wysokosc': new_wys,
                        'Waga': new_waga / 1000, 'EAN': new_ean_product_clean, 'Typ_Palety': new_pal,
                        'Max_Wysokosc': new_max_h, 'Max_Waga': new_max_w,
                        'displays_in_mc': new_disp_mc, 'boxes_in_display': new_boxes_disp, 'pcs_in_box': new_pcs_box,
                        'SKU': new_sku_clean, 'Producent': new_producer.strip(), 'Klient': new_client.strip(),
                        'Tagi': new_tags.strip(),
                        'Aktywny': new_status == "Aktywny", 'Status': new_status,
                        'Data_ostatniej_weryfikacji': new_verified.isoformat(), 'Zdjecie': image_data,
                        'Zalaczniki': attachment_data, 'Pola_dodatkowe': new_custom_values,
                        'Produkt': {'Dlugosc': new_dl, 'Szerokosc': new_szer, 'Wysokosc': new_wys, 'Masa_netto_g': new_waga, 'EAN': new_ean_product_clean},
                        'Display': {'Dlugosc': new_display_l, 'Szerokosc': new_display_w, 'Wysokosc': new_display_h,
                                    'Masa_pustego_g': new_display_empty_mass, 'Masa_pelnego_g': new_display_full_mass, 'EAN': new_ean_display_clean,
                                    'Mozna_obracac': new_display_rotation, 'Dozwolona_pozycja': new_display_position,
                                    'Pudelka_w_displayu': new_boxes_disp},
                        'MasterCase': {'Dlugosc_wewnetrzna': new_mc_inner_l, 'Szerokosc_wewnetrzna': new_mc_inner_w, 'Wysokosc_wewnetrzna': new_mc_inner_h,
                                       'Dlugosc_zewnetrzna': new_mc_outer_l, 'Szerokosc_zewnetrzna': new_mc_outer_w, 'Wysokosc_zewnetrzna': new_mc_outer_h,
                                       'Tara_kg': new_mc_tare, 'Masa_brutto_max_kg': new_mc_gross_max, 'EAN': new_ean_mastercase_clean, 'FEFCO': new_mc_fefco, 'Zamkniecie': new_mc_closure,
                                       'Tektura': new_mc_board, 'Fala': new_mc_flute, 'Displayow_w_mastercase': new_disp_mc},
                    }
                    try:
                        zapisz_produkt_w_db(new_name_clean, dane_prod)
                        st.session_state['database_products'] = wczytaj_produkty_z_db()
                        st.success(f"Dodano produkt: **{new_name_clean}**!")
                        time.sleep(0.5)
                        st.rerun()
                    except ValueError as error:
                        st.error(str(error))

    with sub_tab2:
        db = st.session_state['database_products']
        if not db:
            st.info("Brak produktów w bazie do edycji.")
        else:
            selected_name = st.selectbox("Wybierz produkt do edycji:", list(db.keys()), key="edit_selector_box")
            previous_locked_product = st.session_state.get("edit_locked_product")
            if previous_locked_product and previous_locked_product != selected_name:
                # Zmiana kartoteki kończy edycję poprzedniej, więc nie zostawiamy
                # po niej blokady należącej do bieżącego użytkownika.
                release_product_lock(previous_locked_product)
            lock_ok, lock_owner = acquire_product_lock(selected_name)
            if not lock_ok:
                st.error(f"Produkt jest obecnie edytowany przez użytkownika: {lock_owner}.")
                st.stop()
            st.session_state["edit_locked_product"] = selected_name
            st.caption("🔒 Edytujesz tę kartotekę — dla innych użytkowników jest ona tymczasowo zablokowana.")
            p_data = db[selected_name]
            saved_product_physical = p_data.get("Produkt", {}) if isinstance(p_data.get("Produkt", {}), dict) else {}
            saved_display_physical = p_data.get("Display", {}) if isinstance(p_data.get("Display", {}), dict) else {}
            saved_mastercase_physical = p_data.get("MasterCase", {}) if isinstance(p_data.get("MasterCase", {}), dict) else {}
            existing_image = p_data.get("Zdjecie")
            if isinstance(existing_image, dict) and existing_image.get("b64"):
                st.image(base64.b64decode(existing_image["b64"]), width=220, caption=existing_image.get("name", "Zdjęcie produktu"))
            for attachment_index, attachment in enumerate(p_data.get("Zalaczniki", []) or []):
                if isinstance(attachment, dict) and attachment.get("b64"):
                    st.download_button(f"📎 {attachment.get('name', 'załącznik')}", base64.b64decode(attachment["b64"]), file_name=attachment.get("name", "zalacznik"), mime=attachment.get("mime", "application/octet-stream"), key=f"product_attachment_{selected_name}_{attachment_index}")
            with st.form(key=f"edit_form_{selected_name}"):
                with st.expander("1. Dane identyfikacyjne i status", expanded=True):
                    e_name = st.text_input("Nazwa produktu", value=selected_name)
                    edit_info_col1, edit_info_col2 = st.columns(2)
                    with edit_info_col1:
                        e_sku = st.text_input("Kod produktu / SKU", value=str(p_data.get('SKU', '')))
                        e_producer = st.text_input("Producent", value=str(p_data.get('Producent', '')))
                    with edit_info_col2:
                        e_client = st.text_input("Klient", value=str(p_data.get('Klient', '')))
                        status_options = ["Roboczy", "Aktywny", "Wycofany", "Oczekuje na weryfikację"]
                        saved_status = p_data.get('Status', "Aktywny" if p_data.get('Aktywny', True) else "Wycofany")
                        e_status = st.selectbox("Status", status_options, index=status_options.index(saved_status) if saved_status in status_options else 0)
                    e_tags = st.text_input("Tagi (oddziel przecinkami)", value=str(p_data.get('Tagi', '')))
                    e_verified = st.date_input("Data ostatniej weryfikacji danych", value=safe_product_date(p_data.get('Data_ostatniej_weryfikacji')))
                    change_reason = st.text_input("Uzasadnienie zmiany (wymagane przy zmianie EAN, masy lub wymiarów)")
                    e_custom_values = {}
                    saved_custom = p_data.get('Pola_dodatkowe', {}) if isinstance(p_data.get('Pola_dodatkowe', {}), dict) else {}
                    for field_name in custom_field_names:
                        e_custom_values[field_name] = st.text_input(field_name, value=str(saved_custom.get(field_name, "")), key=f"edit_custom_{selected_name}_{field_name}")
                with st.expander("2. Zdjęcia i załączniki", expanded=False):
                    e_new_image = st.file_uploader("Zastąp zdjęcie", type=["jpg", "jpeg", "png", "gif"], key=f"edit_product_image_{selected_name}")
                    e_new_attachments = st.file_uploader("Dodaj załączniki", type=["pdf", "jpg", "jpeg", "png", "gif"], accept_multiple_files=True, key=f"edit_product_attachments_{selected_name}")
                with st.expander("3. Domyślne parametry paletyzacji", expanded=False):
                    pal_list = list(PALLET_TYPES.keys())
                    current_pal_val = p_data.get('Typ_Palety', 'EURO')
                    pal_idx = pal_list.index(current_pal_val) if current_pal_val in pal_list else 0
                    e_pal = st.selectbox("Domyślny typ palety", pal_list, index=pal_idx)
                    e_max_h = st.number_input("Limit Wysokości [mm]", value=float(p_data.get('Max_Wysokosc', 2000.0)))
                    e_max_w = st.number_input("Limit Wagi [kg]", value=float(p_data.get('Max_Waga', 500.0)))
                with st.expander("4. Relacje pakowania", expanded=False):
                    e_disp_mc = st.number_input("Displays w Master Case", value=int(p_data.get('displays_in_mc', 1)), step=1)
                    e_boxes_disp = st.number_input("Pudełek w displayu", value=int(p_data.get('boxes_in_display', 1)), step=1)
                    e_pcs_box = st.number_input("Sztuk w pudełku", value=int(p_data.get('pcs_in_box', 1)), step=1)
                with st.expander("5. Parametry fizyczne produktu", expanded=False):
                    e_dl = st.number_input("Produkt - długość [mm]", min_value=1.0, value=float(saved_product_physical.get('Dlugosc', p_data.get('Dlugosc', 200.0))))
                    e_szer = st.number_input("Produkt - szerokość [mm]", min_value=1.0, value=float(saved_product_physical.get('Szerokosc', p_data.get('Szerokosc', 470.0))))
                    e_wys = st.number_input("Produkt - wysokość [mm]", min_value=1.0, value=float(saved_product_physical.get('Wysokosc', p_data.get('Wysokosc', 280.0))))
                    e_waga = st.number_input("Produkt - masa netto [g]", min_value=0.0, value=float(saved_product_physical.get('Masa_netto_g', p_data.get('Waga', 8.0) * 1000)))
                    e_ean_product = st.text_input("EAN produktu", value=str(saved_product_physical.get('EAN', p_data.get('EAN', ''))))
                with st.expander("6. Parametry fizyczne displaya", expanded=True):
                    edit_display_col1, edit_display_col2, edit_display_col3 = st.columns(3)
                    with edit_display_col1:
                        e_display_l = st.number_input("Display - długość [mm]", min_value=0.0, value=float(saved_display_physical.get('Dlugosc', 0.0)))
                        e_display_w = st.number_input("Display - szerokość [mm]", min_value=0.0, value=float(saved_display_physical.get('Szerokosc', 0.0)))
                    with edit_display_col2:
                        e_display_h = st.number_input("Display - wysokość [mm]", min_value=0.0, value=float(saved_display_physical.get('Wysokosc', 0.0)))
                        e_display_empty_mass = st.number_input("Masa pustego displaya [g]", min_value=0.0, value=float(saved_display_physical.get('Masa_pustego_g', 0.0)))
                    with edit_display_col3:
                        e_display_full_mass = st.number_input("Masa pełnego displaya [g]", min_value=0.0, value=float(saved_display_physical.get('Masa_pelnego_g', 0.0)))
                        e_ean_display = st.text_input("EAN displaya", value=str(saved_display_physical.get('EAN', '')))
                        e_display_rotation = st.checkbox("Display można obracać", value=bool(saved_display_physical.get('Mozna_obracac', True)))
                        position_options = ["Poziomo", "Pionowo", "Na boku"]
                        saved_position = saved_display_physical.get('Dozwolona_pozycja', "Poziomo")
                        e_display_position = st.selectbox("Dozwolona pozycja displaya", position_options, index=position_options.index(saved_position) if saved_position in position_options else 0)
                with st.expander("7. Parametry fizyczne kartonu / Master Case", expanded=False):
                    edit_master_col1, edit_master_col2, edit_master_col3 = st.columns(3)
                    with edit_master_col1:
                        e_mc_inner_l = st.number_input("Master Case - długość wewnętrzna [mm]", min_value=0.0, value=float(saved_mastercase_physical.get('Dlugosc_wewnetrzna', 0.0)))
                        e_mc_inner_w = st.number_input("Master Case - szerokość wewnętrzna [mm]", min_value=0.0, value=float(saved_mastercase_physical.get('Szerokosc_wewnetrzna', 0.0)))
                        e_mc_inner_h = st.number_input("Master Case - wysokość wewnętrzna [mm]", min_value=0.0, value=float(saved_mastercase_physical.get('Wysokosc_wewnetrzna', 0.0)))
                    with edit_master_col2:
                        e_mc_outer_l = st.number_input("Master Case - długość zewnętrzna [mm]", min_value=0.0, value=float(saved_mastercase_physical.get('Dlugosc_zewnetrzna', 0.0)))
                        e_mc_outer_w = st.number_input("Master Case - szerokość zewnętrzna [mm]", min_value=0.0, value=float(saved_mastercase_physical.get('Szerokosc_zewnetrzna', 0.0)))
                        e_mc_outer_h = st.number_input("Master Case - wysokość zewnętrzna [mm]", min_value=0.0, value=float(saved_mastercase_physical.get('Wysokosc_zewnetrzna', 0.0)))
                    with edit_master_col3:
                        e_mc_tare = st.number_input("Tara Master Case [kg]", min_value=0.0, value=float(saved_mastercase_physical.get('Tara_kg', 0.0)))
                        e_mc_gross_max = st.number_input("Maks. masa brutto Master Case [kg]", min_value=0.0, value=float(saved_mastercase_physical.get('Masa_brutto_max_kg', 0.0)))
                        e_ean_mastercase = st.text_input("EAN Master Case", value=str(saved_mastercase_physical.get('EAN', '')))
                        fefco_options = ["0201", "0215", "0427", "0470", "Inny"]
                        board_options = ["3-warstwowa", "4-warstwowa", "5-warstwowa", "7-warstwowa"]
                        flute_options = ["E", "F", "B", "C", "EB", "BC", "EE", "AC"]
                        saved_fefco = saved_mastercase_physical.get('FEFCO', "0201")
                        saved_board = saved_mastercase_physical.get('Tektura', "3-warstwowa")
                        saved_flute = saved_mastercase_physical.get('Fala', "E")
                        closure_options = ["Klapy standardowe", "Automatyczne dno", "Tacka", "Obwoluta"]
                        saved_closure = saved_mastercase_physical.get('Zamkniecie', "Klapy standardowe")
                        e_mc_fefco = st.selectbox("FEFCO Master Case", fefco_options, index=fefco_options.index(saved_fefco) if saved_fefco in fefco_options else 0)
                        e_mc_closure = st.selectbox("Zamknięcie Master Case", closure_options, index=closure_options.index(saved_closure) if saved_closure in closure_options else 0)
                        e_mc_board = st.selectbox("Tektura Master Case", board_options, index=board_options.index(saved_board) if saved_board in board_options else 0)
                        e_mc_flute = st.selectbox("Fala Master Case", flute_options, index=flute_options.index(saved_flute) if saved_flute in flute_options else 0)
                confirm_delete = st.checkbox("Potwierdzam trwałe usunięcie produktu.", key=f"confirm_delete_{selected_name}")
                
                col_e1, col_e2 = st.columns(2)
                with col_e1:
                    update_btn = st.form_submit_button("💾 Zapisz zmiany")
                with col_e2:
                    delete_btn = st.form_submit_button("📁 Przenieś do archiwum", disabled=not confirm_delete)

                if update_btn:
                    e_ean_product_clean, e_ean_product_error = validate_ean(e_ean_product)
                    e_ean_display_clean, e_ean_display_error = validate_ean(e_ean_display)
                    e_ean_mastercase_clean, e_ean_mastercase_error = validate_ean(e_ean_mastercase)
                    e_name_clean, e_name_error = validate_product_text(e_name, "Nazwa produktu", required=True)
                    e_sku_clean, e_sku_error = validate_product_text(e_sku, "SKU")
                    critical_changed = (
                        e_ean_product_clean != safe_ean(p_data.get('EAN', '')) or
                        any(float(p_data.get(key, 0)) != float(value) for key, value in {
                            'Dlugosc': e_dl, 'Szerokosc': e_szer, 'Wysokosc': e_wys, 'Waga': e_waga
                        }.items())
                    )
                    if e_name_error:
                        st.error(e_name_error)
                    elif e_sku_error:
                        st.error(e_sku_error)
                    elif e_ean_product_error or e_ean_display_error or e_ean_mastercase_error:
                        st.error(e_ean_product_error or e_ean_display_error or e_ean_mastercase_error)
                    elif critical_changed and not change_reason.strip():
                        st.error("Podaj uzasadnienie zmiany EAN, masy lub wymiarów.")
                    else:
                        updated_image = p_data.get('Zdjecie')
                        if e_new_image is not None:
                            updated_image = {"name": e_new_image.name, "mime": e_new_image.type, "b64": base64.b64encode(e_new_image.getvalue()).decode("ascii")}
                        updated_attachments = list(p_data.get('Zalaczniki', []) or []) + [
                            {"name": item.name, "mime": item.type, "b64": base64.b64encode(item.getvalue()).decode("ascii")}
                            for item in e_new_attachments
                        ]
                        nowe_dane = {
                            'Dlugosc': e_dl, 'Szerokosc': e_szer, 'Wysokosc': e_wys,
                            'Waga': e_waga / 1000, 'EAN': e_ean_product_clean, 'Typ_Palety': e_pal,
                            'Max_Wysokosc': e_max_h, 'Max_Waga': e_max_w,
                            'displays_in_mc': e_disp_mc, 'boxes_in_display': e_boxes_disp, 'pcs_in_box': e_pcs_box,
                            'SKU': e_sku_clean, 'Producent': e_producer.strip(), 'Klient': e_client.strip(),
                            'Tagi': e_tags.strip(),
                            'Aktywny': e_status == "Aktywny", 'Status': e_status,
                            'Data_ostatniej_weryfikacji': e_verified.isoformat(), 'Zdjecie': updated_image,
                            'Zalaczniki': updated_attachments, 'Pola_dodatkowe': e_custom_values,
                            'Produkt': {'Dlugosc': e_dl, 'Szerokosc': e_szer, 'Wysokosc': e_wys, 'Masa_netto_g': e_waga, 'EAN': e_ean_product_clean},
                            'Display': {'Dlugosc': e_display_l, 'Szerokosc': e_display_w, 'Wysokosc': e_display_h,
                                        'Masa_pustego_g': e_display_empty_mass, 'Masa_pelnego_g': e_display_full_mass, 'EAN': e_ean_display_clean,
                                        'Mozna_obracac': e_display_rotation, 'Dozwolona_pozycja': e_display_position,
                                        'Pudelka_w_displayu': e_boxes_disp},
                            'MasterCase': {'Dlugosc_wewnetrzna': e_mc_inner_l, 'Szerokosc_wewnetrzna': e_mc_inner_w, 'Wysokosc_wewnetrzna': e_mc_inner_h,
                                           'Dlugosc_zewnetrzna': e_mc_outer_l, 'Szerokosc_zewnetrzna': e_mc_outer_w, 'Wysokosc_zewnetrzna': e_mc_outer_h,
                                           'Tara_kg': e_mc_tare, 'Masa_brutto_max_kg': e_mc_gross_max, 'EAN': e_ean_mastercase_clean, 'FEFCO': e_mc_fefco, 'Zamkniecie': e_mc_closure,
                                           'Tektura': e_mc_board, 'Fala': e_mc_flute, 'Displayow_w_mastercase': e_disp_mc},
                        }
                        try:
                            for db_name, db_data in wczytaj_produkty_z_db().items():
                                if db_name != selected_name and e_ean_product_clean and safe_ean(db_data.get('EAN', '')) == e_ean_product_clean:
                                    raise ValueError(f"Kod EAN produktu {e_ean_product_clean} jest już przypisany do produktu: {db_name}.")
                            update_product_in_db(selected_name, e_name_clean, nowe_dane, change_reason)
                            release_product_lock(selected_name)
                            st.session_state['database_products'] = wczytaj_produkty_z_db()
                            st.success(f"Zaktualizowano produkt: **{e_name_clean}**!")
                            time.sleep(0.5)
                            st.rerun()
                        except ValueError as error:
                            st.error(str(error))

                if delete_btn:
                    archive_product(selected_name, change_reason)
                    st.session_state['database_products'] = wczytaj_produkty_z_db()
                    st.success(f"Przeniesiono produkt „{selected_name}” do archiwum.")
                    time.sleep(0.5)
                    st.rerun()

    with sub_tab3:
        current_db = wczytaj_produkty_z_db()
        active_db = {name: data for name, data in current_db.items() if data.get('Aktywny', True) is not False}
        if not active_db:
            st.info("Brak aktywnych produktów w bazie.")
        else:
            if len(active_db) < len(current_db):
                st.caption(f"Produkty nieaktywne ({len(current_db) - len(active_db)}) są ukryte na liście obliczeń.")
            sel_prod = st.selectbox("Wybierz produkt z bazy do obliczeń:", list(active_db.keys()), key="calc_from_db_select")
            p_inf = active_db[sel_prod]
            integration_col1, integration_col2 = st.columns(2)
            with integration_col1:
                if st.button("➕ Dodaj do Packing List", key="catalog_to_packing"):
                    st.session_state.setdefault('packing_list_items', [])
                    existing_item = next((item for item in st.session_state['packing_list_items'] if item.get("Produkt") == sel_prod), None)
                    if existing_item:
                        existing_item["Liczba Kartonów"] = int(existing_item.get("Liczba Kartonów", 0)) + 1
                    else:
                        st.session_state['packing_list_items'].append({"Produkt": sel_prod, "EAN": str(p_inf.get("EAN", "Brak")), "Liczba Kartonów": 1})
                    st.success("Produkt przekazano do Packing List.")
            with integration_col2:
                if st.button("📄 Użyj w zamówieniu (moduł 9)", key="catalog_to_order"):
                    st.session_state["product_to_order"] = {"name": sel_prod, "sku": p_inf.get("SKU", ""), "ean": p_inf.get("EAN", "")}
                    st.success("Produkt zostanie wstawiony do pola nazwy po otwarciu modułu 9.")
            if st.button("🚀 Oblicz układ dla wybranego produktu"):
                wykonaj_obliczenia_i_wyswietl(
                    sel_prod,
                    float(p_inf.get('Dlugosc', 200.0)),
                    float(p_inf.get('Szerokosc', 470.0)),
                    float(p_inf.get('Wysokosc', 280.0)),
                    float(p_inf.get('Waga', 8.0)),
                    str(p_inf.get('EAN', '')),
                    str(p_inf.get('Typ_Palety', 'EURO')),
                    float(p_inf.get('Max_Wysokosc', 2000.0)),
                    float(p_inf.get('Max_Waga', 500.0)),
                    int(p_inf.get('displays_in_mc', 1)),
                    int(p_inf.get('boxes_in_display', 1)),
                    int(p_inf.get('pcs_in_box', 1)),
                    "db_calc"
                )

    with sub_tab4:
        st.markdown("#### Archiwum produktów")
        with sqlite3.connect(DB_FILENAME) as conn:
            archived_rows = conn.execute('SELECT original_name, data, archived_at, archived_by, reason FROM archived_products ORDER BY archived_at DESC').fetchall()
        if archived_rows:
            archive_view = pd.DataFrame([
                {"Produkt": row[0], "Data archiwizacji": row[2], "Użytkownik": row[3], "Uzasadnienie": row[4]}
                for row in archived_rows
            ])
            st.dataframe(archive_view, width="stretch")
            archived_name = st.selectbox("Produkt do przywrócenia", [row[0] for row in archived_rows], key="restore_archived_product")
            if st.button("↩️ Przywróć produkt z archiwum"):
                try:
                    restore_archived_product(archived_name)
                    st.session_state['database_products'] = wczytaj_produkty_z_db()
                    st.success("Produkt przywrócono do aktywnej bazy.")
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))
        else:
            st.info("Archiwum produktów jest puste.")

        st.markdown("#### Historia i porównanie wersji")
        history_products = list(wczytaj_produkty_z_db().keys()) + [row[0] for row in archived_rows]
        if history_products:
            history_name = st.selectbox("Wybierz produkt", sorted(set(history_products)), key="product_history_name")
            history_items = get_product_history(history_name)
            if history_items:
                st.dataframe(pd.DataFrame([{key: value for key, value in item.items() if key not in ("Przed", "Po")} for item in history_items]), width="stretch")
                version_choice = st.selectbox("Wersja do porównania", list(range(len(history_items))), format_func=lambda i: f"{history_items[i]['Data']} — {history_items[i]['Akcja']}")
                selected_version = history_items[version_choice]
                compare_rows = []
                all_keys = sorted(set(selected_version["Przed"]) | set(selected_version["Po"]))
                for key in all_keys:
                    before, after = selected_version["Przed"].get(key), selected_version["Po"].get(key)
                    if before != after:
                        # Historia może mieszać daty, liczby i flagi; do tabeli porównawczej
                        # przekazujemy jednolity tekst, aby Arrow nie musiał zgadywać typu kolumny.
                        compare_rows.append({
                            "Pole": str(key),
                            "Poprzednia wartość": "" if before is None else str(before),
                            "Bieżąca wartość": "" if after is None else str(after),
                        })
                if compare_rows:
                    st.dataframe(pd.DataFrame(compare_rows), width="stretch")
                else:
                    st.info("Wybrana wersja nie zawiera zmian pól do porównania.")
            else:
                st.info("Brak zapisanej historii dla wybranego produktu.")

        st.markdown("#### Duplikuj produkt")
        active_names = list(wczytaj_produkty_z_db().keys())
        if active_names:
            duplicate_source = st.selectbox("Produkt źródłowy", active_names, key="duplicate_product_source")
            duplicate_name = st.text_input("Nazwa nowej pozycji", value=f"Kopia — {duplicate_source}", key="duplicate_product_name")
            if st.button("⧉ Utwórz kopię produktu"):
                copy_name, copy_error = validate_product_text(duplicate_name, "Nazwa produktu", required=True)
                if copy_error:
                    st.error(copy_error)
                elif copy_name in wczytaj_produkty_z_db():
                    st.error("Produkt o tej nazwie już istnieje.")
                else:
                    copied_data = dict(wczytaj_produkty_z_db()[duplicate_source])
                    copied_data["EAN"] = ""
                    copied_data["SKU"] = ""
                    copied_data["Status"] = "Roboczy"
                    copied_data["Aktywny"] = False
                    zapisz_produkt_w_db(copy_name, copied_data)
                    st.session_state['database_products'] = wczytaj_produkty_z_db()
                    st.success("Utworzono kopię jako produkt roboczy. Uzupełnij EAN i SKU przed aktywacją.")
                    st.rerun()

    with sub_tab5:
        is_product_admin = st.session_state.get("user_role") == "Administrator"
        st.markdown("#### Blokady edycji")
        st.caption("Możesz usunąć tylko blokady wygasłe albo wszystkie, także aktywne.")
        with st.container(horizontal=True):
            remove_expired_locks = st.button(
                "Usuń wygasłe blokady",
                icon=":material/lock_open:",
                key="remove_expired_product_locks",
                disabled=not is_product_admin,
            )
            remove_all_locks = st.button(
                "Usuń wszystkie blokady",
                icon=":material/delete_forever:",
                key="remove_all_product_locks",
                disabled=not is_product_admin,
                type="secondary",
            )
        if remove_expired_locks:
            removed_locks = remove_expired_product_locks()
            if removed_locks:
                st.success(f"Usunięto wygasłe blokady: {len(removed_locks)}.")
            else:
                st.info("Nie znaleziono wygasłych blokad.")
        if remove_all_locks:
            removed_count = remove_all_product_locks()
            if removed_count:
                st.success(f"Usunięto wszystkie blokady: {removed_count}.")
            else:
                st.info("Nie znaleziono blokad do usunięcia.")

        st.markdown("#### Własne pola dodatkowe")
        if is_product_admin:
            with st.form("add_custom_product_field"):
                custom_field_name = st.text_input("Nazwa nowego pola")
                add_custom_field = st.form_submit_button("➕ Dodaj pole")
            if add_custom_field:
                cleaned_name, field_error = validate_product_text(custom_field_name, "Nazwa pola", required=True)
                if field_error:
                    st.error(field_error)
                else:
                    with sqlite3.connect(DB_FILENAME) as conn:
                        conn.execute('INSERT OR IGNORE INTO product_custom_fields (field_name, active) VALUES (?, 1)', (cleaned_name,))
                    st.rerun()
            if custom_field_names:
                st.write("Aktywne pola: " + ", ".join(custom_field_names))
        else:
            st.info("Tylko administrator może definiować własne pola dodatkowe.")

        st.markdown("#### Kopia zapasowa bazy")
        st.caption("Aplikacja tworzy automatyczną kopię SQLite maksymalnie raz na 24 godziny w folderze backups_bazy_produktow.")
        if os.path.exists(DB_FILENAME):
            with open(DB_FILENAME, "rb") as database_file:
                st.download_button("⬇️ Eksportuj kopię bazy", data=database_file.read(), file_name="baza_produktow_backup.db", mime="application/octet-stream", disabled=not is_product_admin)
        restore_database = st.file_uploader("Przywróć kopię bazy (.db)", type=["db"], key="restore_product_database")
        restore_confirm = st.checkbox("Rozumiem, że przywrócenie zastąpi bieżącą bazę produktów.", key="restore_database_confirm")
        if restore_database is not None and restore_confirm and st.button("⚠️ Przywróć wskazaną kopię", disabled=not is_product_admin):
            restored_bytes = restore_database.getvalue()
            if not restored_bytes.startswith(b"SQLite format 3"):
                st.error("Wybrany plik nie jest prawidłową kopią bazy SQLite.")
            else:
                safety_copy = f"{DB_FILENAME}.before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
                shutil.copy2(DB_FILENAME, safety_copy)
                with open(DB_FILENAME, "wb") as target_database:
                    target_database.write(restored_bytes)
                st.session_state['database_products'] = wczytaj_produkty_z_db()
                st.success("Przywrócono bazę. Poprzednia wersja została zabezpieczona obok pliku bazy.")
                st.rerun()

    # Importy zewnętrzne (w tym Subiekt) przeniesiono do modułu 20.
    st.info("Importy z Subiekta oraz integracje Excel/CSV są dostępne w module 20: 🔌 Integracje.")

def generuj_pdf_instrukcje_ukladania(result, zabezpieczenia, store_document=False):
    """Tworzy instrukcję; do Centrum zlecenia zapisuje ją tylko na żądanie."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=38, rightMargin=38, topMargin=42, bottomMargin=42
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "PalletInstructionTitle", parent=styles["Title"], fontName=FONT_BOLD,
        fontSize=20, leading=24, textColor=colors.HexColor("#123B69"), spaceAfter=5,
    )
    subtitle = ParagraphStyle(
        "PalletInstructionSubtitle", parent=styles["Normal"], fontName=FONT_REGULAR,
        fontSize=9, leading=12, textColor=colors.HexColor("#5B6470"), spaceAfter=14,
    )
    heading = ParagraphStyle(
        "PalletInstructionHeading", parent=styles["Heading2"], fontName=FONT_BOLD,
        fontSize=12, leading=15, textColor=colors.HexColor("#123B69"), spaceBefore=12, spaceAfter=6,
    )
    body = ParagraphStyle(
        "PalletInstructionBody", parent=styles["Normal"], fontName=FONT_REGULAR,
        fontSize=9.5, leading=13,
    )
    small = ParagraphStyle(
        "PalletInstructionSmall", parent=body, fontSize=8, leading=10, textColor=colors.HexColor("#5B6470"),
    )

    def footer(pdf_canvas, pdf_doc):
        pdf_canvas.saveState()
        pdf_canvas.setStrokeColor(colors.HexColor("#D7DEE8"))
        pdf_canvas.line(38, 28, A4[0] - 38, 28)
        pdf_canvas.setFont(FONT_REGULAR, 7.5)
        pdf_canvas.setFillColor(colors.HexColor("#5B6470"))
        pdf_canvas.drawString(38, 17, "Instrukcja operacyjna - przygotowana przez Kalkulator")
        pdf_canvas.drawRightString(A4[0] - 38, 17, f"Strona {pdf_doc.page}")
        pdf_canvas.restoreState()

    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    product_name = escape(str(result["Produkt"]))
    pallet_name = escape(str(result["Paleta"]))
    orientation_name = escape(str(result["Orientacja"]))
    story = [
        Paragraph("INSTRUKCJA UKŁADANIA PALETY", title),
        Paragraph(f"Dokument operacyjny dla magazynu | Wygenerowano: {now}", subtitle),
    ]
    product_table = Table([
        [Paragraph("PRODUKT", small), Paragraph("PALETA", small), Paragraph("ORIENTACJA KARTONU", small)],
        [Paragraph(product_name, body), Paragraph(pallet_name, body), Paragraph(orientation_name, body)],
    ], colWidths=[170, 130, 189])
    product_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF1F8")),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#C8D4E3")),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D7DEE8")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story += [product_table, Spacer(1, 12), Paragraph("Parametry docelowe", heading)]

    parameters = [
        ["Kartonów na warstwę", str(result["Kartonów/warstwę"]), "Pełnych warstw", str(result["Pełnych warstw"])],
        ["Pojemność pełnej palety", str(result["Pojemność palety"]), "Liczba palet", str(result["Liczba palet"])],
        ["Ostatnia paleta", f"{result['Kartonów na ostatniej palecie']} kart. / {result['Warstw na ostatniej palecie']} warstw", "Wysokość", f"{result['Wysokość palety mm']} mm"],
        ["Masa brutto", f"{result['Masa brutto/paleta kg']} kg", "Stabilność", f"{result['Stabilność /100']} / 100"],
    ]
    parameter_table = Table(parameters, colWidths=[132, 112, 132, 113])
    parameter_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#5B6470")),
        ("TEXTCOLOR", (2, 0), (2, -1), colors.HexColor("#5B6470")),
        ("FONTNAME", (0, 0), (-1, -1), FONT_REGULAR),
        ("FONTNAME", (1, 0), (1, -1), FONT_BOLD),
        ("FONTNAME", (3, 0), (3, -1), FONT_BOLD),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D7DEE8")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
    ]))
    story += [parameter_table, Paragraph("Kolejność wykonywania", heading)]
    security_text = escape(", ".join(zabezpieczenia) if zabezpieczenia else "brak dodatkowych zabezpieczeń")
    steps = [
        "Sprawdź stan palety: powierzchnia musi być sucha, czysta, bez uszkodzonych desek i wystających elementów.",
        f"Ustaw pierwszą warstwę: <b>{result['Kartonów/warstwę']} kart.</b>, orientacja: <b>{orientation_name}</b>. Kartony ustawiaj równo do krawędzi palety.",
        f"Buduj kolejne warstwy do maksymalnie <b>{result['Pełnych warstw']}</b> pełnych warstw. Zachowaj równą płaszczyznę każdej warstwy.",
        f"Na ostatniej palecie przygotuj <b>{result['Kartonów na ostatniej palecie']} kart.</b> w maksymalnie <b>{result['Warstw na ostatniej palecie']}</b> warstwach.",
        f"Zastosuj zabezpieczenia: <b>{security_text}</b>. Folia i narożniki nie mogą zasłaniać etykiety logistycznej.",
        f"Przed przekazaniem do wysyłki potwierdź wysokość do <b>{result['Wysokość palety mm']} mm</b> oraz masę brutto do <b>{result['Masa brutto/paleta kg']} kg</b>.",
    ]
    for number, step in enumerate(steps, 1):
        story.append(Paragraph(f"<b>{number}.</b> {step}", body))
        story.append(Spacer(1, 4))

    story += [Paragraph("Kontrola końcowa", heading)]
    checks = [
        "Liczba kartonów i warstw zgodna z instrukcją.",
        "Paleta stabilna; ładunek nie wystaje poza jej obrys.",
        "Zabezpieczenia założone, etykieta logistyczna widoczna.",
        "Paleta oznaczona numerem zlecenia / miejscem docelowym.",
    ]
    check_table = Table([[Paragraph(f"□  {item}", body)] for item in checks], colWidths=[489])
    check_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#C8D4E3")),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D7DEE8")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
    ]))
    story += [check_table, Spacer(1, 16)]
    story += [Paragraph("Wykonał: ______________________________    Data / godzina: ______________________________", body)]
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    pdf_bytes = buffer.getvalue()
    product_name = re.sub(r"[^A-Za-z0-9_-]+", "_", str(result.get("Produkt", "produkt"))).strip("_") or "produkt"
    if store_document:
        store_order_pdf("Instrukcja paletyzacji", pdf_bytes, f"instrukcja_ukladania_{product_name}.pdf")
    return pdf_bytes

