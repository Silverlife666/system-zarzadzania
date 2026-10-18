"""Widok modułu 8 wydzielony z app.py."""

def render_module_eight(st, deps):
    for _bridge_name, _bridge_value in deps.items():
        if not _bridge_name.startswith("__"):
            globals()[_bridge_name] = _bridge_value
    del _bridge_name, _bridge_value
    st.subheader("⚖️ Kalkulator Wytrzymałości i BCT (Na podstawie parametrów tektury)")
    st.markdown("Wprowadź parametry techniczne kartonu, aby automatycznie obliczyć jego wytrzymałość BCT i sprawdzić stabilność na palecie.")
    bct_db = wczytaj_produkty_z_db()
    bct_source = st.radio("Źródło danych kartonu", ["Ręczne", "Produkt z sekcji 1", "Mastercase z sekcji 7", "Paletyzacja z sekcji 2/4"], horizontal=True)
    bct_context = {}
    if bct_source == "Produkt z sekcji 1" and bct_db:
        bct_product = st.selectbox("Produkt", list(bct_db), key="bct_product")
        bct_context = bct_db[bct_product]
    elif bct_source == "Mastercase z sekcji 7": bct_context = st.session_state.get("box_rightsizing_result", {})
    elif bct_source == "Paletyzacja z sekcji 2/4": bct_context = st.session_state.get("sug_layout_result") or st.session_state.get("pal_calc_result") or {}
    bct_units_a, bct_units_b, bct_units_c = st.columns(3)
    with bct_units_a: bct_size_unit = st.selectbox("Wymiary", ["mm", "cm"], key="bct_size_unit")
    with bct_units_b: bct_weight_unit = st.selectbox("Masa", ["kg", "g"], key="bct_weight_unit")
    with bct_units_c: bct_method = st.selectbox("Metoda", ["Uproszczona", "McKee", "Wynik laboratoryjny"], key="bct_method")
    bct_length_factor = 1.0 if bct_size_unit == "mm" else 10.0
    bct_weight_factor = 1.0 if bct_weight_unit == "kg" else 0.001
    bct_document_language = st.selectbox("Język dokumentów BCT", ["PL", "EN", "PL/EN"], key="bct_document_language")
    bct_library = bct_load_json(BCT_LIBRARY_FILE, [])
    bct_templates = bct_load_json(BCT_TEMPLATE_FILE, {})
    with st.expander("📦 Szablony kartonów BCT", expanded=False):
        if bct_templates:
            selected_template = st.selectbox("Wczytaj szablon", list(bct_templates), key="bct_template_load")
            st.caption("Szablon zapisuje parametry konstrukcji; nie zastępuje archiwum wyników BCT.")
            if st.button("↩️ Wczytaj parametry szablonu"):
                template_params = bct_templates[selected_template].get("parameters", bct_templates[selected_template].get("context", {}))
                mapping = {"Waga":"stk_weight", "Dlugosc":"stk_blen", "Szerokosc":"stk_bwid", "Wysokosc":"stk_height", "Gramatura":"stk_gramatura"}
                for source_key, widget_key in mapping.items():
                    if source_key in template_params:
                        st.session_state[widget_key] = template_params[source_key]
                st.session_state["bct_loaded_template"] = bct_templates[selected_template]
                st.success("Parametry szablonu zostały wpisane do formularza.")
                st.rerun()
        template_name = st.text_input("Nazwa nowego szablonu", key="bct_template_name")
        if st.button("💾 Zapisz bieżący karton jako szablon") and template_name.strip():
            bct_templates[template_name.strip()] = {"saved_at": datetime.now().isoformat(timespec="seconds"), "source": bct_source, "context": bct_context, "parameters": {"Waga":st.session_state.get("stk_weight",0),"Dlugosc":st.session_state.get("stk_blen",0),"Szerokosc":st.session_state.get("stk_bwid",0),"Gramatura":st.session_state.get("stk_gramatura",0)}}
            bct_save_json(BCT_TEMPLATE_FILE, bct_templates)
            st.success("Szablon kartonu zapisano niezależnie od archiwum analiz.")
    with st.expander("📚 Biblioteka tektur dostawców", expanded=False):
        if bct_library:
            selected_board = st.selectbox("Zapisana tektura", [x["name"] for x in bct_library], key="bct_saved_board")
            board_data = next(x for x in bct_library if x["name"] == selected_board)
            st.json(board_data)
        with st.form("bct_board_library_form"):
            board_name = st.text_input("Nazwa / specyfikacja tektury")
            supplier = st.text_input("Dostawca")
            certificates = st.text_input("Certyfikaty FSC / PEFC")
            recycled = st.number_input("Udział recyklatu [%]", min_value=0.0, max_value=100.0, value=0.0)
            expiry = st.date_input("Ważność certyfikatu / specyfikacji")
            if st.form_submit_button("💾 Zapisz tekturę") and board_name.strip():
                bct_library = [x for x in bct_library if x["name"] != board_name.strip()] + [{"name":board_name.strip(),"supplier":supplier,"certificates":certificates,"recycled_pct":recycled,"expiry":str(expiry)}]
                bct_save_json(BCT_LIBRARY_FILE, bct_library); st.success("Tekturę zapisano w bibliotece.")
    
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        b_weight_raw = st.number_input(f"Waga brutto kartonu z towarem ({bct_weight_unit})", min_value=0.0, value=float(bct_context.get("Masa brutto/paleta kg", bct_context.get("Waga",10.0)))/bct_weight_factor, key="stk_weight")
        box_length_raw = st.number_input(f"Długość zewnętrzna kartonu ({bct_size_unit})", min_value=0.0, value=float(bct_context.get("Dlugosc",300.0))/bct_length_factor, key="stk_blen")
        box_width_raw = st.number_input(f"Szerokość zewnętrzna kartonu ({bct_size_unit})", min_value=0.0, value=float(bct_context.get("Szerokosc",200.0))/bct_length_factor, key="stk_bwid")
    with col_b2:
        b_layers = st.number_input("Planowana liczba warstw na palecie", min_value=1, value=int(bct_context.get("Pełnych warstw",5)), step=1, key="stk_layers")
        board_layers_type = st.selectbox("Struktura tektury", ["3-warstwowa", "4-warstwowa", "5-warstwowa", "7-warstwowa"], key="stk_board_layers")
        flute_type = st.selectbox("Typ fali", ["Fala E (micro)", "Fala F", "Fala B", "Fala C", "Fala EB (kombinowana)", "Fala BC (kombinowana)", "Fala EE", "Fala AC"], key="stk_flute")
    approved_pallet_height = st.number_input(
        "Maksymalna zatwierdzona wysokość palety [mm] (0 = bez limitu BCT)",
        min_value=0.0, value=0.0, step=10.0, key="bct_approved_pallet_height",
        help="Ten limit jest przekazywany do modułów 2 i 4 jako twarda bramka BCT.",
    )

    b_weight, box_length, box_width = b_weight_raw*bct_weight_factor, box_length_raw*bct_length_factor, box_width_raw*bct_length_factor
    ect_manual, bct_supplier, board_thickness = st.columns(3)
    with ect_manual: manual_ect = st.number_input("ECT z certyfikatu [kN/m]", min_value=0.0, value=0.0, key="bct_ect_manual")
    with bct_supplier: declared_bct = st.number_input("BCT deklarowane [kg]", min_value=0.0, value=0.0, key="bct_declared")
    with board_thickness: thickness_manual = st.number_input("Grubość tektury [mm]", min_value=0.0, value=0.0, key="bct_thickness")
    with st.expander("Konstrukcja kartonu i materiały", expanded=False):
        ci1,ci2,ci3=st.columns(3)
        with ci1: inner_length=st.number_input("Długość wewnętrzna [mm]",min_value=0.0,value=0.0); inner_width=st.number_input("Szerokość wewnętrzna [mm]",min_value=0.0,value=0.0); inner_height=st.number_input("Wysokość wewnętrzna [mm]",min_value=0.0,value=0.0)
        with ci2: product_net=st.number_input("Masa netto produktu [kg]",min_value=0.0,value=0.0); carton_mass=st.number_input("Masa kartonu [kg]",min_value=0.0,value=0.0); filler_mass=st.number_input("Przekładki i wypełnienia [kg]",min_value=0.0,value=0.0)
        with ci3: fefco_bct=st.selectbox("FEFCO",["0201","0215","0427","0470","Inny"]); closure_bct=st.selectbox("Zamknięcie",["Klapy","Automatyczne dno","Tacka","Obwoluta"]); flap_size=st.number_input("Wymiar klap [mm]",min_value=0.0,value=0.0)
        weakening=st.multiselect("Elementy osłabiające",["Perforacja","Uchwyty","Okienka","Wycięcia"])
        st.caption("Warstwy papieru: wpisz gramaturę i rodzaj papieru dla każdej warstwy tektury.")
        paper_layers=st.data_editor(pd.DataFrame([{"Warstwa":1,"Gramatura g/m²":480,"Papier":"testliner"}]),num_rows="dynamic",key="bct_paper_layers")

    gramatura = st.number_input("Gramatura całkowita tektury (g/m²)", min_value=200, max_value=1200, value=480, step=10, key="stk_gramatura")

    bct_result_for_active_order = (
        st.session_state.get("bct_last_result", {}).get("order_id") == get_current_order_id()
    )
    if st.button("🔍 Oblicz BCT i sprawdź bezpieczeństwo", key="btn_stacking_calc") or bct_result_for_active_order:
        if product_net + carton_mass + filler_mass > 0:
            b_weight = product_net + carton_mass + filler_mass
        if min(b_weight, box_length, box_width) <= 0:
            st.error("Nie można obliczyć BCT: masa i wymiary kartonu muszą być większe od zera.")
            st.stop()
        if "E" in flute_type and "B" not in flute_type:
            board_thickness = 1.4
        elif "B" in flute_type and "C" not in flute_type and "E" not in flute_type:
            board_thickness = 3.0
        elif "C" in flute_type and "B" not in flute_type:
            board_thickness = 4.0
        elif "BC" in flute_type:
            board_thickness = 7.0
        elif "EB" in flute_type:
            board_thickness = 4.8
        else:
            board_thickness = 4.0
            
        if "5" in board_layers_type:
            ect_factor = 0.0145
        elif "4" in board_layers_type:
            ect_factor = 0.0135
        else:
            ect_factor = 0.0120
            
        estimated_ect = manual_ect if manual_ect > 0 else gramatura * ect_factor
        if thickness_manual > 0:
            board_thickness = thickness_manual
        bct_metrics = calculate_bct(
            estimated_ect, board_thickness, box_length, box_width, b_weight, b_layers, weakening,
            laboratory_bct_kg=declared_bct, use_laboratory_result=bct_method == "Wynik laboratoryjny",
        )
        mckee_bct = bct_metrics["mckee_bct"]
        bct_calculated = bct_metrics["bct"]
        safe_bct = bct_metrics["safe_bct"]
        total_load = bct_metrics["total_load"]
        max_safe_layers = bct_metrics["max_safe_layers"]
        max_safe_pallet_mass = bct_metrics["max_safe_pallet_mass_kg"]
        margin_pct = bct_metrics["margin_pct"]
        risk = bct_metrics["risk"]
        st.session_state["bct_last_result"] = {"order_id": get_current_order_id(), "safe_bct": safe_bct, "bct": bct_calculated, "layers": b_layers, "weight": b_weight, "max_safe_layers":max_safe_layers, "max_safe_pallet_mass_kg": max_safe_pallet_mass, "max_safe_pallet_height_mm": float(approved_pallet_height), "risk":risk, "material":board_layers_type, "flute":flute_type}
        st.session_state["bct_last_result"]["language"] = bct_document_language
        
        st.markdown("---")
        st.markdown("#### Wyniki obliczeń inżynierskich:")
        
        col_res1, col_res2, col_res3 = st.columns(3)
        with col_res1:
            st.metric("Szacowany ECT", f"{estimated_ect:.2f} kN/m")
        with col_res2:
            st.metric("Wytrzymałość BCT", f"{bct_calculated:.1f} kg")
        with col_res3:
            st.metric("Bezpieczne BCT (SF 1.8)", f"{safe_bct:.1f} kg")
            
        st.write(f"- Szacowany nacisk spoczywający na dolnej warstwie: **{total_load:.1f} kg**")
        
        st.markdown("---")
        if total_load < safe_bct:
            st.success(f"✅ **Bezpieczny margines wytrzymałości (Struktura stabilna).** Dopuszczalne bezpieczne obciążenie ({safe_bct:.1f} kg) jest wyższe niż nacisk ({total_load:.1f} kg).")
        else:
            st.warning(f"⚠️ **Ryzyko zgniecenia dolnych kartonów!** Nacisk ({total_load:.1f} kg) przekracza bezpieczny próg BCT ({safe_bct:.1f} kg). Zwiększ gramaturę, liczbę warstw tektury lub zmniejsz liczbę warstw na palecie.")
        recommendations = []
        if risk != "bezpieczne": recommendations.append("Zwiększ falę, gramaturę lub strukturę tektury; ewentualnie zmniejsz wysokość palety.")
        if board_thickness < 2.0: recommendations.append("Rozważ większą grubość tektury.")
        st.write("**Ocena ryzyka:**", risk, "| **Maks. bezpieczne warstwy:**", max_safe_layers, "| **Maks. masa palety:**", f"{max_safe_pallet_mass} kg", "| **Margines:**", f"{safe_bct-total_load:.1f} kg ({margin_pct:.0f}%)")
        if declared_bct > 0:
            st.write(f"**Porównanie z deklaracją dostawcy:** obliczone {bct_calculated:.1f} kg / deklarowane {declared_bct:.1f} kg")
            if bct_calculated <= declared_bct: st.success("BCT obliczone jest zgodne z deklarowanym przez dostawcę.")
            else: st.warning("BCT obliczone przekracza deklarację dostawcy - konstrukcja wymaga weryfikacji.")
        bct_approval = st.selectbox("Status konstrukcji BCT", ["roboczy", "do testu", "zatwierdzony", "wycofany"], key="bct_approval")
        st.session_state["bct_last_result"]["approval"] = bct_approval
        sign_a, sign_b, sign_c = st.columns(3)
        with sign_a: constructor_sign = st.text_input("Konstruktor", key="bct_constructor")
        with sign_b: quality_sign = st.text_input("Jakość", key="bct_quality")
        with sign_c: warehouse_sign = st.text_input("Magazyn", key="bct_warehouse")
        st.session_state["bct_last_result"]["signatures"] = {"constructor":constructor_sign,"quality":quality_sign,"warehouse":warehouse_sign}
        if recommendations: st.info(" ".join(recommendations))
        if risk == "bezpieczne":
            board_recommendation = f"Utrzymaj {board_layers_type}, falę {flute_type}, minimum {gramatura} g/m²."
        elif risk == "warunkowo bezpieczne":
            board_recommendation = f"Zalecenie: tektura 5-warstwowa, fala BC lub EB, minimum {int(gramatura + 80)} g/m²."
        else:
            board_recommendation = f"Zalecenie: tektura 7-warstwowa, fala BC/AC, minimum {int(gramatura + 150)} g/m² oraz redukcja liczby warstw."
        st.success("**Rekomendowana konstrukcja:** " + board_recommendation)
        st.session_state["bct_last_result"]["recommendation"] = board_recommendation
        # Zatwierdzenie BCT jest jedną z automatycznych bramek procesu zlecenia.
        save_order_context()
        update_order_lifecycle_status(get_current_order_id())
        bct_report_pdf = generuj_pdf_raport_bct(st.session_state["bct_last_result"])
        bct_report_col1, bct_report_col2 = st.columns(2)
        with bct_report_col1:
            st.download_button("📄 Pobierz raport BCT PDF", bct_report_pdf, file_name="raport_bct.pdf", mime="application/pdf")
        with bct_report_col2:
            if st.button("💾 Zapisz raport BCT w Centrum zlecenia", key="store_bct_report"):
                generuj_pdf_raport_bct(st.session_state["bct_last_result"], store_document=True)
                st.success("Raport BCT zapisano w Centrum zlecenia.")
        with st.expander("📋 Specyfikacja dla drukarni / producenta kartonów", expanded=False):
            specification = f"""SPECYFIKACJA KARTONU / CARTON SPECIFICATION
Język / Language: {bct_document_language}
FEFCO: {fefco_bct} | Zamknięcie: {closure_bct} | Klapy: {flap_size} mm
Wymiary zewnętrzne: {box_length:.0f} x {box_width:.0f} mm | Wewnętrzne: {inner_length:.0f} x {inner_width:.0f} x {inner_height:.0f} mm
Tektura: {board_layers_type}, fala {flute_type}, gramatura: {gramatura} g/m², grubość: {board_thickness:.1f} mm
ECT: {estimated_ect:.2f} kN/m | BCT wymagane: {bct_calculated:.1f} kg | BCT bezpieczne: {safe_bct:.1f} kg
Osłabienia: {', '.join(weakening) if weakening else 'brak'}
Status BCT: {bct_approval}
Podpis konstruktor: {constructor_sign} | jakość: {quality_sign} | magazyn: {warehouse_sign}"""
            st.text_area("Treść specyfikacji", specification, height=260, key="bct_supplier_spec")
            st.download_button("⬇️ Pobierz specyfikację TXT", specification.encode("utf-8"), file_name="specyfikacja_kartonu.txt", mime="text/plain")
        with st.expander("✅ Karta kontroli jakości kartonu", expanded=False):
            qa_checks = {
                "Wymiary kartonu zgodne ze specyfikacją": False,
                "Tektura, fala i gramatura zgodne z zamówieniem": False,
                "Brak uszkodzeń, perforacji i wad klejenia": False,
                "BCT oraz liczba warstw spełniają wymagania": False,
                "Oznaczenia, EAN i numer partii są czytelne": False,
            }
            completed = []
            for label in qa_checks:
                if st.checkbox(label, key=f"bct_qa_{label}"): completed.append(label)
            st.progress(len(completed) / len(qa_checks))
            st.caption(f"Wynik kontroli: {len(completed)} z {len(qa_checks)} punktów potwierdzonych.")
            qa_pdf=generuj_pdf_bct_dokument("KARTA KONTROLI JAKOŚCI KARTONU",[f"□ {label}" for label in qa_checks]+[f"Konstruktor: {constructor_sign}",f"Jakość: {quality_sign}",f"Magazyn: {warehouse_sign}"])
            st.download_button("📄 Pobierz kartę kontroli PDF",qa_pdf,file_name="karta_kontroli_kartonu.pdf",mime="application/pdf")
            if st.button("💾 Zapisz kartę kontroli w Centrum zlecenia", key="store_bct_quality_card"):
                store_order_pdf("Karta kontroli jakości", qa_pdf, "karta_kontroli_kartonu.pdf")
                st.success("Kartę kontroli zapisano w Centrum zlecenia.")
        supplier_pdf=generuj_pdf_bct_dokument("SPECYFIKACJA DLA PRODUCENTA KARTONÓW",[specification])
        instruction_pdf=generuj_pdf_bct_dokument("INSTRUKCJA PALETYZACJI",[f"Maksymalna bezpieczna liczba warstw: {max_safe_layers}.",f"Maksymalna bezpieczna masa palety: {max_safe_pallet_mass} kg.","Nie przekraczać limitu; kontrolować dolne warstwy i narożniki."])
        pdf_a,pdf_b=st.columns(2)
        with pdf_a:
            st.download_button("📄 Pobierz specyfikację producenta PDF",supplier_pdf,file_name="specyfikacja_producenta_kartonow.pdf",mime="application/pdf")
            if st.button("💾 Zapisz specyfikację producenta", key="store_bct_supplier_spec"):
                store_order_pdf("Specyfikacja producenta", supplier_pdf, "specyfikacja_producenta_kartonow.pdf")
                st.success("Specyfikację zapisano w Centrum zlecenia.")
        with pdf_b:
            st.download_button("📄 Pobierz instrukcję paletyzacji PDF",instruction_pdf,file_name="instrukcja_paletyzacji_bct.pdf",mime="application/pdf")
            if st.button("💾 Zapisz instrukcję paletyzacji", key="store_bct_pallet_instruction"):
                store_order_pdf("Instrukcja paletyzacji", instruction_pdf, "instrukcja_paletyzacji_bct.pdf")
                st.success("Instrukcję zapisano w Centrum zlecenia.")
        simulation_layers = list(range(1, max(max_safe_layers + 3, b_layers + 2)))
        simulation_loads = [b_weight * (layer - 1) for layer in simulation_layers]
        fig_bct, ax_bct = plt.subplots(figsize=(7, 3.2))
        ax_bct.plot(simulation_layers, simulation_loads, marker="o", label="Obciążenie dolnego kartonu")
        ax_bct.axhline(safe_bct, color="#16A34A", linestyle="--", label="Bezpieczne BCT")
        ax_bct.axhline(bct_calculated, color="#DC2626", linestyle=":", label="BCT nominalne")
        ax_bct.set_xlabel("Liczba warstw"); ax_bct.set_ylabel("Obciążenie [kg]"); ax_bct.set_title("Symulacja wpływu liczby warstw na ryzyko zgniecenia"); ax_bct.legend(); ax_bct.grid(alpha=.25)
        st.pyplot(fig_bct, clear_figure=True)
        png_buffer = BytesIO(); fig_bct.savefig(png_buffer, format="png", dpi=180, bbox_inches="tight"); png_buffer.seek(0)
        st.download_button("🖼️ Pobierz wykres BCT (PNG)", png_buffer.getvalue(), file_name="symulacja_bct.png", mime="image/png")
        support_area = box_length * box_width
        pallet_area = float((st.session_state.get("sug_layout_result") or st.session_state.get("pal_calc_result") or {}).get("Paleta powierzchnia mm2", 1200*800))
        if support_area < pallet_area * 0.08:
            st.warning("Mała powierzchnia podparcia kartonu - sprawdź stabilność i zastosuj przekładkę.")
        grammar_sim = [max(100, gramatura-80), gramatura, gramatura+80]
        st.dataframe(pd.DataFrame({"Gramatura g/m²":grammar_sim,"Szacowane BCT kg":[round(bct_calculated*(g/gramatura),1) for g in grammar_sim]}),hide_index=True,width="stretch")
        st.caption("Mapa ryzyka: dolne warstwy są najbardziej obciążone; narożniki i środek ściany wymagają szczególnej kontroli przy ryzyku warunkowym lub wyższym.")
        active_bct_order_id = get_current_order_id()
        bct_record = {"order_id":active_bct_order_id,"saved_at":datetime.now().isoformat(timespec="seconds"),"source":bct_source,"method":bct_method,"result":st.session_state["bct_last_result"],"supplier_bct":declared_bct,"ect":estimated_ect,"recommendations":recommendations}
        save_bct_a, save_bct_b = st.columns(2)
        with save_bct_a:
            if st.button("💾 Zapisz analizę BCT do archiwum"):
                archive=bct_load_json(BCT_ARCHIVE_FILE,[])
                order_versions=[item for item in archive if item.get("order_id") == active_bct_order_id]
                bct_record["version"]=(max((safe_int(item.get("version"), 0) for item in order_versions), default=0) + 1)
                archive.append(bct_record)
                bct_save_json(BCT_ARCHIVE_FILE,archive)
                register_document("Analiza BCT", {"version":bct_record["version"],"risk":risk,"approval":bct_approval}, order_id=active_bct_order_id)
                save_order_context(active_bct_order_id)
                st.success(f"Analizę zapisano jako wersję v{bct_record['version']} zlecenia {active_bct_order_id}.")
        with save_bct_b:
            if st.button("🔗 Przekaż wynik do paletyzacji i Packing List"):
                st.session_state["bct_for_palletization"]=st.session_state["bct_last_result"]
                st.session_state["bct_for_packing_list"]=st.session_state["bct_last_result"]
                st.success("Wynik przekazano do dalszych modułów.")
        if st.button("🔗 Przekaż BCT do TDS, PPWR, Karty Pracy, zamówienia i e-maila"):
            result_bct=st.session_state["bct_last_result"]
            st.session_state["bct_for_tds"]=result_bct; st.session_state["bct_for_ppwr"]=result_bct
            st.session_state["bct_for_worksheet"]=result_bct; st.session_state["bct_for_order"]=result_bct
            stored_bct_pdf = generuj_pdf_raport_bct(result_bct, store_document=True)
            st.session_state["email_bct_report_pending"]={"name":"raport_bct.pdf","data":stored_bct_pdf,"mime":"application/pdf"}
            st.success("Wynik BCT został przekazany do TDS, PPWR, Karty Pracy, zamówienia i e-maila.")
        with st.expander("📚 Szablony i archiwum analiz BCT", expanded=False):
            bct_versions=[item for item in bct_load_json(BCT_ARCHIVE_FILE,[]) if item.get("order_id") == active_bct_order_id]
            if bct_versions:
                version_labels=[f"v{x.get('version','?')} - {x.get('saved_at','')}" for x in bct_versions]
                chosen_version=st.selectbox("Wersja archiwalna",version_labels,key="bct_restore_version")
                if st.button("↩️ Przywróć wybraną wersję"):
                    restored=bct_versions[version_labels.index(chosen_version)]["result"]
                    restored["order_id"] = active_bct_order_id
                    st.session_state["bct_last_result"]=restored; st.success("Przywrócono wersję analizy BCT.")
                st.dataframe(pd.DataFrame([{ "Wersja":x.get("version"),"Data":x.get("saved_at"),"Metoda":x.get("method"),"Ryzyko":x.get("result",{}).get("risk"),"Status":x.get("result",{}).get("approval")} for x in bct_versions]),hide_index=True,width="stretch")
            else: st.info(f"Brak zapisanych wersji BCT dla zlecenia {active_bct_order_id}.")


