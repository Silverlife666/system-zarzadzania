"""Widok wydzielony z app.py; przejściowy most zależności."""

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





def render_palletization_screen(st, deps):
    for _bridge_name, _bridge_value in deps.items():
        if not _bridge_name.startswith("__"):
            globals()[_bridge_name] = _bridge_value
    del _bridge_name, _bridge_value
    st.subheader("📐 Kalkulator paletyzacji i logistyki")
    st.caption("Wynik można przekazać do Packing List, zamówienia/Karty Pracy, transportu oraz PPWR.")
    products_for_calc = wczytaj_produkty_z_db()
    custom_pallets = {**load_custom_pallets(), **st.session_state.get("custom_pallets", {})}
    st.session_state["custom_pallets"] = custom_pallets
    all_pallets = {**PALLET_TYPES, **custom_pallets}
    if "pal_calc_last" in st.session_state and st.button("↩️ Wczytaj ostatnie obliczenie"):
        for key, value in st.session_state["pal_calc_last"].items():
            st.session_state[key] = value
        st.rerun()
    if st.button("🧹 Wyczyść formularz"):
        for key in ["calc_product", "calc_name", "calc_l", "calc_w", "calc_h", "calc_wg", "calc_qty"]:
            st.session_state.pop(key, None)
        st.rerun()

    with st.expander("⚙️ Własne typy palet", expanded=False):
        with st.form("custom_pallet_form"):
            cp_name = st.text_input("Nazwa palety")
            cp1, cp2, cp3 = st.columns(3)
            with cp1: cp_l = st.number_input("Długość [mm]", min_value=1.0, value=1200.0)
            with cp2: cp_w = st.number_input("Szerokość [mm]", min_value=1.0, value=800.0)
            with cp3: cp_h = st.number_input("Wysokość / tara [mm]", min_value=1.0, value=150.0)
            cp_weight = st.number_input("Tara palety [kg]", min_value=0.0, value=15.0)
            cp_max_h = st.number_input("Maks. wysokość [mm]", min_value=1.0, value=2000.0)
            cp_max_w = st.number_input("Nośność [kg]", min_value=1.0, value=500.0)
            cp_cost = st.number_input("Koszt palety [PLN]", min_value=0.0, value=0.0)
            if st.form_submit_button("➕ Zapisz własną paletę") and cp_name.strip():
                custom_pallets[cp_name.strip()] = {"L": cp_l, "W": cp_w, "H": cp_h, "WEIGHT": cp_weight, "MAX_H": cp_max_h, "MAX_W": cp_max_w, "COST": cp_cost}
                save_custom_pallets(custom_pallets)
                st.session_state["custom_pallets"] = custom_pallets
                st.rerun()
        if custom_pallets:
            st.caption("Własne palety są zapisane w pliku i dostępne w modułach 2 oraz 4.")
            st.dataframe(pd.DataFrame([{"Nazwa": name, **data} for name, data in custom_pallets.items()]), width="stretch", hide_index=True)
            pallet_to_delete = st.selectbox("Usuń własną paletę", ["—"] + sorted(custom_pallets), key="delete_custom_pallet")
            if pallet_to_delete != "—" and st.button("🗑️ Usuń wybraną paletę"):
                del custom_pallets[pallet_to_delete]
                save_custom_pallets(custom_pallets)
                st.session_state["custom_pallets"] = custom_pallets
                st.rerun()

    with st.expander("🧰 Zabezpieczenia palety", expanded=False):
        sec_col1, sec_col2, sec_col3 = st.columns(3)
        with sec_col1:
            use_stretch = st.checkbox("Folia stretch", value=True)
            stretch_mass = st.number_input("Masa folii / paletę [kg]", min_value=0.0, value=0.3)
        with sec_col2:
            use_layer = st.checkbox("Przekładki", value=False)
            layer_mass = st.number_input("Masa przekładki [kg]", min_value=0.0, value=0.05)
        with sec_col3:
            use_corners = st.checkbox("Narożniki / kaptur", value=False)
            corner_mass = st.number_input("Masa narożników/kaptura [kg]", min_value=0.0, value=0.2)

    calc_source = st.radio("Źródło danych kartonu", ["Produkt z sekcji 1", "Ręczne dane", "Parametry z Box Rightsizing (moduł 7)"], horizontal=True)
    selected_product = None
    source_data = {}
    calc_packaging_level = "Master Case"
    if calc_source == "Produkt z sekcji 1" and products_for_calc:
        selected_product = st.selectbox("Produkt", list(products_for_calc), key="calc_product")
        source_data = products_for_calc[selected_product]
        calc_packaging_level = st.selectbox(
            "Poziom, który ma być paletyzowany", PACKAGING_LEVEL_OPTIONS,
            index=PACKAGING_LEVEL_OPTIONS.index("Master Case"), key="calc_packaging_level",
            help="Wybierz fizyczny poziom opakowania. Dla wysyłki kartonów wybierz Master Case.",
        )
    elif calc_source.startswith("Parametry"):
        source_data = st.session_state.get("box_rightsizing_result", {})
        calc_packaging_level = "Master Case"
        if not source_data:
            st.warning("Brak zapisanego wyniku modułu 7 — wprowadź dane ręcznie lub oblicz Box Rightsizing.")
    calc_physical_data = get_packaging_level_physical(source_data, calc_packaging_level) if source_data else {}
    refresh_calc_physical_values = False
    if calc_physical_data:
        calc_signature = f"{calc_source}|{selected_product or source_data.get('source_product', '')}|{calc_packaging_level}"
        if st.session_state.get("_calc_physical_signature") != calc_signature:
            refresh_calc_physical_values = True
            st.session_state["_calc_physical_signature"] = calc_signature
        st.caption(
            f"Do obliczeń pobrano poziom: **{calc_physical_data['label']}** — "
            f"{calc_physical_data['Dlugosc']:.0f} × {calc_physical_data['Szerokosc']:.0f} × {calc_physical_data['Wysokosc']:.0f} mm, "
            f"{calc_physical_data['Waga']:.3f} kg; EAN: {calc_physical_data.get('EAN') or 'brak'}"
        )
    unit_col1, unit_col2 = st.columns(2)
    with unit_col1: size_unit = st.selectbox("Jednostka wymiarów", ["mm", "cm"], key="calc_size_unit")
    with unit_col2: weight_unit = st.selectbox("Jednostka masy", ["kg", "g"], key="calc_weight_unit")
    conv_length, conv_weight = (1.0 if size_unit == "mm" else 10.0), (1.0 if weight_unit == "kg" else 0.001)
    if refresh_calc_physical_values:
        st.session_state.update({
            "calc_l": calc_physical_data.get("Dlugosc", 0) / conv_length,
            "calc_w": calc_physical_data.get("Szerokosc", 0) / conv_length,
            "calc_h": calc_physical_data.get("Wysokosc", 0) / conv_length,
            "calc_wg": calc_physical_data.get("Waga", 0) / conv_weight,
        })
    else:
        previous_units = st.session_state.get("_calc_input_units", {})
        previous_length_factor = 1.0 if previous_units.get("size") == "mm" else 10.0
        previous_weight_factor = 1.0 if previous_units.get("weight") == "kg" else 0.001
        if previous_units.get("size") and previous_units.get("size") != size_unit:
            for key in ("calc_l", "calc_w", "calc_h"):
                if key in st.session_state:
                    st.session_state[key] = float(st.session_state[key]) * previous_length_factor / conv_length
        if previous_units.get("weight") and previous_units.get("weight") != weight_unit and "calc_wg" in st.session_state:
            st.session_state["calc_wg"] = float(st.session_state["calc_wg"]) * previous_weight_factor / conv_weight
    st.session_state["_calc_input_units"] = {"size": size_unit, "weight": weight_unit}
    # Widgety z kluczem pobierają wartość z session_state. Ustawiamy domyślne
    # tylko przed ich utworzeniem, zamiast łączyć `value=` z tym samym kluczem.
    # To usuwa ostrzeżenie Streamlit i nie nadpisuje ręcznej edycji operatora.
    calc_defaults = {
        "calc_name": selected_product or source_data.get("Nazwa", "Produkt niestandardowy"),
        "calc_l": float(calc_physical_data.get("Dlugosc", source_data.get("Dlugosc", source_data.get("length", 200.0)))) / conv_length,
        "calc_w": float(calc_physical_data.get("Szerokosc", source_data.get("Szerokosc", source_data.get("width", 470.0)))) / conv_length,
        "calc_h": float(calc_physical_data.get("Wysokosc", source_data.get("Wysokosc", source_data.get("height", 280.0)))) / conv_length,
        "calc_wg": float(calc_physical_data.get("Waga", source_data.get("Waga", source_data.get("weight", 8.0)))) / conv_weight,
        "calc_qty": 1,
    }
    for key, default_value in calc_defaults.items():
        st.session_state.setdefault(key, default_value)
    inputs1, inputs2, inputs3 = st.columns(3)
    with inputs1:
        calc_name = st.text_input("Nazwa produktu", key="calc_name")
        p_l_raw = st.number_input(f"Długość zewnętrzna [{size_unit}]", min_value=0.0, key="calc_l")
        p_w_raw = st.number_input(f"Szerokość zewnętrzna [{size_unit}]", min_value=0.0, key="calc_w")
    with inputs2:
        p_h_raw = st.number_input(f"Wysokość zewnętrzna [{size_unit}]", min_value=0.0, key="calc_h")
        p_weight_raw = st.number_input(f"Masa kartonu [{weight_unit}]", min_value=0.0, key="calc_wg")
        p_qty = st.number_input(f"Liczba pozycji do wysłania ({calc_packaging_level})", min_value=1, step=1, key="calc_qty")
    with inputs3:
        p_type = st.selectbox("Typ palety", list(all_pallets), key="calc_pt")
        orientation = st.selectbox("Orientacja kartonu na warstwie", ["Automatycznie najlepsza", "Oryginalna", "Obrót 90°"], key="calc_orientation")
        st.session_state.setdefault("calc_mw", float(all_pallets[p_type].get("MAX_W", source_data.get("Max_Waga", 500.0))))
        st.session_state.setdefault("calc_mh", float(all_pallets[p_type].get("MAX_H", source_data.get("Max_Wysokosc", 2000.0))))
        st.session_state.setdefault("calc_height_tolerance", 20.0)
        p_max_w = st.number_input("Limit masy palety [kg]", min_value=1.0, key="calc_mw")
        p_max_h = st.number_input("Limit wysokości palety [mm]", min_value=1.0, key="calc_mh")
        height_tolerance = st.number_input(
            "Tolerancja wysokości [mm]", min_value=0.0, step=1.0,
            key="calc_height_tolerance",
            help="Dopuszczalne technicznie przekroczenie limitu wysokości. Ustaw 0 dla limitu bez tolerancji.",
        )
    with st.expander("Wymiary wewnętrzne i relacja opakowania", expanded=False):
        inner_l = st.number_input(f"Długość wewnętrzna [{size_unit}]", min_value=0.0, value=0.0)
        inner_w = st.number_input(f"Szerokość wewnętrzna [{size_unit}]", min_value=0.0, value=0.0)
        inner_h = st.number_input(f"Wysokość wewnętrzna [{size_unit}]", min_value=0.0, value=0.0)
        r1, r2, r3 = st.columns(3)
        relacje_zrodla = calc_physical_data.get("relacje", {})
        with r1: displays_mc = st.number_input("Displayów / Master Case", min_value=1, value=int(relacje_zrodla.get("displays_per_mastercase", source_data.get("displays_in_mc", 1))))
        with r2: boxes_display = st.number_input("Pudełek / display", min_value=1, value=int(relacje_zrodla.get("boxes_per_display", source_data.get("boxes_in_display", 1))))
        with r3: pcs_box = st.number_input("Sztuk / pudełko", min_value=1, value=int(relacje_zrodla.get("pieces_per_box", source_data.get("pcs_in_box", 1))))
        st.caption(f"1 Master Case = {displays_mc} × {boxes_display} × {pcs_box} = {displays_mc * boxes_display * pcs_box} szt.")

    effective_max_height = p_max_h + height_tolerance
    if st.button("🧮 Oblicz paletyzację", type="primary"):
        p_l, p_w, p_h, p_weight = p_l_raw * conv_length, p_w_raw * conv_length, p_h_raw * conv_length, p_weight_raw * conv_weight
        if min(p_l, p_w, p_h, p_weight) <= 0:
            st.error("Nie można obliczyć: wszystkie wymiary i masa muszą być większe od zera.")
        else:
            pallet = all_pallets[p_type]
            layout_variants = [
                ("Oryginalna", layout_for_orientation(pallet["L"], pallet["W"], p_l, p_w)),
                ("Obrót 90°", layout_for_orientation(pallet["L"], pallet["W"], p_w, p_l)),
            ]
            if orientation == "Automatycznie najlepsza":
                layout_variants.append(("Mieszany / zaawansowany", mixed_layout_for_orientation(pallet["L"], pallet["W"], p_l, p_w)))
            else:
                layout_variants = [item for item in layout_variants if item[0] == orientation]
            variant_name, layer_layout = max(layout_variants, key=lambda item: len(item[1]))
            boxes_layer = len(layer_layout)
            security_mass = (stretch_mass if use_stretch else 0) + (corner_mass if use_corners else 0)
            # W praktyce wysokość palety i kartonów może różnić się o kilka
            # milimetrów. Tolerancja jest jawna i może zostać wyzerowana.
            layers_height = int(max(0, effective_max_height - pallet["H"]) // p_h)
            layers_weight = int(max(0, p_max_w - pallet["WEIGHT"] - security_mass) // (boxes_layer * p_weight)) if boxes_layer else 0
            full_layers = min(layers_height, layers_weight)
            capacity = boxes_layer * full_layers
            if capacity <= 0:
                st.error("Karton nie mieści się na wybranej palecie w granicach masy lub wysokości.")
            else:
                full_pallets, remainder = divmod(int(p_qty), capacity)
                total_pallets = full_pallets + (1 if remainder else 0)
                layers_last = int(np.ceil(remainder / boxes_layer)) if remainder else 0
                layer_sheets = max(full_layers - 1, 0) * layer_mass if use_layer else 0
                cargo_mass_full = capacity * p_weight
                gross_full = cargo_mass_full + pallet["WEIGHT"] + security_mass + layer_sheets
                last_layer_sheets = max(layers_last - 1, 0) * layer_mass if use_layer else 0
                gross_last = (remainder * p_weight + pallet["WEIGHT"] + security_mass + last_layer_sheets) if remainder else gross_full
                total_gross_weight = full_pallets * gross_full + (gross_last if remainder else 0)
                loaded_height = pallet["H"] + full_layers * p_h
                stability = max(0, min(100, round(100 - max(0, loaded_height / max(pallet["L"], pallet["W"]) - 1) * 45 - (100 - (boxes_layer * p_l * p_w / (pallet["L"] * pallet["W"]) * 100)) * 0.25)))
                volume_m3 = (pallet["L"] / 1000) * (pallet["W"] / 1000) * (loaded_height / 1000) * total_pallets
                catalog_snapshot = build_tab9_catalog_snapshot(selected_product) if selected_product else {}
                bct_gate = get_bct_palletization_gate(get_current_order_id(), full_layers, gross_full, loaded_height)
                selected_level_ean = (
                    calc_physical_data.get("EAN")
                    or tab9_selected_ean(catalog_snapshot, calc_packaging_level)
                    or source_data.get("EAN", "")
                )
                result = {
                    "order_id": get_current_order_id(), "Produkt": calc_name,
                    "SKU": catalog_snapshot.get("SKU", source_data.get("SKU", "")),
                    "Poziom obliczeń": calc_packaging_level,
                    "EAN produktu": tab9_selected_ean(catalog_snapshot, "Produkt") or product_ean_levels(source_data).get("produkt", ""),
                    "EAN displaya": tab9_selected_ean(catalog_snapshot, "Display") or product_ean_levels(source_data).get("display", ""),
                    "EAN Master Case": tab9_selected_ean(catalog_snapshot, "Master Case") or product_ean_levels(source_data).get("master_case", ""),
                    "EAN/GTIN": selected_level_ean, "catalog_snapshot": catalog_snapshot,
                    "Wymiary kartonu mm": f"{p_l:.0f} × {p_w:.0f} × {p_h:.0f}",
                    "Wymiary palety mm": [round(pallet["L"], 1), round(pallet["W"], 1), round(loaded_height, 1)],
                    "Paleta": p_type, "Orientacja": variant_name, "Kartonów/warstwę": boxes_layer,
                    "Pełnych warstw": full_layers, "Pojemność palety": capacity, "Pełne palety": full_pallets,
                    "Ilość w zleceniu": int(p_qty),
                    "Kartonów na ostatniej palecie": remainder or capacity, "Warstw na ostatniej palecie": layers_last or full_layers,
                    "Liczba palet": total_pallets, "Masa netto/paleta kg": round(cargo_mass_full, 2),
                    "Masa zabezpieczeń kg": round(security_mass + layer_sheets, 2), "Masa brutto/paleta kg": round(gross_full, 2),
                    "Masa brutto ostatniej palety kg": round(gross_last, 2), "Masa brutto całkowita kg": round(total_gross_weight, 2), "Wysokość palety mm": round(loaded_height, 1),
                    "Limit wysokości z tolerancją mm": round(effective_max_height, 1),
                    "Stabilność /100": stability, "Objętość transportowa m³": round(volume_m3, 3),
                    "LDM": round((pallet["L"] / 1000) * (pallet["W"] / 1000) * total_pallets / 2.4, 2),
                    "BCT status": bct_gate["status"], "BCT blokada": bct_gate["blocked"], "BCT powody": bct_gate["reasons"],
                }
                st.session_state["pal_calc_result"] = result
                st.session_state["pal_calc_last"] = {key: st.session_state[key] for key in st.session_state if key.startswith("calc_")}
                # Pozycje przekazane wcześniej do E-Order/Karty Pracy były dotąd
                # jedynie kopią wyniku. Aktualizujemy więc ich dane logistyczne po
                # każdym ponownym obliczeniu paletyzacji.
                relations = catalog_snapshot.get("Relacje pakowania", {})
                displays_in_mc = safe_int(relations.get("Displayów w Master Case"), safe_int(source_data.get("displays_in_mc"), 1)) or 1
                boxes_in_display = safe_int(relations.get("Pudełek w displayu"), safe_int(source_data.get("boxes_in_display"), 1)) or 1
                pcs_in_box = safe_int(relations.get("Sztuk w pudełku"), safe_int(source_data.get("pcs_in_box"), 1)) or 1
                level_quantities = packaging_level_quantities(p_qty, calc_packaging_level, {
                    "displays_per_mastercase": displays_in_mc,
                    "boxes_per_display": boxes_in_display,
                    "pieces_per_box": pcs_in_box,
                })
                pallet_quantities = packaging_level_quantities(int(capacity), calc_packaging_level, {
                    "displays_per_mastercase": displays_in_mc,
                    "boxes_per_display": boxes_in_display,
                    "pieces_per_box": pcs_in_box,
                })
                palletization_update = {
                    "packaging_calculation": {
                        **level_quantities, "palet": int(total_pallets),
                        "kartonow_na_palecie": pallet_quantities["mastercase"],
                        "displayow_na_palecie": pallet_quantities["displayow"],
                        "produktow_na_palecie": pallet_quantities["produktow"],
                        "paleta": p_type, "ldm": result["LDM"],
                        "masa_brutto_palety": result["Masa brutto/paleta kg"],
                    },
                    "qty_cartons_palette": pallet_quantities["mastercase"],
                    "qty_displays_palette": pallet_quantities["displayow"],
                    "dimensions": result["Wymiary kartonu mm"],
                    "palletization_source": True,
                }
                active_order_id = get_current_order_id()
                for collection_name, note_field in (("e_order_items", "other_criteria"), ("work_sheet_items", "order_notes")):
                    for item in st.session_state.get(collection_name, []):
                        is_same_item = (
                            item.get("order_id") == active_order_id
                            and item.get("product_name") == result["Produkt"]
                        )
                        if is_same_item:
                            item.update(palletization_update)
                            item[note_field] = f"Paletyzacja: {p_type}, {total_pallets} palet; LDM {result['LDM']}."
                # TDS jest osobnym źródłem danych dla instrukcji technicznej,
                # dlatego aktualizujemy także jego przeliczenie dla tego produktu.
                for item in st.session_state.get("tds_items", []):
                    if item.get("order_id") == active_order_id and item.get("name") == result["Produkt"]:
                        item.update(palletization_update)
                if bct_gate["reasons"]:
                    st.warning("Informacja BCT: " + " ".join(bct_gate["reasons"]))
                update_order_snapshot("paletyzacja", result, get_current_order_id())
                save_order_context(get_current_order_id())
                st.success("Obliczenie gotowe. Wynik można przekazać do kolejnych modułów.")

    result = st.session_state.get("pal_calc_result")
    if result:
        # Najważniejszy wynik pokazujemy bez przewijania w poziomie. "Pełne
        # palety" nie oznaczają sumy: ostatnia, niepełna paleta jest dodawana
        # dopiero do pola "Łączna liczba palet".
        result_display = {
            "Produkt": result.get("Produkt", ""),
            "Ilość w zleceniu": result.get("Ilość w zleceniu", 0),
            "Łączna liczba palet": result.get("Liczba palet", 0),
            "Pełne palety (bez ostatniej)": result.get("Pełne palety", 0),
            "Ostatnia paleta — kartony": result.get("Kartonów na ostatniej palecie", 0),
            "Kartonów / warstwę": result.get("Kartonów/warstwę", 0),
            "Pełnych warstw": result.get("Pełnych warstw", 0),
            "Pojemność palety": result.get("Pojemność palety", 0),
            "Paleta": result.get("Paleta", ""),
            "Wysokość palety [mm]": result.get("Wysokość palety mm", 0),
            "Limit z tolerancją [mm]": result.get("Limit wysokości z tolerancją mm", 0),
            "LDM": result.get("LDM", 0),
        }
        st.dataframe(pd.DataFrame([result_display]), width="stretch", hide_index=True)
        selected_security = []
        if use_stretch:
            selected_security.append("folia stretch")
        if use_layer:
            selected_security.append("przekładki")
        if use_corners:
            selected_security.append("narożniki / kaptur")
        instruction_pdf = generuj_pdf_instrukcje_ukladania(result, selected_security)
        filename_product = re.sub(r"[^A-Za-z0-9_-]+", "_", str(result["Produkt"])).strip("_") or "produkt"
        if st.button("💾 Zapisz instrukcję w Centrum zlecenia", key="store_pallet_instruction"):
            generuj_pdf_instrukcje_ukladania(result, selected_security, store_document=True)
            st.success("Instrukcję zapisano w Centrum zlecenia.")
        st.download_button(
            "📄 Pobierz profesjonalną instrukcję układania (PDF)",
            data=instruction_pdf,
            file_name=f"instrukcja_ukladania_{filename_product}.pdf",
            mime="application/pdf",
            type="primary",
        )
        compare_rows = []
        for compare_name, compare_pallet in PALLET_TYPES.items():
            compare_layer = max(int(compare_pallet["L"] // (p_l_raw * conv_length)) * int(compare_pallet["W"] // (p_w_raw * conv_length)), int(compare_pallet["L"] // (p_w_raw * conv_length)) * int(compare_pallet["W"] // (p_l_raw * conv_length)))
            compare_layers = int(max(0, effective_max_height - compare_pallet["H"]) // (p_h_raw * conv_length))
            compare_rows.append({"Paleta": compare_name, "Kartonów / warstwę": compare_layer, "Szac. pojemność": compare_layer * compare_layers})
        with st.expander("⚖️ Porównanie palet EURO / przemysłowej / półpalety", expanded=False):
            st.dataframe(pd.DataFrame(compare_rows), width="stretch", hide_index=True)
        if result["Stabilność /100"] < 60:
            st.warning("Niska ocena stabilności — rozważ niższą paletę, przekładki albo inny układ.")
        result_bct_gate = get_bct_palletization_gate(
            get_current_order_id(), result.get("Pełnych warstw", 0),
            result.get("Masa brutto/paleta kg", 0), result.get("Wysokość palety mm", 0),
        )
        bct_blocked = result_bct_gate["blocked"]
        if result_bct_gate["reasons"]:
            st.warning("Informacja BCT: " + " ".join(result_bct_gate["reasons"]))
        else:
            safe_bct = result_bct_gate["result"].get("safe_bct", 0)
            st.info(f"BCT: zgodne z zatwierdzoną analizą (bezpieczne BCT: {safe_bct:.1f} kg).")
        action1, action2, action3, action4 = st.columns(4)
        with action1:
            if st.button("➕ Packing List"):
                packing_document = st.session_state.setdefault("packing_document", {"order_id": get_current_order_id(), "number": f"PL/{datetime.now().strftime('%Y')}/{datetime.now().strftime('%H%M%S')}", "created_at": datetime.now().strftime("%Y-%m-%d"), "sent_at": "", "planned_delivery": "", "status": "roboczy", "delivery_type": "kompletna", "language": "PL", "sender": "", "recipient": "", "delivery_place": "", "carrier": "", "items": [], "pallets": []})
                packing_document["order_id"] = get_current_order_id()
                packing_level = result.get("Poziom obliczeń", "Master Case")
                packing_quantities = packaging_level_quantities(p_qty, packing_level, calc_physical_data.get("relacje", {}))
                packing_document["items"].append({"Produkt": result["Produkt"], "SKU": result.get("SKU", ""), "EAN produktu": result.get("EAN produktu", ""), "EAN displaya": result.get("EAN displaya", ""), "EAN Master Case": result.get("EAN Master Case", ""), "Poziom opakowania": packing_level, "EAN/GTIN": result.get("EAN/GTIN", ""), "LOT": "", "Sztuki": packing_quantities["produktow"], "Pudełka": packing_quantities["pudelek"], "Displaye": packing_quantities["displayow"], "Kartony": packing_quantities["mastercase"], "Paleta": result.get("Paleta", ""), "Jednostka": packing_level.casefold(), "Masa kg": result.get("Masa brutto całkowita kg", result.get("Masa brutto/paleta kg", 0))})
                packing_document["transport_data"] = {
                    "order_id": get_current_order_id(), "Produkt": result["Produkt"], "Paleta": result.get("Paleta", ""),
                    "Liczba palet": result.get("Liczba palet", 0), "Masa brutto/paleta kg": result.get("Masa brutto/paleta kg", 0),
                    "Masa brutto całkowita kg": result.get("Masa brutto całkowita kg", 0),
                    "Wymiary palety mm": result.get("Wymiary palety mm", []), "Wysokość palety mm": result.get("Wysokość palety mm", 0),
                    "LDM": result.get("LDM", 0),
                }
                update_order_snapshot("packing_list", packing_document, get_current_order_id())
                save_order_context(get_current_order_id())
                st.success("Dodano wynik bezpośrednio do Packing List aktywnego zlecenia.")
        with action2:
            if st.button("➕ E-Order / Karta Pracy"):
                snapshot = result.get("catalog_snapshot", {}) or {}
                relations = snapshot.get("Relacje pakowania", {})
                displays_in_mc = safe_int(relations.get("Displayów w Master Case"), safe_int(source_data.get("displays_in_mc"), 1)) or 1
                boxes_in_display = safe_int(relations.get("Pudełek w displayu"), safe_int(source_data.get("boxes_in_display"), 1)) or 1
                pcs_in_box = safe_int(relations.get("Sztuk w pudełku"), safe_int(source_data.get("pcs_in_box"), 1)) or 1
                pieces_per_display = boxes_in_display * pcs_in_box
                pieces_per_mc = displays_in_mc * pieces_per_display
                selected_level = result.get("Poziom obliczeń", "Master Case")
                level_quantities = packaging_level_quantities(p_qty, selected_level, {
                    "displays_per_mastercase": displays_in_mc,
                    "boxes_per_display": boxes_in_display,
                    "pieces_per_box": pcs_in_box,
                })
                units_per_pallet = int(result["Pojemność palety"])
                pallet_quantities = packaging_level_quantities(units_per_pallet, selected_level, {
                    "displays_per_mastercase": displays_in_mc,
                    "boxes_per_display": boxes_in_display,
                    "pieces_per_box": pcs_in_box,
                })
                packaging_calculation = {
                    **level_quantities, "palet": int(result["Liczba palet"]),
                    "kartonow_na_palecie": pallet_quantities["mastercase"],
                    "displayow_na_palecie": pallet_quantities["displayow"],
                    "produktow_na_palecie": pallet_quantities["produktow"], "paleta": result["Paleta"],
                    "ldm": result["LDM"], "masa_brutto_palety": result["Masa brutto/paleta kg"],
                }
                shared = {"product_name": result["Produkt"], "product_type": selected_level, "order_channel": snapshot.get("Klient", source_data.get("Klient", "-")), "qty_net": int(p_qty), "qty_buffer": 0, "qty_with_buffer": int(p_qty), "qty_production": int(p_qty), "qty_shipping": int(p_qty), "lot_number": "", "qty_display_pieces": pieces_per_display, "qty_carton": pieces_per_mc, "qty_cartons_palette": pallet_quantities["mastercase"], "qty_displays_palette": pallet_quantities["displayow"], "sku": result.get("SKU", ""), "ean_product": result.get("EAN produktu", ""), "ean_display": result.get("EAN displaya", ""), "ean_mastercase": result.get("EAN Master Case", ""), "ean_selected": result.get("EAN/GTIN", ""), "packaging_level": selected_level, "catalog_snapshot": snapshot, "packaging_calculation": packaging_calculation, "order_id": get_current_order_id(), "order_header": st.session_state.get("tab9_order_header", {})}
                e_order_item = {**shared, "other_criteria": f"Paletyzacja: {result['Paleta']}, {result['Liczba palet']} palet.", "filter_color": "", "dimensions": result.get("Wymiary kartonu mm", ""), "box_paper_color": "", "project_info": {}, "palletization_source": True}
                work_sheet_item = {**shared, "display_type": "", "other_criteria": "", "filter_color": "", "dimensions": result.get("Wymiary kartonu mm", ""), "box_paper_color": "", "production_planned": int(p_qty), "production_made": 0, "production_waste": 0, "waste_reason": "", "qty_box": level_quantities["mastercase"], "qty_cover": 0, "qty_display": level_quantities["displayow"], "order_notes": f"Paletyzacja: {result['Paleta']}, {result['Liczba palet']} palet; LDM {result['LDM']}.", "invoice_status": "Brak", "project_info": {}, "palletization_source": True}

                def upsert_palletization_item(items, new_item):
                    for index, existing_item in enumerate(items):
                        if (
                            existing_item.get("order_id") == new_item["order_id"]
                            and existing_item.get("product_name") == new_item["product_name"]
                        ):
                            items[index] = {**existing_item, **new_item}
                            return "zaktualizowano"
                    items.append(new_item)
                    return "dodano"

                e_order_action = upsert_palletization_item(st.session_state.setdefault("e_order_items", []), e_order_item)
                work_sheet_action = upsert_palletization_item(st.session_state.setdefault("work_sheet_items", []), work_sheet_item)
                save_order_context(get_current_order_id())
                st.success(f"E-Order: {e_order_action}; Karta Pracy: {work_sheet_action}. Pozycja poziomu „{selected_level}” jest zsynchronizowana z paletyzacją.")
        with action3:
            if st.button("🚚 Przekaż do transportu"):
                st.session_state["transport_prefill"] = result
                st.success("Dane będą dostępne w module 5.")
        with action4:
            if st.button("♻️ Dodaj komponenty PPWR"):
                st.session_state.setdefault("ppwr_components", pd.DataFrame())
                ppwr_rows = []
                selected_pallet = all_pallets.get(p_type, {})
                pallet_mass_g = float(selected_pallet.get("WEIGHT", 0) or 0) * 1000
                if use_stretch: ppwr_rows.append({"Uwzględniać jako opakowanie PPWR": True, "Komponent opakowania": "Folia stretch", "Poziom opakowania": "Transportowe / pallet", "Materiał główny": "Plastics", "Surowiec": "LDPE / other plastic", "Masa jednostkowa (g)": stretch_mass * 1000, "Ilość / 1 SKU": 0, "Ilość / 1 paletę": 1, "Kolor / druk / uwagi": "transparent"})
                if use_layer: ppwr_rows.append({"Uwzględniać jako opakowanie PPWR": True, "Komponent opakowania": "Przekładka", "Poziom opakowania": "Transportowe / pallet", "Materiał główny": "Paper", "Surowiec": "Paper / cardboard", "Masa jednostkowa (g)": layer_mass * 1000, "Ilość / 1 SKU": 0, "Ilość / 1 paletę": max(int(result["Pełnych warstw"]) - 1, 0), "Kolor / druk / uwagi": "brak"})
                if use_corners: ppwr_rows.append({"Uwzględniać jako opakowanie PPWR": True, "Komponent opakowania": "Narożniki / kaptur", "Poziom opakowania": "Transportowe / pallet", "Materiał główny": "Other", "Surowiec": "Other", "Masa jednostkowa (g)": corner_mass * 1000, "Ilość / 1 SKU": 0, "Ilość / 1 paletę": 1, "Kolor / druk / uwagi": "brak"})
                ppwr_rows.append({"Uwzględniać jako opakowanie PPWR": True, "Komponent opakowania": "Paleta drewniana", "Poziom opakowania": "Transportowe / pallet", "Materiał główny": "Wood", "Surowiec": "Wood", "Masa jednostkowa (g)": pallet_mass_g, "Ilość / 1 SKU": 0, "Ilość / 1 paletę": 1, "Kolor / druk / uwagi": "brak"})
                st.session_state["ppwr_components"] = pd.concat([st.session_state["ppwr_components"], pd.DataFrame(ppwr_rows)], ignore_index=True)
                st.success("Dodano komponenty transportowe do PPWR.")
        with st.expander("📧 Wyślij raport paletyzacji e-mailem", expanded=False):
            with st.form("pal_calc_email_form"):
                pal_email = st.text_input("Adres odbiorcy", key="pal_calc_email_recipient")
                pal_subject = st.text_input("Temat", value=f"Raport paletyzacji — {result['Produkt']}", key="pal_calc_email_subject")
                if st.form_submit_button("📤 Wyślij raport"):
                    sender = st.secrets.get("SENDER_EMAIL", "")
                    password = st.secrets.get("SENDER_PASSWORD", "")
                    if not sender or not password or not pal_email.strip():
                        st.error("Uzupełnij adres odbiorcy oraz konfigurację SMTP w secrets.toml.")
                    else:
                        try:
                            message = EmailMessage()
                            message["Subject"], message["From"], message["To"] = pal_subject, sender, pal_email.strip()
                            message.set_content("Raport paletyzacji\n\n" + "\n".join(f"{key}: {value}" for key, value in result.items()))
                            with smtplib.SMTP_SSL(st.secrets.get("SMTP_SERVER", "smtp.gmail.com"), int(st.secrets.get("SMTP_PORT", 465))) as smtp:
                                smtp.login(sender, password)
                                smtp.send_message(message)
                            st.success("Wysłano raport e-mailem.")
                        except Exception as error:
                            st.error(f"Nie udało się wysłać raportu: {error}")
