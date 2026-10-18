"""Widok modułu 9: TDS, E-Order i Karta Pracy."""

def render_tab9_screen(st, deps):
    for _bridge_name, _bridge_value in deps.items():
        if not _bridge_name.startswith("__"):
            globals()[_bridge_name] = _bridge_value
    del _bridge_name, _bridge_value
    render_production_documents_intro(
        bct_for_order=st.session_state.get("bct_for_order"),
        bct_for_tds=st.session_state.get("bct_for_tds") or st.session_state.get("bct_last_result"),
    )

    db = load_database()
    # Jedna kartoteka na cały przebieg modułu: jest używana zarówno przez
    # formularz zamówienia, jak i edycję pozycji E-Order.
    catalog_products = wczytaj_produkty_z_db()
    active_order_id = get_current_order_id()
    registry_header = load_document_registry().get(active_order_id, {}).get("order_header", {})
    order_header = prepare_production_documents_state(
        session_state=st.session_state, active_order_id=active_order_id, registry_header=registry_header,
        default_order_header=tab9_default_order_header, priorities=TAB9_ORDER_PRIORITIES,
        document_statuses=TAB9_DOCUMENT_STATUSES, languages=TAB9_DOCUMENT_LANGUAGES,
    )

    # Odtworzenie formularza musi nastąpić przed utworzeniem jego widgetów.
    restore_production_document_state(st.session_state)
    order_image_bytes = st.session_state.get("order_technical_image_bytes")
    order_image_name = st.session_state.get("order_technical_image_name", "")
    existing_project_attachment = st.session_state.get("tab9_project_attachment", {})

    form_tab, technical_card_tab, dict_tab, archive_tab, eorder_tab, worksheet_tab = st.tabs([
        "📝 Formularz Zamówienia", 
        "📄 Karta techniczna produktu",
        "⚙️ Zarządzanie Słownikami (Baza)", 
        "📁 Archiwum Zleceń",
        "📦 E-Order",
        "📋 Karta Pracy"
    ])

    with form_tab:
        render_tds_form_intro(st.session_state)

        order_header = render_order_header_form(
            active_order_id=active_order_id, order_header=order_header, priorities=TAB9_ORDER_PRIORITIES,
            document_statuses=TAB9_DOCUMENT_STATUSES, languages=TAB9_DOCUMENT_LANGUAGES,
            save_order_header=save_tab9_order_header,
        )

        catalog_snapshot, packaging_level = render_catalog_selector(
            session_state=st.session_state, catalog_products=catalog_products,
            order_clients=db.get("orders_clients", []), build_snapshot=build_tab9_catalog_snapshot,
            packaging_calculation=tab9_packaging_calculation, selected_ean=tab9_selected_ean,
        )

        with st.form("specyfikacja_offset_form"):
            
            st.markdown("### Informacje Ogólne")
            inc_internal_no, internal_no = render_field("Dotyczy zamówienia / Numer wewnętrzny *", "text", default_value="KSS Rolling Papers", key_prefix="internal_no")
            inc_file_ref, file_ref = render_field("Dotyczy pliku", "text", default_value="Set_of_xxx.pdf", key_prefix="file_ref")
            st.markdown("---")

            st.markdown("### SEKCJA I: PARAMETRY PODSTAWOWE & MATERIAŁY")

            render_catalog_snapshot_preview(catalog_snapshot)
            
            material_fields = render_tds_materials_section(database=db, render_field=render_field, render_master_checkbox=render_master_checkbox)
            inc_product_type, product_type = material_fields["product_type"]
            inc_product_name, product_name = material_fields["product_name"]
            inc_other_criteria, other_criteria = material_fields["other_criteria"]
            inc_dimensions, dimensions = material_fields["dimensions"]
            inc_filter_color, filter_color = material_fields["filter_color"]
            inc_custom_filter_color, custom_filter_color = material_fields["custom_filter_color"]
            inc_box_paper_color, box_paper_color = material_fields["box_paper_color"]
            inc_print_type, print_type = material_fields["print_type"]
            inc_order_channel, order_channel = material_fields["order_channel"]

            quantity_fields = render_tds_quantities_section(render_field=render_field, render_master_checkbox=render_master_checkbox)
            inc_lot_number, lot_number = quantity_fields["lot_number"]
            inc_qty_net, qty_net = quantity_fields["qty_net"]
            inc_qty_buffer, qty_buffer = quantity_fields["qty_buffer"]
            inc_qty_production, qty_production = quantity_fields["qty_production"]
            inc_qty_shipping, qty_shipping = quantity_fields["qty_shipping"]
            inc_qty_display_pieces, qty_display_pieces = quantity_fields["qty_display_pieces"]
            inc_qty_carton, qty_carton = quantity_fields["qty_carton"]
            inc_qty_cartons_palette, qty_cartons_palette = quantity_fields["qty_cartons_palette"]
            inc_qty_displays_palette, qty_displays_palette = quantity_fields["qty_displays_palette"]
            inc_qty_box, qty_box = quantity_fields["qty_box"]
            buffer_box = quantity_fields["buff_box"]
            inc_qty_cover, qty_cover = quantity_fields["qty_cover"]
            buffer_cover = quantity_fields["buff_cover"]
            inc_qty_display, qty_display = quantity_fields["qty_display"]
            buffer_disp = quantity_fields["buff_disp"]

            (inc_artwork_number, artwork_number), (inc_artwork_version, artwork_version), (inc_artwork_link, artwork_link), uploaded_source_project = render_tds_artwork_section(
                render_field=render_field, render_master_checkbox=render_master_checkbox,
                existing_attachment=existing_project_attachment,
            )

            st.markdown("### Podglądy karty technicznej")
            st.caption("Opcjonalne pliki pomagające jednoznacznie rozpoznać produkt. Obrazy są widoczne w PDF; pozostałe pliki zostają opisane w karcie.")
            visual_product_col, visual_cover_col, visual_display_col = st.columns(3)
            with visual_product_col:
                uploaded_product_visual = st.file_uploader("Produkt", type=["jpg", "jpeg", "png", "gif", "pdf"], key="technical_visual_product")
            with visual_cover_col:
                uploaded_cover_visual = st.file_uploader("Cover", type=["jpg", "jpeg", "png", "gif", "pdf"], key="technical_visual_cover")
            with visual_display_col:
                uploaded_display_visual = st.file_uploader("Display", type=["jpg", "jpeg", "png", "gif", "pdf"], key="technical_visual_display")

            st.markdown("---")
            st.markdown("### SEKCJA II: SPECYFIKACJA")
            specification_fields = render_tds_specification_section(
                database=db, render_field=render_field, render_master_checkbox=render_master_checkbox,
            )
            (inc_ok_gram, ok_gram), (inc_ok_print, ok_print), (inc_ok_rozb, ok_rozb), (inc_ok_druk, ok_druk), (inc_ok_lakier, ok_lakier), (inc_ok_awers, ok_awers), (inc_ok_rewers, ok_rewers), (inc_ok_wyk, ok_wyk) = (specification_fields[key] for key in ("ok_gram", "ok_print", "ok_rozb", "ok_druk", "ok_lakier", "ok_awers", "ok_rewers", "ok_wyk"))

            (inc_br_gram, br_gram), (inc_br_zadruk, br_zadruk), (inc_br_rozb, br_rozb), (inc_br_druk, br_druk), (inc_br_lakier, br_lakier), (inc_br_front, br_front), (inc_br_tyl, br_tyl), (inc_br_wyk, br_wyk) = (specification_fields[key] for key in ("br_gram", "br_zadruk", "br_rozb", "br_druk", "br_lakier", "br_front", "br_tyl", "br_wyk"))
            (inc_bl_gram, bl_gram), (inc_bl_zadruk, bl_zadruk), (inc_bl_rozb, bl_rozb), (inc_bl_druk, bl_druk), (inc_bl_lakier, bl_lakier), (inc_bl_front, bl_front), (inc_bl_tyl, bl_tyl), (inc_bl_wyk, bl_wyk) = (specification_fields[key] for key in ("bl_gram", "bl_zadruk", "bl_rozb", "bl_druk", "bl_lakier", "bl_front", "bl_tyl", "bl_wyk"))
            (inc_af_gram, af_gram), (inc_af_zadruk, af_zadruk), (inc_af_rozb, af_rozb), (inc_af_druk, af_druk), (inc_af_lakier, af_lakier), (inc_af_front, af_front), (inc_af_tyl, af_tyl), (inc_af_wyk, af_wyk) = (specification_fields[key] for key in ("af_gram", "af_zadruk", "af_rozb", "af_druk", "af_lakier", "af_front", "af_tyl", "af_wyk"))
            (inc_perf_count, perf_count), (inc_add_perf, add_perf), (inc_sheets_count, sheets_count), (inc_pack_display, pack_display), (inc_pack_carton, pack_carton), (inc_carton_print, carton_print) = (specification_fields[key] for key in ("perf_count", "add_perf", "sheets_count", "pack_display", "pack_carton", "carton_print"))
            (inc_dsp_type, dsp_type), (inc_dsp_gram, dsp_gram), (inc_dsp_zadruk, dsp_zadruk), (inc_dsp_rozb, dsp_rozb), (inc_dsp_lakier, dsp_lakier), (inc_dsp_wyk, dsp_wyk), (inc_dsp_lakierowanie, dsp_lakierowanie) = (specification_fields[key] for key in ("dsp_type", "dsp_gram", "dsp_zadruk", "dsp_rozb", "dsp_lakier", "dsp_wyk", "dsp_lakierowanie"))
            inc_other_notes, other_notes = specification_fields["other_notes"]

            col_b1, col_b2, col_b3, col_b4 = st.columns(4)
            with col_b1:
                submitted_save = st.form_submit_button("💾 Zapisz w sesji")
            with col_b2:
                submitted_archive = st.form_submit_button("📁 Dodaj do archiwum")
            with col_b3:
                submitted_eorder = st.form_submit_button("➕ Dodaj do e-order")
            with col_b4:
                submitted_worksheet = st.form_submit_button("📋 Dodaj do karty pracy")
            
            if submitted_save or submitted_archive or submitted_eorder or submitted_worksheet:
                errors = []
                validation_warnings = []
                if inc_internal_no and not internal_no.strip():
                    errors.append("Pole 'Numer wewnętrzny' jest wymagane, jeśli jest zaznaczone.")
                if inc_product_name and not product_name.strip():
                    errors.append("Pole 'Nazwa produktu' jest wymagane, jeśli jest zaznaczone.")
                if submitted_archive or submitted_eorder:
                    errors.extend(tab9_validate_base_data(
                        product_name if inc_product_name else "",
                        order_channel if inc_order_channel else "",
                        qty_net if inc_qty_net else 0,
                        order_header.get("delivery_date", ""),
                        require_client=True,
                        require_delivery=True,
                        location="Formularz zamówienia",
                        quantity_field="Ilość netto",
                    ))
                if submitted_worksheet:
                    errors.extend(tab9_validate_base_data(
                        product_name if inc_product_name else "", "",
                        qty_net if inc_qty_net else 0,
                        require_client=False,
                        require_delivery=False,
                        location="Formularz zamówienia → Karta Pracy",
                        quantity_field="Ilość netto",
                    ))
                validation_warnings.extend(tab9_validate_packaging_relations(
                    catalog_snapshot, qty_display_pieces, qty_carton, qty_cartons_palette, qty_displays_palette
                ))
                expected_level_ean = tab9_selected_ean(catalog_snapshot, packaging_level)
                if catalog_snapshot and not expected_level_ean:
                    validation_warnings.append(f"W kartotece brakuje EAN dla wybranego poziomu „{packaging_level}”.")
                if submitted_archive or submitted_eorder:
                    tab9_apply_approval_validation(
                        errors, validation_warnings, order_header.get("document_status"),
                    )

                if errors:
                    for err in errors:
                        st.error(err)
                else:
                    for warning in validation_warnings:
                        st.warning(warning)
                    final_filter_color = filter_color
                    if inc_filter_color and filter_color == "Inny" and inc_custom_filter_color and custom_filter_color.strip():
                        final_filter_color = f"Inny: {custom_filter_color}"
                    qty_with_buffer = tab9_as_positive_int(qty_net) + tab9_as_positive_int(qty_buffer)
                    qty_for_production = tab9_as_positive_int(qty_production) or qty_with_buffer
                    qty_for_shipping = tab9_as_positive_int(qty_shipping) or tab9_as_positive_int(qty_net)
                    packaging_calculation = (
                        tab9_packaging_calculation(catalog_snapshot, "Master Case", qty_cartons_palette, qty_cartons_palette)
                        if catalog_snapshot else {}
                    )
                    project_info = {
                        "project_number": artwork_number if inc_artwork_number else "",
                        "project_version": artwork_version if inc_artwork_version else "",
                        "source_link": artwork_link if inc_artwork_link else "",
                        "attachment": tab9_project_file_payload(uploaded_source_project, existing_project_attachment),
                    }
                    technical_visual_attachments = [
                        {"label": label, "name": uploaded_file.name, "mime": uploaded_file.type or "", "b64": base64.b64encode(uploaded_file.getvalue()).decode("ascii")}
                        for label, uploaded_file in (("Produkt", uploaded_product_visual), ("Cover", uploaded_cover_visual), ("Display", uploaded_display_visual))
                        if uploaded_file is not None
                    ]
                    if uploaded_source_project is not None:
                        st.session_state["tab9_project_attachment"] = project_info["attachment"]
                    catalog_product_image = tab9_catalog_product_image(catalog_snapshot)
                    pdf_attachment_bytes = order_image_bytes
                    pdf_attachment_name = order_image_name
                    if not pdf_attachment_bytes and catalog_product_image.get("b64"):
                        pdf_attachment_bytes = base64.b64decode(catalog_product_image["b64"])
                        pdf_attachment_name = catalog_product_image.get("name", "zdjecie_produktu")

                    pdf_data_built = {}
                    info_sec = {}
                    info_sec["Data utworzenia karty"] = datetime.now().strftime("%d.%m.%Y")
                    if inc_internal_no: info_sec["Numer wewnętrzny"] = internal_no
                    if inc_file_ref: info_sec["Plik"] = file_ref
                    if info_sec: pdf_data_built["Informacje Ogólne"] = info_sec

                    if catalog_snapshot:
                        pdf_data_built.update(tab9_tds_catalog_sections(catalog_snapshot, packaging_level))

                    sec1 = {}
                    if inc_product_type: sec1["Produkt"] = product_type
                    if inc_product_name: sec1["Nazwa produktu"] = product_name
                    if inc_other_criteria: sec1["Inne kryteria"] = other_criteria
                    if inc_dimensions: sec1["Rozmiar/typ filtra"] = dimensions
                    if inc_filter_color: sec1["Kolor filtra"] = final_filter_color
                    if inc_box_paper_color: sec1["Kolor papieru w boxie"] = box_paper_color
                    if inc_print_type: sec1["Druk"] = print_type
                    if inc_order_channel: sec1["Zamówienie/klient"] = order_channel
                    if inc_lot_number: sec1["Numer partii / LOT"] = lot_number
                    if inc_qty_net: sec1["Ilość netto"] = qty_net
                    if inc_qty_buffer: sec1["Ilość z zapasem"] = qty_with_buffer
                    if inc_qty_production: sec1["Ilość do produkcji"] = qty_for_production
                    if inc_qty_shipping: sec1["Ilość do wysyłki"] = qty_for_shipping
                    if inc_qty_box: sec1["Ilość box"] = qty_box + buffer_box
                    if inc_qty_cover: sec1["Ilość cover"] = qty_cover + buffer_cover
                    if inc_qty_display: sec1["Ilość display"] = qty_display + buffer_disp
                    if inc_qty_carton: sec1["Ilość w kartonie zbiorczym"] = qty_carton
                    if sec1: pdf_data_built["Sekcja I: Parametry Podstawowe & Materiały"] = sec1
                    if packaging_calculation:
                        pdf_data_built["Przelicznik opakowań - 1 paleta"] = tab9_packaging_pdf_fields(packaging_calculation)
                    if any(project_info.values()) and (
                        project_info["project_number"] or project_info["project_version"] or project_info["source_link"] or project_info["attachment"]
                    ):
                        pdf_data_built["Specyfikacja projektu dla drukarni"] = tab9_project_pdf_fields(project_info)

                    # Archiwum musi przechowywać identyczny komplet sekcji jak PDF.
                    sec2 = {}
                    for label, included, value in [
                        ("Okładka - Gramatura", inc_ok_gram, ok_gram), ("Okładka - Zadruk", inc_ok_print, ok_print), ("Okładka - Rozbarwienie", inc_ok_rozb, ok_rozb), ("Okładka - Druk", inc_ok_druk, ok_druk), ("Okładka - Lakier", inc_ok_lakier, ok_lakier), ("Okładka - Foliowanie/Lakierowanie awers", inc_ok_awers, ok_awers), ("Okładka - Foliowanie/Lakierowanie rewers", inc_ok_rewers, ok_rewers), ("Okładka - Wykrojnik", inc_ok_wyk, ok_wyk),
                        ("Box rolls - Gramatura", inc_br_gram, br_gram), ("Box rolls - Zadruk", inc_br_zadruk, br_zadruk), ("Box rolls - Rozbarwienie", inc_br_rozb, br_rozb), ("Box rolls - Druk", inc_br_druk, br_druk), ("Box rolls - Lakier", inc_br_lakier, br_lakier), ("Box rolls - Foliowanie front", inc_br_front, br_front), ("Box rolls - Foliowanie tył", inc_br_tyl, br_tyl), ("Box rolls - Wykrojnik", inc_br_wyk, br_wyk),
                        ("Bletka - Gramatura", inc_bl_gram, bl_gram), ("Bletka - Zadruk", inc_bl_zadruk, bl_zadruk), ("Bletka - Rozbarwienie", inc_bl_rozb, bl_rozb), ("Bletka - Druk", inc_bl_druk, bl_druk), ("Bletka - Lakier", inc_bl_lakier, bl_lakier), ("Bletka - Foliowanie front", inc_bl_front, bl_front), ("Bletka - Foliowanie tył", inc_bl_tyl, bl_tyl), ("Bletka - Wykrojnik", inc_bl_wyk, bl_wyk),
                        ("Arkusz filtra - Gramatura", inc_af_gram, af_gram), ("Arkusz filtra - Zadruk", inc_af_zadruk, af_zadruk), ("Arkusz filtra - Rozbarwienie", inc_af_rozb, af_rozb), ("Arkusz filtra - Druk", inc_af_druk, af_druk), ("Arkusz filtra - Lakier", inc_af_lakier, af_lakier), ("Arkusz filtra - Foliowanie front", inc_af_front, af_front), ("Arkusz filtra - Foliowanie tył", inc_af_tyl, af_tyl), ("Arkusz filtra - Wykrojnik", inc_af_wyk, af_wyk),
                        ("Ilość perforacji", inc_perf_count, perf_count), ("Dodatkowa perforacja", inc_add_perf, add_perf), ("Ilość listków", inc_sheets_count, sheets_count), ("Ilość w Display", inc_pack_display, pack_display), ("Ilość w kartonie", inc_pack_carton, pack_carton), ("Nadruk na kartonie", inc_carton_print, carton_print),
                    ]:
                        if included:
                            sec2[label] = value
                    if sec2:
                        pdf_data_built["SEKCJA II: SPECYFIKACJA"] = sec2

                    sec3 = {}
                    for label, included, value in [
                        ("Display", inc_dsp_type, dsp_type), ("Gramatura (Display)", inc_dsp_gram, dsp_gram), ("Zadruk (Display)", inc_dsp_zadruk, dsp_zadruk), ("Rozbarwienie (Display)", inc_dsp_rozb, dsp_rozb), ("Lakier (Display)", inc_dsp_lakier, dsp_lakier), ("Wykrojnik (Display)", inc_dsp_wyk, dsp_wyk), ("Foliowanie/lakierowanie (Display)", inc_dsp_lakierowanie, dsp_lakierowanie),
                    ]:
                        if included:
                            sec3[label] = value
                    if sec3:
                        pdf_data_built["Sekcja III: Display"] = sec3

                    sec4 = {}
                    if inc_other_notes:
                        sec4["Uwagi do zamówienia"] = other_notes
                    if sec4:
                        pdf_data_built["SEKCJA IV: INNE ISTOTNE INFORMACJE"] = sec4

                    form_state = {
                        key: value for key, value in st.session_state.items()
                        if key.startswith(("chk_", "val_", "master_")) or key in {
                            "buff_box", "buff_cover", "buff_disp", "tab9_document_packaging_level"
                        }
                    }

                    order_data = {
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "order_id": active_order_id,
                        "order_header": order_header,
                        "lot_number": lot_number if inc_lot_number else "",
                        "qty_net": qty_net if inc_qty_net else 0,
                        "qty_buffer": qty_buffer if inc_qty_buffer else 0,
                        "qty_with_buffer": qty_with_buffer if inc_qty_buffer else qty_net,
                        "qty_production": qty_for_production if inc_qty_production else 0,
                        "qty_shipping": qty_for_shipping if inc_qty_shipping else 0,
                        "packaging_calculation": packaging_calculation,
                        "project_info": project_info,
                        "catalog_product_image": catalog_product_image,
                        "technical_visual_attachments": technical_visual_attachments,
                        "numer_wewnetrzny": internal_no if inc_internal_no else "Brak",
                        "plik": file_ref if inc_file_ref else "Brak",
                        "pdf_data": pdf_data_built,
                        "form_state": form_state,
                        "catalog_snapshot": catalog_snapshot,
                        "packaging_level": packaging_level,
                    }

                    # Jedno zlecenie może obejmować wiele produktów. Każda zapisana
                    # karta staje się pozycją wspólnego TDS, bez nadpisywania innych.
                    if submitted_save or submitted_archive:
                        tds_item = {
                            "name": product_name if inc_product_name else catalog_snapshot.get("Nazwa produktu", "Pozycja bez nazwy"),
                            "sku": catalog_snapshot.get("SKU", ""), "packaging_level": packaging_level,
                            "ean_product": tab9_selected_ean(catalog_snapshot, "Produkt"),
                            "ean_display": tab9_selected_ean(catalog_snapshot, "Display"),
                            "ean_mastercase": tab9_selected_ean(catalog_snapshot, "Master Case"),
                            "catalog_snapshot": catalog_snapshot, "packaging_calculation": packaging_calculation,
                            "pdf_data": pdf_data_built, "order_id": active_order_id,
                        }
                        existing_tds = st.session_state.setdefault("tds_items", [])
                        item_key = (tds_item["name"], tds_item["packaging_level"])
                        st.session_state["tds_items"] = [item for item in existing_tds if (item.get("name"), item.get("packaging_level")) != item_key] + [tds_item]
                        update_order_snapshot("tds", {"order_header": order_header, "items": st.session_state["tds_items"]}, active_order_id)
                        save_order_context(active_order_id)

                    if submitted_save:
                        st.session_state["saved_specification"] = order_data
                        st.success("Dane specyfikacji zostały pomyślnie zapisane w pamięci sesji!")

                    if submitted_archive:
                        st.session_state["saved_specification"] = order_data
                        if order_image_bytes:
                            order_data["technical_image_b64"] = base64.b64encode(order_image_bytes).decode("ascii")
                            order_data["technical_image_name"] = order_image_name
                        # Zachowujemy gotowy PDF, aby pobranie z archiwum było identyczne z wersją zapisaną.
                        archived_pdf = generate_pdf(
                            pdf_data_built, pdf_attachment_bytes, pdf_attachment_name,
                            order_id=order_data["order_id"],
                            include_bct=False,
                        )
                        archived_pdf_bytes = (
                            archived_pdf.getvalue()
                            if hasattr(archived_pdf, "getvalue")
                            else archived_pdf
                        )
                        order_data["pdf_binary_b64"] = base64.b64encode(archived_pdf_bytes).decode("ascii")
                        db["orders"].append(order_data)
                        save_database(db)
                        st.success("Karta produktu została pomyślnie dodana do archiwum!")

                    if submitted_eorder:
                        eorder_item = {
                            "product_name": product_name if inc_product_name else "-",
                            "product_type": product_type if inc_product_type else "-",
                            "other_criteria": other_criteria if inc_other_criteria else "-",
                            "filter_color": final_filter_color if inc_filter_color else "-",
                            "dimensions": dimensions if inc_dimensions else "-",
                            "box_paper_color": box_paper_color if inc_box_paper_color else "-",
                            "order_channel": order_channel if inc_order_channel else "-",
                            "qty_net": qty_net if inc_qty_net else 0,
                            "qty_buffer": qty_buffer if inc_qty_buffer else 0,
                            "qty_with_buffer": qty_with_buffer if inc_qty_buffer else qty_net,
                            "qty_production": qty_for_production if inc_qty_production else 0,
                            "qty_shipping": qty_for_shipping if inc_qty_shipping else 0,
                            "production_planned": qty_for_production if inc_qty_production else 0,
                            "production_made": 0,
                            "production_waste": 0,
                            "waste_reason": "",
                            "lot_number": lot_number if inc_lot_number else "",
                            "qty_display_pieces": qty_display_pieces if inc_qty_display_pieces else 0,
                            "qty_carton": qty_carton if inc_qty_carton else 0,
                            "qty_cartons_palette": qty_cartons_palette if inc_qty_cartons_palette else 0,
                            "qty_displays_palette": qty_displays_palette if inc_qty_displays_palette else 0,
                            "sku": catalog_snapshot.get("SKU", ""),
                            "ean_product": tab9_selected_ean(catalog_snapshot, "Produkt"),
                            "ean_display": tab9_selected_ean(catalog_snapshot, "Display"),
                            "ean_mastercase": tab9_selected_ean(catalog_snapshot, "Master Case"),
                            "ean_selected": tab9_selected_ean(catalog_snapshot, packaging_level),
                            "packaging_level": packaging_level,
                            "catalog_snapshot": catalog_snapshot,
                            "packaging_calculation": packaging_calculation,
                            "project_info": project_info,
                            "order_id": active_order_id,
                            "order_header": order_header,
                        }
                        st.session_state["e_order_items"].append(eorder_item)
                        st.success(f"Dodano pozycję '{product_name}' do listy E-Order!")

                    if submitted_worksheet:
                        worksheet_item = {
                            "order_channel": order_channel if inc_order_channel else "-",
                            "product_name": product_name if inc_product_name else "-",
                            "other_criteria": other_criteria if inc_other_criteria else "-",
                            "display_type": dsp_type if inc_dsp_type else "-",
                            "box_paper_color": box_paper_color if inc_box_paper_color else "-",
                            "filter_color": final_filter_color if inc_filter_color else "-",
                            "dimensions": dimensions if inc_dimensions else "-",
                            "qty_net": qty_net if inc_qty_net else 0,
                            "qty_buffer": qty_buffer if inc_qty_buffer else 0,
                            "qty_with_buffer": qty_with_buffer if inc_qty_buffer else qty_net,
                            "qty_production": qty_for_production if inc_qty_production else 0,
                            "qty_shipping": qty_for_shipping if inc_qty_shipping else 0,
                            "production_planned": qty_for_production if inc_qty_production else 0,
                            "production_made": 0,
                            "production_waste": 0,
                            "waste_reason": "",
                            "lot_number": lot_number if inc_lot_number else "",
                            "qty_box": (qty_box + buffer_box) if inc_qty_box else 0,
                            "qty_cover": (qty_cover + buffer_cover) if inc_qty_cover else 0,
                            "qty_display": (qty_display + buffer_disp) if inc_qty_display else 0,
                            "order_notes": other_notes if inc_other_notes else "-",
                            "invoice_status": "Brak",
                            "sku": catalog_snapshot.get("SKU", ""),
                            "ean_product": tab9_selected_ean(catalog_snapshot, "Produkt"),
                            "ean_display": tab9_selected_ean(catalog_snapshot, "Display"),
                            "ean_mastercase": tab9_selected_ean(catalog_snapshot, "Master Case"),
                            "ean_selected": tab9_selected_ean(catalog_snapshot, packaging_level),
                            "packaging_level": packaging_level,
                            "catalog_snapshot": catalog_snapshot,
                            "packaging_calculation": packaging_calculation,
                            "project_info": project_info,
                            "order_id": active_order_id,
                            "order_header": order_header,
                        }
                        st.session_state["work_sheet_items"].append(worksheet_item)
                        st.success(f"Dodano pozycję '{product_name}' do Karty Pracy!")

        st.markdown("---")
        st.markdown("#### Załącznik graficzny do Sekcji IV")
        uploaded_order_image = st.file_uploader(
            "Dodaj projekt lub inną istotną grafikę (JPG, PNG, GIF)",
            type=["jpg", "jpeg", "png", "gif"],
            key="order_technical_image",
        )
        if uploaded_order_image is not None:
            st.session_state["order_technical_image_bytes"] = uploaded_order_image.getvalue()
            st.session_state["order_technical_image_name"] = uploaded_order_image.name
            st.image(uploaded_order_image, width=350, caption="Podgląd załączonego pliku")

        st.markdown("### 🖨️ Eksport do pliku PDF (Pojedyncza Karta)")
        if st.button("📄 Generuj i pobierz profesjonalny PDF"):
            pdf_errors = []
            pdf_warnings = []
            if inc_internal_no and not internal_no.strip():
                pdf_errors.append("Uzupełnij 'Numer wewnętrzny'.")
            if inc_product_name and not product_name.strip():
                pdf_errors.append("Uzupełnij 'Nazwę produktu'.")
            pdf_errors.extend(tab9_validate_base_data(
                product_name if inc_product_name else "",
                order_channel if inc_order_channel else "",
                qty_net if inc_qty_net else 0,
                order_header.get("delivery_date", ""),
                require_client=False,
                require_delivery=False,
                location="Karta techniczna produktu",
                quantity_field="Ilość netto",
            ))
            pdf_warnings.extend(tab9_validate_packaging_relations(
                catalog_snapshot, qty_display_pieces, qty_carton, qty_cartons_palette, qty_displays_palette
            ))
            if catalog_snapshot and not tab9_selected_ean(catalog_snapshot, packaging_level):
                pdf_warnings.append(f"W kartotece brakuje EAN dla wybranego poziomu „{packaging_level}”.")
            tab9_apply_approval_validation(
                pdf_errors, pdf_warnings, order_header.get("document_status"),
            )

            if pdf_errors:
                for err in pdf_errors:
                    st.warning(err)
            else:
                for warning in pdf_warnings:
                    st.warning(warning)
                pdf_data = {}
                info_sec = {}
                info_sec["Data utworzenia karty"] = datetime.now().strftime("%d.%m.%Y")
                if inc_internal_no: info_sec["Numer wewnętrzny"] = internal_no
                if inc_file_ref: info_sec["Plik"] = file_ref
                if info_sec: pdf_data["Informacje Ogólne"] = info_sec
                qty_with_buffer = tab9_as_positive_int(qty_net) + tab9_as_positive_int(qty_buffer)
                qty_for_production = tab9_as_positive_int(qty_production) or qty_with_buffer
                qty_for_shipping = tab9_as_positive_int(qty_shipping) or tab9_as_positive_int(qty_net)
                packaging_calculation = (
                    tab9_packaging_calculation(catalog_snapshot, "Master Case", qty_cartons_palette, qty_cartons_palette)
                    if catalog_snapshot else {}
                )
                project_info = {
                    "project_number": artwork_number if inc_artwork_number else "",
                    "project_version": artwork_version if inc_artwork_version else "",
                    "source_link": artwork_link if inc_artwork_link else "",
                    "attachment": tab9_project_file_payload(uploaded_source_project, existing_project_attachment),
                }
                if uploaded_source_project is not None:
                    st.session_state["tab9_project_attachment"] = project_info["attachment"]
                catalog_product_image = tab9_catalog_product_image(catalog_snapshot)
                pdf_attachment_bytes = order_image_bytes
                pdf_attachment_name = order_image_name
                if not pdf_attachment_bytes and catalog_product_image.get("b64"):
                    pdf_attachment_bytes = base64.b64decode(catalog_product_image["b64"])
                    pdf_attachment_name = catalog_product_image.get("name", "zdjecie_produktu")

                if catalog_snapshot:
                    pdf_data.update(tab9_tds_catalog_sections(catalog_snapshot, packaging_level))

                sec1 = {}
                if inc_product_type: sec1["Produkt"] = product_type
                if inc_product_name: sec1["Nazwa produktu"] = product_name
                if inc_other_criteria: sec1["Inne kryteria"] = other_criteria
                if inc_dimensions: sec1["Rozmiar/typ filtra"] = dimensions
                if inc_filter_color: 
                    final_fc = filter_color
                    if filter_color == "Inny" and custom_filter_color.strip():
                        final_fc = f"Inny: {custom_filter_color}"
                    sec1["Kolor filtra"] = final_fc
                if inc_box_paper_color: sec1["Kolor papieru w boxie"] = box_paper_color
                if inc_print_type: sec1["Druk"] = print_type
                if inc_order_channel: sec1["Zamówienie/klient"] = order_channel
                if inc_lot_number: sec1["Numer partii / LOT"] = lot_number
                if inc_qty_net: sec1["Ilość netto"] = qty_net
                if inc_qty_buffer: sec1["Ilość z zapasem"] = qty_with_buffer
                if inc_qty_production: sec1["Ilość do produkcji"] = qty_for_production
                if inc_qty_shipping: sec1["Ilość do wysyłki"] = qty_for_shipping
                if inc_qty_box: sec1["Ilość box"] = qty_box + buffer_box
                if inc_qty_cover: sec1["Ilość cover"] = qty_cover + buffer_cover
                if inc_qty_display: sec1["Ilość display"] = qty_display + buffer_disp
                if inc_qty_carton: sec1["Ilość w kartonie zbiorczym"] = qty_carton
                if sec1: pdf_data["Sekcja I: Parametry Podstawowe & Materiały"] = sec1
                if packaging_calculation:
                    pdf_data["Przelicznik opakowań - 1 paleta"] = tab9_packaging_pdf_fields(packaging_calculation)
                if project_info["project_number"] or project_info["project_version"] or project_info["source_link"] or project_info["attachment"]:
                    pdf_data["Specyfikacja projektu dla drukarni"] = tab9_project_pdf_fields(project_info)

                sec2 = {}
                if inc_ok_gram: sec2["Okładka - Gramatura"] = ok_gram
                if inc_ok_print: sec2["Okładka - Zadruk"] = ok_print
                if inc_ok_rozb: sec2["Okładka - Rozbarwienie"] = ok_rozb
                if inc_ok_druk: sec2["Okładka - Druk"] = ok_druk
                if inc_ok_lakier: sec2["Okładka - Lakier"] = ok_lakier
                if inc_ok_awers: sec2["Okładka - Foliowanie/Lakierowanie awers"] = ok_awers
                if inc_ok_rewers: sec2["Okładka - Foliowanie/Lakierowanie rewers"] = ok_rewers
                if inc_ok_wyk: sec2["Okładka - Wykrojnik"] = ok_wyk
                if inc_br_gram: sec2["Box rolls - Gramatura"] = br_gram
                if inc_br_zadruk: sec2["Box rolls - Zadruk"] = br_zadruk
                if inc_br_rozb: sec2["Box rolls - Rozbarwienie"] = br_rozb
                if inc_br_druk: sec2["Box rolls - Druk"] = br_druk
                if inc_br_lakier: sec2["Box rolls - Lakier"] = br_lakier
                if inc_br_front: sec2["Box rolls - Foliowanie front"] = br_front
                if inc_br_tyl: sec2["Box rolls - Foliowanie tył"] = br_tyl
                if inc_br_wyk: sec2["Box rolls - Wykrojnik"] = br_wyk
                if inc_bl_gram: sec2["Bletka - Gramatura"] = bl_gram
                if inc_bl_zadruk: sec2["Bletka - Zadruk"] = bl_zadruk
                if inc_bl_rozb: sec2["Bletka - Rozbarwienie"] = bl_rozb
                if inc_bl_druk: sec2["Bletka - Druk"] = bl_druk
                if inc_bl_lakier: sec2["Bletka - Lakier"] = bl_lakier
                if inc_bl_front: sec2["Bletka - Foliowanie front"] = bl_front
                if inc_bl_tyl: sec2["Bletka - Foliowanie tył"] = bl_tyl
                if inc_bl_wyk: sec2["Bletka - Wykrojnik"] = bl_wyk
                if inc_af_gram: sec2["Arkusz filtra - Gramatura"] = af_gram
                if inc_af_zadruk: sec2["Arkusz filtra - Zadruk"] = af_zadruk
                if inc_af_rozb: sec2["Arkusz filtra - Rozbarwienie"] = af_rozb
                if inc_af_druk: sec2["Arkusz filtra - Druk"] = af_druk
                if inc_af_lakier: sec2["Arkusz filtra - Lakier"] = af_lakier
                if inc_af_front: sec2["Arkusz filtra - Foliowanie front"] = af_front
                if inc_af_tyl: sec2["Arkusz filtra - Foliowanie tył"] = af_tyl
                if inc_af_wyk: sec2["Arkusz filtra - Wykrojnik"] = af_wyk
                if inc_perf_count: sec2["Ilość perforacji"] = perf_count
                if inc_add_perf: sec2["Dodatkowa perforacja"] = add_perf
                if inc_sheets_count: sec2["Ilość listków"] = sheets_count
                if inc_pack_display: sec2["Ilość w Display"] = pack_display
                if inc_pack_carton: sec2["Ilość w kartonie"] = pack_carton
                if inc_carton_print: sec2["Nadruk na kartonie"] = carton_print
                if sec2: pdf_data["SEKCJA II: SPECYFIKACJA"] = sec2

                sec3 = {}
                if inc_dsp_type: sec3["Display"] = dsp_type
                if inc_dsp_gram: sec3["Gramatura (Display)"] = dsp_gram
                if inc_dsp_zadruk: sec3["Zadruk (Display)"] = dsp_zadruk
                if inc_dsp_rozb: sec3["Rozbarwienie (Display)"] = dsp_rozb
                if inc_dsp_lakier: sec3["Lakier (Display)"] = dsp_lakier
                if inc_dsp_wyk: sec3["Wykrojnik (Display)"] = dsp_wyk
                if inc_dsp_lakierowanie: sec3["Foliowanie/lakierowanie (Display)"] = dsp_lakierowanie
                if sec3: pdf_data["Sekcja III: Display"] = sec3

                sec4 = {}
                if inc_other_notes: sec4["Uwagi do zamówienia"] = other_notes
                if sec4: pdf_data["SEKCJA IV: INNE ISTOTNE INFORMACJE"] = sec4

                if pdf_data:
                    st.session_state["printer_copy_en_source_data"] = pdf_data
                    internal_pdf = generate_pdf(pdf_data, pdf_attachment_bytes, pdf_attachment_name)
                    printer_pdf = generate_pdf(
                        printer_copy_data(pdf_data), pdf_attachment_bytes, pdf_attachment_name,
                        document_title="ZAMÓWIENIE DLA DRUKARNI",
                    )
                    printer_pdf_en = None
                    manual_translations = st.session_state.get("printer_copy_en_translation_overrides", {})
                    try:
                        printer_pdf_en = generate_pdf(
                            printer_copy_data_en(
                                pdf_data,
                                st.secrets.get("DEEPL_API_KEY", ""),
                                manual_translations,
                            ),
                            pdf_attachment_bytes,
                            pdf_attachment_name,
                            document_title="ORDER FOR PRINTER",
                        )
                    except DeepLTranslationError as error:
                        st.warning(f"{error} Uzupełnij ręczne tłumaczenia poniżej, zapisz je i wygeneruj kopię EN ponownie.")
                        st.session_state["printer_copy_en_translation_rows"] = printer_copy_translation_rows(
                            pdf_data, manual_translations,
                        )
                    st.download_button(
                        label="📥 Pobierz PDF wewnętrzny (z nagłówkiem zlecenia)",
                        data=internal_pdf,
                        file_name=f"specyfikacja_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                        mime="application/pdf",
                        key="download_internal_order_pdf",
                    )
                    st.download_button(
                        label="🖨️ Pobierz kopię dla drukarni (bez nagłówka zlecenia)",
                        data=printer_pdf,
                        file_name=f"specyfikacja_dla_drukarni_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                        mime="application/pdf",
                        key="download_printer_order_pdf",
                    )
                    if printer_pdf_en is not None:
                        st.download_button(
                            label="🖨️ Download printer copy (English)",
                            data=printer_pdf_en,
                            file_name=f"specification_for_printer_en_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                            mime="application/pdf",
                            key="download_printer_order_pdf_en",
                        )

        if st.button("Ręczne tłumaczenia EN", icon=":material/translate:", key="open_printer_copy_en_manual_translations"):
            source_data = st.session_state.get("printer_copy_en_source_data")
            if source_data:
                st.session_state["printer_copy_en_translation_rows"] = printer_copy_translation_rows(
                    source_data,
                    st.session_state.get("printer_copy_en_translation_overrides", {}),
                )
            else:
                st.info("Najpierw kliknij „Generuj i pobierz profesjonalny PDF”, aby przygotować opisy z bieżącego formularza.")

        manual_translation_rows = st.session_state.get("printer_copy_en_translation_rows", [])
        if manual_translation_rows:
            with st.expander("Ręczne tłumaczenia do kopii EN", expanded=True):
                st.caption("Gdy limit DeepL jest niedostępny, wpisz profesjonalne wersje angielskie obok polskich opisów. Wpisane pola nie będą wysyłane do DeepL.")
                editable_translations = pd.DataFrame([
                    {"Opis PL": row["Polski"], "English version": row.get("English version", "")}
                    for row in manual_translation_rows
                ])
                edited_translations = st.data_editor(
                    editable_translations,
                    hide_index=True,
                    disabled=["Opis PL"],
                    column_config={
                        "Opis PL": st.column_config.TextColumn("Opis PL"),
                        "English version": st.column_config.TextColumn("English version"),
                    },
                    key="printer_copy_en_manual_translation_editor",
                )
                if st.button("Zapisz tłumaczenia ręczne", icon=":material/save:", key="save_printer_copy_en_manual_translations"):
                    st.session_state["printer_copy_en_translation_overrides"] = {
                        row["key"]: str(edited_translations.iloc[index]["English version"]).strip()
                        for index, row in enumerate(manual_translation_rows)
                        if str(edited_translations.iloc[index]["English version"]).strip()
                    }
                    st.success("Tłumaczenia zapisane w bieżącej sesji. Wygeneruj kopię EN ponownie.")

    with technical_card_tab:
        st.markdown("### Karta techniczna produktu")
        st.caption("Karta wykorzystuje pełny zestaw danych z Formularza Zamówienia i pozwala pobrać jego techniczną wersję PDF.")
        active_tds_items = [item for item in st.session_state.get("tds_items", []) if item.get("order_id") == active_order_id]
        with st.expander("📚 TDS zlecenia - wiele produktów", expanded=bool(active_tds_items)):
            if active_tds_items:
                st.dataframe(pd.DataFrame([{
                    "Pozycja": index + 1, "Produkt": item.get("name", ""), "SKU": item.get("sku", ""),
                    "Poziom": item.get("packaging_level", ""), "EAN produktu": item.get("ean_product", ""),
                    "EAN displaya": item.get("ean_display", ""), "EAN Master Case": item.get("ean_mastercase", ""),
                } for index, item in enumerate(active_tds_items)]), hide_index=True, width="stretch")
                tds_to_remove = st.multiselect("Usuń pozycje z kompletnego TDS", [item.get("name", "") + " | " + item.get("packaging_level", "") for item in active_tds_items], key="tds_remove_items")
                if tds_to_remove and st.button("🗑️ Usuń wybrane pozycje TDS"):
                    st.session_state["tds_items"] = [item for item in st.session_state["tds_items"] if item.get("order_id") != active_order_id or (item.get("name", "") + " | " + item.get("packaging_level", "")) not in tds_to_remove]
                    update_order_snapshot("tds", {"order_header": order_header, "items": st.session_state["tds_items"]}, active_order_id)
                    save_order_context(active_order_id)
                    st.rerun()
                combined_tds_data = {}
                for index, item in enumerate(active_tds_items, start=1):
                    snapshot = item.get("catalog_snapshot", {})
                    combined_tds_data[f"TDS pozycja {index}: identyfikacja"] = {
                        "Produkt": item.get("name", ""), "SKU": item.get("sku", ""), "Poziom opakowania": item.get("packaging_level", ""),
                        "EAN produktu": item.get("ean_product", "—") or "—", "EAN displaya": item.get("ean_display", "—") or "—", "EAN Master Case": item.get("ean_mastercase", "—") or "—",
                    }
                    for level in ("Produkt", "Display", "Master Case", "Paleta", "Relacje pakowania"):
                        level_data = snapshot.get(level, {})
                        if level_data:
                            catalog_included = item.get("catalog_pdf_included", {})
                            selected_level_data = {
                                field_name: field_value
                                for field_name, field_value in level_data.items()
                                if catalog_included.get(f"{level}|{field_name}", True)
                            }
                            if selected_level_data:
                                combined_tds_data[f"TDS pozycja {index}: {level}"] = selected_level_data
                    for section, fields in item.get("pdf_data", {}).items():
                        if section != "Nagłówek zlecenia" and fields:
                            combined_tds_data[f"TDS pozycja {index}: {section}"] = fields
                combined_tds_pdf = generate_pdf(
                    combined_tds_data, document_title="KARTY TECHNICZNE PRODUKTÓW - KOMPLET",
                    order_id=active_order_id, include_bct=False,
                )
                st.download_button("📄 Pobierz kompletny TDS wszystkich pozycji", data=combined_tds_pdf.getvalue(), file_name=f"TDS_komplet_{active_order_id}.pdf", mime="application/pdf", key="download_tds_bundle")
            else:
                st.info("Zapisz w Formularzu Zamówienia co najmniej jedną kartę, aby dodać ją do kompletnego TDS zlecenia.")
        technical_source = st.session_state.get("saved_specification")
        # Karty utworzone przed zmianą nazwy pola przechowują poprzednią
        # etykietę w danych PDF. Normalizujemy ją przy odczycie, aby podgląd
        # i kolejne wygenerowanie dokumentu używały aktualnej nazwy.
        if technical_source and technical_source.get("pdf_data"):
            technical_source["pdf_data"].pop("Nagłówek zlecenia", None)
            general_info = technical_source["pdf_data"].setdefault("Informacje Ogólne", {})
            general_info.setdefault("Data utworzenia karty", technical_source.get("timestamp", datetime.now().strftime("%d.%m.%Y"))[:10])
            for section_fields in technical_source["pdf_data"].values():
                if "Wymiary" in section_fields:
                    section_fields["Rozmiar/typ filtra"] = section_fields.pop("Wymiary")
            main_section = technical_source["pdf_data"].get("Sekcja I: Parametry Podstawowe & Materiały", {})
            if "Rozmiar/typ filtra" not in main_section:
                legacy_dimension_value = (
                    technical_source.get("form_state", {}).get("val_dimensions")
                    or st.session_state.get("val_dimensions")
                )
                if legacy_dimension_value not in (None, ""):
                    main_section["Rozmiar/typ filtra"] = legacy_dimension_value
            if "Rozmiar/typ filtra" in main_section:
                dimension_value = main_section.pop("Rozmiar/typ filtra")
                ordered_main_section = {}
                for field_name, field_value in main_section.items():
                    if field_name == "Kolor filtra":
                        ordered_main_section["Rozmiar/typ filtra"] = dimension_value
                    ordered_main_section[field_name] = field_value
                if "Rozmiar/typ filtra" not in ordered_main_section:
                    ordered_main_section["Rozmiar/typ filtra"] = dimension_value
                main_section.clear()
                main_section.update(ordered_main_section)
            pallet_cartons = tab9_as_positive_int(
                technical_source.get("packaging_calculation", {}).get("kartonow_na_palecie")
            )
            if technical_source.get("catalog_snapshot") and pallet_cartons:
                technical_source["pdf_data"].pop("Przeliczenie pozycji: Produkt → Display → Master Case → Paleta", None)
                technical_source["pdf_data"]["Przelicznik opakowań - 1 paleta"] = tab9_packaging_pdf_fields(
                    tab9_packaging_calculation(technical_source["catalog_snapshot"], "Master Case", pallet_cartons, pallet_cartons)
                )
            st.session_state["saved_specification"] = technical_source
        for tds_item in st.session_state.get("tds_items", []):
            if tds_item.get("order_id") == active_order_id:
                tds_item.get("pdf_data", {}).pop("Nagłówek zlecenia", None)
                item_pallet_cartons = tab9_as_positive_int(
                    tds_item.get("packaging_calculation", {}).get("kartonow_na_palecie")
                )
                if tds_item.get("catalog_snapshot") and item_pallet_cartons:
                    tds_item["pdf_data"].pop("Przeliczenie pozycji: Produkt → Display → Master Case → Paleta", None)
                    tds_item["pdf_data"]["Przelicznik opakowań - 1 paleta"] = tab9_packaging_pdf_fields(
                        tab9_packaging_calculation(tds_item["catalog_snapshot"], "Master Case", item_pallet_cartons, item_pallet_cartons)
                    )
                for section_fields in tds_item.get("pdf_data", {}).values():
                    if "Wymiary" in section_fields:
                        section_fields["Rozmiar/typ filtra"] = section_fields.pop("Wymiary")
        if technical_source and technical_source.get("pdf_data"):
            st.success(
                f"Aktywna karta: {technical_source.get('numer_wewnetrzny', 'bez numeru')} "
                f"| plik: {technical_source.get('plik', 'brak')}"
            )
            tds_snapshot = technical_source.get("catalog_snapshot", {})
            if tds_snapshot:
                st.markdown("#### Dane techniczne z kartoteki")
                id_rows = [
                    {"Poziom": "Produkt", "SKU": tds_snapshot.get("SKU", ""), "EAN": tab9_selected_ean(tds_snapshot, "Produkt") or "—"},
                    {"Poziom": "Display", "SKU": tds_snapshot.get("SKU", ""), "EAN": tab9_selected_ean(tds_snapshot, "Display") or "—"},
                    {"Poziom": "Master Case", "SKU": tds_snapshot.get("SKU", ""), "EAN": tab9_selected_ean(tds_snapshot, "Master Case") or "—"},
                ]
                st.dataframe(pd.DataFrame(id_rows), hide_index=True, width="stretch")
                for section_name in ("Produkt", "Display", "Master Case", "Paleta", "Relacje pakowania"):
                    section_data = tds_snapshot.get(section_name, {})
                    if section_data:
                        with st.expander(f"TDS: {section_name}", expanded=section_name in {"Produkt", "Display", "Master Case"}):
                            st.dataframe(
                                pd.DataFrame(list(section_data.items()), columns=["Parametr", "Wartość"]),
                                hide_index=True, width="stretch",
                            )
                catalog_pdf_included = technical_source.get("catalog_pdf_included", {})
                catalog_rows = [
                    {
                        "Uwzględnij w kompletnym TDS": catalog_pdf_included.get(f"{section_name}|{field_name}", True),
                        "Sekcja kartoteki": section_name,
                        "Pole": field_name,
                    }
                    for section_name in ("Produkt", "Display", "Master Case", "Paleta", "Relacje pakowania")
                    for field_name in tds_snapshot.get(section_name, {}).keys()
                ]
                if catalog_rows:
                    st.caption("Pola kartoteki widoczne w kompletnym TDS")
                    catalog_editor = st.data_editor(
                        pd.DataFrame(catalog_rows),
                        hide_index=True,
                        width="stretch",
                        disabled=["Sekcja kartoteki", "Pole"],
                        column_config={
                            "Uwzględnij w kompletnym TDS": st.column_config.CheckboxColumn("Uwzględnij w kompletnym TDS", default=True),
                        },
                        key=f"technical_catalog_editor_{active_order_id}",
                    )
                    if st.button("💾 Zapisz wybór pól kartoteki", key=f"save_technical_catalog_fields_{active_order_id}"):
                        selected_catalog_fields = {
                            f"{row['Sekcja kartoteki']}|{row['Pole']}": bool(row["Uwzględnij w kompletnym TDS"])
                            for row in catalog_editor.to_dict("records")
                        }
                        technical_source["catalog_pdf_included"] = selected_catalog_fields
                        st.session_state["saved_specification"] = technical_source
                        for item in st.session_state.get("tds_items", []):
                            if item.get("order_id") == active_order_id and item.get("catalog_snapshot") == tds_snapshot:
                                item["catalog_pdf_included"] = selected_catalog_fields
                        update_order_snapshot("tds", {"order_header": order_header, "items": st.session_state.get("tds_items", [])}, active_order_id)
                        save_order_context(active_order_id)
                        st.success("Zapisano wybór pól kartoteki do kompletnego TDS.")
                        st.rerun()
            st.markdown("#### Pełna zawartość karty technicznej")
            st.caption("To jest dokładnie zestaw danych używany w PDF. Możesz zmienić wartość oraz zdecydować checkboxem przy każdym polu, czy ma zostać wygenerowane.")

            original_pdf_data = technical_source["pdf_data"]
            technical_card_rows = [
                {
                    "Uwzględnij w PDF": True,
                    "Sekcja": section_name,
                    "Pole": field_name,
                    "Wartość": "" if field_value is None else str(field_value),
                }
                for section_name, section_fields in original_pdf_data.items()
                for field_name, field_value in section_fields.items()
            ]
            technical_card_editor = st.data_editor(
                pd.DataFrame(technical_card_rows),
                hide_index=True,
                width="stretch",
                disabled=["Sekcja", "Pole"],
                column_config={
                    "Uwzględnij w PDF": st.column_config.CheckboxColumn("Uwzględnij w PDF", default=True),
                    "Sekcja": st.column_config.TextColumn("Sekcja"),
                    "Pole": st.column_config.TextColumn("Pole"),
                    "Wartość": st.column_config.TextColumn("Wartość"),
                },
                key=f"technical_card_editor_{active_order_id}",
            )
            if st.button("💾 Zapisz zmiany karty technicznej", key=f"save_technical_card_changes_{active_order_id}"):
                edited_pdf_data = {}
                for row in technical_card_editor.to_dict("records"):
                    if row.get("Uwzględnij w PDF"):
                        edited_pdf_data.setdefault(str(row["Sekcja"]), {})[str(row["Pole"])] = str(row["Wartość"])
                if not edited_pdf_data:
                    st.warning("Wybierz co najmniej jedno pole do wygenerowania w PDF.")
                else:
                    previous_pdf_data = technical_source["pdf_data"]
                    technical_source["pdf_data"] = edited_pdf_data
                    st.session_state["saved_specification"] = technical_source
                    for item in st.session_state.get("tds_items", []):
                        if item.get("order_id") == active_order_id and item.get("pdf_data") == previous_pdf_data:
                            item["pdf_data"] = edited_pdf_data
                    update_order_snapshot("tds", {"order_header": order_header, "items": st.session_state.get("tds_items", [])}, active_order_id)
                    save_order_context(active_order_id)
                    st.success("Zapisano edycję oraz wybór pól do PDF.")
                    st.rerun()
            technical_image_bytes = (
                base64.b64decode(technical_source["technical_image_b64"])
                if technical_source.get("technical_image_b64") else None
            )
            if not technical_image_bytes and technical_source.get("catalog_product_image", {}).get("b64"):
                technical_image_bytes = base64.b64decode(technical_source["catalog_product_image"]["b64"])
                st.image(technical_image_bytes, width=220, caption="Zdjęcie produktu z kartoteki")
            technical_visual_attachments = []
            stored_visuals = technical_source.get("technical_visual_attachments", [])
            if stored_visuals:
                st.markdown("#### Podglądy produktu")
                preview_columns = st.columns(len(stored_visuals))
                for column, visual in zip(preview_columns, stored_visuals):
                    visual_bytes = base64.b64decode(visual["b64"])
                    technical_visual_attachments.append({
                        "label": visual.get("label", "Załącznik graficzny"),
                        "name": visual.get("name", "plik"),
                        "bytes": visual_bytes,
                    })
                    with column:
                        if str(visual.get("mime", "")).startswith("image/"):
                            st.image(visual_bytes, caption=visual.get("label", "Podgląd"), width="stretch")
                        else:
                            st.caption(f"{visual.get('label', 'Załącznik')}: {visual.get('name', 'plik')}")
                            st.download_button(
                                "Pobierz plik", data=visual_bytes, file_name=visual.get("name", "plik"),
                                mime=visual.get("mime", "application/octet-stream"),
                                key=f"download_technical_visual_{active_order_id}_{visual.get('label', 'file')}",
                            )
            technical_pdf = generate_pdf(
                technical_source["pdf_data"], technical_image_bytes,
                technical_source.get("technical_image_name", ""),
                document_title="KARTA TECHNICZNA PRODUKTU",
                order_id=technical_source.get("order_id", active_order_id),
                include_bct=False,
                visual_attachments=technical_visual_attachments,
            )
            technical_pdf_bytes = technical_pdf.getvalue()
            st.download_button(
                "📄 Pobierz kartę techniczną produktu PDF",
                data=technical_pdf_bytes,
                file_name=f"Karta_techniczna_{technical_source.get('numer_wewnetrzny', 'produkt').replace(' ', '_')}.pdf",
                mime="application/pdf",
                key="download_technical_product_card",
            )
            if st.button("📁 Dodaj kartę techniczną do archiwum", key="archive_technical_product_card"):
                technical_entry = {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "order_id": technical_source.get("order_id", active_order_id),
                    "order_header": technical_source.get("order_header", order_header),
                    "numer_wewnetrzny": technical_source.get("numer_wewnetrzny", "Brak"),
                    "plik": technical_source.get("plik", "Brak"),
                    "pdf_data": technical_source["pdf_data"],
                    "form_state": technical_source.get("form_state", {}),
                    "catalog_snapshot": technical_source.get("catalog_snapshot", {}),
                    "catalog_pdf_included": technical_source.get("catalog_pdf_included", {}),
                    "packaging_level": technical_source.get("packaging_level", "Produkt"),
                    "project_info": technical_source.get("project_info", {}),
                    "catalog_product_image": technical_source.get("catalog_product_image", {}),
                    "technical_image_b64": technical_source.get("technical_image_b64", ""),
                    "technical_image_name": technical_source.get("technical_image_name", ""),
                    "technical_visual_attachments": technical_source.get("technical_visual_attachments", []),
                    "pdf_binary_b64": base64.b64encode(technical_pdf_bytes).decode("ascii"),
                }
                db["technical_cards"].append(technical_entry)
                save_database(db)
                st.success("Kartę techniczną zapisano w archiwum.")
            if technical_source.get("form_state") and st.button(
                "📂 Przywołaj dane do edycji w Formularzu Zamówienia",
                key="restore_saved_technical_card",
            ):
                st.session_state["tab9_order_to_restore"] = technical_source["form_state"]
                st.rerun()
        else:
            st.info("Zapisz w sesji lub dodaj do archiwum pełny Formularz Zamówienia, aby utworzyć kartę techniczną produktu.")

        st.markdown("---")
        st.markdown("#### 📁 Archiwum kart technicznych")
        if db["technical_cards"]:
            technical_to_remove = []
            for index, archived_card in enumerate(db["technical_cards"]):
                with st.expander(
                    f"Karta: {archived_card.get('numer_wewnetrzny', 'Brak')} | "
                    f"{archived_card.get('timestamp', '')}", expanded=False
                ):
                    download_col, restore_col, remove_col = st.columns(3)
                    with download_col:
                        if archived_card.get("pdf_binary_b64"):
                            archived_tds_pdf = base64.b64decode(archived_card["pdf_binary_b64"])
                        else:
                            archived_tds_image = (
                                base64.b64decode(archived_card["technical_image_b64"])
                                if archived_card.get("technical_image_b64") else None
                            )
                            if not archived_tds_image and archived_card.get("catalog_product_image", {}).get("b64"):
                                archived_tds_image = base64.b64decode(archived_card["catalog_product_image"]["b64"])
                            archived_tds_buffer = generate_pdf(
                                archived_card.get("pdf_data", {}), archived_tds_image,
                                archived_card.get("technical_image_name", ""),
                                document_title="KARTA TECHNICZNA (TDS)",
                                order_id=archived_card.get("order_id", active_order_id),
                                include_bct=False,
                            )
                            archived_tds_pdf = archived_tds_buffer.getvalue()
                        st.download_button(
                            "📄 Pobierz TDS PDF", data=archived_tds_pdf,
                            file_name=f"Karta_Techniczna_TDS_{archived_card.get('numer_wewnetrzny', 'produkt').replace(' ', '_')}.pdf",
                            mime="application/pdf", key=f"download_archived_tds_{index}",
                        )
                    with restore_col:
                        if archived_card.get("form_state") and st.button(
                            "📂 Przywołaj do edycji", key=f"restore_archived_tds_{index}"
                        ):
                            st.session_state["tab9_order_to_restore"] = archived_card["form_state"]
                            st.session_state["tab9_catalog_snapshot_to_restore"] = archived_card.get("catalog_snapshot", {})
                            st.session_state["tab9_project_attachment_to_restore"] = archived_card.get("project_info", {}).get("attachment", {})
                            st.rerun()
                    with remove_col:
                        if st.button("🗑️ Usuń", key=f"delete_archived_tds_{index}"):
                            technical_to_remove.append(index)
            if technical_to_remove:
                db["technical_cards"] = [
                    card for index, card in enumerate(db["technical_cards"])
                    if index not in technical_to_remove
                ]
                save_database(db)
                st.rerun()
        else:
            st.info("Brak zapisanych kart technicznych.")

    with dict_tab:
        st.markdown("### ⚙️ Zarządzanie Słownikami (Baza Danych)")
        dict_labels = {
            "products": "📦 Produkty", "other_criteria": "📋 Inne kryteria", "dimensions": "📏 Wymiary",
            "filter_colors": "🎨 Kolory filtrów", "box_paper_colors": "📄 Kolory papieru w boxie",
            "print_types": "🖨️ Rodzaje druku", "orders_clients": "👥 Klienci / Kanały zamówień",
            "grammages": "⚖️ Gramatury", "print_covers": "📖 Zadruki / Okładki",
            "color_spaces": "🌈 Przestrzenie kolorów (Rozbarwienia)", "press_combinations": "⚙️ Kombinacje maszynowe",
            "varnishes": "✨ Lakiery / Folie", "foil_options": "🛡️ Opcje foliowania",
            "perforations": "✂️ Perforacje", "yes_no": "✅ Tak / Nie", "display_prints": "🖼️ Zadruki Display"
        }

        selected_dict_key = st.selectbox("Wybierz słownik do edycji", options=list(dict_labels.keys()), format_func=lambda x: dict_labels[x])

        if selected_dict_key in db:
            col_add1, col_add2 = st.columns([3, 1])
            with col_add1:
                new_item = st.text_input("Nowa pozycja do dodania", key=f"new_item_{selected_dict_key}")
            with col_add2:
                st.write("") 
                st.write("")
                add_btn = st.button("➕ Dodaj pozycję")
            
            if add_btn:
                if new_item and new_item not in db[selected_dict_key]:
                    db[selected_dict_key].append(new_item)
                    save_database(db)
                    st.success(f"Dodano pomyślnie: '{new_item}'")
                    st.rerun()
                elif new_item in db[selected_dict_key]:
                    st.warning("Taka pozycja już znajduje się w tym słowniku.")

            st.markdown("---")
            items_to_remove = []
            for item in db[selected_dict_key]:
                cols = st.columns([4, 1])
                with cols[0]:
                    st.text(f"• {item}")
                with cols[1]:
                    if st.button("🗑️ Usuń", key=f"del_{selected_dict_key}_{item}"):
                        items_to_remove.append(item)
            
            if items_to_remove:
                for item in items_to_remove:
                    db[selected_dict_key].remove(item)
                save_database(db)
                st.success("Usunięto wybrane pozycje!")
                st.rerun()

    with archive_tab:
        st.markdown("### 📁 Zapisane w bazie zlecenia i karty produktów")
        if db["orders"]:
            st.info("Pobierz PDF, przywołaj zapisane zamówienie do edycji albo zaznacz pozycje do usunięcia.")
            
            indices_to_remove = []
            for i, order in enumerate(db["orders"]):
                col_chk, col_info, col_dl, col_restore = st.columns([1, 6, 3, 3])
                with col_chk:
                    is_selected = st.checkbox("Wybierz", key=f"archive_del_{i}", label_visibility="collapsed")
                with col_info:
                    st.text(f"[{order.get('timestamp', 'Brak daty')}] Numer wewnętrzny: {order.get('numer_wewnetrzny', 'Brak')} | Plik: {order.get('plik', 'Brak')}")
                with col_dl:
                    if order.get("pdf_binary_b64"):
                        pdf_bytes = base64.b64decode(order["pdf_binary_b64"])
                        st.download_button(
                            label="📥 Pobierz PDF",
                            data=pdf_bytes,
                            file_name=f"zamowienie_{order.get('numer_wewnetrzny', 'archiwum').replace(' ', '_')}_{i}.pdf",
                            mime="application/pdf",
                            key=f"dl_pdf_archive_{i}"
                        )
                    elif 'pdf_data' in order and order['pdf_data']:
                        archived_image_bytes = (
                            base64.b64decode(order["technical_image_b64"])
                            if order.get("technical_image_b64") else None
                        )
                        pdf_bytes = generate_pdf(
                            order['pdf_data'], archived_image_bytes,
                            order.get("technical_image_name", ""),
                            order_id=order.get("order_id", active_order_id),
                            include_bct=False,
                        )
                        st.download_button(
                            label="📥 Pobierz PDF",
                            data=pdf_bytes,
                            file_name=f"zamowienie_{order.get('numer_wewnetrzny', 'archiwum').replace(' ', '_')}_{i}.pdf",
                            mime="application/pdf",
                            key=f"dl_pdf_archive_{i}"
                        )
                    else:
                        st.caption("Brak danych PDF")
                    project_attachment = order.get("project_info", {}).get("attachment", {})
                    if project_attachment.get("b64"):
                        st.download_button(
                            "📎 Pobierz plik źródłowy",
                            data=base64.b64decode(project_attachment["b64"]),
                            file_name=project_attachment.get("name", "projekt_zrodlowy"),
                            mime=project_attachment.get("mime", "application/octet-stream"),
                            key=f"download_project_source_{i}",
                        )
                        for version_index, project_version in enumerate(project_attachment.get("versions", []), start=1):
                            if project_version.get("b64"):
                                st.download_button(
                                    f"📎 Pobierz starszą wersję projektu v{version_index}",
                                    data=base64.b64decode(project_version["b64"]),
                                    file_name=project_version.get("name", f"projekt_v{version_index}"),
                                    mime=project_version.get("mime", "application/octet-stream"),
                                    key=f"download_project_source_{i}_old_{version_index}",
                                )
                with col_restore:
                    if order.get("form_state"):
                        if st.button("📂 Przywołaj zamówienie", key=f"restore_order_{i}"):
                            st.session_state["tab9_order_to_restore"] = order["form_state"]
                            st.session_state["tab9_catalog_snapshot_to_restore"] = order.get("catalog_snapshot", {})
                            st.session_state["tab9_project_attachment_to_restore"] = order.get("project_info", {}).get("attachment", {})
                            st.rerun()
                    else:
                        st.caption("Starszy wpis: brak danych do edycji")

                if is_selected:
                    indices_to_remove.append(i)
            
            st.markdown("---")
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("🗑️ Usuń zaznaczone z archiwum"):
                    if indices_to_remove:
                        db["orders"] = [order for idx, order in enumerate(db["orders"]) if idx not in indices_to_remove]
                        save_database(db)
                        st.success("Usunięto zaznaczone pozycje z archiwum!")
                        st.rerun()
                    else:
                        st.warning("Nie zaznaczono żadnych pozycji do usunięcia.")
            with col_btn2:
                if st.button("🗑️ Wyczyść całe archiwum"):
                    db["orders"] = []
                    save_database(db)
                    st.success("Archiwum zostało wyczyszczone.")
                    st.rerun()
        else:
            st.info("Brak zapisanych zleceń w bazie danych.")

    with eorder_tab:
        st.markdown("### 📦 E-Order – Elektroniczne Potwierdzenie Zamówienia dla Klienta")
        st.markdown("Tutaj znajdują się pozycje dodane tymczasowo z formularza. Możesz je sprawdzić, poprawić dane w tabeli poniżej, wygenerować zbiorcze potwierdzenie PDF lub zapisać/wczytać z archiwum bazy danych.")

        if st.session_state["e_order_items"]:
            db.setdefault("delivery_contacts", [])
            delivery_contacts = list(db.get("delivery_contacts", []))
            # Kontakty utworzone w module E-mail są również dostępne jako odbiorcy,
            # nawet jeśli nie mają jeszcze zapisanego adresu dostawy.
            for email_contact in db.get("email_contacts", []):
                if email_contact.get("group") == "Klient" and not any(
                    entry.get("email", "").lower() == email_contact.get("email", "").lower()
                    for entry in delivery_contacts
                ):
                    delivery_contacts.append({
                        "name": email_contact.get("name", ""), "company": email_contact.get("name", ""),
                        "email": email_contact.get("email", ""), "street": "", "postal_code": "", "city": "", "country": "",
                    })
            contact_labels = ["— wprowadź ręcznie —"] + [
                f"{item.get('company') or item.get('name') or 'Odbiorca'} | {item.get('email', '')}" for item in delivery_contacts
            ]
            shared_delivery = order_header.get("delivery", {}) or {}
            shared_recipient = order_header.get("recipient", {}) or shared_delivery.get("recipient", {}) or {}
            shared_address = order_header.get("delivery_address", {}) or shared_delivery.get("address", {}) or {}
            shared_email = str(shared_recipient.get("email", "")).lower()
            saved_contact_index = next(
                (index for index, item in enumerate(delivery_contacts, start=1)
                 if shared_email and str(item.get("email", "")).lower() == shared_email),
                0,
            )
            selected_contact_label = st.selectbox(
                "Odbiorca z książki kontaktów",
                contact_labels,
                index=saved_contact_index,
                key=f"eo_delivery_contact_select_{active_order_id}",
            )
            selected_contact = {}
            if selected_contact_label != contact_labels[0]:
                selected_contact = delivery_contacts[contact_labels.index(selected_contact_label) - 1]
            recipient_keys = {
                "name": f"eo_recipient_name_{active_order_id}", "company": f"eo_recipient_company_{active_order_id}",
                "email": f"eo_recipient_email_{active_order_id}", "street": f"eo_delivery_street_{active_order_id}",
                "postal_code": f"eo_delivery_postal_{active_order_id}", "city": f"eo_delivery_city_{active_order_id}",
                "country": f"eo_delivery_country_{active_order_id}",
            }
            contact_marker = f"eo_delivery_contact_loaded_{active_order_id}"
            if st.session_state.get(contact_marker) != selected_contact_label:
                initial_contact = selected_contact or {**shared_address, **shared_recipient}
                for field, state_key in recipient_keys.items():
                    st.session_state[state_key] = initial_contact.get(field, "") if initial_contact else ("Polska" if field == "country" else "")
                st.session_state[contact_marker] = selected_contact_label

            with st.expander("Odbiorca i adres dostawy", expanded=True):
                recipient_col, delivery_col = st.columns(2)
                with recipient_col:
                    eo_recipient_name = st.text_input("Osoba kontaktowa", key=recipient_keys["name"])
                    eo_recipient_company = st.text_input("Firma odbiorcy", key=recipient_keys["company"])
                    eo_recipient_email = st.text_input("E-mail odbiorcy", key=recipient_keys["email"])
                with delivery_col:
                    eo_delivery_street = st.text_input("Ulica i numer", key=recipient_keys["street"])
                    delivery_subcol1, delivery_subcol2 = st.columns(2)
                    with delivery_subcol1:
                        eo_delivery_postal = st.text_input("Kod pocztowy", key=recipient_keys["postal_code"])
                    with delivery_subcol2:
                        eo_delivery_city = st.text_input("Miasto", key=recipient_keys["city"])
                    eo_delivery_country = st.text_input("Kraj", value="Polska", key=recipient_keys["country"])
                if st.button("📇 Zapisz odbiorcę do książki kontaktów", key=f"save_delivery_contact_{active_order_id}"):
                    if not eo_recipient_company.strip() or not eo_recipient_email.strip():
                        st.warning("Podaj co najmniej firmę odbiorcy i adres e-mail.")
                    else:
                        contact_payload = {
                            "name": eo_recipient_name.strip(), "company": eo_recipient_company.strip(), "email": eo_recipient_email.strip().lower(),
                            "street": eo_delivery_street.strip(), "postal_code": eo_delivery_postal.strip(),
                            "city": eo_delivery_city.strip(), "country": eo_delivery_country.strip(),
                        }
                        db["delivery_contacts"] = [item for item in db["delivery_contacts"] if item.get("email", "").lower() != contact_payload["email"]]
                        db["delivery_contacts"].append(contact_payload)
                        save_database(db)
                        st.success("Odbiorcę zapisano w książce kontaktów.")

            recipient_payload = {"name": eo_recipient_name, "company": eo_recipient_company, "email": eo_recipient_email}
            delivery_address_payload = {
                "street": eo_delivery_street, "postal_code": eo_delivery_postal,
                "city": eo_delivery_city, "country": eo_delivery_country,
            }

            if st.button("🔗 Ustaw jako wspólne dane dostawy zlecenia", key=f"save_shared_delivery_{active_order_id}"):
                save_order_delivery_data(active_order_id, recipient_payload, delivery_address_payload, order_header.get("delivery_date", ""))
                st.success("Odbiorcę i adres zapisano jako wspólne dane zlecenia.")

            col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
            with col_m1:
                eo_order_no = st.text_input("Nr zlecenia", value=order_header["order_number"], key=f"eo_order_no_{active_order_id}")
            with col_m2:
                try:
                    eo_delivery_default = datetime.fromisoformat(str(order_header.get("delivery_date", ""))).date()
                except (TypeError, ValueError):
                    eo_delivery_default = datetime.now().date()
                eo_delivery_date = st.date_input(
                    "Data dostawy", value=eo_delivery_default, key=f"eo_delivery_date_{active_order_id}",
                ).isoformat()
            with col_m3:
                eo_order_date = st.text_input("Data zamówienia", value=datetime.now().strftime('%d.%m.%Y'))
            with col_m4:
                eo_reprint = st.selectbox("REPRINT", options=["TAK", "NIE"], index=1)
            with col_m5:
                eo_response_status = st.selectbox("Status odpowiedzi klienta", ["wysłano", "zaakceptowano", "odrzucono", "wymaga zmian"], key=f"eo_response_status_{active_order_id}")
            eo_document_language = st.selectbox(
                "Wersja językowa E-Order", ["PL", "EN", "PL/EN"],
                index=["PL", "EN", "PL/EN"].index(order_header.get("language", "PL")),
                key=f"eo_document_language_{active_order_id}",
            )
            eo_confirmation_note = st.text_input(
                "Potwierdzenie terminu i ilości przez klienta",
                value="Oczekuje na potwierdzenie",
                key=f"eo_confirmation_note_{active_order_id}",
            )

            st.markdown("---")
            st.markdown("#### Lista pozycji do potwierdzenia:")

            items_to_drop = []
            updated_items = []

            for idx, item in enumerate(st.session_state["e_order_items"]):
                with st.expander(f"Poz. {idx+1}: {item.get('product_name', 'Brak')} ({item.get('product_type', '')})", expanded=False):
                    c1, c2, c3 = st.columns(3)
                    previous_snapshot = item.get("catalog_snapshot", {}) or {}
                    previous_catalog_name = previous_snapshot.get("Nazwa produktu", "")
                    eorder_catalog_options = ["— pozycja ręczna —"] + sorted(catalog_products.keys(), key=str.lower)
                    if previous_catalog_name not in eorder_catalog_options:
                        previous_catalog_name = "— pozycja ręczna —"
                    current_eorder_level = item.get("packaging_level", "Produkt")
                    if current_eorder_level not in ["Produkt", "Display", "Master Case"]:
                        current_eorder_level = "Produkt"
                    with c1:
                        selected_eorder_catalog = st.selectbox(
                            "Produkt z kartoteki", eorder_catalog_options,
                            index=eorder_catalog_options.index(previous_catalog_name),
                            key=f"eo_catalog_{idx}",
                        )
                        new_packaging_level = st.selectbox(
                            "Poziom pozycji", ["Produkt", "Display", "Master Case"],
                            index=["Produkt", "Display", "Master Case"].index(current_eorder_level),
                            key=f"eo_packaging_level_{idx}",
                        )
                        eorder_snapshot = (
                            build_tab9_catalog_snapshot(selected_eorder_catalog)
                            if selected_eorder_catalog != "— pozycja ręczna —" else {}
                        )
                        catalog_changed = selected_eorder_catalog != previous_catalog_name
                        if catalog_changed and eorder_snapshot:
                            st.session_state[f"eo_pname_{idx}"] = eorder_snapshot.get("Nazwa produktu", selected_eorder_catalog)
                            st.session_state[f"eo_client_{idx}"] = eorder_snapshot.get("Klient", "")
                        inc_pname, new_pname = render_existing_includable_field("Nazwa produktu", "text", value=eorder_snapshot.get("Nazwa produktu", item.get("product_name", "")), key=f"eo_pname_{idx}")
                        inc_ptype, new_ptype = render_existing_includable_field("Produkt", "text", value=item.get("product_type", ""), key=f"eo_ptype_{idx}")
                        inc_crit, new_crit = render_existing_includable_field("Inne kryteria", "text", value=item.get("other_criteria", ""), key=f"eo_crit_{idx}")
                        inc_lot, new_lot = render_existing_includable_field("Numer partii / LOT", "text", value=item.get("lot_number", ""), key=f"eo_lot_{idx}")
                        st.caption(
                            f"SKU: {eorder_snapshot.get('SKU') or item.get('sku') or 'brak'} | "
                            f"EAN użyty: {tab9_selected_ean(eorder_snapshot, new_packaging_level) or item.get('ean_selected') or 'brak'}"
                        )
                        eorder_calc = item.get("packaging_calculation", {})
                        if eorder_calc:
                            st.caption(
                                f"Przeliczenie wysyłki: {eorder_calc.get('displayow', 0)} displaye | "
                                f"{eorder_calc.get('mastercase', 0)} Master Case | {eorder_calc.get('palet', 0)} palet"
                            )
                    with c2:
                        inc_fcolor, new_fcolor = render_existing_includable_field("Kolor filtra", "text", value=item.get("filter_color", ""), key=f"eo_fcolor_{idx}")
                        inc_dim, new_dim = render_existing_includable_field("Wymiary", "text", value=item.get("dimensions", ""), key=f"eo_dim_{idx}")
                        inc_pcolor, new_pcolor = render_existing_includable_field("Kolor papieru w boxie", "text", value=item.get("box_paper_color", ""), key=f"eo_pcolor_{idx}")
                        inc_client, new_client = render_existing_includable_field("Klient", "text", value=item.get("order_channel", ""), key=f"eo_client_{idx}")
                    with c3:
                        inc_qnet, new_qnet = render_existing_includable_field("Ilość netto", "number", value=item.get("qty_net", 0), key=f"eo_qnet_{idx}")
                        inc_qbuffer, new_qbuffer = render_existing_includable_field("Zapas [szt.]", "number", value=item.get("qty_buffer", 0), key=f"eo_qbuffer_{idx}")
                        st.caption(f"Ilość z zapasem: {new_qnet + new_qbuffer}")
                        inc_qproduction, new_qproduction = render_existing_includable_field("Ilość do produkcji", "number", value=item.get("qty_production", 0), key=f"eo_qproduction_{idx}")
                        inc_qshipping, new_qshipping = render_existing_includable_field("Ilość do wysyłki", "number", value=item.get("qty_shipping", 0), key=f"eo_qshipping_{idx}")
                        inc_qdpieces, new_qdpieces = render_existing_includable_field("Ilość sztuk w display", "number", value=item.get("qty_display_pieces", 0), key=f"eo_qdpieces_{idx}")
                        inc_qcarton, new_qcarton = render_existing_includable_field("Ilość sztuk w kartonie", "number", value=item.get("qty_carton", 0), key=f"eo_qcarton_{idx}")
                        inc_carr_pal, new_carr_pal = render_existing_includable_field("Kartony na palecie", "number", value=item.get("qty_cartons_palette", 0), key=f"eo_cpal_{idx}")
                        inc_disp_pal, new_disp_pal = render_existing_includable_field("Display'e na palecie", "number", value=item.get("qty_displays_palette", 0), key=f"eo_dpal_{idx}")

                    drop_chk = st.checkbox("Usuń tę pozycję z E-Order", key=f"eo_drop_{idx}")
                    if drop_chk:
                        items_to_drop.append(idx)

                    eorder_recalculated = (
                        tab9_packaging_calculation(
                            eorder_snapshot,
                            new_packaging_level,
                            new_qshipping or new_qnet,
                            new_carr_pal,
                        ) if eorder_snapshot else item.get("packaging_calculation", {})
                    )
                    updated_items.append({
                        "product_name": new_pname,
                        "product_type": new_ptype,
                        "other_criteria": new_crit,
                        "filter_color": new_fcolor,
                        "dimensions": new_dim,
                        "box_paper_color": new_pcolor,
                        "order_channel": new_client,
                        "qty_net": new_qnet,
                        "qty_buffer": new_qbuffer,
                        "qty_with_buffer": new_qnet + new_qbuffer,
                        "qty_production": new_qproduction,
                        "qty_shipping": new_qshipping,
                        "lot_number": new_lot,
                        "qty_display_pieces": new_qdpieces,
                        "qty_carton": new_qcarton,
                        "qty_cartons_palette": new_carr_pal,
                        "qty_displays_palette": new_disp_pal,
                        "sku": eorder_snapshot.get("SKU", item.get("sku", "")),
                        "ean_product": tab9_selected_ean(eorder_snapshot, "Produkt") or item.get("ean_product", ""),
                        "ean_display": tab9_selected_ean(eorder_snapshot, "Display") or item.get("ean_display", ""),
                        "ean_mastercase": tab9_selected_ean(eorder_snapshot, "Master Case") or item.get("ean_mastercase", ""),
                        "ean_selected": tab9_selected_ean(eorder_snapshot, new_packaging_level) or item.get("ean_selected", ""),
                        "packaging_level": new_packaging_level,
                        "catalog_snapshot": eorder_snapshot,
                        "packaging_calculation": eorder_recalculated,
                        "project_info": item.get("project_info", {}),
                        "order_id": item.get("order_id", active_order_id),
                        "order_header": item.get("order_header", order_header),
                        "included_fields": {"product_name": inc_pname, "product_type": inc_ptype, "other_criteria": inc_crit, "lot_number": inc_lot, "filter_color": inc_fcolor, "dimensions": inc_dim, "box_paper_color": inc_pcolor, "order_channel": inc_client, "qty_net": inc_qnet, "qty_buffer": inc_qbuffer, "qty_production": inc_qproduction, "qty_shipping": inc_qshipping, "qty_display_pieces": inc_qdpieces, "qty_carton": inc_qcarton, "qty_cartons_palette": inc_carr_pal, "qty_displays_palette": inc_disp_pal},
                    })

            st.session_state["e_order_items"] = [item for i, item in enumerate(updated_items) if i not in items_to_drop]

            st.markdown("---")
            col_act1, col_act2, col_act3, col_act4 = st.columns(4)
            with col_act1:
                if st.button("🗑️ Wyczyść całą listę E-Order"):
                    st.session_state["e_order_items"] = []
                    st.success("Wyczyszczono listę E-Order.")
                    st.rerun()
            with col_act2:
                if st.button("💾 Zapisz E-Order w archiwum bazy"):
                    eorder_errors, eorder_warnings = tab9_validate_eorder(
                        st.session_state["e_order_items"], recipient_payload, eo_delivery_date,
                    )
                    tab9_apply_approval_validation(
                        eorder_errors, eorder_warnings, order_header.get("document_status"), eo_response_status,
                    )
                    eorder_entry = {
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "order_id": active_order_id,
                        "order_header": order_header,
                        "order_no": eo_order_no,
                        "delivery_date": eo_delivery_date,
                        "order_date": eo_order_date,
                        "reprint": eo_reprint,
                        "recipient": recipient_payload,
                        "delivery_address": delivery_address_payload,
                        "response_status": eo_response_status,
                        "confirmation_note": eo_confirmation_note,
                        "language": eo_document_language,
                        "items": st.session_state["e_order_items"]
                    }
                    if eorder_errors:
                        st.error("E-Order nie został zapisany. Uzupełnij: " + " | ".join(eorder_errors))
                    else:
                        for warning in eorder_warnings:
                            st.warning(warning)
                        save_order_delivery_data(
                            active_order_id, recipient_payload, delivery_address_payload, eo_delivery_date,
                        )
                        db["e_orders"].append(eorder_entry)
                        save_database(db)
                        register_document("E-Order", {
                            "order_no": eo_order_no, "items": len(st.session_state["e_order_items"]),
                            "recipient": eo_recipient_company, "response_status": eo_response_status,
                        }, status=eo_response_status)
                        update_order_snapshot("eorder", {"order_no": eo_order_no, "recipient": recipient_payload, "items": st.session_state["e_order_items"]}, active_order_id)
                        save_order_context(active_order_id)
                        st.success("E-Order został zapisany w archiwum bazy danych!")
            with col_act3:
                eorder_errors, eorder_warnings = tab9_validate_eorder(
                    st.session_state["e_order_items"], recipient_payload, eo_delivery_date,
                )
                tab9_apply_approval_validation(
                    eorder_errors, eorder_warnings, order_header.get("document_status"), eo_response_status,
                )
                meta_bundle = {
                    "order_no": eo_order_no,
                    "delivery_date": eo_delivery_date,
                    "order_date": eo_order_date,
                    "reprint": eo_reprint,
                    "order_id": active_order_id,
                    "priority": order_header["priority"],
                    "document_version": order_header["document_version"],
                    "recipient": recipient_payload,
                    "delivery_address": delivery_address_payload,
                    "response_status": eo_response_status,
                    "confirmation_note": eo_confirmation_note,
                }
                if eorder_errors:
                    st.error("PDF E-Order jest zablokowany: " + " | ".join(eorder_errors))
                else:
                    for warning in eorder_warnings:
                        st.warning(warning)
                    if eo_document_language == "PL":
                        meta_bundle["lang"] = "pl"
                        eorder_pdf = generate_eorder_pdf(st.session_state["e_order_items"], meta_bundle)
                        eorder_file_name = f"E_Zamowienie_PL_{eo_order_no.replace('/', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
                    elif eo_document_language == "EN":
                        meta_bundle["lang"] = "en"
                        eorder_pdf = generate_eorder_pdf(st.session_state["e_order_items"], meta_bundle)
                        eorder_file_name = f"E_Order_EN_{eo_order_no.replace('/', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
                    else:
                        eorder_pdf = generate_eorder_bilingual_pdf(st.session_state["e_order_items"], meta_bundle)
                        eorder_file_name = f"E_Order_PL_EN_{eo_order_no.replace('/', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
                    st.download_button(
                        label=f"📄 Pobierz E-Order PDF ({eo_document_language})",
                        data=eorder_pdf, file_name=eorder_file_name, mime="application/pdf", key="dl_eorder_active"
                    )
            with col_act4:
                st.info(f"Status: **{eo_response_status}**\n\n{eo_confirmation_note}")

        st.markdown("---")
        st.markdown("#### 📁 Archiwum zapisanych E-Orderów")
        if db["e_orders"]:
            eo_to_remove = []
            for i, eo_arch in enumerate(db["e_orders"]):
                with st.expander(f"E-Order nr: {eo_arch.get('order_no', 'Brak')} | Data: {eo_arch.get('timestamp', '')} | Pozycji: {len(eo_arch.get('items', []))}", expanded=False):
                    st.text(
                        f"Data zamówienia: {eo_arch.get('order_date')} | Dostawa: {eo_arch.get('delivery_date')} | "
                        f"Odbiorca: {eo_arch.get('recipient', {}).get('company', 'brak')} | "
                        f"Status: {eo_arch.get('response_status', 'brak')} | Reprint: {eo_arch.get('reprint')}"
                    )
                    
                    col_dl_pl, col_dl_en, col_dl_bilingual, col_load_eo, col_del_eo = st.columns(5)
                    with col_dl_pl:
                        pdf_eo_pl = generate_eorder_pdf(eo_arch.get('items', []), {
                            "order_id": eo_arch.get("order_id", active_order_id),
                            "order_no": eo_arch.get('order_no', ''),
                            "delivery_date": eo_arch.get('delivery_date', ''),
                            "order_date": eo_arch.get('order_date', ''),
                            "reprint": eo_arch.get('reprint', 'NIE'),
                            "lang": "pl",
                            "priority": eo_arch.get("order_header", {}).get("priority", "normalny"),
                            "document_version": eo_arch.get("order_header", {}).get("document_version", "v1"),
                            "recipient": eo_arch.get("recipient", {}),
                            "delivery_address": eo_arch.get("delivery_address", {}),
                            "response_status": eo_arch.get("response_status", "wysłano"),
                            "confirmation_note": eo_arch.get("confirmation_note", ""),
                        })
                        st.download_button(
                            label="📥 Pobierz E-zamówenie PDF",
                            data=pdf_eo_pl,
                            file_name=f"E_Zamowienie_PL_{eo_arch.get('order_no', '14').replace('/', '_')}_{i}.pdf",
                            mime="application/pdf",
                            key=f"dl_eo_arch_pl_{i}"
                        )
                    with col_dl_en:
                        pdf_eo_en = generate_eorder_pdf(eo_arch.get('items', []), {
                            "order_id": eo_arch.get("order_id", active_order_id),
                            "order_no": eo_arch.get('order_no', ''),
                            "delivery_date": eo_arch.get('delivery_date', ''),
                            "order_date": eo_arch.get('order_date', ''),
                            "reprint": eo_arch.get('reprint', 'NIE'),
                            "lang": "en",
                            "priority": eo_arch.get("order_header", {}).get("priority", "normalny"),
                            "document_version": eo_arch.get("order_header", {}).get("document_version", "v1"),
                            "recipient": eo_arch.get("recipient", {}),
                            "delivery_address": eo_arch.get("delivery_address", {}),
                            "response_status": eo_arch.get("response_status", "wysłano"),
                            "confirmation_note": eo_arch.get("confirmation_note", ""),
                        })
                        st.download_button(
                            label="📥 E-Order PDF",
                            data=pdf_eo_en,
                            file_name=f"E_Order_EN_{eo_arch.get('order_no', '14').replace('/', '_')}_{i}.pdf",
                            mime="application/pdf",
                            key=f"dl_eo_arch_en_{i}"
                        )
                    with col_dl_bilingual:
                        pdf_eo_bilingual = generate_eorder_bilingual_pdf(eo_arch.get('items', []), {
                            "order_id": eo_arch.get("order_id", active_order_id),
                            "order_no": eo_arch.get('order_no', ''),
                            "delivery_date": eo_arch.get('delivery_date', ''),
                            "order_date": eo_arch.get('order_date', ''),
                            "reprint": eo_arch.get('reprint', 'NIE'),
                            "priority": eo_arch.get("order_header", {}).get("priority", "normalny"),
                            "document_version": eo_arch.get("order_header", {}).get("document_version", "v1"),
                            "recipient": eo_arch.get("recipient", {}),
                            "delivery_address": eo_arch.get("delivery_address", {}),
                            "response_status": eo_arch.get("response_status", "wysłano"),
                            "confirmation_note": eo_arch.get("confirmation_note", ""),
                        })
                        st.download_button(
                            label="📥 E-Order PL/EN",
                            data=pdf_eo_bilingual,
                            file_name=f"E_Order_PL_EN_{eo_arch.get('order_no', '14').replace('/', '_')}_{i}.pdf",
                            mime="application/pdf",
                            key=f"dl_eo_arch_bilingual_{i}"
                        )
                    with col_load_eo:
                        if st.button("📂 Wczytaj do edycji", key=f"load_eo_arch_{i}"):
                            st.session_state["e_order_items"] = eo_arch.get('items', [])
                            st.success("Wczytano E-Order do aktywnego formularza!")
                            st.rerun()
                    with col_del_eo:
                        if st.button("🗑️ Usuń z archiwum", key=f"del_eo_arch_{i}"):
                            eo_to_remove.append(i)
            if eo_to_remove:
                db["e_orders"] = [item for idx, item in enumerate(db["e_orders"]) if idx not in eo_to_remove]
                save_database(db)
                st.success("Usunięto zaznaczone E-Ordery z archiwum.")
                st.rerun()
        else:
            if not st.session_state["e_order_items"]:
                st.info("Brak pozycji w E-Order oraz brak zapisanych E-Orderów w archiwum.")

    with worksheet_tab:
        st.markdown("### 📋 Karta Pracy – Zestawienie Produkcyjne")
        st.markdown("Tutaj znajdują się pozycje dodane do Karty Pracy. Możesz edytować ich parametry, zapisać w archiwum bazy lub wygenerować oficjalny plik PDF.")

        if st.session_state["work_sheet_items"]:
            col_wm1, col_wm2, col_wm3, col_wm4, col_wm5 = st.columns(5)
            with col_wm1:
                inc_ws_order_no, ws_order_no = render_existing_includable_field("Nr zlecenia / Karty Pracy", "text", value=order_header["order_number"], key=f"ws_ord_no_{active_order_id}")
            with col_wm2:
                inc_ws_order_date, ws_order_date = render_existing_includable_field("Data sporządzenia", "text", value=datetime.now().strftime('%d.%m.%Y'), key="ws_ord_date")
            with col_wm3:
                inc_ws_production_order_no, ws_production_order_no = render_existing_includable_field("Nr zlecenia produkcyjnego", "text", value=f"{order_header['order_number']}-P", key=f"ws_production_order_{active_order_id}")
            with col_wm4:
                inc_ws_machine, ws_machine = render_existing_includable_field("Stanowisko / maszyna", "text", value=st.session_state.get(f"ws_machine_{active_order_id}", ""), key=f"ws_machine_{active_order_id}")
                inc_ws_operator, ws_operator = render_existing_includable_field("Operator", "text", value=st.session_state.get(f"ws_operator_{active_order_id}", ""), key=f"ws_operator_{active_order_id}")
            with col_wm5:
                inc_ws_shift, ws_shift = render_existing_includable_field("Zmiana", "select", value=st.session_state.get(f"ws_shift_{active_order_id}", "I"), options=["I", "II", "III", "nocna", "inna"], key=f"ws_shift_{active_order_id}")
                inc_ws_planned_time, ws_planned_time = render_existing_includable_field("Czas planowany [h]", "number", value=st.session_state.get(f"ws_planned_time_{active_order_id}", 0.0), key=f"ws_planned_time_{active_order_id}")
            include_production_realization = st.checkbox(
                "Uwzględnij realizację produkcji w PDF", value=True,
                key=f"ws_include_production_realization_{active_order_id}",
            )
            production_meta = {
                "production_order_no": ws_production_order_no,
                "machine": ws_machine,
                "operator": ws_operator,
                "shift": ws_shift,
                "planned_time_hours": ws_planned_time,
                "included_fields": {
                    "production_order_no": inc_ws_production_order_no, "machine": inc_ws_machine,
                    "operator": inc_ws_operator, "shift": inc_ws_shift, "planned_time_hours": inc_ws_planned_time,
                },
            }

            st.markdown("---")
            st.markdown("#### Pozycje w Karcie Pracy:")

            ws_items_to_drop = []
            updated_ws_items = []

            for idx, item in enumerate(st.session_state["work_sheet_items"]):
                with st.expander(f"Poz. {idx+1}: Klient: {item.get('order_channel', '-')} | Towar: {item.get('product_name', '-')}", expanded=False):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        inc_ws_client, ws_client = render_existing_includable_field("Klient", "text", value=item.get("order_channel", ""), key=f"ws_client_{idx}")
                        inc_ws_pname, ws_pname = render_existing_includable_field("Nazwa towaru lub usługi", "text", value=item.get("product_name", ""), key=f"ws_pname_{idx}")
                        inc_ws_crit, ws_crit = render_existing_includable_field("Inne kryteria", "text", value=item.get("other_criteria", ""), key=f"ws_crit_{idx}")
                        inc_ws_display, ws_display = render_existing_includable_field("Display", "text", value=item.get("display_type", ""), key=f"ws_display_{idx}")
                        inc_ws_lot, ws_lot = render_existing_includable_field("Numer partii / LOT", "text", value=item.get("lot_number", ""), key=f"ws_lot_{idx}")
                        st.caption(
                            f"Poziom: {item.get('packaging_level', 'Produkt')} | "
                            f"SKU: {item.get('sku') or 'brak'} | "
                            f"EAN użyty: {item.get('ean_selected') or 'brak'}"
                        )
                        worksheet_calc = item.get("packaging_calculation", {})
                        if worksheet_calc:
                            st.caption(
                                f"Przeliczenie wysyłki: {worksheet_calc.get('displayow', 0)} displaye | "
                                f"{worksheet_calc.get('mastercase', 0)} Master Case | {worksheet_calc.get('palet', 0)} palet"
                            )
                    with c2:
                        inc_ws_pcolor, ws_pcolor = render_existing_includable_field("Kolor papieru", "text", value=item.get("box_paper_color", ""), key=f"ws_pcolor_{idx}")
                        inc_ws_fcolor, ws_fcolor = render_existing_includable_field("Kolor filtrów", "text", value=item.get("filter_color", ""), key=f"ws_fcolor_{idx}")
                        inc_ws_dim, ws_dim = render_existing_includable_field("Wymiar", "text", value=item.get("dimensions", ""), key=f"ws_dim_{idx}")
                        inc_ws_qnet, ws_qnet = render_existing_includable_field("Ilość zamówienia netto", "number", value=item.get("qty_net", 0), key=f"ws_qnet_{idx}")
                        inc_ws_qbuffer, ws_qbuffer = render_existing_includable_field("Zapas [szt.]", "number", value=item.get("qty_buffer", 0), key=f"ws_qbuffer_{idx}")
                        st.caption(f"Ilość z zapasem: {ws_qnet + ws_qbuffer}")
                        inc_ws_qproduction, ws_qproduction = render_existing_includable_field("Ilość do produkcji", "number", value=item.get("qty_production", 0), key=f"ws_qproduction_{idx}")
                        inc_ws_qshipping, ws_qshipping = render_existing_includable_field("Ilość do wysyłki", "number", value=item.get("qty_shipping", 0), key=f"ws_qshipping_{idx}")
                    with c3:
                        inc_ws_prod_planned, ws_prod_planned = render_existing_includable_field("Ilość planowana", "number", value=item.get("production_planned", item.get("qty_production", 0)), key=f"ws_prod_planned_{idx}")
                        inc_ws_prod_made, ws_prod_made = render_existing_includable_field("Ilość wykonana", "number", value=item.get("production_made", 0), key=f"ws_prod_made_{idx}")
                        inc_ws_prod_waste, ws_prod_waste = render_existing_includable_field("Odpady", "number", value=item.get("production_waste", 0), key=f"ws_prod_waste_{idx}")
                        inc_ws_waste_reason, ws_waste_reason = render_existing_includable_field("Przyczyna odpadu", "text", value=item.get("waste_reason", ""), key=f"ws_waste_reason_{idx}")
                        inc_ws_qbox, ws_qbox = render_existing_includable_field("Ilość zamówienia box", "number", value=item.get("qty_box", 0), key=f"ws_qbox_{idx}")
                        inc_ws_qcover, ws_qcover = render_existing_includable_field("Ilość zamówienia cover", "number", value=item.get("qty_cover", 0), key=f"ws_qcover_{idx}")
                        inc_ws_qdisp, ws_qdisp = render_existing_includable_field("Ilość zamówienia display", "number", value=item.get("qty_display", 0), key=f"ws_qdisp_{idx}")
                        inc_ws_notes, ws_notes = render_existing_includable_field("Uwagi do zamówienia", "text", value=item.get("order_notes", ""), key=f"ws_notes_{idx}")
                        inc_ws_invoice, ws_invoice = render_existing_includable_field("Wystawiony dokument Faktura", "text", value=item.get("invoice_status", "Brak"), key=f"ws_invoice_{idx}")

                    drop_ws_chk = st.checkbox("Usuń tę pozycję z Karty Pracy", key=f"ws_drop_{idx}")
                    if drop_ws_chk:
                        ws_items_to_drop.append(idx)

                    worksheet_snapshot = item.get("catalog_snapshot", {})
                    worksheet_recalculated = (
                        tab9_packaging_calculation(
                            worksheet_snapshot,
                            item.get("packaging_level", "Produkt"),
                            ws_qshipping or ws_qnet,
                            item.get("packaging_calculation", {}).get("kartonow_na_palecie", 0),
                        ) if worksheet_snapshot else item.get("packaging_calculation", {})
                    )
                    updated_ws_items.append({
                        "order_channel": ws_client,
                        "product_name": ws_pname,
                        "other_criteria": ws_crit,
                        "display_type": ws_display,
                        "box_paper_color": ws_pcolor,
                        "filter_color": ws_fcolor,
                        "dimensions": ws_dim,
                        "qty_net": ws_qnet,
                        "qty_buffer": ws_qbuffer,
                        "qty_with_buffer": ws_qnet + ws_qbuffer,
                        "qty_production": ws_qproduction,
                        "qty_shipping": ws_qshipping,
                        "production_planned": ws_prod_planned,
                        "production_made": ws_prod_made,
                        "production_waste": ws_prod_waste,
                        "waste_reason": ws_waste_reason,
                        "lot_number": ws_lot,
                        "qty_box": ws_qbox,
                        "qty_cover": ws_qcover,
                        "qty_display": ws_qdisp,
                        "order_notes": ws_notes,
                        "invoice_status": ws_invoice,
                        "sku": item.get("sku", ""),
                        "ean_product": item.get("ean_product", ""),
                        "ean_display": item.get("ean_display", ""),
                        "ean_mastercase": item.get("ean_mastercase", ""),
                        "ean_selected": item.get("ean_selected", ""),
                        "packaging_level": item.get("packaging_level", "Produkt"),
                        "catalog_snapshot": item.get("catalog_snapshot", {}),
                        "packaging_calculation": worksheet_recalculated,
                        "project_info": item.get("project_info", {}),
                        "order_id": item.get("order_id", active_order_id),
                        "order_header": item.get("order_header", order_header),
                        "included_fields": {
                            "order_channel": inc_ws_client, "product_name": inc_ws_pname, "other_criteria": inc_ws_crit,
                            "display_type": inc_ws_display, "lot_number": inc_ws_lot, "box_paper_color": inc_ws_pcolor,
                            "filter_color": inc_ws_fcolor, "dimensions": inc_ws_dim, "qty_net": inc_ws_qnet,
                            "qty_buffer": inc_ws_qbuffer, "qty_production": inc_ws_qproduction, "qty_shipping": inc_ws_qshipping,
                            "production_planned": inc_ws_prod_planned, "production_made": inc_ws_prod_made,
                            "production_waste": inc_ws_prod_waste, "waste_reason": inc_ws_waste_reason,
                            "qty_box": inc_ws_qbox, "qty_cover": inc_ws_qcover, "qty_display": inc_ws_qdisp,
                            "order_notes": inc_ws_notes, "invoice_status": inc_ws_invoice,
                        },
                    })

            st.session_state["work_sheet_items"] = [item for i, item in enumerate(updated_ws_items) if i not in ws_items_to_drop]

            st.markdown("---")
            col_wact1, col_wact2, col_wact3 = st.columns(3)
            with col_wact1:
                if st.button("🗑️ Wyczyść całą Kartę Pracy"):
                    st.session_state["work_sheet_items"] = []
                    st.success("Wyczyszczono listę Karty Pracy.")
                    st.rerun()
            with col_wact2:
                if st.button("💾 Zapisz Kartę Pracy w archiwum bazy", key="save_ws_arch_btn"):
                    worksheet_errors, worksheet_warnings = tab9_validate_worksheet(
                        st.session_state["work_sheet_items"]
                    )
                    tab9_apply_approval_validation(
                        worksheet_errors, worksheet_warnings, order_header.get("document_status"),
                    )
                    ws_entry = {
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "order_id": active_order_id,
                        "order_header": order_header,
                        "order_no": ws_order_no,
                        "order_date": ws_order_date,
                        "included_fields": {"order_no": inc_ws_order_no, "order_date": inc_ws_order_date},
                        "include_production_realization": include_production_realization,
                        "production_meta": production_meta,
                        "items": st.session_state["work_sheet_items"]
                    }
                    if worksheet_errors:
                        st.error("Karta Pracy nie została zapisana. Uzupełnij: " + " | ".join(worksheet_errors))
                    else:
                        for warning in worksheet_warnings:
                            st.warning(warning)
                        db["work_sheets"].append(ws_entry)
                        save_database(db)
                        production_summary = update_order_production_summary(active_order_id, production_meta, st.session_state["work_sheet_items"])
                        register_document("Karta Pracy", {
                            "order_no": ws_order_no, "production_order_no": ws_production_order_no,
                            "machine": ws_machine, "operator": ws_operator, "shift": ws_shift,
                            "items": len(st.session_state["work_sheet_items"]), "production": production_summary,
                        })
                        update_order_snapshot("karta_pracy", {"order_no": ws_order_no, "production": production_summary, "items": st.session_state["work_sheet_items"]}, active_order_id)
                        save_order_context(active_order_id)
                        st.success("Karta Pracy została zapisana w archiwum bazy danych!")
            with col_wact3:
                worksheet_errors, worksheet_warnings = tab9_validate_worksheet(
                    st.session_state["work_sheet_items"]
                )
                tab9_apply_approval_validation(
                    worksheet_errors, worksheet_warnings, order_header.get("document_status"),
                )
                ws_meta_bundle = {
                    "order_no": ws_order_no,
                    "order_date": ws_order_date,
                    "order_id": active_order_id,
                    "priority": order_header["priority"],
                    "document_version": order_header["document_version"],
                    "included_fields": {"order_no": inc_ws_order_no, "order_date": inc_ws_order_date},
                    "include_production_realization": include_production_realization,
                    "production_meta": production_meta,
                }
                if worksheet_errors:
                    st.error("PDF Karty Pracy jest zablokowany: " + " | ".join(worksheet_errors))
                else:
                    for warning in worksheet_warnings:
                        st.warning(warning)
                    pdf_worksheet_bytes = generate_worksheet_pdf(st.session_state["work_sheet_items"], ws_meta_bundle)
                    st.download_button(
                        label="📄 Pobierz Karta Pracy PDF",
                        data=pdf_worksheet_bytes,
                        file_name=f"Karta_Pracy_{ws_order_no.replace('/', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf",
                        mime="application/pdf"
                    )

        st.markdown("---")
        st.markdown("#### 📁 Archiwum zapisanych Kart Pracy")
        if db["work_sheets"]:
            ws_to_remove = []
            for i, ws_arch in enumerate(db["work_sheets"]):
                with st.expander(f"Karta Pracy nr: {ws_arch.get('order_no', 'Brak')} | Data: {ws_arch.get('timestamp', '')} | Pozycji: {len(ws_arch.get('items', []))}", expanded=False):
                    st.text(f"Data sporządzenia: {ws_arch.get('order_date')}")
                    
                    col_dl_ws, col_load_ws, col_del_ws = st.columns(3)
                    with col_dl_ws:
                        pdf_ws_bytes = generate_worksheet_pdf(ws_arch.get('items', []), {
                            "order_id": ws_arch.get("order_id", active_order_id),
                            "order_no": ws_arch.get('order_no', ''),
                            "order_date": ws_arch.get('order_date', ''),
                            "priority": ws_arch.get("order_header", {}).get("priority", "normalny"),
                            "document_version": ws_arch.get("order_header", {}).get("document_version", "v1"),
                            "included_fields": ws_arch.get("included_fields", {}),
                            "include_production_realization": ws_arch.get("include_production_realization", True),
                            "production_meta": ws_arch.get("production_meta", {}),
                        })
                        st.download_button(
                            label="📥 Pobierz PDF",
                            data=pdf_ws_bytes,
                            file_name=f"Karta_Pracy_Arch_{ws_arch.get('order_no', '14').replace('/', '_')}_{i}.pdf",
                            mime="application/pdf",
                            key=f"dl_ws_arch_{i}"
                        )
                    with col_load_ws:
                        if st.button("📂 Wczytaj do edycji", key=f"load_ws_arch_{i}"):
                            st.session_state["work_sheet_items"] = ws_arch.get('items', [])
                            st.success("Wczytano Kartę Pracy do aktywnego formularza!")
                            st.rerun()
                    with col_del_ws:
                        if st.button("🗑️ Usuń z archiwum", key=f"del_ws_arch_{i}"):
                            ws_to_remove.append(i)
            if ws_to_remove:
                db["work_sheets"] = [item for idx, item in enumerate(db["work_sheets"]) if idx not in ws_to_remove]
                save_database(db)
                st.success("Usunięto zaznaczone Karty Pracy z archiwum.")
                st.rerun()
        else:
            if not st.session_state["work_sheet_items"]:
                st.info("Brak pozycji w Karcie Pracy oraz brak zapisanych Kart Pracy w archiwum.")


#koniec nowy kod#

# ==================== KONFIGURACJA STRONY ====================