def _legacy_generate_ppwr_mass_specification_pdf(metadata, components, material_summary, language="en", store_document=False):
    """Tworzy raport masy i materiałów PPWR w języku polskim lub angielskim."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=25,
        rightMargin=25,
        topMargin=48,
        bottomMargin=42,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "PPWRTitle", parent=styles["Heading1"], fontName=FONT_BOLD,
        fontSize=18, leading=22, textColor=colors.HexColor("#123B66"), spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "PPWRSubtitle", parent=styles["Normal"], fontName=FONT_REGULAR,
        fontSize=8.5, leading=11, textColor=colors.HexColor("#475569"), spaceAfter=12,
    )
    body_style = ParagraphStyle(
        "PPWRBody", parent=styles["Normal"], fontName=FONT_REGULAR,
        fontSize=7, leading=8.5, textColor=colors.HexColor("#0F172A"),
    )
    header_style = ParagraphStyle(
        "PPWRHeader", parent=body_style, fontName=FONT_BOLD,
        fontSize=6.8, leading=8, textColor=colors.white, alignment=1,
    )
    section_style = ParagraphStyle(
        "PPWRSection", parent=styles["Heading2"], fontName=FONT_BOLD,
        fontSize=10.5, leading=13, textColor=colors.HexColor("#123B66"),
        spaceBefore=11, spaceAfter=6,
    )

    def cell(value, style=body_style):
        return Paragraph(escape(str(value if value is not None else "-")), style)

    def number(value, digits=3):
        return format_ppwr_number(value, digits)

    pl = language == "pl"
    text = {
        "title": "SPECYFIKACJA MASY I MATERIAŁÓW OPAKOWAŃ" if pl else "PACKAGING MASS AND MATERIAL SPECIFICATION",
        "subtitle": "PPWR B2B - zestawienie techniczne wygenerowane z bieżącego rejestru komponentów" if pl else "PPWR B2B - technical mass statement | Generated from the current component register",
        "product": "Produkt / pozycja" if pl else "Product / Item",
        "client": "Klient / marka" if pl else "Client / Brand",
        "issue_date": "Data wystawienia" if pl else "Issue date",
        "issuer_vat": "NIP / VAT ID wystawcy" if pl else "Issuer VAT ID / NIP",
        "version": "Wersja dokumentu" if pl else "Document version",
        "working": "1.0 (kalkulacja robocza)" if pl else "1.0 (working calculation)",
        "units_display": "Sztuk w displayu" if pl else "Units per display",
        "displays_pallet": "Displayów na palecie" if pl else "Displays per pallet",
        "units_pallet": "Sztuk na palecie" if pl else "Units per pallet",
        "pallets_order": "Palet w zamówieniu" if pl else "Pallets in order",
        "mass_sku": "MASA / 1 SKU" if pl else "MASS PER 1 SKU",
        "mass_pallet": "MASA / 1 PALETĘ" if pl else "MASS PER PALLET",
        "mass_order": "MASA / CAŁE ZAMÓWIENIE" if pl else "MASS FOR ENTIRE ORDER",
        "components_section": "1. Rejestr komponentów opakowania" if pl else "1. Packaging component register",
        "materials_section": "2. Podział masy według materiałów" if pl else "2. Material mass split",
        "calculation_section": "3. Podstawa obliczeń i dokumentacja techniczna" if pl else "3. Calculation basis and technical-file note",
    }
    component_headers = (
        ["Lp.", "Komponent opakowania", "Poziom", "Materiał główny", "Surowiec", "Masa jednostkowa (g)", "Ilość / SKU", "Ilość / paletę", "Masa / SKU (g)", "Masa / paletę (kg)", "Masa / zamówienie (kg)", "Kolor / druk / uwagi"]
        if pl else
        ["No.", "Packaging component", "Level", "Main material", "Raw material", "Unit mass (g)", "Qty / SKU", "Qty / pallet", "Mass / SKU (g)", "Mass / pallet (kg)", "Mass / order (kg)", "Colour / print / notes"]
    )
    material_headers = (
        ["Materiał główny", "Masa / SKU (g)", "Udział / SKU (%)", "Masa / paletę (kg)", "Udział / paletę (%)", "Masa / zamówienie (kg)", "Udział / zamówienie (%)"]
        if pl else
        ["Main material", "Mass / SKU (g)", "Share / SKU (%)", "Mass / pallet (kg)", "Share / pallet (%)", "Mass / order (kg)", "Share / order (%)"]
    )
    calculation_note = (
        "Masa / 1 SKU = masa jednostkowa × (ilość / SKU + ilość / paletę / liczba SKU na palecie). Masa / paletę = masa / 1 SKU × liczba SKU na palecie. Masa / zamówienie = masa / paletę × liczba palet. Raport jest kontrolowaną kalkulacją roboczą i powinien być przechowywany wraz ze specyfikacjami dostawców, deklaracjami materiałowymi oraz dowodami zgodności."
        if pl else
        "Mass per SKU = unit mass x (quantity per SKU + quantity per pallet / units per pallet). Mass per pallet = mass per SKU x units per pallet. Mass for the order = mass per pallet x number of pallets. This report is a controlled working calculation and should be retained with supplier specifications, material declarations and compliance evidence."
    )

    story = [
        Paragraph(text["title"], title_style),
        Paragraph(text["subtitle"], subtitle_style),
    ]

    info_rows = [
        [cell(text["product"]), cell(metadata["product_name"]), cell("SKU / EAN"), cell(metadata["sku"] or "-" )],
        [cell(text["client"]), cell(metadata["client"] or "-"), cell(text["issue_date"]), cell(datetime.now().strftime("%d.%m.%Y"))],
        [cell(text["issuer_vat"]), cell(metadata.get("nip", "-") or "-"), cell(text["version"]), cell(text["working"])],
        [cell(text["units_display"]), cell(metadata["units_per_display"]), cell(text["displays_pallet"]), cell(metadata["displays_per_pallet"])],
        [cell(text["units_pallet"]), cell(f"{metadata['units_per_pallet']:,}"), cell(text["pallets_order"]), cell(metadata["pallets_per_order"])],
    ]
    info_table = Table(info_rows, colWidths=[115, 280, 115, 272])
    info_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E8F0F8")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#E8F0F8")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([info_table, Spacer(1, 10)])

    summary_rows = [
        [cell(text["mass_sku"], header_style), cell(text["mass_pallet"], header_style), cell(text["mass_order"], header_style)],
        [
            cell(f"{number(metadata['total_sku_g'])} g"),
            cell(f"{number(metadata['total_pallet_kg'])} kg"),
            cell(f"{number(metadata['total_order_kg'])} kg"),
        ],
    ]
    summary_table = Table(summary_rows, colWidths=[260, 260, 262])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#123B66")),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#F1F5F9")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#94A3B8")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.extend([summary_table, Paragraph(text["components_section"], section_style)])
    component_rows = [[cell(label, header_style) for label in component_headers]]
    for index, (_, item) in enumerate(components.iterrows(), start=1):
        component_rows.append([
            cell(index),
            cell(item.get("Komponent opakowania", "")),
            cell(item.get("Poziom opakowania", "")),
            cell(item.get("Materiał główny", "")),
            cell(item.get("Surowiec", "")),
            cell(number(item.get("Masa jednostkowa (g)", 0))),
            cell(number(item.get("Ilość / 1 SKU", 0), 2)),
            cell(number(item.get("Ilość / 1 paletę", 0), 2)),
            cell(number(item.get("Masa / 1 SKU (g)", 0))),
            cell(number(item.get("Masa / 1 paletę (kg)", 0))),
            cell(number(item.get("Masa / zamówienie (kg)", 0))),
            cell(item.get("Kolor / druk / uwagi", "")),
        ])
    component_table = Table(
        component_rows,
        colWidths=[20, 91, 59, 53, 66, 43, 39, 43, 49, 53, 53, 113],
        repeatRows=1,
    )
    component_style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#123B66")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]
    for row_index in range(1, len(component_rows)):
        if row_index % 2 == 0:
            component_style.append(("BACKGROUND", (0, row_index), (-1, row_index), colors.HexColor("#F8FAFC")))
    component_table.setStyle(TableStyle(component_style))
    story.extend([component_table, Paragraph(text["materials_section"], section_style)])
    material_rows = [[cell(label, header_style) for label in material_headers]]
    for _, item in material_summary.iterrows():
        material_rows.append([
            cell(item.get("Materiał główny", "")),
            cell(number(item.get("Masa / 1 SKU (g)", 0))),
            cell(number(item.get("Udział / 1 SKU (%)", 0), 1)),
            cell(number(item.get("Masa / 1 paletę (kg)", 0))),
            cell(number(item.get("Udział / 1 paleta (%)", 0), 1)),
            cell(number(item.get("Masa / zamówienie (kg)", 0))),
            cell(number(item.get("Udział / zamówienie (%)", 0), 1)),
        ])
    material_table = Table(material_rows, colWidths=[180, 95, 85, 105, 95, 115, 105], repeatRows=1)
    material_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#123B66")),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.extend([
        material_table,
        Paragraph(text["calculation_section"], section_style),
        Paragraph(calculation_note, body_style),
    ])
    story.extend(bct_pdf_section())
    class LocalPPWRCanvas(PPWRCanvas):
        HEADER_LABEL = text["title"]
    doc.build(story, canvasmaker=LocalPPWRCanvas)
    pdf_bytes = buffer.getvalue()
    if store_document:
        store_order_pdf("Raport PPWR", pdf_bytes, f"raport_ppwr_{language}.pdf", {"language": language})
    return pdf_bytes


def generate_ppwr_mass_specification_pdf(metadata, components, material_summary, language="en", store_document=False):
    """Warstwa aplikacji raportu PPWR: generator i rejestr dokumentów są rozdzielone."""
    title = "SPECYFIKACJA MASY I MATERIAŁÓW OPAKOWAŃ" if language == "pl" else "PACKAGING MASS AND MATERIAL SPECIFICATION"
    class LocalPPWRCanvas(PPWRCanvas):
        HEADER_LABEL = title
        FOOTER_LABEL = "System Zarządzania Produkcją - made by Adrian" if language == "pl" else "Production Management System - made by Adrian"
        PAGE_LABEL = "Strona" if language == "pl" else "Page"
    pdf_bytes = build_ppwr_mass_specification_pdf(
        metadata, components, material_summary, language=language,
        font_regular=FONT_REGULAR, font_bold=FONT_BOLD,
        bct_flowables=bct_pdf_section(), canvasmaker=LocalPPWRCanvas,
    )
    if store_document:
        store_order_pdf("Raport PPWR", pdf_bytes, f"raport_ppwr_{language}.pdf", {"language": language})
    return pdf_bytes


def generate_eu_declaration_of_conformity_pdf(issuer, customer, products, confirmations, language="en", store_document=False):
    """Tworzy deklarację zgodności PPWR w wybranym języku."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=45, rightMargin=45, topMargin=52, bottomMargin=48
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle("EUDeclTitle", parent=styles["Heading1"], fontName=FONT_BOLD, fontSize=16,
                           leading=20, textColor=colors.HexColor("#123B66"), spaceAfter=5)
    body = ParagraphStyle("EUDeclBody", parent=styles["Normal"], fontName=FONT_REGULAR, fontSize=9,
                          leading=13, textColor=colors.HexColor("#0F172A"), spaceAfter=7)
    section = ParagraphStyle("EUDeclSection", parent=styles["Heading2"], fontName=FONT_BOLD, fontSize=10,
                             leading=13, textColor=colors.HexColor("#123B66"), spaceBefore=9, spaceAfter=5)
    table_header = ParagraphStyle("EUDeclHeader", parent=body, fontName=FONT_BOLD, fontSize=8,
                                  leading=9, textColor=colors.white, alignment=1)

    def p(value, style=body):
        return Paragraph(escape(str(value if value else "-")), style)

    pl = language == "pl"
    text = {
        "title": "DEKLARACJA ZGODNOŚCI UE (PPWR)" if pl else "EU DECLARATION OF CONFORMITY (PPWR)",
        "issuer": "1. DANE PRODUCENTA / WYSTAWCY DEKLARACJI" if pl else "1. MANUFACTURER / DECLARATION ISSUER DETAILS",
        "customer": "2. DANE KLIENTA / ODBIORCY" if pl else "2. CUSTOMER / CONSIGNEE DETAILS",
        "subject": "3. PRZEDMIOT DEKLARACJI" if pl else "3. SUBJECT OF DECLARATION",
        "statement": "4. OŚWIADCZENIE O ZGODNOŚCI Z PPWR" if pl else "4. EU COMPLIANCE STATEMENT",
        "support": "5. DOKUMENTACJA WSPARCIA / PLIK TECHNICZNY" if pl else "5. SUPPORTING DOCUMENTATION / TECHNICAL FILE",
        "signature": "6. WYSTAWIENIE I PODPIS" if pl else "6. AUTHORISED ISSUE AND SIGNATURE",
        "company": "Nazwa firmy" if pl else "Company name",
        "vat": "NIP / VAT ID" if pl else "VAT ID",
        "address": "Adres rejestrowy" if pl else "Registered address",
        "issue_date": "Data wystawienia" if pl else "Issue date",
        "contact": "Osoba kontaktowa" if pl else "Contact person",
        "place": "Miejsce wystawienia" if pl else "Place of issue",
        "no": "Lp." if pl else "No.",
        "product": "Produkt / komponent" if pl else "Product / component",
        "batch": "Partia / dowód" if pl else "Batch / evidence",
        "confirmed": "POTWIERDZONE PRZEZ PRZYGOTOWUJĄCEGO" if pl else "CONFIRMED BY PREPARER",
        "pending": "DO POTWIERDZENIA" if pl else "PENDING VERIFICATION",
    }
    declaration_text = (
        "Wystawca oświadcza z pełną odpowiedzialnością, że wskazane opakowania zostały ocenione pod kątem wymagań rozporządzenia (UE) 2025/40 w sprawie opakowań i odpadów opakowaniowych (PPWR)."
        if pl else
        "The issuer declares, under its sole responsibility, that the listed packaging is assessed against the applicable requirements of Regulation (EU) 2025/40 on packaging and packaging waste (PPWR)."
    )
    support_text = (
        "Deklarację wspierają: specyfikacja masy i materiałów opakowaniowych, deklaracje dostawców, dokumentacja SDS/TDS oraz dowody potwierdzeń wskazanych poniżej."
        if pl else
        "This declaration is supported by the Packaging Mass & Material Specification, supplier declarations, SDS/TDS documentation, and evidence for the confirmations below."
    )

    story = [
        Paragraph(text["title"], title),
        Paragraph(text["issuer"], section),
    ]
    issuer_table = Table([
        [p(text["company"]), p(issuer["company"]), p(text["vat"]), p(issuer["nip"])],
        [p(text["address"]), p(issuer["address"]), p(text["issue_date"]), p(issuer["issue_date"].strftime("%d.%m.%Y"))],
        [p(text["contact"]), p(issuer["contact"]), p(text["place"]), p(issuer["place"])],
    ], colWidths=[100, 180, 100, 145])
    issuer_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E8F0F8")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#E8F0F8")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.extend([issuer_table, Paragraph(text["customer"], section)])
    
    customer_table = Table([
        [p(text["company"]), p(customer["company"]), p(text["vat"]), p(customer["nip"])],
        [p(text["address"]), p(customer["address"]), p(""), p("")]
    ], colWidths=[100, 180, 100, 145])
    customer_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F8FAFC")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#F8FAFC")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.extend([customer_table, Paragraph(text["subject"], section)])
    
    product_rows = [[p(text["no"], table_header), p(text["product"], table_header), p("SKU / EAN", table_header), p(text["batch"], table_header)]]
    for index, (_, product) in enumerate(products.iterrows(), start=1):
        product_rows.append([
            p(index), p(product.get("Produkt / komponent", "")), p(product.get("SKU / EAN", "")), p(product.get("Partia / dowód", "")),
        ])
    product_table = Table(product_rows, colWidths=[35, 245, 125, 120], repeatRows=1)
    product_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#123B66")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.extend([product_table, Paragraph(text["statement"], section)])
    story.append(Paragraph(declaration_text, body))
    for label, confirmed in confirmations.items():
        status = text["confirmed"] if confirmed else text["pending"]
        story.append(Paragraph(f"<b>{escape(label)}:</b> {status}", body))
    story.extend([
        Paragraph(text["support"], section),
        Paragraph(support_text, body),
        Paragraph(text["signature"], section),
        Paragraph(f"{'Osoba upoważniona' if pl else 'Authorised person'}: {escape(issuer['contact'])}<br/>{'Podpis i pieczęć firmowa' if pl else 'Signature and company stamp'}: ________________________________________________", body),
    ])
    class LocalEUDeclarationCanvas(EUDeclarationCanvas):
        HEADER_LABEL = text["title"]
        FOOTER_LABEL = "Production Management System - made by Adrian" if not pl else NumberedCanvasPortrait.FOOTER_LABEL
        PAGE_LABEL = "Page" if not pl else NumberedCanvasPortrait.PAGE_LABEL
    doc.build(story, canvasmaker=LocalEUDeclarationCanvas)
    pdf_bytes = buffer.getvalue()
    if store_document:
        store_order_pdf("Deklaracja zgodności PPWR", pdf_bytes, f"deklaracja_zgodnosci_{language}.pdf", {"language": language})
    return pdf_bytes


