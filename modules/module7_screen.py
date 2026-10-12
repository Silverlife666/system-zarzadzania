"""Widok modułu 7 wydzielony z app.py."""


def _create_mastercase_2d_figure(result):
    """Rysuje rzut jednej warstwy i zwraca figurę Matplotlib."""
    layout = result.get("layout", {}) or {}
    display = result.get("Display", {}) or {}
    nx = max(1, int(layout.get("length", 1) or 1))
    ny = max(1, int(layout.get("width", 1) or 1))
    d_len = float(display.get("Dlugosc", 0) or 0)
    d_wid = float(display.get("Szerokosc", 0) or 0)
    if d_len <= 0 or d_wid <= 0:
        return None

    fig, axis = plt.subplots(figsize=(6, 5), facecolor="#FFFFFF")
    axis.set_title(f"Warstwa w kartonie: {nx} kolumny × {ny} rzędy (razem: {nx * ny} szt.)", fontsize=10, fontweight="bold")
    axis.set_facecolor("#F8F9FA")
    axis.grid(True, linestyle="--", alpha=0.5, color="#CBD5E0")
    axis.add_patch(patches.Rectangle((0, 0), nx * d_len, ny * d_wid, linewidth=2, edgecolor="#C05621", facecolor="#ED8936", alpha=0.2))
    for ix in range(nx):
        for iy in range(ny):
            x, y = ix * d_len, iy * d_wid
            axis.add_patch(patches.Rectangle((x, y), d_len, d_wid, linewidth=1, edgecolor="#1A202C", facecolor="#3182CE", alpha=0.85))
            axis.text(x + d_len / 2, y + d_wid / 2, f"{ix + 1},{iy + 1}", color="#FFFFFF", fontsize=8, fontweight="bold", ha="center", va="center")
    margin = max(nx * d_len, ny * d_wid) * 0.1
    axis.set_xlim([-margin, nx * d_len + margin])
    axis.set_ylim([-margin, ny * d_wid + margin])
    axis.set_aspect("equal")
    axis.set_xlabel("Długość [mm]")
    axis.set_ylabel("Szerokość [mm]")
    fig.tight_layout()
    return fig


def _create_mastercase_vertical_figure(result):
    """Rysuje przekrój pionowy Master Case wzdłuż jego długości."""
    layout = result.get("layout", {}) or {}
    display = result.get("Display", {}) or {}
    nx = max(1, int(layout.get("length", 1) or 1))
    nz = max(1, int(layout.get("height", 1) or 1))
    d_len = float(display.get("Dlugosc", 0) or 0)
    d_hei = float(display.get("Wysokosc", 0) or 0)
    if d_len <= 0 or d_hei <= 0:
        return None

    fig, axis = plt.subplots(figsize=(6, 4), facecolor="#FFFFFF")
    axis.set_title(f"Przekrój pionowy: {nx} displayów w długości × {nz} warstwy", fontsize=10, fontweight="bold")
    axis.set_facecolor("#F8F9FA")
    axis.grid(True, linestyle="--", alpha=0.5, color="#CBD5E0")
    axis.add_patch(patches.Rectangle((0, 0), nx * d_len, nz * d_hei, linewidth=2, edgecolor="#C05621", facecolor="#ED8936", alpha=0.2))
    for ix in range(nx):
        for iz in range(nz):
            x, y = ix * d_len, iz * d_hei
            axis.add_patch(patches.Rectangle((x, y), d_len, d_hei, linewidth=1, edgecolor="#1A202C", facecolor="#38A169", alpha=0.85))
            axis.text(x + d_len / 2, y + d_hei / 2, f"W{iz + 1}", color="#FFFFFF", fontsize=8, fontweight="bold", ha="center", va="center")
    margin = max(nx * d_len, nz * d_hei) * 0.1
    axis.set_xlim([-margin, nx * d_len + margin])
    axis.set_ylim([-margin, nz * d_hei + margin])
    axis.set_aspect("equal")
    axis.set_xlabel("Długość [mm]")
    axis.set_ylabel("Wysokość [mm]")
    fig.tight_layout()
    return fig

