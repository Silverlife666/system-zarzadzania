"""Reguły danych formularza TDS, E-Order i Karty Pracy.

Funkcje nie zależą od Streamlit ani od trwałego magazynu danych, dzięki czemu
widok modułu 9 może korzystać z nich bez kopiowania reguł walidacyjnych.
"""

from __future__ import annotations

import base64
import hashlib
from datetime import datetime
from typing import Any

from services.order_documents import (
    as_positive_int,
    packaging_calculation,
    selected_ean,
    validate_base_data,
)

ADVISORY_WARNING_PREFIX = "Informacyjnie: "


def validate_packaging_relations(snapshot: dict[str, Any], qty_display_pieces: Any,
                                 qty_carton: Any, qty_cartons_palette: Any,
                                 qty_displays_palette: Any) -> list[str]:
    if not snapshot:
        return []
    calculation = packaging_calculation(snapshot, "Produkt", 1, as_positive_int(qty_cartons_palette))
    warnings = []
    if as_positive_int(qty_display_pieces) != calculation["produktow_w_displayu"]:
        warnings.append(
            f"{ADVISORY_WARNING_PREFIX}Relacja Produkt → Display: wpisano {qty_display_pieces}, "
            f"a kartoteka wskazuje {calculation['produktow_w_displayu']} produktów w displayu."
        )
    if as_positive_int(qty_carton) != calculation["produktow_w_mastercase"]:
        warnings.append(
            f"{ADVISORY_WARNING_PREFIX}Relacja Display → Master Case: wpisano {qty_carton}, "
            f"a kartoteka wskazuje {calculation['produktow_w_mastercase']} produktów w Master Case."
        )
    expected_displays = calculation["displayow_w_mastercase"] * as_positive_int(qty_cartons_palette)
    if as_positive_int(qty_cartons_palette) and as_positive_int(qty_displays_palette) != expected_displays:
        warnings.append(
            f"{ADVISORY_WARNING_PREFIX}Relacja Master Case → paleta: wpisano {qty_displays_palette} displayów, "
            f"a kartoteka wskazuje {expected_displays} displayów na palecie."
        )
    return warnings


def validate_eorder(items: list[dict[str, Any]], recipient: dict[str, Any], delivery_date: Any) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    if not str(recipient.get("company", "")).strip() or not str(recipient.get("email", "")).strip():
        errors.append("Uzupełnij firmę i e-mail odbiorcy.")
    if not str(delivery_date or "").strip():
        errors.append("Uzupełnij planowaną datę dostawy.")
    if not items:
        errors.append("E-Order nie zawiera żadnej pozycji.")
    for index, item in enumerate(items, start=1):
        errors.extend(validate_base_data(item.get("product_name"), item.get("order_channel"), item.get("qty_net"), delivery_date, False, False, f"E-Order → pozycja {index}", "Ilość netto"))
        snapshot, level = item.get("catalog_snapshot", {}), item.get("packaging_level", "Produkt")
        expected = selected_ean(snapshot, level)
        if expected and str(item.get("ean_selected", "")) != expected:
            warnings.append(f"Pozycja {index}: EAN nie odpowiada wybranemu poziomowi „{level}”.")
        elif snapshot and not expected:
            warnings.append(f"Pozycja {index}: w kartotece brakuje EAN dla poziomu „{level}”.")
        warnings.extend(f"Pozycja {index}: {message}" for message in validate_packaging_relations(snapshot, item.get("qty_display_pieces", 0), item.get("qty_carton", 0), item.get("qty_cartons_palette", 0), item.get("qty_displays_palette", 0)))
    return errors, warnings


def validate_worksheet(items: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    if not items:
        errors.append("Karta Pracy nie zawiera żadnej pozycji.")
    for index, item in enumerate(items, start=1):
        errors.extend(validate_base_data(item.get("product_name"), "", item.get("qty_production") or item.get("qty_net"), "", False, False, f"Karta Pracy → pozycja {index}", "Ilość do produkcji / netto"))
        snapshot, level = item.get("catalog_snapshot", {}), item.get("packaging_level", "Produkt")
        expected = selected_ean(snapshot, level)
        if expected and str(item.get("ean_selected", "")) != expected:
            warnings.append(f"Pozycja {index}: EAN nie odpowiada poziomowi „{level}”.")
        elif snapshot and not expected:
            warnings.append(f"Pozycja {index}: w kartotece brakuje EAN dla poziomu „{level}”.")
    return errors, warnings


def requires_strict_approval(*statuses: Any) -> bool:
    return any(str(status or "").strip().lower() in {"zatwierdzone", "zaakceptowano", "approved", "accepted"} for status in statuses)


def apply_approval_validation(errors: list[str], warnings: list[str], *statuses: Any) -> list[str]:
    if requires_strict_approval(*statuses):
        errors.extend(
            f"Zatwierdzenie zablokowane: {warning}"
            for warning in warnings
            if ADVISORY_WARNING_PREFIX not in str(warning)
        )
    return errors


def project_file_payload(uploaded_file: Any, existing_payload: dict[str, Any] | None = None,
                         *, uploaded_by: str = "", uploaded_at: str | None = None) -> dict[str, Any]:
    """Zwraca wersjonowany, możliwy do serializacji załącznik projektu."""
    if uploaded_file is None:
        return existing_payload or {}
    file_bytes = uploaded_file.getvalue()
    checksum = hashlib.sha256(file_bytes).hexdigest()
    existing_payload = existing_payload or {}
    if existing_payload.get("sha256") == checksum:
        return existing_payload
    versions = list(existing_payload.get("versions", []))
    if existing_payload.get("b64"):
        versions.append({key: existing_payload.get(key, default) for key, default in (
            ("name", "projekt"), ("mime", "application/octet-stream"), ("size", 0),
            ("sha256", ""), ("uploaded_at", ""), ("uploaded_by", ""), ("b64", ""),
        )})
    return {
        "name": uploaded_file.name, "mime": uploaded_file.type or "application/octet-stream",
        "size": len(file_bytes), "sha256": checksum,
        "uploaded_at": uploaded_at or datetime.now().isoformat(timespec="seconds"),
        "uploaded_by": uploaded_by, "b64": base64.b64encode(file_bytes).decode("ascii"),
        "versions": versions,
    }


def project_pdf_fields(project_info: dict[str, Any] | None) -> dict[str, str]:
    project_info = project_info or {}
    attachment = project_info.get("attachment", {}) if isinstance(project_info, dict) else {}
    return {
        "Numer projektu": project_info.get("project_number", "") or "—",
        "Wersja projektu": project_info.get("project_version", "") or "—",
        "Link do pliku źródłowego": project_info.get("source_link", "") or "—",
        "Załącznik projektu": attachment.get("name", "brak"),
        "Rozmiar załącznika": f"{attachment.get('size', 0) / 1024 / 1024:.2f} MB" if attachment else "—",
        "SHA-256": attachment.get("sha256", "—") or "—",
        "Wgrano": attachment.get("uploaded_at", "—") or "—",
        "Wgrał": attachment.get("uploaded_by", "—") or "—",
    }
