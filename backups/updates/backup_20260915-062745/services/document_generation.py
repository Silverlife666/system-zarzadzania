"""Wspólne dane prezentowane w dokumentach PDF."""

from __future__ import annotations

from typing import Any


def bct_document_rows(result: dict[str, Any] | None) -> list[list[str]]:
    result = result or {}
    if not result:
        return []
    signatures = result.get("signatures", {}) or {}
    return [
        ["OCENA BCT", ""],
        ["BCT nominalne", f"{float(result.get('bct', 0) or 0):.1f} kg"],
        ["Bezpieczne BCT", f"{float(result.get('safe_bct', 0) or 0):.1f} kg"],
        ["Maks. warstwy", str(result.get("max_safe_layers", "-"))],
        ["Ryzyko", str(result.get("risk", "-"))],
        ["Rekomendacja", str(result.get("recommendation", "-"))],
        ["Status", str(result.get("approval", "-"))],
        ["Podpisy", " / ".join(str(value) for value in signatures.values())],
    ]
