"""Moduł 24: ewidencja i rozliczenie wykonanej pracy."""

from datetime import date

from services.work_settlement_documents import build_work_settlement_pdf


ACTIVITIES = ("Stosy ucięte", "Rolki nakręcone", "Pakowanie", "Kontrola jakości", "Inne")
UNITS = ("szt.", "rolki", "kg", "palety", "godz.")
SHIFTS = ("I zmiana", "II zmiana", "III zmiana", "—")


def render_work_settlement_screen(st, deps):
    order_id = deps["get_current_order_id"]()
    state_key = "work_settlement_entries"
    entries = st.session_state.setdefault(state_key, [])
    changeover_state_key = "machine_changeover_entries"
    changeovers = st.session_state.setdefault(changeover_state_key, [])
    known_paper_names = sorted({str(item.get("paper_name", "")).strip() for item in entries if str(item.get("paper_name", "")).strip()})
    st.header("Rozliczenie pracy")
    st.caption("Rejestruj wykonane czynności dla aktywnego zlecenia, np. ucięte stosy i nakręcone rolki.")

    with st.form("work_settlement_add_entry", clear_on_submit=True):
        left, middle, right = st.columns(3)
        with left:
            entry_date = st.date_input("Data", value=date.today())
            employee = st.text_input("Pracownik", value=deps["current_operator"]())
        with middle:
            activity = st.selectbox("Czynność", ACTIVITIES)
            quantity = st.number_input("Ilość wykonana", min_value=0.0, step=1.0, format="%.2f")
            waste_quantity = st.number_input("Ilość odpadu", min_value=0.0, step=1.0, format="%.2f")
        with right:
            unit = st.selectbox("Jednostka", UNITS)
            shift = st.selectbox("Zmiana", SHIFTS)
            duration_minutes = st.number_input("Czas pracy (min)", min_value=0, step=5)
        paper_type, paper_name = st.columns(2)
        with paper_type:
            selected_paper_type = st.selectbox("Rodzaj papieru", ("Papier powlekany", "Papier niepowlekany", "Kraft", "Makulaturowy", "Tektura", "Inny"))
        with paper_name:
            paper_choice = st.selectbox("Nazwa papieru", ["➕ Dodaj nową nazwę"] + known_paper_names)
            new_paper_name = st.text_input("Nowa nazwa papieru", placeholder="np. GC1 300 g/m²") if paper_choice == "➕ Dodaj nową nazwę" else ""
        notes = st.text_area("Uwagi", placeholder="Opcjonalnie: maszyna, numer rolki, przyczyna przestoju…")
        submitted = st.form_submit_button("➕ Dodaj wpis", width="stretch")
    if submitted:
        if not employee.strip():
            st.error("Podaj pracownika.")
        elif quantity <= 0 and waste_quantity <= 0:
            st.error("Podaj ilość wykonaną lub ilość odpadu większą od zera.")
        elif not (new_paper_name if paper_choice == "➕ Dodaj nową nazwę" else paper_choice).strip():
            st.error("Wybierz lub wpisz nazwę papieru.")
        else:
            resolved_paper_name = (new_paper_name if paper_choice == "➕ Dodaj nową nazwę" else paper_choice).strip()
            entries.append({"date": entry_date.isoformat(), "employee": employee.strip(), "activity": activity,
                            "quantity": quantity, "waste_quantity": waste_quantity, "unit": unit,
                            "shift": shift, "duration_minutes": duration_minutes, "paper_type": selected_paper_type,
                            "paper_name": resolved_paper_name, "notes": notes.strip()})
            deps["save_order_context"]()
            st.success("Dodano wpis do rozliczenia pracy.")

    st.subheader("Zarejestrowane czynności")
    if entries:
        table_data = [{"Data": item["date"], "Pracownik": item["employee"], "Czynność": item["activity"],
                       "Rodzaj papieru": item.get("paper_type", "Nieokreślony"), "Nazwa papieru": item.get("paper_name", "Nieokreślony"),
                       "Ilość wykonana": item["quantity"], "Ilość odpadu": item.get("waste_quantity", 0),
                       "Jednostka": item["unit"], "Zmiana": item["shift"],
                       "Czas (min)": item.get("duration_minutes", 0), "Uwagi": item["notes"]}
                      for item in entries]
        st.dataframe(deps["pd"].DataFrame(table_data), width="stretch", hide_index=True)
        with st.expander("✏️ Edytuj wpis pracy"):
            entry_to_edit = st.selectbox("Wpis do edycji", range(len(entries)), key="work_entry_to_edit", format_func=lambda index: f"{entries[index]['date']} · {entries[index]['activity']} · {entries[index].get('paper_name', 'Nieokreślony papier')}")
            edited_entry = entries[entry_to_edit]
            with st.form("work_settlement_edit_entry"):
                left, middle, right = st.columns(3)
                with left:
                    edit_date = st.date_input("Data wpisu", value=date.fromisoformat(edited_entry["date"]))
                    edit_employee = st.text_input("Pracownik wpisu", value=edited_entry["employee"])
                    edit_activity = st.selectbox("Czynność wpisu", ACTIVITIES, index=ACTIVITIES.index(edited_entry["activity"]) if edited_entry["activity"] in ACTIVITIES else len(ACTIVITIES) - 1)
                with middle:
                    edit_quantity = st.number_input("Ilość wykonana — edycja", min_value=0.0, value=float(edited_entry["quantity"]), step=1.0, format="%.2f")
                    edit_waste = st.number_input("Ilość odpadu — edycja", min_value=0.0, value=float(edited_entry.get("waste_quantity", 0)), step=1.0, format="%.2f")
                    edit_paper_name = st.text_input("Nazwa papieru — edycja", value=edited_entry.get("paper_name", ""))
                with right:
                    edit_unit = st.selectbox("Jednostka — edycja", UNITS, index=UNITS.index(edited_entry["unit"]) if edited_entry["unit"] in UNITS else 0)
                    edit_shift = st.selectbox("Zmiana — edycja", SHIFTS, index=SHIFTS.index(edited_entry["shift"]) if edited_entry["shift"] in SHIFTS else len(SHIFTS) - 1)
                    edit_duration = st.number_input("Czas pracy (min) — edycja", min_value=0, value=int(edited_entry.get("duration_minutes", 0)), step=5)
                    edit_paper_type = st.selectbox("Rodzaj papieru — edycja", ("Papier powlekany", "Papier niepowlekany", "Kraft", "Makulaturowy", "Tektura", "Inny"), index=("Papier powlekany", "Papier niepowlekany", "Kraft", "Makulaturowy", "Tektura", "Inny").index(edited_entry.get("paper_type", "Inny")) if edited_entry.get("paper_type") in ("Papier powlekany", "Papier niepowlekany", "Kraft", "Makulaturowy", "Tektura", "Inny") else 5)
                edit_notes = st.text_area("Uwagi — edycja", value=edited_entry.get("notes", ""))
                save_edited_entry = st.form_submit_button("💾 Zapisz zmiany we wpisie", width="stretch")
            if save_edited_entry:
                if not edit_employee.strip() or not edit_paper_name.strip():
                    st.error("Podaj pracownika oraz nazwę papieru.")
                elif edit_quantity <= 0 and edit_waste <= 0:
                    st.error("Podaj ilość wykonaną lub ilość odpadu większą od zera.")
                else:
                    entries[entry_to_edit] = {"date": edit_date.isoformat(), "employee": edit_employee.strip(), "activity": edit_activity,
                                              "quantity": edit_quantity, "waste_quantity": edit_waste, "unit": edit_unit, "shift": edit_shift,
                                              "duration_minutes": edit_duration, "paper_type": edit_paper_type, "paper_name": edit_paper_name.strip(), "notes": edit_notes.strip()}
                    deps["save_order_context"]()
                    st.success("Zapisano zmiany we wpisie.")
                    st.rerun()
        row_to_delete = st.selectbox("Usuń wpis", range(len(entries)), format_func=lambda index: f"{entries[index]['date']} · {entries[index]['activity']} · wykonano: {entries[index]['quantity']:g} {entries[index]['unit']}")
        if st.button("🗑️ Usuń wybrany wpis"):
            entries.pop(row_to_delete)
            deps["save_order_context"]()
            st.rerun()
    else:
        st.info("Brak wpisów dla tego zlecenia.")

    st.divider()
    st.subheader("Przezbrojenie maszyny")
    st.caption("Zarejestruj przygotowanie maszyny lub stanowiska do realizacji kolejnego zlecenia.")
    with st.form("machine_changeover_add_entry", clear_on_submit=True):
        left, middle, right = st.columns(3)
        with left:
            changeover_date = st.date_input("Data przezbrojenia", value=date.today())
            changeover_employee = st.text_input("Pracownik przezbrojenia", value=deps["current_operator"]())
        with middle:
            machine = st.text_input("Maszyna / stanowisko", placeholder="np. Bobst 102")
            next_order = st.text_input("Następne zlecenie", placeholder="Numer zlecenia")
        with right:
            changeover_duration = st.number_input("Czas przezbrojenia (min)", min_value=0, step=5)
        changeover_notes = st.text_area("Uwagi do przezbrojenia", placeholder="np. wymiana wykrojnika, ustawienie kolorów, test jakości")
        changeover_submitted = st.form_submit_button("➕ Dodaj przezbrojenie", width="stretch")
    if changeover_submitted:
        if not changeover_employee.strip() or not machine.strip() or not next_order.strip():
            st.error("Podaj pracownika, maszynę oraz następne zlecenie.")
        elif changeover_duration <= 0:
            st.error("Czas przezbrojenia musi być większy od zera.")
        else:
            changeovers.append({"date": changeover_date.isoformat(), "employee": changeover_employee.strip(),
                                "machine": machine.strip(), "next_order": next_order.strip(),
                                "duration_minutes": changeover_duration, "notes": changeover_notes.strip()})
            deps["save_order_context"]()
            st.success("Dodano przezbrojenie maszyny.")

    if changeovers:
        st.dataframe(deps["pd"].DataFrame([{
            "Data": item["date"], "Pracownik": item["employee"], "Maszyna / stanowisko": item["machine"],
            "Następne zlecenie": item["next_order"], "Czas (min)": item["duration_minutes"], "Uwagi": item["notes"],
        } for item in changeovers]), width="stretch", hide_index=True)
        with st.expander("✏️ Edytuj przezbrojenie"):
            changeover_to_edit = st.selectbox("Przezbrojenie do edycji", range(len(changeovers)), key="changeover_to_edit", format_func=lambda index: f"{changeovers[index]['date']} · {changeovers[index]['machine']} → {changeovers[index]['next_order']}")
            edited_changeover = changeovers[changeover_to_edit]
            with st.form("machine_changeover_edit_entry"):
                edit_changeover_date = st.date_input("Data przezbrojenia — edycja", value=date.fromisoformat(edited_changeover["date"]))
                first, second, third = st.columns(3)
                with first:
                    edit_changeover_employee = st.text_input("Pracownik przezbrojenia — edycja", value=edited_changeover["employee"])
                with second:
                    edit_machine = st.text_input("Maszyna / stanowisko — edycja", value=edited_changeover["machine"])
                with third:
                    edit_next_order = st.text_input("Następne zlecenie — edycja", value=edited_changeover["next_order"])
                    edit_changeover_duration = st.number_input("Czas przezbrojenia (min) — edycja", min_value=0, value=int(edited_changeover.get("duration_minutes", 0)), step=5)
                edit_changeover_notes = st.text_area("Uwagi do przezbrojenia — edycja", value=edited_changeover.get("notes", ""))
                save_edited_changeover = st.form_submit_button("💾 Zapisz zmiany przezbrojenia", width="stretch")
            if save_edited_changeover:
                if not edit_changeover_employee.strip() or not edit_machine.strip() or not edit_next_order.strip() or edit_changeover_duration <= 0:
                    st.error("Uzupełnij pracownika, maszynę, następne zlecenie i czas większy od zera.")
                else:
                    changeovers[changeover_to_edit] = {"date": edit_changeover_date.isoformat(), "employee": edit_changeover_employee.strip(), "machine": edit_machine.strip(), "next_order": edit_next_order.strip(), "duration_minutes": edit_changeover_duration, "notes": edit_changeover_notes.strip()}
                    deps["save_order_context"]()
                    st.success("Zapisano zmiany przezbrojenia.")
                    st.rerun()
        changeover_to_delete = st.selectbox("Usuń przezbrojenie", range(len(changeovers)), format_func=lambda index: f"{changeovers[index]['date']} · {changeovers[index]['machine']} → {changeovers[index]['next_order']}")
        if st.button("🗑️ Usuń wybrane przezbrojenie"):
            changeovers.pop(changeover_to_delete)
            deps["save_order_context"]()
            st.rerun()

    pdf_bytes = build_work_settlement_pdf(entries, order_id, deps["current_operator"](), deps["font_regular"], deps["font_bold"], changeovers)
    left, right = st.columns(2)
    with left:
        st.download_button("📄 Pobierz raport PDF", pdf_bytes, "raport_rozliczenia_pracy.pdf", "application/pdf", width="stretch")
    with right:
        if st.button("💾 Zapisz raport w Centrum zlecenia", width="stretch"):
            deps["store_order_pdf"]("Raport rozliczenia pracy", pdf_bytes, "raport_rozliczenia_pracy.pdf", {"entries": len(entries), "changeovers": len(changeovers)}, order_id=order_id)
            st.success("Raport PDF zapisano w Centrum zlecenia.")
