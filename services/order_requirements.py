"""Reguły kompletności dokumentów zlecenia, niezależne od magazynu i Streamlit."""

from __future__ import annotations

from typing import Any, Callable


def requirement_status(record: dict[str, Any], context: dict[str, Any], default_requirements: list[str], *, document_ready: Callable[[str, list[dict[str, Any]]], bool]) -> tuple[list[str], dict[str, bool]]:
    """Wyznacza spełnienie profilu dokumentów; BCT wymaga jawnego zatwierdzenia."""
    record, context = record or {}, context or {}
    requirements = list(record.get("required_documents") or default_requirements)
    documents = record.get("documents", []) or []
    bct = context.get("bct_last_result", {}) or {}
    bct_approved = str(bct.get("approval", "")).strip().lower() == "zatwierdzony"
    if not bct_approved:
        bct_approved = any(
            "bct" in str(document.get("type", "")).lower()
            and str((document.get("metadata", {}) or {}).get("approval", "")).strip().lower() == "zatwierdzony"
            for document in documents
        )
    checks = {key: document_ready(key, documents) for key in (
        "tds", "eorder", "worksheet", "packing_list", "ppwr", "declaration_compliance", "declaration_production_date", "qa",
    )}
    checks["bct"] = bct_approved
    return requirements, checks
