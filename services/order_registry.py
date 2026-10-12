"""Czyste operacje na wpisach Centrum zlecenia."""

from __future__ import annotations

from typing import Any


def generate_short_order_id(date_code: str, existing_ids, token_factory) -> str:
    """Tworzy krótki identyfikator EMBURN-YYMMDD-XXXX, odporny na kolizje."""
    existing_ids = set(existing_ids or ())
    for _ in range(100):
        candidate = f"EMBURN-{date_code}-{str(token_factory(2)).upper()}"
        if candidate not in existing_ids:
            return candidate
    raise RuntimeError("Nie udało się utworzyć unikalnego identyfikatora zlecenia.")


def new_order_record(created_at: str, created_by: str = "") -> dict[str, Any]:
    return {
        "created_at": created_at,
        "updated_at": created_at,
        "order_name": "",
        "order_status": "robocze",
        "documents": [],
        "order_history": [{"at": created_at, "action": "utworzono nowe zlecenie", "by": created_by, "to": "robocze"}],
    }


def register_document_record(
    documents: list[dict[str, Any]],
    document_type: str,
    timestamp: str,
    *,
    metadata: dict[str, Any] | None = None,
    status: str = "wygenerowany",
    file_name: str = "",
    file_path: str = "",
    approved_by: str = "",
    operator: str = "",
) -> list[dict[str, Any]]:
    """Tworzy albo aktualizuje jeden wpis, bez dopisywania duplikatu."""
    matching = [item for item in documents if item.get("type") == document_type]
    existing = next((item for item in matching if file_name and item.get("file_name") == file_name), None)
    if existing is None and not file_name:
        unnamed = [item for item in matching if not item.get("file_name")]
        existing = unnamed[0] if unnamed else (matching[-1] if matching else None)
    if existing:
        previous_status = existing.get("status", "wygenerowany")
        existing["version"] = int(existing.get("version", 1)) + 1
        existing["status"] = status or previous_status
        if file_name:
            existing["file_name"] = file_name
        if file_path:
            existing["file_path"] = file_path
        if approved_by:
            existing["approved_by"] = approved_by
        existing["metadata"] = {**existing.get("metadata", {}), **(metadata or {})}
        existing.setdefault("history", []).append({
            "at": timestamp, "action": "zaktualizowano wpis dokumentu",
            "by": approved_by or operator, "status": existing["status"],
        })
    else:
        entry = {
            "type": document_type, "created_at": timestamp, "status": status,
            "file_name": file_name, "file_path": file_path,
            "approved_by": approved_by or operator, "metadata": metadata or {}, "version": 1,
        }
        entry["history"] = [{"at": timestamp, "action": "utworzono", "by": entry["approved_by"], "status": status}]
        documents.append(entry)
    return documents


def derive_order_lifecycle(
    current_status: str, has_documents: bool, missing_requirements: list[str], email_sent: bool
) -> tuple[str, str]:
    """Wyznacza status bez dostępu do Streamlit ani plików danych."""
    if current_status == "zamknięte":
        return "zamknięte", "status zamknięty pozostawiono bez automatycznej zmiany"
    if email_sent:
        return "wysłane", "potwierdzona wysyłka e-mail"
    if not missing_requirements:
        return "gotowe do wysyłki", "komplet wymaganych dokumentów"
    if has_documents:
        return "w produkcji", "oczekuje na komplet: " + ", ".join(missing_requirements)
    return "robocze", "brak wygenerowanych dokumentów"
