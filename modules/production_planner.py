"""Widok Streamlit planowania pracy na dwie zmiany."""

from __future__ import annotations

from datetime import date, timedelta
import json
from typing import Any, Callable

import pandas as pd
import streamlit as st

from services.production_planning import (
    SHIFT_OPTIONS, add_assignment, add_employee, assignments_for_week,
    export_plan_for_offline_html, import_plan_from_offline_html, normalize_production_plan,
    remove_assignment, update_assignment, week_dates,
)
from services.production_schedule_pdf import build_production_schedule_pdf


def render_production_planner(plan_data: dict[str, Any], *, save_plan: Callable[[dict[str, Any]], None], active_order_id: str,
                              font_regular: str = "Helvetica", font_bold: str = "Helvetica-Bold") -> None:
    """Renderuje planer i zapisuje tylko przez funkcję przekazaną z app.py."""
    plan = normalize_production_plan(plan_data)
    st.title("🏭 13. Planowanie pracy na produkcji")
    st.caption("Planuj zadania dla dwóch zmian. Przykład: Poniedziałek → Judyta → Kręcenie Rolls Ritual.")

    with st.expander("👥 Pracownicy", expanded=True):
        employee_col, employee_action_col = st.columns([4, 1])
        with employee_col:
            employee_name = st.text_input("Imię i nazwisko pracownika", key="production_planner_employee")
        with employee_action_col:
            st.write("")
            if st.button("➕ Dodaj pracownika", key="production_planner_add_employee"):
                try:
                    save_plan(add_employee(plan, employee_name))
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))
        if plan["employees"]:
            st.caption("Lista: " + ", ".join(plan["employees"]))
        else:
            st.info("Dodaj pracownika, aby przypisać mu zadanie.")

    with st.expander("↔️ Wymiana planu z wersją HTML", expanded=False):
        st.caption("Ten sam plik JSON działa w samodzielnej stronie Plan_produkcji_offline.html.")
        offline_payload = json.dumps(export_plan_for_offline_html(plan), ensure_ascii=False, indent=2).encode("utf-8")
        st.download_button(
            "⬇️ Eksportuj plan do HTML (JSON)", offline_payload,
            file_name="plan_produkcji_offline.json", mime="application/json",
            key="production_planner_export_offline_html",
        )
        import_file = st.file_uploader(
            "Importuj plan z HTML (JSON)", type=["json"],
            key="production_planner_import_offline_html",
        )
        if import_file is not None and st.button("Wczytaj dane z pliku HTML", key="production_planner_import_offline_html_button"):
            try:
                imported_plan, imported_count = import_plan_from_offline_html(
                    plan, json.loads(import_file.getvalue().decode("utf-8")),
                )
                save_plan(imported_plan)
                st.success(f"Wczytano lub zaktualizowano {imported_count} przypisań.")
                st.rerun()
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
                st.error(f"Nie można wczytać pliku: {error}")

    default_monday = date.today() - timedelta(days=date.today().weekday())
    week_start = st.date_input("Tydzień planowania", value=default_monday, key="production_planner_week")
    week = week_dates(week_start)
    day_options = {day.strftime("%A %d.%m.%Y"): day.isoformat() for day in week}
    polish_days = ["Poniedziałek", "Wtorek", "Środa", "Czwartek", "Piątek", "Sobota", "Niedziela"]
    day_options = {f"{polish_days[index]} · {day.strftime('%d.%m.%Y')}": day.isoformat() for index, day in enumerate(week)}

    with st.expander("➕ Przypisz zadanie", expanded=True):
        if plan["employees"]:
            with st.form("production_planner_assignment_form"):
                day_label = st.selectbox("Dzień", list(day_options))
                form_col1, form_col2 = st.columns(2)
                with form_col1:
                    employee = st.selectbox("Pracownik", plan["employees"])
                    shift = st.selectbox("Zmiana", list(SHIFT_OPTIONS))
                with form_col2:
                    task = st.text_input("Zadanie", placeholder="np. Kręcenie Rolls Ritual")
                    notes = st.text_input("Uwagi (opcjonalnie)")
                assign_to_current_order = st.checkbox("Powiąż z aktywnym zleceniem", value=True)
                submitted = st.form_submit_button("Zapisz zadanie", type="primary")
            if submitted:
                try:
                    save_plan(add_assignment(plan, {
                        "date": day_options[day_label], "shift": shift, "employee": employee, "task": task,
                        "notes": notes, "order_id": active_order_id if assign_to_current_order else "",
                    }))
                    st.success("Zadanie zapisano w planie produkcji.")
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))
        else:
            st.caption("Najpierw dodaj co najmniej jednego pracownika.")

    st.markdown("### Plan tygodnia")
    tab_one, tab_two = st.tabs([SHIFT_OPTIONS[0], SHIFT_OPTIONS[1]])
    for tab, shift in ((tab_one, SHIFT_OPTIONS[0]), (tab_two, SHIFT_OPTIONS[1])):
        with tab:
            rows = assignments_for_week(plan, week_start, shift)
            if rows:
                view = pd.DataFrame(rows).rename(columns={
                    "date": "Data", "employee": "Pracownik", "task": "Zadanie", "notes": "Uwagi", "order_id": "Zlecenie",
                })
                st.dataframe(view[["Data", "Pracownik", "Zadanie", "Uwagi", "Zlecenie"]], width="stretch", hide_index=True)
            else:
                st.caption("Brak przypisanych zadań na tę zmianę w wybranym tygodniu.")

    all_rows = assignments_for_week(plan, week_start)

    st.markdown("### Eksport harmonogramu do PDF")
    pdf_scope = st.segmented_control(
        "Zakres PDF", ["Jeden dzień", "Cały tydzień"], default="Jeden dzień",
        key="production_planner_pdf_scope",
    )
    if pdf_scope == "Jeden dzień":
        selected_day_label = st.selectbox("Dzień do PDF", list(day_options), key="production_planner_pdf_day")
        selected_day = day_options[selected_day_label]
        pdf_rows = [row for row in all_rows if row.get("date") == selected_day]
        pdf_title = "HARMONOGRAM PRODUKCJI - DZIEŃ"
        pdf_period = selected_day_label
        pdf_file_name = f"harmonogram_{selected_day}.pdf"
    else:
        pdf_rows = all_rows
        pdf_title = "HARMONOGRAM PRODUKCJI - TYDZIEŃ"
        pdf_period = f"{week[0].strftime('%d.%m.%Y')}–{week[-1].strftime('%d.%m.%Y')}"
        pdf_file_name = f"harmonogram_tydzien_{week[0].isoformat()}.pdf"
    schedule_pdf = build_production_schedule_pdf(
        pdf_rows, title=pdf_title, period_label=pdf_period,
        font_regular=font_regular, font_bold=font_bold,
    )
    st.download_button(
        "📄 Pobierz harmonogram PDF", schedule_pdf, file_name=pdf_file_name,
        mime="application/pdf", key="production_planner_pdf_download",
    )

    if all_rows:
        with st.expander("✏️ Edytuj przypisanie", expanded=False):
            choices = {
                f"{row['date']} · {row['shift']} · {row['employee']} — {row['task']}": row
                for row in all_rows
            }
            selected_label = st.selectbox("Wybierz zadanie do edycji", list(choices), key="production_planner_edit_assignment")
            selected_row = choices[selected_label]
            with st.form(f"production_planner_edit_form_{selected_row['id']}"):
                edit_day_label = st.selectbox(
                    "Dzień", list(day_options),
                    index=list(day_options.values()).index(selected_row["date"]),
                    key=f"production_planner_edit_day_{selected_row['id']}",
                )
                edit_col1, edit_col2 = st.columns(2)
                with edit_col1:
                    edit_employee = st.selectbox(
                        "Pracownik", plan["employees"],
                        index=plan["employees"].index(selected_row["employee"]),
                        key=f"production_planner_edit_employee_{selected_row['id']}",
                    )
                    edit_shift = st.selectbox(
                        "Zmiana", list(SHIFT_OPTIONS),
                        index=list(SHIFT_OPTIONS).index(selected_row["shift"]),
                        key=f"production_planner_edit_shift_{selected_row['id']}",
                    )
                with edit_col2:
                    edit_task = st.text_input("Zadanie", value=selected_row["task"], key=f"production_planner_edit_task_{selected_row['id']}")
                    edit_notes = st.text_input("Uwagi", value=selected_row.get("notes", ""), key=f"production_planner_edit_notes_{selected_row['id']}")
                    edit_order_id = st.text_input("Zlecenie", value=selected_row.get("order_id", ""), key=f"production_planner_edit_order_{selected_row['id']}")
                submitted_edit = st.form_submit_button("Zapisz zmiany", type="primary")
            if submitted_edit:
                try:
                    save_plan(update_assignment(plan, selected_row["id"], {
                        "date": day_options[edit_day_label], "shift": edit_shift, "employee": edit_employee,
                        "task": edit_task, "notes": edit_notes, "order_id": edit_order_id,
                    }))
                    st.success("Zaktualizowano przypisanie.")
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))

        with st.expander("🗑️ Usuń przypisanie", expanded=False):
            choices = {f"{row['date']} · {row['shift']} · {row['employee']} — {row['task']}": row["id"] for row in all_rows}
            selected = st.selectbox("Wybierz zadanie", list(choices), key="production_planner_remove_assignment")
            if st.button("Usuń wybrane zadanie", key="production_planner_remove_button"):
                save_plan(remove_assignment(plan, choices[selected]))
                st.rerun()
