"""Trwałe, proste reguły planowania pracy na dwóch zmianach."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4


SHIFT_OPTIONS = ("Zmiana 1 · 06:00–14:00", "Zmiana 2 · 14:00–22:00")


def empty_production_plan():
    return {"employees": [], "assignments": []}


def normalize_production_plan(data):
    data = data if isinstance(data, dict) else {}
    employees = [str(name).strip() for name in data.get("employees", []) if str(name).strip()]
    assignments = [dict(item) for item in data.get("assignments", []) if isinstance(item, dict)]
    return {"employees": list(dict.fromkeys(employees)), "assignments": assignments}


def week_dates(start_date):
    """Zwraca poniedziałek–niedzielę dla daty wskazanej przez użytkownika."""
    if isinstance(start_date, str):
        start_date = date.fromisoformat(start_date)
    monday = start_date - timedelta(days=start_date.weekday())
    return [monday + timedelta(days=offset) for offset in range(7)]


def add_employee(plan, employee):
    result = normalize_production_plan(plan)
    employee = str(employee or "").strip()
    if not employee:
        raise ValueError("Wpisz imię i nazwisko pracownika.")
    if employee.casefold() not in {name.casefold() for name in result["employees"]}:
        result["employees"].append(employee)
    return result


def add_assignment(plan, assignment):
    result = normalize_production_plan(plan)
    row = dict(assignment or {})
    for field, label in (("date", "datę"), ("shift", "zmianę"), ("employee", "pracownika"), ("task", "zadanie")):
        if not str(row.get(field, "")).strip():
            raise ValueError(f"Uzupełnij {label}.")
    if row["shift"] not in SHIFT_OPTIONS:
        raise ValueError("Wybierz prawidłową zmianę.")
    if str(row["employee"]).strip() not in result["employees"]:
        raise ValueError("Najpierw dodaj pracownika do listy.")
    row["id"] = row.get("id") or uuid4().hex
    row["date"] = str(row["date"])
    row["employee"] = str(row["employee"]).strip()
    row["task"] = str(row["task"]).strip()
    row["notes"] = str(row.get("notes", "")).strip()
    result["assignments"].append(row)
    return result


def remove_assignment(plan, assignment_id):
    result = normalize_production_plan(plan)
    result["assignments"] = [row for row in result["assignments"] if row.get("id") != assignment_id]
    return result


def update_assignment(plan, assignment_id, assignment):
    """Aktualizuje istniejące przypisanie bez zmiany jego stabilnego identyfikatora."""
    result = normalize_production_plan(plan)
    existing = next((row for row in result["assignments"] if row.get("id") == assignment_id), None)
    if existing is None:
        raise ValueError("Nie znaleziono wybranego przypisania.")
    updated = dict(existing)
    updated.update(dict(assignment or {}))
    result["assignments"] = [row for row in result["assignments"] if row.get("id") != assignment_id]
    try:
        return add_assignment(result, updated)
    except ValueError:
        result["assignments"].append(existing)
        raise


def export_plan_for_offline_html(plan):
    """Zwraca format JSON obsługiwany przez samodzielny Plan_produkcji_offline.html."""
    normalized = normalize_production_plan(plan)
    shift_map = {SHIFT_OPTIONS[0]: "1", SHIFT_OPTIONS[1]: "2"}
    return {
        "format": "plan-produkcji-html-v1",
        "employees": normalized["employees"],
        "assignments": [
            {
                "id": str(row.get("id") or uuid4().hex),
                "date": str(row.get("date") or ""),
                "shift": shift_map.get(row.get("shift"), str(row.get("shift") or "")),
                "employee": str(row.get("employee") or ""),
                "task": str(row.get("task") or ""),
                "order": str(row.get("order_id") or ""),
                "notes": str(row.get("notes") or ""),
            }
            for row in normalized["assignments"]
        ],
    }


def import_plan_from_offline_html(plan, payload):
    """Scala dane z pliku JSON HTML z planem systemowym; identyczne ID są aktualizowane."""
    if not isinstance(payload, dict):
        raise ValueError("Plik importu ma nieprawidłowy format.")
    raw_employees = payload.get("employees", [])
    raw_assignments = payload.get("assignments", [])
    if not isinstance(raw_employees, list) or not isinstance(raw_assignments, list):
        raise ValueError("Plik importu nie zawiera listy pracowników lub przypisań.")

    result = normalize_production_plan(plan)
    for employee in raw_employees:
        name = str(employee or "").strip()
        if name and name.casefold() not in {item.casefold() for item in result["employees"]}:
            result["employees"].append(name)

    shift_map = {"1": SHIFT_OPTIONS[0], "2": SHIFT_OPTIONS[1]}
    imported = 0
    for raw in raw_assignments:
        if not isinstance(raw, dict):
            continue
        employee = str(raw.get("employee") or "").strip()
        task = str(raw.get("task") or "").strip()
        assignment_id = str(raw.get("id") or uuid4().hex)
        if not employee or not task:
            continue
        if employee.casefold() not in {item.casefold() for item in result["employees"]}:
            result["employees"].append(employee)
        result["assignments"] = [item for item in result["assignments"] if item.get("id") != assignment_id]
        result = add_assignment(result, {
            "id": assignment_id,
            "date": str(raw.get("date") or ""),
            "shift": shift_map.get(str(raw.get("shift") or ""), str(raw.get("shift") or "")),
            "employee": employee,
            "task": task,
            "notes": str(raw.get("notes") or ""),
            "order_id": str(raw.get("order", raw.get("order_id", "")) or ""),
        })
        imported += 1
    return result, imported


def assignments_for_week(plan, start_date, shift=None):
    week = {item.isoformat() for item in week_dates(start_date)}
    rows = [row for row in normalize_production_plan(plan)["assignments"] if row.get("date") in week]
    if shift:
        rows = [row for row in rows if row.get("shift") == shift]
    return sorted(rows, key=lambda item: (item.get("date", ""), item.get("shift", ""), item.get("employee", "")))
