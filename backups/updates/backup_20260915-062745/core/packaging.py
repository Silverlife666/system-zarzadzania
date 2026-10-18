"""Przeliczenia poziomów opakowania: Produkt, Display i Master Case."""

from __future__ import annotations

from math import ceil
from typing import Any, Mapping


def _as_non_negative_int(value: Any, default: int = 0) -> int:
    """Zwraca liczbę całkowitą bezpieczną dla ilości w formularzach."""
    try:
        return max(0, int(float(value)))
    except (TypeError, ValueError):
        return default


def packaging_level_quantities(
    quantity: Any,
    level: str,
    relations: Mapping[str, Any] | None = None,
) -> dict[str, int]:
    """Przelicza ilość z wybranego poziomu na wszystkie poziomy opakowania.

    ``quantity`` oznacza zawsze ilość wybraną przez użytkownika. Relacje są
    odporne na puste pola — minimalna wartość logistyczna to 1.
    """
    relations = relations or {}
    displays_per_mastercase = max(
        1,
        _as_non_negative_int(
            relations.get("displays_per_mastercase", relations.get("Displayów w Master Case", 1)),
            1,
        ),
    )
    boxes_per_display = max(
        1,
        _as_non_negative_int(
            relations.get("boxes_per_display", relations.get("Pudełek w displayu", 1)),
            1,
        ),
    )
    pieces_per_box = max(
        1,
        _as_non_negative_int(
            relations.get("pieces_per_box", relations.get("Sztuk w pudełku", 1)),
            1,
        ),
    )
    selected_quantity = _as_non_negative_int(quantity)
    pieces_per_display = boxes_per_display * pieces_per_box

    if level == "Produkt":
        products = selected_quantity
        displays = ceil(products / pieces_per_display) if products else 0
        mastercases = ceil(displays / displays_per_mastercase) if displays else 0
    elif level == "Display":
        displays = selected_quantity
        products = displays * pieces_per_display
        mastercases = ceil(displays / displays_per_mastercase) if displays else 0
    elif level == "Master Case":
        mastercases = selected_quantity
        displays = mastercases * displays_per_mastercase
        products = displays * pieces_per_display
    else:
        raise ValueError("Nieznany poziom opakowania. Wybierz: Produkt, Display albo Master Case.")

    return {
        "produktow": products,
        "displayow": displays,
        "mastercase": mastercases,
        "pudelek": displays * boxes_per_display,
        "pieces_per_display": pieces_per_display,
        "pieces_per_mastercase": displays_per_mastercase * pieces_per_display,
        "displays_per_mastercase": displays_per_mastercase,
    }
