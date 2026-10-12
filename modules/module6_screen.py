"""Widok modułu 6 wydzielony z app.py."""

def render_module_six(st, deps):
    for _bridge_name, _bridge_value in deps.items():
        if not _bridge_name.startswith("__"):
            globals()[_bridge_name] = _bridge_value
    del _bridge_name, _bridge_value
    st.subheader("📋 Packing List")
    role = st.session_state.get("user_role", "Użytkownik")
    can_manage = role in ["Administrator", "Manager"]
    can_warehouse = role in ["Administrator", "Manager", "Magazynier"]
    if "packing_document" not in st.session_state:
        st.session_state["packing_document"] = {"order_id": get_current_order_id(), "number": f"PL/{datetime.now().strftime('%Y')}/{datetime.now().strftime('%H%M%S')}", "created_at": datetime.now().strftime("%Y-%m-%d"), "sent_at":"", "planned_delivery":"", "status":"roboczy", "delivery_type":"kompletna", "language":"PL", "sender":"", "recipient":"", "delivery_place":"", "carrier":"", "items":[], "pallets":[]}
    document = st.session_state["packing_document"]
    active_packing_order_id = get_current_order_id()
    # Dokument przywrócony ze starszej sesji zawsze należy do aktualnie otwartego zlecenia.
    document["order_id"] = active_packing_order_id
    archive = _load_packing_archive()
    order_archive = [item for item in archive if item.get("order_id") == active_packing_order_id]
    st.caption(f"Rola: {role}. Magazynier potwierdza kompletację; Manager zatwierdza i wysyła; Administrator zarządza archiwum.")
    with st.expander("Nagłówek dokumentu", expanded=True):
        a,b,c = st.columns(3)
        with a: document["created_at"] = str(st.date_input("Data utworzenia", value=datetime.strptime(document["created_at"], "%Y-%m-%d").date(), disabled=not can_manage)); document["sent_at"] = str(st.date_input("Data wysyłki", value=datetime.now().date(), disabled=not can_manage))
        with b: document["planned_delivery"] = str(st.date_input("Planowana data dostawy", value=datetime.now().date(), disabled=not can_manage)); document["status"] = st.selectbox("Status", ["roboczy","zatwierdzony","wysłany","anulowany"], index=["roboczy","zatwierdzony","wysłany","anulowany"].index(document["status"]), disabled=not can_manage)
        with c: document["delivery_type"] = st.selectbox("Dostawa", ["kompletna","częściowa"], index=0 if document["delivery_type"]=="kompletna" else 1, disabled=not can_manage); document["language"] = st.selectbox("Język dokumentu", ["PL","EN","PL/EN"], index=["PL","EN","PL/EN"].index(document["language"]), disabled=not can_manage)
        document["sender"] = st.text_input("Nadawca", value=document["sender"], disabled=not can_manage); document["recipient"] = st.text_input("Odbiorca", value=document["recipient"], disabled=not can_manage); document["delivery_place"] = st.text_input("Miejsce dostawy", value=document["delivery_place"], disabled=not can_manage); document["carrier"] = st.text_input("Przewoźnik", value=document["carrier"], disabled=not can_manage)
    db_pl = wczytaj_produkty_z_db()
    with st.expander("Dodaj produkt i dane z modułów", expanded=True):
        source = st.radio("Źródło pozycji", ["Produkt z sekcji 1", "Paletyzacja 2/4", "e-Order / Karta Pracy", "TDS / PPWR"], horizontal=True)
        source_bct_blocked = False
        if source == "Produkt z sekcji 1" and db_pl:
            product = st.selectbox("Produkt", list(db_pl), key="pl_product"); data = db_pl[product]
            ean_levels = product_ean_levels(data)
            pl_level = st.selectbox("Poziom opakowania pozycji", ["Produkt", "Display", "Master Case"], index=2, key="pl_packaging_level")
            selected_ean = {"Produkt": ean_levels.get("produkt", ""), "Display": ean_levels.get("display", ""), "Master Case": ean_levels.get("master_case", "")}.get(pl_level, "")
            new_item = {"Produkt":product,"SKU":data.get("SKU",""),"EAN produktu":ean_levels.get("produkt", ""),"EAN displaya":ean_levels.get("display", ""),"EAN Master Case":ean_levels.get("master_case", ""),"Poziom opakowania":pl_level,"EAN/GTIN":selected_ean,"LOT":"","Sztuki":0,"Pudełka":0,"Displaye":0,"Kartony":1,"Paleta":"","Jednostka":"karton","Masa kg":data.get("Waga",0)}
        elif source == "Paletyzacja 2/4":
            data = st.session_state.get("sug_layout_result") or st.session_state.get("pal_calc_result") or {}
            if data.get("BCT powody"):
                st.info("Informacja BCT: " + " ".join(data.get("BCT powody", [])))
            product=data.get("Produkt","Brak wyniku paletyzacji"); new_item={"Produkt":product,"SKU":data.get("SKU", ""),"EAN produktu":data.get("EAN produktu", data.get("EAN", "")),"EAN displaya":data.get("EAN displaya", ""),"EAN Master Case":data.get("EAN Master Case", ""),"Poziom opakowania":"Master Case","EAN/GTIN":data.get("EAN Master Case", data.get("EAN", "")),"LOT":"","Sztuki":0,"Pudełka":0,"Displaye":0,"Kartony":data.get("Kartonów na pełnej palecie",data.get("Pojemność palety",0)),"Paleta":data.get("Paleta",""),"Jednostka":"paleta","Masa kg":data.get("Masa brutto/paleta kg",0)}
        elif source == "e-Order / Karta Pracy":
            source_items = st.session_state.get("e_order_items", []) or st.session_state.get("work_sheet_items", [])
            if source_items:
                labels = [f"{index + 1}. {item.get('product_name', 'Pozycja')} | {item.get('packaging_level', 'Produkt')}" for index, item in enumerate(source_items)]
                selected_item = source_items[labels.index(st.selectbox("Pozycja z E-Order / Karty Pracy", labels, key="pl_order_item"))]
                new_item = {"Produkt":selected_item.get("product_name", ""),"SKU":selected_item.get("sku", ""),"EAN produktu":selected_item.get("ean_product", ""),"EAN displaya":selected_item.get("ean_display", ""),"EAN Master Case":selected_item.get("ean_mastercase", ""),"Poziom opakowania":selected_item.get("packaging_level", "Master Case"),"EAN/GTIN":selected_item.get("ean_selected", ""),"LOT":selected_item.get("lot_number", ""),"Sztuki":selected_item.get("qty_shipping", selected_item.get("qty_net", 0)),"Pudełka":0,"Displaye":0,"Kartony":selected_item.get("packaging_calculation", {}).get("mastercase", 1),"Paleta":selected_item.get("packaging_calculation", {}).get("paleta", ""),"Jednostka":"karton","Masa kg":selected_item.get("packaging_calculation", {}).get("masa_brutto_palety", 0)}
            else:
                st.info("Brak pozycji E-Order i Karty Pracy dla aktywnego zlecenia.")
                new_item = {"Produkt":"","SKU":"","EAN produktu":"","EAN displaya":"","EAN Master Case":"","Poziom opakowania":"Master Case","EAN/GTIN":"","LOT":"","Sztuki":0,"Pudełka":0,"Displaye":0,"Kartony":1,"Paleta":"","Jednostka":"karton","Masa kg":0}
        elif source == "TDS / PPWR":
            source_items = [item for item in st.session_state.get("tds_items", []) if item.get("order_id") == active_packing_order_id]
            if source_items:
                labels = [f"{index + 1}. {item.get('name', 'Pozycja')} | {item.get('packaging_level', 'Produkt')}" for index, item in enumerate(source_items)]
                selected_item = source_items[labels.index(st.selectbox("Pozycja z TDS", labels, key="pl_tds_item"))]
                calc = selected_item.get("packaging_calculation", {})
                new_item = {"Produkt":selected_item.get("name", ""),"SKU":selected_item.get("sku", ""),"EAN produktu":selected_item.get("ean_product", ""),"EAN displaya":selected_item.get("ean_display", ""),"EAN Master Case":selected_item.get("ean_mastercase", ""),"Poziom opakowania":selected_item.get("packaging_level", "Master Case"),"EAN/GTIN": {"Produkt":selected_item.get("ean_product", ""), "Display":selected_item.get("ean_display", ""), "Master Case":selected_item.get("ean_mastercase", "")}.get(selected_item.get("packaging_level"), ""),"LOT":"","Sztuki":calc.get("produktow", 0),"Pudełka":0,"Displaye":calc.get("displayow", 0),"Kartony":calc.get("mastercase", 1),"Paleta":calc.get("paleta", ""),"Jednostka":"karton","Masa kg":calc.get("masa_brutto_palety", 0)}
            else:
                st.info("Brak zapisanych pozycji TDS dla aktywnego zlecenia.")
                new_item = {"Produkt":"","SKU":"","EAN produktu":"","EAN displaya":"","EAN Master Case":"","Poziom opakowania":"Master Case","EAN/GTIN":"","LOT":"","Sztuki":0,"Pudełka":0,"Displaye":0,"Kartony":1,"Paleta":"","Jednostka":"karton","Masa kg":0}
        else:
            product = st.text_input("Produkt", key="pl_external_product"); new_item={"Produkt":product,"SKU":"","EAN produktu":"","EAN displaya":"","EAN Master Case":"","Poziom opakowania":"Master Case","EAN/GTIN":"","LOT":"","Sztuki":0,"Pudełka":0,"Displaye":0,"Kartony":1,"Paleta":"","Jednostka":"karton","Masa kg":0}
        new_item["LOT"] = st.text_input("Numer partii / LOT", key="pl_lot"); qty = st.number_input("Ilość kartonów", min_value=1, value=max(1,int(new_item.get("Kartony",1))), disabled=not can_manage); new_item["Kartony"] = qty
        if st.button("➕ Dodaj pozycję", disabled=not can_manage): document["items"].append(new_item); st.rerun()
    frame = pd.DataFrame(document["items"], columns=["Produkt","SKU","EAN produktu","EAN displaya","EAN Master Case","Poziom opakowania","EAN/GTIN","LOT","Sztuki","Pudełka","Displaye","Kartony","Paleta","Jednostka","Masa kg"])
    edited = st.data_editor(frame, num_rows="dynamic", width="stretch", disabled=not can_manage, key="pl_editor")
    document["items"] = edited.to_dict("records")
    invalid=[]
    seen=set()
    for i,item in enumerate(document["items"],1):
        if not str(item.get("Produkt","")).strip() or float(item.get("Kartony",0) or 0)<=0: invalid.append(f"Pozycja {i}: brak produktu lub ilość niepoprawna.")
        if not str(item.get("LOT","")).strip(): invalid.append(f"Pozycja {i}: brak numeru LOT.")
        level = item.get("Poziom opakowania", "")
        expected_ean = {"Produkt": item.get("EAN produktu", ""), "Display": item.get("EAN displaya", ""), "Master Case": item.get("EAN Master Case", "")}.get(level, "")
        if level not in {"Produkt", "Display", "Master Case"}:
            invalid.append(f"Pozycja {i}: wybierz poziom opakowania Produkt, Display albo Master Case.")
        elif expected_ean and str(item.get("EAN/GTIN", "")) != str(expected_ean):
            invalid.append(f"Pozycja {i}: EAN/GTIN nie odpowiada wybranemu poziomowi „{level}”.")
        identity=(str(item.get("SKU","")),str(item.get("EAN/GTIN","")),str(item.get("LOT","")))
        if identity in seen: invalid.append(f"Pozycja {i}: możliwy duplikat SKU/EAN/LOT.")
        seen.add(identity)
    if not document["recipient"].strip(): invalid.append("Brak odbiorcy dokumentu.")
    for message in invalid: st.warning(message)
    if document["items"]:
        st.markdown("### Palety i kompletacja")
        if st.button("🔄 Automatycznie rozbij pozycje na palety", disabled=not can_manage):
            document["pallets"] = []
        if not document.get("pallets"):
            pallet_rows=[]
            calc_capacity = int((st.session_state.get("sug_layout_result") or st.session_state.get("pal_calc_result") or {}).get("Kartonów na pełnej palecie", (st.session_state.get("pal_calc_result") or {}).get("Pojemność palety", 0)) or 0)
            for item in document["items"]:
                quantity=max(1,int(item.get("Kartony",1) or 1)); capacity=max(1,calc_capacity or quantity); count=int(np.ceil(quantity/capacity))
                for pallet_no in range(1,count+1):
                    cartons=min(capacity, quantity-(pallet_no-1)*capacity); number=f"{pallet_no}/{count}"
                    pallet_rows.append({"Paleta":number, "Produkt":item["Produkt"], "Kartony":cartons, "Status":"oczekuje", "QR":json.dumps({"pl":document["number"],"produkt":item["Produkt"],"paleta":number},ensure_ascii=False)})
            document["pallets"] = pallet_rows
        document["pallets"] = st.data_editor(pd.DataFrame(document["pallets"]), num_rows="dynamic", width="stretch", disabled=not can_warehouse, key="pl_pallet_editor").to_dict("records")
        checks = st.multiselect("Potwierdź skompletowane palety", [f"{p['Paleta']} - {p['Produkt']}" for p in document["pallets"]], disabled=not can_warehouse)
        if checks: st.success(f"Potwierdzono: {len(checks)} palet.")
        with st.expander("📷 Skanowanie QR przy kompletacji i wydaniu", expanded=False):
            qr_photo = st.camera_input("Zrób zdjęcie kodu QR palety", key="pl_qr_camera")
            qr_upload = st.file_uploader("lub wgraj zdjęcie QR", type=["png","jpg","jpeg"], key="pl_qr_upload")
            qr_source = qr_photo if qr_photo is not None else qr_upload
            if qr_source is not None:
                qr_text, qr_error = odczytaj_kod_qr(qr_source)
                if qr_error: st.warning(qr_error)
                else:
                    try:
                        qr_data=json.loads(qr_text)
                        if qr_data.get("pl")==document["number"]:
                            st.success(f"Potwierdzono QR: paleta {qr_data.get('paleta')} - {qr_data.get('produkt')}.")
                        else: st.error("Zeskanowany kod QR należy do innego Packing List.")
                    except json.JSONDecodeError: st.warning("Kod QR nie zawiera danych Packing List.")
    summary={"pallets":len(document.get("pallets",[])),"cartons":sum(float(x.get("Kartony",0)or 0) for x in document["items"]),"pieces":sum(float(x.get("Sztuki",0)or 0) for x in document["items"]),"weight":round(sum(float(x.get("Masa kg",0)or 0) for x in document["items"]),2),"m3":0,"ldm":st.session_state.get("transport_prefill",{}).get("LDM",0)}; document["summary"]=summary
    st.info(f"Podsumowanie: {summary['pallets']} palet | {summary['cartons']} kartonów | {summary['pieces']} szt. | {summary['weight']} kg | {summary['m3']} m³ | {summary['ldm']} LDM")
    packing_pdf_name = f"packing_list_{str(document['number']).replace('/', '_')}.pdf"
    packing_pdf_state_key = f"packing_pdf_{active_packing_order_id}_{document['number']}"
    actions=st.columns(5)
    with actions[0]:
        if st.button("💾 Zapisz do archiwum", disabled=not can_manage or bool(invalid)):
            archived_document=json.loads(json.dumps(document, ensure_ascii=False)); archive=[x for x in archive if not (x.get("order_id") == active_packing_order_id and x.get("number") == document["number"])]+[archived_document]; _save_packing_archive(archive); update_order_snapshot("packing_list", document, active_packing_order_id); register_document("Packing List", {"number":document["number"],"recipient":document["recipient"]}, order_id=active_packing_order_id); save_order_context(active_packing_order_id); st.success("Dokument zapisano trwale w archiwum tego zlecenia.")
    with actions[1]:
        if st.button("📄 Przygotuj PDF", key="prepare_packing_pdf", disabled=bool(invalid)):
            st.session_state[packing_pdf_state_key] = generuj_pdf_packing_list_prof(document, store_document=True)
            st.success("PDF zapisano i dodano do Centrum zlecenia.")
        if st.session_state.get(packing_pdf_state_key):
            st.download_button("⬇️ Pobierz PDF", st.session_state[packing_pdf_state_key], file_name=f"{document['number'].replace('/','_')}.pdf", mime="application/pdf", key="download_packing_pdf")
    with actions[2]: st.download_button("🏷️ Etykiety palet PDF", generuj_pdf_etykiety_packing(document), file_name=f"etykiety_{document['number'].replace('/','_')}.pdf", mime="application/pdf", disabled=not bool(document.get("pallets")))
    with actions[3]:
        if st.button("📧 Przekaż do E-mail", disabled=not can_manage or bool(invalid)):
            pdf_bytes = st.session_state.get(packing_pdf_state_key) or generuj_pdf_packing_list_prof(document, store_document=True)
            st.session_state[packing_pdf_state_key] = pdf_bytes
            stored_path = get_order_document_file_path(active_packing_order_id, "Packing List", packing_pdf_name)
            st.session_state["email_auto_attachment"] = {
                "name": packing_pdf_name, "file_path": stored_path, "order_id": active_packing_order_id,
                "source": "Packing List",
            }
            save_order_context(active_packing_order_id)
            st.success("PDF będzie dostępny w module E-mail także po restarcie aplikacji.")
    with actions[4]:
        if st.button("🚚 Przekaż do transportu", disabled=not can_manage):
            palletization = st.session_state.get("sug_layout_result") or st.session_state.get("pal_calc_result") or {}
            saved_transport = document.get("transport_data", {}) if isinstance(document.get("transport_data", {}), dict) else {}
            transport_prefill = {
                "order_id": active_packing_order_id,
                "Produkt": document["items"][0].get("Produkt", "") if document["items"] else saved_transport.get("Produkt", ""),
                "Paleta": saved_transport.get("Paleta", palletization.get("Paleta", "")),
                "Liczba palet": saved_transport.get("Liczba palet") or summary["pallets"] or palletization.get("Liczba palet", 0),
                "Masa brutto/paleta kg": saved_transport.get("Masa brutto/paleta kg") or palletization.get("Masa brutto/paleta kg", 0),
                "Masa brutto całkowita kg": saved_transport.get("Masa brutto całkowita kg") or palletization.get("Masa brutto całkowita kg") or summary["weight"],
                "Wymiary palety mm": saved_transport.get("Wymiary palety mm") or palletization.get("Wymiary palety mm", []),
                "Wysokość palety mm": saved_transport.get("Wysokość palety mm") or palletization.get("Wysokość palety mm", 0),
                "LDM": saved_transport.get("LDM") or palletization.get("LDM") or summary["ldm"],
            }
            st.session_state["transport_prefill"] = transport_prefill
            update_order_snapshot("transport", transport_prefill, active_packing_order_id)
            save_order_context(active_packing_order_id)
            st.success("Przekazano do transportu liczbę palet, masę, wymiary, LDM i typ palety.")
    with st.expander("📚 Archiwum Packing List", expanded=False):
        if order_archive:
            st.caption(f"Wyświetlane są tylko dokumenty zlecenia {active_packing_order_id}.")
            st.dataframe(pd.DataFrame([{k:x.get(k,"") for k in ["number","created_at","recipient","status","delivery_type"]} for x in order_archive]),width="stretch")
            chosen=st.selectbox("Dokument archiwalny",[x["number"] for x in order_archive])
            if st.button("↩️ Przywołaj jako kopię",disabled=not can_manage): st.session_state["packing_document"]={**next(x for x in order_archive if x["number"]==chosen),"order_id":active_packing_order_id,"number":f"PL/{datetime.now().strftime('%Y')}/{datetime.now().strftime('%H%M%S')}","status":"roboczy"};st.rerun()
        else: st.info("Archiwum jest puste.")

# --- TAB 7: BOX RIGHTSIZING ---

