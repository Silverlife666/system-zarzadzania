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


def assignments_for_week(plan, start_date, shift=None):
    week = {item.isoformat() for item in week_dates(start_date)}
    rows = [row for row in normalize_production_plan(plan)["assignments"] if row.get("date") in week]
    if shift:
        rows = [row for row in rows if row.get("shift") == shift]
    return sorted(rows, key=lambda item: (item.get("date", ""), item.get("shift", ""), item.get("employee", "")))
