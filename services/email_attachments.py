"""Bezpieczne pobieranie załączników dokumentów do modułu E-mail."""

from __future__ import annotations

import os
from io import BytesIO

from core.document_safety import document_file_is_ready


def load_order_pdf_attachments(documents, order_directory):
    """Wczytuje wyłącznie istniejące PDF-y należące do danego zlecenia."""
    attachments = []
    for document in documents or []:
        path = str((document or {}).get("file_path", ""))
        if not document_file_is_ready(path, order_directory):
            continue
        with open(path, "rb") as stream:
            payload = BytesIO(stream.read())
        payload.name = (document or {}).get("file_name") or os.path.basename(path)
        payload.type = "application/pdf"
        attachments.append(payload)
    return attachments
