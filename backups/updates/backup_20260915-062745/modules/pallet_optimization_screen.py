"""Ekran optymalizacji kartonów na palecie (moduł 4)."""

from __future__ import annotations

from datetime import datetime
import io
import json

import matplotlib.pyplot as plt

from core.pallet_optimization import optimize_pallet_layout


def render_pallet_optimization_screen(st, deps):
    """Renderuje moduł 4; wszystkie zależności aplikacyjne są przekazane przez router."""
    pd, np = deps["pd"], deps["np"]
    st.subheader("💡 Optymalizacja układu kartonów na palecie")
    st.caption("Porównaj trzy warianty: oryginalny, obrót 90° oraz mieszany/zaawansowany. Każdy wariant ma podgląd 2D.")
    database = deps["load_products"]()
    template_path = deps["storage_path"]("szablony_ukladu_palet.json")
    templates = deps["load_json"](template_path, {})
    if not database:
        st.info("Brak produktów w bazie.")
        return
    pallets = {**deps["load_custom_pallets"](), **st.session_state.get("custom_pallets", {})}
    all_pallets = {**deps["pallet_types"], **pallets}
    action_a, action_b, action_c = st.columns(3)
    with action_a:
        if st.button("🧹 Wyczyść formularz", key="sug_clear"):
            for key in [key for key in st.session_state if key.startswith("sug_") and key != "sug_clear"]:
                st.session_state.pop(key, None)
            st.session_state.pop("sug_layout_result", None); st.rerun()
    with action_b:
        if st.button("↩️ Wczytaj ostatnie obliczenie", key="sug_load_session"):
            saved = st.session_state.get("sug_layout_session")
            if saved:
                st.session_state["sug_layout_result"] = saved; st.success("Wczytano obliczenie zapisane w sesji.")
            else:
                st.warning("Brak obliczenia zapisanego w sesji.")
    with action_c:
        if templates:
            choice = st.selectbox("Szablon z pliku", list(templates), key="sug_template_choice")
            if st.button("📂 Wczytaj z pliku", key="sug_load_file"):
                st.session_state["sug_layout_result"] = templates[choice]["result"]; st.success("Wczytano obliczenie z pliku.")
    product_name = st.selectbox("Produkt", list(database), key="sug_product")
    product = database[product_name]
    level = st.selectbox("Poziom, który ma być paletyzowany", deps["packaging_levels"], index=deps["packaging_levels"].index("Master Case"), key="sug_packaging_level", help="Dla układu kartonów na palecie wybierz Master Case.")
    physical = deps["get_physical"](product, level)
    signature = f"{product_name}|{level}"; refresh = st.session_state.get("_sug_physical_signature") != signature
    if refresh:
        st.session_state["_sug_physical_signature"] = signature
    eans = deps["ean_levels"](product); catalog = deps["catalog_snapshot"](product_name)
    st.caption("EAN produktu: " + (eans.get("produkt") or "brak") + " | EAN displaya: " + (eans.get("display") or "brak") + " | EAN Master Case: " + (eans.get("master_case") or "brak"))
    unit_a, unit_b = st.columns(2)
    with unit_a: size_unit = st.selectbox("Jednostka wymiarów", ["mm", "cm"], key="sug_size_unit")
    with unit_b: weight_unit = st.selectbox("Jednostka masy", ["kg", "g"], key="sug_weight_unit")
    length_factor, weight_factor = (1.0 if size_unit == "mm" else 10.0), (1.0 if weight_unit == "kg" else .001)
    if refresh:
        st.session_state.update({"sug_l": physical.get("Dlugosc", 0) / length_factor, "sug_w": physical.get("Szerokosc", 0) / length_factor, "sug_h": physical.get("Wysokosc", 0) / length_factor, "sug_mass": physical.get("Waga", 0) / weight_factor})
    else:
        previous = st.session_state.get("_sug_input_units", {})
        old_length, old_weight = (1.0 if previous.get("size") == "mm" else 10.0), (1.0 if previous.get("weight") == "kg" else .001)
        if previous.get("size") and previous.get("size") != size_unit:
            for key in ("sug_l", "sug_w", "sug_h"):
                if key in st.session_state: st.session_state[key] = float(st.session_state[key]) * old_length / length_factor
        if previous.get("weight") and previous.get("weight") != weight_unit and "sug_mass" in st.session_state:
            st.session_state["sug_mass"] = float(st.session_state["sug_mass"]) * old_weight / weight_factor
    st.session_state["_sug_input_units"] = {"size": size_unit, "weight": weight_unit}
    st.caption(f"Do obliczeń pobrano poziom: **{physical['label']}** — {physical['Dlugosc']:.0f} × {physical['Szerokosc']:.0f} × {physical['Wysokosc']:.0f} mm, {physical['Waga']:.3f} kg; EAN: {physical.get('EAN') or 'brak'}")
    input_a, input_b, input_c = st.columns(3)
    with input_a:
        carton_l = st.number_input(f"Długość kartonu [{size_unit}]", min_value=0.0, value=float(physical.get("Dlugosc", 200)) / length_factor, key="sug_l")
        carton_w = st.number_input(f"Szerokość kartonu [{size_unit}]", min_value=0.0, value=float(physical.get("Szerokosc", 300)) / length_factor, key="sug_w")
    with input_b:
        carton_h = st.number_input(f"Wysokość kartonu [{size_unit}]", min_value=0.0, value=float(physical.get("Wysokosc", 400)) / length_factor, key="sug_h")
        carton_mass = st.number_input(f"Masa kartonu [{weight_unit}]", min_value=0.0, value=float(physical.get("Waga", 1)) / weight_factor, key="sug_mass")
    with input_c:
        selected_pallet = st.selectbox("Paleta", list(all_pallets), key="sug_pallet")
        carton_qty = st.number_input("Liczba kartonów do wysłania", min_value=1, value=1, step=1, key="sug_qty")
        destination = st.text_input("Miejsce dostawy na etykiecie", key="sug_destination")
    opt_a, opt_b, opt_c = st.columns(3)
    with opt_a:
        layout_choice = st.selectbox("Wybór układu", ["Automatycznie najlepszy", "Oryginalnie", "Obrót 90°"], key="sug_layout_choice")
        vertical = st.checkbox("Można obracać karton pionowo", key="sug_vertical")
    with opt_b: can_stack = st.checkbox("Można piętrować kartony", value=True, key="sug_stack")
    with opt_c:
        max_height = st.number_input("Maks. wysokość palety [mm]", min_value=1.0, value=float(all_pallets[selected_pallet].get("MAX_H", product.get("Max_Wysokosc", 2000))), key="sug_max_height")
        max_weight = st.number_input("Maks. nośność [kg]", min_value=1.0, value=float(all_pallets[selected_pallet].get("MAX_W", product.get("Max_Waga", 500))), key="sug_max_weight")
    if st.button("🔍 Oblicz układ", key="sug_calculate", type="primary"):
        c_l, c_w, c_h, c_mass = carton_l * length_factor, carton_w * length_factor, carton_h * length_factor, carton_mass * weight_factor
        pallet = all_pallets[selected_pallet]
        if min(c_l, c_w, c_h, c_mass) <= 0:
            st.error("Nie można obliczyć: wszystkie wymiary i masa kartonu muszą być większe od zera.")
        else:
            orientations = [("Oryginalna", c_l, c_w, c_h, False), ("Obrót 90°", c_w, c_l, c_h, False), ("Mieszany / pionowy" if vertical else "Mieszany / zaawansowany", c_l, c_h if vertical else c_w, c_w if vertical else c_h, True)]
            variants = []
            for name, base_l, base_w, height, advanced in orientations:
                layout = deps["layout_mixed"](pallet["L"], pallet["W"], base_l, base_w) if advanced else deps["layout"](pallet["L"], pallet["W"], base_l, base_w)
                cartons_layer = len(layout); status, overhang = deps["overhang"](layout, pallet["L"], pallet["W"])
                by_height = int(max(0, max_height - pallet["H"]) // height)
                by_weight = int(max(0, max_weight - pallet.get("WEIGHT", 0)) // (cartons_layer * c_mass)) if cartons_layer else 0
                layers = min(by_height, by_weight, 1 if not can_stack else 10**6)
                variants.append({"Nazwa": name, "Układ": layout, "Kartonów/warstwę": cartons_layer, "Pełnych warstw": layers, "Pojemność": cartons_layer * layers, "Status": status, "Wystawanie mm": round(overhang, 1), "Wysokość kartonu": height})
            valid = [item for item in variants if item["Pojemność"] > 0]
            if not valid:
                st.error("Żaden wariant nie spełnia jednocześnie ograniczeń wysokości i nośności.")
            else:
                if layout_choice == "Oryginalnie": best = next((item for item in valid if item["Nazwa"] == "Oryginalna"), max(valid, key=lambda item: item["Pojemność"]))
                elif layout_choice == "Obrót 90°": best = next((item for item in valid if item["Nazwa"] == "Obrót 90°"), max(valid, key=lambda item: item["Pojemność"]))
                else: best = max(valid, key=lambda item: item["Pojemność"])
                full, remainder = divmod(int(carton_qty), best["Pojemność"]); pallets_count = full + (1 if remainder else 0); last = remainder or best["Pojemność"]
                last_layers = int(np.ceil(last / best["Kartonów/warstwę"])); loaded_height = pallet["H"] + best["Pełnych warstw"] * best["Wysokość kartonu"]
                gross_full, gross_last = best["Pojemność"] * c_mass + pallet.get("WEIGHT", 0), last * c_mass + pallet.get("WEIGHT", 0)
                gross_weight = gross_full if full else gross_last; total_weight = full * gross_full + (gross_last if remainder else 0)
                footprint = best["Kartonów/warstwę"] * (c_l * c_w) / (pallet["L"] * pallet["W"])
                stability = max(0, min(100, round(100 - max(0, loaded_height / min(pallet["L"], pallet["W"]) - 1) * 55 - max(0, 1 - footprint) * 25)))
                warnings = []
                if loaded_height > max_height or gross_weight > max_weight: warnings.append("Przekroczony limit wysokości lub nośności.")
                if best["Wystawanie mm"] > 0: warnings.append(f"Wykryto wystawanie poza obrys: {best['Wystawanie mm']} mm.")
                if stability < 60: warnings.append("Paleta wysoka lub niestabilna - wymagane dodatkowe zabezpieczenie.")
                optimized = optimize_pallet_layout(
                    carton_length=c_l, carton_width=c_w, carton_height=c_h, carton_mass=c_mass,
                    pallet=pallet, carton_quantity=carton_qty, max_height=max_height, max_weight=max_weight,
                    can_stack=can_stack, can_rotate_vertical=vertical, layout_standard=deps["layout"],
                    layout_mixed=deps["layout_mixed"], overhang_check=deps["overhang"], preferred_layout=layout_choice,
                )
                variants, best = optimized["variants"], optimized["best"]
                pallets_count, last, last_layers = optimized["pallet_count"], optimized["last_cartons"], optimized["last_layers"]
                report_cartons, report_layers = optimized["report_cartons"], optimized["report_layers"]
                cargo_dimensions = optimized["cargo_dimensions"]
                loaded_height, gross_weight, gross_last = optimized["loaded_height"], optimized["gross_weight"], optimized["gross_last"]
                total_weight, stability, warnings = optimized["total_gross_weight"], optimized["stability"], list(optimized["warnings"])
                bct = deps["bct_gate"](deps["current_order_id"](), report_layers, gross_weight, loaded_height)
                warnings.extend("Informacja BCT: " + reason for reason in bct["reasons"])
                selected_ean = physical.get("EAN") or {"Produkt": eans.get("produkt", ""), "Display": eans.get("display", ""), "Master Case": eans.get("master_case", "")}.get(level, "")
                result = {"order_id": deps["current_order_id"](), "source_module": "Inteligentne sugestie (4)", "Produkt": product_name, "SKU": product.get("SKU", ""), "Poziom obliczeń": level, "catalog_snapshot": catalog, "EAN produktu": eans.get("produkt", ""), "EAN displaya": eans.get("display", ""), "EAN Master Case": eans.get("master_case", ""), "EAN/GTIN": selected_ean, "EAN": selected_ean, "Paleta": selected_pallet, "Orientacja": best["Nazwa"], "Kartonów/warstwę": best["Kartonów/warstwę"], "Pełnych warstw": best["Pełnych warstw"], "Kartonów na pełnej palecie": best["Pojemność"], "Kartonów na wizualizowanej palecie": report_cartons, "Warstw wizualizowanej palety": report_layers, "Wymiary ładunku XYZ mm": cargo_dimensions, "Liczba palet": pallets_count, "Kartonów na ostatniej palecie": last, "Warstw na ostatniej palecie": last_layers, "Masa brutto/paleta kg": round(gross_weight, 2), "Masa brutto ostatniej palety kg": round(gross_last, 2), "Masa brutto całkowita kg": round(total_weight, 2), "Wymiary palety mm": [round(pallet["L"], 1), round(pallet["W"], 1), round(loaded_height, 1)], "Wysokość palety mm": round(loaded_height, 1), "Stabilność /100": stability, "Ocena stabilności": "stabilna" if stability >= 80 else "wymaga zabezpieczenia" if stability >= 60 else "ryzykowna", "Wystawanie mm": best["Wystawanie mm"], "Miejsce dostawy": destination, "Ostrzeżenia": warnings, "Warianty": variants, "BCT status": bct["status"], "BCT blokada": bct["blocked"], "BCT powody": bct["reasons"]}
                st.session_state["sug_layout_result"] = result; deps["update_snapshot"]("paletyzacja", result, result["order_id"]); deps["save_context"](result["order_id"]); st.success("Obliczenie gotowe. Wynik można przekazać do kolejnych modułów.")
    result = st.session_state.get("sug_layout_result")
    if not result:
        return
    st.markdown("### Wynik optymalizacji"); st.success(f"Rekomendacja: **{result['Orientacja']}** - do {result['Kartonów/warstwę']} kartonów na warstwę; wizualizacja i raport pokazują {result.get('Kartonów na wizualizowanej palecie', result['Kartonów na ostatniej palecie'])} kartonów w {result.get('Warstw wizualizowanej palety', result['Warstw na ostatniej palecie'])} warstwach.")
    for warning in result["Ostrzeżenia"]: st.warning(warning)
    st.dataframe(pd.DataFrame([{key: value for key, value in result.items() if key not in ["Warianty", "Ostrzeżenia"]}]), width="stretch", hide_index=True)
    st.markdown("#### Porównanie orientacji"); st.dataframe(pd.DataFrame([{key: value for key, value in item.items() if key not in ["Układ", "Wysokość kartonu"]} for item in result["Warianty"]]), width="stretch", hide_index=True)
    for column, variant in zip(st.columns(3), result["Warianty"]):
        with column:
            st.markdown(f"**{variant['Nazwa']}**")
            if variant["Układ"]: st.pyplot(deps["mini_chart"](0, 0, variant["Układ"], all_pallets.get(result["Paleta"], deps["pallet_types"]["EURO"]), f"{variant['Nazwa']} - {variant['Kartonów/warstwę']} kart."), clear_figure=True)
            else: st.warning("Brak poprawnego układu.")
    selected_variant = next((item for item in result["Warianty"] if item["Nazwa"] == result["Orientacja"]), None)
    if selected_variant and selected_variant.get("Układ"):
        st.markdown("#### Wizualizacja 2D rekomendowanej palety")
        palette_data = all_pallets.get(result["Paleta"], deps["pallet_types"]["EURO"])
        layout_figure = deps["full_chart"](
            0, 0, selected_variant["Wysokość kartonu"], selected_variant["Układ"],
            result.get("Warstw wizualizowanej palety", result["Pełnych warstw"]), result["Wysokość palety mm"], result["Kartonów/warstwę"], palette_data,
            cartons_to_show=result.get("Kartonów na wizualizowanej palecie"),
        )
        st.pyplot(layout_figure)
        layout_image_buffer = io.BytesIO()
        layout_figure.savefig(layout_image_buffer, format="png", dpi=180, bbox_inches="tight")
        plt.close(layout_figure)
        layout_pdf_key = f"pallet_layout_2d_pdf_{result.get('order_id', deps['current_order_id']())}"
        if st.button("Przygotuj raport PDF z wizualizacją 2D", icon=":material/picture_as_pdf:", key="sug_generate_layout_pdf"):
            layout_pdf = deps["build_layout_pdf"](
                result, layout_image_buffer.getvalue(), font_regular=deps["font_regular"], font_bold=deps["font_bold"],
            )
            st.session_state[layout_pdf_key] = layout_pdf
            deps["store_order_pdf"]("Raport paletyzacji 2D", layout_pdf, "raport_paletyzacji_2d.pdf", order_id=result.get("order_id"))
            st.success("Raport PDF zapisano w Centrum zlecenia.")
        if layout_pdf := st.session_state.get(layout_pdf_key):
            st.download_button("Pobierz raport PDF z wizualizacją 2D", layout_pdf, file_name="raport_paletyzacji_2d.pdf", mime="application/pdf", icon=":material/download:", key="sug_download_layout_pdf")
    with st.expander("📷 Odczytaj i sprawdź kod QR z etykiety paletowej", expanded=False):
        camera, upload = st.columns(2)
        with camera: captured = st.camera_input("Zrób zdjęcie kodu QR", key="sug_qr_camera")
        with upload: uploaded = st.file_uploader("Wgraj zdjęcie kodu QR", type=["png", "jpg", "jpeg"], key="sug_qr_upload")
        qr_file = captured if captured is not None else uploaded
        if qr_file is not None:
            qr_text, qr_error = deps["read_qr"](qr_file)
            if qr_error: st.warning(qr_error)
            else:
                try:
                    qr_data = json.loads(qr_text); st.success(f"Odczytano etykietę: paleta {qr_data.get('paleta', '?')} z {qr_data.get('z', '?')}.")
                    if str(qr_data.get("produkt", "")) == str(result["Produkt"]) and str(qr_data.get("ean", "")) == str(result.get("EAN", "")): st.success("Kod QR jest zgodny z aktualnym produktem i numerem EAN.")
                    else: st.error("Kod QR nie odpowiada aktualnemu produktowi lub numerowi EAN.")
                    st.json(qr_data)
                except json.JSONDecodeError: st.info(f"Odczytany kod QR: {qr_text}")
    label_pdf = deps["labels_pdf"](result, result.get("EAN", ""), result.get("Miejsce dostawy", ""))
    if st.button("💾 Zapisz etykiety w Centrum zlecenia", key="store_pallet_labels"):
        deps["labels_pdf"](result, result.get("EAN", ""), result.get("Miejsce dostawy", ""), store_document=True); st.success("Etykiety zapisano w Centrum zlecenia.")
    st.download_button("🏷️ Pobierz etykiety paletowe PDF", label_pdf, file_name="etykiety_paletowe.pdf", mime="application/pdf")
    st.markdown("#### Zapis obliczenia"); save_a, save_b = st.columns(2)
    with save_a:
        if st.button("💾 Zapisz wynik w sesji", key="sug_save_session"):
            st.session_state["sug_layout_session"] = result; st.success("Wynik zapisano w sesji aplikacji.")
    with save_b:
        if st.button("💾 Zapisz wynik do pliku", key="sug_save_file"):
            file_key = f"{result['Produkt']} - {result['Paleta']} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"; templates[file_key] = {"saved_at": datetime.now().isoformat(timespec="seconds"), "result": result}; deps["save_json"](template_path, templates); st.success("Wynik zapisano w pliku szablony_ukladu_palet.json. Będzie dostępny po restarcie aplikacji.")
    st.caption("Zapis sesyjny znika po zamknięciu aplikacji. Zapis do pliku pozostaje dostępny po restarcie i można go wczytać przyciskiem „Wczytaj z pliku”.")
