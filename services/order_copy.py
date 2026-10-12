"""Tworzenie bezpiecznej kopii i reprintu zlecenia."""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any


def create_order_copy_record(
    source_order_id: str,
    source_record: dict[str, Any],
    new_order_id: str,
    created_at: str,
    created_by: str = "",
    is_reprint: bool = False,
) -> dict[str, Any]:
    """Zwraca nową roboczą kopię bez współdzielenia PDF-ów z oryginałem."""
    copied = deepcopy(source_record)
    copied["created_at"] = created_at
    copied["updated_at"] = created_at
    copied["source_order_id"] = source_order_id
    copied["order_status"] = "robocze"
    copied["email_history"] = []
    copied.setdefault("order_history", []).append({
        "at": created_at,
        "action": f"utworzono {'reprint' if is_reprint else 'kopię'} z {source_order_id}",
        "by": created_by,
        "to": "robocze",
    })
    header = copied.get("order_header", {})
    if header:
        header["order_id"] = new_order_id
        header["order_number"] = f"{header.get('order_number') or source_order_id}-R" if is_reprint else new_order_id
        header["document_status"] = "robocze"
        if is_reprint:
            old_version = str(header.get("document_version", "v1"))
            match = re.search(r"(\d+)", old_version)
            header["document_version"] = f"v{int(match.group(1)) + 1 if match else 2}"
            header["priority"] = "reprint"
            header["change_reason"] = f"Reprint utworzony na podstawie {source_order_id}"
        copied["order_header"] = header
    copied["source_documents"] = [
        {
            "type": item.get("type", "Dokument"),
            "version": item.get("version", 1),
            "source_file_name": item.get("file_name", ""),
            "source_order_id": source_order_id,
        }
        for item in copied.get("documents", [])
    ]
    copied["documents"] = []
    return copied


def copy_order_context(
    contexts: dict[str, Any], source_order_id: str, new_order_id: str, copied_record: dict[str, Any], created_at: str
) -> dict[str, Any]:
    """Kopiuje kontekst modułów, podmieniając referencje na nowe zlecenie."""
    result = deepcopy(contexts)
    if source_order_id not in result:
        return result
    # Dane kontekstu są JSON-serializowalne — kontrolowana zamiana aktualizuje
    # referencje order_id we wszystkich sekcjach nowej kopii.
    import json

    copied_context = json.loads(json.dumps(result[source_order_id], ensure_ascii=False).replace(source_order_id, new_order_id))
    context_data = copied_context.setdefault("data", {})
    if copied_record.get("order_header"):
        context_data["tab9_order_header"] = copied_record["order_header"]
    copied_context["updated_at"] = created_at
    result[new_order_id] = copied_context
    return result