def generate_production_date_declaration_pdf(issuer, customer, products, cutoff_date, language="en", store_document=False):
    """Tworzy deklarację dat produkcji w wybranym języku."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=45, rightMargin=45, topMargin=52, bottomMargin=48
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle("ProdDateTitle", parent=styles["Heading1"], fontName=FONT_BOLD, fontSize=16,
                           leading=20, textColor=colors.HexColor("#123B66"), spaceAfter=9)
    body = ParagraphStyle("ProdDateBody", parent=styles["Normal"], fontName=FONT_REGULAR, fontSize=9,
                          leading=13, textColor=colors.HexColor("#0F172A"), spaceAfter=8)
    section = ParagraphStyle("ProdDateSection", parent=styles["Heading2"], fontName=FONT_BOLD, fontSize=10,
                             leading=13, textColor=colors.HexColor("#123B66"), spaceBefore=9, spaceAfter=5)
    header = ParagraphStyle("ProdDateHeader", parent=body, fontName=FONT_BOLD, fontSize=8,
                            leading=9, textColor=colors.white, alignment=1)

    def p(value, style=body):
        return Paragraph(escape(str(value if value else "-")), style)

    pl = language == "pl"
    text = {
        "title": "DEKLARACJA DATY PRODUKCJI OPAKOWAŃ" if pl else "DECLARATION OF PACKAGING PRODUCTION DATE",
        "issuer": "1. Wystawca" if pl else "1. Issuer",
        "customer": "2. Klient / odbiorca" if pl else "2. Customer / Consignee",
        "list": "3. Wykaz objętych produktów i komponentów" if pl else "3. List of covered products and components",
        "no": "Lp." if pl else "No.",
        "product": "Produkt / komponent" if pl else "Product / component",
        "batch": "Partia / dowód" if pl else "Batch / evidence",
        "date": "Data produkcji" if pl else "Production date",
        "source": "Źródło" if pl else "Source",
    }
    declaration_text = (
        f"Niniejszym oświadczam z pełną odpowiedzialnością, iż niżej wymienione partie opakowań, zawierające połączenie papieru/kartonu z laminatem z tworzyw sztucznych, zostały w pełni wyprodukowane przed dniem {cutoff_date.strftime('%d.%m.%Y')} r. Wyroby te zostały wytworzone zgodnie z przepisami prawa i normami technicznymi obowiązującymi w dacie ich produkcji. Niniejsze oświadczenie potwierdza status prawny przedmiotowych partii towaru w zakresie przepisów dotyczących stanów magazynowych oraz wyrobów wyprodukowanych przed wejściem w życie restrykcji materiałowych."
        if pl else
        f"I hereby declare under my sole responsibility that the packaging batches listed below, containing a combination of paper/cardboard and plastic laminate, were fully manufactured before {cutoff_date.strftime('%B %d, %Y')}. The products were manufactured in accordance with the laws and technical standards applicable on their production date. This declaration confirms the legal status of the relevant goods batches with respect to rules concerning inventory and products manufactured before material restrictions entered into force."
    )

    story = [
        Paragraph(text["title"], title),
        Paragraph(f"{escape(issuer['place'])}, {issuer['issue_date'].strftime('%B %d, %Y')}", body),
        Paragraph(text["issuer"], section),
        Paragraph(
            f"<b>{escape(issuer['company'])}</b><br/>{escape(issuer['address'])}<br/>VAT ID / NIP: {escape(issuer['nip'])}",
            body,
        ),
        Paragraph(text["customer"], section),
        Paragraph(
            f"<b>{escape(customer['company'])}</b><br/>{escape(customer['address'])}<br/>VAT ID / NIP: {escape(customer['nip'])}",
            body,
        ),
        Paragraph(declaration_text, body),
        Paragraph(text["list"], section),
    ]
    rows = [[p(text["no"], header), p(text["product"], header), p("SKU / EAN", header), p(text["batch"], header), p(text["date"], header), p(text["source"], header)]]
    for index, (_, product) in enumerate(products.iterrows(), start=1):
        production_date = pd.to_datetime(product.get("Data produkcji"), errors="coerce")
        date_label = production_date.strftime("%d.%m.%Y") if not pd.isna(production_date) else "-"
        rows.append([
            p(index), p(product.get("Produkt / komponent", "")), p(product.get("SKU / EAN", "")),
            p(product.get("Partia / dowód", "")), p(date_label), p(product.get("Źródło", "")),
        ])
    product_table = Table(rows, colWidths=[32, 180, 105, 105, 80, 58], repeatRows=1)
    product_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#123B66")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.extend([
        product_table,
        Spacer(1, 12),
        Paragraph("Dokumentacja techniczna potwierdzająca powyższe dane jest przechowywana w archiwum wystawcy." if pl else "The technical documentation confirming the above data is retained in the issuer's archives.", body),
        Paragraph(f"{'Osoba upoważniona' if pl else 'Authorised person'}: {escape(issuer['contact'])}<br/>{'Podpis i pieczęć firmowa' if pl else 'Signature and company stamp'}: ________________________________________________", body),
    ])
    class LocalProductionDateCanvas(ProductionDateCanvas):
        HEADER_LABEL = text["title"]
        FOOTER_LABEL = "Production Management System - made by Adrian" if not pl else NumberedCanvasPortrait.FOOTER_LABEL
        PAGE_LABEL = "Page" if not pl else NumberedCanvasPortrait.PAGE_LABEL
    doc.build(story, canvasmaker=LocalProductionDateCanvas)
    pdf_bytes = buffer.getvalue()
    if store_document:
        store_order_pdf("Deklaracja daty produkcji", pdf_bytes, f"deklaracja_daty_produkcji_{language}.pdf", {"language": language})
    return pdf_bytes


# --- MODUŁ 10: MASS SPECIFICATION PPWR ---