def render_module_seven(st, deps):
    for _bridge_name, _bridge_value in deps.items():
        if not _bridge_name.startswith("__"):
            globals()[_bridge_name] = _bridge_value
    del _bridge_name, _bridge_value
    st.subheader("📦 Kreator Box Rightsizing (Pełna Optymalizacja Mastercase)")
    st.markdown("Projektuj Mastercase z danych produktu lub ręcznie; porównuj warianty, paletę, BCT i materiały PPWR.")
    rs_db = wczytaj_produkty_z_db()
    rs_source = st.radio("Źródło danych", ["Ręczne", "Produkt z sekcji 1", "Szablon Mastercase"], horizontal=True, key="rs_source")
    rs_data = {}
    rs_display_data = {}
    rs_mastercase_data = {}
    rs_source_product_name = ""
    rs_templates = load_mastercase_templates()
    if rs_source == "Produkt z sekcji 1" and rs_db:
        rs_product = st.selectbox("Produkt z bazy", list(rs_db), key="rs_product")
        rs_source_product_name = rs_product
        rs_data = rs_db[rs_product]
        rs_display_data = rs_data.get("Display", {}) if isinstance(rs_data.get("Display", {}), dict) else {}
        rs_mastercase_data = rs_data.get("MasterCase", {}) if isinstance(rs_data.get("MasterCase", {}), dict) else {}
        st.caption(f"Relacja z bazy: {rs_mastercase_data.get('Displayow_w_mastercase', rs_data.get('displays_in_mc', 1))} displayów / Master Case, {rs_display_data.get('Pudelka_w_displayu', rs_data.get('boxes_in_display', 1))} pudełek / display, {rs_data.get('pcs_in_box',1)} szt. / pudełko.")
        if not all(float(rs_display_data.get(key, 0) or 0) > 0 for key in ("Dlugosc", "Szerokosc", "Wysokosc")):
            st.warning("Dla tego produktu nie zapisano pełnych wymiarów displaya. Tymczasowo użyto dawnych wymiarów produktu; uzupełnij sekcję „Parametry fizyczne displaya” w Bazie produktów.")
    elif rs_source == "Szablon Mastercase":
        if not rs_templates:
            st.info("Brak zapisanych szablonów Master Case. Najpierw oblicz wariant i zapisz go jako szablon.")
        else:
            template_name = st.selectbox("Szablon Master Case", sorted(rs_templates), key="rs_template_choice")
            template_result = rs_templates[template_name].get("result", {})
            rs_data = template_result
            rs_display_data = template_result.get("Display", {}) if isinstance(template_result.get("Display", {}), dict) else {}
            rs_mastercase_data = template_result.get("MasterCase", {}) if isinstance(template_result.get("MasterCase", {}), dict) else {}
            rs_mastercase_data["Displayow_w_mastercase"] = template_result.get("displays_per_mastercase", 1)
            rs_source_product_name = template_result.get("source_product", template_name)
            if st.button("↩️ Wczytaj parametry szablonu do formularza", key="rs_load_template"):
                constraints = template_result.get("Ograniczenia", {}) or {}
                st.session_state.update({
                    "rs_size_unit": "mm", "rs_weight_unit": "kg",
                    "rs_d_len": float(rs_display_data.get("Dlugosc", 0) or 0),
                    "rs_d_wid": float(rs_display_data.get("Szerokosc", 0) or 0),
                    "rs_d_hei": float(rs_display_data.get("Wysokosc", 0) or 0),
                    "rs_display_mass": float(rs_display_data.get("Masa_pelnego_kg", 0) or 0),
                    "rs_max_disp": int(template_result.get("displays_per_mastercase", 1) or 1),
                    "rs_margin": float(constraints.get("luz_montazowy_mm", 5) or 5),
                    "rs_board_layers": rs_mastercase_data.get("Tektura", "3-warstwowa"),
                    "rs_flute": rs_mastercase_data.get("Fala", "E"),
                    "rs_closure": rs_mastercase_data.get("Zamkniecie", "Klapy standardowe"),
                    "rs_fefco": rs_mastercase_data.get("FEFCO", "0201"),
                    "rs_rotation": bool(rs_display_data.get("Mozna_obracac", True)),
                    "rs_position": rs_display_data.get("Dozwolona_pozycja", "Poziomo"),
                    "rs_mc_wall": float(rs_mastercase_data.get("Grubosc_scianki_mm", 2) or 2),
                    "rs_mc_tare": float(rs_mastercase_data.get("Tara_kg", 0) or 0),
                    "rs_mc_gross_limit": float(rs_mastercase_data.get("Masa_brutto_max_kg", 0) or 0),
                    "rs_pallet_select": template_result.get("pallet", "Euro (1200 x 800 mm)"),
                    "rs_use_mlen": bool((constraints.get("limit_dlugosci", {}) or {}).get("aktywny", False)),
                    "rs_mlen_val": float((constraints.get("limit_dlugosci", {}) or {}).get("mm", 600) or 600),
                    "rs_use_mwid": bool((constraints.get("limit_szerokosci", {}) or {}).get("aktywny", False)),
                    "rs_mwid_val": float((constraints.get("limit_szerokosci", {}) or {}).get("mm", 400) or 400),
                    "rs_use_mhei": bool((constraints.get("limit_warstw", {}) or {}).get("aktywny", True)),
                    "rs_mhei_val": int((constraints.get("limit_warstw", {}) or {}).get("liczba", 3) or 3),
                })
                st.success("Parametry szablonu wpisano do formularza.")
                st.rerun()
    rs_units_a, rs_units_b = st.columns(2)
    with rs_units_a: rs_size_unit = st.selectbox("Jednostka wymiarów", ["mm", "cm"], key="rs_size_unit")
    with rs_units_b: rs_weight_unit = st.selectbox("Jednostka masy", ["kg", "g"], key="rs_weight_unit")
    rs_length_factor = 1.0 if rs_size_unit == "mm" else 10.0
    rs_weight_factor = 1.0 if rs_weight_unit == "kg" else 0.001
    
    col_r1, col_r2, col_r3 = st.columns(3)
    with col_r1:
        d_len_raw = st.number_input(f"Długość displaya [{rs_size_unit}]", min_value=0.0, value=float(rs_display_data.get("Dlugosc") or rs_data.get("Dlugosc",131.0))/rs_length_factor, key="rs_d_len")
    with col_r2:
        d_wid_raw = st.number_input(f"Szerokość displaya [{rs_size_unit}]", min_value=0.0, value=float(rs_display_data.get("Szerokosc") or rs_data.get("Szerokosc",114.0))/rs_length_factor, key="rs_d_wid")
    with col_r3:
        d_hei_raw = st.number_input(f"Wysokość displaya [{rs_size_unit}]", min_value=0.0, value=float(rs_display_data.get("Wysokosc") or rs_data.get("Wysokosc",55.0))/rs_length_factor, key="rs_d_hei")
        
    col_r4, col_r5 = st.columns(2)
    with col_r4:
        target_total_displays = st.number_input("Docelowa liczba displayów w kartonie", min_value=1, value=int(rs_mastercase_data.get("Displayow_w_mastercase", rs_data.get("displays_in_mc", 24)) or 24), step=1, key="rs_max_disp")
    with col_r5:
        cardboard_margin = st.number_input("Luz montażowy / ścianka [mm]", min_value=0.0, value=5.0, key="rs_margin")
    d_len, d_wid, d_hei = d_len_raw*rs_length_factor, d_wid_raw*rs_length_factor, d_hei_raw*rs_length_factor
    material_a, material_b, material_c = st.columns(3)
    with material_a:
        display_mass = st.number_input(f"Masa pełnego displaya [{rs_weight_unit}]", min_value=0.0, value=float(rs_display_data.get("Masa_pelnego_kg") or rs_data.get("Waga",0.0))/rs_weight_factor, key="rs_display_mass")
    with material_b:
        board_options_rs = ["3-warstwowa", "4-warstwowa", "5-warstwowa"]
        flute_options_rs = ["E", "B", "C", "EB", "BC"]
        board_saved_rs = rs_mastercase_data.get("Tektura", "3-warstwowa")
        flute_saved_rs = rs_mastercase_data.get("Fala", "E")
        board_layers = st.selectbox("Tektura", board_options_rs, index=board_options_rs.index(board_saved_rs) if board_saved_rs in board_options_rs else 0, key="rs_board_layers")
        flute = st.selectbox("Typ fali", flute_options_rs, index=flute_options_rs.index(flute_saved_rs) if flute_saved_rs in flute_options_rs else 0, key="rs_flute")
    with material_c:
        closure_options_rs = ["Klapy standardowe", "Automatyczne dno", "Tacka", "Obwoluta"]
        fefco_options_rs = ["0201", "0215", "0427", "0470", "Inny"]
        closure_saved_rs = rs_mastercase_data.get("Zamkniecie", "Klapy standardowe")
        fefco_saved_rs = rs_mastercase_data.get("FEFCO", "0201")
        closure = st.selectbox("Zamknięcie", closure_options_rs, index=closure_options_rs.index(closure_saved_rs) if closure_saved_rs in closure_options_rs else 0, key="rs_closure")
        fefco = st.selectbox("Typ FEFCO", fefco_options_rs, index=fefco_options_rs.index(fefco_saved_rs) if fefco_saved_rs in fefco_options_rs else 0, key="rs_fefco")
    allow_rotation = st.checkbox("Display można obracać", value=bool(rs_display_data.get("Mozna_obracac", True)), key="rs_rotation")
    position_options_rs = ["Poziomo", "Pionowo", "Na boku"]
    saved_position_rs = rs_display_data.get("Dozwolona_pozycja", "Poziomo")
    position = st.selectbox("Pozycja displaya", position_options_rs, index=position_options_rs.index(saved_position_rs) if saved_position_rs in position_options_rs else 0, key="rs_position")
    display_mass_kg = float(display_mass) * rs_weight_factor

    with st.expander("📋 Parametry fizyczne Master Case", expanded=False):
        saved_inner_length = float(rs_mastercase_data.get("Dlugosc_wewnetrzna", 0) or 0)
        saved_outer_length = float(rs_mastercase_data.get("Dlugosc_zewnetrzna", 0) or 0)
        inferred_wall = max(0.0, (saved_outer_length - saved_inner_length) / 2) if saved_outer_length and saved_inner_length else 2.0
        mc_spec_a, mc_spec_b, mc_spec_c = st.columns(3)
        with mc_spec_a:
            mastercase_wall = st.number_input("Grubość ścianki Master Case [mm]", min_value=0.0, value=float(inferred_wall), key="rs_mc_wall")
        with mc_spec_b:
            mastercase_tare = st.number_input(f"Tara pustego Master Case [{rs_weight_unit}]", min_value=0.0, value=float(rs_mastercase_data.get("Tara_kg", 0) or 0) / rs_weight_factor, key="rs_mc_tare")
        with mc_spec_c:
            mastercase_gross_limit = st.number_input(f"Maks. masa brutto Master Case [{rs_weight_unit}]", min_value=0.0, value=float(rs_mastercase_data.get("Masa_brutto_max_kg", 0) or 0) / rs_weight_factor, key="rs_mc_gross_limit")
    mastercase_tare_kg = float(mastercase_tare) * rs_weight_factor
    mastercase_gross_limit_kg = float(mastercase_gross_limit) * rs_weight_factor

    pallet_options = {
        "Euro (1200 x 800 mm)": (1200, 800),
        "Industrial / Przemysłowa (1200 x 1000 mm)": (1200, 1000),
        "Półpaleta (800 x 600 mm)": (800, 600)
    }
    selected_pallet_name = st.selectbox("Wybierz typ palety docelowej", list(pallet_options.keys()), key="rs_pallet_select")
    pallet_l, pallet_w = pallet_options[selected_pallet_name]

    with st.expander("⚙️ Opcjonalne ograniczenia gabarytowe kartonu (Mastercase)", expanded=False):
        st.info("Zaznacz i ustaw limity, jeśli chcesz ograniczyć maksymalne wymiary lub liczbę warstw w pionie.")
        
        col_c1, col_c2, col_c3 = st.columns(3)
        with col_c1:
            use_max_len = st.checkbox("Limit maks. długości", value=False, key="rs_use_mlen")
            max_len_val = st.number_input("Maks. długość [mm]", min_value=50.0, value=600.0, step=10.0, key="rs_mlen_val", disabled=not use_max_len)
        with col_c2:
            use_max_wid = st.checkbox("Limit maks. szerokości", value=False, key="rs_use_mwid")
            max_wid_val = st.number_input("Maks. szerokość [mm]", min_value=50.0, value=400.0, step=10.0, key="rs_mwid_val", disabled=not use_max_wid)
        with col_c3:
            use_max_hei = st.checkbox("Limit maks. warstw (wysokość)", value=True, key="rs_use_mhei")
            max_nz_limit = st.number_input("Maks. liczba warstw", min_value=1, max_value=10, value=3, step=1, key="rs_mhei_val", disabled=not use_max_hei)

    if st.button("⚙️ Oblicz optymalny Mastercase i wizualizację", key="btn_rs_calc"):
        best_config = None
        min_score = float('inf')
        candidate_configs = []
        
        max_search_nz = max_nz_limit if use_max_hei else target_total_displays
        
        for nz in range(1, max_search_nz + 1):
            for ny in range(1, target_total_displays + 1):
                for nx in range(1, target_total_displays + 1):
                    total = nx * ny * nz
                    if total >= target_total_displays:
                        waste = total - target_total_displays
                        if waste > 3:
                            continue
                            
                        l_in = nx * d_len + cardboard_margin
                        w_in = ny * d_wid + cardboard_margin
                        h_in = nz * d_hei + cardboard_margin
                        
                        if use_max_len and l_in > max_len_val:
                            continue
                        if use_max_wid and w_in > max_wid_val:
                            continue
                        if l_in > pallet_l or w_in > pallet_w:
                            continue
                            
                        c1 = pallet_l // l_in
                        r1 = pallet_w // w_in
                        boxes_layer_1 = c1 * r1
                        
                        c2 = pallet_l // w_in
                        r2 = pallet_w // l_in
                        boxes_layer_2 = c2 * r2
                        
                        max_boxes_on_pallet_layer = max(boxes_layer_1, boxes_layer_2)
                        box_footprint = l_in * w_in
                        pallet_area = pallet_l * pallet_w
                        surface_utilization = (max_boxes_on_pallet_layer * box_footprint) / pallet_area
                        
                        max_dim = max(l_in, w_in, h_in)
                        min_dim = min(l_in, w_in, h_in)
                        aspect_ratio = max_dim / min_dim
                        
                        score = (waste * 50) + (aspect_ratio * 10) - (surface_utilization * 100)
                        candidate_configs.append({
                            "score": round(float(score), 2), "uklad": {"length": int(nx), "width": int(ny), "height": int(nz)},
                            "displaye": int(total), "puste_miejsca": int(waste),
                            "wymiary_wewnetrzne_mm": {"dlugosc": round(float(l_in), 1), "szerokosc": round(float(w_in), 1), "wysokosc": round(float(h_in), 1)},
                            "kartony_na_warstwe_palety": int(max_boxes_on_pallet_layer),
                            "wykorzystanie_palety_pct": round(float(surface_utilization * 100), 1),
                        })
                        
                        if score < min_score:
                            min_score = score
                            best_config = (nx, ny, nz, total, l_in, w_in, h_in, max_boxes_on_pallet_layer)
        
        if not best_config:
            st.error("❌ Nie znaleziono układu spełniającego podane ograniczenia gabarytowe i docelową liczbę sztuk. Spróbuj poluzować limity.")
        else:
            nx, ny, nz, total_displays_fitted, l_in, w_in, h_in, max_boxes_on_pallet_layer = best_config
            outer_l = float(l_in + 2 * mastercase_wall)
            outer_w = float(w_in + 2 * mastercase_wall)
            outer_h = float(h_in + 2 * mastercase_wall)
            calculated_gross_mass = round(mastercase_tare_kg + total_displays_fitted * display_mass_kg, 3)
            best_variants = sorted(candidate_configs, key=lambda item: item["score"])[:10]
            st.session_state["box_rightsizing_result"] = {
                # Płaskie pola pozostają dla modułów 2 i 8, a pełna specyfikacja
                # jest dostępna w kluczu MasterCase dla TDS, PPWR i Centrum zlecenia.
                "Nazwa": "Master Case z Box Rightsizing", "Dlugosc": outer_l, "Szerokosc": outer_w,
                "Wysokosc": outer_h, "Waga": calculated_gross_mass, "boxes_per_layer": int(max_boxes_on_pallet_layer),
                "order_id": get_current_order_id(), "source_product": rs_source_product_name or rs_data.get("SKU", ""),
                "source_sku": rs_data.get("SKU", ""), "source_type": rs_source,
                "displays_per_mastercase": int(total_displays_fitted), "layout": {"length": int(nx), "width": int(ny), "height": int(nz)},
                "pallet": selected_pallet_name, "warianty": best_variants,
                "Display": {
                    "Dlugosc": float(d_len), "Szerokosc": float(d_wid), "Wysokosc": float(d_hei),
                    "Masa_pelnego_kg": display_mass_kg, "Mozna_obracac": allow_rotation, "Dozwolona_pozycja": position,
                },
                "MasterCase": {
                    "Dlugosc_wewnetrzna": float(l_in), "Szerokosc_wewnetrzna": float(w_in), "Wysokosc_wewnetrzna": float(h_in),
                    "Dlugosc_zewnetrzna": outer_l, "Szerokosc_zewnetrzna": outer_w, "Wysokosc_zewnetrzna": outer_h,
                    "Tara_kg": mastercase_tare_kg, "Masa_brutto_kg": calculated_gross_mass,
                    "Masa_brutto_max_kg": mastercase_gross_limit_kg, "Grubosc_scianki_mm": float(mastercase_wall),
                    "FEFCO": fefco, "Zamkniecie": closure, "Tektura": board_layers, "Fala": flute,
                },
                "Ograniczenia": {
                    "docelowa_liczba_displayow": int(target_total_displays), "luz_montazowy_mm": float(cardboard_margin),
                    "limit_dlugosci": {"aktywny": use_max_len, "mm": float(max_len_val)},
                    "limit_szerokosci": {"aktywny": use_max_wid, "mm": float(max_wid_val)},
                    "limit_warstw": {"aktywny": use_max_hei, "liczba": int(max_nz_limit)},
                },
            }
            # Wynik jest od razu przypisany do zlecenia; przejście do modułu 2/4/8
            # nie może go usunąć ani pokazać pod innym order_id.
            active_rightsizing_order_id = get_current_order_id()
            update_order_snapshot("mastercase", st.session_state["box_rightsizing_result"], active_rightsizing_order_id)
            save_order_context(active_rightsizing_order_id)
            
            st.success(f"✅ Znaleziono optymalny układ: **{nx} (długość) × {ny} (szerokość) × {nz} (wysokość)** = **{total_displays_fitted} displayów** w kartonie.")
            if mastercase_gross_limit_kg > 0 and calculated_gross_mass > mastercase_gross_limit_kg:
                st.error(f"Masa brutto wyliczonego Master Case ({calculated_gross_mass:.2f} kg) przekracza limit ({mastercase_gross_limit_kg:.2f} kg).")
            
            col_info1, col_info2 = st.columns(2)
            with col_info1:
                st.markdown("#### Wymiary wewnętrzne Mastercase:")
                st.write(f"- Długość wewnętrzna: **{l_in:.1f} mm**")
                st.write(f"- Szerokość wewnętrzna: **{w_in:.1f} mm**")
                st.write(f"- Wysokość wewnętrzna: **{h_in:.1f} mm**")
            with col_info2:
                st.markdown(f"#### Dopasowanie do palety ({selected_pallet_name}):")
                st.write(f"- Kartonów w warstwie palety: **{max_boxes_on_pallet_layer} szt.**")
                pallet_box_area = max_boxes_on_pallet_layer * (l_in * w_in)
                pallet_util = (pallet_box_area / pallet_area) * 100
                st.write(f"- Wykorzystanie powierzchni palety: **ok. {pallet_util:.1f}%**")
                st.write(f"- Liczba warstw w pionie: **{nz}**")
                
    # Szablon jest niezależny od archiwum obliczeń: przechowuje konstrukcję,
    # aby można było szybko rozpocząć kolejny projekt Master Case.
    rs_current_result = st.session_state.get("box_rightsizing_result", {})
    if rs_current_result:
        st.markdown("---")
        st.markdown("#### 🎨 Wizualizacja 2D i dokument PDF")
        rs_top_figure = _create_mastercase_2d_figure(rs_current_result)
        rs_vertical_figure = _create_mastercase_vertical_figure(rs_current_result)
        if rs_top_figure is None or rs_vertical_figure is None:
            st.warning("Brakuje wymiarów displaya potrzebnych do utworzenia wizualizacji 2D.")
        else:
            rs_top_column, rs_vertical_column = st.columns(2)
            with rs_top_column:
                st.caption("Rzut z góry jednej warstwy")
                st.pyplot(rs_top_figure)
            with rs_vertical_column:
                st.caption("Przekrój pionowy warstw")
                st.pyplot(rs_vertical_figure)
            rs_top_image_buffer = io.BytesIO()
            rs_top_figure.savefig(rs_top_image_buffer, format="png", dpi=180, bbox_inches="tight")
            rs_vertical_image_buffer = io.BytesIO()
            rs_vertical_figure.savefig(rs_vertical_image_buffer, format="png", dpi=180, bbox_inches="tight")
            plt.close(rs_top_figure)
            plt.close(rs_vertical_figure)
            rs_pdf_key = f"mastercase_2d_pdf_{rs_current_result.get('order_id', get_current_order_id())}"
            if st.button("Przygotuj PDF z wizualizacją 2D", icon=":material/picture_as_pdf:", key="rs_generate_pdf"):
                pdf_bytes = build_mastercase_2d_pdf(
                    rs_current_result, rs_top_image_buffer.getvalue(), rs_vertical_image_buffer.getvalue(),
                    font_regular=FONT_REGULAR, font_bold=FONT_BOLD,
                )
                st.session_state[rs_pdf_key] = pdf_bytes
                store_order_pdf("Karta Master Case 2D", pdf_bytes, "karta_mastercase_2d.pdf", order_id=rs_current_result.get("order_id"))
                st.success("PDF zapisano w Centrum zlecenia i jest gotowy do pobrania.")
            if pdf_bytes := st.session_state.get(rs_pdf_key):
                st.download_button("Pobierz PDF z wizualizacją 2D", pdf_bytes, file_name="karta_mastercase_2d.pdf", mime="application/pdf", icon=":material/download:", key="rs_download_pdf")
        with st.expander("💾 Szablony Master Case", expanded=False):
            st.caption("Zapisz konfigurację kartonu jako wzorzec. Archiwum wyników BCT i dokumentów zlecenia pozostaje oddzielne.")
            template_columns = st.columns([3, 1])
            with template_columns[0]:
                rs_template_name = st.text_input(
                    "Nazwa szablonu Master Case",
                    value=str(rs_current_result.get("source_product") or rs_current_result.get("Nazwa") or "Master Case"),
                    key="rs_template_name_save",
                )
            with template_columns[1]:
                st.write("")
                st.write("")
                if st.button("💾 Zapisz szablon", key="rs_template_save"):
                    name = rs_template_name.strip()
                    if not name:
                        st.error("Podaj nazwę szablonu.")
                    else:
                        rs_templates[name] = {
                            "saved_at": datetime.now().isoformat(timespec="seconds"),
                            "source_product": rs_current_result.get("source_product", ""),
                            "source_order_id": rs_current_result.get("order_id", get_current_order_id()),
                            "result": rs_current_result,
                        }
                        save_mastercase_templates(rs_templates)
                        st.success(f"Zapisano szablon „{name}”.")
            if rs_templates:
                overview = [
                    {"Nazwa": name, "Produkt źródłowy": item.get("source_product", ""), "Zapisano": item.get("saved_at", "")}
                    for name, item in sorted(rs_templates.items())
                ]
                st.dataframe(pd.DataFrame(overview), hide_index=True, width="stretch")
                delete_name = st.selectbox("Usuń szablon", ["—"] + sorted(rs_templates), key="rs_template_delete_choice")
                if st.button("🗑️ Usuń wybrany szablon", key="rs_template_delete", disabled=delete_name == "—"):
                    rs_templates.pop(delete_name, None)
                    save_mastercase_templates(rs_templates)
                    st.success("Usunięto szablon Master Case.")
                    st.rerun()
