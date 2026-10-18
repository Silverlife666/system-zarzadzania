"""Moduł 31: niezależne rozliczenie produkcji bobin."""
from datetime import date, datetime
from io import BytesIO
import json
import math


def _planning_values(entries, settings, order_name):
    """Ostatni profil użyty w zleceniu albo domyślny profil planowania."""
    matching = [row for row in entries if row.get("order") == order_name]
    source = matching[-1] if matching else settings
    return (float(source.get("bobbin_m", source.get("planning_capacity", 3000)) or 3000),
            float(source.get("roll_length_m", source.get("planning_roll_length", 6)) or 6))


def _report_pdf(order_name, target, rows, font_regular="Helvetica", font_bold="Helvetica-Bold"):
    """Buduje raport PDF bez zapisywania go na dysku serwera."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    produced = sum(float(row.get("produced", 0) or 0) for row in rows)
    waste = sum(float(row.get("waste", 0) or 0) for row in rows)
    remaining = max(float(target or 0) - produced, 0)
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=14*mm, rightMargin=14*mm, topMargin=14*mm)
    style = getSampleStyleSheet()
    title = ParagraphStyle("m31title", parent=style["Title"], fontName=font_bold, fontSize=16, textColor=colors.HexColor("#245783"))
    body = ParagraphStyle("m31body", parent=style["Normal"], fontName=font_regular, fontSize=8)
    summary = [["Docelowo", "Wykonano", "Pozostało", "Postęp", "Odpad [szt.]"], [str(int(target or 0)), str(int(produced)), str(int(remaining)), f"{(produced / target * 100) if target else 0:.1f}%", str(int(waste))]]
    details = [["Data", "Bobina", "Pracownik", "Maszyna", "Zmiana", "Pojemność [m]", "Dł. rolki [m]", "Wykonano", "Odpad", "Status"]]
    details += [[str(r.get(k, "")) for k in ("date", "bobbin_index", "employee", "machine", "shift", "bobbin_m", "roll_length_m", "produced", "waste", "completed")] for r in rows]
    story = [Paragraph("RAPORT ROZLICZENIA BOBIN", title), Paragraph(f"Zlecenie: <b>{order_name}</b>", body), Paragraph(f"Wygenerowano: {datetime.now().strftime('%Y-%m-%d %H:%M')}", body), Spacer(1, 5*mm)]
    for values in (summary, details):
        table = Table(values, repeatRows=1)
        table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#245783")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTNAME", (0, 0), (-1, 0), font_bold), ("FONTNAME", (0, 1), (-1, -1), font_regular), ("FONTSIZE", (0, 0), (-1, -1), 7), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#B8C9D9")), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        story.extend([table, Spacer(1, 5*mm)])
    document.build(story)
    return buffer.getvalue()

def render_bobbin_settlement_screen(st, deps):
    data = deps["load_json"](deps["archive_file"], {"orders": [], "entries": [], "settings": {}})
    orders, entries = data.setdefault("orders", []), data.setdefault("entries", [])
    settings = data.setdefault("settings", {})
    employees = settings.setdefault("employees", [])
    capacities = settings.setdefault("capacities", [3000, 5000])
    roll_lengths = settings.setdefault("roll_lengths", [3, 4, 5, 6, 8, 20])
    st.title("Moduł 31 - Rozliczenie produkcji bobin")
    tab_orders, tab_entries, tab_summary, tab_settings, tab_transfer = st.tabs(["Zlecenia", "Wpisy produkcyjne", "Podsumowanie", "Konfiguracja", "Import / eksport"])
    with tab_orders:
        with st.form("m31_order", clear_on_submit=True):
            name = st.text_input("Nazwa / numer zlecenia")
            target = st.number_input("Ilość docelowa [szt.]", min_value=1, step=1)
            if st.form_submit_button("Dodaj zlecenie") and name.strip():
                orders.append({"name": name.strip(), "target": target, "closed": False}); deps["save_json"](deps["archive_file"], data); st.rerun()
        if orders:
            st.dataframe(deps["pd"].DataFrame(orders), hide_index=True, width="stretch")
            st.markdown("### Zarządzanie zleceniem")
            selected_name = st.selectbox("Wybierz zlecenie", [order["name"] for order in orders], key="m31_manage_order")
            selected_order = next(order for order in orders if order["name"] == selected_name)
            linked_entries = [entry for entry in entries if entry.get("order") == selected_name]
            with st.expander("✏️ Edytuj nazwę i ilość docelową zlecenia"):
                with st.form("m31_edit_order"):
                    edit_name = st.text_input("Nazwa / numer zlecenia — edycja", value=selected_order["name"])
                    edit_target = st.number_input("Ilość docelowa [szt.] — edycja", min_value=1, value=int(selected_order.get("target", 1)), step=1)
                    if st.form_submit_button("Zapisz dane zlecenia"):
                        new_name = edit_name.strip()
                        if not new_name:
                            st.error("Podaj nazwę zlecenia.")
                        elif new_name != selected_name and any(order["name"] == new_name for order in orders):
                            st.error("Zlecenie o tej nazwie już istnieje.")
                        else:
                            selected_order.update({"name": new_name, "target": edit_target})
                            for entry in entries:
                                if entry.get("order") == selected_name:
                                    entry["order"] = new_name
                            deps["save_json"](deps["archive_file"], data); st.rerun()
            manage_a, manage_b = st.columns(2)
            with manage_a:
                action_label = "↩️ Otwórz ponownie zlecenie" if selected_order.get("closed", False) else "✅ Zamknij zlecenie"
                if st.button(action_label, width="stretch"):
                    selected_order["closed"] = not selected_order.get("closed", False)
                    deps["save_json"](deps["archive_file"], data); st.rerun()
            with manage_b:
                if linked_entries:
                    st.caption(f"Zlecenie ma {len(linked_entries)} wpisów; usuń je najpierw w „Wpisy produkcyjne”.")
                elif st.button("🗑️ Usuń puste zlecenie", width="stretch"):
                    orders.remove(selected_order)
                    deps["save_json"](deps["archive_file"], data); st.rerun()
    with tab_entries:
        choices = [o["name"] for o in orders] or ["Zlecenie niezależne"]
        if True:  # pola pozostają poza formularzem, aby szacowanie reagowało natychmiast
            a,b,c=st.columns(3)
            with a: order=st.selectbox("Zlecenie",choices); employee=st.selectbox("Pracownik",employees or [deps["current_operator"]()]); day=st.date_input("Data",date.today())
            latest_by_bobbin = {}
            for entry in entries:
                if entry.get("order") == order and entry.get("bobbin_id"):
                    latest_by_bobbin[entry["bobbin_id"]] = entry
            open_bobbins = [entry for entry in latest_by_bobbin.values() if entry.get("completed") != "TAK"]
            used_indices = [int(entry.get("bobbin_index", 0) or 0) for entry in entries if entry.get("order") == order and entry.get("date") == day.isoformat()]
            next_index = max(used_indices, default=0) + 1
            bobbin_choices = ["Nowa bobina — indeks " + str(next_index)] + [f"Wznów: bobina {entry.get('bobbin_index')} z {entry.get('date')} · {entry.get('machine')}" for entry in open_bobbins]
            bobbin_choice = st.selectbox("Numer / wznowienie bobiny", bobbin_choices, help="Nowe bobiny zaczynają numerację od 1 każdego dnia. Wznowienie zachowuje wcześniejszy indeks.")
            resumed_entry = open_bobbins[bobbin_choices.index(bobbin_choice) - 1] if bobbin_choice != bobbin_choices[0] else None
            bobbin_index = int(resumed_entry.get("bobbin_index", 0)) if resumed_entry else next_index
            bobbin_id = resumed_entry.get("bobbin_id") if resumed_entry else f"{order}|{day.isoformat()}|{bobbin_index}"
            st.caption(f"Identyfikator operacyjny: bobina {bobbin_index}" + (" — wznowienie" if resumed_entry else " — nowa"))
            active_machines = [str(row.get("Maszyna", "")).strip() for row in settings.get("machines", []) if row.get("Aktywna", True) and str(row.get("Maszyna", "")).strip()] or ["Nowa", "Stara"]
            with b: machine=st.selectbox("Maszyna",active_machines); shift=st.selectbox("Zmiana",["1","2","3"], index=["1","2","3"].index(str(settings.get("default_shift", "1"))) if str(settings.get("default_shift", "1")) in ["1","2","3"] else 0); bobbin=st.selectbox("Pojemność bobiny [m]",capacities); roll_length=st.selectbox("Długość rolki [m]",roll_lengths)
            expected_auto = int(bobbin // roll_length) if roll_length else 0
            with c: produced=st.number_input("Wykonano [szt.]",min_value=0,step=1); st.caption(f"Szacowanie automatyczne: {expected_auto} szt. ({bobbin} m ÷ {roll_length} m)"); expected=st.number_input("Szacowane [szt.] - korekta",min_value=0,value=expected_auto,step=1); completed=st.selectbox("Bobina zakończona?",["NIE","TAK"]); remaining=st.number_input("Reszta bobiny [m]",min_value=0,step=1); waste_override=st.number_input("Korekta odpadu [szt.]",min_value=0,step=1); st.caption("Odpad [m] jest liczony automatycznie: odpad [szt.] × długość rolki.")
            notes=st.text_area("Uwagi / powód korekty")
            if st.button("Dodaj wpis", key="m31_add_entry"):
                unfinished_pieces = max(expected - produced, 0)
                waste = (waste_override if waste_override else unfinished_pieces) if completed == "TAK" else 0
                calculated_remaining = unfinished_pieces * float(roll_length) if completed == "NIE" else remaining
                entries.append({"date":day.isoformat(),"order":order,"employee":employee,"machine":machine,"shift":shift,"bobbin_id":bobbin_id,"bobbin_index":bobbin_index,"bobbin_m":bobbin,"roll_length_m":roll_length,"produced":produced,"expected":expected,"waste":waste,"waste_m":waste * float(roll_length),"completed":completed,"remaining_m":calculated_remaining,"carry_m":calculated_remaining if completed == "NIE" else 0,"notes":notes}); deps["save_json"](deps["archive_file"],data); st.rerun()
        if entries:
            history = [{"Data": item.get("date", ""), "Zlecenie": item.get("order", ""), "Bobina": item.get("bobbin_index", "—"), "Pracownik": item.get("employee", ""), "Maszyna": item.get("machine", ""), "Zmiana": item.get("shift", ""), "Pojemność bobiny [m]": item.get("bobbin_m", ""), "Długość rolki [m]": item.get("roll_length_m", ""), "Wykonano [szt.]": item.get("produced", 0), "Szacowane [szt.]": item.get("expected", 0), "Odpad [szt.]": item.get("waste", 0) if item.get("completed") == "TAK" else 0, "Odpad [m]": (item.get("waste_m") or float(item.get("waste", 0) or 0) * float(item.get("roll_length_m", 0) or 0)) if item.get("completed") == "TAK" else 0, "Status": item.get("completed", ""), "Pozostało do wznowienia [m]": item.get("remaining_m") or (max(float(item.get("expected", 0) or 0) - float(item.get("produced", 0) or 0), 0) * float(item.get("roll_length_m", 0) or 0) if item.get("completed") == "NIE" else 0), "Uwagi": item.get("notes", "")} for item in entries]
            st.dataframe(deps["pd"].DataFrame(history), hide_index=True, width="stretch")
            delete_index = st.selectbox("Usuń wpis", range(len(entries)), key="m31_delete_entry", format_func=lambda i: f"{entries[i].get('date', '')} · {entries[i].get('order', '')} · bobina {entries[i].get('bobbin_index', '—')}")
            if st.button("🗑️ Usuń wybrany wpis", key="m31_delete_entry_button"):
                entries.pop(delete_index); deps["save_json"](deps["archive_file"], data); st.rerun()
            with st.expander("✏️ Edytuj wcześniejszy wpis"):
                index = st.selectbox(
                    "Wpis do edycji", range(len(entries)), key="m31_edit_entry_select",
                    format_func=lambda i: f"{entries[i].get('date', '')} · {entries[i].get('order', '')} · bobina {entries[i].get('bobbin_index', '—')} · {entries[i].get('machine', '')} · zmiana {entries[i].get('shift', '')} · {entries[i].get('employee', '')}",
                )
                item = entries[index]
                with st.form("m31_edit_entry"):
                    saved_date = item.get("date", date.today().isoformat())
                    try:
                        saved_date = date.fromisoformat(str(saved_date))
                    except ValueError:
                        saved_date = date.today()
                    edit_a, edit_b, edit_c = st.columns(3)
                    with edit_a:
                        e_date = st.date_input("Data — edycja", value=saved_date)
                    with edit_b:
                        shift_options = ["1", "2", "3"]
                        saved_shift = str(item.get("shift", "1"))
                        e_shift = st.selectbox("Zmiana — edycja", shift_options, index=shift_options.index(saved_shift) if saved_shift in shift_options else 0)
                    with edit_c:
                        e_roll_length = st.selectbox("Długość rolki [m] — edycja", roll_lengths, index=roll_lengths.index(item.get("roll_length_m")) if item.get("roll_length_m") in roll_lengths else 0)
                    e_produced=st.number_input("Wykonano [szt.] — edycja",min_value=0,value=int(item.get("produced",0))); e_expected=st.number_input("Szacowane [szt.] — edycja",min_value=0,value=int(item.get("expected",0))); e_waste=st.number_input("Odpad [szt.] — edycja",min_value=0,value=int(item.get("waste",0))); st.caption("Odpad [m] zostanie przeliczony: odpad [szt.] × długość rolki."); e_completed=st.selectbox("Bobina zakończona? — edycja",["NIE","TAK"],index=0 if item.get("completed")!="TAK" else 1); e_notes=st.text_area("Uwagi — edycja",value=item.get("notes",""))
                    if st.form_submit_button("Zapisz edycję wpisu"):
                        unfinished_after_edit = max(e_expected - e_produced, 0)
                        remaining_after_edit = unfinished_after_edit * float(e_roll_length) if e_completed == "NIE" else 0
                        final_waste = (e_waste if e_waste > 0 else unfinished_after_edit) if e_completed == "TAK" else 0
                        item.update({"date": e_date.isoformat(), "shift": e_shift, "roll_length_m": e_roll_length, "produced":e_produced,"expected":e_expected,"waste":final_waste,"waste_m":final_waste * float(e_roll_length),"completed":e_completed,"remaining_m":remaining_after_edit,"carry_m":remaining_after_edit if e_completed=="NIE" else 0,"notes":e_notes}); deps["save_json"](deps["archive_file"],data); st.rerun()
    with tab_summary:
        if entries:
            frame=deps["pd"].DataFrame(entries)
            for column, default in (("completed", "NIE"), ("remaining_m", 0), ("bobbin_m", 0), ("waste_m", None)):
                if column not in frame: frame[column] = default
            frame["waste_m"] = frame.apply(lambda row: row["waste_m"] if not deps["pd"].isna(row["waste_m"]) and row["waste_m"] else float(row.get("waste", 0) or 0) * float(row.get("roll_length_m", 0) or 0), axis=1)
            frame.loc[frame["completed"] != "TAK", "waste"] = 0
            frame.loc[frame["completed"] != "TAK", "waste_m"] = 0
            frame["waste_bobbins"] = frame.apply(lambda row: row["waste_m"] / row["bobbin_m"] if row["bobbin_m"] else 0, axis=1)
            st.markdown("### Statystyki produkcji")
            metrics = [("Ilość zmian", len(frame)), ("Ilość wykonanych sztuk", int(frame.produced.sum())), ("Odpad w sztukach", int(frame.waste.sum())), ("Średnia ilość wykonanych sztuk na zmianę", round(frame.produced.mean(), 1)), ("Ilość wykonanych bobin", int((frame.completed == "TAK").sum())), ("Ilość osób", frame.employee.nunique()), ("Odpad w metrach", round(frame.waste_m.sum(), 1)), ("Odpad w bobinach", round(frame.waste_bobbins.sum(), 2))]
            for group in (metrics[:4], metrics[4:]):
                columns = st.columns(4)
                for column, (label, value) in zip(columns, group): column.metric(label, value)
            target_map = {o["name"]: float(o.get("target", 0) or 0) for o in orders}
            waste_rate = float(settings.get("waste_rate_pct", 1.0) or 0)
            rows = []
            for order_name, group in frame.groupby("order"):
                produced = float(group["produced"].sum())
                target = target_map.get(order_name, 0)
                remaining = max(target - produced, 0)
                capacity, length = _planning_values(entries, settings, order_name)
                effective_pieces = (capacity / length) * (1 - waste_rate / 100) if length else 0
                forecast = math.ceil(remaining / effective_pieces) if effective_pieces and remaining else 0
                progress = (produced / target) if target else 0
                st.markdown(f"#### {order_name}")
                st.progress(min(progress, 1.0), text=f"Postęp: {int(produced)} z {int(target)} szt. · pozostało {int(remaining)} szt.")
                st.caption(f"Prognoza: {forecast} bobin do wykonania ({capacity:g} m / {length:g} m, planowany odpad {waste_rate:g}%).")
                order_metrics = [("Zmiany", len(group)), ("Wykonano [szt.]", int(group["produced"].sum())), ("Odpad [szt.]", int(group["waste"].sum())), ("Średnio / zmianę", round(group["produced"].mean(), 1)), ("Bobiny zakończone", int((group["completed"] == "TAK").sum())), ("Osoby", group["employee"].nunique()), ("Odpad [m]", round(group["waste_m"].sum(), 1)), ("Odpad [bob.]", round(group["waste_bobbins"].sum(), 2))]
                for metric_group in (order_metrics[:4], order_metrics[4:]):
                    for metric_column, (label, value) in zip(st.columns(4), metric_group):
                        metric_column.metric(label, value)
                rows.append({"Zlecenie": order_name, "Docelowo": int(target), "Wykonano": int(produced), "Pozostało [szt.]": int(remaining), "Postęp": f"{progress * 100:.1f}%", "Bobiny do wykonania (z odpadem)": forecast, "Odpad planowany": f"{waste_rate:g}%", "Odpad [szt.]": int(group["waste"].sum()), "Odpad [m]": round(group["waste_m"].sum(), 1), "Zmiany": len(group), "Bobiny zakończone": int((group["completed"] == "TAK").sum())})
            summary = deps["pd"].DataFrame(rows)
            st.markdown("### Pełne zestawienie według zlecenia")
            st.dataframe(summary, hide_index=True, width="stretch")
            report_order = st.selectbox("Zlecenie do raportu PDF", list(frame["order"].unique()), key="m31_report_order")
            selected_order = next((o for o in orders if o["name"] == report_order), {"target": 0})
            report_rows = [row for row in entries if row.get("order") == report_order]
            st.download_button("📄 Pobierz raport PDF zlecenia", _report_pdf(report_order, selected_order.get("target", 0), report_rows, deps.get("font_regular", "Helvetica"), deps.get("font_bold", "Helvetica-Bold")), f"Rozliczenie_bobin_{report_order.replace('/', '_')}.pdf", "application/pdf", width="stretch")
    with tab_settings:
        st.markdown("### Konfigurator produkcji")
        staff_tab, machine_tab, material_tab, rules_tab = st.tabs(["Pracownicy", "Maszyny", "Bobiny i rolki", "Reguły"])
        with staff_tab:
            staff_rows = deps["pd"].DataFrame(settings.get("staff_records") or [{"Pracownik": name, "Aktywny": True, "Stawka/h": 0} for name in employees])
            staff_edit = st.data_editor(staff_rows, num_rows="dynamic", hide_index=True, width="stretch", key="m31_staff_config")
        with machine_tab:
            machine_rows = deps["pd"].DataFrame(settings.get("machines") or [{"Maszyna": "Nowa", "Typ": "Nowa", "Aktywna": True}, {"Maszyna": "Stara", "Typ": "Stara", "Aktywna": True}])
            machine_edit = st.data_editor(machine_rows, num_rows="dynamic", hide_index=True, width="stretch", key="m31_machine_config")
        with material_tab:
            material_rows = deps["pd"].DataFrame(settings.get("bobbin_profiles") or [{"Pojemność bobiny [m]": cap, "Długość rolki [m]": length, "Aktywny": True} for cap in capacities for length in roll_lengths])
            material_edit = st.data_editor(material_rows, num_rows="dynamic", hide_index=True, width="stretch", key="m31_material_config")
        with rules_tab:
            default_shift = st.selectbox("Domyślna zmiana", ["1", "2", "3"], index=["1", "2", "3"].index(str(settings.get("default_shift", "1"))))
            automatic_waste = st.checkbox("Automatycznie licz odpad po zakończeniu bobiny", value=settings.get("automatic_waste", True))
            waste_rate = st.number_input("Planowany odpad do prognozy bobin [%]", min_value=0.0, max_value=100.0, value=float(settings.get("waste_rate_pct", 1.0)), step=0.1)
            planning_capacity = st.selectbox("Domyślna pojemność do planowania [m]", capacities, index=capacities.index(settings.get("planning_capacity", capacities[0])) if settings.get("planning_capacity", capacities[0]) in capacities else 0)
            planning_length = st.selectbox("Domyślna długość rolki do planowania [m]", roll_lengths, index=roll_lengths.index(settings.get("planning_roll_length", roll_lengths[0])) if settings.get("planning_roll_length", roll_lengths[0]) in roll_lengths else 0)
            st.caption("Gdy bobina nie jest zakończona, reszta jest przenoszona. Prognoza bobin uwzględnia podany procent odpadu.")
        if st.button("💾 Zapisz konfigurację produkcji", type="primary", width="stretch"):
            settings["staff_records"] = staff_edit.to_dict("records"); settings["employees"] = [str(row["Pracownik"]).strip() for row in settings["staff_records"] if str(row.get("Pracownik", "")).strip() and row.get("Aktywny", True)]
            settings["machines"] = machine_edit.to_dict("records"); settings["bobbin_profiles"] = material_edit.to_dict("records"); settings["capacities"] = sorted({int(row["Pojemność bobiny [m]"]) for row in settings["bobbin_profiles"] if row.get("Aktywny", True)}) or [3000]; settings["roll_lengths"] = sorted({float(row["Długość rolki [m]"]) for row in settings["bobbin_profiles"] if row.get("Aktywny", True)}) or [6]; settings["default_shift"] = default_shift; settings["automatic_waste"] = automatic_waste; settings["waste_rate_pct"] = waste_rate; settings["planning_capacity"] = planning_capacity; settings["planning_roll_length"] = planning_length
            deps["save_json"](deps["archive_file"], data); st.success("Zapisano konfigurację produkcji.")
    with tab_transfer:
        st.markdown("### Kopia danych modułu")
        payload = {"format": "system-produkcji/bobbin-settlement", "version": 1, "exported_at": datetime.now().isoformat(timespec="seconds"), "data": data}
        st.download_button("⬇️ Eksportuj dane JSON", json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"), "rozliczenie_bobin.json", "application/json", width="stretch")
        imported = st.file_uploader("Importuj kopię JSON", type=["json"], key="m31_import")
        if imported:
            try:
                imported_data = json.loads(imported.getvalue().decode("utf-8")).get("data", {})
                if not isinstance(imported_data, dict) or not isinstance(imported_data.get("orders", []), list) or not isinstance(imported_data.get("entries", []), list):
                    raise ValueError("Plik nie zawiera danych modułu 31.")
                st.success(f"Poprawny plik: {len(imported_data['orders'])} zleceń i {len(imported_data['entries'])} wpisów.")
                if st.button("Wczytaj plik i zastąp bieżące dane", type="primary"):
                    data.clear(); data.update(imported_data); data.setdefault("settings", {}); deps["save_json"](deps["archive_file"], data); st.rerun()
            except Exception as exc:
                st.error(f"Nie można odczytać pliku JSON: {exc}")
