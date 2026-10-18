"""Odczyt i pakowanie PDF-ów należących do jednego zlecenia."""

from __future__ import annotations

from io import BytesIO
import os
from typing import Any
import zipfile

from core.document_safety import document_file_is_ready


def order_document_files(documents: list[dict[str, Any]], order_directories: str | list[str]) -> list[dict[str, Any]]:
    """Zwraca wyłącznie istniejące pliki z katalogu zlecenia albo jego archiwum."""
    files: list[dict[str, Any]] = []
    used_names: set[str] = set()
    for index, document in enumerate(documents):
        path = str(document.get("file_path", ""))
        if not document_file_is_ready(path, order_directories):
            continue
        file_name = os.path.basename(str(document.get("file_name") or path))
        stem, extension = os.path.splitext(file_name)
        candidate = file_name
        duplicate_number = 2
        while candidate.casefold() in used_names:
            candidate = f"{stem}_{duplicate_number}{extension}"
            duplicate_number += 1
        used_names.add(candidate.casefold())
        with open(path, "rb") as stream:
            files.append({"index": index, "document": document, "path": path, "file_name": candidate, "bytes": stream.read()})
    return files


def build_order_documents_zip(files: list[dict[str, Any]]) -> bytes:
    """Tworzy ZIP z unikatowymi nazwami dokumentów aktualnego zlecenia."""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for item in files:
            archive.writestr(item["file_name"], item["bytes"])
    return buffer.getvalue()
