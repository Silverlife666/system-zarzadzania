"""Moduł 17: centralna biblioteka surowców i materiałów."""


MATERIAL_COLUMNS = [
    "Kod", "Materiał", "Kategoria", "Jednostka", "Parametry", "Dostawca",
    "Cena netto", "Stan minimalny", "Czas dostawy (dni)", "Status", "Uwagi",
]


def render_material_library_screen(st, deps):
    pd = deps["pd"]
    datetime = deps["datetime"]
    load_database = deps["load_database"]
    save_database = deps["save_database"]

    st.title("📚 Biblioteka materiałów")
    st.caption("Centralna kartoteka surowców do przyszłego zapotrzebowania materiałowego, PPWR i magazynu.")
    database = load_database()
    records = database.setdefault("materials_library", [])
    if not isinstance(records, list):
        records = []
        database["materials_library"] = records

    with st.expander("➕ Dodaj materiał", expanded=True):
        with st.form("add_material_form", clear_on_submit=True):
            first, second, third = st.columns(3)
            with first:
                code = st.text_input("Kod materiału", placeholder="np. PAP-ROZ-14-44")
                name = st.text_input("Nazwa materiału", placeholder="np. Papier Różowy 14 gsm")
                category = st.selectbox("Kategoria", ["Papier", "Filtr", "Tektura", "Folia", "Klej", "Paleta", "Inne"])
            with second:
                unit = st.selectbox("Jednostka", ["m", "kg", "szt.", "arkusz", "bobina", "rolka"])
                parameters = st.text_input("Parametry", placeholder="np. 14 gsm, 44 mm, rdzeń 130 mm")
                supplier = st.text_input("Dostawca")
            with third:
                price = st.number_input("Cena netto", min_value=0.0, step=0.01)
                minimum = st.number_input("Stan minimalny", min_value=0.0, step=1.0)
                lead_time = st.number_input("Czas dostawy [dni]", min_value=0, step=1)
            notes = st.text_input("Uwagi")
            submitted = st.form_submit_button("➕ Dodaj do biblioteki", type="primary")
        if submitted:
            if not name.strip():
                st.error("Podaj nazwę materiału.")
            elif any(str(item.get("Kod", "")).casefold() == code.strip().casefold() for item in records if code.strip()):
                st.error("Materiał o takim kodzie już istnieje.")
            else:
                records.append({
                    "Kod": code.strip(), "Materiał": name.strip(), "Kategoria": category, "Jednostka": unit,
                    "Parametry": parameters.strip(), "Dostawca": supplier.strip(), "Cena netto": price,
                    "Stan minimalny": minimum, "Czas dostawy (dni)": lead_time, "Status": "Aktywny",
                    "Uwagi": notes.strip(), "Utworzono": datetime.now().isoformat(timespec="seconds"),
                })
                save_database(database)
                st.success("Dodano materiał do biblioteki.")
                st.rerun()

    frame = pd.DataFrame(records).reindex(columns=MATERIAL_COLUMNS, fill_value="")
    search_col, category_col, status_col = st.columns(3)
    with search_col:
        phrase = st.text_input("Szukaj", placeholder="kod, materiał lub dostawca")
    with category_col:
        categories = ["Wszystkie"] + sorted({str(value) for value in frame["Kategoria"].dropna() if str(value)})
        category_filter = st.selectbox("Kategoria", categories)
    with status_col:
        status_filter = st.selectbox("Status", ["Wszystkie", "Aktywny", "Wycofany"])
    filtered = frame.copy()
    if phrase.strip():
        mask = filtered[["Kod", "Materiał", "Dostawca", "Parametry"]].fillna("").astype(str).apply(
            lambda column: column.str.contains(phrase.strip(), case=False, regex=False)
        ).any(axis=1)
        filtered = filtered[mask]
    if category_filter != "Wszystkie":
        filtered = filtered[filtered["Kategoria"] == category_filter]
    if status_filter != "Wszystkie":
        filtered = filtered[filtered["Status"] == status_filter]

    st.markdown("### Materiały")
    edited = st.data_editor(filtered, num_rows="dynamic", width="stretch", hide_index=True, key="materials_library_editor")
    save_col, delete_col = st.columns(2)
    with save_col:
        if st.button("💾 Zapisz widoczną listę", type="primary"):
            # Przy aktywnych filtrach zachowujemy ukryte rekordy i podmieniamy tylko widoczne.
            visible_keys = {(str(row.get("Kod", "")), str(row.get("Materiał", ""))) for row in filtered.to_dict(orient="records")}
            retained = [item for item in records if (str(item.get("Kod", "")), str(item.get("Materiał", ""))) not in visible_keys]
            database["materials_library"] = retained + edited.fillna("").to_dict(orient="records")
            save_database(database)
            st.success("Biblioteka materiałów została zapisana.")
            st.rerun()
    with delete_col:
        existing_names = [f"{item.get('Kod', '—')} · {item.get('Materiał', '')}" for item in records]
        to_delete = st.multiselect("Usuń materiały", existing_names)
        confirm_delete = st.checkbox("Potwierdzam usunięcie wybranych materiałów")
        if st.button("🗑️ Usuń wybrane", disabled=not (to_delete and confirm_delete)):
            database["materials_library"] = [
                item for item, label in zip(records, existing_names) if label not in to_delete
            ]
            save_database(database)
            st.success("Usunięto wybrane materiały.")
            st.rerun()
