"""Niezależne, trwałe archiwum rozliczeń pracy dla modułu 24."""

from datetime import date

from services.work_settlement_documents import build_work_settlement_pdf


ACTIVITIES = ("Stosy ucięte", "Rolki nakręcone", "Pakowanie", "Kontrola jakości", "Inne")
UNITS = ("szt.", "rolki", "kg", "palety", "godz.")
SHIFTS = ("I zmiana", "II zmiana", "III zmiana", "—")
PAPER_TYPES = ("Papier powlekany", "Papier niepowlekany", "Kraft", "Makulaturowy", "Tektura", "Inny")


def _save(deps, archive):
    deps["save_json"](deps["archive_file"], archive)


def render_work_settlement_archive_screen(st, deps):
    active_order_id = deps["get_current_order_id"]()
    archive = deps["load_json"](deps["archive_file"], {"entries": [], "changeovers": []})
    if not isinstance(archive, dict):
        archive = {"entries": [], "changeovers": []}
    entries = archive.setdefault("entries", [])
    changeovers = archive.setdefault("changeovers", [])
    if not archive.get("legacy_context_migrated"):
        for legacy_order_id, context in deps["load_order_contexts"]().items():
            decoded = {key: deps["deserialize_context"](value) for key, value in (context.get("data", {}) if isinstance(context, dict) else {}).items()}
            for item in decoded.get("work_settlement_entries", []) or []:
                if isinstance(item, dict):
                    entries.append({**item, "order_id": item.get("order_id") or legacy_order_id})
            for item in decoded.get("machine_changeover_entries", []) or []:
                if isinstance(item, dict):
                    changeovers.append({**item, "order_id": item.get("order_id") or legacy_order_id})
        archive["legacy_context_migrated"] = True
        _save(deps, archive)
    known_papers = sorted({str(item.get("paper_name", "")).strip() for item in entries if str(item.get("paper_name", "")).strip()})

    st.header("Archiwum rozliczenia pracy")
    st.caption("Dane są zapisywane niezależnie od zleceń. Powiązanie ze zleceniem jest opcjonalne.")
    with st.form("archive_add_work", clear_on_submit=True):
        a, b, c = st.columns(3)
        with a:
            entry_date = st.date_input("Data", date.today())
            employee = st.text_input("Pracownik", value=deps["current_operator"]())
            link_order = st.checkbox("Przypisz do aktywnego zlecenia")
        with b:
            activity = st.selectbox("Czynność", ACTIVITIES)
            quantity = st.number_input("Ilość wykonana", min_value=0.0, step=1.0)
            waste = st.number_input("Ilość odpadu", min_value=0.0, step=1.0)
        with c:
            unit = st.selectbox("Jednostka", UNITS)
            shift = st.selectbox("Zmiana", SHIFTS)
            duration = st.number_input("Czas pracy (min)", min_value=0, step=5)
        d, e = st.columns(2)
        with d:
            paper_type = st.selectbox("Rodzaj papieru", PAPER_TYPES)
        with e:
            choice = st.selectbox("Nazwa papieru", ["➕ Dodaj nową nazwę"] + known_papers)
            new_name = st.text_input("Nowa nazwa papieru") if choice == "➕ Dodaj nową nazwę" else ""
        notes = st.text_area("Uwagi")
        add_work = st.form_submit_button("➕ Dodaj wpis", width="stretch")
    if add_work:
        paper_name = (new_name if choice == "➕ Dodaj nową nazwę" else choice).strip()
        if not employee.strip() or not paper_name or (quantity <= 0 and waste <= 0):
            st.error("Podaj pracownika, nazwę papieru oraz ilość wykonaną lub odpadu.")
        else:
            entries.append({"date": entry_date.isoformat(), "employee": employee.strip(), "activity": activity, "quantity": quantity, "waste_quantity": waste, "unit": unit, "shift": shift, "duration_minutes": duration, "paper_type": paper_type, "paper_name": paper_name, "order_id": active_order_id if link_order else "", "notes": notes.strip()})
            _save(deps, archive); st.success("Wpis zapisano w niezależnym archiwum.")

    st.subheader("Wpisy archiwum")
    if entries:
        frame = [{"Data": x.get("date", ""), "Pracownik": x.get("employee", ""), "Czynność": x.get("activity", ""), "Papier": x.get("paper_name", "Nieokreślony"), "Rodzaj": x.get("paper_type", "Nieokreślony"), "Wykonano": x.get("quantity", 0), "Odpad": x.get("waste_quantity", 0), "Jednostka": x.get("unit", ""), "Czas (min)": x.get("duration_minutes", 0), "Zlecenie (opcjonalne)": x.get("order_id", "") or "—", "Uwagi": x.get("notes", "")} for x in entries]
        st.dataframe(deps["pd"].DataFrame(frame), width="stretch", hide_index=True)
        with st.expander("✏️ Edytuj wpis"):
            index = st.selectbox("Wpis do edycji", range(len(entries)), key="archive_work_edit", format_func=lambda i: f"{entries[i].get('date', '')} · {entries[i].get('activity', '')} · {entries[i].get('paper_name', 'Nieokreślony')}")
            item = entries[index]
            with st.form("archive_edit_work"):
                edit_date = st.date_input("Data wpisu", value=date.fromisoformat(item.get("date", date.today().isoformat())))
                edit_employee = st.text_input("Pracownik wpisu", value=item.get("employee", ""))
                edit_activity = st.selectbox("Czynność — edycja", ACTIVITIES, index=ACTIVITIES.index(item.get("activity")) if item.get("activity") in ACTIVITIES else len(ACTIVITIES) - 1)
                edit_quantity = st.number_input("Ilość wykonana — edycja", min_value=0.0, value=float(item.get("quantity", 0)), step=1.0)
                edit_waste = st.number_input("Ilość odpadu — edycja", min_value=0.0, value=float(item.get("waste_quantity", 0)), step=1.0)
                edit_name = st.text_input("Nazwa papieru — edycja", value=item.get("paper_name", ""))
                edit_type = st.selectbox("Rodzaj papieru — edycja", PAPER_TYPES, index=PAPER_TYPES.index(item.get("paper_type")) if item.get("paper_type") in PAPER_TYPES else len(PAPER_TYPES) - 1)
                edit_unit = st.selectbox("Jednostka — edycja", UNITS, index=UNITS.index(item.get("unit")) if item.get("unit") in UNITS else 0)
                edit_shift = st.selectbox("Zmiana — edycja", SHIFTS, index=SHIFTS.index(item.get("shift")) if item.get("shift") in SHIFTS else len(SHIFTS) - 1)
                edit_duration = st.number_input("Czas pracy (min) — edycja", min_value=0, value=int(item.get("duration_minutes", 0)), step=5)
                edit_link = st.checkbox("Przypisz do aktywnego zlecenia — edycja", value=bool(item.get("order_id")))
                edit_notes = st.text_area("Uwagi — edycja", value=item.get("notes", ""))
                save_edit = st.form_submit_button("💾 Zapisz zmiany")
            if save_edit:
                if not edit_employee.strip() or not edit_name.strip() or (edit_quantity <= 0 and edit_waste <= 0):
                    st.error("Uzupełnij pracownika, nazwę papieru oraz ilość.")
                else:
                    item.update({"date": edit_date.isoformat(), "employee": edit_employee.strip(), "activity": edit_activity, "quantity": edit_quantity, "waste_quantity": edit_waste, "paper_name": edit_name.strip(), "paper_type": edit_type, "unit": edit_unit, "shift": edit_shift, "duration_minutes": edit_duration, "order_id": active_order_id if edit_link else "", "notes": edit_notes.strip()})
                    _save(deps, archive); st.rerun()
        delete = st.selectbox("Usuń wpis", range(len(entries)), key="archive_work_delete", format_func=lambda i: f"{entries[i].get('date', '')} · {entries[i].get('activity', '')}")
        if st.button("🗑️ Usuń wybrany wpis"):
            entries.pop(delete); _save(deps, archive); st.rerun()
    else:
        st.info("Archiwum nie zawiera jeszcze wpisów.")

    st.divider(); st.subheader("Przezbrojenie maszyny")
    with st.form("archive_add_changeover", clear_on_submit=True):
        a, b, c = st.columns(3)
        with a:
            co_date = st.date_input("Data przezbrojenia", date.today())
            co_employee = st.text_input("Pracownik przezbrojenia", value=deps["current_operator"]())
            co_link = st.checkbox("Przypisz przezbrojenie do aktywnego zlecenia")
        with b:
            machine = st.text_input("Maszyna / stanowisko")
            next_order = st.text_input("Następne zlecenie")
        with c:
            co_minutes = st.number_input("Czas przezbrojenia (min)", min_value=0, step=5)
        co_notes = st.text_area("Uwagi do przezbrojenia")
        add_changeover = st.form_submit_button("➕ Dodaj przezbrojenie", width="stretch")
    if add_changeover:
        if not co_employee.strip() or not machine.strip() or not next_order.strip() or co_minutes <= 0:
            st.error("Uzupełnij pracownika, maszynę, następne zlecenie i czas.")
        else:
            changeovers.append({"date": co_date.isoformat(), "employee": co_employee.strip(), "machine": machine.strip(), "next_order": next_order.strip(), "duration_minutes": co_minutes, "order_id": active_order_id if co_link else "", "notes": co_notes.strip()})
            _save(deps, archive); st.success("Przezbrojenie zapisano w niezależnym archiwum.")
    if changeovers:
        st.dataframe(deps["pd"].DataFrame([{"Data": x.get("date", ""), "Pracownik": x.get("employee", ""), "Maszyna": x.get("machine", ""), "Następne zlecenie": x.get("next_order", ""), "Czas (min)": x.get("duration_minutes", 0), "Zlecenie (opcjonalne)": x.get("order_id", "") or "—", "Uwagi": x.get("notes", "")} for x in changeovers]), width="stretch", hide_index=True)

    archive_pdf = build_work_settlement_pdf(entries, "Archiwum niezależne", deps["current_operator"](), deps["font_regular"], deps["font_bold"], changeovers)
    linked_entries = [item for item in entries if item.get("order_id") == active_order_id]
    linked_changeovers = [item for item in changeovers if item.get("order_id") == active_order_id]
    order_pdf = build_work_settlement_pdf(linked_entries, active_order_id, deps["current_operator"](), deps["font_regular"], deps["font_bold"], linked_changeovers)
    left, middle, right = st.columns(3)
    with left:
        st.download_button("📄 Pobierz pełny raport archiwum", archive_pdf, "raport_rozliczenia_pracy.pdf", "application/pdf", width="stretch")
    with middle:
        st.download_button("📄 Pobierz raport bieżącego zlecenia", order_pdf, f"rozliczenie_{active_order_id}.pdf", "application/pdf", width="stretch", disabled=not (linked_entries or linked_changeovers))
    with right:
        if st.button("💾 Opcjonalnie: zapisz raport bieżącego zlecenia w Centrum", width="stretch", disabled=not (linked_entries or linked_changeovers)):
            deps["store_order_pdf"]("Raport rozliczenia pracy", order_pdf, f"rozliczenie_{active_order_id}.pdf", {"entries": len(linked_entries), "changeovers": len(linked_changeovers), "source": "niezależne archiwum"}, order_id=active_order_id)
            st.success("Raport zapisano w Centrum aktywnego zlecenia.")
