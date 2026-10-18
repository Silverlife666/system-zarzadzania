"""Trwały zapis PDF-ów i ich wersjonowanie, niezależne od Streamlit."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
from typing import Any

from core.document_safety import is_path_in_directory


def safe_document_file_name(file_name: str) -> str:
    """Usuwa znaki niebezpieczne w nazwie pliku przekazanej przez moduł."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(file_name or "dokument.pdf"))


def store_pdf_version(
    documents: list[dict[str, Any]],
    document_type: str,
    pdf_bytes: bytes,
    file_name: str,
    order_directory: str,
    *,
    metadata: dict[str, Any] | None = None,
    operator: str = "",
    timestamp: str,
) -> tuple[list[dict[str, Any]], str, bool]:
    """Zapisuje PDF oraz aktualizuje jego wpis.

    Zwraca ``(documents, file_path, changed)``. Identyczna treść nie tworzy
    nowej wersji, natomiast zmieniona treść archiwizuje poprzednią wersję i
    wymaga ponownego zatwierdzenia.
    """
    safe_name = safe_document_file_name(file_name)
    os.makedirs(order_directory, exist_ok=True)
    file_path = os.path.join(order_directory, safe_name)
    content_hash = hashlib.sha256(pdf_bytes).hexdigest()
    matching = [
        item for item in documents
        if item.get("type") == document_type
        and (item.get("document_key") == safe_name or item.get("file_name") == safe_name)
    ]
    existing = matching[0] if matching else None
    if existing is None:
        unnamed = [item for item in documents if item.get("type") == document_type and not item.get("file_name")]
        existing = unnamed[0] if len(unnamed) == 1 else None

    if existing and existing.get("content_hash") == content_hash and os.path.isfile(existing.get("file_path", "")):
        existing["metadata"] = {**existing.get("metadata", {}), **(metadata or {})}
        existing["updated_at"] = timestamp
        return documents, str(existing["file_path"]), False

    if existing:
        previous_version = int(existing.get("version", 1))
        previous_path = str(existing.get("file_path", ""))
        historical_path = ""
        if previous_path and os.path.isfile(previous_path):
            versions_directory = os.path.join(order_directory, "wersje")
            os.makedirs(versions_directory, exist_ok=True)
            stem, extension = os.path.splitext(safe_name)
            historical_path = os.path.join(versions_directory, f"{stem}_v{previous_version}{extension}")
            if os.path.exists(historical_path):
                historical_path = os.path.join(versions_directory, f"{stem}_v{previous_version}_{timestamp.replace(':', '').replace('-', '')}{extension}")
            shutil.copy2(previous_path, historical_path)
        with open(file_path, "wb") as stream:
            stream.write(pdf_bytes)
        previous_status = existing.get("status", "wygenerowany")
        previous_approver = existing.get("approved_by", "")
        existing.update({
            "version": previous_version + 1,
            "document_key": safe_name,
            "file_name": safe_name,
            "file_path": file_path,
            "content_hash": content_hash,
            "metadata": {**existing.get("metadata", {}), **(metadata or {})},
            "status": "wygenerowany",
            "approved_by": "",
            "updated_at": timestamp,
        })
        existing.setdefault("history", []).append({
            "at": timestamp, "action": "zaktualizowano wersję PDF", "by": operator,
            "status": "wygenerowany", "previous_version": previous_version,
            "previous_file_path": historical_path, "previous_status": previous_status,
            "previous_approved_by": previous_approver,
            "requires_reapproval": previous_status in {"zatwierdzony", "zatwierdzone", "wysłany", "wysłane"},
        })
    else:
        with open(file_path, "wb") as stream:
            stream.write(pdf_bytes)
        documents.append({
            "type": document_type, "created_at": timestamp, "status": "wygenerowany",
            "file_name": safe_name, "document_key": safe_name, "file_path": file_path,
            "content_hash": content_hash, "approved_by": operator, "metadata": metadata or {}, "version": 1,
            "history": [{"at": timestamp, "action": "utworzono PDF", "by": operator, "status": "wygenerowany"}],
        })
    return documents, file_path, True


def clear_pdf_version_history(documents: list[dict[str, Any]], order_directories: list[str]) -> int:
    """Usuwa poprzednie wersje PDF i czyści ich historię, zostawiając bieżące pliki."""
    safe_directories = [os.path.abspath(directory) for directory in order_directories]
    removed_files = 0
    for document in documents:
        for event in document.get("history", []):
            previous_path = str(event.get("previous_file_path", ""))
            if previous_path and any(is_path_in_directory(previous_path, directory) for directory in safe_directories):
                if os.path.isfile(previous_path):
                    os.remove(previous_path)
                    removed_files += 1
        document["history"] = []
        document["version"] = 1
    # Usuwa również osierocone pliki wcześniejszych wersji utworzone przez
    # aplikację, ale nigdy nie dotyka bieżących PDF-ów katalogu zlecenia.
    for directory in safe_directories:
        versions_directory = os.path.join(directory, "wersje")
        if is_path_in_directory(versions_directory, directory) and os.path.isdir(versions_directory):
            removed_files += sum(1 for _, _, names in os.walk(versions_directory) for name in names)
            shutil.rmtree(versions_directory)
    return removed_files
