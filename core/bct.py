"""Obliczenia wytrzymałości BCT niezależne od ekranu Streamlit."""

from __future__ import annotations

from typing import Iterable


def calculate_bct(
    ect_kn_m: float,
    thickness_mm: float,
    box_length_mm: float,
    box_width_mm: float,
    box_weight_kg: float,
    layers: int,
    weakening_features: Iterable[object] = (),
    safety_factor: float = 1.8,
    laboratory_bct_kg: float = 0.0,
    use_laboratory_result: bool = False,
) -> dict[str, float | int | str]:
    """Zwraca wynik McKee, obciążenie bezpieczne, warstwy i klasyfikację ryzyka."""
    ect = max(0.0, float(ect_kn_m))
    thickness = max(0.0, float(thickness_mm))
    perimeter = max(0.0, 2 * (float(box_length_mm) + float(box_width_mm)))
    weight = max(0.0, float(box_weight_kg))
    layer_count = max(1, int(layers))
    factor = max(0.55, 1 - 0.08 * len(list(weakening_features)))
    mckee_bct = 5.87 * ect * (thickness * perimeter) ** 0.5 * factor if thickness and perimeter else 0.0
    bct = max(0.0, float(laboratory_bct_kg)) if use_laboratory_result and laboratory_bct_kg > 0 else mckee_bct
    safe_bct = bct / max(1.0, float(safety_factor))
    load = weight * (layer_count - 1)
    max_layers = max(1, int(safe_bct // weight) + 1) if weight else 1
    max_pallet_mass = round(max_layers * weight, 2)
    margin_pct = ((safe_bct - load) / load * 100) if load else 100.0
    risk = "bezpieczne" if load <= safe_bct * 0.7 else "warunkowo bezpieczne" if load <= safe_bct else "ryzykowne" if load <= safe_bct * 1.2 else "niedopuszczalne"
    return {
        "mckee_bct": mckee_bct, "bct": bct, "safe_bct": safe_bct, "total_load": load,
        "max_safe_layers": max_layers, "max_safe_pallet_mass_kg": max_pallet_mass,
        "margin_pct": margin_pct, "risk": risk,
    }
